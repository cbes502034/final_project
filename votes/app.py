"""
選題投票服務
------------
四人各選一題，共用一份選擇結果。

儲存優先序：
  1. 有 DATABASE_URL  → PostgreSQL（正式部署用，重啟不會遺失）
  2. 沒有             → 本機 JSON 檔（開發用；雲端免費方案重啟會遺失）

刻意保持極小：沒有帳號、沒有密碼，只用固定的四個名字做白名單。
這是給四個人自己用的內部工具，不是公開服務。
"""
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

MEMBERS = ("冠文", "明樺", "囷洧", "宇傑")
MAX_PROJECT_ID_LEN = 8

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
JSON_PATH = Path(os.getenv("PICKS_FILE", "picks.json"))
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv(
        "ALLOWED_ORIGINS",
        "https://llm-capstone-top20.onrender.com,http://localhost:5173",
    ).split(",") if o.strip()
]

app = FastAPI(title="Capstone Pick Service", docs_url=None, redoc_url=None)
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
def set_pick(body: PickIn):
    store.put(
        body.member, body.project, datetime.now(timezone.utc).isoformat()
    )
    return _payload()


@app.delete("/api/picks/{member}")
def clear_pick(member: str):
    if member not in MEMBERS:
        raise HTTPException(status_code=404, detail="unknown member")
    store.delete(member)
    return _payload()


@app.get("/healthz")
def healthz():
    return {"ok": True, "backend": backend}
