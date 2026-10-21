"""
刪除自己的帳號（DELETE /api/auth/me）要用的規則與清理。

領域：認證

===========================================================================
刪什麼、留什麼
===========================================================================
刪掉：這個人記的每一筆帳（含 AI 解析紀錄、相關通知）、只有他自己在用的帳本、預算、存款目標、
     提醒門檻、財務建議、零用金、照看關係、邀請、通知、登入工作階段、重設密碼連結。
抹掉：users 那一列的名字、email、密碼、大頭貼、出生年、理財習慣——email 改成用不到的位址，
     原本的 email 空出來，可以再註冊一個新帳號。
留著：users 那一列（墓碑，deleted_at 填上時間）。稽核紀錄、他建立過的家庭還指著它，
     整列刪掉外鍵會斷；安全事件與錯誤紀錄的 user_id 改成 NULL（只留次數，不留是誰）。

===========================================================================
什麼時候不能刪（回要給使用者看的話）
===========================================================================
    還在家庭裡           先退出或解散家庭——那兩條路已經處理好照看、零用金、帳本成員，不在這裡重寫一次
    他開的帳本還有別人   先把別人移出、或移除那本帳——別人的帳不能跟著他一起消失
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from app.toolkit import crud, passwords

#: 刪除之後的 email：@deleted.invalid 是保留的網域，寄不到、也不會跟任何人撞到
DELETED_DOMAIN = "deleted.invalid"
DELETED_NAME = "已刪除的帳號"


def _models():
    from app import models
    return models


def why_not_delete(user_id: int, family_id: int | None, *, db) -> str | None:
    """不能刪的原因；可以刪回 None。"""
    m = _models()
    if family_id is not None:
        return "你還在一個家庭裡：先到「家庭成員」退出（或解散）家庭，才能刪除帳號"
    mine = crud.find(m.Group, {"created_by": user_id, "removed_at__isnull": True}, db=db)
    for g in mine:
        others = crud.count(m.GroupMember, {"group_id": g.id, "user_id__ne": user_id}, db=db)
        theirs = crud.count(m.Transaction, {"group_id": g.id, "user_id__ne": user_id}, db=db)
        if others or theirs:
            return "你開的帳本「%s」還有別人在用：先把他們移出、或移除這本帳，才能刪除帳號" % g.name
    return None


def delete_everything(user_id: int, *, db) -> dict:
    """刪掉這個人的紀錄、抹掉個資，回傳刪了幾筆（給測試與稽核看）。只 flush，呼叫的人 commit。"""
    m = _models()
    now = datetime.now(timezone.utc)
    groups = crud.find(m.Group, {"created_by": user_id}, fields="id", db=db)
    tx_ids = crud.find(m.Transaction, {"or": [{"user_id": user_id}, {"group_id__in": groups or [0]}]},
                       fields="id", db=db)
    count = {"transactions": len(tx_ids), "groups": len(groups)}

    # 1. 帳：AI 解析紀錄、指著這些帳的通知先清，再刪帳
    crud.remove(m.NlpParse, {"or": [{"user_id": user_id}, {"transaction_id__in": tx_ids or [0]}]}, db=db)
    crud.remove(m.Notification, {"or": [{"recipient_id": user_id}, {"actor_id": user_id},
                                        {"transaction_id__in": tx_ids or [0]}]}, db=db)
    if tx_ids:
        crud.remove(m.Transaction, {"id__in": tx_ids}, db=db)

    # 2. 設定類：門檻、存款目標、預算、建議、零用金、照看、邀請
    crud.remove(m.AlertRule, {"or": [{"user_id": user_id}, {"group_id__in": groups or [0]}]}, db=db)
    crud.remove(m.SavingsGoal, {"or": [{"user_id": user_id}, {"created_by": user_id},
                                       {"group_id__in": groups or [0]}]}, db=db)
    crud.remove(m.Budget, {"or": [{"user_id": user_id}, {"created_by": user_id}]}, db=db)
    crud.remove(m.Advice, {"user_id": user_id}, db=db)
    crud.remove(m.Allowance, {"or": [{"payer_id": user_id}, {"ward_id": user_id}]}, db=db)
    crud.remove(m.Guardianship, {"or": [{"guardian_id": user_id}, {"ward_id": user_id},
                                        {"created_by": user_id}]}, db=db)
    crud.remove(m.FamilyInvite, {"or": [{"inviter_id": user_id}, {"invitee_id": user_id}]}, db=db)

    crud.remove(m.ActivityInvite, {"or": [{"inviter_id": user_id}, {"invitee_id": user_id},
                                           {"group_id__in": groups or [0]}]}, db=db)

    # 3. 帳本：他自己在用的帳本整本刪，別人的帳本只把他移出
    crud.remove(m.GroupMember, {"or": [{"user_id": user_id}, {"group_id__in": groups or [0]}]}, db=db)
    if groups:
        # 其他人的收支明細仍可能引用已結束的活動；保留活動名稱供來源搜尋。
        referenced = set(crud.find(m.Transaction, {"origin_group_id__in": groups}, fields="origin_group_id", db=db))
        removable = [gid for gid in groups if gid not in referenced]
        count["groups"] = len(removable)
        if removable:
            crud.remove(m.Group, {"id__in": removable}, db=db)
    crud.remove(m.Account, {"user_id": user_id}, db=db)

    # 4. 登入：工作階段、重設密碼連結；安全事件與錯誤紀錄只留次數，不留是誰
    crud.remove(m.UserSession, {"user_id": user_id}, db=db)
    crud.remove(m.PasswordReset, {"user_id": user_id}, db=db)
    crud.save(m.SecurityEvent, {"user_id": None}, where={"user_id": user_id}, db=db)
    crud.save(m.ErrorLog, {"user_id": None}, where={"user_id": user_id}, db=db)

    # 5. 抹掉個資，留下墓碑（email 空出來，可以再註冊）
    crud.save(m.User, {
        "id": user_id,
        "email": "deleted-%d-%s@%s" % (user_id, secrets.token_hex(4), DELETED_DOMAIN),
        "display_name": DELETED_NAME,
        "password_hash": passwords.hash_password(secrets.token_urlsafe(32)),
        "birth_year": None, "avatar_bytes": None, "avatar_mime": None,
        "finance_style": None, "finance_goals": None, "finance_habits": None, "finance_note": None,
        "email_verified_at": None, "email_verify_sent_at": None, "last_active_at": None,
        "deleted_at": now,
    }, db=db)
    return count


# ===========================================================================
# 服務啟動時：清空所有帳號（一次性）、預設的平台管理員
# ===========================================================================
# 使用者 2026-10-20：「所有帳戶全部清空，再設一組管理者帳號，不用驗證、資料庫寫死」。
# ⚠️ 密碼不寫進程式：repo 是公開的，寫進去等於任何人都能用管理員登入正式站。
#    改成 Render 的環境變數 ADMIN_BOOTSTRAP_EMAIL／ADMIN_BOOTSTRAP_PASSWORD，啟動時直接寫進資料庫。
# ⚠️ 清空是救不回來的動作，由使用者自己在 Render 設 RESET_ACCOUNTS 觸發；同一個值只會清一次。

def wipe_all(*, db) -> dict[str, int]:
    """刪光所有帳號與紀錄，系統分類留著。回傳每張表刪了幾列（只 flush，不 commit）。

    照外鍵的相依順序倒著刪（Base.metadata.sorted_tables 反過來＝先刪指著別人的）。
    分類只刪家庭自訂的（family_id 不是 NULL），系統分類是遷移建好的，所有人共用。
    """
    from app.models import Category  # noqa: F401  確定模型都載入了，sorted_tables 才完整
    from app.toolkit.db import Base

    counts: dict[str, int] = {}
    for table in reversed(Base.metadata.sorted_tables):
        stmt = table.delete()
        if table.name == "categories":
            stmt = stmt.where(table.c.family_id.isnot(None))
        counts[table.name] = db.execute(stmt).rowcount or 0
    db.flush()
    return counts


def bootstrap_admin(email: str, password: str, name: str = "平台管理員", *, db) -> str:
    """建好（或補好）預設的平台管理員：已驗證、已走完設定、不用收信。回傳一句給人看的話。

    帳號已經存在：只補上管理員與已驗證，**不改密碼**（改密碼走「改密碼」）；
    但已經加入家庭或記過帳的帳號不設（跟 cli.promote_admins 同一條：設了他就看不到自己的帳）。
    """
    from app.models import FamilyMember, Transaction, User

    email = (email or "").strip().lower()
    if not email or not password:
        return "沒有設定 ADMIN_BOOTSTRAP_EMAIL／ADMIN_BOOTSTRAP_PASSWORD，略過"
    now = datetime.now(timezone.utc)
    user = crud.get(User, where={"email": email}, db=db)
    if user is None:
        try:
            hashed = passwords.hash_password(password)
        except ValueError as exc:
            return "預設管理員的密碼不合格（%s），沒有建立" % exc
        crud.save(User, {"email": email, "password_hash": hashed, "display_name": name, "theme": "paper",
                         "is_platform_admin": True, "email_verified_at": now, "onboarded_at": now}, db=db)
        return "建好預設的平台管理員 %s（已驗證，可以直接登入）" % email
    if not user.is_platform_admin and (crud.exists(FamilyMember, {"user_id": user.id, "status": "active"}, db=db)
                                       or crud.exists(Transaction, {"user_id": user.id}, db=db)):
        return "%s 已經加入家庭或記過帳，不設成平台管理員；請換一個 email" % email
    changes = {"is_platform_admin": True}
    if user.email_verified_at is None:
        changes["email_verified_at"] = now
    if user.onboarded_at is None:
        changes["onboarded_at"] = now
    crud.save(User, {"id": user.id, **changes}, db=db)
    return "%s 是平台管理員（已驗證）" % email


def on_startup(settings) -> list[str]:
    """服務啟動時跑一次：RESET_ACCOUNTS（一次性清空）→ 預設的平台管理員。回傳給 Render 紀錄看的句子。"""
    from app.models import SecurityEvent
    from app.toolkit import security
    from app.toolkit.db import session_scope

    out = []
    token = (settings.reset_accounts or "").strip()
    if token:
        marker = "RESET_ACCOUNTS=" + token[:100]
        with session_scope() as db:
            if crud.exists(SecurityEvent, {"kind": "accounts_reset", "detail": marker}, db=db):
                out.append("RESET_ACCOUNTS=%s 已經清過了，不再清（要再清一次就換一個值）" % token)
            else:
                counts = wipe_all(db=db)
                security.record("accounts_reset", db=db, detail=marker)
                out.append("清空所有帳號：刪掉 %d 個帳號、%d 筆收支（RESET_ACCOUNTS=%s）"
                           % (counts.get("users", 0), counts.get("transactions", 0), token))
    if settings.admin_bootstrap_email or settings.admin_bootstrap_password:
        with session_scope() as db:
            out.append(bootstrap_admin(settings.admin_bootstrap_email, settings.admin_bootstrap_password, db=db))
    return out
