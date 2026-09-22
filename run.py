#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一鍵把整套跑起來（Windows / macOS / Linux 都可以）。

    python run.py                前端 5174 ＋ 後端 8000，第一次會自己裝好、建好
    python run.py --front-only   只跑前端（mock 模式，不需要後端，也不需要 Docker）
    python run.py --reset        把本機資料庫砍掉重建
    python run.py --port 5555    換前端的埠號（後端用 --api-port）

需要：Python 3.10 以上、Docker Desktop（要先打開）。
本機的資料庫跟正式環境一樣是 PostgreSQL，跑在 Docker 裡（docker-compose.yml 的 db）。

做的事，照順序：

    1. 檢查 Python 版本
    2. 套件沒裝好就 pip install -r backend/requirements.txt
    3. backend/.env 不存在就建出來（順便產生 JWT_SECRET）
    4. docker compose up -d --wait db   開 PostgreSQL，等到真的能連
    5. alembic upgrade head    建表
    6. python -m app.cli init-db     放入系統預設分類
    7. python -m app.cli seed-team   建立四位成員的開發用帳號（密碼都是 abcd1234）
    8. 同時起 uvicorn（後端）與一個靜態伺服器（前端），印出網址

關掉 run.py（Ctrl+C）不會關掉 PostgreSQL，資料也還在。要關它：docker compose stop db

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
# Windows 的主控台預設是 cp950，印不出「✗」「█」這類字元會直接 UnicodeEncodeError，
# 而且是在**報錯的那條路徑上**爆掉 —— 使用者看到的會是一串 traceback，不是我們寫的說明。
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def say(msg: str = "") -> None:
    try:
        sys.stdout.write(msg + "\n")
    except UnicodeEncodeError:           # 真的還是印不出來，就退成 ASCII，訊息至少看得到
        sys.stdout.write(msg.encode("ascii", "replace").decode("ascii") + "\n")
    sys.stdout.flush()


def step(n: int, total: int, msg: str) -> None:
    say("[%d/%d] %s" % (n, total, msg))


def die(msg: str) -> "None":
    say("")
    say("[停下來了] " + msg)
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


def env_line(key: str) -> str | None:
    """讀 backend/.env 裡某一行的值（沒有就回 None）。"""
    env = os.path.join(BACKEND, ".env")
    if not os.path.exists(env):
        return None
    for line in open(env, encoding="utf-8"):
        line = line.strip()
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip()
    return None


def sqlite_file() -> str | None:
    """.env 用的是 SQLite 的話，回傳那個檔案的路徑；用 PostgreSQL 回 None。"""
    url = env_line("DATABASE_URL")
    if not url or "sqlite" not in url:
        return None
    return os.path.join(BACKEND, url.split("///")[-1].strip().lstrip("./"))


def local_postgres() -> bool:
    """.env 指的是本機 Docker 裡那顆 PostgreSQL（docker-compose.yml 的 db）嗎？"""
    url = env_line("DATABASE_URL") or ""
    return url.startswith("postgresql") and ("@localhost" in url or "@127.0.0.1" in url)


def ensure_postgres(reset: bool) -> None:
    """用 docker compose 把 PostgreSQL 開起來，等到它真的能連才往下走。

    本機跟正式環境（Render）用同一種資料庫，本機寫得對，部署上去就一樣對。
    資料存在 Docker 的 volume 裡（pgdata），關掉 run.py 甚至重開機都還在。
    """
    if not shutil.which("docker"):
        die("找不到 docker。本機的資料庫跑在 Docker 裡，請先安裝 Docker Desktop：\n"
            "    https://www.docker.com/products/docker-desktop/\n"
            "  裝好之後打開它，等它顯示「Engine running」再跑一次 python run.py。")
    if subprocess.call(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
        die("Docker 沒有在執行。請先打開 Docker Desktop，等它顯示「Engine running」，\n"
            "  再跑一次 python run.py。\n"
            "  （Docker Desktop 一打開就跳錯誤、訊息裡有 Inference manager 的話，\n"
            "    看 README 的「Docker Desktop 一打開就跳「An unexpected error occurred」」那一段。）")
    if reset:
        say("    砍掉本機資料庫重建（docker compose down -v）")
        subprocess.call(["docker", "compose", "down", "-v"], cwd=ROOT)
    say("    docker compose up -d --wait db（第一次會下載 PostgreSQL，要等一下）")
    if subprocess.call(["docker", "compose", "up", "-d", "--wait", "db"], cwd=ROOT) != 0:
        die("PostgreSQL 起不來（上面有 Docker 的錯誤訊息）。\n"
            "  最常見的是 5432 埠被別的程式占用（例如電腦上另外裝了 PostgreSQL）：\n"
            "    Windows    netstat -ano | findstr :5432\n"
            "  關掉它之後再跑一次。")


def api_env(front_port: int) -> dict:
    """給 uvicorn 的環境變數。

    ⚠️ 只為了一件事：**把前端實際用的埠號加進 ALLOWED_ORIGINS**。
    .env 裡寫死的是 5174，`python run.py --port 5555` 的話瀏覽器就會被 CORS 擋住，
    而畫面上只會說「連不上後端」—— 很難看出是埠號的問題。
    環境變數的優先權高於 .env，所以這裡不用去動使用者的檔案。
    """
    env = dict(os.environ)
    origins = [o for o in (env_line("ALLOWED_ORIGINS") or "").split(",") if o.strip()]
    for host in ("localhost", "127.0.0.1"):
        origin = "http://%s:%d" % (host, front_port)
        if origin not in origins:
            origins.append(origin)
    env["ALLOWED_ORIGINS"] = ",".join(origins)
    return env


# ======================================================================
# 埠號
# ======================================================================
def stop_tree(proc: subprocess.Popen) -> None:
    """把 uvicorn 整棵關掉。

    ⚠️ `uvicorn --reload` 是**兩個行程**：監看檔案的 reloader，加上真正跑 app 的 worker。
       只 terminate() 外面那個的話，worker 會活下來繼續占著 8000 埠 ——
       下次再跑 run.py 就會說「埠被占用」，但工作管理員裡看起來什麼都沒開。
    """
    if proc.poll() is not None:
        return
    if os.name == "nt":
        # /T 連子行程一起，/F 強制。Windows 沒有 process group 可以用
        subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


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
                "  1. 先把上一次跑 run.py 的視窗關掉（Ctrl+C）\n"
                "  2. 還是不行的話，找出是誰在用：\n"
                "       Windows    netstat -ano | findstr :%d\n"
                "       Mac／Linux lsof -i :%d\n"
                "  3. 或直接換一個埠：python run.py %s %d"
                % (what, port, port, port,
                   "--port" if what == "前端" else "--api-port", port + 1))


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

    total = 6
    step(1, total, "檢查套件")
    if not deps_ready():
        install_deps()

    step(2, total, "檢查設定檔")
    ensure_env()

    step(3, total, "啟動資料庫")
    if local_postgres():
        ensure_postgres(reset=args.reset)
    else:
        db = sqlite_file()
        say("    backend/.env 用的不是本機的 PostgreSQL，這一步跳過（%s）"
            % ("SQLite：" + os.path.relpath(db, ROOT) if db else env_line("DATABASE_URL")))
        if args.reset and db and os.path.exists(db):
            os.remove(db)
            say("    砍掉了 %s" % os.path.relpath(db, ROOT))

    step(4, total, "建立資料表")
    # 一律用 python -m：PATH 上的 alembic 可能是別的 Python 裝的，套件版本對不上
    run_cli("-m", "alembic", "upgrade", "head", why="建表 ")

    step(5, total, "放入系統預設分類與開發用帳號")
    run_cli("-m", "app.cli", "init-db", why="建立預設分類 ")
    run_cli("-m", "app.cli", "seed-team", why="建立開發用帳號 ")

    step(6, total, "啟動")
    httpd = serve_frontend(args.port)
    api = subprocess.Popen(
        [PY, "-m", "uvicorn", "app.main:app", "--reload",
         "--host", "127.0.0.1", "--port", str(args.api_port)],
        cwd=BACKEND,
        env=api_env(args.port),
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
    say("  登入用上面印出來的那五個帳號，密碼都是 abcd1234。")
    say("  忘記或改壞了：cd backend && python -m app.cli seed-team")
    say("")
    say("  停止：Ctrl+C")
    say("=" * 62)

    try:
        api.wait()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()
        stop_tree(api)
        say("\n關掉了。")


if __name__ == "__main__":
    main()
