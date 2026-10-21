"""
平台管理：帳號清單（含即時的紅綠燈）、停權與解除停權、錯誤訊息、安全事件，以及前端回報畫面上出的錯。

領域：認證

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
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.guards import admin_required
from app.models import AuditLog, ErrorLog, FamilyMember, SecurityEvent, User, UserSession
from app.routers._stub import not_ready, stub
from app.schemas.auth import ClientErrorIn, SuspendIn
from app.toolkit import crud, email_verify, errors, roles, security
from app.toolkit.db import get_db

router = APIRouter(tags=["平台管理"])
OWNER = "認證"


@router.get("/admin/users", summary="帳號清單（停權用）")
@admin_required
def admin_list_users(me: User, db: Session = Depends(get_db)):
    """帳號清單（停權用）

    GET /api/admin/users

    【這支做什麼】
        平台管理頁的帳號清單：停權用，也是即時的紅綠燈（管理頁每 10 秒打一次）。
        presence：online 綠燈（90 秒內有請求）、idle 黃燈（15 分鐘內）、offline 紅燈（更久、或每一台都登出了）、suspended 停權。
        「最後一次有請求」記在 users.last_active_at，守衛每 30 秒最多寫一次（toolkit/security.py 的 touch）。
        ⚠️ 只有身分欄位與上線狀態：id、名字、email、家庭角色、註冊日、停權狀態、紅綠燈。收入、支出、存款目標一律不給——
           停權是關門，不是配鑰匙；一個讀得到全系統消費明細的帳號，比家長越權嚴重得多。
        其他平台管理員不列（他們不能被停權）；刪除了帳號的（只剩墓碑）也不列。

    【前端怎麼打】
        frontend/js/api.js 的 API.adminUsers()
        平台管理頁（#/admin）。前端檢查回應裡一定要有 users；頁面開著時每 10 秒重打一次，燈號跟著變。

    【誰能打】
        只有平台管理員。上面的 @admin_required 已經擋好了：
            沒登入 → 401；被停權、不是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的平台管理員（User 物件），me.id 是他的 id。

    【請求參數】沒有

    【成功回應】狀態碼 200
        {"users": [{"id": "5", "name": "王小華", "email": "xiaohua@wang.tw", "role": "child",
                    "joined": "2026-02-11", "suspendedAt": null, "suspendedReason": null,
                    "presence": "online", "lastActiveAt": "2026-10-20T03:05:12+00:00"}],
         "at": "2026-10-20T03:05:40+00:00"}
        · role 是家庭角色（parent／child），沒有家庭是 null
        · presence 是 online／idle／offline／suspended；lastActiveAt 是最後一次請求或登入（比較晚的那個），從來沒有過是 null
        · at 是伺服器現在的時間：前端拿它算「3 分鐘前」，不用自己電腦的時鐘
        · 照 id 排

    【錯誤回應】
        只有守衛的 401／403，這支本身不會出錯。

    【會用到的資料表】
        表              讀／寫  用來做什麼
        users           讀      不是平台管理員的帳號
        family_members  讀      每個人的家庭角色
        sessions        讀      誰還有沒登出、沒過期的登入

    【每一步用的工具與資料庫方法】
        步驟    呼叫                                                  做什麼
        1 帳號  crud.find(User, {"is_platform_admin": False, "deleted_at__isnull": True}, order_by="id", db=db)  所有一般帳號（刪除的不列）
        2 角色  crud.find(FamilyMember, {"status": "active"}, db=db)  做成 {user_id: role}
        3 登入  crud.find(UserSession, {"revoked_at__isnull": True, "expires_at__gt": now}, fields="user_id", db=db)  還登入著的人
        4 燈號  security.last_seen(u)                                 最後一次請求與最後一次登入，取比較晚的那個（補上時區）
                security.presence(最後請求, 還登入著, 停權中, now)    回 online／idle／offline／suspended
                u.suspended_at.isoformat()                            有停權才轉字串

    【寫法步驟】
        1. 查所有一般帳號
        2. 一次查出每個人的家庭角色
        3. 一次查出誰還有沒登出的登入
        4. 一個人一列，只放身分欄位與紅綠燈，連同伺服器現在的時間回傳
        ⚠️ 只讀不寫，不用 db.commit()。

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, Request
            from sqlalchemy.orm import Session

            from app.guards import admin_required
            from app.models import AuditLog, ErrorLog, FamilyMember, SecurityEvent, User, UserSession
            from app.routers._stub import not_ready, stub
            from app.schemas.auth import ClientErrorIn, SuspendIn
            from app.toolkit import crud, email_verify, errors, roles, security
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 所有一般帳號（其他平台管理員不列）
            users = crud.find(User, {"is_platform_admin": False, "deleted_at__isnull": True}, order_by="id", db=db)

            # 2. 每個人的家庭角色
            role_of = {m.user_id: m.role for m in crud.find(FamilyMember, {"status": "active"}, db=db)}

            # 3. 誰還有一台沒登出、沒過期的登入（按了登出就馬上是紅燈，不用等 15 分鐘）
            now = datetime.now(timezone.utc)
            signed_in = set(crud.find(UserSession, {"revoked_at__isnull": True, "expires_at__gt": now},
                                      fields="user_id", db=db))

            # 4. 只放身分欄位與上線狀態，任何金額都不給
            out = []
            ttl = timedelta(minutes=email_verify.TOKEN_MINUTES)
            for u in users:
                # 還沒點驗證信的帳號：連結還有效就列成「待驗證」；連結過期了就從後台消失（帳號也不能登入）
                waiting = u.email_verified_at is None
                if waiting:
                    sent = u.email_verify_sent_at or u.created_at
                    if sent.tzinfo is None:
                        sent = sent.replace(tzinfo=timezone.utc)
                    if now - sent > ttl:
                        continue
                last = security.last_seen(u)
                out.append({
                    "id": str(u.id),
                    "name": u.display_name,
                    "email": u.email,
                    "role": role_of.get(u.id),
                    "joined": u.created_at.date().isoformat(),
                    "suspendedAt": u.suspended_at.isoformat() if u.suspended_at else None,
                    "suspendedReason": u.suspended_reason,
                    "presence": "unverified" if waiting else security.presence(last, u.id in signed_in, u.suspended_at is not None, now),
                    "lastActiveAt": last.isoformat() if last else None,
                })
            return {"users": out, "at": now.isoformat()}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 GET /api/admin/users
        3. 按右上角 Authorize，貼上平台管理員登入拿到的 accessToken（帳號先用 python -m app.cli make-admin 你的信箱 設成管理員）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               平台管理員打  → 200，每個人只有九個欄位，沒有任何金額
               另一個視窗用一般帳號登入、隨便點一頁，再打一次 → 那個人的 presence 是 online
               那個帳號按登出，再打一次 → offline
               一般帳號打    → 403
        5. 前端改成連你的後端（frontend/index.html 的 api-base），平台管理頁列出所有帳號、紅綠燈與停權狀態
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "admin_list_users and 你的"，要全部通過
    """
    # 1. 所有一般帳號（其他平台管理員不列）
    users = crud.find(User, {"is_platform_admin": False, "deleted_at__isnull": True}, order_by="id", db=db)

    # 2. 每個人的家庭角色
    role_of = {m.user_id: m.role for m in crud.find(FamilyMember, {"status": "active"}, db=db)}

    # 3. 誰還有一台沒登出、沒過期的登入（按了登出就馬上是紅燈，不用等 15 分鐘）
    now = datetime.now(timezone.utc)
    signed_in = set(crud.find(UserSession, {"revoked_at__isnull": True, "expires_at__gt": now},
                              fields="user_id", db=db))

    # 4. 只放身分欄位與上線狀態，任何金額都不給
    out = []
    ttl = timedelta(minutes=email_verify.TOKEN_MINUTES)
    for u in users:
        # 還沒點驗證信的帳號：連結還有效就列成「待驗證」；連結過期了就從後台消失（帳號也不能登入）
        waiting = u.email_verified_at is None
        if waiting:
            sent = u.email_verify_sent_at or u.created_at
            if sent.tzinfo is None:
                sent = sent.replace(tzinfo=timezone.utc)
            if now - sent > ttl:
                continue
        last = security.last_seen(u)
        out.append({
            "id": str(u.id),
            "name": u.display_name,
            "email": u.email,
            "role": role_of.get(u.id),
            "joined": u.created_at.date().isoformat(),
            "suspendedAt": u.suspended_at.isoformat() if u.suspended_at else None,
            "suspendedReason": u.suspended_reason,
            "presence": "unverified" if waiting else security.presence(last, u.id in signed_in, u.suspended_at is not None, now),
            "lastActiveAt": last.isoformat() if last else None,
        })
    return {"users": out, "at": now.isoformat()}


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

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, Request
            from sqlalchemy.orm import Session

            from app.guards import admin_required
            from app.models import AuditLog, ErrorLog, FamilyMember, SecurityEvent, User, UserSession
            from app.routers._stub import not_ready, stub
            from app.schemas.auth import ClientErrorIn, SuspendIn
            from app.toolkit import crud, email_verify, errors, roles, security
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

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

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, Request
            from sqlalchemy.orm import Session

            from app.guards import admin_required
            from app.models import AuditLog, ErrorLog, FamilyMember, SecurityEvent, User, UserSession
            from app.routers._stub import not_ready, stub
            from app.schemas.auth import ClientErrorIn, SuspendIn
            from app.toolkit import crud, email_verify, errors, roles, security
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

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


@router.get("/admin/errors", summary="錯誤訊息")
@admin_required
def admin_errors(me: User, db: Session = Depends(get_db)):
    """錯誤訊息

    GET /api/admin/errors

    【這支做什麼】
        平台管理頁的「錯誤訊息」：最新 100 筆，管理頁每 10 秒打一次，新的那幾筆會亮一下。
        來源有兩種（都寫在 error_logs，寫入一律走 toolkit/security.py 的 log_error）：
            server  後端沒接住的錯誤（500）、路由自己丟的 5xx（例如模型叫不動的 503）——app/main.py 的兩個例外處理器記的
            client  使用者畫面上出的錯——前端打 POST /api/client-errors 回報的
        ⚠️ 使用者的畫面上只講「哪裡出了問題、可以怎麼做」，出錯的函式、路由、例外類型只出現在這裡。
        ⚠️ 只有訊息的第一行，SQL 與參數切掉（參數裡可能有金額）；不記請求內容。

    【前端怎麼打】
        frontend/js/api.js 的 API.adminErrors()
        平台管理頁（#/admin）的「錯誤訊息」區。前端檢查回應裡一定要有 errors。

    【誰能打】
        只有平台管理員。上面的 @admin_required 已經擋好了：
            沒登入 → 401；被停權、不是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的平台管理員（User 物件），me.id 是他的 id。

    【請求參數】沒有

    【成功回應】狀態碼 200
        {"errors": [{"id": "41", "at": "2026-10-20T03:05:00+00:00", "source": "client", "status": null,
                     "method": null, "path": "#/entry", "location": "vEntry", "message": "Cannot read properties of undefined",
                     "userName": "王小華"}],
         "lastHour": 3}
        · 由新到舊，最多 100 筆；userName 是遇到的人（沒登入是 null）
        · lastHour 是最近一小時的筆數

    【錯誤回應】
        只有守衛的 401／403，這支本身不會出錯。

    【會用到的資料表】
        表          讀／寫  用來做什麼
        error_logs  讀      錯誤紀錄
        users       讀      遇到錯誤的人的名字

    【每一步用的工具與資料庫方法】
        步驟    呼叫                                                      做什麼
        1 查    crud.find(ErrorLog, order_by="-id", limit=100, db=db)     最新的 100 筆
        2 名字  crud.find(User, {"id__in": […]}, db=db)                   一次查完
        3 數    crud.count(ErrorLog, {"created_at__gte": 一小時前}, db=db)  最近一小時幾筆
        4 時間  security.aware(r.created_at).isoformat()                  SQLite 讀回來沒有時區，補上 UTC

    【寫法步驟】
        1. 查最新的 100 筆
        2. 一次查出遇到的人的名字
        3. 數最近一小時幾筆
        4. 一筆一筆轉成前端要的形狀，回傳
        ⚠️ 只讀不寫，不用 db.commit()。

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, Request
            from sqlalchemy.orm import Session

            from app.guards import admin_required
            from app.models import AuditLog, ErrorLog, FamilyMember, SecurityEvent, User, UserSession
            from app.routers._stub import not_ready, stub
            from app.schemas.auth import ClientErrorIn, SuspendIn
            from app.toolkit import crud, email_verify, errors, roles, security
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 最新的 100 筆：後端沒接住的錯、模型叫不動的 503、使用者畫面上出的錯
            rows = crud.find(ErrorLog, order_by="-id", limit=100, db=db)

            # 2. 一次查出是誰遇到的（沒登入的是 null）
            ids = list({r.user_id for r in rows if r.user_id})
            names = {u.id: u.display_name for u in crud.find(User, {"id__in": ids}, db=db)} if ids else {}

            # 3. 最近一小時幾筆（管理頁上方的數字）
            hour = crud.count(ErrorLog, {"created_at__gte": datetime.now(timezone.utc) - timedelta(hours=1)}, db=db)

            return {
                "errors": [{
                    "id": str(r.id),
                    "at": security.aware(r.created_at).isoformat(),
                    "source": r.source,
                    "status": r.status,
                    "method": r.method,
                    "path": r.path,
                    "location": r.location,
                    "message": r.message,
                    "userName": names.get(r.user_id),
                } for r in rows],
                "lastHour": hour,
            }

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，先打 POST /api/client-errors，message 填「測試」
        3. 按右上角 Authorize，貼上平台管理員登入拿到的 accessToken
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               平台管理員打  → 200，第一筆是剛才那句「測試」，source 是 client
               一般帳號打    → 403
        5. 前端改成連你的後端（frontend/index.html 的 api-base），平台管理頁的「錯誤訊息」10 秒內出現新的那一筆
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "admin_errors and u4f60" -v，要全部通過
    """
    # 1. 最新的 100 筆：後端沒接住的錯、模型叫不動的 503、使用者畫面上出的錯
    rows = crud.find(ErrorLog, order_by="-id", limit=100, db=db)

    # 2. 一次查出是誰遇到的（沒登入的是 null）
    ids = list({r.user_id for r in rows if r.user_id})
    names = {u.id: u.display_name for u in crud.find(User, {"id__in": ids}, db=db)} if ids else {}

    # 3. 最近一小時幾筆（管理頁上方的數字）
    hour = crud.count(ErrorLog, {"created_at__gte": datetime.now(timezone.utc) - timedelta(hours=1)}, db=db)

    return {
        "errors": [{
            "id": str(r.id),
            "at": security.aware(r.created_at).isoformat(),
            "source": r.source,
            "status": r.status,
            "method": r.method,
            "path": r.path,
            "location": r.location,
            "message": r.message,
            "userName": names.get(r.user_id),
        } for r in rows],
        "lastHour": hour,
    }


@router.get("/admin/security-events", summary="安全事件")
@admin_required
def admin_security_events(me: User, db: Session = Depends(get_db)):
    """安全事件

    GET /api/admin/security-events

    【這支做什麼】
        平台管理頁的「安全事件」：被規則擋下來的請求，以及今天的用量。管理頁每 10 秒打一次。
        規則在 toolkit/security.py（登入錯太多次鎖 15 分鐘、同一來源大量註冊、AI 每日額度、找人太頻繁、確認密碼錯太多次），
        全部是「數過去一段時間發生了幾次」，**不用 AI 判斷**；規則只會暫時擋下、時間到自己解開。
        ⚠️ 要不要停權由管理員決定（列上有停權鈕，走 POST /api/admin/users/{user_id}/suspend）——系統不自動停權。
        只列程度「中」「高」的：登入失敗一次一筆太多（家人打錯密碼也算），只放進 today 的總數，鎖住了才列出來。

    【前端怎麼打】
        frontend/js/api.js 的 API.adminSecurityEvents()
        平台管理頁（#/admin）的「安全事件」區與上方的數字。前端檢查回應裡一定要有 events、today。

    【誰能打】
        只有平台管理員。上面的 @admin_required 已經擋好了：
            沒登入 → 401；被停權、不是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的平台管理員（User 物件），me.id 是他的 id。

    【請求參數】沒有

    【成功回應】狀態碼 200
        {"events": [{"id": "12", "at": "2026-10-20T03:05:00+00:00", "kind": "login_locked", "level": "high",
                     "levelText": "高", "title": "同一個帳號登入失敗太多次，暫時鎖住 15 分鐘",
                     "detail": "15 分鐘內錯了 5 次", "userId": "5", "userName": "王小華",
                     "email": "xiaohua@wang.tw", "suspended": false, "canSuspend": true}],
         "today": {"loginFailed": 7, "locked": 1, "registered": 2, "aiParse": 35, "aiAdvice": 3}}
        · 由新到舊，最多 100 筆；level 是 high／medium，levelText 是「高」「中」
        · 帳號不存在的登入失敗查不到是誰：userId、userName、email 都是 null，也不能停權
        · canSuspend：查得到人、不是平台管理員、還沒被停權
        · today 從台灣時間今天 00:00 算起：登入失敗、被鎖住、註冊、AI 解析、AI 產生建議各幾次

    【錯誤回應】
        只有守衛的 401／403，這支本身不會出錯。

    【會用到的資料表】
        表               讀／寫  用來做什麼
        security_events  讀      安全事件與今天的用量
        users            讀      事件是誰的

    【每一步用的工具與資料庫方法】
        步驟    呼叫                                                                 做什麼
        1 查    security.KINDS                                                       kind → (程度, 標題)
                crud.find(SecurityEvent, {"kind__in": […]}, order_by="-id", limit=100, db=db)  中、高的最新 100 筆
        2 名字  crud.find(User, {"id__in": […]}, db=db)                              一次查完
        3 今天  security.today_start()                                               台灣時間今天 00:00（轉成 UTC）
                security.count(kind 或 (kind, …), 從什麼時候, db=db)                  那幾種事件發生了幾次
        4 時間  security.aware(r.created_at).isoformat()                             補上時區

    【寫法步驟】
        1. 挑出程度是中、高的事件種類，查最新的 100 筆
        2. 一次查出是誰
        3. 數今天的用量
        4. 一筆一列（程度、標題照 KINDS），連同今天的數字回傳
        ⚠️ 只讀不寫，不用 db.commit()。

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, Request
            from sqlalchemy.orm import Session

            from app.guards import admin_required
            from app.models import AuditLog, ErrorLog, FamilyMember, SecurityEvent, User, UserSession
            from app.routers._stub import not_ready, stub
            from app.schemas.auth import ClientErrorIn, SuspendIn
            from app.toolkit import crud, email_verify, errors, roles, security
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 要讓管理員看的事件：程度是「中」「高」的。
            #    註冊、AI 呼叫只是計數；登入失敗一次一筆太多（家人打錯密碼也算），只算總數，鎖住了才列出來
            shown = [k for k, (level, _title) in security.KINDS.items() if level in ("high", "medium")]
            rows = crud.find(SecurityEvent, {"kind__in": shown}, order_by="-id", limit=100, db=db)

            # 2. 一次查出是誰（帳號不存在的登入失敗沒有 user_id）
            ids = list({r.user_id for r in rows if r.user_id})
            people = {u.id: u for u in crud.find(User, {"id__in": ids}, db=db)} if ids else {}

            # 3. 今天（台灣時間）的數字
            start = security.today_start()
            today = {
                "loginFailed": security.count("login_failed", start, db=db),
                "locked": security.count(("login_locked", "source_locked", "verify_locked"), start, db=db),
                "registered": security.count("register", start, db=db),
                "aiParse": security.count("ai_parse", start, db=db),
                "aiAdvice": security.count("ai_advice", start, db=db),
            }

            # 4. 一筆一列：程度與標題由 security.KINDS 決定，前端照著顯示
            out = []
            for r in rows:
                level, title = security.KINDS[r.kind]
                who = people.get(r.user_id)
                out.append({
                    "id": str(r.id),
                    "at": security.aware(r.created_at).isoformat(),
                    "kind": r.kind,
                    "level": level,
                    "levelText": security.LEVEL_TEXT[level],
                    "title": title,
                    "detail": r.detail or "",
                    "userId": str(who.id) if who else None,
                    "userName": who.display_name if who else None,
                    "email": who.email if who else None,
                    "suspended": bool(who and who.suspended_at),
                    "canSuspend": bool(who and not who.is_platform_admin and not who.suspended_at),
                })
            return {"events": out, "today": today}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，用一個帳號打 POST /api/auth/login，故意打錯密碼 5 次
        3. 按右上角 Authorize，貼上平台管理員登入拿到的 accessToken
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               平台管理員打  → 200，第一筆是 login_locked，today.loginFailed 是 5
               一般帳號打    → 403
        5. 前端改成連你的後端（frontend/index.html 的 api-base），平台管理頁的「安全事件」10 秒內出現那一筆，按停權會先問理由
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "admin_security_events and u4f60" -v，要全部通過
    """
    # 1. 要讓管理員看的事件：程度是「中」「高」的。
    #    註冊、AI 呼叫只是計數；登入失敗一次一筆太多（家人打錯密碼也算），只算總數，鎖住了才列出來
    shown = [k for k, (level, _title) in security.KINDS.items() if level in ("high", "medium")]
    rows = crud.find(SecurityEvent, {"kind__in": shown}, order_by="-id", limit=100, db=db)

    # 2. 一次查出是誰（帳號不存在的登入失敗沒有 user_id）
    ids = list({r.user_id for r in rows if r.user_id})
    people = {u.id: u for u in crud.find(User, {"id__in": ids}, db=db)} if ids else {}

    # 3. 今天（台灣時間）的數字
    start = security.today_start()
    today = {
        "loginFailed": security.count("login_failed", start, db=db),
        "locked": security.count(("login_locked", "source_locked", "verify_locked"), start, db=db),
        "registered": security.count("register", start, db=db),
        "aiParse": security.count("ai_parse", start, db=db),
        "aiAdvice": security.count("ai_advice", start, db=db),
    }

    # 4. 一筆一列：程度與標題由 security.KINDS 決定，前端照著顯示
    out = []
    for r in rows:
        level, title = security.KINDS[r.kind]
        who = people.get(r.user_id)
        out.append({
            "id": str(r.id),
            "at": security.aware(r.created_at).isoformat(),
            "kind": r.kind,
            "level": level,
            "levelText": security.LEVEL_TEXT[level],
            "title": title,
            "detail": r.detail or "",
            "userId": str(who.id) if who else None,
            "userName": who.display_name if who else None,
            "email": who.email if who else None,
            "suspended": bool(who and who.suspended_at),
            "canSuspend": bool(who and not who.is_platform_admin and not who.suspended_at),
        })
    return {"events": out, "today": today}


@router.post("/client-errors", status_code=202, summary="回報畫面上出的錯")
def report_client_error(body: ClientErrorIn, request: Request, db: Session = Depends(get_db)):
    """回報畫面上出的錯

    POST /api/client-errors

    【這支做什麼】
        使用者的畫面上出了錯（畫面程式出錯、回應形狀不對、連不上），前端把技術細節送到這裡，
        平台管理頁的「錯誤訊息」即時看得到。使用者的畫面上只講「哪裡出了問題、可以怎麼做」。
        ⚠️ 只收訊息、畫面、函式名稱，不收請求內容（金額、備註）。
        ⚠️ 防洗版：同一個人 10 分鐘最多 30 筆；沒登入的全部加起來 1 分鐘最多 20 筆；同一句話 1 分鐘內只記一次。
           超過不回錯，回 {"accepted": false}——回報錯誤的地方再出錯，前端只會一直重送。

    【前端怎麼打】
        frontend/js/api.js 的 API.reportError({ message, location, page, status })
        畫面出錯時（app.js 的錯誤卡、window.onerror）在背景送出，不等回應、失敗也不提示。

    【誰能打】
        任何人都能打，不用登入（登入頁也可能出錯）。帶了有效的 access token 就記下是誰遇到的。
        另外收一個 request（FastAPI 的 Request）：從 Authorization 讀是誰（security.user_from）。

    【請求主體】body 是 ClientErrorIn（app/schemas/auth.py）
        欄位      型別  必填  說明
        message   字串  是    1～2000 字；只留前 300 字，換行壓成空白
        location  字串  否    出錯的函式（API.summary、vEntry…），最多 200 字
        page      字串  否    出錯的畫面（#/entry），最多 200 字
        status    數字  否    HTTP 狀態碼（回應形狀不對時是那一支的狀態碼）
        範例：{"message": "Cannot read properties of undefined", "location": "vEntry", "page": "#/entry"}

    【成功回應】狀態碼 202
        {"accepted": true}
        · 被防洗版擋下來也是 202，accepted 是 false

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候          detail
        422     message 全是空白  錯誤訊息是空的
        422     欄位太長          （FastAPI 自動回）

    【會用到的資料表】
        表          讀／寫  用來做什麼
        error_logs  讀＋寫  數最近幾筆（防洗版）；新增一筆 source=client

    【每一步用的工具與資料庫方法】
        步驟      呼叫                                                       做什麼
        1 整理    " ".join(body.message.split())[:300]                       壓掉換行與連續空白
                  security.user_from(request)                                有效的 access token → user id；沒有是 None
        2 防洗版  crud.count(ErrorLog, {…, "created_at__gte": …}, db=db)     最近幾筆
                  crud.exists(ErrorLog, {…, "message": message, …}, db=db)   同一句話一分鐘內記過了沒
        3 記下來  crud.save(ErrorLog, {…}, db=db)＋db.commit()

    【寫法步驟】
        1. 整理訊息；全是空白 → 422；讀出是誰
        2. 太多、或同一句話剛記過 → 回 {"accepted": false}
        3. 新增一筆、commit，回 {"accepted": true}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, Request
            from sqlalchemy.orm import Session

            from app.guards import admin_required
            from app.models import AuditLog, ErrorLog, FamilyMember, SecurityEvent, User, UserSession
            from app.routers._stub import not_ready, stub
            from app.schemas.auth import ClientErrorIn, SuspendIn
            from app.toolkit import crud, email_verify, errors, roles, security
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 整理：壓掉換行與連續空白、最多 300 字；全是空白不收
            message = " ".join(body.message.split())[:300]
            if not message:
                raise errors.unprocessable("錯誤訊息是空的")
            uid = security.user_from(request)

            # 2. 防洗版：同一個人 10 分鐘最多 30 筆；沒登入的全部加起來 1 分鐘最多 20 筆；同一句話 1 分鐘內只記一次
            now = datetime.now(timezone.utc)
            who = {"user_id": uid} if uid else {"user_id__isnull": True}
            if uid:
                flood = crud.count(ErrorLog, {"source": "client", "user_id": uid,
                                              "created_at__gte": now - timedelta(minutes=10)}, db=db) >= 30
            else:
                flood = crud.count(ErrorLog, {"source": "client", "user_id__isnull": True,
                                              "created_at__gte": now - timedelta(minutes=1)}, db=db) >= 20
            same = crud.exists(ErrorLog, {"source": "client", **who, "message": message,
                                          "created_at__gte": now - timedelta(minutes=1)}, db=db)
            if flood or same:
                return {"accepted": False}

            # 3. 記下來：哪個畫面、哪個函式、什麼訊息。不收請求內容（金額、備註）
            crud.save(ErrorLog, {"source": "client", "status": body.status, "method": None,
                                 "path": (body.page or "")[:200] or None, "location": (body.location or "")[:200] or None,
                                 "message": message, "user_id": uid}, db=db)
            db.commit()
            return {"accepted": True}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/client-errors
        3. 這支不用登入，不用按 Authorize（按了的話會記下是誰）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               message 填「測試」          → 202，accepted 是 true
               同一句話馬上再送一次        → 202，accepted 是 false
               message 填三個空白          → 422
        5. 前端改成連你的後端（frontend/index.html 的 api-base），平台管理頁的「錯誤訊息」出現「測試」
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "report_client_error and u4f60" -v，要全部通過
    """
    # 1. 整理：壓掉換行與連續空白、最多 300 字；全是空白不收
    message = " ".join(body.message.split())[:300]
    if not message:
        raise errors.unprocessable("錯誤訊息是空的")
    uid = security.user_from(request)

    # 2. 防洗版：同一個人 10 分鐘最多 30 筆；沒登入的全部加起來 1 分鐘最多 20 筆；同一句話 1 分鐘內只記一次
    now = datetime.now(timezone.utc)
    who = {"user_id": uid} if uid else {"user_id__isnull": True}
    if uid:
        flood = crud.count(ErrorLog, {"source": "client", "user_id": uid,
                                      "created_at__gte": now - timedelta(minutes=10)}, db=db) >= 30
    else:
        flood = crud.count(ErrorLog, {"source": "client", "user_id__isnull": True,
                                      "created_at__gte": now - timedelta(minutes=1)}, db=db) >= 20
    same = crud.exists(ErrorLog, {"source": "client", **who, "message": message,
                                  "created_at__gte": now - timedelta(minutes=1)}, db=db)
    if flood or same:
        return {"accepted": False}

    # 3. 記下來：哪個畫面、哪個函式、什麼訊息。不收請求內容（金額、備註）
    crud.save(ErrorLog, {"source": "client", "status": body.status, "method": None,
                         "path": (body.page or "")[:200] or None, "location": (body.location or "")[:200] or None,
                         "message": message, "user_id": uid}, db=db)
    db.commit()
    return {"accepted": True}
