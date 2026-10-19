"""
防濫用的規則、上線狀態、安全事件與錯誤紀錄的寫入。平台管理頁看到的東西都從這裡來。

領域：認證（共用元件）——登入、註冊、AI 解析、產生建議、找人都會呼叫，改之前先講

===========================================================================
規則：全部是「數過去一段時間發生了幾次」，不用 AI 判斷
===========================================================================
    登入   同一個 email 15 分鐘內錯 LOGIN_MAX_FAILURES 次（預設 5）→ 這個 email 鎖 15 分鐘
           ⚠️ 帳號不存在也一樣算、一樣鎖：只鎖存在的帳號的話，「會不會被鎖」就洩漏了帳號在不在
           同一個來源 15 分鐘內錯 4 倍（預設 20 次，不管哪個帳號）→ 這個來源鎖 15 分鐘（撞庫）
    註冊   同一個來源一小時內註冊 REGISTER_PER_HOUR 個（預設 5）→ 擋到滿一小時
    AI     每人每天（台灣時間）解析 AI_PARSE_PER_DAY 次、產生建議 AI_ADVICE_PER_DAY 次
    找人   一分鐘 10 次（規則在 routers/access/family.py 的 lookup_user，這裡只記事件）
    確認密碼  15 分鐘錯 5 次（規則在 routers/auth/auth.py 的 verify_password，這裡只記事件）

為什麼不讓 AI 判斷、自動封鎖：上面每一條都是明確的事實（5 分鐘錯 20 次），規則判斷得很清楚；
換成 AI 只會多出誤判（把打錯密碼的家人鎖住）跟費用。**停權一律由平台管理員按**，
規則只做「暫時擋下＋記一筆」，時間到自己解開。

===========================================================================
⚠️ 這裡寫進去的東西平台管理員都看得到
===========================================================================
不放密碼、金額、備註、記帳的那句話。email 與 IP 只存 HMAC（用 JWT_SECRET 當鑰匙），
只拿來數次數，從雜湊推不回原文。

===========================================================================
來源 IP
===========================================================================
Render 前面有一層代理，request.client.host 是代理的位址（所有人都一樣）。
真正的來源在 X-Forwarded-For 的第一個。那一欄瀏覽器自己也能偽造——偽造的人只能
躲掉「同一個來源」的限制，躲不掉「同一個 email」的鎖；而且他猜不到別人的 IP，
沒辦法拿這個去鎖別人。所以兩條規則一定要一起用。
"""

from __future__ import annotations

import hashlib
import hmac
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from app.toolkit.config import settings

TAIPEI = timezone(timedelta(hours=8))

LOGIN_WINDOW = timedelta(minutes=15)
REGISTER_WINDOW = timedelta(hours=1)

#: 守衛多久寫一次 users.last_active_at。每個請求都寫的話，一頁十幾支 API 就是十幾次寫入
TOUCH_SECONDS = 30
#: 綠燈：90 秒內有請求（前端的通知每 20 秒問一次，連漏三次才算離開）
ONLINE_SECONDS = 90
#: 黃燈：15 分鐘內有請求（分頁切到背景、或剛關掉）；更久或已經登出就是紅燈
IDLE_MINUTES = 15

#: 安全事件與錯誤紀錄留幾天
KEEP_DAYS = 30

#: kind → (程度, 管理頁上的標題)。程度是 None 的只是計數（註冊、AI 呼叫），不列在安全事件
KINDS: dict[str, tuple[str | None, str]] = {
    "login_failed": ("low", "登入失敗"),
    "login_locked": ("high", "同一個帳號登入失敗太多次，暫時鎖住 15 分鐘"),
    "source_locked": ("high", "同一個來源大量登入失敗（疑似撞庫），暫時擋下 15 分鐘"),
    "register": (None, "註冊"),
    "register_limited": ("medium", "同一個來源短時間註冊太多帳號，暫時擋下"),
    "ai_parse": (None, "AI 解析"),
    "ai_advice": (None, "AI 產生建議"),
    "ai_quota": ("medium", "今天的 AI 額度用完了"),
    "verify_locked": ("high", "重大操作前的密碼確認錯太多次，鎖 15 分鐘"),
    "lookup_limited": ("medium", "用帳號找人太頻繁（疑似在試帳號）"),
}

LEVEL_TEXT = {"high": "高", "medium": "中", "low": "低"}


def _models():
    from app import models
    return models


def aware(dt: datetime | None) -> datetime | None:
    """SQLite 讀回來的時間沒有時區（存的時候是 UTC），補上才比得了大小。"""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def now() -> datetime:
    return datetime.now(timezone.utc)


def today_start(at: datetime | None = None) -> datetime:
    """台灣時間今天 00:00（轉成 UTC）。AI 額度每天這個時候重算。"""
    local = (at or now()).astimezone(TAIPEI)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


# ===========================================================================
# 雜湊與來源
# ===========================================================================
def digest(value: str | None) -> str | None:
    """email、IP 的 HMAC。只拿來數次數，推不回原文。"""
    if not value:
        return None
    key = (settings.jwt_secret or "fambudget").encode()
    return hmac.new(key, value.strip().lower().encode(), hashlib.sha256).hexdigest()[:32]


def user_from(request: Any) -> int | None:
    """Authorization 裡有效的 access token → user id；沒帶、過期、壞掉都是 None（不丟錯）。"""
    from app.toolkit import tokens
    auth = request.headers.get("authorization", "") if request is not None else ""
    if not auth.lower().startswith("bearer "):
        return None
    try:
        return int(tokens.read_access_token(auth[7:].strip())["sub"])
    except Exception:            # noqa: BLE001 —— 壞掉的 token 就當作沒登入
        return None


def source_of(request: Any) -> str:
    """這個請求的來源 IP（見檔頭「來源 IP」）。"""
    fwd = request.headers.get("x-forwarded-for", "") if request is not None else ""
    if fwd.strip():
        return fwd.split(",")[0].strip()
    client = getattr(request, "client", None)
    return client.host if client else ""


# ===========================================================================
# 安全事件
# ===========================================================================
def record(kind: str, *, db, user_id: int | None = None, subject: str | None = None,
           ip: str | None = None, detail: str | None = None):
    """記一筆安全事件。⚠️ 只 flush 不 commit：要不要跟著請求一起寫，由路由決定。

    擋下來的請求（429）要在 raise 之前自己 db.commit()，不然請求一結束就跟著被丟掉了。
    """
    from app.toolkit import crud
    if kind not in KINDS:
        raise ValueError("不認得的安全事件：%s" % kind)
    m = _models()
    row = crud.save(m.SecurityEvent, {"kind": kind, "user_id": user_id, "subject": subject,
                                      "ip_hash": digest(ip) if ip else None,
                                      "detail": (detail or "")[:200] or None}, db=db)
    if random.random() < 0.02:
        crud.remove(m.SecurityEvent, {"created_at__lt": now() - timedelta(days=KEEP_DAYS)}, db=db)
    return row


def count(kind: str | tuple[str, ...], since: datetime, *, db, user_id: int | None = None,
          subject: str | None = None, ip: str | None = None) -> int:
    from app.toolkit import crud
    m = _models()
    where: dict[str, Any] = {"created_at__gte": since}
    where["kind__in" if isinstance(kind, tuple) else "kind"] = list(kind) if isinstance(kind, tuple) else kind
    if user_id is not None:
        where["user_id"] = user_id
    if subject is not None:
        where["subject"] = subject
    if ip is not None:
        where["ip_hash"] = digest(ip)
    return crud.count(m.SecurityEvent, where, db=db)


def _last(kind: str, *, db, subject: str | None = None, ip: str | None = None) -> datetime | None:
    from app.toolkit import crud
    m = _models()
    where: dict[str, Any] = {"kind": kind}
    if subject is not None:
        where["subject"] = subject
    if ip is not None:
        where["ip_hash"] = digest(ip)
    return aware(crud.get(m.SecurityEvent, where=where, fields="created_at", order_by="-id", db=db))


LOCKED_MESSAGE = "密碼錯太多次了，請 15 分鐘後再試"
SOURCE_LOCKED_MESSAGE = "這台裝置登入失敗太多次了，請 15 分鐘後再試"


def login_blocked(email: str, ip: str, *, db) -> str | None:
    """這次登入要不要先擋下來。回傳要給使用者看的話；None 就是可以試。"""
    t = now()
    subject = digest(email)
    for kind, key, msg in (("login_locked", {"subject": subject}, LOCKED_MESSAGE),
                           ("source_locked", {"ip": ip}, SOURCE_LOCKED_MESSAGE)):
        if not key.get("subject") and not key.get("ip"):
            continue
        last = _last(kind, db=db, **key)
        if last and last > t - LOGIN_WINDOW:
            return msg
    return None


def login_failed(email: str, ip: str, *, db, user_id: int | None = None) -> None:
    """登入失敗：記一筆，次數到了就開始鎖。只 flush，呼叫的人要 commit。"""
    t = now()
    subject = digest(email)
    record("login_failed", db=db, user_id=user_id, subject=subject, ip=ip)
    # 鎖解開之後重新數：上一次鎖之前的失敗不算
    since = max(t - LOGIN_WINDOW, _last("login_locked", db=db, subject=subject) or t - LOGIN_WINDOW)
    if count("login_failed", since, db=db, subject=subject) >= settings.login_max_failures:
        record("login_locked", db=db, user_id=user_id, subject=subject, ip=ip,
               detail="15 分鐘內錯了 %d 次" % settings.login_max_failures)
    if ip:
        since = max(t - LOGIN_WINDOW, _last("source_locked", db=db, ip=ip) or t - LOGIN_WINDOW)
        if count("login_failed", since, db=db, ip=ip) >= settings.login_max_failures * 4:
            record("source_locked", db=db, ip=ip,
                   detail="15 分鐘內這個來源錯了 %d 次（不只一個帳號）" % (settings.login_max_failures * 4))


REGISTER_MESSAGE = "這台裝置短時間內註冊太多帳號了，請一小時後再試"


def register_blocked(ip: str, *, db) -> str | None:
    if not ip:
        return None
    if count("register", now() - REGISTER_WINDOW, db=db, ip=ip) >= settings.register_per_hour:
        if not count("register_limited", now() - REGISTER_WINDOW, db=db, ip=ip):
            record("register_limited", db=db, ip=ip,
                   detail="一小時內已經註冊 %d 個帳號" % settings.register_per_hour)
        return REGISTER_MESSAGE
    return None


AI_LIMITS = {"ai_parse": ("ai_parse_per_day", "今天的 AI 解析次數用完了（每天 %d 次），明天會恢復；也可以直接手動記一筆"),
             "ai_advice": ("ai_advice_per_day", "今天產生建議的次數用完了（每天 %d 次），明天會恢復")}


def ai_quota(kind: str, user_id: int, *, db) -> str | None:
    """AI 額度：還有就記一次、回 None；用完了回要給使用者看的話（第一次用完時記一筆 ai_quota）。

    ⚠️ 在呼叫模型**之前**記：模型失敗也算一次——失敗的呼叫一樣花錢。
    """
    field, msg = AI_LIMITS[kind]
    limit = getattr(settings, field)
    start = today_start()
    if count(kind, start, db=db, user_id=user_id) >= limit:
        if not count("ai_quota", start, db=db, user_id=user_id):
            record("ai_quota", db=db, user_id=user_id, detail="%s 用完（%d 次）" % (KINDS[kind][1], limit))
        return msg % limit
    record(kind, db=db, user_id=user_id)
    return None


# ===========================================================================
# 上線狀態
# ===========================================================================
def touch(user: Any, *, db) -> None:
    """守衛每個請求都呼叫：距離上次超過 TOUCH_SECONDS 才寫，寫完馬上 commit（這時候路由還沒開始寫東西）。"""
    t = now()
    last = aware(user.last_active_at)
    if last is not None and (t - last).total_seconds() < TOUCH_SECONDS:
        return
    m = _models()
    from sqlalchemy import update
    db.execute(update(m.User).where(m.User.id == user.id).values(last_active_at=t)
               .execution_options(synchronize_session=False))
    db.commit()
    from sqlalchemy.orm.attributes import set_committed_value
    set_committed_value(user, "last_active_at", t)     # 不要讓這個物件變成「改過」，路由 commit 時才不會再寫一次


def last_seen(user: Any) -> datetime | None:
    """最後一次有動靜的時間：最後一次請求（last_active_at）與最後一次登入（last_login_at）取比較晚的。

    登入、註冊不經過守衛，不會寫 last_active_at；剛登入還沒點任何地方的人，也算剛剛有動靜。
    """
    times = [t for t in (aware(user.last_active_at), aware(getattr(user, "last_login_at", None))) if t]
    return max(times) if times else None


def presence(last_active_at: datetime | None, signed_in: bool, suspended: bool,
             at: datetime | None = None) -> str:
    """online 綠燈／idle 黃燈／offline 紅燈／suspended 停權。

    signed_in：還有沒有一台沒登出、沒過期的登入。按了登出就馬上變紅燈，不用等 15 分鐘。
    """
    if suspended:
        return "suspended"
    last = aware(last_active_at)
    if not signed_in or last is None:
        return "offline"
    gap = ((at or now()) - last).total_seconds()
    if gap <= ONLINE_SECONDS:
        return "online"
    if gap <= IDLE_MINUTES * 60:
        return "idle"
    return "offline"


# ===========================================================================
# 錯誤紀錄
# ===========================================================================
def log_error(source: str, message: str, *, status: int | None = None, method: str | None = None,
              path: str | None = None, location: str | None = None, user_id: int | None = None) -> None:
    """記一筆錯誤。自己開一個交易寫完就走；寫不進去也不能讓原本的錯誤變得更糟，所以吞掉。"""
    from app.toolkit import crud
    try:
        m = _models()
        crud.save(m.ErrorLog, {"source": source, "status": status, "method": method,
                               "path": (path or "")[:200] or None, "location": (location or "")[:200] or None,
                               "message": (message or "沒有訊息")[:300], "user_id": user_id})
        if random.random() < 0.02:
            crud.remove(m.ErrorLog, {"created_at__lt": now() - timedelta(days=KEEP_DAYS)})
    except Exception:            # noqa: BLE001 —— 記錯誤的地方自己出錯，只能放掉
        pass
