"""
家庭：建立、邀請、成員角色、解散、監管關係、零用金、稽核。

負責人：成員4（家庭）　✦ 分支：m4-access

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

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import catalog
from app.guards import admin_required, block_admin, family_required, parent_required, protect, visible_scope
from app.models import (
    Allowance, AuditLog, Family, FamilyInvite, FamilyMember, Group, GroupMember, Guardianship, SavingsGoal,
    Transaction, User,
)
from app.routers._stub import not_ready, stub
from app.schemas.family import AllowanceIn, FamilyIn, GuardianshipIn, InviteCodeIn, InviteIn, JoinIn, RolePatchIn
from app.toolkit import crud, errors, family, images, money, password_reset, period
from app.toolkit.config import settings
from app.toolkit.db import get_db

router = APIRouter(tags=["家庭與權限"])
OWNER = "成員4"


@router.get("/family", summary="家庭、成員、監管關係")
@block_admin
@stub
def get_family(me: User, db: Session = Depends(get_db)):
    """家庭、成員、監管關係

    GET /api/family

    【這支做什麼】
        家庭成員頁的全部資料：我是誰、我的角色、家庭、成員卡片、監管關係，以及兩份固定的說明（角色、權限表）。
        ⚠️ 名字、角色、監管關係是公開的（被照看的人一定要知道誰在看他）；
           存款目標是個人財務資料：不在 visible 裡的人，members 裡就不要放他的 savingsGoal。
        ⚠️ members 只列同一個家庭的人；還沒有家庭時只有自己。平台管理員永遠不會出現在這裡。

    【前端怎麼打】
        frontend/js/api.js 的 API.members()
        家庭成員頁、成員紀錄頁、帳本的加人選單，也是前端補名字的對照表。前端檢查回應裡一定要有 family、members、guardianships。

    【誰能打】
        登入、沒被停權、不是平台管理員。上面的 @block_admin 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【請求參數】沒有

    【成功回應】狀態碼 200
        {"me": "3", "myRole": "parent",
         "family": {"id": "2", "name": "王家", "createdBy": "3"},
         "visible": ["3", "4", "5"], "queryable": ["3", "4", "5", "6"],
         "members": [{"id": "3", "name": "王大明", "email": "daming@wang.tw", "role": "parent", "familyId": "2",
                      "avatar": "明", "avatarUrl": null, "age": 52, "joined": "2026-01-05", "savingsGoal": 20000}],
         "roles": [{"id": "parent", "name": "家長", "layer": "家庭", "desc": "…"}],
         "guardianships": [{"id": "7", "guardian": "3", "ward": "5", "since": "2026-02-11", "scope": "全部明細",
                            "guardianName": "王大明", "wardName": "王小華"}],
         "permissions": [{"action": "記錄自己的收支", "parent": "Y", "child": "Y"}]}
        欄位                   怎麼來的
        visible                看得到全部紀錄的人：自己＋我照看的人＋同家庭的其他家長（自己排第一個）
        queryable              visible 再加上跟我共用帳本的人（只看得到共用帳本那部分）
        family                 還沒有家庭是 null——前端靠這個決定畫「建立／加入」還是成員卡片
        members[].age          今年 − birth_year。⚠️ 只是顯示用，任何權限判斷都不准讀它
        members[].savingsGoal  只有 visible 裡的人才有這個欄位
        roles／permissions     app/catalog.py 的 ROLES、PERMISSIONS（固定的說明資料，不建表）

    【錯誤回應】
        只有守衛的 401／403，這支本身不會出錯。

    【會用到的資料表】
        表                                                    讀／寫  用來做什麼
        guardianships、family_members、group_members、groups  讀      visible_scope()
        group_members                                         讀      跟我共用帳本的人（queryable）
        families、family_members                              讀      我的家庭、成員與角色
        users                                                 讀      成員的名字、email、頭像、出生年
        savings_goals                                         讀      看得到的人的整體存款目標（最新一筆）
        guardianships                                         讀      家庭裡還有效的監管關係

    【每一步用的工具與資料庫方法】
        步驟        呼叫                                               做什麼
        1 看得到誰  users, groups = visible_scope(me, db)              兩個 set
                    users.union(sharing)                               兩份合起來（聯集），重複的只留一個
        2 家庭      crud.get(Family, me.family_id, db=db)              用主鍵拿我的家庭
                    crud.find(FamilyMember, {"family_id": …, "status": "active"}, order_by="joined_at", db=db)  成員，照加入先後
                    crud.find(User, {"id__in": ids, "is_platform_admin": False}, db=db)  成員本人（排掉平台管理員）
        3 目標      crud.find(SavingsGoal, {"user_id__in": users, "group_id__isnull": True}, order_by="id", db=db)  只查看得到的人
        4 卡片      images.to_data_uri(u.avatar_bytes, u.avatar_mime)  有大頭貼才轉
        5 監管      crud.find(Guardianship, {"guardian_id__in": ids, "ward_id__in": ids, "ended_at__isnull": True}, db=db)  兩邊都是這一家的人、還沒結束
                    catalog.ROLES／catalog.PERMISSIONS                 固定清單，直接回

    【寫法步驟】
        1. visible_scope 拿到看得到的人與帳本；帳本裡的人併進去就是 queryable
        2. 有家庭：查家庭與成員；沒有：成員只有自己
        3. 查看得到的人的存款目標
        4. 一個一個組成員卡片：看得到的人才放 savingsGoal
        5. 查這一家還有效的監管關係
        6. 全部組起來：visible、queryable 自己排第一個，其他照 id 排
        ⚠️ 只讀不寫，不用 db.commit()。

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, HTTPException, Query
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import admin_required, block_admin, family_required, parent_required, protect, visible_scope
            from app.models import (
                Allowance, AuditLog, Family, FamilyInvite, FamilyMember, Group, GroupMember, Guardianship, SavingsGoal,
                Transaction, User,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.family import AllowanceIn, FamilyIn, GuardianshipIn, InviteCodeIn, InviteIn, JoinIn, RolePatchIn
            from app.toolkit import crud, errors, family, images, money, password_reset, period
            from app.toolkit.config import settings
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 我看得到誰（全部紀錄）、查得到誰（再加上共用帳本的人）
            users, groups = visible_scope(me, db)
            sharing = crud.find(GroupMember, {"group_id__in": groups}, fields="user_id", db=db)
            queryable = users.union(sharing)

            # 2. 我的家庭與成員；還沒有家庭時，成員只有自己
            fam = crud.get(Family, me.family_id, db=db) if me.family_id else None
            rows = []
            if fam:
                rows = crud.find(FamilyMember, {"family_id": fam.id, "status": "active"}, order_by="joined_at", db=db)
            role_of = {r.user_id: r.role for r in rows}
            ids = [r.user_id for r in rows] or [me.id]
            people = {u.id: u for u in crud.find(User, {"id__in": ids, "is_platform_admin": False}, db=db)}

            # 3. 存款目標只查看得到的人（每人最新的整體目標）
            goals = {}
            for g in crud.find(SavingsGoal, {"user_id__in": users, "group_id__isnull": True}, order_by="id", db=db):
                goals[g.user_id] = g.goal_amount

            # 4. 成員卡片：看得到的人才放存款目標
            this_year = datetime.now(timezone(timedelta(hours=8))).year
            members = []
            for uid in ids:
                u = people.get(uid)
                if u is None:
                    continue
                card = {
                    "id": str(u.id),
                    "name": u.display_name,
                    "email": u.email,
                    "role": role_of.get(u.id),
                    "familyId": str(fam.id) if fam else None,
                    "avatar": u.display_name[-1:],
                    "avatarUrl": images.to_data_uri(u.avatar_bytes, u.avatar_mime) if u.avatar_bytes else None,
                    "age": this_year - u.birth_year if u.birth_year else None,
                    "joined": u.created_at.date().isoformat(),
                }
                if u.id in users:
                    card["savingsGoal"] = goals.get(u.id, 0)
                members.append(card)

            # 5. 這一家還有效的監管關係（雙向可見）
            guardianships = []
            if fam:
                for g in crud.find(Guardianship, {"guardian_id__in": ids, "ward_id__in": ids,
                                                  "ended_at__isnull": True}, order_by="id", db=db):
                    guardianships.append({
                        "id": str(g.id),
                        "guardian": str(g.guardian_id),
                        "ward": str(g.ward_id),
                        "since": g.since.date().isoformat(),
                        "scope": g.scope,
                        "guardianName": people[g.guardian_id].display_name if g.guardian_id in people else "",
                        "wardName": people[g.ward_id].display_name if g.ward_id in people else "",
                    })

            # 6. 全部組起來（自己排第一個）
            return {
                "me": str(me.id),
                "myRole": me.family_role,
                "family": {"id": str(fam.id), "name": fam.name, "createdBy": str(fam.created_by)} if fam else None,
                "visible": [str(me.id)] + [str(u) for u in sorted(users) if u != me.id],
                "queryable": [str(me.id)] + [str(u) for u in sorted(queryable) if u != me.id],
                "members": members,
                "roles": catalog.ROLES,
                "guardianships": guardianships,
                "permissions": catalog.PERMISSIONS,
            }

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 GET /api/family
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               還沒有家庭的人        → family 是 null，members 只有自己
               家長（照看一個孩子）  → 孩子與另一位家長有 savingsGoal；沒照看的孩子沒有這個欄位
               子女                  → 只有自己有 savingsGoal，但看得到全家的名字與監管關係
        5. 前端改成連你的後端（frontend/index.html 的 api-base），家庭成員頁的卡片、照看中的標記要對
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "get_family and 你的"，要全部通過
    """
    raise not_ready("GET /api/family", OWNER)


@router.post("/family", status_code=201, summary="建立家庭（建立的人是家長）")
@protect(family=False, platform_admin=False)
@stub
def create_family(body: FamilyIn, me: User, db: Session = Depends(get_db)):
    """建立家庭（建立的人是家長）

    POST /api/family

    【這支做什麼】
        還沒有家庭的人建立一個家庭，建立的人成為家長。

    【前端怎麼打】
        frontend/js/api.js 的 API.createFamily({ name })
        家庭頁「建立我的家庭」。成功之後前端重拿成員清單、重畫帳號選單。

    【誰能打】
        登入、沒被停權、不是平台管理員、而且還沒有家庭。
        上面的 @protect(family=False, platform_admin=False) 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403；已經在一個家庭裡 → 409「你已經在一個家庭裡了」
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件），me.id 是他的 id。

    【請求主體】body 是 FamilyIn（app/schemas/family.py）
        欄位  型別  必填  說明
        name  字串  是    1～20 字（FastAPI 先擋）；去頭尾空白、壓掉連續空白後不能是空的
        範例：{"name": "王家"}

    【成功回應】狀態碼 201
        {"family": {"id": "2", "name": "王家", "createdBy": "3", "createdAt": "2026-09-17"}, "role": "parent"}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                  detail
        403     平台管理員                平台管理員不能使用財務功能（守衛回）
        409     已經在一個家庭裡          你已經在一個家庭裡了（守衛回）
        422     名稱整理完是空的          幫你的家庭取個名字，例如「林家」
        422     名稱是空字串、超過 20 字  （FastAPI 自動回）

    【會用到的資料表】
        表              讀／寫  用來做什麼
        families        寫      新增家庭
        family_members  寫      先拿掉我以前離開家庭留下的那一列，再新增一列（role = parent）
        audit_logs      寫      create_family

    【每一步用的工具與資料庫方法】
        步驟    呼叫                                                        做什麼
        1 名稱  family.clean_family_name(body.name)                         整理空白、最多 20 字；空的丟 ValueError
        2 新增  crud.save(Family, {"name": …, "created_by": me.id}, db=db)  新增家庭，拿到 id
                crud.remove(FamilyMember, {"user_id": me.id, "status": "removed"}, db=db)  以前離開過的那一列
                crud.save(FamilyMember, {"family_id": …, "user_id": me.id, "role": "parent"}, db=db)  兩個主鍵都帶 → 新增
                crud.save(AuditLog, {…}, db=db)                             稽核只記動作，不記金額
                db.commit()                                                 全部一起寫進去
        ⚠️ 為什麼要先拿掉 removed 那一列：family_members.user_id 是 UNIQUE（一個人只能有一列），
           以前離開過家庭的人不先拿掉，就再也加不進任何家庭。離開的紀錄在 audit_logs 裡查得到。

    【寫法步驟】
        1. clean_family_name（422）
        2. 新增家庭 → 拿掉我以前的 removed 列 → 新增我這一列（家長）→ 寫稽核
        3. db.commit()，回傳 {family, role}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, HTTPException, Query
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import admin_required, block_admin, family_required, parent_required, protect, visible_scope
            from app.models import (
                Allowance, AuditLog, Family, FamilyInvite, FamilyMember, Group, GroupMember, Guardianship, SavingsGoal,
                Transaction, User,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.family import AllowanceIn, FamilyIn, GuardianshipIn, InviteCodeIn, InviteIn, JoinIn, RolePatchIn
            from app.toolkit import crud, errors, family, images, money, password_reset, period
            from app.toolkit.config import settings
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 整理名稱
            try:
                name = family.clean_family_name(body.name)
            except ValueError as exc:
                raise errors.unprocessable(str(exc)) from None

            # 2. 新增家庭，建立的人是家長
            fam = crud.save(Family, {"name": name, "created_by": me.id}, db=db)
            crud.remove(FamilyMember, {"user_id": me.id, "status": "removed"}, db=db)
            crud.save(FamilyMember, {"family_id": fam.id, "user_id": me.id, "role": "parent"}, db=db)
            crud.save(AuditLog, {"actor_id": me.id, "action": "create_family", "target_type": "family",
                                 "target_id": fam.id, "meta_json": {"note": "建立「%s」" % name}}, db=db)
            db.commit()
            return {
                "family": {"id": str(fam.id), "name": fam.name, "createdBy": str(me.id),
                           "createdAt": fam.created_at.date().isoformat()},
                "role": "parent",
            }

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/family
        3. 按右上角 Authorize，貼上一個「還沒有家庭」的人登入拿到的 accessToken
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               {"name": " 王家 "}  → 201，name 是「王家」、role 是 parent
               再建一次            → 409
               {"name": "   "}     → 422
        5. 打 GET /api/auth/me → user.role 變成 parent
        6. 前端改成連你的後端（frontend/index.html 的 api-base），家庭頁「建立我的家庭」，畫面換成成員卡片
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "create_family and 你的"，要全部通過
    """
    raise not_ready("POST /api/family", OWNER)


@router.delete("/family", summary="解散家庭（唯一的家長）")
@parent_required
@stub
def dissolve_family(me: User, db: Session = Depends(get_db)):
    """解散家庭（唯一的家長）

    DELETE /api/family

    【這支做什麼】
        唯一的家長解散家庭：每個人都離開，同一個交易裡一起收掉——
            · 家人之間的監管關係結束（ended_at），零用金歸零
            · 家人之間的帳本互相移出（每本帳只留下開帳的人）
            · 還沒回覆的邀請、還沒用的邀請碼作廢（cancelled）
        ⚠️ 紀錄一筆都不刪：每一筆仍在記帳的人自己的明細裡；帳本也還在，只是不再共用。
        ⚠️ 家裡還有其他家長時不行：一個人不能替另一位家長決定解散，他可以自己退出。

    【前端怎麼打】
        frontend/js/api.js 的 API.dissolveFamily()
        家庭成員頁最下面「解散家庭」（只有唯一的家長看得到），先輸入確認碼、再用密碼確認（POST /api/auth/verify-password）。

    【誰能打】
        登入、沒被停權、而且是家長。上面的 @parent_required 已經擋好了：
            沒登入 → 401；被停權、不是家長（子女、還沒有家庭、平台管理員）→ 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（這裡一定有值）
            me.family_role   一定是 'parent'

    【請求主體】沒有

    【成功回應】狀態碼 200
        {"dissolved": true, "family": {"id": "2", "name": "王家"}, "released": 4}
        · released = 離開家庭的人數（含自己）

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候            detail
        403     不是家長、沒有家庭  只有家長可以做這件事（守衛回）
        409     家裡還有其他家長    家裡還有其他家長，不能一個人解散。你可以自己退出家庭

    【會用到的資料表】
        表              讀／寫    用來做什麼
        family_members  讀＋寫    這一家有誰；每個人 status 改成 removed
        guardianships   寫        跟這些人有關、還有效的，設 ended_at
        allowances      寫        這些人之間的零用金設成 0
        groups          讀        這些人開的帳本
        group_members   寫（刪）  每本帳只留下開帳的人
        family_invites  寫        這一家還沒回覆的邀請、邀請碼 → cancelled
        audit_logs      寫        dissolve_family

    【每一步用的工具與資料庫方法】
        步驟          呼叫                                                       做什麼
        1 能不能解散  family.require_can_dissolve(me.family_role, 其他家長人數)  還有別的家長丟 ValueError
        2 離開        crud.save(FamilyMember, {"status": "removed"}, where={"family_id": …, "user_id__in": people}, db=db)  有 where = 一次改很多列
        3 監管        crud.save(Guardianship, {"ended_at": now}, where={"ended_at__isnull": True, "or": [...]}, db=db)  監管人或被照看的人是這一家的
                      crud.save(Allowance, {"amount": 0}, where={"payer_id__in": people, "ward_id__in": people}, db=db)  零用金歸零（設定，不是紀錄）
        4 帳本        crud.remove(GroupMember, {"group_id": g.id, "user_id__in": people, "user_id__ne": g.created_by}, db=db)  開帳的人以外的家人都移出
        5 邀請        crud.save(FamilyInvite, {"status": "cancelled", …}, where={"family_id": …, "status": "pending"}, db=db)  邀請與邀請碼一起作廢
        6 存檔        db.commit()                                                全部在同一個交易裡寫進去
        ⚠️ 全部帶 db=db、最後才 commit：解散到一半失敗的話，會留下「人還在、監管沒了」這種說不清的狀態。

    【寫法步驟】
        1. 查這一家的成員；除了我以外還有家長 → 409
        2. 每個人 status 改成 removed
        3. 監管關係結束、零用金歸零
        4. 這些人開的帳本，把其他家人移出
        5. 邀請、邀請碼作廢；寫稽核
        6. db.commit()，回傳 {dissolved, family, released}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, HTTPException, Query
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import admin_required, block_admin, family_required, parent_required, protect, visible_scope
            from app.models import (
                Allowance, AuditLog, Family, FamilyInvite, FamilyMember, Group, GroupMember, Guardianship, SavingsGoal,
                Transaction, User,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.family import AllowanceIn, FamilyIn, GuardianshipIn, InviteCodeIn, InviteIn, JoinIn, RolePatchIn
            from app.toolkit import crud, errors, family, images, money, password_reset, period
            from app.toolkit.config import settings
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 只有唯一的家長能解散
            rows = crud.find(FamilyMember, {"family_id": me.family_id, "status": "active"}, db=db)
            people = [r.user_id for r in rows]
            other_parents = len([r for r in rows if r.role == "parent" and r.user_id != me.id])
            try:
                family.require_can_dissolve(me.family_role, other_parents)
            except ValueError as exc:
                raise errors.conflict(str(exc)) from None
            fam = crud.get(Family, me.family_id, db=db)
            now = datetime.now(timezone.utc)

            # 2. 每個人都離開家庭（紀錄一筆都不刪）
            crud.save(FamilyMember, {"status": "removed"}, where={"family_id": fam.id, "user_id__in": people}, db=db)

            # 3. 家人之間的監管關係結束，零用金歸零
            crud.save(Guardianship, {"ended_at": now}, where={
                "ended_at__isnull": True,
                "or": [{"guardian_id__in": people}, {"ward_id__in": people}],
            }, db=db)
            crud.save(Allowance, {"amount": 0}, where={"payer_id__in": people, "ward_id__in": people}, db=db)

            # 4. 家人之間的帳本互相移出：每本帳只留下開帳的人
            for g in crud.find(Group, {"created_by__in": people}, db=db):
                crud.remove(GroupMember, {"group_id": g.id, "user_id__in": people, "user_id__ne": g.created_by}, db=db)

            # 5. 還沒回覆的邀請與邀請碼作廢，寫稽核
            crud.save(FamilyInvite, {"status": "cancelled", "responded_at": now},
                      where={"family_id": fam.id, "status": "pending"}, db=db)
            crud.save(AuditLog, {"actor_id": me.id, "action": "dissolve_family", "target_type": "family",
                                 "target_id": fam.id,
                                 "meta_json": {"note": "解散「%s」（%d 人離開）" % (fam.name, len(people))}}, db=db)
            db.commit()
            return {"dissolved": True, "family": {"id": str(fam.id), "name": fam.name}, "released": len(people)}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 DELETE /api/family
        3. 按右上角 Authorize，貼上「唯一的家長」登入拿到的 accessToken
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               家裡還有另一位家長時打  → 409
               只有你一位家長時打      → 200，released 是全家人數
        5. 家人打 GET /api/auth/me → family 變成 null；GET /api/transactions 自己的紀錄都還在
        6. 前端改成連你的後端（frontend/index.html 的 api-base），家庭成員頁「解散家庭」走完確認流程，每個人都回到「建立／加入」畫面
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "dissolve_family and 你的"，要全部通過
    """
    raise not_ready("DELETE /api/family", OWNER)


@router.post("/family/invite", status_code=201, summary="產生邀請碼")
@parent_required
@stub
def create_invite_code(body: InviteCodeIn, me: User, db: Session = Depends(get_db)):
    """產生邀請碼

    POST /api/family/invite

    【這支做什麼】
        家長產生一組邀請碼（例如 K7QM-3XWP），傳給家人輸入就能加入。
        ⚠️ 身分由家長決定，碼本身帶著身分；拿到碼的人不能自己選。
        ⚠️ 資料庫只存雜湊（hash_code），明碼只在這一次回應裡出現。產生用 secrets（family.new_code 已經用了）。
        只能用一次、七天（INVITE_TTL_DAYS）後過期；同一個身分再產生一次，舊的那組作廢。

    【前端怎麼打】
        frontend/js/api.js 的 API.createInviteCode({ role })
        家庭成員頁「邀請家人」→ 產生邀請碼。

    【誰能打】
        登入、沒被停權、而且是家長。上面的 @parent_required 已經擋好了：
            沒登入 → 401；被停權、不是家長（子女、還沒有家庭、平台管理員）→ 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（這裡一定有值）
            me.family_role   一定是 'parent'

    【請求主體】body 是 InviteCodeIn（app/schemas/family.py）
        欄位  型別  必填  說明
        role  字串  是    parent／child，其他值 FastAPI 自動回 422
        範例：{"role": "child"}

    【成功回應】狀態碼 201
        {"code": "K7QM-3XWP", "role": "child", "expiresAt": "2026-09-24T03:00:00+00:00"}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                 detail
        403     不是家長                 只有家長可以做這件事（守衛回）
        422     role 不是 parent／child  （FastAPI 自動回）

    【會用到的資料表】
        表              讀／寫  用來做什麼
        family_invites  寫      同身分的舊碼作廢；新增一列（只有 code_hash，沒有 invitee）

    【每一步用的工具與資料庫方法】
        步驟        呼叫                                              做什麼
        1 舊碼作廢  crud.save(FamilyInvite, {"status": "cancelled", …}, where={…, "code_hash__isnull": False}, db=db)  code_hash 不是 NULL 的才是邀請碼
        2 產生      family.new_code()                                 8 碼、中間一個 -，用 secrets 產生
                    family.hash_code(code)                            雜湊（會先正規化），資料庫只存這個
                    family.expires_at(days=settings.invite_ttl_days)  現在起算 N 天
                    crud.save(FamilyInvite, {…}, db=db)               新增一列
                    db.commit()                                       寫進去

    【寫法步驟】
        1. 我們家同一個身分、還沒用的舊碼 → cancelled
        2. 產生新碼，存雜湊與到期時間
        3. db.commit()，回傳明碼（只有這一次）

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, HTTPException, Query
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import admin_required, block_admin, family_required, parent_required, protect, visible_scope
            from app.models import (
                Allowance, AuditLog, Family, FamilyInvite, FamilyMember, Group, GroupMember, Guardianship, SavingsGoal,
                Transaction, User,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.family import AllowanceIn, FamilyIn, GuardianshipIn, InviteCodeIn, InviteIn, JoinIn, RolePatchIn
            from app.toolkit import crud, errors, family, images, money, password_reset, period
            from app.toolkit.config import settings
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 同一個身分再產生一次，舊的那組作廢
            now = datetime.now(timezone.utc)
            crud.save(FamilyInvite, {"status": "cancelled", "responded_at": now}, where={
                "family_id": me.family_id, "role": body.role, "status": "pending", "code_hash__isnull": False,
            }, db=db)

            # 2. 產生新碼：資料庫只存雜湊
            code = family.new_code()
            expires = family.expires_at(days=settings.invite_ttl_days)
            crud.save(FamilyInvite, {
                "family_id": me.family_id,
                "inviter_id": me.id,
                "code_hash": family.hash_code(code),
                "role": body.role,
                "expires_at": expires,
            }, db=db)
            db.commit()

            # 3. 明碼只在這一次回應裡出現
            return {"code": code, "role": body.role, "expiresAt": expires.isoformat()}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/family/invite
        3. 按右上角 Authorize，貼上家長登入拿到的 accessToken
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               {"role": "child"}  → 201，拿到一組 XXXX-XXXX
               再產生一次 child   → 201，舊的那組拿去 join 會回 400
               子女的 token       → 403
        5. 資料庫 family_invites 的 code_hash 不能是明碼
        6. 前端改成連你的後端（frontend/index.html 的 api-base），家庭成員頁產生邀請碼，畫面顯示碼與到期日
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "create_invite_code and 你的"，要全部通過
    """
    raise not_ready("POST /api/family/invite", OWNER)


@router.post("/family/join", summary="用邀請碼加入")
@protect(family=False, platform_admin=False)
@stub
def join_family(body: JoinIn, me: User, db: Session = Depends(get_db)):
    """用邀請碼加入

    POST /api/family/join

    【這支做什麼】
        還沒有家庭的人輸入邀請碼加入，身分照碼上寫的（家長決定的）。碼只能用一次。

    【前端怎麼打】
        frontend/js/api.js 的 API.joinFamily({ code })
        家庭頁「用邀請碼加入」。成功之後前端重拿成員清單、重畫帳號選單與帳本。

    【誰能打】
        登入、沒被停權、不是平台管理員、而且還沒有家庭。
        上面的 @protect(family=False, platform_admin=False) 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403；已經在一個家庭裡 → 409「你已經在一個家庭裡了」
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件），me.id 是他的 id。

    【請求主體】body 是 JoinIn（app/schemas/family.py）
        欄位  型別  必填  說明
        code  字串  是    使用者打的碼，大小寫、空白、- 都可以（會先整理）
        範例：{"code": "k7qm 3xwp"}

    【成功回應】狀態碼 200
        {"family": {"id": "2", "name": "王家"}, "role": "child"}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候            detail
        400     整理完不是 8 個字   邀請碼是 8 個字，例如 K7QM-3XWP
        400     用過了              這個邀請已經用過了
        400     被作廢了            這個邀請已經取消了
        400     過期了              這個邀請已經過期了，請家人重新邀請一次
        404     找不到這組碼        找不到這組邀請碼，確認一下有沒有打錯
        409     已經在家庭裡        你已經在一個家庭裡了（守衛回）
        409     那一家已經沒有家長  這個家目前沒有家長，暫時不能加入
        · 用過、作廢、過期要講得出是哪一種：使用者才知道要請家人重產。

    【會用到的資料表】
        表              讀／寫  用來做什麼
        family_invites  讀＋寫  用雜湊找碼；用掉之後 status = accepted、invitee_id = 我
        family_members  讀＋寫  那一家有沒有家長；我加入
        families        讀      家庭名字
        audit_logs      寫      join_family

    【每一步用的工具與資料庫方法】
        步驟        呼叫                                             做什麼
        1 找碼      family.normalize_code(body.code)                 去空白與 -、轉大寫："k7qm 3xwp" → "K7QM3XWP"
                    crud.get(FamilyInvite, where={"code_hash": family.hash_code(code)}, db=db)  用雜湊去找
        2 能不能用  family.require_joinable(invite.status, expires)  用過、作廢、過期丟 ValueError（訊息講得出是哪一種）
                    invite.expires_at.replace(tzinfo=timezone.utc)   SQLite 讀回來的時間沒有時區，補上 UTC 才能跟現在比
        3 有家長    crud.count(FamilyMember, {"family_id": …, "role": "parent", "status": "active"}, db=db)  數有幾位家長
                    family.require_has_parent(人數)                  0 位丟 ValueError
        4 加入      crud.remove(FamilyMember, {"user_id": me.id, "status": "removed"}, db=db)  以前離開家庭留下的那一列（user_id 是 UNIQUE）
                    crud.save(FamilyMember, {…}, db=db)／crud.save(FamilyInvite, {"id": …, "status": "accepted"}, db=db)  加入、把碼用掉
                    db.commit()                                      一起寫進去

    【寫法步驟】
        1. 整理碼（不是 8 個字 400），用雜湊找（404）
        2. require_joinable（400）
        3. require_has_parent（409）
        4. 拿掉我以前的 removed 列 → 新增我這一列（身分照碼上的）→ 碼改成 accepted → 寫稽核
        5. db.commit()，回傳 {family, role}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, HTTPException, Query
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import admin_required, block_admin, family_required, parent_required, protect, visible_scope
            from app.models import (
                Allowance, AuditLog, Family, FamilyInvite, FamilyMember, Group, GroupMember, Guardianship, SavingsGoal,
                Transaction, User,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.family import AllowanceIn, FamilyIn, GuardianshipIn, InviteCodeIn, InviteIn, JoinIn, RolePatchIn
            from app.toolkit import crud, errors, family, images, money, password_reset, period
            from app.toolkit.config import settings
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 整理使用者打的碼，用雜湊去找
            code = family.normalize_code(body.code)
            if len(code) != 8:
                raise errors.bad_request("邀請碼是 8 個字，例如 K7QM-3XWP")
            invite = crud.get(FamilyInvite, where={"code_hash": family.hash_code(code)}, db=db)
            if invite is None:
                raise errors.not_found("找不到這組邀請碼，確認一下有沒有打錯")

            # 2. 還能不能用（SQLite 讀回來的時間沒有時區，補上 UTC）
            expires = invite.expires_at if invite.expires_at.tzinfo else invite.expires_at.replace(tzinfo=timezone.utc)
            try:
                family.require_joinable(invite.status, expires)
            except ValueError as exc:
                raise errors.bad_request(str(exc)) from None

            # 3. 家裡至少要有一位家長
            parents = crud.count(FamilyMember, {"family_id": invite.family_id, "role": "parent", "status": "active"}, db=db)
            try:
                family.require_has_parent(parents)
            except ValueError as exc:
                raise errors.conflict(str(exc)) from None

            # 4. 加入（身分照碼上的），把碼用掉，寫稽核
            now = datetime.now(timezone.utc)
            crud.remove(FamilyMember, {"user_id": me.id, "status": "removed"}, db=db)
            crud.save(FamilyMember, {"family_id": invite.family_id, "user_id": me.id, "role": invite.role}, db=db)
            crud.save(FamilyInvite, {"id": invite.id, "status": "accepted", "invitee_id": me.id,
                                     "responded_at": now}, db=db)
            fam = crud.get(Family, invite.family_id, db=db)
            crud.save(AuditLog, {"actor_id": me.id, "action": "join_family", "target_type": "family",
                                 "target_id": fam.id, "meta_json": {"note": "用邀請碼加入「%s」" % fam.name}}, db=db)
            db.commit()
            return {"family": {"id": str(fam.id), "name": fam.name}, "role": invite.role}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/family/join
        3. 按右上角 Authorize，貼上一個「還沒有家庭」的人登入拿到的 accessToken
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               家長剛產生的碼（打小寫、中間加空白）  → 200，role 跟產生時選的一樣
               同一組碼換另一個人再用                → 400「這個邀請已經用過了」
               {"code": "ABCD"}                      → 400
               {"code": "ZZZZ-ZZZZ"}                 → 404
        5. 前端改成連你的後端（frontend/index.html 的 api-base），家庭頁輸入邀請碼，畫面換成成員卡片、帳號選單出現家庭
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "join_family and 你的"，要全部通過
    """
    raise not_ready("POST /api/family/join", OWNER)


@router.get("/family/lookup", summary="用完整 email 找人")
@parent_required
@stub
def lookup_user(me: User, email: str | None = None, db: Session = Depends(get_db)):
    """用完整 email 找人

    GET /api/family/lookup

    【這支做什麼】
        家長用「完整的 email」找人，看他現在能不能被邀請。
        ⚠️ 不做模糊搜尋：模糊搜尋等於送出一份「這個系統裡有哪些人」的名單。
        ⚠️ 只回名字與頭像，不回任何財務資料，連 email 都不回（是家長自己打的）。
        ⚠️ 一定要速率限制，不然它就是一支「帳號存不存在」的查詢器：每查一次在 audit_logs 記一筆，一分鐘超過 10 次回 429。

    【前端怎麼打】
        frontend/js/api.js 的 API.lookupUser(email)
        家庭成員頁「用帳號邀請」的搜尋。前端檢查回應裡一定要有 user 與 status。

    【誰能打】
        登入、沒被停權、而且是家長。上面的 @parent_required 已經擋好了：
            沒登入 → 401；被停權、不是家長（子女、還沒有家庭、平台管理員）→ 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（這裡一定有值）
            me.family_role   一定是 'parent'

    【查詢參數】
        參數   型別  說明
        email  字串  完整的 email（大小寫不拘）
        範例：GET /api/family/lookup?email=yuzhen@wang.tw

    【成功回應】狀態碼 200
        {"user": {"id": "6", "name": "王玉珍", "avatar": "珍", "avatarUrl": null}, "status": "available"}
        status       意思
        available    可以邀請
        member       已經是我們家的人
        invited      已經邀請過，對方還沒回覆
        unavailable  目前不能邀請（在別的家庭、或是平台管理員）——⚠️ 刻意不說原因，不透露他在哪個家庭

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                        detail
        400     沒帶 email、或不是完整的 email  請輸入完整的 email
        403     不是家長                        只有家長可以做這件事（守衛回）
        404     沒有這個帳號                    找不到這個帳號
        429     一分鐘內查超過 10 次            查太多次了，請一分鐘後再試

    【會用到的資料表】
        表              讀／寫  用來做什麼
        audit_logs      讀＋寫  數我這一分鐘查了幾次；每查一次記一筆 lookup_user（不記 email）
        users           讀      用 email 找人
        family_members  讀      他現在在哪個家庭
        family_invites  讀      我們家有沒有邀請過他、還沒回覆

    【每一步用的工具與資料庫方法】
        步驟      呼叫                                          做什麼
        1 限速    crud.count(AuditLog, {"actor_id": me.id, "action": "lookup_user", "created_at__gte": 一分鐘前}, db=db)  數最近一分鐘的次數
                  HTTPException(status_code=429, detail="…")    errors 裡沒有 429，直接用 FastAPI 的（from fastapi import HTTPException）
        2 email   password_reset.normalize_email(email)         去空白、轉小寫、檢查格式；不對丟 ValueError
        3 記一筆  crud.save(AuditLog, {…}, db=db)＋db.commit()  找不到也要記（不然查不存在的帳號不算次數），而且要在丟 404 之前 commit
        4 狀態    family.lookup_status(是不是管理員, 他的家庭, 我的家庭, 有沒有邀請過)  回 available／member／invited／unavailable

    【寫法步驟】
        1. 最近一分鐘查了 10 次以上 → 429
        2. email 不完整 → 400
        3. 找人，記一筆稽核，先 commit；找不到 → 404
        4. 查他的家庭、我們家有沒有邀請過他，交給 lookup_status
        5. 只回 id、名字、頭像與 status

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, HTTPException, Query
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import admin_required, block_admin, family_required, parent_required, protect, visible_scope
            from app.models import (
                Allowance, AuditLog, Family, FamilyInvite, FamilyMember, Group, GroupMember, Guardianship, SavingsGoal,
                Transaction, User,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.family import AllowanceIn, FamilyIn, GuardianshipIn, InviteCodeIn, InviteIn, JoinIn, RolePatchIn
            from app.toolkit import crud, errors, family, images, money, password_reset, period
            from app.toolkit.config import settings
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            now = datetime.now(timezone.utc)

            # 1. 速率限制：一分鐘最多查 10 次
            recent = crud.count(AuditLog, {"actor_id": me.id, "action": "lookup_user",
                                           "created_at__gte": now - timedelta(minutes=1)}, db=db)
            if recent >= 10:
                raise HTTPException(status_code=429, detail="查太多次了，請一分鐘後再試")

            # 2. 只收完整的 email（不做模糊搜尋）
            try:
                mail = password_reset.normalize_email(email)
            except ValueError:
                raise errors.bad_request("請輸入完整的 email") from None

            # 3. 找人；不管找不找得到都記一筆（限速要算），先存起來再丟錯
            target = crud.get(User, where={"email": mail}, db=db)
            crud.save(AuditLog, {"actor_id": me.id, "action": "lookup_user", "target_type": "user",
                                 "target_id": target.id if target else None, "meta_json": {"note": "用帳號找人"}}, db=db)
            db.commit()
            if target is None:
                raise errors.not_found("找不到這個帳號")

            # 4. 他現在能不能被邀請（在別的家庭、平台管理員一律 unavailable，不說原因）
            target_family = crud.get(FamilyMember, where={"user_id": target.id, "status": "active"},
                                     fields="family_id", db=db)
            pending = crud.exists(FamilyInvite, {"family_id": me.family_id, "invitee_id": target.id,
                                                 "status": "pending", "expires_at__gt": now}, db=db)
            status = family.lookup_status(target.is_platform_admin, target_family, me.family_id, pending)

            # 5. 只回名字與頭像，不回任何財務資料
            return {
                "user": {
                    "id": str(target.id),
                    "name": target.display_name,
                    "avatar": target.display_name[-1:],
                    "avatarUrl": images.to_data_uri(target.avatar_bytes, target.avatar_mime) if target.avatar_bytes else None,
                },
                "status": status,
            }

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 GET /api/family/lookup
        3. 按右上角 Authorize，貼上家長登入拿到的 accessToken
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               email 填一個沒有家庭的人  → 200，status 是 available
               email 填別的家庭的人      → 200，status 是 unavailable（不說原因）
               email=abc                 → 400
               連續查 11 次              → 第 11 次 429
        5. 前端改成連你的後端（frontend/index.html 的 api-base），家庭成員頁「用帳號邀請」搜尋，找得到人時顯示名字與頭像
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "lookup_user and 你的"，要全部通過
    """
    raise not_ready("GET /api/family/lookup", OWNER)


@router.get("/family/invites", summary="收到的邀請、送出去的、邀請碼")
@block_admin
@stub
def list_invites(me: User, db: Session = Depends(get_db)):
    """收到的邀請、送出去的、邀請碼

    GET /api/family/invites

    【這支做什麼】
        三份清單：我收到的邀請（任何人）、我們家送出去還沒回覆的（家長）、我們家還有效的邀請碼（家長）。過期的一律不回。
        ⚠️ 邀請碼資料庫只存雜湊，拿不回明碼：codes 只回「有一組有效的碼、什麼身分、幾號到期」，code 是 null。
           明碼只在 POST /api/family/invite 當下出現一次。

    【前端怎麼打】
        frontend/js/api.js 的 API.invites()
        總覽最上面的邀請卡、家庭頁、家庭成員頁「等待回覆」與邀請碼區。前端檢查回應裡一定要有 received、sent、codes。

    【誰能打】
        登入、沒被停權、不是平台管理員。上面的 @block_admin 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【請求參數】沒有

    【成功回應】狀態碼 200
        {"received": [{"id": "9", "familyName": "王家", "inviterName": "王大明", "role": "child",
                       "expiresAt": "2026-09-24T03:00:00+00:00"}],
         "sent": [{"id": "10", "name": "王玉珍", "email": "yuzhen@wang.tw", "avatar": "珍", "role": "child",
                   "expiresAt": "2026-09-24T03:00:00+00:00"}],
         "codes": [{"code": null, "role": "parent", "expiresAt": "2026-09-24T03:00:00+00:00"}]}
        · 不是家長的人，sent、codes 都是空陣列
        · 新的在前

    【錯誤回應】
        只有守衛的 401／403，這支本身不會出錯。

    【會用到的資料表】
        表               讀／寫  用來做什麼
        family_invites   讀      三份清單都從這裡來
        families、users  讀      家庭名字、邀請人與被邀請人的名字

    【每一步用的工具與資料庫方法】
        步驟      呼叫                                                           做什麼
        1 還有效  {"status": "pending", "expires_at__gt": now}                   三份清單共用的條件，用 {**live, …} 合進去
                  crud.find(FamilyInvite, {**live, "invitee_id": me.id}, order_by="-id", db=db)  我收到的
        2 家長    {"code_hash__isnull": True}／{"code_hash__isnull": False}      帳號邀請沒有 code_hash；邀請碼有
        3 名字    crud.find(User, {"id__in": {…}}, db=db)／crud.find(Family, …)  一次查完做成對照表

    【寫法步驟】
        1. 我收到的、還有效的邀請
        2. 我是家長才查：我們家送出去的帳號邀請、我們家的邀請碼
        3. 一次查出需要的家庭名與人名
        4. 組成三份清單回傳（codes 的 code 一律 null）
        ⚠️ 只讀不寫，不用 db.commit()。

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, HTTPException, Query
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import admin_required, block_admin, family_required, parent_required, protect, visible_scope
            from app.models import (
                Allowance, AuditLog, Family, FamilyInvite, FamilyMember, Group, GroupMember, Guardianship, SavingsGoal,
                Transaction, User,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.family import AllowanceIn, FamilyIn, GuardianshipIn, InviteCodeIn, InviteIn, JoinIn, RolePatchIn
            from app.toolkit import crud, errors, family, images, money, password_reset, period
            from app.toolkit.config import settings
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            live = {"status": "pending", "expires_at__gt": datetime.now(timezone.utc)}

            # 1. 我收到的
            received_rows = crud.find(FamilyInvite, {**live, "invitee_id": me.id, "code_hash__isnull": True},
                                      order_by="-id", db=db)

            # 2. 家長才看得到：我們家送出去的帳號邀請、我們家的邀請碼
            sent_rows, code_rows = [], []
            if me.family_role == "parent":
                sent_rows = crud.find(FamilyInvite, {**live, "family_id": me.family_id, "code_hash__isnull": True},
                                      order_by="-id", db=db)
                code_rows = crud.find(FamilyInvite, {**live, "family_id": me.family_id, "code_hash__isnull": False},
                                      order_by="-id", db=db)

            # 3. 一次查出家庭名與人名
            ids = {r.inviter_id for r in received_rows} | {r.invitee_id for r in sent_rows}
            people = {u.id: u for u in crud.find(User, {"id__in": ids}, db=db)}
            families = {f.id: f.name for f in crud.find(Family, {"id__in": {r.family_id for r in received_rows}}, db=db)}

            # 4. 組成三份清單
            received = []
            for r in received_rows:
                received.append({"id": str(r.id), "familyName": families.get(r.family_id, ""),
                                 "inviterName": people[r.inviter_id].display_name, "role": r.role,
                                 "expiresAt": r.expires_at.isoformat()})
            sent = []
            for r in sent_rows:
                who = people[r.invitee_id]
                sent.append({"id": str(r.id), "name": who.display_name, "email": who.email,
                             "avatar": who.display_name[-1:], "role": r.role, "expiresAt": r.expires_at.isoformat()})
            codes = [{"code": None, "role": r.role, "expiresAt": r.expires_at.isoformat()} for r in code_rows]
            return {"received": received, "sent": sent, "codes": codes}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 GET /api/family/invites
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               被邀請的人打                      → received 有那一筆，sent、codes 是空的
               發邀請的家長打                    → sent 有那一筆；產生過邀請碼的話 codes 有一筆、code 是 null
               把邀請的 expires_at 改成昨天再打  → 那一筆不見
        5. 前端改成連你的後端（frontend/index.html 的 api-base），被邀請的人登入，總覽最上面出現邀請卡
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "list_invites and 你的"，要全部通過
    """
    raise not_ready("GET /api/family/invites", OWNER)


@router.post("/family/invites", status_code=201, summary="用帳號邀請")
@parent_required
@stub
def send_invite(body: InviteIn, me: User, db: Session = Depends(get_db)):
    """用帳號邀請

    POST /api/family/invites

    【這支做什麼】
        家長用帳號（先用 lookup 找到的 userId）邀請一個人加入，身分由家長決定。
        對方會在自己的畫面上看到邀請，按「加入」才算數（POST /api/family/invites/{id}/accept）。

    【前端怎麼打】
        frontend/js/api.js 的 API.sendInvite({ userId, role })
        家庭成員頁找到人之後的「送出邀請」。

    【誰能打】
        登入、沒被停權、而且是家長。上面的 @parent_required 已經擋好了：
            沒登入 → 401；被停權、不是家長（子女、還沒有家庭、平台管理員）→ 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（這裡一定有值）
            me.family_role   一定是 'parent'

    【請求主體】body 是 InviteIn（app/schemas/family.py）
        欄位    型別  必填  說明
        userId  字串  是    要邀請的人
        role    字串  是    parent／child，其他值 FastAPI 自動回 422
        範例：{"userId": "6", "role": "child"}

    【成功回應】狀態碼 201
        {"id": "10", "status": "pending"}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                              detail
        400     對方已經在某個家庭裡、或是平台管理員  這個帳號目前不能邀請
        403     不是家長                              只有家長可以做這件事（守衛回）
        404     沒有這個人                            找不到這個帳號
        409     我們家已經邀請過他、還沒回覆          已經邀請過了，等對方回覆就好

    【會用到的資料表】
        表              讀／寫  用來做什麼
        users           讀      對方存不存在、是不是平台管理員
        family_members  讀      對方是不是已經有家庭
        family_invites  讀＋寫  有沒有重複；新增一列（有 invitee、沒有 code_hash）
        audit_logs      寫      invite_member

    【每一步用的工具與資料庫方法】
        步驟    呼叫                                              做什麼
        1 對方  crud.get(User, user_id, db=db)                    用主鍵拿
                crud.exists(FamilyMember, {"user_id": …, "status": "active"}, db=db)  他有沒有家庭
        2 重複  crud.exists(FamilyInvite, {…, "status": "pending", "expires_at__gt": now}, db=db)  過期的不算
        3 新增  family.expires_at(days=settings.invite_ttl_days)  七天後
                crud.save(FamilyInvite, {…}, db=db)＋crud.save(AuditLog, {…}, db=db)  邀請與稽核
                db.commit()                                       一起寫進去

    【寫法步驟】
        1. 對方要存在（404）、不是平台管理員、沒有家庭（400）
        2. 我們家已經有一筆還有效的邀請給他 → 409
        3. 新增邀請、寫稽核，db.commit()
        4. 回 {"id", "status": "pending"}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, HTTPException, Query
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import admin_required, block_admin, family_required, parent_required, protect, visible_scope
            from app.models import (
                Allowance, AuditLog, Family, FamilyInvite, FamilyMember, Group, GroupMember, Guardianship, SavingsGoal,
                Transaction, User,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.family import AllowanceIn, FamilyIn, GuardianshipIn, InviteCodeIn, InviteIn, JoinIn, RolePatchIn
            from app.toolkit import crud, errors, family, images, money, password_reset, period
            from app.toolkit.config import settings
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            now = datetime.now(timezone.utc)

            # 1. 對方要存在、不是平台管理員、還沒有家庭
            user_id = int(body.userId) if body.userId.isdigit() else 0
            target = crud.get(User, user_id, db=db)
            if target is None:
                raise errors.not_found("找不到這個帳號")
            if target.is_platform_admin or crud.exists(FamilyMember, {"user_id": user_id, "status": "active"}, db=db):
                raise errors.bad_request("這個帳號目前不能邀請")

            # 2. 我們家還有一筆沒回覆的，就不再寄
            if crud.exists(FamilyInvite, {"family_id": me.family_id, "invitee_id": user_id,
                                          "status": "pending", "expires_at__gt": now}, db=db):
                raise errors.conflict("已經邀請過了，等對方回覆就好")

            # 3. 新增邀請（身分由家長決定），寫稽核
            invite = crud.save(FamilyInvite, {
                "family_id": me.family_id,
                "inviter_id": me.id,
                "invitee_id": user_id,
                "role": body.role,
                "expires_at": family.expires_at(days=settings.invite_ttl_days),
            }, db=db)
            crud.save(AuditLog, {"actor_id": me.id, "action": "invite_member", "target_type": "user",
                                 "target_id": user_id, "meta_json": {"note": "邀請%s成為%s" % (
                                     target.display_name, "家長" if body.role == "parent" else "子女")}}, db=db)
            db.commit()
            return {"id": str(invite.id), "status": "pending"}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/family/invites
        3. 按右上角 Authorize，貼上家長登入拿到的 accessToken
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               邀請一個沒有家庭的人  → 201
               再邀請一次            → 409
               邀請別的家庭的人      → 400
        5. 被邀請的人打 GET /api/family/invites → received 有這一筆
        6. 前端改成連你的後端（frontend/index.html 的 api-base），家庭成員頁送出邀請，「等待回覆」多一個人
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "send_invite and 你的"，要全部通過
    """
    raise not_ready("POST /api/family/invites", OWNER)


@router.post("/family/invites/{invite_id}/accept", summary="接受邀請")
@protect(family=False, platform_admin=False)
@stub
def accept_invite(invite_id: str, me: User, db: Session = Depends(get_db)):
    """接受邀請

    POST /api/family/invites/{invite_id}/accept

    【這支做什麼】
        被邀請的人按「加入」：邀請要是給他的、還沒回覆、沒過期，而且那一家還有家長。
        身分照邀請上寫的（家長決定的）。

    【前端怎麼打】
        frontend/js/api.js 的 API.acceptInvite(id)
        邀請卡的「加入」。成功之後前端重畫帳號選單（身分變了）、帳本清單和目前這一頁。

    【誰能打】
        登入、沒被停權、不是平台管理員、而且還沒有家庭。
        上面的 @protect(family=False, platform_admin=False) 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403；已經在一個家庭裡 → 409「你已經在一個家庭裡了」
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件），me.id 是他的 id。

    【路徑參數】{invite_id} 是邀請的 id（字串）
        範例：POST /api/family/invites/10/accept

    【成功回應】狀態碼 200
        {"family": {"id": "2", "name": "王家"}, "role": "child"}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                          detail
        400     已經回覆過（接受、婉拒、被取消）  這個邀請已經用過了／這個邀請已經取消了
        400     過期了                            這個邀請已經過期了，請家人重新邀請一次
        404     找不到、或不是給我的              找不到這個邀請
        409     我已經在家庭裡                    你已經在一個家庭裡了（守衛回）
        409     那一家已經沒有家長                這個家目前沒有家長，暫時不能加入
        · 別人的邀請回 404，不要回 403：不透露那個 id 存在。

    【會用到的資料表】
        表              讀／寫  用來做什麼
        family_invites  讀＋寫  找邀請；接受後 status = accepted
        family_members  讀＋寫  那一家有沒有家長；我加入
        families        讀      家庭名字
        audit_logs      寫      join_family

    【每一步用的工具與資料庫方法】（跟 POST /api/family/join 幾乎一樣）
        步驟        呼叫                                             做什麼
        1 找邀請    crud.get(FamilyInvite, where={"id": …, "invitee_id": me.id}, db=db)  條件帶上 invitee_id，別人的自然找不到
        2 能不能用  family.require_joinable(invite.status, expires)  400
        3 有家長    family.require_has_parent(人數)                  409
        4 加入      crud.remove(…removed 那一列…)／crud.save(FamilyMember, …)／crud.save(FamilyInvite, …)  同 join
                    db.commit()                                      一起寫進去

    【寫法步驟】
        1. 找「給我的」這個邀請（404）
        2. require_joinable（400）→ require_has_parent（409）
        3. 拿掉我以前的 removed 列 → 加入 → 邀請改成 accepted → 寫稽核
        4. db.commit()，回傳 {family, role}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, HTTPException, Query
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import admin_required, block_admin, family_required, parent_required, protect, visible_scope
            from app.models import (
                Allowance, AuditLog, Family, FamilyInvite, FamilyMember, Group, GroupMember, Guardianship, SavingsGoal,
                Transaction, User,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.family import AllowanceIn, FamilyIn, GuardianshipIn, InviteCodeIn, InviteIn, JoinIn, RolePatchIn
            from app.toolkit import crud, errors, family, images, money, password_reset, period
            from app.toolkit.config import settings
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 只有被邀請的本人找得到這個邀請
            number = int(invite_id) if invite_id.isdigit() else 0
            invite = crud.get(FamilyInvite, where={"id": number, "invitee_id": me.id}, db=db)
            if invite is None:
                raise errors.not_found("找不到這個邀請")

            # 2. 還沒回覆、沒過期（SQLite 讀回來的時間沒有時區，補上 UTC）
            expires = invite.expires_at if invite.expires_at.tzinfo else invite.expires_at.replace(tzinfo=timezone.utc)
            try:
                family.require_joinable(invite.status, expires)
            except ValueError as exc:
                raise errors.bad_request(str(exc)) from None

            # 3. 家裡至少要有一位家長
            parents = crud.count(FamilyMember, {"family_id": invite.family_id, "role": "parent", "status": "active"}, db=db)
            try:
                family.require_has_parent(parents)
            except ValueError as exc:
                raise errors.conflict(str(exc)) from None

            # 4. 加入（身分照邀請上的），邀請改成已接受，寫稽核
            now = datetime.now(timezone.utc)
            crud.remove(FamilyMember, {"user_id": me.id, "status": "removed"}, db=db)
            crud.save(FamilyMember, {"family_id": invite.family_id, "user_id": me.id, "role": invite.role}, db=db)
            crud.save(FamilyInvite, {"id": invite.id, "status": "accepted", "responded_at": now}, db=db)
            fam = crud.get(Family, invite.family_id, db=db)
            crud.save(AuditLog, {"actor_id": me.id, "action": "join_family", "target_type": "family",
                                 "target_id": fam.id, "meta_json": {"note": "接受邀請加入「%s」" % fam.name}}, db=db)
            db.commit()
            return {"family": {"id": str(fam.id), "name": fam.name}, "role": invite.role}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/family/invites/{invite_id}/accept
        3. 按右上角 Authorize，貼上「被邀請的人」登入拿到的 accessToken
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               接受給自己的邀請                  → 200，role 是邀請上的
               再接受一次                        → 409（已經在家庭裡了）
               用另一個人的 token 接受同一個 id  → 404
        5. 前端改成連你的後端（frontend/index.html 的 api-base），邀請卡按「加入」，帳號選單出現家庭
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "accept_invite and 你的"，要全部通過
    """
    raise not_ready("POST /api/family/invites/{invite_id}/accept", OWNER)


@router.delete("/family/invites/{invite_id}", summary="婉拒或取消邀請")
@block_admin
@stub
def decline_invite(invite_id: str, me: User, db: Session = Depends(get_db)):
    """婉拒或取消邀請

    DELETE /api/family/invites/{invite_id}

    【這支做什麼】
        婉拒或取消一個帳號邀請，不刪資料列：
            被邀請的人 → status = declined（婉拒）
            發邀請那一家的家長 → status = cancelled（取消）
            其他人 → 403

    【前端怎麼打】
        frontend/js/api.js 的 API.declineInvite(id)
        邀請卡的「婉拒」、家庭成員頁「等待回覆」的「取消」。

    【誰能打】
        登入、沒被停權、不是平台管理員。上面的 @block_admin 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【路徑參數】{invite_id} 是邀請的 id（字串）
        範例：DELETE /api/family/invites/10

    【成功回應】狀態碼 200
        {"id": "10", "status": "declined"}　或　{"id": "10", "status": "cancelled"}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                            detail
        403     不是被邀請的人，也不是那一家的家長  這個邀請不是給你的
        404     找不到、已經回覆過、或是邀請碼      找不到這個邀請

    【會用到的資料表】
        表              讀／寫  用來做什麼
        family_invites  讀＋寫  改 status 與 responded_at

    【每一步用的工具與資料庫方法】
        步驟      呼叫                        做什麼
        1 找      crud.get(FamilyInvite, where={"id": …, "status": "pending", "code_hash__isnull": True}, db=db)  還沒回覆的帳號邀請
        2 誰在按  invite.invitee_id == me.id  被邀請的人
                  me.family_role == "parent" and me.family_id == invite.family_id  那一家的家長
        3 改      crud.save(FamilyInvite, {"id": …, "status": …, "responded_at": now}, db=db)  不刪列
                  db.commit()                 寫進去

    【寫法步驟】
        1. 找還沒回覆的帳號邀請（404）
        2. 被邀請的人 → declined；那一家的家長 → cancelled；其他人 → 403
        3. 寫回去，db.commit()，回 {"id", "status"}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, HTTPException, Query
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import admin_required, block_admin, family_required, parent_required, protect, visible_scope
            from app.models import (
                Allowance, AuditLog, Family, FamilyInvite, FamilyMember, Group, GroupMember, Guardianship, SavingsGoal,
                Transaction, User,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.family import AllowanceIn, FamilyIn, GuardianshipIn, InviteCodeIn, InviteIn, JoinIn, RolePatchIn
            from app.toolkit import crud, errors, family, images, money, password_reset, period
            from app.toolkit.config import settings
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 還沒回覆的帳號邀請
            number = int(invite_id) if invite_id.isdigit() else 0
            invite = crud.get(FamilyInvite, where={"id": number, "status": "pending", "code_hash__isnull": True}, db=db)
            if invite is None:
                raise errors.not_found("找不到這個邀請")

            # 2. 被邀請的人是婉拒；那一家的家長是取消
            if invite.invitee_id == me.id:
                status = "declined"
            elif me.family_role == "parent" and me.family_id == invite.family_id:
                status = "cancelled"
            else:
                raise errors.forbidden("這個邀請不是給你的")

            # 3. 不刪列，只改狀態
            crud.save(FamilyInvite, {"id": invite.id, "status": status,
                                     "responded_at": datetime.now(timezone.utc)}, db=db)
            db.commit()
            return {"id": str(invite.id), "status": status}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 DELETE /api/family/invites/{invite_id}
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               被邀請的人刪                → 200，status 是 declined
               發邀請那一家的家長刪另一筆  → 200，status 是 cancelled
               不相干的人刪                → 403
               同一筆再刪一次              → 404
        5. 前端改成連你的後端（frontend/index.html 的 api-base），邀請卡按「婉拒」，卡片不見
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "decline_invite and 你的"，要全部通過
    """
    raise not_ready("DELETE /api/family/invites/{invite_id}", OWNER)


@router.patch("/family/members/{user_id}", summary="改角色")
@parent_required
@stub
def change_member_role(user_id: str, body: RolePatchIn, me: User, db: Session = Depends(get_db)):
    """改角色

    PATCH /api/family/members/{user_id}

    【這支做什麼】
        家長改家庭角色：
            · 把子女設為家長 → 他被照看的關係一起結束（家長之間本來就看得到彼此）
            · 把自己改成子女（家裡要還有別的家長）→ 自己照看別人的關係一起結束
            · ⚠️ 不能把另一位家長改成子女：那跟「移除另一位家長」是同一件事，他只能自己調整
        本來就是那個角色：回 changed: false，不是錯誤。

    【前端怎麼打】
        frontend/js/api.js 的 API.changeMemberRole(userId, role)
        家庭成員頁子女卡片上的「設為家長」、家長自己的「改成子女」，先用密碼確認。

    【誰能打】
        登入、沒被停權、而且是家長。上面的 @parent_required 已經擋好了：
            沒登入 → 401；被停權、不是家長（子女、還沒有家庭、平台管理員）→ 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（這裡一定有值）
            me.family_role   一定是 'parent'

    【請求主體】body 是 RolePatchIn（app/schemas/family.py）
        欄位  型別  必填  說明
        role  字串  是    parent／child，其他值 FastAPI 自動回 422
        範例：{"role": "parent"}

    【成功回應】狀態碼 200
        {"id": "5", "role": "parent", "changed": true}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                            detail
        403     要把另一位家長改成子女              不能把另一位家長改成子女，他只能自己調整
        404     對方不在我們家                      這個家庭裡沒有這個人
        409     我是唯一的家長，卻要把自己改成子女  你是唯一的家長，先把另一位家人設為家長
        422     role 不是 parent／child             （FastAPI 自動回）

    【會用到的資料表】
        表              讀／寫  用來做什麼
        family_members  讀＋寫  對方的角色、家長人數；改角色
        guardianships   寫      連帶結束的監管關係（ended_at）
        allowances      寫      跟著監管關係歸零
        users           讀      稽核裡的名字
        audit_logs      寫      change_role

    【每一步用的工具與資料庫方法】
        步驟    呼叫                                                    做什麼
        1 對象  crud.get(FamilyMember, where={"family_id": me.family_id, "user_id": …, "status": "active"}, db=db)  我們家的這個人
        2 規則  family.require_can_change_role(me.id, me.family_role, uid, 他現在的角色, 新角色, 家長人數)  不行丟 PermissionError（403）或 ValueError（409）
        3 連帶  crud.save(Guardianship, {"ended_at": now}, where={"ward_id": uid, "ended_at__isnull": True}, db=db)  設為家長：他被照看的結束
                crud.save(Guardianship, {"ended_at": now}, where={"guardian_id": uid, …}, db=db)  改成子女：他照看別人的結束
        4 改    crud.save(FamilyMember, {"role": …}, where={…}, db=db)  複合主鍵的表，用 where 改最直接
                crud.get(User, uid, fields="display_name", db=db)       只拿名字一個欄位
                db.commit()                                             一起寫進去

    【寫法步驟】
        1. 對象要在我們家（404）
        2. require_can_change_role（403／409）；角色沒變就回 changed: false
        3. 設為家長：結束他被照看的關係、零用金歸零；改成子女：結束他照看別人的關係、零用金歸零
        4. 改角色、寫稽核，db.commit()，回 changed: true

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, HTTPException, Query
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import admin_required, block_admin, family_required, parent_required, protect, visible_scope
            from app.models import (
                Allowance, AuditLog, Family, FamilyInvite, FamilyMember, Group, GroupMember, Guardianship, SavingsGoal,
                Transaction, User,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.family import AllowanceIn, FamilyIn, GuardianshipIn, InviteCodeIn, InviteIn, JoinIn, RolePatchIn
            from app.toolkit import crud, errors, family, images, money, password_reset, period
            from app.toolkit.config import settings
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 對象要在同一個家庭
            uid = int(user_id) if user_id.isdigit() else 0
            target = crud.get(FamilyMember, where={"family_id": me.family_id, "user_id": uid, "status": "active"}, db=db)
            if target is None:
                raise errors.not_found("這個家庭裡沒有這個人")

            # 2. 規則：不能把另一位家長改成子女；自己改成子女要還有別的家長
            parents = crud.count(FamilyMember, {"family_id": me.family_id, "role": "parent", "status": "active"}, db=db)
            try:
                family.require_can_change_role(me.id, me.family_role, uid, target.role, body.role, parents)
            except PermissionError as exc:
                raise errors.forbidden(str(exc)) from None
            except ValueError as exc:
                raise errors.conflict(str(exc)) from None
            if target.role == body.role:
                return {"id": str(uid), "role": body.role, "changed": False}

            # 3. 連帶結束的監管關係（零用金跟著歸零）
            now = datetime.now(timezone.utc)
            if body.role == "parent":
                # 設為家長：他被照看的關係結束（家長之間本來就看得到）
                crud.save(Guardianship, {"ended_at": now}, where={"ward_id": uid, "ended_at__isnull": True}, db=db)
                crud.save(Allowance, {"amount": 0}, where={"ward_id": uid}, db=db)
            else:
                # 自己改成子女：他照看別人的關係結束
                crud.save(Guardianship, {"ended_at": now}, where={"guardian_id": uid, "ended_at__isnull": True}, db=db)
                crud.save(Allowance, {"amount": 0}, where={"payer_id": uid}, db=db)

            # 4. 改角色、寫稽核
            crud.save(FamilyMember, {"role": body.role}, where={"family_id": me.family_id, "user_id": uid}, db=db)
            name = crud.get(User, uid, fields="display_name", db=db)
            crud.save(AuditLog, {"actor_id": me.id, "action": "change_role", "target_type": "user", "target_id": uid,
                                 "meta_json": {"note": "把%s設為%s" % (name, "家長" if body.role == "parent" else "子女")}},
                      db=db)
            db.commit()
            return {"id": str(uid), "role": body.role, "changed": True}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 PATCH /api/family/members/{user_id}
        3. 按右上角 Authorize，貼上家長登入拿到的 accessToken
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               把子女設為家長            → 200，changed 是 true；原本照看他的關係結束了
               再送一次一樣的            → 200，changed 是 false
               把另一位家長改成子女      → 403
               唯一的家長把自己改成子女  → 409
        5. 前端改成連你的後端（frontend/index.html 的 api-base），家庭成員頁「設為家長」，卡片上的角色改變、「照看中」的標記消失
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "change_member_role and 你的"，要全部通過
    """
    raise not_ready("PATCH /api/family/members/{user_id}", OWNER)


@router.delete("/family/members/{user_id}", summary="家長移出子女；{user_id} 寫 me 是自己退出")
@family_required
@stub
def remove_member(user_id: str, me: User, db: Session = Depends(get_db)):
    """家長移出子女；{user_id} 寫 me 是自己退出

    DELETE /api/family/members/{user_id}

    【這支做什麼】
        兩件事，看路徑：
            /api/family/members/me   → 自己退出家庭（任何人都可以；但唯一的家長在家裡還有別人時不行）
            /api/family/members/5    → 家長把子女移出家庭（⚠️ 不能移除另一位家長，他只能自己退出）
        ⚠️ 紀錄一筆都不刪（family_members.status 改成 removed），同一個交易裡一起收掉：
            · 跟他有關的監管關係結束（ended_at），零用金歸零
            · 他開的帳本把家人移出；家人開的帳本把他移出——不收的話，人離開了家人還看得到他後來記的每一筆
            · 他送出去還沒回覆的邀請、他產生還沒用的邀請碼 → cancelled
              （不作廢的話，家長離開後有人拿舊碼加入，會出現一個只有子女、沒有家長的家）

    【前端怎麼打】
        frontend/js/api.js 的 API.removeMember(userId)　→ DELETE /api/family/members/5
        frontend/js/api.js 的 API.leaveFamily()　　　　→ DELETE /api/family/members/me
        家庭成員頁的「移出家庭」「退出家庭」，兩個都先用密碼確認。

    【誰能打】
        登入、沒被停權、已經加入家庭（家長、子女都可以）。上面的 @family_required 已經擋好了：
            沒登入 → 401；被停權、還沒有家庭（平台管理員也沒有家庭）→ 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（這裡一定有值）
            me.family_role   'parent' 或 'child'
        移出別人另外要是家長（在函式裡用 family.require_can_remove 檢查）。

    【路徑參數】{user_id} 是要移出的人的 id（字串），寫 me 是自己退出
        範例：DELETE /api/family/members/me

    【成功回應】狀態碼 200
        移出：{"id": "5", "removed": true, "endedGuardianships": 1}
        退出：{"left": true, "family": {"id": "2", "name": "王家"}}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                          detail
        400     家長用 id 移出自己                要離開請用「退出家庭」
        403     子女要移出別人                    只有家長可以移除成員
        403     要移出另一位家長                  另一位家長只能自己退出，不能被移除
        404     對方不在我們家                    這個家庭裡沒有這個人
        409     唯一的家長要退出，但家裡還有別人  你是這個家唯一的家長。先邀請另一位家長，或把其他成員移出，才能退出

    【會用到的資料表】
        表               讀／寫    用來做什麼
        family_members   讀＋寫    這一家有誰、誰是家長；他的 status 改成 removed
        guardianships    寫        跟他有關的結束
        allowances       寫        跟他有關的歸零
        groups           讀        他開的帳本、家人開的帳本
        group_members    寫（刪）  互相移出
        family_invites   寫        他送出去的邀請、邀請碼 → cancelled
        users、families  讀        稽核裡的名字
        audit_logs       寫        leave_family／remove_member

    【每一步用的工具與資料庫方法】
        步驟    呼叫                                                       做什麼
        1 退出  family.require_can_leave(me.family_role, 其他家長人數, 其他人數)  唯一的家長而且還有別人 → ValueError
        2 移出  family.require_can_remove(me.id, me.family_role, uid, 他的角色)  不是家長、對方是家長 → PermissionError；移出自己 → ValueError
        3 監管  crud.save(Guardianship, {"ended_at": now}, where={"ended_at__isnull": True, "or": [{"guardian_id": uid}, {"ward_id": uid}]}, db=db)  回傳改了幾列＝結束了幾個監管關係
                crud.find(Group, {"created_by": uid}, fields="id", db=db)  他開的帳本 id
                crud.remove(GroupMember, {"group_id__in": …, "user_id__in": people, "user_id__ne": uid}, db=db)  家人從他的帳本移出
                crud.remove(GroupMember, {"group_id__in": …, "user_id": uid}, db=db)  他從家人的帳本移出
                crud.save(FamilyInvite, {"status": "cancelled", …}, where={"inviter_id": uid, "status": "pending"}, db=db)  邀請與邀請碼一起作廢
        4 存檔  db.commit()                                                全部一起寫進去

    【寫法步驟】
        1. 查這一家的成員與角色
        2. 路徑是 me：require_can_leave（409），要處理的人是自己
           不是 me：對方要在我們家（404），require_can_remove（403／400）
        3. 收掉關係：監管、零用金、帳本互相移出、邀請作廢；他的 status 改成 removed
        4. 寫稽核（退出記 leave_family、移出記 remove_member），db.commit()
        5. 退出回 {left, family}；移出回 {id, removed, endedGuardianships}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, HTTPException, Query
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import admin_required, block_admin, family_required, parent_required, protect, visible_scope
            from app.models import (
                Allowance, AuditLog, Family, FamilyInvite, FamilyMember, Group, GroupMember, Guardianship, SavingsGoal,
                Transaction, User,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.family import AllowanceIn, FamilyIn, GuardianshipIn, InviteCodeIn, InviteIn, JoinIn, RolePatchIn
            from app.toolkit import crud, errors, family, images, money, password_reset, period
            from app.toolkit.config import settings
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 這一家有誰、誰是家長
            rows = crud.find(FamilyMember, {"family_id": me.family_id, "status": "active"}, db=db)
            role_of = {r.user_id: r.role for r in rows}
            fam = crud.get(Family, me.family_id, db=db)
            leaving = user_id == "me"

            # 2. 自己退出：唯一的家長在家裡還有別人時不行；移出別人：只有家長、只能移子女
            if leaving:
                others = [u for u in role_of if u != me.id]
                other_parents = [u for u in others if role_of[u] == "parent"]
                try:
                    family.require_can_leave(me.family_role, len(other_parents), len(others))
                except ValueError as exc:
                    raise errors.conflict(str(exc)) from None
                uid = me.id
            else:
                uid = int(user_id) if user_id.isdigit() else 0
                if uid not in role_of:
                    raise errors.not_found("這個家庭裡沒有這個人")
                try:
                    family.require_can_remove(me.id, me.family_role, uid, role_of[uid])
                except PermissionError as exc:
                    raise errors.forbidden(str(exc)) from None
                except ValueError as exc:
                    raise errors.bad_request(str(exc)) from None

            # 3. 收掉跟他有關的關係（紀錄一筆都不刪）
            now = datetime.now(timezone.utc)
            people = list(role_of)
            ended = crud.save(Guardianship, {"ended_at": now}, where={
                "ended_at__isnull": True, "or": [{"guardian_id": uid}, {"ward_id": uid}]}, db=db)
            crud.save(Allowance, {"amount": 0}, where={"or": [{"payer_id": uid}, {"ward_id": uid}]}, db=db)
            his = crud.find(Group, {"created_by": uid}, fields="id", db=db)
            if his:
                crud.remove(GroupMember, {"group_id__in": his, "user_id__in": people, "user_id__ne": uid}, db=db)
            theirs = crud.find(Group, {"created_by__in": people, "created_by__ne": uid}, fields="id", db=db)
            if theirs:
                crud.remove(GroupMember, {"group_id__in": theirs, "user_id": uid}, db=db)
            crud.save(FamilyInvite, {"status": "cancelled", "responded_at": now},
                      where={"inviter_id": uid, "status": "pending"}, db=db)
            crud.save(FamilyMember, {"status": "removed"}, where={"family_id": fam.id, "user_id": uid}, db=db)

            # 4. 寫稽核
            name = crud.get(User, uid, fields="display_name", db=db)
            note = ("退出「%s」" % fam.name) if leaving else ("把%s移出「%s」" % (name, fam.name))
            crud.save(AuditLog, {"actor_id": me.id, "action": "leave_family" if leaving else "remove_member",
                                 "target_type": "user", "target_id": uid, "meta_json": {"note": note}}, db=db)
            db.commit()

            # 5. 回傳
            if leaving:
                return {"left": True, "family": {"id": str(fam.id), "name": fam.name}}
            return {"id": str(uid), "removed": True, "endedGuardianships": ended}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 DELETE /api/family/members/{user_id}
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               家長移出子女                              → 200；子女的 GET /api/family 變成沒有家庭，他的紀錄都還在
               家長移出另一位家長                        → 403
               子女打 /members/me                        → 200，left 是 true
               唯一的家長（家裡還有孩子）打 /members/me  → 409
        5. 被移出的子女原本開的帳本 → 家人打 GET /api/groups 看不到了
        6. 前端改成連你的後端（frontend/index.html 的 api-base），家庭成員頁「移出家庭」「退出家庭」各走一次確認流程
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "remove_member and 你的"，要全部通過
    """
    raise not_ready("DELETE /api/family/members/{user_id}", OWNER)


@router.get("/guardianships", summary="監管關係（雙向可見）")
@family_required
@stub
def list_guardianships(me: User, db: Session = Depends(get_db)):
    """監管關係（雙向可見）

    GET /api/guardianships

    【這支做什麼】
        列出同一個家庭裡還有效的監管關係（誰在照看誰）。
        ⚠️ 監管必須雙向可見：被照看的人一定看得到是誰在看，所以子女也拿得到這份清單。

    【前端怎麼打】
        frontend/js/api.js 的 API.guardianships()
        家庭成員頁每張卡片上的「照看中」與「停止照看」。前端檢查回應裡一定要有 guardianships；名字前端會自己補。

    【誰能打】
        登入、沒被停權、已經加入家庭（家長、子女都可以）。上面的 @family_required 已經擋好了：
            沒登入 → 401；被停權、還沒有家庭（平台管理員也沒有家庭）→ 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（這裡一定有值）
            me.family_role   'parent' 或 'child'

    【請求參數】沒有

    【成功回應】狀態碼 200
        {"guardianships": [{"id": "7", "guardian": "3", "ward": "5", "since": "2026-02-11",
                            "scope": "全部明細", "mine": true}]}
        · mine = 監管人是不是我
        · guardianName、wardName 可以不帶，前端用成員清單補

    【錯誤回應】
        只有守衛的 401／403，這支本身不會出錯。

    【會用到的資料表】
        表              讀／寫  用來做什麼
        family_members  讀      這一家有誰
        guardianships   讀      兩邊都是這一家的人、還沒結束的

    【每一步用的工具與資料庫方法】
        步驟    呼叫                        做什麼
        1 家人  crud.find(FamilyMember, {"family_id": me.family_id, "status": "active"}, fields="user_id", db=db)  這一家的人的 id
        2 監管  crud.find(Guardianship, {"guardian_id__in": ids, "ward_id__in": ids, "ended_at__isnull": True}, order_by="id", db=db)  兩個條件都要成立（同一個 dict 裡就是「且」）
                g.since.date().isoformat()  時間只留日期

    【寫法步驟】
        1. 查這一家的人
        2. 查兩邊都是這一家的人、還沒結束的監管關係
        3. 一筆一筆轉成前端要的樣子（mine = 監管人是我），回傳
        ⚠️ 只讀不寫，不用 db.commit()。

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, HTTPException, Query
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import admin_required, block_admin, family_required, parent_required, protect, visible_scope
            from app.models import (
                Allowance, AuditLog, Family, FamilyInvite, FamilyMember, Group, GroupMember, Guardianship, SavingsGoal,
                Transaction, User,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.family import AllowanceIn, FamilyIn, GuardianshipIn, InviteCodeIn, InviteIn, JoinIn, RolePatchIn
            from app.toolkit import crud, errors, family, images, money, password_reset, period
            from app.toolkit.config import settings
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 這一家的人
            ids = crud.find(FamilyMember, {"family_id": me.family_id, "status": "active"}, fields="user_id", db=db)

            # 2. 兩邊都是這一家的人、還沒結束的監管關係
            rows = crud.find(Guardianship, {"guardian_id__in": ids, "ward_id__in": ids, "ended_at__isnull": True},
                             order_by="id", db=db)

            # 3. 轉成前端要的樣子
            out = []
            for g in rows:
                out.append({
                    "id": str(g.id),
                    "guardian": str(g.guardian_id),
                    "ward": str(g.ward_id),
                    "since": g.since.date().isoformat(),
                    "scope": g.scope,
                    "mine": g.guardian_id == me.id,
                })
            return {"guardianships": out}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 GET /api/guardianships
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               家長打          → 看得到自己與另一位家長的監管關係，自己的 mine 是 true
               被照看的子女打  → 看得到誰在照看他
               沒有家庭的人打  → 403
        5. 前端改成連你的後端（frontend/index.html 的 api-base），家庭成員頁卡片上的「照看中」標記要對
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "list_guardianships and 你的"，要全部通過
    """
    raise not_ready("GET /api/guardianships", OWNER)


@router.post("/guardianships", status_code=201, summary="開始照看（監管人一定是自己）")
@parent_required
@stub
def create_guardianship(body: GuardianshipIn, me: User, db: Session = Depends(get_db)):
    """開始照看（監管人一定是自己）

    POST /api/guardianships

    【這支做什麼】
        家長開始照看同一個家庭的一個子女：之後看得到他所有帳本的紀錄、他記帳會收到通知。
        ⚠️ 監管人一定是自己：主體帶了別人的 guardianId 回 403——不能替別的家長決定他要看誰。
        ⚠️ 只能照看子女：家長之間本來就看得到彼此。

    【前端怎麼打】
        frontend/js/api.js 的 API.createGuardianship({ wardId })
        家庭成員頁子女卡片上的「開始照看」。前端檢查回應裡一定要有 id。

    【誰能打】
        登入、沒被停權、而且是家長。上面的 @parent_required 已經擋好了：
            沒登入 → 401；被停權、不是家長（子女、還沒有家庭、平台管理員）→ 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（這裡一定有值）
            me.family_role   一定是 'parent'

    【請求主體】body 是 GuardianshipIn（app/schemas/family.py）
        欄位        型別  必填  說明
        wardId      字串  是    要照看的人
        guardianId  字串  否    不收：帶了而且不是自己回 403（欄位留著只是為了講清楚原因）
        範例：{"wardId": "5"}

    【成功回應】狀態碼 201
        {"id": "7", "guardian": "3", "ward": "5", "since": "2026-09-17", "scope": "全部明細",
         "guardianName": "王大明", "wardName": "王小華", "mine": true}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候             detail
        403     guardianId 帶了別人  只能設定「我」照看誰，不能替別的家長設定
        403     不是家長             只有家長可以做這件事（守衛回）
        404     對方不在我們家       這個家庭裡沒有這個人
        409     已經在照看他         已經在照看這個人了
        422     對方是家長           只能照看子女；家長之間本來就看得到彼此

    【會用到的資料表】
        表              讀／寫  用來做什麼
        family_members  讀      對方在不在我們家、是不是子女
        guardianships   讀＋寫  是不是已經在照看；新增一列
        users           讀      回傳與稽核用的名字
        audit_logs      寫      grant_guardianship

    【每一步用的工具與資料庫方法】
        步驟    呼叫         做什麼
        2 規則  family.require_can_guard(me.id, me.family_role, 對方角色, 在不在我們家, 是否已經在照看)  不在我們家丟 LookupError；是家長、已經在照看丟 ValueError
                raise (errors.conflict(…) if already else errors.unprocessable(…)) from None  同一種 ValueError，看情況回 409 或 422
        3 新增  crud.save(Guardianship, {"guardian_id": me.id, "ward_id": …, "created_by": me.id}, db=db)  since、scope 用資料表的預設值
                db.commit()  監管與稽核一起寫進去
        ⚠️ LookupError、ValueError 是兩種不同的例外：except 要分開寫。

    【寫法步驟】
        1. guardianId 帶了別人 → 403
        2. 查對方在我們家的那一列、是不是已經在照看，交給 require_can_guard（404／409／422）
        3. 新增監管關係、寫稽核，db.commit()
        4. 回傳新的那一列（mine: true）

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, HTTPException, Query
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import admin_required, block_admin, family_required, parent_required, protect, visible_scope
            from app.models import (
                Allowance, AuditLog, Family, FamilyInvite, FamilyMember, Group, GroupMember, Guardianship, SavingsGoal,
                Transaction, User,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.family import AllowanceIn, FamilyIn, GuardianshipIn, InviteCodeIn, InviteIn, JoinIn, RolePatchIn
            from app.toolkit import crud, errors, family, images, money, password_reset, period
            from app.toolkit.config import settings
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 監管人一定是自己
            if body.guardianId and body.guardianId != str(me.id):
                raise errors.forbidden("只能設定「我」照看誰，不能替別的家長設定")

            # 2. 對象要在同一個家庭、是子女、還沒在照看
            ward_id = int(body.wardId) if body.wardId.isdigit() else 0
            ward = crud.get(FamilyMember, where={"family_id": me.family_id, "user_id": ward_id, "status": "active"}, db=db)
            already = crud.exists(Guardianship, {"guardian_id": me.id, "ward_id": ward_id, "ended_at__isnull": True}, db=db)
            try:
                family.require_can_guard(me.id, me.family_role, ward.role if ward else None, ward is not None, already)
            except LookupError as exc:
                raise errors.not_found(str(exc)) from None
            except ValueError as exc:
                raise (errors.conflict(str(exc)) if already else errors.unprocessable(str(exc))) from None

            # 3. 新增監管關係，寫稽核
            row = crud.save(Guardianship, {"guardian_id": me.id, "ward_id": ward_id, "created_by": me.id}, db=db)
            name = crud.get(User, ward_id, fields="display_name", db=db)
            crud.save(AuditLog, {"actor_id": me.id, "action": "grant_guardianship", "target_type": "user",
                                 "target_id": ward_id, "meta_json": {"note": "開始照看" + name}}, db=db)
            db.commit()
            return {
                "id": str(row.id),
                "guardian": str(me.id),
                "ward": str(ward_id),
                "since": row.since.date().isoformat(),
                "scope": row.scope,
                "guardianName": me.display_name,
                "wardName": name,
                "mine": True,
            }

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/guardianships
        3. 按右上角 Authorize，貼上家長登入拿到的 accessToken
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               {"wardId": 我們家的子女}                    → 201
               再送一次                                    → 409
               {"wardId": 另一位家長}                      → 422
               {"wardId": 子女, "guardianId": 另一位家長}  → 403
        5. 打 GET /api/transactions?userId=那個子女 → 他記在任何帳本的都看得到
        6. 前端改成連你的後端（frontend/index.html 的 api-base），家庭成員頁「開始照看」，卡片出現「照看中」
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "create_guardianship and 你的"，要全部通過
    """
    raise not_ready("POST /api/guardianships", OWNER)


@router.delete("/guardianships/{gid}", summary="解除監管")
@family_required
@stub
def end_guardianship(gid: str, me: User, db: Session = Depends(get_db)):
    """解除監管

    DELETE /api/guardianships/{gid}

    【這支做什麼】
        停止照看：監管人自己，或同一個家庭的其他家長可以解除。
        ⚠️ 被照看的人自己不能解除——他可以退出家庭，但監管的意義就是「不是他說停就停」。
        設 ended_at，不刪資料列（稽核要看得到歷史）；零用金跟著歸零。

    【前端怎麼打】
        frontend/js/api.js 的 API.endGuardianship(id)
        家庭成員頁的「停止照看」。

    【誰能打】
        登入、沒被停權、已經加入家庭（家長、子女都可以）。上面的 @family_required 已經擋好了：
            沒登入 → 401；被停權、還沒有家庭（平台管理員也沒有家庭）→ 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（這裡一定有值）
            me.family_role   'parent' 或 'child'
        監管人或同一家的家長（在函式裡用 family.require_can_end_guard 檢查）。

    【路徑參數】{gid} 是監管關係的 id（字串）
        範例：DELETE /api/guardianships/7

    【成功回應】狀態碼 200
        {"id": "7", "ended": true}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                        detail
        403     被照看的人自己、或別的家庭的人  只有家長可以解除監管
        404     找不到、或已經結束              找不到這個監管關係

    【會用到的資料表】
        表              讀／寫  用來做什麼
        guardianships   讀＋寫  找還有效的那一列；設 ended_at
        family_members  讀      被照看的人在哪個家庭
        allowances      寫      這個監管人給這個孩子的零用金歸零
        users           讀      稽核裡的名字
        audit_logs      寫      end_guardianship

    【每一步用的工具與資料庫方法】
        步驟        呼叫         做什麼
        1 找        crud.get(Guardianship, where={"id": …, "ended_at__isnull": True}, db=db)  還有效的
        2 誰能解除  family.require_can_end_guard(me.id, me.family_role, row.guardian_id, 同一家嗎)  不行丟 PermissionError
                    crud.get(FamilyMember, where={"user_id": row.ward_id, "status": "active"}, fields="family_id", db=db)  被照看的人的家庭 id
        3 結束      crud.save(Guardianship, {"id": row.id, "ended_at": now}, db=db)  不刪列
                    crud.save(Allowance, {"amount": 0}, where={"payer_id": …, "ward_id": …}, db=db)  零用金歸零
                    db.commit()  一起寫進去

    【寫法步驟】
        1. 找還有效的監管關係（404）
        2. require_can_end_guard（403）
        3. 設 ended_at、零用金歸零、寫稽核，db.commit()
        4. 回 {"id", "ended": true}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, HTTPException, Query
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import admin_required, block_admin, family_required, parent_required, protect, visible_scope
            from app.models import (
                Allowance, AuditLog, Family, FamilyInvite, FamilyMember, Group, GroupMember, Guardianship, SavingsGoal,
                Transaction, User,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.family import AllowanceIn, FamilyIn, GuardianshipIn, InviteCodeIn, InviteIn, JoinIn, RolePatchIn
            from app.toolkit import crud, errors, family, images, money, password_reset, period
            from app.toolkit.config import settings
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 找還有效的那一列
            number = int(gid) if gid.isdigit() else 0
            row = crud.get(Guardianship, where={"id": number, "ended_at__isnull": True}, db=db)
            if row is None:
                raise errors.not_found("找不到這個監管關係")

            # 2. 監管人自己，或同一個家庭的家長；被照看的人自己不行
            ward_family = crud.get(FamilyMember, where={"user_id": row.ward_id, "status": "active"},
                                   fields="family_id", db=db)
            try:
                family.require_can_end_guard(me.id, me.family_role, row.guardian_id, ward_family == me.family_id)
            except PermissionError as exc:
                raise errors.forbidden(str(exc)) from None

            # 3. 設 ended_at（不刪列）、零用金歸零、寫稽核
            crud.save(Guardianship, {"id": row.id, "ended_at": datetime.now(timezone.utc)}, db=db)
            crud.save(Allowance, {"amount": 0}, where={"payer_id": row.guardian_id, "ward_id": row.ward_id}, db=db)
            names = {u.id: u.display_name for u in crud.find(User, {"id__in": [row.guardian_id, row.ward_id]}, db=db)}
            if row.guardian_id == me.id:
                note = "停止照看" + names[row.ward_id]
            else:
                note = "解除%s對%s的監管" % (names[row.guardian_id], names[row.ward_id])
            crud.save(AuditLog, {"actor_id": me.id, "action": "end_guardianship", "target_type": "user",
                                 "target_id": row.ward_id, "meta_json": {"note": note}}, db=db)
            db.commit()
            return {"id": str(row.id), "ended": True}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 DELETE /api/guardianships/{gid}
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               監管人自己解除          → 200
               同一家的另一位家長解除  → 200
               被照看的子女自己解除    → 403
               解除一個已經結束的      → 404
        5. 前端改成連你的後端（frontend/index.html 的 api-base），家庭成員頁「停止照看」，卡片的「照看中」消失
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "end_guardianship and 你的"，要全部通過
    """
    raise not_ready("DELETE /api/guardianships/{gid}", OWNER)


@router.get("/allowances", summary="我給每個被照看的人多少零用金")
@block_admin
@stub
def list_allowances(me: User, db: Session = Depends(get_db)):
    """我給每個被照看的人多少零用金

    GET /api/allowances

    【這支做什麼】
        列出我照看的每個人：我每月給他多少零用金（設定），以及他這個月花了多少（從明細現算）。
        ⚠️ 零用金是「設定」，不是一筆支出紀錄。

    【前端怎麼打】
        frontend/js/api.js 的 API.allowances()
        成員紀錄頁（家長看孩子的那一頁）。前端檢查回應裡一定要有 allowances。

    【誰能打】
        登入、沒被停權、不是平台管理員。上面的 @block_admin 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【請求參數】沒有

    【成功回應】狀態碼 200
        {"allowances": [{"wardId": "5", "wardName": "王小華", "amount": 3000, "spent": 1850}]}
        · 沒照看任何人：{"allowances": []}
        · 沒設過零用金的是 0

    【錯誤回應】
        只有守衛的 401／403，這支本身不會出錯。

    【會用到的資料表】
        表             讀／寫  用來做什麼
        guardianships  讀      我照看的人（還沒結束的）
        users          讀      他們的名字
        allowances     讀      我給每個人的設定
        transactions   讀      他們這個月的支出

    【每一步用的工具與資料庫方法】
        步驟      呼叫                               做什麼
        1 照看誰  crud.find(Guardianship, {"guardian_id": me.id, "ended_at__isnull": True}, fields="ward_id", order_by="id", db=db)  回傳 id 清單
        2 設定    crud.find(Allowance, {"payer_id": me.id, "ward_id__in": wards, "period_key__isnull": True}, db=db)  period_key 是 NULL 的就是「每月的預設值」
        3 花費    period.month_range(這個月)         起訖日
                  crud.find(Transaction, {"user_id__in": wards, "kind": "expense", "occurred_on__between": …}, fields=("user_id", "amount"), db=db)  只拿兩個欄位
                  money.add(spent.get(uid), amount)  一個人一個人加

    【寫法步驟】
        1. 查我照看的人；沒有就回空的
        2. 一次查出名字、零用金設定
        3. 一次查出他們這個月的支出，照人加起來
        4. 一個人一列回傳
        ⚠️ 只讀不寫，不用 db.commit()。

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, HTTPException, Query
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import admin_required, block_admin, family_required, parent_required, protect, visible_scope
            from app.models import (
                Allowance, AuditLog, Family, FamilyInvite, FamilyMember, Group, GroupMember, Guardianship, SavingsGoal,
                Transaction, User,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.family import AllowanceIn, FamilyIn, GuardianshipIn, InviteCodeIn, InviteIn, JoinIn, RolePatchIn
            from app.toolkit import crud, errors, family, images, money, password_reset, period
            from app.toolkit.config import settings
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 我照看的人
            wards = crud.find(Guardianship, {"guardian_id": me.id, "ended_at__isnull": True},
                              fields="ward_id", order_by="id", db=db)
            if not wards:
                return {"allowances": []}

            # 2. 名字、零用金設定
            names = {u.id: u.display_name for u in crud.find(User, {"id__in": wards}, db=db)}
            amounts = {}
            for a in crud.find(Allowance, {"payer_id": me.id, "ward_id__in": wards, "period_key__isnull": True},
                               order_by="id", db=db):
                amounts[a.ward_id] = a.amount

            # 3. 這個月花了多少（從明細現算）
            start, end = period.month_range(period.current_month(datetime.now(timezone(timedelta(hours=8))).date()))
            spent = {}
            for t in crud.find(Transaction, {"user_id__in": wards, "kind": "expense",
                                             "occurred_on__between": (start, end)}, fields=("user_id", "amount"), db=db):
                spent[t["user_id"]] = money.add(spent.get(t["user_id"]), t["amount"])

            # 4. 一個人一列
            out = []
            for w in wards:
                out.append({"wardId": str(w), "wardName": names.get(w, ""),
                            "amount": amounts.get(w, 0), "spent": spent.get(w, 0)})
            return {"allowances": out}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 GET /api/allowances
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               沒照看任何人             → {"allowances": []}
               照看一個孩子、設過 3000  → amount 是 3000，spent 是他這個月的支出
        5. 前端改成連你的後端（frontend/index.html 的 api-base），成員紀錄頁（家長看孩子）顯示零用金與花掉多少
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "list_allowances and 你的"，要全部通過
    """
    raise not_ready("GET /api/allowances", OWNER)


@router.put("/allowance", summary="設定零用金")
@parent_required
@stub
def set_allowance(body: AllowanceIn, me: User, db: Session = Depends(get_db)):
    """設定零用金

    PUT /api/allowance

    【這支做什麼】
        家長設定每月給某個被照看的人多少零用金。有就改、沒有就新增（所以用 PUT）。
        ⚠️ 零用金是設定，不是一筆支出紀錄：記成支出的話，家長的支出會憑空多一筆，孩子花掉時又算一次。
        ⚠️ 只有監管他的人能設。

    【前端怎麼打】
        frontend/js/api.js 的 API.setAllowance(wardId, amount)
        成員紀錄頁的零用金輸入框。

    【誰能打】
        登入、沒被停權、而且是家長。上面的 @parent_required 已經擋好了：
            沒登入 → 401；被停權、不是家長（子女、還沒有家庭、平台管理員）→ 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（這裡一定有值）
            me.family_role   一定是 'parent'

    【請求主體】body 是 AllowanceIn（app/schemas/family.py）
        欄位    型別  必填  說明
        wardId  字串  是    被照看的人
        amount  數字  是    0 以上（負數 FastAPI 自動回 422）
        範例：{"wardId": "5", "amount": 3000}

    【成功回應】狀態碼 200
        {"wardId": "5", "wardName": "王小華", "amount": 3000}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候            detail
        403     我沒有在照看這個人  你沒有監管這個人
        403     不是家長            只有家長可以做這件事（守衛回）
        422     amount 小於 0       （FastAPI 自動回）

    【會用到的資料表】
        表             讀／寫  用來做什麼
        guardianships  讀      我有沒有在照看他
        allowances     寫      我給他的那一列：有就改、沒有就新增
        users          讀      回傳的名字

    【每一步用的工具與資料庫方法】
        步驟    呼叫                         做什麼
        1 監管  crud.exists(Guardianship, {"guardian_id": me.id, "ward_id": …, "ended_at__isnull": True}, db=db)  還有效的監管關係
        2 寫入  crud.save(Allowance, {"amount": …}, where={"payer_id", "ward_id", "period_key": None}, upsert=True, db=db)  period_key 是 None = 每月的預設值
                money.quantize(body.amount)  3000 → Decimal("3000.00")
                db.commit()                  寫進去

    【寫法步驟】
        1. 我沒有在照看他 → 403
        2. upsert 我給他的零用金，db.commit()
        3. 回 {wardId, wardName, amount}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, HTTPException, Query
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import admin_required, block_admin, family_required, parent_required, protect, visible_scope
            from app.models import (
                Allowance, AuditLog, Family, FamilyInvite, FamilyMember, Group, GroupMember, Guardianship, SavingsGoal,
                Transaction, User,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.family import AllowanceIn, FamilyIn, GuardianshipIn, InviteCodeIn, InviteIn, JoinIn, RolePatchIn
            from app.toolkit import crud, errors, family, images, money, password_reset, period
            from app.toolkit.config import settings
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 只有監管他的人能設
            ward_id = int(body.wardId) if body.wardId.isdigit() else 0
            if not crud.exists(Guardianship, {"guardian_id": me.id, "ward_id": ward_id, "ended_at__isnull": True}, db=db):
                raise errors.forbidden("你沒有監管這個人")

            # 2. 有就改、沒有就新增（這是設定，不是一筆支出）
            crud.save(Allowance, {"amount": money.quantize(body.amount)},
                      where={"payer_id": me.id, "ward_id": ward_id, "period_key": None}, upsert=True, db=db)
            db.commit()
            name = crud.get(User, ward_id, fields="display_name", db=db)
            return {"wardId": str(ward_id), "wardName": name, "amount": body.amount}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 PUT /api/allowance
        3. 按右上角 Authorize，貼上家長登入拿到的 accessToken
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               設照看中的孩子 3000  → 200；再設 3500，allowances 還是只有一列
               設一個沒在照看的人   → 403
               amount 填 -1         → 422
        5. 打 GET /api/allowances → amount 是剛設的；GET /api/summary 的支出不能變
        6. 前端改成連你的後端（frontend/index.html 的 api-base），成員紀錄頁改零用金，重新整理後還在
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "set_allowance and 你的"，要全部通過
    """
    raise not_ready("PUT /api/allowance", OWNER)


@router.get("/audit", summary="稽核紀錄")
@admin_required
@stub
def list_audit(me: User, db: Session = Depends(get_db)):
    """稽核紀錄

    GET /api/audit

    【這支做什麼】
        平台管理頁的稽核紀錄：誰在什麼時候做了什麼（停權、改角色、照看、解散…），由新到舊。
        ⚠️ 只記動作，不記金額——稽核是查「誰改了權限」，不是另一個看帳的後門。

    【前端怎麼打】
        frontend/js/api.js 的 API.audit()
        平台管理頁。前端檢查回應裡一定要有 logs；時間前端轉成當地時間顯示。

    【誰能打】
        只有平台管理員。上面的 @admin_required 已經擋好了：
            沒登入 → 401；被停權、不是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的平台管理員（User 物件），me.id 是他的 id。

    【請求參數】沒有

    【成功回應】狀態碼 200
        {"logs": [{"id": "31", "at": "2026-09-14T10:05:00+00:00", "actor": "3", "actorName": "王大明",
                   "action": "change_role", "target": "5", "note": "把王小華設為家長"}]}
        · at 是帶時區的 ISO 8601
        · actorName 一定要後端帶：平台管理員不屬於任何家庭，前端沒有成員清單可以對名字
        · 最多回最新的 200 筆

    【錯誤回應】
        只有守衛的 401／403，這支本身不會出錯。

    【會用到的資料表】
        表          讀／寫  用來做什麼
        audit_logs  讀      稽核紀錄
        users       讀      做這件事的人的名字

    【每一步用的工具與資料庫方法】
        步驟    呼叫                                                   做什麼
        1 查    crud.find(AuditLog, order_by="-id", limit=200, db=db)  沒有條件：where 不傳就是全部；limit 限制筆數
        2 名字  crud.find(User, {"id__in": {…}}, db=db)                一次查完
        3 時間  log.created_at.replace(tzinfo=timezone.utc)            SQLite 讀回來沒有時區，補上 UTC 再 isoformat
                (log.meta_json or {}).get("note", "")                  說明放在 meta_json 的 note

    【寫法步驟】
        1. 查最新的 200 筆
        2. 一次查出做事的人的名字
        3. 一筆一筆轉成 {id, at, actor, actorName, action, target, note}，回傳
        ⚠️ 只讀不寫，不用 db.commit()。

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, HTTPException, Query
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import admin_required, block_admin, family_required, parent_required, protect, visible_scope
            from app.models import (
                Allowance, AuditLog, Family, FamilyInvite, FamilyMember, Group, GroupMember, Guardianship, SavingsGoal,
                Transaction, User,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.family import AllowanceIn, FamilyIn, GuardianshipIn, InviteCodeIn, InviteIn, JoinIn, RolePatchIn
            from app.toolkit import crud, errors, family, images, money, password_reset, period
            from app.toolkit.config import settings
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 最新的 200 筆
            logs = crud.find(AuditLog, order_by="-id", limit=200, db=db)

            # 2. 做事的人的名字（平台管理員沒有家庭，前端對不到，要後端帶）
            actor_ids = {log.actor_id for log in logs if log.actor_id}
            names = {u.id: u.display_name for u in crud.find(User, {"id__in": actor_ids}, db=db)}

            # 3. 轉成前端要的樣子（時間補上時區）
            out = []
            for log in logs:
                at = log.created_at if log.created_at.tzinfo else log.created_at.replace(tzinfo=timezone.utc)
                out.append({
                    "id": str(log.id),
                    "at": at.isoformat(),
                    "actor": str(log.actor_id) if log.actor_id else None,
                    "actorName": names.get(log.actor_id),
                    "action": log.action,
                    "target": str(log.target_id) if log.target_id is not None else None,
                    "note": (log.meta_json or {}).get("note", ""),
                })
            return {"logs": out}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 GET /api/audit
        3. 按右上角 Authorize，貼上平台管理員登入拿到的 accessToken（帳號先用 python -m app.cli make-admin 你的信箱 設成管理員）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               平台管理員打  → 200，最新的在最前面，每一筆都有 actorName
               一般使用者打  → 403
        5. 家長改一個角色之後再打 → 最上面多一筆 change_role
        6. 前端改成連你的後端（frontend/index.html 的 api-base），平台管理頁的稽核紀錄，時間顯示成台灣時間
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "list_audit and 你的"，要全部通過
    """
    raise not_ready("GET /api/audit", OWNER)
