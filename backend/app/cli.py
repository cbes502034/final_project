"""
後端的小工具指令。在 backend/ 底下跑：

    python -m app.cli init-env            從 .env.example 建出 .env，順便產生一組 JWT_SECRET
    python -m app.cli check-config        列出每一段設定填了沒、沒填會怎樣
    python -m app.cli init-db             建表（本機、測試用）＋ 放入系統預設分類
    python -m app.cli make-admin [email]  把帳號設成平台管理員（不給 email 就用 ADMIN_EMAILS）
    python -m app.cli db [SQL]            看資料庫：不給 SQL 就列出每張表有幾筆
    python -m app.cli seed-team           建立四位成員的開發用帳號（只在本機，正式環境會拒絕）

負責人：成員1（共用元件）

⚠️ 正式環境建表用 Alembic：`alembic upgrade head`。init-db 的 create_all 不會幫你改既有的表。
"""

from __future__ import annotations

import argparse
import io
import os
import secrets
import sys

from app import catalog

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)

#: 系統預設分類：(名稱, 收支, 顏色)。正本在 app/catalog.py（跟 frontend/js/data.js 的 categories 一致，測試會比對）
SYSTEM_CATEGORIES = [(name, kind, color) for name, kind, color, _icon in catalog.SYSTEM_CATEGORIES]


def _say(text: str) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")        # Windows 主控台預設 cp950
    except Exception:
        pass
    print(text)


def init_env(force: bool = False) -> int:
    src, dst = os.path.join(BACKEND, ".env.example"), os.path.join(BACKEND, ".env")
    if os.path.exists(dst) and not force:
        _say("backend/.env 已經存在，不覆蓋（要重建加 --force）。")
        return 1
    text = io.open(src, encoding="utf-8").read()
    text = text.replace("\nJWT_SECRET=\n", "\nJWT_SECRET=%s\n" % secrets.token_urlsafe(48))
    io.open(dst, "w", encoding="utf-8", newline="").write(text)
    _say("建好了 backend/.env（JWT_SECRET 已經自動產生）。接著打開它把自己那一段填一填，再跑 check-config。")
    return 0


def check_config() -> int:
    try:
        from app.toolkit.config import settings
    except Exception as exc:                          # 必填的沒填，Settings 會直接起不來
        _say("設定讀不起來：%s\n先跑 python -m app.cli init-env，再把 .env 填好。" % exc)
        return 1
    rows = settings.report()
    width = max(len(r[1]) for r in rows)
    current = None
    for section, name, status in rows:
        if section != current:
            _say("\n【%s】" % section)
            current = section
        _say("  %-*s  %s" % (width, name, status))
    _say("\n目前資料庫：%s" % settings.database_url.split("@")[-1])
    return 0


def init_db() -> int:
    from app.models import Category
    from app.toolkit import crud, db

    db.create_all()
    have = set(crud.find(Category, {"family_id__isnull": True}, fields="name"))
    new = [{"name": n, "kind": k, "color": c, "sort_order": i} for i, (n, k, c) in enumerate(SYSTEM_CATEGORIES) if n not in have]
    if new:
        crud.save(Category, new)
    _say("表都建好了；系統分類新增 %d 個（原本有 %d 個）。" % (len(new), len(have)))
    return 0


def make_admin(email: str | None) -> int:
    from app.models import User
    from app.toolkit import crud
    from app.toolkit.config import settings

    emails = [email.strip().lower()] if email else settings.admin_email_list
    if not emails:
        _say("沒有指定 email，ADMIN_EMAILS 也是空的。")
        return 1
    for e in emails:
        n = crud.save(User, {"is_platform_admin": True}, where={"email": e})
        _say(("%s 設成平台管理員了" if n else "找不到 %s（要先註冊）") % e)
    return 0


#: 四位成員的開發用帳號。帳號＝路由資料夾的名字，四個人共用同一組密碼。
#: ⚠️ 密碼不能是「12345678」：toolkit/passwords.check_strength 擋全部都是數字的密碼
#:    （長度 ≥ 8 而且不可全數字）。那是產品規則，不為了測試帳號放寬。
TEAM_PASSWORD = "abcd1234"

TEAM: list[tuple[str, str, str]] = [
    ("auth", "成員一", "成員1 · 認證"),
    ("ledger", "成員二", "成員2 · 記帳"),
    ("analytics", "成員三", "成員3 · 數字"),
    ("access", "成員四", "成員4 · 家庭"),
    ("admin", "管理員", "平台管理員（測 admin/ 那三支用）"),
]
TEAM_DOMAIN = "fambudget.tw"


def seed_team() -> int:
    """建立（或重設）四位成員的開發用帳號。

    ⚠️ **只給本機開發用。** 密碼是公開寫在文件裡的，正式環境有這種帳號等於沒有密碼，
       所以 APP_ENV=production 時直接拒絕。

    可以重複跑：帳號已經在了就把密碼重設回來（有人改過密碼、忘了密碼時很好用）。
    """
    from datetime import datetime, timezone

    from app.models import User
    from app.toolkit import crud, passwords
    from app.toolkit.config import settings

    if settings.app_env == "production":
        _say("APP_ENV=production，不建立開發用帳號。")
        return 1

    rows = []
    for key, name, role in TEAM:
        email = "%s@%s" % (key, TEAM_DOMAIN)
        password = TEAM_PASSWORD
        data = {
            "display_name": name,
            "password_hash": passwords.hash_password(password),
            "theme": "paper",
            "is_platform_admin": key == "admin",
            "suspended_at": None,
            "suspended_reason": None,
            # 設過了就不用走註冊後的個人化設定，登入直接進總覽
            "onboarded_at": datetime.now(timezone.utc),
        }
        before = crud.get(User, where={"email": email})
        crud.save(User, dict(data, email=email), where={"email": email}, upsert=True)
        rows.append((email, password, name, role, "已存在，重設密碼" if before else "新建"))

    width = max(len(e) for e, *_ in rows)
    _say("開發用帳號（只在你這台機器上）：\n")
    _say("  %-*s  %-16s  %-6s  %s" % (width, "帳號", "密碼", "名字", "誰用"))
    _say("  %s" % ("-" * (width + 46)))
    for email, password, name, role, what in rows:
        _say("  %-*s  %-16s  %-6s  %s（%s）" % (width, email, password, name, role, what))
    _say("\n拿去登入前端，或在 /docs 上按 Authorize。密碼忘了就再跑一次這個指令。")
    return 0


def db(sql: str | None) -> int:
    """看自己剛剛寫進去的資料長什麼樣子。

    不裝任何工具、不離開終端機就看得到——做一支路由的過程裡，
    「我到底有沒有寫進去、寫成什麼樣」是最常問的問題。

    ⚠️ 只讓查（SELECT／PRAGMA／WITH）。這支是開發用的，
       不想有人用它一行 DELETE 把自己的資料清掉。
    """
    from sqlalchemy import inspect, text

    from app.toolkit.db import engine

    if not sql:
        names = sorted(inspect(engine).get_table_names())
        with engine.connect() as conn:
            rows = [(t, conn.execute(text("SELECT COUNT(*) FROM %s" % t)).scalar()) for t in names]
        width = max(len(t) for t, _ in rows) if rows else 0
        _say("\n".join("%-*s  %s 筆" % (width, t, n) for t, n in rows) or "一張表都還沒有，先跑 init-db")
        return 0

    if not sql.lstrip().lower().startswith(("select", "pragma", "with")):
        _say("只能查（SELECT／PRAGMA／WITH）。要改資料請寫在路由或測試裡。")
        return 1

    with engine.connect() as conn:
        result = conn.execute(text(sql))
        cols = list(result.keys())
        rows = [["" if v is None else str(v) for v in r] for r in result.fetchall()]
    if not rows:
        _say("查不到資料（0 筆）。")
        return 0
    width = [max(len(cols[i]), *(len(r[i]) for r in rows)) for i in range(len(cols))]
    line = "  ".join("-" * w for w in width)
    _say("  ".join("%-*s" % (width[i], c) for i, c in enumerate(cols)))
    _say(line)
    for r in rows:
        _say("  ".join("%-*s" % (width[i], v) for i, v in enumerate(r)))
    _say("%s\n%d 筆" % (line, len(rows)))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.cli", description="家庭記帳後端的小工具")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init-env", help="從 .env.example 建出 .env")
    p.add_argument("--force", action="store_true")
    sub.add_parser("check-config", help="列出設定填了沒")
    sub.add_parser("init-db", help="建表＋系統預設分類")
    p = sub.add_parser("make-admin", help="設定平台管理員")
    p.add_argument("email", nargs="?")
    sub.add_parser("seed-team", help="建立四位成員的開發用帳號")
    p = sub.add_parser("db", help="看資料庫（只能查）")
    p.add_argument("sql", nargs="?", help='例如 "SELECT id, email FROM users"；不給就列出每張表幾筆')
    args = ap.parse_args(argv)
    if args.cmd == "init-env":
        return init_env(args.force)
    if args.cmd == "check-config":
        return check_config()
    if args.cmd == "init-db":
        return init_db()
    if args.cmd == "seed-team":
        return seed_team()
    if args.cmd == "db":
        return db(args.sql)
    return make_admin(args.email)


if __name__ == "__main__":
    raise SystemExit(main())
