"""
階段性提醒門檻。

負責人：成員3（數字）　✦ 分支：m3-analytics

===========================================================================
現在每一支都回 501（後端還沒做這一支），**守衛與主體模型已經接好**
===========================================================================
要做的事：把函式裡的 `raise not_ready(...)` 換成真的實作，然後拿掉 `@stub`。
* 誰能打這一支：已經由守衛擋好（看 @xxx_required 或 Depends(...)），不用自己再判斷身分
* 前端送什麼、要回什麼：docs/02-前後端串接契約.md 同名的章節
* 增刪改查：app/toolkit/crud.py（find／get／save／remove／to_dict）
* 規則（誰可以、什麼時候不行）：app/toolkit/ 對應的模組，函式說明裡寫了拿來怎麼用
* 回傳的 id 要轉成字串（crud.to_dict 預設就會轉）

`python -m app.ownership` 會列出每個人還剩幾支（有 @stub 的算還沒做）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.guards import block_admin, own
from app.models import AlertRule, User
from app.routers._stub import not_ready, stub
from app.schemas.stats import AlertIn, AlertPatchIn
from app.toolkit.db import get_db

router = APIRouter(tags=["提醒"])
OWNER = "成員3"


@router.get("/alerts", summary="我設的提醒門檻")
@block_admin
@stub
def list_alerts(me: User, db: Session = Depends(get_db)):
    """我設的提醒門檻

    GET /api/alerts

    【這支做什麼】
        列出我自己設的階段性提醒門檻（例如 60%／85%／100%）。
        百分比算的是「支出佔可支配上限的幾成」，可支配上限 = 本月收入 − 每月存款目標。
        跨過門檻時發通知的是 GET /api/notifications（提醒只發給設門檻的人自己，他每 20 秒會來拿一次通知）。

    【前端怎麼打】
        frontend/js/api.js 的 API.alerts()
        個人資料頁「階段性提醒」。前端檢查回應裡一定要有 alerts。

    【誰能打】
        登入、沒被停權、不是平台管理員。上面的 @block_admin 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【請求參數】沒有

    【成功回應】狀態碼 200
        {"alerts": [
           {"id": "1", "percent": 60, "groupId": null, "groupName": "整體", "enabled": true, "firedPeriod": null},
           {"id": "2", "percent": 85, "groupId": "6", "groupName": "旅遊基金", "enabled": false, "firedPeriod": "2026-09"}
         ]}
        · 百分比由小到大
        · groupId 是 null = 針對整體目標；有值 = 針對那本帳自己的目標
        · firedPeriod = 上次響是哪個月（同一個門檻一個月只響一次）

    【錯誤回應】
        只有守衛的 401／403，這支本身不會出錯。

    【會用到的資料表】
        表           讀／寫  用來做什麼
        alert_rules  讀      我的門檻
        groups       讀      針對帳本的門檻，帳本叫什麼名字

    【每一步用的工具與資料庫方法】
        步驟      呼叫                                      做什麼
        1 門檻    crud.find(AlertRule, {"user_id": me.id}, order_by=("percent", "id"), db=db)  先照百分比、再照建立先後
        2 帳本名  crud.find(Group, {"id__in": {…}}, db=db)  一次查完，做成 {id: 名字}

    【寫法步驟】
        1. 查我的門檻，百分比由小到大
        2. 一次查出這些門檻指到的帳本名字
        3. 一筆一筆轉成前端要的樣子（groupId 是 None 的，groupName 寫「整體」）
        ⚠️ 只讀不寫，不用 db.commit()。

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：把檔案最上面的 import 換成這樣（這個檔案每一支的第一步都一樣，換過一次就好）

            from fastapi import APIRouter, Depends
            from sqlalchemy.orm import Session

            from app.guards import block_admin, own
            from app.models import AlertRule, Group, GroupMember, User
            from app.routers._stub import not_ready, stub
            from app.schemas.stats import AlertIn, AlertPatchIn
            from app.toolkit import alerts, crud, errors
            from app.toolkit.db import get_db

        第二步：把整個 list_alerts（從 @router.get 到 raise not_ready 那行）換成這段。
        注意 @stub 拿掉了；這段說明字串可以留著。

            @router.get("/alerts", summary="我設的提醒門檻")
            @block_admin
            def list_alerts(me: User, db: Session = Depends(get_db)):
                # 1. 我的門檻，百分比由小到大
                rows = crud.find(AlertRule, {"user_id": me.id}, order_by=("percent", "id"), db=db)

                # 2. 針對帳本的門檻，一次查出帳本名字
                group_ids = {r.group_id for r in rows if r.group_id}
                names = {g.id: g.name for g in crud.find(Group, {"id__in": group_ids}, db=db)}

                # 3. 轉成前端要的樣子
                out = []
                for r in rows:
                    out.append({
                        "id": str(r.id),
                        "percent": r.percent,
                        "groupId": str(r.group_id) if r.group_id else None,
                        "groupName": names.get(r.group_id, "") if r.group_id else "整體",
                        "enabled": r.enabled,
                        "firedPeriod": r.fired_period,
                    })
                return {"alerts": out}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 GET /api/alerts
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               還沒設過            → {"alerts": []}
               設了 85 和 60 之後  → 60 排在前面
        5. 前端改成連你的後端（frontend/index.html 的 api-base），個人資料頁「階段性提醒」要列出每一個門檻與開關
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "list_alerts and 你的"，要全部通過
    """
    raise not_ready("GET /api/alerts", OWNER)


@router.post("/alerts", summary="新增門檻")
@block_admin
@stub
def create_alert(body: AlertIn, me: User, db: Session = Depends(get_db)):
    """新增門檻

    POST /api/alerts

    【這支做什麼】
        新增一個提醒門檻。可以針對整體目標（不帶 groupId），或針對某一本帳。
        ⚠️ 同一個（人、帳本、百分比）只能有一筆：兩筆一樣的門檻，同一次跨越會發兩則一模一樣的通知。

    【前端怎麼打】
        frontend/js/api.js 的 API.createAlert({ percent, groupId })
        個人資料頁「階段性提醒」的新增。

    【誰能打】
        登入、沒被停權、不是平台管理員。上面的 @block_admin 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【請求主體】body 是 AlertIn（app/schemas/stats.py）
        欄位     型別  必填  說明
        percent  整數  是    1～200。超出範圍、不是整數 FastAPI 自動回 422
        groupId  字串  否    針對哪本帳；不帶 = 整體。要是我加入、沒移除的帳本
        範例：{"percent": 80, "groupId": "6"}
        · 為什麼 1～200：0% 一開始就成立，沒有意義；超過 200% 早就該提醒了。

    【成功回應】狀態碼 201
        {"id": "3", "percent": 80, "groupId": "6", "groupName": "旅遊基金", "enabled": true, "firedPeriod": null}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                              detail
        403     groupId 是我沒加入、或已經移除的帳本  你不在這本帳裡
        409     同一個帳本（或整體）已經有這個百分比  這個門檻已經設過了
        422     percent 不在 1～200                   （FastAPI 自動回）

    【會用到的資料表】
        表                     讀／寫  用來做什麼
        group_members、groups  讀      帶 groupId 時：我在不在裡面、有沒有被移除
        alert_rules            讀＋寫  有沒有重複；新增一列

    【每一步用的工具與資料庫方法】
        步驟    呼叫                                   做什麼
        1 門檻  alerts.validate_percent(body.percent)  轉成 1～200 的整數，不合法丟 InvalidThreshold（schema 已經擋過一次，這是第二道）
        2 帳本  crud.exists(GroupMember, {…}, db=db)／crud.get(Group, where={…, "removed_at__isnull": True}, db=db)  我加入、沒移除
        3 重複  crud.exists(AlertRule, {"user_id": me.id, "group_id": group_id, "percent": percent}, db=db)  group_id 是 None 就是 IS NULL
        4 新增  crud.save(AlertRule, {…}, db=db)       enabled 預設 true
                db.commit()                            寫進去
        ⚠️ 為什麼一定要自己查重複：資料表有 UNIQUE (user_id, group_id, percent)，
           但 PostgreSQL 把兩個 NULL 當成「不一樣」，針對整體（group_id 是 NULL）的重複擋不住。

    【寫法步驟】
        1. validate_percent（422）
        2. 有 groupId：要是我加入、沒移除的帳本（403）
        3. 同一個（我、帳本、百分比）已經有了 → 409
        4. 新增一列，db.commit()，回傳

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：把檔案最上面的 import 換成這樣（這個檔案每一支的第一步都一樣，換過一次就好）

            from fastapi import APIRouter, Depends
            from sqlalchemy.orm import Session

            from app.guards import block_admin, own
            from app.models import AlertRule, Group, GroupMember, User
            from app.routers._stub import not_ready, stub
            from app.schemas.stats import AlertIn, AlertPatchIn
            from app.toolkit import alerts, crud, errors
            from app.toolkit.db import get_db

        第二步：把整個 create_alert（從 @router.post 到 raise not_ready 那行）換成這段。
        注意 @stub 拿掉了、多了 status_code=201；這段說明字串可以留著。

            @router.post("/alerts", status_code=201, summary="新增門檻")
            @block_admin
            def create_alert(body: AlertIn, me: User, db: Session = Depends(get_db)):
                # 1. 門檻要是 1～200 的整數
                try:
                    percent = alerts.validate_percent(body.percent)
                except alerts.InvalidThreshold as exc:
                    raise errors.unprocessable(str(exc)) from None

                # 2. 帶了 groupId：針對那本帳，要是我加入、沒移除的
                group = None
                if body.groupId:
                    group_id = int(body.groupId) if body.groupId.isdigit() else 0
                    if crud.exists(GroupMember, {"group_id": group_id, "user_id": me.id}, db=db):
                        group = crud.get(Group, where={"id": group_id, "removed_at__isnull": True}, db=db)
                    if group is None:
                        raise errors.forbidden("你不在這本帳裡")
                group_id = group.id if group else None

                # 3. 同一個（人、帳本、百分比）只能有一筆
                if crud.exists(AlertRule, {"user_id": me.id, "group_id": group_id, "percent": percent}, db=db):
                    raise errors.conflict("這個門檻已經設過了")

                # 4. 新增
                row = crud.save(AlertRule, {"user_id": me.id, "group_id": group_id, "percent": percent}, db=db)
                db.commit()
                return {
                    "id": str(row.id),
                    "percent": row.percent,
                    "groupId": str(group_id) if group_id else None,
                    "groupName": group.name if group else "整體",
                    "enabled": row.enabled,
                    "firedPeriod": None,
                }

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/alerts
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               {"percent": 80}                           → 201，groupName 是「整體」
               再送一次 {"percent": 80}                  → 409
               {"percent": 80, "groupId": 我加入的帳本}  → 201（跟整體的不算重複）
               {"percent": 0}                            → 422
               {"percent": 80, "groupId": 別人的帳本}    → 403
        5. 前端改成連你的後端（frontend/index.html 的 api-base），個人資料頁新增一個門檻，清單馬上多一列
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "create_alert and 你的"，要全部通過
    """
    raise not_ready("POST /api/alerts", OWNER)


@router.patch("/alerts/{aid}", summary="改門檻或暫停")
@stub
def update_alert(
    body: AlertPatchIn,
    row=Depends(own(AlertRule, "aid")),
    db: Session = Depends(get_db),
):
    """改門檻或暫停

    PATCH /api/alerts/{aid}

    【這支做什麼】
        改自己一個門檻的百分比，或暫停／恢復（enabled）。
        ⚠️ 暫時不想被吵用 enabled: false，不要叫使用者刪掉再重建：關掉保留設定，下個月想開直接開。
        改了百分比，就當作這個新門檻這個月還沒響過（fired_period 清掉）。

    【前端怎麼打】
        frontend/js/api.js 的 API.updateAlert(aid, patch)
        個人資料頁每個門檻的開關、改數字。

    【誰能打】
        登入、沒被停權，而且這一筆是自己的。參數 row=Depends(own(AlertRule, "aid")) 已經擋好了：
            沒登入 → 401；被停權 → 403
            {aid} 不是數字、或找不到這一筆 → 404「找不到這筆資料」
            這一筆的 user_id 不是我 → 403「這是別人的資料，你只能檢視」
        所以函式裡不用再檢查。row 就是那一筆（AlertRule 物件），直接拿來用。

    【請求主體】body 是 AlertPatchIn（app/schemas/stats.py），只送要改的
        欄位     型別         說明
        percent  整數         1～200（超出 FastAPI 自動回 422）
        enabled  true／false  開或關
        範例：{"enabled": false}
        · 不認得的欄位 FastAPI 直接回 422（AlertPatchIn 設了 extra="forbid"）

    【成功回應】狀態碼 200
        {"id": "3", "percent": 90, "groupId": null, "groupName": "整體", "enabled": false, "firedPeriod": null}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                                        detail
        400     什麼都沒送                                      沒有要改的欄位
        403     別人的門檻                                      這是別人的資料，你只能檢視（守衛回）
        404     找不到                                          找不到這筆資料（守衛回）
        409     新的百分比跟同一本帳（或整體）的另一個門檻重複  這個門檻已經設過了
        422     percent 超出 1～200、不認得的欄位               （FastAPI 自動回）

    【會用到的資料表】
        表           讀／寫  用來做什麼
        alert_rules  讀＋寫  檢查重複；改這一列
        groups       讀      回傳時的帳本名字

    【每一步用的工具與資料庫方法】
        步驟    呼叫                                                    做什麼
        1 重複  crud.exists(AlertRule, {…, "percent": body.percent, "id__ne": row.id}, db=db)  排除自己這一列
        3 寫回  crud.save(AlertRule, {"id": row.id, **changes}, db=db)  帶主鍵 = 改那一列；row 也會跟著變
                db.commit()                                             寫進去
        4 回傳  crud.get(Group, row.group_id, db=db)                    用主鍵拿帳本名字

    【寫法步驟】
        1. 兩個都沒送 → 400
        2. 送了 percent 而且跟原本不同：不能跟自己的其他門檻重複（409），fired_period 一起清掉
        3. 送了 enabled：照改
        4. 有改到才寫回、db.commit()；回傳改完的樣子

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：把檔案最上面的 import 換成這樣（這個檔案每一支的第一步都一樣，換過一次就好）

            from fastapi import APIRouter, Depends
            from sqlalchemy.orm import Session

            from app.guards import block_admin, own
            from app.models import AlertRule, Group, GroupMember, User
            from app.routers._stub import not_ready, stub
            from app.schemas.stats import AlertIn, AlertPatchIn
            from app.toolkit import alerts, crud, errors
            from app.toolkit.db import get_db

        第二步：把整個 update_alert（從 @router.patch 到 raise not_ready 那行）換成這段。
        注意 @stub 拿掉了；這段說明字串可以留著。

            @router.patch("/alerts/{aid}", summary="改門檻或暫停")
            def update_alert(
                body: AlertPatchIn,
                row=Depends(own(AlertRule, "aid")),
                db: Session = Depends(get_db),
            ):
                if body.percent is None and body.enabled is None:
                    raise errors.bad_request("沒有要改的欄位")
                changes = {}

                # 1. 改百分比：不能跟自己的其他門檻重複；換了門檻就當作這個月還沒響過
                if body.percent is not None and body.percent != row.percent:
                    if crud.exists(AlertRule, {"user_id": row.user_id, "group_id": row.group_id,
                                               "percent": body.percent, "id__ne": row.id}, db=db):
                        raise errors.conflict("這個門檻已經設過了")
                    changes["percent"] = body.percent
                    changes["fired_period"] = None

                # 2. 暫停／恢復（關掉不刪）
                if body.enabled is not None:
                    changes["enabled"] = body.enabled

                # 3. 寫回去
                if changes:
                    crud.save(AlertRule, {"id": row.id, **changes}, db=db)
                    db.commit()

                # 4. 回傳改完的樣子
                group = crud.get(Group, row.group_id, db=db) if row.group_id else None
                return {
                    "id": str(row.id),
                    "percent": row.percent,
                    "groupId": str(row.group_id) if row.group_id else None,
                    "groupName": group.name if group else "整體",
                    "enabled": row.enabled,
                    "firedPeriod": row.fired_period,
                }

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 PATCH /api/alerts/{aid}
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               {"enabled": false}           → 200，enabled 變 false，其他沒變
               {"percent": 90}              → 200，firedPeriod 變 null
               {"percent": 另一個門檻的值}  → 409
               {}                           → 400
               別人的門檻                   → 403
        5. 前端改成連你的後端（frontend/index.html 的 api-base），個人資料頁把一個門檻關掉，重新整理之後還是關的
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "update_alert and 你的"，要全部通過
    """
    raise not_ready("PATCH /api/alerts/{aid}", OWNER)


@router.delete("/alerts/{aid}", summary="刪門檻")
@stub
def delete_alert(row=Depends(own(AlertRule, "aid")), db: Session = Depends(get_db)):
    """刪門檻

    DELETE /api/alerts/{aid}

    【這支做什麼】
        刪掉自己的一個門檻。門檻只是設定，不是紀錄，可以真的刪（已經發出去的通知不受影響）。

    【前端怎麼打】
        frontend/js/api.js 的 API.deleteAlert(aid)
        個人資料頁每個門檻的「刪除」。

    【誰能打】
        登入、沒被停權，而且這一筆是自己的。參數 row=Depends(own(AlertRule, "aid")) 已經擋好了：
            沒登入 → 401；被停權 → 403
            {aid} 不是數字、或找不到這一筆 → 404「找不到這筆資料」
            這一筆的 user_id 不是我 → 403「這是別人的資料，你只能檢視」
        所以函式裡不用再檢查。row 就是那一筆（AlertRule 物件），直接拿來用。

    【路徑參數】{aid} 是門檻的 id（字串），守衛已經換成那一列，函式裡叫 row
        範例：DELETE /api/alerts/3

    【成功回應】狀態碼 200
        {"id": "3", "deleted": true}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候    detail
        403     別人的門檻  這是別人的資料，你只能檢視（守衛回）
        404     找不到      找不到這筆資料（守衛回）

    【會用到的資料表】
        表           讀／寫    用來做什麼
        alert_rules  寫（刪）  刪這一列

    【每一步用的工具與資料庫方法】
        步驟  呼叫                                        做什麼
        1 刪  crud.remove(AlertRule, id=alert_id, db=db)  用主鍵刪一列
              db.commit()                                 寫進去
        ⚠️ 刪之前先把 row.id 存起來，刪掉之後就不要再讀 row 了。

    【寫法步驟】
        1. 記下 id，刪掉那一列，db.commit()
        2. 回 {"id", "deleted": true}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：把檔案最上面的 import 換成這樣（這個檔案每一支的第一步都一樣，換過一次就好）

            from fastapi import APIRouter, Depends
            from sqlalchemy.orm import Session

            from app.guards import block_admin, own
            from app.models import AlertRule, Group, GroupMember, User
            from app.routers._stub import not_ready, stub
            from app.schemas.stats import AlertIn, AlertPatchIn
            from app.toolkit import alerts, crud, errors
            from app.toolkit.db import get_db

        第二步：把整個 delete_alert（從 @router.delete 到 raise not_ready 那行）換成這段。
        注意 @stub 拿掉了；這段說明字串可以留著。

            @router.delete("/alerts/{aid}", summary="刪門檻")
            def delete_alert(row=Depends(own(AlertRule, "aid")), db: Session = Depends(get_db)):
                alert_id = row.id
                crud.remove(AlertRule, id=alert_id, db=db)
                db.commit()
                return {"id": str(alert_id), "deleted": True}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 DELETE /api/alerts/{aid}
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               刪自己的  → 200
               再刪一次  → 404
               刪別人的  → 403
        5. 前端改成連你的後端（frontend/index.html 的 api-base），個人資料頁刪一個門檻，清單少一列
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "delete_alert and 你的"，要全部通過
    """
    raise not_ready("DELETE /api/alerts/{aid}", OWNER)
