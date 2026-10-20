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

    # 3. 帳本：他自己在用的帳本整本刪，別人的帳本只把他移出
    crud.remove(m.GroupMember, {"or": [{"user_id": user_id}, {"group_id__in": groups or [0]}]}, db=db)
    if groups:
        crud.remove(m.Group, {"id__in": groups}, db=db)
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
