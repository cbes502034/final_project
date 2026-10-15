"""
平台管理：停權與解除停權。

負責人：成員1（認證）　✦ 分支：m1-auth

===========================================================================
現在每一支都回 501（後端還沒做這一支），**守衛與主體模型已經接好**
===========================================================================
要做的事：刪掉那一支上面的 `@stub`，再把 `raise not_ready(...)` 那一行換成說明字串裡的第二步。
裝飾器、參數、檔案最上面的 import 都已經放好最終版本，不用動。
* 誰能打這一支：已經由守衛擋好（看 @xxx_required 或 Depends(...)），不用自己再判斷身分
* 前端送什麼、要回什麼：docs/02-前後端串接契約.md 同名的章節
* 增刪改查：app/toolkit/crud.py（find／get／save／remove／to_dict）
* 規則（誰可以、什麼時候不行）：app/toolkit/ 對應的模組，函式說明裡寫了拿來怎麼用
* 回傳的 id 要轉成字串（crud.to_dict 預設就會轉）

`python -m app.ownership` 會列出每個人還剩幾支（有 @stub 的算還沒做）。
"""

from __future__ import annotations

# 這個檔案裡每一支做完之後會用到的 import 都已經放好了。
# 還沒做的那幾支看起來「沒用到」是正常的，不要刪。
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.guards import admin_required
from app.models import AuditLog, FamilyMember, User, UserSession
from app.routers._stub import not_ready, stub
from app.schemas.auth import SuspendIn
from app.toolkit import crud, errors, roles
from app.toolkit.db import get_db

router = APIRouter(tags=["平台管理"])
OWNER = "成員1"


@router.get("/admin/users", summary="帳號清單（停權用）")
@admin_required
def admin_list_users(me: User, db: Session = Depends(get_db)):
    """帳號清單（停權用）

    GET /api/admin/users

    【這支做什麼】
        平台管理頁的帳號清單（停權用）。
        ⚠️ 只有身分欄位：id、名字、email、家庭角色、註冊日、停權狀態。收入、支出、存款目標一律不給——
           停權是關門，不是配鑰匙；一個讀得到全系統消費明細的帳號，比家長越權嚴重得多。
        其他平台管理員不列（他們不能被停權）。

    【前端怎麼打】
        frontend/js/api.js 的 API.adminUsers()
        平台管理頁（#/admin）。前端檢查回應裡一定要有 users。

    【誰能打】
        只有平台管理員。上面的 @admin_required 已經擋好了：
            沒登入 → 401；被停權、不是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的平台管理員（User 物件），me.id 是他的 id。

    【請求參數】沒有

    【成功回應】狀態碼 200
        {"users": [{"id": "5", "name": "王小華", "email": "xiaohua@wang.tw", "role": "child",
                    "joined": "2026-02-11", "suspendedAt": null, "suspendedReason": null}]}
        · role 是家庭角色（parent／child），沒有家庭是 null
        · 照 id 排

    【錯誤回應】
        只有守衛的 401／403，這支本身不會出錯。

    【會用到的資料表】
        表              讀／寫  用來做什麼
        users           讀      不是平台管理員的帳號
        family_members  讀      每個人的家庭角色

    【每一步用的工具與資料庫方法】
        步驟    呼叫                                                  做什麼
        1 帳號  crud.find(User, {"is_platform_admin": False}, order_by="id", db=db)  所有一般帳號
        2 角色  crud.find(FamilyMember, {"status": "active"}, db=db)  做成 {user_id: role}
        3 時間  u.suspended_at.isoformat()                            有停權才轉字串

    【寫法步驟】
        1. 查所有一般帳號
        2. 一次查出每個人的家庭角色
        3. 一個人一列，只放身分欄位，回傳
        ⚠️ 只讀不寫，不用 db.commit()。



    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 GET /api/admin/users
        3. 按右上角 Authorize，貼上平台管理員登入拿到的 accessToken（帳號先用 python -m app.cli make-admin 你的信箱 設成管理員）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               平台管理員打  → 200，每個人只有七個欄位，沒有任何金額
               一般帳號打    → 403
        5. 前端改成連你的後端（frontend/index.html 的 api-base），平台管理頁列出所有帳號與停權狀態
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "admin_list_users and 你的"，要全部通過
    """
    # 1. 所有一般帳號（其他平台管理員不列）
    users = crud.find(User, {"is_platform_admin": False}, order_by="id", db=db)

    # 2. 每個人的家庭角色
    role_of = {m.user_id: m.role for m in crud.find(FamilyMember, {"status": "active"}, db=db)}

    # 3. 只放身分欄位，任何金額都不給
    out = []
    for u in users:
        out.append({
            "id": str(u.id),
            "name": u.display_name,
            "email": u.email,
            "role": role_of.get(u.id),
            "joined": u.created_at.date().isoformat(),
            "suspendedAt": u.suspended_at.isoformat() if u.suspended_at else None,
            "suspendedReason": u.suspended_reason,
        })
    return {"users": out}


@router.post("/admin/users/{user_id}/suspend", summary="停權")
@admin_required
def suspend_user(user_id: str, body: SuspendIn, me: User, db: Session = Depends(get_db)):
    """停權

    POST /api/admin/users/{user_id}/suspend

    【這支做什麼】
        停權一個帳號：一定要寫理由（沒有理由的停權就是任意封鎖）；平台管理員不能被停權。
        ⚠️ 停權只擋登入與之後的每一個請求，不刪任何資料；已經登入的人，下一個請求就被守衛擋下（守衛每次都查 suspended_at）。
        順便撤銷他所有的 sessions，refresh token 也換不到新的。寫一筆稽核。

    【前端怎麼打】
        frontend/js/api.js 的 API.suspendUser(userId, reason)
        平台管理頁每一列的「停權」，要先填理由。

    【誰能打】
        只有平台管理員。上面的 @admin_required 已經擋好了：
            沒登入 → 401；被停權、不是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的平台管理員（User 物件），me.id 是他的 id。

    【請求主體】body 是 SuspendIn（app/schemas/auth.py）
        欄位    型別  必填  說明
        reason  字串  是    壓掉連續空白後至少 4 個字，超過 200 字的部分截掉
        範例：{"reason": "多次騷擾其他使用者"}

    【成功回應】狀態碼 200
        {"id": "5", "suspendedAt": "2026-09-14T10:05:00+00:00"}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候          detail
        403     對象是平台管理員  不能停權平台管理員
        404     沒有這個帳號      找不到這個帳號
        422     理由太短          停權一定要寫理由（至少 4 個字）——沒有理由的停權就是任意封鎖

    【會用到的資料表】
        表          讀／寫  用來做什麼
        users       讀＋寫  找人；設 suspended_at、suspended_reason
        sessions    寫      他所有還沒撤銷的登入 → revoked_at
        audit_logs  寫      suspend_user（理由放在 note）

    【每一步用的工具與資料庫方法】
        步驟    呼叫                                                 做什麼
        1 找人  crud.get(User, 數字 id, db=db)                       用主鍵拿；id 不是數字當 0（一定找不到）
        2 理由  roles.clean_suspend_reason(body.reason)              整理空白；太短丟 ValueError
        3 對象  roles.require_suspendable(target.is_platform_admin)  平台管理員丟 Forbidden（PermissionError 的一種）
        4 停權  crud.save(User, {"id": …, "suspended_at": now, "suspended_reason": why}, db=db)  設時間與理由
                crud.save(UserSession, {"revoked_at": now}, where={"user_id": …, "revoked_at__isnull": True}, db=db)  所有登入撤銷
                crud.save(AuditLog, {…}, db=db)                      稽核
                db.commit()                                          一起寫進去

    【寫法步驟】
        1. 找人（404）
        2. 整理理由（422）
        3. 平台管理員不能停（403）
        4. 設停權、撤銷所有 sessions、寫稽核，db.commit()
        5. 回 {"id", "suspendedAt"}



    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/admin/users/{user_id}/suspend
        3. 按右上角 Authorize，貼上平台管理員登入拿到的 accessToken（帳號先用 python -m app.cli make-admin 你的信箱 設成管理員）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               {"reason": "多次騷擾其他使用者"}  → 200
               {"reason": "  "}                  → 422
               停另一個平台管理員                → 403
               user_id 填 99999                  → 404
        5. 被停權的人原本的 accessToken 打 GET /api/auth/me → 403，附理由；他的資料一筆都沒少
        6. 前端改成連你的後端（frontend/index.html 的 api-base），平台管理頁按「停權」，那一列出現停權時間與理由
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "suspend_user and 你的"，要全部通過
    """
    # 1. 找人
    target = crud.get(User, int(user_id) if user_id.isdigit() else 0, db=db)
    if target is None:
        raise errors.not_found("找不到這個帳號")

    # 2. 一定要有理由
    try:
        why = roles.clean_suspend_reason(body.reason)
    except ValueError as exc:
        raise errors.unprocessable(str(exc)) from None

    # 3. 平台管理員不能停（停掉最後一個就沒有人能解除了）
    try:
        roles.require_suspendable(target.is_platform_admin)
    except PermissionError as exc:
        raise errors.forbidden(str(exc)) from None

    # 4. 停權（不刪任何資料）、所有登入撤銷、寫稽核
    now = datetime.now(timezone.utc)
    crud.save(User, {"id": target.id, "suspended_at": now, "suspended_reason": why}, db=db)
    crud.save(UserSession, {"revoked_at": now}, where={"user_id": target.id, "revoked_at__isnull": True}, db=db)
    crud.save(AuditLog, {"actor_id": me.id, "action": "suspend_user", "target_type": "user",
                         "target_id": target.id, "meta_json": {"note": why}}, db=db)
    db.commit()
    return {"id": str(target.id), "suspendedAt": now.isoformat()}


@router.delete("/admin/users/{user_id}/suspend", summary="解除停權")
@admin_required
def unsuspend_user(user_id: str, me: User, db: Session = Depends(get_db)):
    """解除停權

    DELETE /api/admin/users/{user_id}/suspend

    【這支做什麼】
        解除停權：suspended_at、suspended_reason 設回 NULL，寫一筆稽核。之後他要重新登入。

    【前端怎麼打】
        frontend/js/api.js 的 API.unsuspendUser(userId)
        平台管理頁停權那一列的「解除停權」。

    【誰能打】
        只有平台管理員。上面的 @admin_required 已經擋好了：
            沒登入 → 401；被停權、不是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的平台管理員（User 物件），me.id 是他的 id。

    【路徑參數】{user_id} 是要解除的帳號 id（字串）
        範例：DELETE /api/admin/users/5/suspend

    【成功回應】狀態碼 200
        {"id": "5", "suspendedAt": null}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候            detail
        400     他本來就沒有被停權  這個帳號沒有被停權
        404     沒有這個帳號        找不到這個帳號

    【會用到的資料表】
        表          讀／寫  用來做什麼
        users       讀＋寫  suspended_at、suspended_reason 設 NULL
        audit_logs  寫      unsuspend_user

    【每一步用的工具與資料庫方法】
        步驟    呼叫                             做什麼
        1 找人  crud.get(User, 數字 id, db=db)   用主鍵拿
        2 解除  crud.save(User, {"id": …, "suspended_at": None, "suspended_reason": None}, db=db)  None 就是存 NULL
                crud.save(AuditLog, {…}, db=db)  稽核
                db.commit()                      一起寫進去

    【寫法步驟】
        1. 找人（404）；沒被停權（400）
        2. 兩個欄位設 NULL、寫稽核，db.commit()
        3. 回 {"id", "suspendedAt": null}



    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 DELETE /api/admin/users/{user_id}/suspend
        3. 按右上角 Authorize，貼上平台管理員登入拿到的 accessToken
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               解除一個停權中的帳號  → 200
               再解除一次            → 400
               user_id 填 99999      → 404
        5. 他重新登入 → 200
        6. 前端改成連你的後端（frontend/index.html 的 api-base），平台管理頁按「解除停權」，那一列的停權標記消失
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "unsuspend_user and 你的"，要全部通過
    """
    # 1. 找人，而且要是停權中的
    target = crud.get(User, int(user_id) if user_id.isdigit() else 0, db=db)
    if target is None:
        raise errors.not_found("找不到這個帳號")
    if target.suspended_at is None:
        raise errors.bad_request("這個帳號沒有被停權")

    # 2. 解除、寫稽核
    crud.save(User, {"id": target.id, "suspended_at": None, "suspended_reason": None}, db=db)
    crud.save(AuditLog, {"actor_id": me.id, "action": "unsuspend_user", "target_type": "user",
                         "target_id": target.id, "meta_json": {"note": "解除停權"}}, db=db)
    db.commit()
    return {"id": str(target.id), "suspendedAt": None}
