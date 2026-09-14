"""
後端的小工具指令。在 backend/ 底下跑：

    python -m app.cli init-env            從 .env.example 建出 .env，順便產生一組 JWT_SECRET
    python -m app.cli check-config        列出每一段設定填了沒、沒填會怎樣
    python -m app.cli init-db             建表（本機、測試用）＋ 放入系統預設分類
    python -m app.cli make-admin [email]  把帳號設成平台管理員（不給 email 就用 ADMIN_EMAILS）

負責人：成員1（共用元件）

⚠️ 正式環境建表用 Alembic：`alembic upgrade head`。init-db 的 create_all 不會幫你改既有的表。
"""

from __future__ import annotations

import argparse
import io
import os
import secrets
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)

#: 系統預設分類。⚠️ 跟 frontend/js/data.js 的 categories 名稱、收支、顏色一致（測試會比對）
SYSTEM_CATEGORIES = [
    ("餐飲", "expense", "cat-food"), ("交通", "expense", "cat-transit"), ("居住", "expense", "cat-home"),
    ("日用品", "expense", "cat-daily"), ("娛樂", "expense", "cat-fun"), ("教育", "expense", "cat-study"),
    ("醫療", "expense", "cat-health"), ("其他", "expense", "cat-other"),
    ("薪資", "income", "cat-daily"), ("獎金", "income", "cat-bonus"), ("零用金", "income", "cat-transit"),
    ("其他收入", "income", "cat-other"),
]


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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.cli", description="家庭記帳後端的小工具")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init-env", help="從 .env.example 建出 .env")
    p.add_argument("--force", action="store_true")
    sub.add_parser("check-config", help="列出設定填了沒")
    sub.add_parser("init-db", help="建表＋系統預設分類")
    p = sub.add_parser("make-admin", help="設定平台管理員")
    p.add_argument("email", nargs="?")
    args = ap.parse_args(argv)
    if args.cmd == "init-env":
        return init_env(args.force)
    if args.cmd == "check-config":
        return check_config()
    if args.cmd == "init-db":
        return init_db()
    return make_admin(args.email)


if __name__ == "__main__":
    raise SystemExit(main())
