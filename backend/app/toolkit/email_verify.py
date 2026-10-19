"""
註冊後的 email 驗證：簽一張「這個 email 是你的」的權杖、組信裡的連結、組信件內容。

領域：認證

    from app.toolkit import email_verify

    token = email_verify.make_token(user.id, user.email)          # EMAIL_VERIFY_MINUTES 分鐘有效（預設 24 小時）
    link = email_verify.verify_link(settings.app_base_url, token)  # https://…/#/verify/<token>
    subject, text, html = email_verify.mail_content(user.display_name, link)

    user_id, email = email_verify.read_token(token)               # 無效、過期丟 email_verify.InvalidToken

為什麼不另開一張表存 token（忘記密碼是存雜湊的）：
  · 忘記密碼的 token 拿到就能改密碼，一定要「只能用一次」，所以要存、要能作廢
  · 驗證 email 只是把 email_verified_at 填上時間，用兩次結果一樣（冪等），簽章＋過期時間就夠
  · token 裡放 email：使用者改了 email 之後，舊信裡的連結自然失效（email 對不上）

⚠️ token 放在網址的 # 後面（跟重設密碼一樣）：# 後面不會送到伺服器、不會進 Render 的存取紀錄。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from html import escape
from typing import Any

import jwt

from app.toolkit.config import settings

__all__ = ["TOKEN_MINUTES", "COOLDOWN_SECONDS", "InvalidToken", "make_token", "read_token", "verify_link",
           "mail_content", "should_resend", "ttl_text"]

#: 驗證連結幾分鐘後失效。正式環境 24 小時（1440）；測試過期時在 Render 設 EMAIL_VERIFY_MINUTES=3，測完刪掉
TOKEN_MINUTES = settings.email_verify_minutes
#: 重寄的間隔：太頻繁會把 Brevo 每天 300 封的額度用光
COOLDOWN_SECONDS = 60
_TYPE = "verify_email"


class InvalidToken(Exception):
    """連結無效、過期、或 email 已經改掉了。路由轉成 400，訊息講「登入後可以重寄」。"""


def make_token(user_id: Any, email: str, now: datetime | None = None) -> str:
    """簽一張驗證 email 的權杖（JWT，type 是 verify_email，TOKEN_MINUTES 分鐘後過期）。

    >>> read_token(make_token(7, "a@x.tw"))
    (7, 'a@x.tw')
    """
    now = now or datetime.now(UTC)
    payload = {"sub": str(user_id), "email": str(email).strip().lower(), "type": _TYPE,
               "iat": now, "exp": now + timedelta(minutes=TOKEN_MINUTES)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def read_token(token: object) -> tuple[int, str]:
    """解開權杖，回傳 (user_id, email)。簽章不對、過期、類型不對都丟 InvalidToken。

    ⚠️ 一定要檢查 type：不然拿 access token 來這裡也解得開（同一把密鑰簽的）。
    """
    try:
        data = jwt.decode(str(token or ""), settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise InvalidToken("這個驗證連結過期了") from None
    except Exception:  # noqa: BLE001 — 其他 JWT 錯誤一律當成無效
        raise InvalidToken("這個驗證連結無效") from None
    if data.get("type") != _TYPE or not str(data.get("sub", "")).isdigit() or not data.get("email"):
        raise InvalidToken("這個驗證連結無效")
    return int(data["sub"]), str(data["email"])


def verify_link(base_url: str, token: str) -> str:
    """信裡的連結：<前端網址>/#/verify/<token>。

    >>> verify_link("https://fambudget-web.onrender.com/", "abc")
    'https://fambudget-web.onrender.com/#/verify/abc'
    """
    base = str(base_url or "").strip().rstrip("/")
    if not base.startswith(("https://", "http://localhost", "http://127.0.0.1")):
        raise ValueError("APP_BASE_URL 要是 https 網址（本機可以用 http://localhost）")
    return "%s/#/verify/%s" % (base, token)


def should_resend(last_sent_at: datetime | None, now: datetime | None = None,
                  cooldown: int = COOLDOWN_SECONDS) -> bool:
    """距離上一封夠久了沒（沒寄過就是夠久）。"""
    if last_sent_at is None:
        return True
    now = now or datetime.now(UTC)
    if last_sent_at.tzinfo is None:
        last_sent_at = last_sent_at.replace(tzinfo=UTC)
    return (now - last_sent_at).total_seconds() >= cooldown


def ttl_text(minutes: int | None = None) -> str:
    """給人看的有效期：整點的寫「24 小時」，其他寫「3 分鐘」。

    >>> ttl_text(1440), ttl_text(90), ttl_text(3)
    ('24 小時', '90 分鐘', '3 分鐘')
    """
    m = TOKEN_MINUTES if minutes is None else int(minutes)
    return "%d 小時" % (m // 60) if m >= 60 and m % 60 == 0 else "%d 分鐘" % m


def mail_content(name: object, link: str, minutes: int | None = None) -> tuple[str, str, str]:
    """驗證信：回傳（主旨、純文字、HTML）。

    ⚠️ 名字是使用者自己填的，放進 HTML 之前一定要 escape。
    """
    who = str(name or "").strip() or "你好"
    subject = "確認你的家庭記帳 email"
    text = (
        "%s，\n\n"
        "歡迎使用家庭記帳！點下面的連結，確認這個 email 是你的：\n\n"
        "%s\n\n"
        "這個連結 %s內有效。確認之後，忘記密碼時我們才寄得到重設信給你。\n\n"
        "如果你沒有註冊家庭記帳，不用理這封信。\n\n"
        "家庭記帳"
    ) % (who, link, ttl_text(minutes))
    html = (
        '<div style="font-family:sans-serif;font-size:15px;line-height:1.8;color:#222">'
        "<p>%s，</p>"
        "<p>歡迎使用家庭記帳！按下面的按鈕，確認這個 email 是你的：</p>"
        '<p><a href="%s" style="display:inline-block;padding:10px 20px;background:#2f5d50;'
        'color:#fff;text-decoration:none;border-radius:8px">確認我的 email</a></p>'
        '<p style="font-size:13px;color:#555">按鈕沒反應的話，把這串貼到瀏覽器：<br>%s</p>'
        "<p>這個連結 <b>%s</b>內有效。確認之後，忘記密碼時我們才寄得到重設信給你。</p>"
        '<p style="color:#555">如果你沒有註冊家庭記帳，不用理這封信。</p>'
        "<p>家庭記帳</p></div>"
    ) % (escape(who), escape(link, quote=True), escape(link), ttl_text(minutes))
    return subject, text, html
