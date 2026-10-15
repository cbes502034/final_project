"""
忘記密碼：重設連結的產生、驗證，以及那封信的內容。

負責人：成員1（認證）

===========================================================================
流程
===========================================================================
    1. POST /api/auth/password-reset            { "email": "..." }
       找得到這個人 → new_token()，資料庫存 hash_token()，寄出 reset_link()
       找不到       → 什麼都不做
       ⚠️ **兩種情況回一模一樣的回應（GENERIC_MESSAGE、同一個狀態碼）**

    2. 使用者點信裡的連結 → 前端 #/reset/<token>

    3. POST /api/auth/password-reset/confirm    { "token": "...", "password": "..." }
       用 hash_token(token) 找那一列 → require_usable() → 改密碼
       → used_at = now → **撤銷這個人所有的 sessions**（連結被偷用過，其他裝置也要踢下線）

===========================================================================
⚠️ 五條規則，每一條都有理由
===========================================================================
  * 「沒這個帳號」不能講出來。講了，這支 API 就是帳號列舉工具：
    不用猜密碼，先把「哪些 email 有註冊」撈出來。登入的錯誤訊息是同一個道理。
  * token 只存雜湊。資料庫外流時，拿到的東西點不開任何連結。
  * 30 分鐘失效、只能用一次。信箱被翻到一封舊信，也拿不到帳號。
  * 重寄要冷卻（should_send）。不然任何人都能拿你的 email 一直轟炸你的信箱。
  * 連結的 token 放在網址 # 後面。# 後面的東西瀏覽器**不會送給伺服器**，
    不會出現在伺服器紀錄，也不會跟著 Referer 外洩到別的網站。

===========================================================================
怎麼用
===========================================================================
    from app.toolkit import password_reset as pr, mailer

    token = pr.new_token()
    row = PasswordReset(user_id=u.id, token_hash=pr.hash_token(token), expires_at=pr.expires_at())
    subject, text, html = pr.mail_content(u.display_name, pr.reset_link(settings.app_base_url, token))
    mailer.send_mail(u.email, subject, text, html, to_name=u.display_name)
    return {"ok": True, "message": pr.GENERIC_MESSAGE}
"""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from html import escape

__all__ = [
    "TOKEN_MINUTES", "COOLDOWN_SECONDS", "GENERIC_MESSAGE", "INVALID_MESSAGE",
    "normalize_email", "new_token", "hash_token", "expires_at",
    "require_usable", "should_send", "reset_link", "mail_content",
]

#: 重設連結幾分鐘後失效
TOKEN_MINUTES = 30

#: 同一個人兩次寄信之間至少隔幾秒
COOLDOWN_SECONDS = 60

#: 申請之後一律回這句。⚠️ 有沒有這個帳號都一樣，不要改成兩種說法
GENERIC_MESSAGE = "如果這個 email 有註冊，重設密碼的信已經寄出，%d 分鐘內有效。" % TOKEN_MINUTES

#: 找不到、過期、用過，一律回這句（不要讓人分辨是哪一種）
INVALID_MESSAGE = "這個重設連結已經失效，請重新申請一次"

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TOKEN = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def normalize_email(raw: object) -> str:
    """去空白、轉小寫。註冊時存的就是小寫，比對也要小寫。

    >>> normalize_email("  Ming@Lin.TW ")
    'ming@lin.tw'
    """
    email = str(raw or "").strip().lower()
    if not _EMAIL.match(email):
        raise ValueError("email 格式看起來不對")
    return email


def new_token() -> str:
    """產生重設用的 token（43 個字元、網址安全）。⚠️ 用 secrets，不要用 random。"""
    return secrets.token_urlsafe(32)


def hash_token(token: object) -> str:
    """token 的雜湊。資料庫只存這個；查詢時把收到的 token 再算一次去比。

    >>> len(hash_token("x" * 43))
    64
    """
    text = str(token or "").strip()
    if not _TOKEN.match(text):
        raise ValueError(INVALID_MESSAGE)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def expires_at(now: datetime | None = None) -> datetime:
    """從現在起算 TOKEN_MINUTES 分鐘。"""
    return _utc(now or datetime.now(timezone.utc)) + timedelta(minutes=TOKEN_MINUTES)


def require_usable(expires: datetime | None, used_at: datetime | None, now: datetime | None = None) -> None:
    """這個連結還能不能用。找不到那一列的時候，路由傳 expires=None 進來，一樣丟同一句。

    >>> t = datetime(2026, 9, 14, tzinfo=timezone.utc)
    >>> require_usable(t + timedelta(minutes=5), None, t)
    >>> require_usable(t - timedelta(minutes=1), None, t)
    Traceback (most recent call last):
    ...
    ValueError: 這個重設連結已經失效，請重新申請一次
    """
    now = _utc(now or datetime.now(timezone.utc))
    if expires is None or used_at is not None or now >= _utc(expires):
        raise ValueError(INVALID_MESSAGE)


def should_send(last_sent_at: datetime | None, now: datetime | None = None,
                cooldown_seconds: int = COOLDOWN_SECONDS) -> bool:
    """距離上一封夠久了沒。不夠久就**不寄，但回應照樣回 GENERIC_MESSAGE**。

    >>> t = datetime(2026, 9, 14, tzinfo=timezone.utc)
    >>> should_send(None, t), should_send(t - timedelta(seconds=10), t), should_send(t - timedelta(minutes=2), t)
    (True, False, True)
    """
    if last_sent_at is None:
        return True
    now = _utc(now or datetime.now(timezone.utc))
    return (now - _utc(last_sent_at)).total_seconds() >= cooldown_seconds


def reset_link(base_url: str, token: str) -> str:
    """信裡的連結。token 放在 # 後面（理由見檔頭）。

    >>> reset_link("https://fambudget-web.onrender.com/", "a" * 43)[:52]
    'https://fambudget-web.onrender.com/#/reset/aaaaaaaaa'
    """
    base = str(base_url or "").strip().rstrip("/")
    if not base.startswith(("https://", "http://localhost", "http://127.0.0.1")):
        raise ValueError("APP_BASE_URL 要是 https 網址（本機可以用 http://localhost）")
    hash_token(token)                                      # 順便確認 token 格式
    return "%s/#/reset/%s" % (base, token)


def mail_content(name: object, link: str, minutes: int = TOKEN_MINUTES) -> tuple[str, str, str]:
    """重設密碼那封信：回傳（主旨、純文字、HTML）。

    ⚠️ 名字是使用者自己填的，放進 HTML 之前一定要 escape。
    """
    who = str(name or "").strip() or "你好"
    subject = "重設你的家庭記帳密碼"
    text = (
        "%s，\n\n"
        "有人（希望是你）申請重設家庭記帳的密碼。點下面的連結設定新密碼：\n\n"
        "%s\n\n"
        "這個連結 %d 分鐘內有效，而且只能用一次。設定好新密碼之後，其他裝置上的登入都會登出。\n\n"
        "如果不是你申請的，不用理這封信，你的密碼不會變。\n\n"
        "家庭記帳"
    ) % (who, link, minutes)
    html = (
        '<div style="font-family:sans-serif;font-size:15px;line-height:1.8;color:#222">'
        "<p>%s，</p>"
        "<p>有人（希望是你）申請重設家庭記帳的密碼。按下面的按鈕設定新密碼：</p>"
        '<p><a href="%s" style="display:inline-block;padding:10px 20px;background:#2f5d50;'
        'color:#fff;text-decoration:none;border-radius:8px">設定新密碼</a></p>'
        '<p style="font-size:13px;color:#555">按鈕沒反應的話，把這串貼到瀏覽器：<br>%s</p>'
        "<p>這個連結 <b>%d 分鐘</b>內有效，而且只能用一次。設定好新密碼之後，其他裝置上的登入都會登出。</p>"
        '<p style="color:#555">如果不是你申請的，不用理這封信，你的密碼不會變。</p>'
        "<p>家庭記帳</p></div>"
    ) % (escape(who), escape(link, quote=True), escape(link), minutes)
    return subject, text, html
