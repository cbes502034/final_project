"""
寄信。包住 Brevo 的 HTTP API，你不用讀它的文件。

負責人：成員1（認證）

===========================================================================
為什麼是 HTTP API，不是 SMTP
===========================================================================
Render 的免費方案從 2025-09-26 起，**擋掉連外的 SMTP 連接埠（25／465／587）**。
用 smtplib 連 Gmail 在本機會通，一部署到 Render 就永遠連不上——而且不會有
清楚的錯誤，只會逾時。所以一律走 HTTPS（443），這個埠不會被擋。

為什麼選 Brevo：免費每天 300 封、不用信用卡；寄件人**驗證一個信箱**就能寄，
不需要自己的網域（Resend 這類服務沒有網域時只能寄給自己）。

===========================================================================
要設的環境變數（都不要 commit，Render 上在後台填）
===========================================================================
    BREVO_API_KEY    Brevo 後台 → SMTP & API → API keys → Generate a new API key
    MAIL_FROM        在 Brevo 驗證過的寄件信箱（Senders, domains & dedicated IPs → Senders）
    MAIL_FROM_NAME   寄件人名稱，預設「家庭記帳」

===========================================================================
怎麼用
===========================================================================
    from app.toolkit import mailer

    mailer.send_mail("a@example.com", "主旨", "純文字內容", html="<p>HTML 內容</p>")

填好環境變數之後，先試寄一封給自己，確定真的收得到：

    python -m app.toolkit.mailer --to 你的信箱@gmail.com

⚠️ 沒設金鑰時丟 `MailNotConfigured`，**不會默默不寄**。
   默默不寄的話，使用者按了「忘記密碼」永遠等不到信，而我們完全不知道。
⚠️ 錯誤訊息裡**不會出現金鑰**，可以放心記進 log。
"""

from __future__ import annotations

import argparse
import re
import sys

import httpx

__all__ = [
    "API_URL", "TIMEOUT_SECONDS", "MailNotConfigured", "MailError",
    "build_payload", "send_mail", "main",
]

API_URL = "https://api.brevo.com/v3/smtp/email"

#: 寄信服務卡住時最多等幾秒。沒有逾時的話，一個卡住的請求會拖住整支 API。
TIMEOUT_SECONDS = 10.0

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class MailNotConfigured(RuntimeError):
    """沒設 BREVO_API_KEY 或 MAIL_FROM。部署設定的問題，不是使用者的錯。"""


class MailError(RuntimeError):
    """寄信服務回錯誤或沒有回應。訊息已經去掉金鑰，可以直接記 log。"""


def build_payload(
    to: str,
    subject: str,
    text: str,
    html: str | None = None,
    *,
    sender: str,
    sender_name: str = "家庭記帳",
    to_name: str | None = None,
) -> dict:
    """組出 Brevo 要的 JSON。拆出來是為了**不用真的寄信就能測**。

    >>> p = build_payload("a@example.com", "主旨", "內文", sender="me@example.com")
    >>> p["to"], p["sender"]["email"], "htmlContent" in p
    ([{'email': 'a@example.com'}], 'me@example.com', False)
    """
    to = str(to or "").strip()
    if not _EMAIL.match(to):
        raise ValueError("收件人的 email 格式不對")
    if not _EMAIL.match(str(sender or "").strip()):
        raise MailNotConfigured("MAIL_FROM 沒設，或不是 email 格式")
    if not str(subject or "").strip():
        raise ValueError("信件要有主旨")
    if not str(text or "").strip():
        raise ValueError("信件要有內容")

    recipient: dict = {"email": to}
    if to_name:
        recipient["name"] = str(to_name)
    payload: dict = {
        "sender": {"name": sender_name or "家庭記帳", "email": str(sender).strip()},
        "to": [recipient],
        "subject": str(subject).strip(),
        # 純文字一定要有：有些信箱只顯示純文字，只寄 HTML 也比較容易被當成垃圾信
        "textContent": str(text),
    }
    if html:
        payload["htmlContent"] = html
    return payload


def _settings():
    from .config import settings  # 用到才讀，import 這個模組不需要資料庫設定

    return settings


def send_mail(
    to: str,
    subject: str,
    text: str,
    html: str | None = None,
    *,
    to_name: str | None = None,
    api_key: str | None = None,
    sender: str | None = None,
    sender_name: str | None = None,
    client: httpx.Client | None = None,
) -> str:
    """寄一封信，回傳 Brevo 的 messageId。

    參數
        to, subject, text: 收件人、主旨、純文字內容（必填）
        html: HTML 內容（選填）
        api_key, sender, sender_name: 不給就讀環境變數（BREVO_API_KEY、MAIL_FROM、MAIL_FROM_NAME）
        client: 測試時傳 httpx.Client(transport=httpx.MockTransport(...))，不會真的連網路

    丟出
        MailNotConfigured: 沒設金鑰或寄件人
        ValueError: 收件人、主旨、內容不對
        MailError: 寄信服務拒絕或沒有回應
    """
    if api_key is None or sender is None or sender_name is None:
        s = _settings()
        api_key = s.brevo_api_key if api_key is None else api_key
        sender = s.mail_from if sender is None else sender
        sender_name = s.mail_from_name if sender_name is None else sender_name
    if not api_key:
        raise MailNotConfigured("BREVO_API_KEY 沒設，寄不出信。到 Render 後台（或本機 .env）填上")

    payload = build_payload(to, subject, text, html, sender=sender or "",
                            sender_name=sender_name or "家庭記帳", to_name=to_name)
    headers = {"api-key": api_key, "accept": "application/json", "content-type": "application/json"}

    def scrub(msg: str) -> str:
        return msg.replace(api_key, "***") if api_key else msg

    own = client is None
    client = client or httpx.Client(timeout=TIMEOUT_SECONDS)
    try:
        res = client.post(API_URL, json=payload, headers=headers)
    except httpx.TimeoutException:
        raise MailError("寄信服務超過 %d 秒沒有回應" % TIMEOUT_SECONDS) from None
    except httpx.HTTPError as exc:
        raise MailError(scrub("連不上寄信服務：%s" % exc.__class__.__name__)) from None
    finally:
        if own:
            client.close()

    if res.status_code not in (200, 201, 202):
        try:
            detail = res.json().get("message") or res.text
        except ValueError:
            detail = res.text
        hint = "（金鑰錯了，或寄件信箱還沒在 Brevo 驗證）" if res.status_code in (400, 401, 403) else ""
        raise MailError(scrub("寄信服務拒絕了這封信 %d%s：%s" % (res.status_code, hint, str(detail)[:200])))
    try:
        return str(res.json().get("messageId") or "")
    except ValueError:
        return ""


def main(argv: list[str] | None = None) -> int:
    """試寄一封：python -m app.toolkit.mailer --to 你的信箱"""
    ap = argparse.ArgumentParser(description="用 Brevo 試寄一封信，確認金鑰和寄件信箱設定正確")
    ap.add_argument("--to", required=True, help="收件信箱（寄給你自己）")
    args = ap.parse_args(argv)
    try:
        mid = send_mail(
            args.to, "家庭記帳 寄信測試",
            "這是一封測試信。收到這封，代表忘記密碼的信也寄得出去。",
            html="<p>這是一封測試信。</p><p>收到這封，代表<b>忘記密碼</b>的信也寄得出去。</p>",
        )
    except (MailNotConfigured, MailError, ValueError) as exc:
        print("沒寄出去：%s" % exc, file=sys.stderr)
        return 1
    except Exception as exc:  # 多半是 .env 少了 DATABASE_URL／JWT_SECRET，設定讀不起來
        print("設定讀不起來（先照 backend/.env.example 建好 .env）：%s" % exc.__class__.__name__, file=sys.stderr)
        return 1
    print("寄出了，messageId：%s。去信箱看看（也看一下垃圾信件匣）" % mid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
