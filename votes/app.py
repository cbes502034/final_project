"""
選題投票服務
------------
四人各選一題，共用一份選擇結果。

儲存優先序：
  1. 有 DATABASE_URL  → PostgreSQL（正式部署用，重啟不會遺失）
  2. 沒有             → 本機 JSON 檔（開發用；雲端免費方案重啟會遺失）

即時更新：
  GET /api/stream 是 Server-Sent Events。整個服務只有「一個」背景工作在輪詢
  儲存層，發現有變動才推給所有連線中的瀏覽器，所以連線數再多也不會加重資料庫。
  自己送出的 PUT / DELETE 會直接廣播，不必等下一次輪詢。

刻意保持極小：沒有帳號、沒有密碼，只用固定的四個名字做白名單。
這是給四個人自己用的內部工具，不是公開服務。
"""
import asyncio
import json
import os
import threading
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

MEMBERS = ("冠文", "明樺", "囷洧", "宇傑")
MAX_PROJECT_ID_LEN = 8

# 背景輪詢間隔；代理層通常 30–60 秒無資料就砍連線，所以心跳要比那個短
POLL_SECONDS = 1.0
HEARTBEAT_SECONDS = 15.0

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
JSON_PATH = Path(os.getenv("PICKS_FILE", "picks.json"))
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv(
        "ALLOWED_ORIGINS",
        "https://llm-capstone-top20.onrender.com,http://localhost:5173",
    ).split(",") if o.strip()
]

_subscribers: "set[asyncio.Queue]" = set()
_last_signature = None


LF = chr(10)


def _sse(payload):
    """組一個 SSE 訊框：data 行 + 空行結尾。"""
    return "data: " + json.dumps(payload, ensure_ascii=False) + LF + LF


def _signature(payload):
    return json.dumps(payload["picks"], sort_keys=True, ensure_ascii=False)


def _broadcast(payload):
    """把最新狀態丟給所有連線中的瀏覽器。慢的連線就讓它掉，不拖累其他人。"""
    global _last_signature
    _last_signature = _signature(payload)
    for q in list(_subscribers):
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            _subscribers.discard(q)


async def _watch_store():
    """全服務只有這一個輪詢者，所以資料庫負擔與連線人數無關。"""
    global _last_signature
    while True:
        try:
            payload = await asyncio.to_thread(_payload)
            if _signature(payload) != _last_signature:
                _broadcast(payload)
        except Exception as exc:
            print(f"[picks] watcher error: {exc}")
        await asyncio.sleep(POLL_SECONDS)


@asynccontextmanager
async def lifespan(_app):
    task = asyncio.create_task(_watch_store())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title="Capstone Pick Service", docs_url=None, redoc_url=None, lifespan=lifespan
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)

_lock = threading.Lock()


# ---------------------------------------------------------------- storage
class JsonStore:
    """開發與降級用。雲端免費方案沒有持久磁碟，重啟會清空。"""

    def read(self):
        if not JSON_PATH.exists():
            return {}
        try:
            return json.loads(JSON_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def write(self, data):
        JSON_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def all(self):
        return self.read()

    def put(self, member, project, ts):
        with _lock:
            data = self.read()
            data[member] = {"project": project, "updated_at": ts}
            self.write(data)

    def delete(self, member):
        with _lock:
            data = self.read()
            existed = data.pop(member, None) is not None
            self.write(data)
            return existed


class PgStore:
    def __init__(self, url):
        import psycopg  # 只有走這條路才需要

        self._psycopg = psycopg
        self._url = url
        with self._conn() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS picks (
                    member     TEXT PRIMARY KEY,
                    project    TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )

    def _conn(self):
        return self._psycopg.connect(self._url, autocommit=True)

    def all(self):
        with self._conn() as c:
            rows = c.execute(
                "SELECT member, project, updated_at FROM picks"
            ).fetchall()
        return {
            m: {"project": p, "updated_at": u.isoformat()} for m, p, u in rows
        }

    def put(self, member, project, ts):
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO picks (member, project, updated_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (member)
                DO UPDATE SET project = EXCLUDED.project,
                              updated_at = EXCLUDED.updated_at
                """,
                (member, project, ts),
            )

    def delete(self, member):
        with self._conn() as c:
            return c.execute(
                "DELETE FROM picks WHERE member = %s", (member,)
            ).rowcount > 0


def _build_store():
    if DATABASE_URL:
        try:
            return PgStore(DATABASE_URL), "postgres"
        except Exception as exc:  # 資料庫還沒好時不要讓整個服務起不來
            print(f"[picks] PostgreSQL unavailable, falling back to JSON: {exc}")
    return JsonStore(), "json"


store, backend = _build_store()


# ---------------------------------------------------------------- schema
class PickIn(BaseModel):
    member: str
    project: str

    @field_validator("member")
    @classmethod
    def known_member(cls, v):
        v = v.strip()
        if v not in MEMBERS:
            raise ValueError("unknown member")
        return v

    @field_validator("project")
    @classmethod
    def valid_project(cls, v):
        v = v.strip()
        if not v or len(v) > MAX_PROJECT_ID_LEN or not v.isalnum():
            raise ValueError("invalid project id")
        return v


# ---------------------------------------------------------------- routes
def _payload():
    data = store.all()
    picks = [
        {"member": m, "project": d["project"], "updated_at": d["updated_at"]}
        for m, d in data.items()
        if m in MEMBERS
    ]
    picks.sort(key=lambda p: MEMBERS.index(p["member"]))
    return {"picks": picks, "members": list(MEMBERS), "backend": backend}


@app.get("/api/picks")
def list_picks():
    return _payload()


@app.put("/api/picks")
async def set_pick(body: PickIn):
    await asyncio.to_thread(
        store.put, body.member, body.project, datetime.now(timezone.utc).isoformat()
    )
    payload = await asyncio.to_thread(_payload)
    _broadcast(payload)          # 不必等下一次輪詢，其他人立刻看到
    return payload


@app.delete("/api/picks/{member}")
async def clear_pick(member: str):
    if member not in MEMBERS:
        raise HTTPException(status_code=404, detail="unknown member")
    await asyncio.to_thread(store.delete, member)
    payload = await asyncio.to_thread(_payload)
    _broadcast(payload)
    return payload


@app.get("/api/stream")
async def stream(request: Request):
    """Server-Sent Events：一有人改選擇，其他人畫面立刻更新。"""
    queue: asyncio.Queue = asyncio.Queue(maxsize=8)
    _subscribers.add(queue)

    async def events():
        try:
            first = await asyncio.to_thread(_payload)
            yield _sse(first)
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(
                        queue.get(), timeout=HEARTBEAT_SECONDS
                    )
                except asyncio.TimeoutError:
                    yield ": keep-alive" + LF + LF     # 讓代理層不要砍掉閒置連線
                    continue
                yield _sse(payload)
        finally:
            _subscribers.discard(queue)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",     # 關掉反向代理的緩衝，否則會積在中間
            "Connection": "keep-alive",
        },
    )


@app.get("/healthz")
def healthz():
    return {"ok": True, "backend": backend}
