#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一鍵把整套跑起來（Windows / macOS / Linux 都可以）。

    python run.py                前端 5174 ＋ 後端 8000，第一次會自己裝好、建好
    python run.py --front-only   只跑前端（mock 模式，不需要後端）
    python run.py --reset        把本機資料庫砍掉重建（dev.db 才有效）
    python run.py --port 5555    換前端的埠號（後端用 --api-port）

做的事，照順序：

    1. 檢查 Python 版本
    2. 套件沒裝好就 pip install -r backend/requirements.txt
    3. backend/.env 不存在就建出來（順便產生 JWT_SECRET）
    4. alembic upgrade head    建表
    5. python -m app.cli init-db   放入系統預設分類
    6. 同時起 uvicorn（後端）與一個靜態伺服器（前端），印出網址

⚠️ 前端不要用 VS Code 的 Live Server 或直接點開 index.html：
   那樣後端的 CORS 會擋住（來源對不上），而且 file:// 不算 localhost。
   一律用這支跑出來的 http://localhost:5174。
"""
from __future__ import annotations

import argparse
import functools
import http.server
import os
import shutil
import socket
import socketserver
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(ROOT, "backend")
FRONTEND = os.path.join(ROOT, "frontend")
PY = sys.executable                      # 用「現在這一支」python，不要用 PATH 上的別支


# ======================================================================
# 印字
# ======================================================================
def say(msg: str = "") -> None:
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def step(n: int, total: int, msg: str) -> None:
    say("[%d/%d] %s" % (n, total, msg))


def die(msg: str) -> "None":
    say("")
    say("✗ " + msg)
    sys.exit(1)


# ======================================================================
# 前置檢查
# ======================================================================
def check_python() -> None:
    if sys.version_info < (3, 10):
        die("Python 太舊了（現在是 %s），請裝 3.10 以上。\n"
            "  Windows：https://www.python.org/downloads/ ，安裝時記得勾 Add python.exe to PATH"
            % sys.version.split()[0])


def deps_ready() -> bool:
    """只看幾個關鍵套件，不用每次都跑 pip（pip 很慢）。"""
    try:
        import alembic            # noqa: F401
        import fastapi            # noqa: F401
        import sqlalchemy         # noqa: F401
        import uvicorn            # noqa: F401
        return True
    except ImportError:
        return False


def install_deps() -> None:
    req = os.path.join(BACKEND, "requirements.txt")
    say("    第一次跑，要先裝套件（大概一兩分鐘）…")
    code = subprocess.call([PY, "-m", "pip", "install", "-r", req])
    if code != 0:
        die("套件裝不起來。手動跑一次看錯誤訊息：\n    %s -m pip install -r %s" % (PY, req))


def run_cli(*args: str, why: str = "") -> None:
    """跑 backend 底下的指令，失敗就停下來講清楚。"""
    code = subprocess.call([PY] + list(args), cwd=BACKEND)
    if code != 0:
        die("%s失敗了（上面有錯誤訊息）。\n    在 backend/ 底下手動跑一次：%s"
            % (why, " ".join(["python"] + list(args))))


def ensure_env() -> None:
    env = os.path.join(BACKEND, ".env")
    if os.path.exists(env):
        return
    say("    backend/.env 還沒有，先建一份（JWT_SECRET 會自動產生）")
    run_cli("-m", "app.cli", "init-env", why="建立 .env ")


def sqlite_file() -> str | None:
    """.env 用的是 SQLite 的話，回傳那個檔案的路徑；用 PostgreSQL 回 None。"""
    env = os.path.join(BACKEND, ".env")
    if not os.path.exists(env):
        return None
    for line in open(env, encoding="utf-8"):
        line = line.strip()
        if line.startswith("DATABASE_URL=") and "sqlite" in line:
            name = line.split("///")[-1].strip()
            return os.path.join(BACKEND, name.lstrip("./"))
    return None


# ======================================================================
# 埠號
# ======================================================================
def port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", port)) == 0


def check_ports(front: int, api: int, front_only: bool) -> None:
    for port, what in ((front, "前端"), (api, "後端")):
        if what == "後端" and front_only:
            continue
        if port_busy(port):
            die("%s要用的 %d 埠已經有別的程式在用了。\n"
                "  先把上一次開的視窗關掉，或換一個埠：python run.py %s %d"
                % (what, port, "--port" if what == "前端" else "--api-port", port + 1))


# ======================================================================
# 前端：靜態伺服器
# ======================================================================
class QuietHandler(http.server.SimpleHTTPRequestHandler):
    """只印錯誤，不要每抓一個 .css 就印一行。"""

    def log_message(self, fmt, *args):       # noqa: A003
        if not str(args[0] if args else "").startswith(("GET", "HEAD")):
            super().log_message(fmt, *args)

    def end_headers(self):
        # 改了 js/css 重新整理就要看到新的，不要讓瀏覽器拿快取
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def serve_frontend(port: int) -> socketserver.TCPServer:
    handler = functools.partial(QuietHandler, directory=FRONTEND)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


# ======================================================================
# 主程式
# ======================================================================
def main() -> None:
    ap = argparse.ArgumentParser(description="一鍵把家庭記帳跑起來")
    ap.add_argument("--front-only", action="store_true", help="只跑前端（mock 模式）")
    ap.add_argument("--reset", action="store_true", help="砍掉本機的 SQLite 重建")
    ap.add_argument("--port", type=int, default=5174, help="前端的埠號（預設 5174）")
    ap.add_argument("--api-port", type=int, default=8000, help="後端的埠號（預設 8000）")
    args = ap.parse_args()

    check_python()
    check_ports(args.port, args.api_port, args.front_only)

    front_url = "http://localhost:%d" % args.port
    api_url = "http://localhost:%d" % args.api_port

    if args.front_only:
        say("")
        say("前端（mock 模式，資料存在瀏覽器裡）")
        say("    %s/?api=" % front_url)
        say("")
        say("停止：Ctrl+C")
        httpd = serve_frontend(args.port)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            httpd.shutdown()
            say("\n關掉了。")
        return

    total = 5
    step(1, total, "檢查套件")
    if not deps_ready():
        install_deps()

    step(2, total, "檢查設定檔")
    ensure_env()

    if args.reset:
        db = sqlite_file()
        if db and os.path.exists(db):
            os.remove(db)
            say("    砍掉了 %s" % os.path.relpath(db, ROOT))
        elif not db:
            say("    你的 .env 用的不是 SQLite，--reset 不動它（請自己處理那顆資料庫）")

    step(3, total, "建立資料表")
    if not shutil.which("alembic"):
        run_cli("-m", "alembic", "upgrade", "head", why="建表 ")
    else:
        code = subprocess.call(["alembic", "upgrade", "head"], cwd=BACKEND)
        if code != 0:
            die("建表失敗（上面有錯誤訊息）。\n"
                "  最常見的原因是 backend/.env 的 DATABASE_URL 指到一顆沒開的 PostgreSQL。\n"
                "  本機不用 PostgreSQL 的話，把那一行改成：DATABASE_URL=sqlite:///./dev.db")

    step(4, total, "放入系統預設分類")
    run_cli("-m", "app.cli", "init-db", why="建立預設分類 ")

    step(5, total, "啟動")
    httpd = serve_frontend(args.port)
    api = subprocess.Popen(
        [PY, "-m", "uvicorn", "app.main:app", "--reload",
         "--host", "127.0.0.1", "--port", str(args.api_port)],
        cwd=BACKEND,
    )

    say("")
    say("=" * 62)
    say("  前端      %s/?api=%s" % (front_url, api_url))
    say("  後端      %s" % api_url)
    say("  API 文件  %s/docs   ← 可以直接在上面試打" % api_url)
    say("")
    say("  第一次打開請用上面那一行**完整的**前端網址（帶 ?api=…）——")
    say("  它會把「要連哪個後端」記在這台瀏覽器裡，之後開 %s 就好。" % front_url)
    say("  要切回 mock（不連後端）：%s/?api=" % front_url)
    say("")
    say("  停止：Ctrl+C")
    say("=" * 62)

    try:
        api.wait()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()
        if api.poll() is None:
            api.terminate()
            try:
                api.wait(timeout=5)
            except subprocess.TimeoutExpired:
                api.kill()
        say("\n關掉了。")


if __name__ == "__main__":
    main()
