"""
預算與每月存款目標。

負責人：成員3（數字）　✦ 分支：m3-analytics

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

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.guards import block_admin, visible_scope
from app.models import Budget, Category, Group, GroupMember, SavingsGoal, Transaction, User
from app.routers._stub import not_ready, stub
from app.schemas.stats import BudgetIn, SavingsGoalIn
from app.toolkit import crud, errors, money, period, roles
from app.toolkit.db import get_db

router = APIRouter(tags=["預算與存款目標"])
OWNER = "成員3"


@router.get("/budgets", summary="預算與已花")
@block_admin
@stub
def list_budgets(me: User, groupId: str | None = None, db: Session = Depends(get_db)):
    """預算與已花

    GET /api/budgets

    【這支做什麼】
        列出「我看得到的人」的每月分類預算，以及這個月已經花了多少（used）。
        ⚠️ used 一律從明細現算，不存在資料庫：存起來的話，每記一筆、改一筆、刪一筆都要記得同步，漏一次就對不起來。
        ⚠️ 帶了 groupId 時，used 只算那本帳裡的支出——跟同一頁的「本月支出」用同一個條件。

    【前端怎麼打】
        frontend/js/api.js 的 API.budgets({ groupId })
        總覽的預算卡、個人資料頁「每月預算」、前端產生建議的備援。前端檢查回應裡一定要有 budgets。
        catName、catColor、userName 前端會自己補；pct、over 這支會回，沒回前端也補得出來。

    【誰能打】
        登入、沒被停權、不是平台管理員。上面的 @block_admin 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【查詢參數】
        參數     型別  說明
        groupId  字串  只算那一本帳的支出；all 等於沒帶。要是我加入的帳本，不然 403

    【成功回應】狀態碼 200
        {"budgets": [
           {"user": "4", "period": "month", "cat": "5", "limit": 3000, "used": 4200, "over": true, "pct": 1.4}
         ]}
        · 用掉比例（pct）高的排前面
        · ⚠️ 這裡的 period 是 "month"／"year"（預算的週期），不是 "2026-09"
        · 這一版畫面只用每月預算，所以只回 period_type = month、而且有分類的

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                  detail
        403     groupId 是我沒加入的帳本  你不在這本帳裡

    【會用到的資料表】
        表                                                    讀／寫  用來做什麼
        guardianships、family_members、group_members、groups  讀      visible_scope()：看得到誰
        budgets                                               讀      這些人的每月分類預算
        transactions                                          讀      這個月每個人、每個分類花了多少

    【每一步用的工具與資料庫方法】
        步驟        呼叫                                                做什麼
        1 這個月    period.month_range(this_month)                      "2026-09" → (9/1, 9/30)，兩端都包含
        2 誰的預算  crud.find(Budget, {"user_id__in": users, "period_type": "month", "category_id__isnull": False}, db=db)  看得到的人的每月分類預算
        4 已花      crud.find(Transaction, {…, "kind": "expense", "occurred_on__between": (start, end)}, fields=("user_id", "category_id", "amount"), db=db)  只拿三個欄位
                    money.add(spent.get(key), t["amount"])              None 會當 0，所以第一次加也不用先判斷
        5 比例      money.ratio(used, limit)                            分母是 0 也不會爆（回 0）
                    money.quantize(…, 4)                                四捨五入到小數 4 位
                    out.sort(key=lambda row: row["pct"], reverse=True)  由大到小排

    【寫法步驟】
        1. 算出台灣的這個月與起訖日
        2. visible_scope 拿到看得到的人，查他們的每月分類預算
        3. 有 groupId：要在我加入的帳本裡（403）
        4. 一次查出這些人這個月的支出，照（人, 分類）加起來
        5. 每一筆預算配上 used、over、pct，照 pct 由大到小排，回傳
        ⚠️ 只讀不寫，不用 db.commit()。

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, Query
            from sqlalchemy.orm import Session

            from app.guards import block_admin, visible_scope
            from app.models import Budget, Category, Group, GroupMember, SavingsGoal, Transaction, User
            from app.routers._stub import not_ready, stub
            from app.schemas.stats import BudgetIn, SavingsGoalIn
            from app.toolkit import crud, errors, money, period, roles
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 這個月的起訖（台灣時間）
            this_month = period.current_month(datetime.now(timezone(timedelta(hours=8))).date())
            start, end = period.month_range(this_month)

            # 2. 我看得到的人的每月分類預算
            users, groups = visible_scope(me, db)
            budgets = crud.find(Budget, {"user_id__in": users, "period_type": "month", "category_id__isnull": False},
                                order_by="id", db=db)

            # 3. 只算某一本帳：要是我加入的
            group_id = None
            if groupId and groupId != "all":
                group_id = int(groupId) if groupId.isdigit() else 0
                if group_id not in groups:
                    raise errors.forbidden("你不在這本帳裡")

            # 4. 已花多少：這個月、這個人、這個分類的支出，從明細現算
            spent = {}
            if budgets:
                where = {"user_id__in": {b.user_id for b in budgets}, "kind": "expense",
                         "occurred_on__between": (start, end)}
                if group_id is not None:
                    where["group_id"] = group_id
                for t in crud.find(Transaction, where, fields=("user_id", "category_id", "amount"), db=db):
                    key = (t["user_id"], t["category_id"])
                    spent[key] = money.add(spent.get(key), t["amount"])

            # 5. 配上已花、有沒有超過、用掉幾成；用掉比例高的排前面
            out = []
            for b in budgets:
                used = spent.get((b.user_id, b.category_id), money.ZERO)
                out.append({
                    "user": str(b.user_id),
                    "period": b.period_type,
                    "cat": str(b.category_id),
                    "limit": b.limit_amount,
                    "used": used,
                    "over": used > b.limit_amount,
                    "pct": money.quantize(money.ratio(used, b.limit_amount), 4),
                })
            out.sort(key=lambda row: row["pct"], reverse=True)
            return {"budgets": out}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 GET /api/budgets
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               什麼都不帶            → 200，自己（與照看的人）的預算都在，used 跟明細加起來一樣
               groupId=某一本帳      → used 只算那本帳的
               groupId=我沒加入的帳  → 403
        5. 前端改成連你的後端（frontend/index.html 的 api-base），總覽的預算卡，超過的要標紅
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "list_budgets and u4f60" -v，要全部通過
           （u4f60 是標籤「你的」的跳脫碼。pytest 會把中文標籤轉成跳脫碼，
            -k 直接打中文比不到任何測試，會印出 0 selected）
    """
    raise not_ready("GET /api/budgets", OWNER)


@router.put("/budgets", summary="設定預算（limit 0 = 拿掉）")
@block_admin
@stub
def set_budget(body: BudgetIn, me: User, db: Session = Depends(get_db)):
    """設定預算（limit 0 = 拿掉）

    PUT /api/budgets

    【這支做什麼】
        設定「我自己」某個支出分類的預算。limit 是 0 表示拿掉這個分類的預算（刪掉那一列，不是存一個 0）。
        同一個人、分類、週期只有一列：有就改、沒有就新增（所以用 PUT：送幾次結果都一樣）。
        ⚠️ 只設自己的，主體不收 userId——預算、存款目標都是本人的決定。

    【前端怎麼打】
        frontend/js/api.js 的 API.setBudget({ cat, limit, period })
        個人資料頁「每月預算」，改完離開欄位就存。toast 會用回應的 catName 與 deleted。

    【誰能打】
        登入、沒被停權、不是平台管理員。上面的 @block_admin 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【請求主體】body 是 BudgetIn（app/schemas/stats.py）
        欄位    型別  必填  說明
        cat     字串  是    支出分類的 id（系統的或我們家的）。不收 null（這一版不做總額預算）
        limit   數字  是    0 以上；0 = 拿掉。負數 FastAPI 自動回 422
        period  字串  否    month（預設）／year。其他值 FastAPI 自動回 422
        範例：{"cat": "1", "limit": 8000, "period": "month"}

    【成功回應】狀態碼 200
        設定：{"user": "3", "period": "month", "cat": "1", "catName": "餐飲", "limit": 8000}
        拿掉：{"user": "3", "period": "month", "cat": "1", "catName": "餐飲", "limit": 0, "deleted": true}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                               detail
        400     分類不存在、是收入分類、或是別人家的   預算只能設在支出分類
        422     limit 小於 0、period 不是 month／year  （FastAPI 自動回）

    【會用到的資料表】
        表          讀／寫  用來做什麼
        categories  讀      分類存在、是支出、是系統的或我們家的
        budgets     寫      新增、修改、或刪掉那一列

    【每一步用的工具與資料庫方法】
        步驟    呼叫                               做什麼
        1 分類  crud.get(Category, where={"id": …, "kind": "expense", "or": [系統的, 我們家的]}, db=db)  條件一次寫完，找不到就是不行
        3 拿掉  crud.remove(Budget, where, db=db)  刪掉符合的那一列（沒有也不會出錯）
        4 設定  crud.save(Budget, {"limit_amount": …}, where=where, upsert=True, db=db)  有符合 where 的就改，沒有就用 where 的值＋這些欄位新增
                money.quantize(body.limit)         8000 → Decimal("8000.00")
                db.commit()                        寫進去

    【寫法步驟】
        1. 分類要存在、是支出、是系統的或我們家的（400）
        2. 條件是（我、這個分類、這個週期）
        3. limit 是 0：刪掉那一列，回 deleted: true
        4. 不是 0：upsert（有就改、沒有就新增），db.commit()，回傳設定

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, Query
            from sqlalchemy.orm import Session

            from app.guards import block_admin, visible_scope
            from app.models import Budget, Category, Group, GroupMember, SavingsGoal, Transaction, User
            from app.routers._stub import not_ready, stub
            from app.schemas.stats import BudgetIn, SavingsGoalIn
            from app.toolkit import crud, errors, money, period, roles
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 只能設在支出分類（系統的或我們家的）
            category_id = int(body.cat) if body.cat.isdigit() else 0
            category = crud.get(Category, where={
                "id": category_id,
                "kind": "expense",
                "or": [{"family_id__isnull": True}, {"family_id": me.family_id}],
            }, db=db)
            if category is None:
                raise errors.bad_request("預算只能設在支出分類")

            # 2. 同一個人、分類、週期只有一列
            where = {"user_id": me.id, "category_id": category.id, "period_type": body.period}
            out = {"user": str(me.id), "period": body.period, "cat": str(category.id), "catName": category.name}

            # 3. limit 0 = 拿掉這個分類的預算（刪掉那一列，不是存一個 0）
            if body.limit == 0:
                crud.remove(Budget, where, db=db)
                db.commit()
                return {**out, "limit": 0, "deleted": True}

            # 4. 有就改、沒有就新增
            crud.save(Budget, {"limit_amount": money.quantize(body.limit), "family_id": me.family_id,
                               "created_by": me.id}, where=where, upsert=True, db=db)
            db.commit()
            return {**out, "limit": body.limit}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 PUT /api/budgets
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               {"cat": 餐飲的 id, "limit": 8000}  → 200；再送一次 9000，資料庫還是只有一列、變成 9000
               {"cat": 餐飲的 id, "limit": 0}     → 200，deleted: true，那一列不見
               {"cat": 薪資的 id, "limit": 100}   → 400
               {"cat": 餐飲的 id, "limit": -1}    → 422
        5. 打 GET /api/budgets → 看得到剛設的預算
        6. 前端改成連你的後端（frontend/index.html 的 api-base），個人資料頁改一個分類的預算，離開欄位就跳「已儲存」的提示
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "set_budget and u4f60" -v，要全部通過
           （u4f60 是標籤「你的」的跳脫碼。pytest 會把中文標籤轉成跳脫碼，
            -k 直接打中文比不到任何測試，會印出 0 selected）
    """
    raise not_ready("PUT /api/budgets", OWNER)


@router.put("/savings-goal", summary="設定每月存款目標")
@block_admin
@stub
def set_savings_goal(body: SavingsGoalIn, me: User, db: Session = Depends(get_db)):
    """設定每月存款目標

    PUT /api/savings-goal

    【這支做什麼】
        設定「我自己」每月想存多少錢；帶 groupId 就是那一本帳自己的目標（跟整體目標並存）。
        ⚠️ 只有本人能設：存多少錢是自己的決定，家長也不能代設（roles.require_set_goal）。
        ⚠️ 改動不覆蓋舊的：一個月一列（period_key），這個月改好幾次就改這個月那一列。
           不然十月回頭看九月時，會拿現在的目標去評斷過去的表現。
        讀的時候拿「最新的一列」就是目前的目標。

    【前端怎麼打】
        frontend/js/api.js 的 API.setSavingsGoal(userId, goal, groupId)
        註冊後個人化設定的第一步、個人資料頁的存錢計畫（整體，toast 讀 name）、帳本頁每本的月目標（toast 讀 groupName）。

    【誰能打】
        登入、沒被停權、不是平台管理員。上面的 @block_admin 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【請求主體】body 是 SavingsGoalIn（app/schemas/stats.py）
        欄位     型別  必填  說明
        userId   字串  否    要設誰的。不帶或是自己都可以；是別人回 403
        goal     數字  是    每月想存多少，0 以上（負數 FastAPI 自動回 422）
        groupId  字串  否    帶了就是那本帳的目標，要是我加入、沒移除的帳本
        範例：{"userId": "3", "goal": 20000, "groupId": null}

    【成功回應】狀態碼 200
        整體：{"id": "3", "name": "王大明", "userId": "3", "goal": 20000, "groupId": null, "savingsGoal": 20000}
        帳本：{"id": "3", "name": "王大明", "userId": "3", "goal": 5000, "groupId": "6", "groupName": "旅遊基金"}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                              detail
        403     userId 不是自己                       存款目標只有本人可以設定
        403     groupId 是我沒加入、或已經移除的帳本  你不在這本帳裡
        422     goal 小於 0                           （FastAPI 自動回）

    【會用到的資料表】
        表                     讀／寫  用來做什麼
        group_members、groups  讀      帶 groupId 時：我在不在裡面、有沒有被移除
        savings_goals          寫      這個月那一列：有就改、沒有就新增

    【每一步用的工具與資料庫方法】
        步驟    呼叫                                                           做什麼
        1 本人  roles.require_set_goal(str(me.id), body.userId or str(me.id))  不是本人丟 PermissionError（兩邊都用字串比）
        2 帳本  crud.exists(GroupMember, {"group_id": …, "user_id": me.id}, db=db)  我在不在裡面
                crud.get(Group, where={"id": …, "removed_at__isnull": True}, db=db)  移除的當作不存在
        3 寫入  crud.save(SavingsGoal, {"goal_amount": …}, where={"user_id", "group_id", "period_key": 這個月}, upsert=True, db=db)  一個月一列：這個月改好幾次只改同一列，下個月再改就是新的一列
                db.commit()                                                    寫進去
        ⚠️ toolkit 的 Forbidden 是 PermissionError 的一種，用 except PermissionError 接。

    【寫法步驟】
        1. 不是本人 → 403
        2. 有 groupId：要是我加入、沒移除的帳本（403）
        3. 這個月（台灣時間）的那一列：upsert 成新的目標，db.commit()
        4. 回傳：整體的帶 name 與 savingsGoal，帳本的帶 groupId 與 groupName

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, Query
            from sqlalchemy.orm import Session

            from app.guards import block_admin, visible_scope
            from app.models import Budget, Category, Group, GroupMember, SavingsGoal, Transaction, User
            from app.routers._stub import not_ready, stub
            from app.schemas.stats import BudgetIn, SavingsGoalIn
            from app.toolkit import crud, errors, money, period, roles
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 只有本人能設（userId 不帶 = 自己）
            try:
                roles.require_set_goal(str(me.id), body.userId or str(me.id))
            except PermissionError as exc:
                raise errors.forbidden(str(exc)) from None

            # 2. 帶了 groupId：那本帳的目標，要是我加入、沒移除的帳本
            group = None
            if body.groupId:
                group_id = int(body.groupId) if body.groupId.isdigit() else 0
                if crud.exists(GroupMember, {"group_id": group_id, "user_id": me.id}, db=db):
                    group = crud.get(Group, where={"id": group_id, "removed_at__isnull": True}, db=db)
                if group is None:
                    raise errors.forbidden("你不在這本帳裡")

            # 3. 一個月一列：這個月改好幾次只改同一列，以前月份的不動
            this_month = period.current_month(datetime.now(timezone(timedelta(hours=8))).date())
            crud.save(SavingsGoal, {"goal_amount": money.quantize(body.goal), "created_by": me.id},
                      where={"user_id": me.id, "group_id": group.id if group else None, "period_key": this_month},
                      upsert=True, db=db)
            db.commit()

            # 4. 回傳：整體目標前端讀 name，帳本目標讀 groupName
            out = {"id": str(me.id), "name": me.display_name, "userId": str(me.id), "goal": body.goal}
            if group:
                out.update({"groupId": str(group.id), "groupName": group.name})
            else:
                out.update({"groupId": None, "savingsGoal": body.goal})
            return out

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 PUT /api/savings-goal
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               {"goal": 20000}                          → 200；再送一次 25000，savings_goals 這個月還是只有一列
               {"userId": 別人的 id, "goal": 1}         → 403
               {"goal": 5000, "groupId": 我加入的帳本}  → 200，有 groupName
               {"goal": -1}                             → 422
        5. 打 GET /api/auth/me → user.savingsGoal 是剛設的整體目標
        6. 前端改成連你的後端（frontend/index.html 的 api-base），個人資料頁改存款目標，總覽的「還可以花」要跟著變
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "set_savings_goal and u4f60" -v，要全部通過
           （u4f60 是標籤「你的」的跳脫碼。pytest 會把中文標籤轉成跳脫碼，
            -k 直接打中文比不到任何測試，會印出 0 selected）
    """
    raise not_ready("PUT /api/savings-goal", OWNER)


@router.get("/savings-goals", summary="整體＋各帳本的存款目標")
@block_admin
@stub
def list_savings_goals(me: User, db: Session = Depends(get_db)):
    """整體＋各帳本的存款目標

    GET /api/savings-goals

    【這支做什麼】
        列出我的每月存款目標：第一列是整體（groupId null），後面是我加入、還在用的每一本帳。
        沒設過的是 0。每一個都拿「最新的一列」。

    【前端怎麼打】
        frontend/js/api.js 的 API.savingsGoals()
        帳本頁每一本的月目標輸入框、存錢計畫。前端檢查回應裡一定要有 goals。

    【誰能打】
        登入、沒被停權、不是平台管理員。上面的 @block_admin 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【請求參數】沒有

    【成功回應】狀態碼 200
        {"goals": [
           {"groupId": null, "groupName": "整體", "goal": 20000},
           {"groupId": "6", "groupName": "旅遊基金", "goal": 5000}
         ]}

    【錯誤回應】
        只有守衛的 401／403，這支本身不會出錯。

    【會用到的資料表】
        表                     讀／寫  用來做什麼
        savings_goals          讀      我所有的目標（每本帳留最新的一列）
        group_members、groups  讀      我加入、沒封存、沒移除的帳本

    【每一步用的工具與資料庫方法】
        步驟      呼叫  做什麼
        1 最新的  crud.find(SavingsGoal, {"user_id": me.id}, order_by="id", db=db)  由舊到新放進 dict：latest[帳本 id] = 金額，後面的蓋掉前面的；整體的鍵是 None
        2 帳本    crud.find(GroupMember, {"user_id": me.id}, fields="group_id", db=db)  我加入的帳本 id
                  crud.find(Group, {"id__in": …, "removed_at__isnull": True, "archived_at__isnull": True}, order_by="id", db=db)  還在用的

    【寫法步驟】
        1. 我所有的目標由舊到新跑一遍，留下每本帳（含整體）最新的金額
        2. 查我加入、還在用的帳本
        3. 第一列放整體，後面一本一列，回傳
        ⚠️ 只讀不寫，不用 db.commit()。

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, Query
            from sqlalchemy.orm import Session

            from app.guards import block_admin, visible_scope
            from app.models import Budget, Category, Group, GroupMember, SavingsGoal, Transaction, User
            from app.routers._stub import not_ready, stub
            from app.schemas.stats import BudgetIn, SavingsGoalIn
            from app.toolkit import crud, errors, money, period, roles
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 我的每一筆目標由舊到新：後面的蓋掉前面的，每本帳留下最新的（整體的鍵是 None）
            latest = {}
            for row in crud.find(SavingsGoal, {"user_id": me.id}, order_by="id", db=db):
                latest[row.group_id] = row.goal_amount

            # 2. 我加入、還在用的帳本
            my_groups = crud.find(GroupMember, {"user_id": me.id}, fields="group_id", db=db)
            groups = crud.find(Group, {"id__in": my_groups, "removed_at__isnull": True, "archived_at__isnull": True},
                               order_by="id", db=db)

            # 3. 第一列是整體，後面一本一列
            goals = [{"groupId": None, "groupName": "整體", "goal": latest.get(None, 0)}]
            for g in groups:
                goals.append({"groupId": str(g.id), "groupName": g.name, "goal": latest.get(g.id, 0)})
            return {"goals": goals}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 GET /api/savings-goals
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               什麼都沒設過      → 整體 0，每本帳都是 0
               設過兩次整體目標  → 整體是後來那個
        5. 封存一本帳 → 那本帳不在清單裡
        6. 前端改成連你的後端（frontend/index.html 的 api-base），帳本頁每一本的月目標要跟這支一致
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "list_savings_goals and u4f60" -v，要全部通過
           （u4f60 是標籤「你的」的跳脫碼。pytest 會把中文標籤轉成跳脫碼，
            -k 直接打中文比不到任何測試，會印出 0 selected）
    """
    raise not_ready("GET /api/savings-goals", OWNER)
