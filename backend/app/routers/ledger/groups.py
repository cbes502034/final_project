"""
帳本：開、改、封存、移除、成員、結算、通知。

負責人：成員2（記帳）　✦ 分支：m2-ledger

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
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import catalog
from app.guards import block_admin, current_user, in_group
from app.models import AuditLog, FamilyMember, Group, GroupMember, SavingsGoal, Transaction, User
from app.routers._stub import not_ready, stub
from app.schemas.group import GroupIn, GroupMemberIn, GroupPatchIn, NotifyIn
from app.toolkit import crud, errors, ledger
from app.toolkit.db import get_db

router = APIRouter(tags=["帳本"])
OWNER = "成員2"


@router.get("/groups", summary="我加入的帳本")
@block_admin
@stub
def list_groups(me: User, includeArchived: bool = False, db: Session = Depends(get_db)):
    """我加入的帳本

    GET /api/groups

    【這支做什麼】
        列出「我加入的」帳本，順便帶上成員、筆數、我在這本帳的存款目標、我的通知開關。
        ⚠️ 只回我加入的：別人的帳本連名字都不該看到。
        ⚠️ 移除的帳本（removed_at 有值）永遠不回；封存的（archived_at 有值）要帶 includeArchived=true 才回。

    【前端怎麼打】
        frontend/js/api.js 的 API.groups() ／ API.groups({ includeArchived: true })
        右上角的帳本切換器、帳本管理頁（「已封存」那一區用 includeArchived）。前端檢查回應裡一定要有 groups。

    【誰能打】
        登入、沒被停權、不是平台管理員。上面的 @block_admin 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【查詢參數】
        參數             型別         說明
        includeArchived  true／false  連封存的一起回，預設 false。FastAPI 會把網址上的 true 轉成 True

    【成功回應】狀態碼 200
        {"me": "3",
         "groups": [
           {"id": "5", "name": "家用", "icon": "用", "color": "book-indigo", "owner": "3",
            "note": "日常開銷", "created": "2026-09-01", "kind": "standing", "endsOn": null,
            "settledAt": null, "archived": false, "settled": false, "overdue": false,
            "members": ["3", "4"], "memberNames": ["王大明", "陳美玲"],
            "count": 7, "goal": 0, "canEdit": true, "notify": false}
         ]}
        欄位     怎麼來的
        icon     名稱最後一個字
        kind     standing（一般）／temp（活動帳本，有 endsOn 結束日）
        overdue  活動帳本、還沒結算、而且 endsOn 已經過了（台灣的今天）
        count    這本帳的筆數。我在這本帳裡，這本帳的每一筆我都看得到（可見範圍的 B 路），所以就是全部筆數——跟點進去看到的一樣
        goal     我在這本帳的每月存款目標（savings_goals 最新的一列），沒設過是 0
        canEdit  我是不是建立的人（改名、加人、封存、結算都只有建立的人能做）
        notify   我自己在這本帳的通知開關（group_members.notify）

    【錯誤回應】
        只有守衛的 401／403，這支本身不會出錯。

    【會用到的資料表】
        表             讀／寫  用來做什麼
        group_members  讀      我加入了哪幾本（含我的通知開關）；每本帳有誰
        groups         讀      帳本本身
        users          讀      成員的名字
        transactions   讀      每本帳幾筆（只拿 group_id 一欄）
        savings_goals  讀      我在每本帳的存款目標

    【每一步用的工具與資料庫方法】
        步驟        呼叫                                               做什麼
        1 我的帳本  crud.find(GroupMember, {"user_id": me.id}, db=db)  我在哪幾本帳裡（每一列有 group_id、notify）
                    crud.find(Group, {"id__in": …, "removed_at__isnull": True, "archived_at__isnull": True}, order_by="id", db=db)  沒帶 includeArchived 才加 archived_at 那個條件
        2 一次查完  crud.find(GroupMember, {"group_id__in": ids}, order_by=("joined_at", "user_id"), db=db)  這幾本帳的所有成員（照加入的先後）
                    crud.find(User, {"id__in": {…}}, db=db)            成員的名字，做成 {id: 名字}
                    Counter(crud.find(Transaction, {"group_id__in": ids}, fields="group_id", db=db))  只拿 group_id 一欄，Counter 幫你數每本幾筆
                    crud.find(SavingsGoal, {"user_id": me.id, "group_id__in": ids}, order_by="id", db=db)  照 id 由舊到新放進 dict，後面的蓋掉前面的，留下最新的
        3 組形狀    g.ends_on.isoformat()                              日期轉字串；None 要先判斷
        ⚠️ 不要在迴圈裡一本一本查：帳本一多就是幾十次查詢。先一次查完，再在 Python 裡分。

    【寫法步驟】
        1. 我加入的帳本 id → 查帳本（排掉移除的；沒帶 includeArchived 也排掉封存的）；一本都沒有直接回空的
        2. 一次查完這幾本帳的成員、名字、筆數、我的存款目標，還有我的通知開關
        3. 一本一本組成前端要的樣子，回傳 {"me", "groups"}
        ⚠️ 這支只讀不寫，不用 db.commit()。

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from collections import Counter
            from datetime import date, datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, Query
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import block_admin, current_user, in_group
            from app.models import AuditLog, FamilyMember, Group, GroupMember, SavingsGoal, Transaction, User
            from app.routers._stub import not_ready, stub
            from app.schemas.group import GroupIn, GroupMemberIn, GroupPatchIn, NotifyIn
            from app.toolkit import crud, errors, ledger
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 我加入的帳本（移除的一律不列；沒帶 includeArchived 也不列封存的）
            mine = crud.find(GroupMember, {"user_id": me.id}, db=db)
            where = {"id__in": [m.group_id for m in mine], "removed_at__isnull": True}
            if not includeArchived:
                where["archived_at__isnull"] = True
            groups = crud.find(Group, where, order_by="id", db=db)
            if not groups:
                return {"me": str(me.id), "groups": []}
            ids = [g.id for g in groups]

            # 2. 一次查完：成員與名字、每本幾筆、我的存款目標、我的通知開關
            members = crud.find(GroupMember, {"group_id__in": ids}, order_by=("joined_at", "user_id"), db=db)
            names = {u.id: u.display_name for u in crud.find(User, {"id__in": {m.user_id for m in members}}, db=db)}
            counts = Counter(crud.find(Transaction, {"group_id__in": ids}, fields="group_id", db=db))
            goals = {}
            for row in crud.find(SavingsGoal, {"user_id": me.id, "group_id__in": ids}, order_by="id", db=db):
                goals[row.group_id] = row.goal_amount              # 後面的蓋掉前面的，留下最新的
            notify_on = {m.group_id: m.notify for m in mine}
            today = datetime.now(timezone(timedelta(hours=8))).date()

            # 3. 一本一本組成前端要的樣子
            out = []
            for g in groups:
                inside = [m.user_id for m in members if m.group_id == g.id]
                out.append({
                    "id": str(g.id),
                    "name": g.name,
                    "icon": g.name[-1:],
                    "color": g.color or catalog.GROUP_COLORS[0],
                    "owner": str(g.created_by),
                    "note": g.note or "",
                    "created": g.created_at.date().isoformat(),
                    "kind": g.kind,
                    "endsOn": g.ends_on.isoformat() if g.ends_on else None,
                    "settledAt": g.settled_at.isoformat() if g.settled_at else None,
                    "archived": g.archived_at is not None,
                    "settled": g.settled_at is not None,
                    "overdue": g.kind == "temp" and g.settled_at is None and g.ends_on is not None and g.ends_on < today,
                    "members": [str(u) for u in inside],
                    "memberNames": [names.get(u, "") for u in inside],
                    "count": counts[g.id],
                    "goal": goals.get(g.id, 0),
                    "canEdit": g.created_by == me.id,
                    "notify": notify_on.get(g.id, False),
                })
            return {"me": str(me.id), "groups": out}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 GET /api/groups
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               什麼都不帶                        → 只有我加入、沒封存、沒移除的
               includeArchived=true              → 封存的也出現，archived 是 true
               別人開、沒有加我的帳本            → 不會出現
               活動帳本 endsOn 填昨天、還沒結算  → overdue 是 true
        5. 前端改成連你的後端（frontend/index.html 的 api-base），右上角切換器的帳本、筆數，要跟點進去的收支明細一致
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "list_groups and u4f60" -v，要全部通過
           （u4f60 是標籤「你的」的跳脫碼。pytest 會把中文標籤轉成跳脫碼，
            -k 直接打中文比不到任何測試，會印出 0 selected）
    """
    raise not_ready("GET /api/groups", OWNER)


@router.post("/groups", status_code=201, summary="開一本帳")
@block_admin
@stub
def create_group(body: GroupIn, me: User, db: Session = Depends(get_db)):
    """開一本帳

    POST /api/groups

    【這支做什麼】
        開一本新帳本。誰都可以開（家長、子女都行）——記帳怎麼分本是個人的事，不看家裡的角色。
        建立的人自動加進這本帳（不加的話，他自己也看不到剛開的帳本）。

    【前端怎麼打】
        frontend/js/api.js 的 API.createGroup({ name, color, note, kind, endsOn })
        帳本頁「開一本帳」送出時呼叫。前端檢查回應裡一定要有 id。

    【誰能打】
        登入、沒被停權、不是平台管理員。上面的 @block_admin 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【請求主體】body 是 GroupIn（app/schemas/group.py）
        欄位    型別  必填       說明
        name    字串  是         1～20 字（FastAPI 先擋）；整理空白後不能是空的
        color   字串  否         顏色代號，只收 app/catalog.py 的 GROUP_COLORS；沒帶用第一個（book-indigo）
        kind    字串  否         standing（預設）／temp（活動帳本）。其他值 FastAPI 自動回 422
        endsOn  字串  temp 必填  活動帳本的結束日 YYYY-MM-DD；standing 帶了也不理
        note    字串  否         這本帳是做什麼的
        範例：{"name": "旅遊基金", "color": "book-violet", "kind": "temp", "endsOn": "2026-10-05", "note": ""}
        ⚠️ 顏色一定要驗：這個字串最後會被放進網頁的 style，不驗等於讓人寫任意 CSS。

    【成功回應】狀態碼 201
        {"id": "6", "name": "旅遊基金", "icon": "金", "color": "book-violet", "owner": "3", "note": "",
         "created": "2026-09-17", "kind": "temp", "endsOn": "2026-10-05", "settledAt": null,
         "archived": false, "settled": false, "members": ["3"], "canEdit": true, "notify": false}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                              detail
        400     kind 是 temp 卻沒帶 endsOn            活動帳本要有結束日
        409     同一個家庭裡已經有同名的（含封存的）  家裡已經有一本叫「旅遊基金」的帳了
        422     名稱整理完是空的                      帳本要有名字
        422     顏色不在清單裡                        沒有這個顏色
        422     endsOn 格式不對                       結束日要是 YYYY-MM-DD
        ⚠️ 重名只比「自己家的人開的帳本」：比了別人家的，等於告訴使用者別的家庭有哪些帳本。

    【會用到的資料表】
        表              讀／寫  用來做什麼
        family_members  讀      我們家有誰（重名只跟他們開的比）
        groups          讀＋寫  檢查重名；新增一列
        group_members   寫      建立的人自動加進去

    【每一步用的工具與資料庫方法】
        步驟    呼叫                             做什麼
        1 檢查  catalog.GROUP_COLORS             允許的顏色代號（跟 frontend/js/data.js 的 groupColors 一樣）
                date.fromisoformat(body.endsOn)  結束日轉日期
        2 重名  crud.find(FamilyMember, {"family_id": me.family_id, "status": "active"}, fields="user_id", db=db)  我們家的人；沒有家庭就只有我自己
                crud.exists(Group, {"name": name, "created_by__in": people, "removed_at__isnull": True}, db=db)  他們開的帳本裡有沒有同名的（移除的不算）
        3 新增  crud.save(Group, {…}, db=db)     新增帳本，拿到 id
                crud.save(GroupMember, {"group_id": group.id, "user_id": me.id}, db=db)  兩個主鍵都帶：找不到就是新增
                db.commit()                      兩列一起寫進去

    【寫法步驟】
        1. 整理名稱（422）、檢查顏色（422）；temp 要有 endsOn（400）而且格式對（422）
        2. 我們家的人開的帳本裡有同名的 → 409
        3. 新增帳本（family_id 記我現在的家庭）＋ 把自己加進去，db.commit()
        4. 回傳剛建好的帳本

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from collections import Counter
            from datetime import date, datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, Query
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import block_admin, current_user, in_group
            from app.models import AuditLog, FamilyMember, Group, GroupMember, SavingsGoal, Transaction, User
            from app.routers._stub import not_ready, stub
            from app.schemas.group import GroupIn, GroupMemberIn, GroupPatchIn, NotifyIn
            from app.toolkit import crud, errors, ledger
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 名稱、顏色、結束日
            name = " ".join(body.name.split())
            if not name:
                raise errors.unprocessable("帳本要有名字")
            color = body.color or catalog.GROUP_COLORS[0]
            if color not in catalog.GROUP_COLORS:
                raise errors.unprocessable("沒有這個顏色")
            ends_on = None
            if body.kind == "temp":
                if not body.endsOn:
                    raise errors.bad_request("活動帳本要有結束日")
                try:
                    ends_on = date.fromisoformat(body.endsOn)
                except ValueError:
                    raise errors.unprocessable("結束日要是 YYYY-MM-DD") from None

            # 2. 同一個家庭裡不能重名（含封存的）；沒有家庭就只跟自己開的比
            if me.family_id:
                people = crud.find(FamilyMember, {"family_id": me.family_id, "status": "active"}, fields="user_id", db=db)
            else:
                people = [me.id]
            if crud.exists(Group, {"name": name, "created_by__in": people, "removed_at__isnull": True}, db=db):
                raise errors.conflict("家裡已經有一本叫「%s」的帳了" % name)

            # 3. 新增帳本，建立的人自動加進去
            group = crud.save(Group, {
                "family_id": me.family_id,
                "name": name,
                "color": color,
                "note": body.note.strip() or None,
                "created_by": me.id,
                "kind": body.kind,
                "ends_on": ends_on,
            }, db=db)
            crud.save(GroupMember, {"group_id": group.id, "user_id": me.id}, db=db)
            db.commit()

            # 4. 回傳剛建好的帳本
            return {
                "id": str(group.id),
                "name": group.name,
                "icon": group.name[-1:],
                "color": group.color,
                "owner": str(me.id),
                "note": group.note or "",
                "created": group.created_at.date().isoformat(),
                "kind": group.kind,
                "endsOn": ends_on.isoformat() if ends_on else None,
                "settledAt": None,
                "archived": False,
                "settled": False,
                "members": [str(me.id)],
                "canEdit": True,
                "notify": False,
            }

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/groups
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               {"name": "家用"}                                 → 201，members 只有自己
               再開一本「家用」                                 → 409
               {"name": "旅遊", "kind": "temp"}（沒有 endsOn）  → 400
               {"name": "旅遊", "color": "red"}                 → 422
        5. 打 GET /api/groups → 剛開的那本要在清單裡
        6. 前端改成連你的後端（frontend/index.html 的 api-base），帳本頁開一本，右上角切換器要馬上出現
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "create_group and u4f60" -v，要全部通過
           （u4f60 是標籤「你的」的跳脫碼。pytest 會把中文標籤轉成跳脫碼，
            -k 直接打中文比不到任何測試，會印出 0 selected）
    """
    raise not_ready("POST /api/groups", OWNER)


@router.patch("/groups/{gid}", summary="改名稱、顏色、說明")
@stub
def update_group(
    body: GroupPatchIn,
    group=Depends(in_group("gid", owner=True)),
    me: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """改名稱、顏色、說明

    PATCH /api/groups/{gid}

    【這支做什麼】
        建立的人改帳本的名稱、顏色、說明；或是帶 {"archived": false} 把封存的帳本復原。
        ⚠️ 封存在使用者眼裡跟刪掉一模一樣，所以「復原」一定要做得出來。
           復原不用還原任何資料：封存從頭到尾沒動過任何一筆紀錄，只是讓它重新出現在清單上。

    【前端怎麼打】
        frontend/js/api.js 的 API.updateGroup(gid, patch)
        帳本頁改名／換色／改說明，以及「已封存」那一區的「復原」。回應是改完的帳本。

    【誰能打】
        登入、沒被停權，而且這本帳是自己開的。參數 group=Depends(in_group("gid", owner=True)) 已經擋好了：
            沒登入 → 401；被停權 → 403
            {gid} 不是數字、找不到、或已經移除 → 404「找不到這本帳」
            不是建立這本帳的人 → 403「只有建立這本帳的人可以做這件事」
        所以函式裡不用再檢查。group 就是那本帳（Group 物件），group.created_by 就是我。
        另外收一個 me=Depends(current_user)（目前登入的人）：檢查重名要用 me.family_id。

    【請求主體】body 是 GroupPatchIn（app/schemas/group.py），只送要改的
        欄位      型別         說明
        name      字串         1～20 字；同一個家庭裡不能跟別本重名
        color     字串         只收 catalog.GROUP_COLORS 裡的代號
        note      字串         說明；空字串 = 清掉
        archived  true／false  只收 false（復原封存）；封存本身走 DELETE
        範例：{"name": "家用開銷"}　或　{"archived": false}
        · body.model_fields_set 是「有送來的欄位名字」，沒送的不要動
        · 不認得的欄位 FastAPI 直接回 422（GroupPatchIn 設了 extra="forbid"）

    【成功回應】狀態碼 200
        改完的帳本：{"id", "name", "icon", "color", "owner", "note", "created", "kind", "endsOn",
                    "settledAt", "archived", "settled", "canEdit": true}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                      detail
        400     什麼都沒送                    沒有要改的欄位
        403     不是建立的人                  只有建立這本帳的人可以做這件事（守衛回）
        404     找不到、已經移除              找不到這本帳（守衛回）
        409     新名稱跟家裡另一本重複        家裡已經有一本叫「家用」的帳了
        422     名稱整理完是空的              帳本要有名字
        422     顏色不在清單裡                沒有這個顏色
        422     archived 送 true              封存請用 DELETE；這裡的 archived 只收 false（復原）
        422     不認得的欄位、名稱超過 20 字  （FastAPI 自動回）

    【會用到的資料表】
        表              讀／寫  用來做什麼
        family_members  讀      我們家有誰（改名時檢查重名）
        groups          讀＋寫  檢查重名；改這一本

    【每一步用的工具與資料庫方法】
        步驟        呼叫                                                  做什麼
        1 有送什麼  body.model_fields_set                                 有送來的欄位名字（set），例如 {"name"}
        2 重名      crud.exists(Group, {"name": …, "created_by__in": people, "removed_at__isnull": True, "id__ne": group.id}, db=db)  "id__ne" = id 不等於：排除自己這一本
        3 寫回      crud.save(Group, {"id": group.id, **changes}, db=db)  帶主鍵 = 改那一本；group 物件也會跟著變
                    db.commit()                                           寫進去

    【寫法步驟】
        1. 有送 name：整理空白（422）；跟原本不一樣才檢查重名（409）
        2. 有送 color：要在清單裡（422）
        3. 有送 note：去頭尾空白，空的存 NULL
        4. 有送 archived：只收 false，把 archived_at 設回 NULL（復原）
        5. 什麼都沒改到 → 400；有的話 crud.save、db.commit()，回傳改完的帳本

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from collections import Counter
            from datetime import date, datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, Query
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import block_admin, current_user, in_group
            from app.models import AuditLog, FamilyMember, Group, GroupMember, SavingsGoal, Transaction, User
            from app.routers._stub import not_ready, stub
            from app.schemas.group import GroupIn, GroupMemberIn, GroupPatchIn, NotifyIn
            from app.toolkit import crud, errors, ledger
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            sent = body.model_fields_set
            changes = {}

            # 1. 名稱：不能空白；同一個家庭裡不能跟別本重名
            if "name" in sent:
                name = " ".join((body.name or "").split())
                if not name:
                    raise errors.unprocessable("帳本要有名字")
                if name != group.name:
                    if me.family_id:
                        people = crud.find(FamilyMember, {"family_id": me.family_id, "status": "active"},
                                           fields="user_id", db=db)
                    else:
                        people = [me.id]
                    if crud.exists(Group, {"name": name, "created_by__in": people, "removed_at__isnull": True,
                                           "id__ne": group.id}, db=db):
                        raise errors.conflict("家裡已經有一本叫「%s」的帳了" % name)
                changes["name"] = name

            # 2. 顏色只收清單裡的代號
            if "color" in sent:
                if body.color not in catalog.GROUP_COLORS:
                    raise errors.unprocessable("沒有這個顏色")
                changes["color"] = body.color

            # 3. 說明
            if "note" in sent:
                changes["note"] = (body.note or "").strip() or None

            # 4. 復原封存：只收 false
            if "archived" in sent:
                if body.archived is not False:
                    raise errors.unprocessable("封存請用 DELETE；這裡的 archived 只收 false（復原）")
                changes["archived_at"] = None

            if not changes:
                raise errors.bad_request("沒有要改的欄位")
            crud.save(Group, {"id": group.id, **changes}, db=db)
            db.commit()
            return {
                "id": str(group.id),
                "name": group.name,
                "icon": group.name[-1:],
                "color": group.color or catalog.GROUP_COLORS[0],
                "owner": str(group.created_by),
                "note": group.note or "",
                "created": group.created_at.date().isoformat(),
                "kind": group.kind,
                "endsOn": group.ends_on.isoformat() if group.ends_on else None,
                "settledAt": group.settled_at.isoformat() if group.settled_at else None,
                "archived": group.archived_at is not None,
                "settled": group.settled_at is not None,
                "canEdit": True,
            }

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 PATCH /api/groups/{gid}
        3. 按右上角 Authorize，貼上「建立這本帳的人」登入拿到的 accessToken
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               {"name": "家用開銷"}                   → 200，name 變了，其他沒變
               {"color": "red"}                       → 422
               {"archived": false}（對一本封存的帳）  → 200，archived 變 false
               {}                                     → 400
               用帳本裡另一個成員的 token             → 403
        5. 前端改成連你的後端（frontend/index.html 的 api-base），帳本頁「已封存」按「復原」，那本帳要回到切換器
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "update_group and u4f60" -v，要全部通過
           （u4f60 是標籤「你的」的跳脫碼。pytest 會把中文標籤轉成跳脫碼，
            -k 直接打中文比不到任何測試，會印出 0 selected）
    """
    raise not_ready("PATCH /api/groups/{gid}", OWNER)


@router.delete("/groups/{gid}", summary="封存；permanent=true 是移除")
@stub
def archive_or_remove_group(
    permanent: bool = False,
    group=Depends(in_group("gid", owner=True)),
    db: Session = Depends(get_db),
):
    """封存；permanent=true 是移除

    DELETE /api/groups/{gid}

    【這支做什麼】
        兩件事，看網址有沒有帶 permanent=true：
            沒帶：封存。設 archived_at，任何紀錄都不動，之後可以用 PATCH 復原
            permanent=true：移除。只給「結算過的活動帳本」用，設 removed_at，不能復原
        ⚠️ 移除的是帳本，不是紀錄：transactions 一筆都不動，每一筆仍在記帳的人自己的明細與統計裡，
           過去月份的數字不會變。只是這本帳從任何清單消失，只靠這本帳看得到別人紀錄的成員之後就看不到了。

    【前端怎麼打】
        frontend/js/api.js 的 API.archiveGroup(gid)　→ DELETE /api/groups/5
        frontend/js/api.js 的 API.removeGroup(gid)　 → DELETE /api/groups/5?permanent=true
        兩個都會先跳確認；移除還要輸入確認碼、用密碼確認。

    【誰能打】
        登入、沒被停權，而且這本帳是自己開的。參數 group=Depends(in_group("gid", owner=True)) 已經擋好了：
            沒登入 → 401；被停權 → 403
            {gid} 不是數字、找不到、或已經移除 → 404「找不到這本帳」
            不是建立這本帳的人 → 403「只有建立這本帳的人可以做這件事」
        所以函式裡不用再檢查。group 就是那本帳（Group 物件），group.created_by 就是我。

    【查詢參數】
        參數       型別         說明
        permanent  true／false  true = 移除，預設 false = 封存

    【成功回應】狀態碼 200
        封存：{"id": "5", "archived": true}
        移除：{"id": "5", "removed": true}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候              detail
        403     不是建立的人          只有建立這本帳的人可以做這件事（守衛回）
        404     找不到、已經移除      找不到這本帳（守衛回）
        409     移除一本還沒結算的帳  只有結算過的活動帳本可以移除；還在用的帳本請改用封存

    【會用到的資料表】
        表          讀／寫  用來做什麼
        groups      寫      設 archived_at 或 removed_at（都是改時間欄位，不是刪列）
        audit_logs  寫      移除要留一筆稽核（remove_group）

    【每一步用的工具與資料庫方法】
        步驟    呼叫                                                           做什麼
        1 封存  crud.save(Group, {"id": group.id, "archived_at": now}, db=db)  已經封存過就不要再改時間
        2 移除  ledger.require_removable(group.created_by, group.created_by, group.settled_at, group.removed_at)  沒結算丟 ValueError（建立者檢查守衛已經做了）
                crud.save(Group, {"id": group.id, "removed_at": now}, db=db)   設移除時間
                crud.save(AuditLog, {"actor_id": …, "action": "remove_group", …}, db=db)  稽核只記動作，不記金額
                db.commit()                                                    兩件事一起寫進去

    【寫法步驟】
        1. 沒帶 permanent：還沒封存才設 archived_at，db.commit()，回 {"id", "archived": true}
        2. 帶 permanent=true：require_removable（沒結算 409）→ 設 removed_at → 寫稽核 → db.commit()
        3. 回 {"id", "removed": true}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from collections import Counter
            from datetime import date, datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, Query
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import block_admin, current_user, in_group
            from app.models import AuditLog, FamilyMember, Group, GroupMember, SavingsGoal, Transaction, User
            from app.routers._stub import not_ready, stub
            from app.schemas.group import GroupIn, GroupMemberIn, GroupPatchIn, NotifyIn
            from app.toolkit import crud, errors, ledger
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            now = datetime.now(timezone.utc)

            # 1. 沒帶 permanent：封存（只設時間，任何紀錄都不動，之後可以復原）
            if not permanent:
                if group.archived_at is None:
                    crud.save(Group, {"id": group.id, "archived_at": now}, db=db)
                    db.commit()
                return {"id": str(group.id), "archived": True}

            # 2. permanent=true：移除。只有結算過的活動帳本可以
            try:
                ledger.require_removable(group.created_by, group.created_by, group.settled_at, group.removed_at)
            except ValueError as exc:
                raise errors.conflict(str(exc)) from None
            crud.save(Group, {"id": group.id, "removed_at": now}, db=db)
            crud.save(AuditLog, {
                "actor_id": group.created_by,
                "action": "remove_group",
                "target_type": "group",
                "target_id": group.id,
                "meta_json": {"note": "移除已結算的「%s」" % group.name},
            }, db=db)
            db.commit()
            return {"id": str(group.id), "removed": True}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 DELETE /api/groups/{gid}
        3. 按右上角 Authorize，貼上「建立這本帳的人」登入拿到的 accessToken
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               不帶 permanent                         → 200，GET /api/groups 看不到、includeArchived=true 看得到
               permanent=true（還沒結算的帳）         → 409
               先 POST .../settle，再 permanent=true  → 200，includeArchived=true 也看不到
        5. 移除之後，那本帳裡的紀錄在 GET /api/transactions 還查得到（自己記的那幾筆）
        6. 前端改成連你的後端（frontend/index.html 的 api-base），帳本頁「封存」「移除」都試一次，確認文案寫著「紀錄不會刪」
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "archive_or_remove_group and u4f60" -v，要全部通過
           （u4f60 是標籤「你的」的跳脫碼。pytest 會把中文標籤轉成跳脫碼，
            -k 直接打中文比不到任何測試，會印出 0 selected）
    """
    raise not_ready("DELETE /api/groups/{gid}", OWNER)


@router.post("/groups/{gid}/members", status_code=201, summary="把家人加進這本帳")
@stub
def add_group_member(
    body: GroupMemberIn,
    group=Depends(in_group("gid", owner=True)),
    me: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """把家人加進這本帳

    POST /api/groups/{gid}/members

    【這支做什麼】
        建立的人把一位家人加進這本帳。只能加同一個家庭的人——平台管理員不屬於任何家庭，自然加不進來。
        加進來之後，他就看得到這本帳的全部紀錄，也能往這本帳記帳（帳本裡沒有權限等級）。

    【前端怎麼打】
        frontend/js/api.js 的 API.addGroupMember(gid, userId)
        帳本頁「加人」選單（名單來自 GET /api/family 的 members）。

    【誰能打】
        登入、沒被停權，而且這本帳是自己開的。參數 group=Depends(in_group("gid", owner=True)) 已經擋好了：
            沒登入 → 401；被停權 → 403
            {gid} 不是數字、找不到、或已經移除 → 404「找不到這本帳」
            不是建立這本帳的人 → 403「只有建立這本帳的人可以做這件事」
        所以函式裡不用再檢查。group 就是那本帳（Group 物件），group.created_by 就是我。
        另外收一個 me=Depends(current_user)：要用 me.family_id 確認對方是同一家的。

    【請求主體】body 是 GroupMemberIn（app/schemas/group.py）
        欄位    型別  必填  說明
        userId  字串  是    要加的人
        範例：{"userId": "4"}

    【成功回應】狀態碼 201
        {"group": "5", "user": "4"}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                                                        detail
        403     不是建立的人                                                    只有建立這本帳的人可以做這件事（守衛回）
        404     對方不在我們家（別的家庭、沒有家庭、平台管理員、根本沒這個人）  這個家庭裡沒有這個人
        409     他已經在這本帳裡                                                他已經在這本帳裡了
        ⚠️ 各種「不行」都回同一句 404，不要說出他在不在別的家庭。

    【會用到的資料表】
        表              讀／寫  用來做什麼
        family_members  讀      對方是不是我們家的人（status = active）
        users           讀      對方是不是平台管理員（多一道保險）
        group_members   讀＋寫  已經在裡面了嗎；新增一列

    【每一步用的工具與資料庫方法】
        步驟      呼叫                            做什麼
        1 同一家  crud.exists(FamilyMember, {"family_id": me.family_id, "user_id": …, "status": "active"}, db=db)  我沒有家庭（None）的話直接當作不是
                  crud.get(User, user_id, db=db)  用主鍵拿對方
        2 重複    crud.exists(GroupMember, {"group_id": group.id, "user_id": user_id}, db=db)  已經在裡面了嗎
        3 新增    crud.save(GroupMember, {"group_id": group.id, "user_id": user_id}, db=db)  兩個主鍵都帶 → 新增一列
                  db.commit()                     寫進去

    【寫法步驟】
        1. userId 轉整數；對方要是我們家、status active、不是平台管理員 → 不然 404
        2. 已經在這本帳裡 → 409
        3. 新增 group_members（notify 預設 false），db.commit()，回 {"group", "user"}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from collections import Counter
            from datetime import date, datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, Query
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import block_admin, current_user, in_group
            from app.models import AuditLog, FamilyMember, Group, GroupMember, SavingsGoal, Transaction, User
            from app.routers._stub import not_ready, stub
            from app.schemas.group import GroupIn, GroupMemberIn, GroupPatchIn, NotifyIn
            from app.toolkit import crud, errors, ledger
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 只能加同一個家庭的人（平台管理員不屬於任何家庭，也加不進來）
            user_id = int(body.userId) if body.userId.isdigit() else 0
            same_family = me.family_id is not None and crud.exists(
                FamilyMember, {"family_id": me.family_id, "user_id": user_id, "status": "active"}, db=db)
            if not same_family or crud.get(User, user_id, db=db).is_platform_admin:
                raise errors.not_found("這個家庭裡沒有這個人")

            # 2. 已經在裡面就不用再加
            if crud.exists(GroupMember, {"group_id": group.id, "user_id": user_id}, db=db):
                raise errors.conflict("他已經在這本帳裡了")

            # 3. 加進去
            crud.save(GroupMember, {"group_id": group.id, "user_id": user_id}, db=db)
            db.commit()
            return {"group": str(group.id), "user": str(user_id)}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/groups/{gid}/members
        3. 按右上角 Authorize，貼上「建立這本帳的人」登入拿到的 accessToken
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               userId 填家人          → 201
               再加一次               → 409
               userId 填別的家庭的人  → 404
        5. 被加進來的人打 GET /api/groups → 看得到這本帳
        6. 前端改成連你的後端（frontend/index.html 的 api-base），帳本頁「加人」選一位家人，成員名單要多一個名字
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "add_group_member and u4f60" -v，要全部通過
           （u4f60 是標籤「你的」的跳脫碼。pytest 會把中文標籤轉成跳脫碼，
            -k 直接打中文比不到任何測試，會印出 0 selected）
    """
    raise not_ready("POST /api/groups/{gid}/members", OWNER)


@router.delete("/groups/{gid}/members/{user_id}", summary="把人移出這本帳")
@stub
def remove_group_member(user_id: str, group=Depends(in_group("gid", owner=True)), db: Session = Depends(get_db)):
    """把人移出這本帳

    DELETE /api/groups/{gid}/members/{user_id}

    【這支做什麼】
        建立的人把某人移出這本帳。
        移出之後他看不到別人記在這本帳的紀錄，也不能再往這本帳記；
        ⚠️ 他自己記過的不會消失：可見範圍一定包含自己，那些紀錄仍在他自己的明細裡。

    【前端怎麼打】
        frontend/js/api.js 的 API.removeGroupMember(gid, userId)
        帳本頁成員名單的「移出」。

    【誰能打】
        登入、沒被停權，而且這本帳是自己開的。參數 group=Depends(in_group("gid", owner=True)) 已經擋好了：
            沒登入 → 401；被停權 → 403
            {gid} 不是數字、找不到、或已經移除 → 404「找不到這本帳」
            不是建立這本帳的人 → 403「只有建立這本帳的人可以做這件事」
        所以函式裡不用再檢查。group 就是那本帳（Group 物件），group.created_by 就是我。

    【路徑參數】{gid} 是帳本（守衛已經換成 group），{user_id} 是要移出的人（字串）
        範例：DELETE /api/groups/5/members/4

    【成功回應】狀態碼 200
        {"group": "5", "user": "4", "removed": true}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候              detail
        400     要移出的是建立者自己  建立者不能把自己移出去
        403     不是建立的人          只有建立這本帳的人可以做這件事（守衛回）
        404     他本來就不在這本帳裡  他不在這本帳裡
        ⚠️ 建立者不能移出自己：不然這本帳就沒人管得動了。

    【會用到的資料表】
        表             讀／寫    用來做什麼
        group_members  寫（刪）  刪掉他那一列（成員關係本來就不是紀錄，可以刪）

    【每一步用的工具與資料庫方法】
        步驟  呼叫         做什麼
        1 刪  crud.remove(GroupMember, {"group_id": group.id, "user_id": uid}, db=db)  回傳刪了幾列；0 表示他本來就不在
              db.commit()  寫進去

    【寫法步驟】
        1. user_id 轉整數；是建立者本人 → 400
        2. 刪掉那一列；刪了 0 列 → 404
        3. db.commit()，回 {"group", "user", "removed": true}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from collections import Counter
            from datetime import date, datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, Query
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import block_admin, current_user, in_group
            from app.models import AuditLog, FamilyMember, Group, GroupMember, SavingsGoal, Transaction, User
            from app.routers._stub import not_ready, stub
            from app.schemas.group import GroupIn, GroupMemberIn, GroupPatchIn, NotifyIn
            from app.toolkit import crud, errors, ledger
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 建立者不能把自己移出去，不然這本帳沒人管得動
            uid = int(user_id) if user_id.isdigit() else 0
            if uid == group.created_by:
                raise errors.bad_request("建立者不能把自己移出去")

            # 2. 刪掉他的成員關係（他自己記過的紀錄不動）
            removed = crud.remove(GroupMember, {"group_id": group.id, "user_id": uid}, db=db)
            if not removed:
                raise errors.not_found("他不在這本帳裡")
            db.commit()
            return {"group": str(group.id), "user": str(uid), "removed": True}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 DELETE /api/groups/{gid}/members/{user_id}
        3. 按右上角 Authorize，貼上「建立這本帳的人」登入拿到的 accessToken
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               移出一位成員    → 200
               再移一次        → 404
               user_id 填自己  → 400
        5. 被移出的人打 GET /api/transactions → 還看得到自己記在這本帳的，看不到別人記的
        6. 前端改成連你的後端（frontend/index.html 的 api-base），帳本頁按「移出」，成員名單少一個名字
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "remove_group_member and u4f60" -v，要全部通過
           （u4f60 是標籤「你的」的跳脫碼。pytest 會把中文標籤轉成跳脫碼，
            -k 直接打中文比不到任何測試，會印出 0 selected）
    """
    raise not_ready("DELETE /api/groups/{gid}/members/{user_id}", OWNER)


@router.post("/groups/{gid}/settle", summary="結算活動帳本")
@stub
def settle_group(group=Depends(in_group("gid", owner=True)), db: Session = Depends(get_db)):
    """結算活動帳本

    POST /api/groups/{gid}/settle

    【這支做什麼】
        結算活動帳本（kind = temp）：標記結束，之後這本帳唯讀——記帳、修改、刪除都回 409。
        ⚠️ 結算不搬動任何一筆紀錄，也不改變任何人的可見範圍。結算過的才能「移除」。

    【前端怎麼打】
        frontend/js/api.js 的 API.settleGroup(gid)
        帳本頁活動帳本的「結算」（過了結束日會提醒，但不會自動結算）。

    【誰能打】
        登入、沒被停權，而且這本帳是自己開的。參數 group=Depends(in_group("gid", owner=True)) 已經擋好了：
            沒登入 → 401；被停權 → 403
            {gid} 不是數字、找不到、或已經移除 → 404「找不到這本帳」
            不是建立這本帳的人 → 403「只有建立這本帳的人可以做這件事」
        所以函式裡不用再檢查。group 就是那本帳（Group 物件），group.created_by 就是我。

    【請求主體】沒有

    【成功回應】狀態碼 200
        {"id": "6", "settledAt": "2026-10-05T10:00:00+00:00"}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                     detail
        400     一般帳本（kind = standing）  只有活動帳本需要結算
        403     不是建立的人                 只有建立這本帳的人可以做這件事（守衛回）
        409     已經結算過了                 這本帳已經結算過了

    【會用到的資料表】
        表      讀／寫  用來做什麼
        groups  寫      設 settled_at

    【每一步用的工具與資料庫方法】
        步驟      呼叫                                                          做什麼
        1 設時間  datetime.now(timezone.utc)                                    現在（UTC）；資料庫的時間一律存 UTC
                  crud.save(Group, {"id": group.id, "settled_at": now}, db=db)  改那一本
                  db.commit()                                                   寫進去
        · 之後記帳、修改、刪除的路由用 ledger.require_open／require_editable 擋，這支不用管。

    【寫法步驟】
        1. 不是活動帳本 → 400；已經結算 → 409
        2. 設 settled_at = 現在，db.commit()
        3. 回 {"id", "settledAt"}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from collections import Counter
            from datetime import date, datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, Query
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import block_admin, current_user, in_group
            from app.models import AuditLog, FamilyMember, Group, GroupMember, SavingsGoal, Transaction, User
            from app.routers._stub import not_ready, stub
            from app.schemas.group import GroupIn, GroupMemberIn, GroupPatchIn, NotifyIn
            from app.toolkit import crud, errors, ledger
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 只有活動帳本、而且還沒結算的才能結算
            if group.kind != "temp":
                raise errors.bad_request("只有活動帳本需要結算")
            if group.settled_at is not None:
                raise errors.conflict("這本帳已經結算過了")

            # 2. 標記結算時間（之後這本帳唯讀；紀錄一筆都不動）
            now = datetime.now(timezone.utc)
            crud.save(Group, {"id": group.id, "settled_at": now}, db=db)
            db.commit()
            return {"id": str(group.id), "settledAt": now.isoformat()}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/groups/{gid}/settle
        3. 按右上角 Authorize，貼上「建立這本帳的人」登入拿到的 accessToken
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               結算一本活動帳本  → 200，有 settledAt
               再結算一次        → 409
               結算一般帳本      → 400
        5. 往這本帳記一筆（POST /api/transactions 帶 groupId）→ 409
        6. 前端改成連你的後端（frontend/index.html 的 api-base），帳本頁按「結算」，那本帳的紀錄不再有修改／刪除鈕
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "settle_group and u4f60" -v，要全部通過
           （u4f60 是標籤「你的」的跳脫碼。pytest 會把中文標籤轉成跳脫碼，
            -k 直接打中文比不到任何測試，會印出 0 selected）
    """
    raise not_ready("POST /api/groups/{gid}/settle", OWNER)


@router.patch("/groups/{gid}/notify", summary="這本帳有動靜要不要通知我")
@stub
def set_group_notify(
    body: NotifyIn,
    group=Depends(in_group("gid")),
    me: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """這本帳有動靜要不要通知我

    PATCH /api/groups/{gid}/notify

    【這支做什麼】
        這本帳有人記帳時，要不要通知我。改的是「我自己」那一列 group_members.notify，不影響別人。
        預設關：開著的話光家用一個月就是好幾十則。
        我照看的人記的帳，不管這裡開不開都會通知（監管優先，見 toolkit/notify.py）。

    【前端怎麼打】
        frontend/js/api.js 的 API.setGroupNotify(gid, on)
        帳本頁每一本的通知開關。

    【誰能打】
        登入、沒被停權，而且我在這本帳裡。參數 group=Depends(in_group("gid")) 已經擋好了：
            沒登入 → 401；被停權 → 403
            {gid} 不是數字、找不到、或已經移除 → 404「找不到這本帳」
            我不在這本帳裡 → 403「你不在這本帳裡」
        所以函式裡不用再檢查。group 就是那本帳（Group 物件）。
        另外收一個 me=Depends(current_user)：要知道改的是哪一個人那一列。

    【請求主體】body 是 NotifyIn（app/schemas/group.py）
        欄位    型別         必填  說明
        notify  true／false  是    開或關
        範例：{"notify": true}

    【成功回應】狀態碼 200
        {"group": "5", "notify": true}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                 detail
        403     我不在這本帳裡           你不在這本帳裡（守衛回）
        404     找不到、已經移除         找不到這本帳（守衛回）
        422     notify 不是 true／false  （FastAPI 自動回）

    【會用到的資料表】
        表             讀／寫  用來做什麼
        group_members  寫      改我那一列的 notify

    【每一步用的工具與資料庫方法】
        步驟  呼叫         做什麼
        1 改  crud.save(GroupMember, {"notify": body.notify}, where={"group_id": group.id, "user_id": me.id}, db=db)  有 where = 改所有符合的（這裡剛好一列），回傳改了幾列
              db.commit()  寫進去

    【寫法步驟】
        1. 把我那一列的 notify 改成送來的值（守衛已經確認我在裡面，一定找得到）
        2. db.commit()，回 {"group", "notify"}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from collections import Counter
            from datetime import date, datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, Query
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import block_admin, current_user, in_group
            from app.models import AuditLog, FamilyMember, Group, GroupMember, SavingsGoal, Transaction, User
            from app.routers._stub import not_ready, stub
            from app.schemas.group import GroupIn, GroupMemberIn, GroupPatchIn, NotifyIn
            from app.toolkit import crud, errors, ledger
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 只改我自己那一列，不影響別人
            crud.save(GroupMember, {"notify": body.notify}, where={"group_id": group.id, "user_id": me.id}, db=db)
            db.commit()
            return {"group": str(group.id), "notify": body.notify}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 PATCH /api/groups/{gid}/notify
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               {"notify": true}    → 200
               不在這本帳裡的人打  → 403
        5. 開了之後，帳本裡另一個人記一筆 → 你的 GET /api/notifications 多一則 group_transaction
        6. 前端改成連你的後端（frontend/index.html 的 api-base），帳本頁切換通知開關，重新整理之後要維持
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "set_group_notify and u4f60" -v，要全部通過
           （u4f60 是標籤「你的」的跳脫碼。pytest 會把中文標籤轉成跳脫碼，
            -k 直接打中文比不到任何測試，會印出 0 selected）
    """
    raise not_ready("PATCH /api/groups/{gid}/notify", OWNER)
