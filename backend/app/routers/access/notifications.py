"""
通知。

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

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.guards import block_admin, own
from app.models import AlertRule, Group, Notification, SavingsGoal, Transaction, User
from app.routers._stub import not_ready, stub
from app.schemas.family import ReadAllIn, ReadOneIn
from app.toolkit import alerts, crud, errors, money, period
from app.toolkit.db import get_db

router = APIRouter(tags=["通知"])
OWNER = "成員4"


@router.get("/notifications", summary="通知清單（輪詢）")
@block_admin
@stub
def list_notifications(
    me: User,
    since: str | None = None,
    unreadOnly: bool = False,
    db: Session = Depends(get_db),
):
    """通知清單（輪詢）

    GET /api/notifications

    【這支做什麼】
        右上角通知鈴鐺每 20 秒來拿一次（輪詢）。回傳：比 since 新的通知（由新到舊）、總未讀數、最新的 id。
        通知有三種 type：
            ward_transaction    我照看的人記了一筆（記帳的路由寫進來的）
            group_transaction   我開了通知的帳本裡有人記了一筆（記帳的路由寫進來的）
            budget_alert        我自己的支出跨過了我設的提醒門檻（就在這支裡檢查、寫進來）
        ⚠️ 為什麼提醒在這裡檢查：提醒只發給設門檻的人自己，而他每 20 秒就會來拿一次通知；
           在這裡一次看完他的所有門檻，記帳的三支路由就不用各自再算一次。
           同一個門檻一個月只響一次，靠 alert_rules.fired_period 擋。

    【前端怎麼打】
        frontend/js/notify.js 透過 frontend/js/api.js 的 API.notifications({ since })
        登入後每 20 秒一次；maxId 變了就叮一聲、跳出通知；maxId 存起來，下次當 since 傳回來。
        前端檢查回應裡一定要有 notifications 與 unread。actorName、catName 前端會自己補。

    【誰能打】
        登入、沒被停權、不是平台管理員。上面的 @block_admin 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【查詢參數】
        參數        型別         說明
        since       字串         上次拿到的 maxId。只回 id 比它大的（嚴格大於）；第一次不帶
        unreadOnly  true／false  只要未讀的，預設 false

    【成功回應】狀態碼 200
        {"notifications": [
           {"id": "12", "type": "ward_transaction", "actorId": "5", "txId": "40", "amount": 320, "cat": "1",
            "merchant": "全家", "groupId": "2", "reason": "guardian",
            "createdAt": "2026-09-11T13:20:05Z", "readAt": null},
           {"id": "11", "type": "budget_alert", "actorId": null, "percent": 85, "reached": 103,
            "groupId": null, "groupName": "整體", "spent": 12800, "allowance": 12400,
            "createdAt": "2026-09-11T10:04:00Z", "readAt": null}
         ],
         "unread": 3, "maxId": "12"}
        · 由新到舊（最新的在 [0]），一次最多 20 則
        · ⚠️ unread 是「全部」的未讀數，不是這一批裡的：用這一批算的話，帶 since 回 0 則時紅點會被清掉
        · ⚠️ maxId 是「我所有通知裡最大的 id」，要另外查，不要拿這一批的最後一個（那是最舊的）
        · ⚠️ since 是嚴格大於（>）：寫成 >= 的話，每 20 秒同一則會重送一次
        · createdAt、readAt 用 UTC 的 ISO 8601（結尾 Z），前端自己轉當地時間
        · budget_alert：percent 是設的門檻、reached 是實際用掉幾成——兩個都要送，不然讀起來像系統算錯

    【錯誤回應】
        只有守衛的 401／403，這支本身不會出錯。

    【會用到的資料表】
        表             讀／寫  用來做什麼
        alert_rules    讀＋寫  我開著、這個月還沒響的門檻；響了記 fired_period
        transactions   讀      我這個月的收支（算用掉幾成）；記帳類通知的金額、分類、店家
        savings_goals  讀      我的存款目標（整體與各帳本）
        groups         讀      門檻指到的帳本名字
        notifications  讀＋寫  寫 budget_alert；查我的通知、未讀數、最大 id

    【每一步用的工具與資料庫方法】
        步驟      呼叫                                                            做什麼
        1 門檻    crud.find(AlertRule, {…, "enabled": True, "or": [{"fired_period__isnull": True}, {"fired_period__ne": 這個月}]}, db=db)  開著、這個月還沒響過的（NULL 要另外寫，因為 SQL 的 != 不會選到 NULL）
                  money.add(*[…])                                                 收入、支出各自加起來
                  alerts.usage_percent(支出, 可支配上限)                          用掉幾成，無條件捨去；上限 ≤ 0 也不會爆
                  alerts.should_fire(門檻, 0, 用掉幾成, fired_period, 這個月)     用掉的已經到門檻、而且這個月還沒響 → True（before 傳 0：沒響過的都當作從 0 開始）
                  crud.save(Notification, {…"type": "budget_alert"…}, db=db)      transaction_id 留空（同一筆帳可能同時跨過好幾個門檻）
                  crud.save(AlertRule, {"id": …, "fired_period": 這個月}, db=db)  記住這個月響過了
        2 通知    crud.find(Notification, {"recipient_id": me.id, "id__gt": since}, order_by="-id", limit=20, db=db)  我的、比 since 新的、由新到舊
        3 總數    crud.count(Notification, {"recipient_id": me.id, "read_at__isnull": True}, db=db)  全部未讀
                  crud.get(Notification, where={"recipient_id": me.id}, fields="id", order_by="-id", db=db)  我最大的通知 id
        4 補資料  crud.find(Transaction, {"id__in": […]}, db=db)                  這一批記帳類通知指到的那幾筆
                  created.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")  轉成 UTC、結尾寫 Z
        ⚠️ 查詢一律 WHERE recipient_id = 我，不要用監管關係現算：監管解除之後，舊通知還是屬於當時的收件人。

    【寫法步驟】
        1. 提醒：查我開著、這個月還沒響的門檻；有的話算出我這個月（整體或那本帳）用掉幾成，
           到了門檻就寫一則 budget_alert、記 fired_period；最後 db.commit()
        2. 查我的通知：比 since 新的、unreadOnly 就只要未讀的，由新到舊最多 20 則
        3. 另外查全部未讀數、我最大的通知 id
        4. 記帳類的補上那一筆的金額、分類、店家、帳本；提醒類把 payload_json 攤開
        5. 回傳 {notifications, unread, maxId}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, Query
            from sqlalchemy.orm import Session

            from app.guards import block_admin, own
            from app.models import AlertRule, Group, Notification, SavingsGoal, Transaction, User
            from app.routers._stub import not_ready, stub
            from app.schemas.family import ReadAllIn, ReadOneIn
            from app.toolkit import alerts, crud, errors, money, period
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 我的提醒門檻：這個月跨過、還沒響過的，寫一則 budget_alert
            this_month = period.current_month(datetime.now(timezone(timedelta(hours=8))).date())
            rules = crud.find(AlertRule, {
                "user_id": me.id,
                "enabled": True,
                "or": [{"fired_period__isnull": True}, {"fired_period__ne": this_month}],
            }, db=db)
            if rules:
                start, end = period.month_range(this_month)
                mine = crud.find(Transaction, {"user_id": me.id, "kind__in": ["income", "expense"],
                                               "occurred_on__between": (start, end)},
                                 fields=("group_id", "kind", "amount"), db=db)
                goals = {}
                for g in crud.find(SavingsGoal, {"user_id": me.id}, order_by="id", db=db):
                    goals[g.group_id] = g.goal_amount                    # 整體目標的鍵是 None
                names = {g.id: g.name for g in crud.find(Group, {"id__in": {r.group_id for r in rules if r.group_id}}, db=db)}
                for rule in rules:
                    rows = [t for t in mine if rule.group_id is None or t["group_id"] == rule.group_id]
                    income = money.add(*[t["amount"] for t in rows if t["kind"] == "income"])
                    spent = money.add(*[t["amount"] for t in rows if t["kind"] == "expense"])
                    allowance = income - goals.get(rule.group_id, money.ZERO)
                    reached = alerts.usage_percent(spent, allowance)
                    if not alerts.should_fire(rule.percent, 0, reached, rule.fired_period, this_month):
                        continue
                    crud.save(Notification, {"recipient_id": me.id, "type": "budget_alert", "payload_json": {
                        "percent": rule.percent,
                        "reached": reached,
                        "groupId": str(rule.group_id) if rule.group_id else None,
                        "groupName": names.get(rule.group_id, "") if rule.group_id else "整體",
                        "spent": float(spent),
                        "allowance": float(allowance),
                    }}, db=db)
                    crud.save(AlertRule, {"id": rule.id, "fired_period": this_month}, db=db)
                db.commit()

            # 2. 我的通知：比 since 新的，由新到舊，一次最多 20 則
            where = {"recipient_id": me.id}
            if since:
                where["id__gt"] = int(since) if since.isdigit() else 0
            if unreadOnly:
                where["read_at__isnull"] = True
            rows = crud.find(Notification, where, order_by="-id", limit=20, db=db)

            # 3. 未讀總數、最大的 id 另外查（不受 since 影響）
            unread = crud.count(Notification, {"recipient_id": me.id, "read_at__isnull": True}, db=db)
            newest = crud.get(Notification, where={"recipient_id": me.id}, fields="id", order_by="-id", db=db)

            # 4. 記帳類補上那一筆的金額、分類、店家；提醒類把 payload 攤開
            tx_ids = [n.transaction_id for n in rows if n.transaction_id]
            txs = {t.id: t for t in crud.find(Transaction, {"id__in": tx_ids}, db=db)}
            out = []
            for n in rows:
                stamps = []
                for value in (n.created_at, n.read_at):
                    if value is not None and value.tzinfo is None:
                        value = value.replace(tzinfo=timezone.utc)          # SQLite 讀回來沒有時區
                    stamps.append(value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if value else None)
                item = {
                    "id": str(n.id),
                    "type": n.type,
                    "actorId": str(n.actor_id) if n.actor_id else None,
                    "createdAt": stamps[0],
                    "readAt": stamps[1],
                }
                item.update(n.payload_json or {})
                t = txs.get(n.transaction_id)
                if t is not None:
                    item.update({"txId": str(t.id), "amount": t.amount, "cat": str(t.category_id),
                                 "merchant": t.merchant or "", "groupId": str(t.group_id)})
                out.append(item)

            # 5. 回傳
            return {"notifications": out, "unread": unread, "maxId": str(newest) if newest else None}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 GET /api/notifications
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               第一次不帶 since                        → 最新的 20 則，maxId 是最大的 id
               since 帶上一次的 maxId、中間沒有新通知  → notifications 是 []，但 unread 不變
               設一個 1% 的門檻、記一筆支出後再打      → 多一則 budget_alert；再打一次不會再多
        5. 照看的孩子記一筆 → 家長下一次輪詢多一則 ward_transaction，txId 是那一筆
        6. 前端改成連你的後端（frontend/index.html 的 api-base），登入家長帳號，孩子記一筆之後 20 秒內鈴鐺叮一聲、紅點加一
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "list_notifications and 你的"，要全部通過
    """
    raise not_ready("GET /api/notifications", OWNER)


@router.patch("/notifications/{nid}", summary="一則標記已讀")
@stub
def read_notification(
    body: ReadOneIn,
    row=Depends(own(Notification, "nid", "recipient_id")),
    db: Session = Depends(get_db),
):
    """一則標記已讀

    PATCH /api/notifications/{nid}

    【這支做什麼】
        把一則通知標成已讀（或改回未讀）。只能改自己的通知（recipient_id = 我）。

    【前端怎麼打】
        frontend/js/api.js 的 API.readNotification(id)，主體固定是 {"read": true}
        通知清單點某一則時呼叫。

    【誰能打】
        登入、沒被停權，而且這一筆是自己的。參數 row=Depends(own(Notification, "nid", "recipient_id")) 已經擋好了：
            沒登入 → 401；被停權 → 403
            {nid} 不是數字、或找不到這一筆 → 404「找不到這筆資料」
            這一筆的 recipient_id 不是我 → 403「這是別人的資料，你只能檢視」
        所以函式裡不用再檢查。row 就是那一筆（Notification 物件），直接拿來用。

    【請求主體】body 是 ReadOneIn（app/schemas/family.py）
        欄位  型別         必填  說明
        read  true／false  否    預設 true；false = 改回未讀
        範例：{"read": true}

    【成功回應】狀態碼 200
        {"id": "12", "readAt": "2026-09-11T13:25:00Z"}
        · 已經讀過的再標一次，保留原本的時間

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候    detail
        403     別人的通知  這是別人的資料，你只能檢視（守衛回）
        404     找不到      找不到這筆資料（守衛回）

    【會用到的資料表】
        表             讀／寫  用來做什麼
        notifications  寫      設 read_at

    【每一步用的工具與資料庫方法】
        步驟    呼叫                                                          做什麼
        1 時間  row.read_at or datetime.now(timezone.utc)                     讀過的保留原本的時間
        2 寫回  crud.save(Notification, {"id": row.id, "read_at": …}, db=db)  帶主鍵 = 改那一則
                db.commit()                                                   寫進去

    【寫法步驟】
        1. read 是 true：read_at = 原本的（有的話）或現在；false：read_at = None
        2. 寫回、db.commit()
        3. 回 {"id", "readAt"}（UTC、結尾 Z）

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, Query
            from sqlalchemy.orm import Session

            from app.guards import block_admin, own
            from app.models import AlertRule, Group, Notification, SavingsGoal, Transaction, User
            from app.routers._stub import not_ready, stub
            from app.schemas.family import ReadAllIn, ReadOneIn
            from app.toolkit import alerts, crud, errors, money, period
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 標已讀（讀過的保留原本的時間）；read: false 是改回未讀
            read_at = (row.read_at or datetime.now(timezone.utc)) if body.read else None
            crud.save(Notification, {"id": row.id, "read_at": read_at}, db=db)
            db.commit()

            # 2. 回傳（UTC、結尾 Z）
            if read_at is not None and read_at.tzinfo is None:
                read_at = read_at.replace(tzinfo=timezone.utc)              # SQLite 讀回來沒有時區
            stamp = read_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if read_at else None
            return {"id": str(row.id), "readAt": stamp}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 PATCH /api/notifications/{nid}
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               {"read": true}   → 200，readAt 有值
               再送一次         → readAt 不變
               {"read": false}  → readAt 是 null
               別人的通知       → 403
        5. 前端改成連你的後端（frontend/index.html 的 api-base），點一則通知，那一則不再是粗體、紅點少一
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "read_notification and 你的"，要全部通過
    """
    raise not_ready("PATCH /api/notifications/{nid}", OWNER)


@router.patch("/notifications", summary="整批標記已讀")
@block_admin
@stub
def read_notifications(body: ReadAllIn, me: User, db: Session = Depends(get_db)):
    """整批標記已讀

    PATCH /api/notifications

    【這支做什麼】
        「全部已讀」：把我的未讀通知標成已讀，但只標到 readUntil 那一則為止。
        ⚠️ 一定要帶 readUntil，不要做成「全部」：按下去的那一瞬間可能正好有新通知進來，
           全部標掉的話，那則使用者根本沒看到的通知就永遠不會被發現了。

    【前端怎麼打】
        frontend/js/api.js 的 API.readNotifications(untilId)
        通知清單的「全部已讀」，untilId 是畫面上最新的那一則。

    【誰能打】
        登入、沒被停權、不是平台管理員。上面的 @block_admin 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【請求主體】body 是 ReadAllIn（app/schemas/family.py）
        欄位       型別  必填                                   說明
        readUntil  字串  是（schema 上可以不帶，但這支一定要）  按下去當時畫面上最新的那一則的 id
        範例：{"readUntil": "12"}

    【成功回應】狀態碼 200
        {"updated": 3, "unread": 0}
        · updated = 這次標了幾則；unread = 標完之後還剩幾則未讀（之後才進來的還是未讀）

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候        detail
        400     沒帶 readUntil  要帶 readUntil（按下去當時最新的那一則）

    【會用到的資料表】
        表             讀／寫  用來做什麼
        notifications  寫      我的、還沒讀、id 不超過 readUntil 的，一次設 read_at

    【每一步用的工具與資料庫方法】
        步驟    呼叫         做什麼
        2 標記  crud.save(Notification, {"read_at": now}, where={"recipient_id": me.id, "read_at__isnull": True, "id__lte": until}, db=db)  有 where = 一次改很多列，回傳改了幾列
                db.commit()  寫進去
        3 剩下  crud.count(Notification, {"recipient_id": me.id, "read_at__isnull": True}, db=db)  還剩幾則未讀

    【寫法步驟】
        1. 沒帶 readUntil → 400
        2. 我的、未讀、id ≤ readUntil 的一次標已讀，db.commit()
        3. 查剩下的未讀數，回 {updated, unread}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, Query
            from sqlalchemy.orm import Session

            from app.guards import block_admin, own
            from app.models import AlertRule, Group, Notification, SavingsGoal, Transaction, User
            from app.routers._stub import not_ready, stub
            from app.schemas.family import ReadAllIn, ReadOneIn
            from app.toolkit import alerts, crud, errors, money, period
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 一定要帶 readUntil：只標到使用者按下去當時看得到的那一則
            if not body.readUntil:
                raise errors.bad_request("要帶 readUntil（按下去當時最新的那一則）")
            until = int(body.readUntil) if body.readUntil.isdigit() else 0

            # 2. 我的、還沒讀、不比 readUntil 新的，一次標掉
            updated = crud.save(Notification, {"read_at": datetime.now(timezone.utc)},
                                where={"recipient_id": me.id, "read_at__isnull": True, "id__lte": until}, db=db)
            db.commit()

            # 3. 剩下的未讀（之後才進來的還是未讀）
            unread = crud.count(Notification, {"recipient_id": me.id, "read_at__isnull": True}, db=db)
            return {"updated": updated, "unread": unread}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 PATCH /api/notifications
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               {"readUntil": 目前最大的 id}  → 200，unread 變 0
               {}                            → 400
               {"readUntil": 比較舊的 id}    → 只有那之前的變已讀，之後的還是未讀
        5. 前端改成連你的後端（frontend/index.html 的 api-base），通知清單按「全部已讀」，紅點消失
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "read_notifications and 你的"，要全部通過
    """
    raise not_ready("PATCH /api/notifications", OWNER)
