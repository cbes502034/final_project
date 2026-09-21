"""
統計摘要。

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

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.guards import block_admin
from app.models import User
from app.routers._stub import not_ready, stub
from app.toolkit.db import get_db

router = APIRouter(tags=["統計"])
OWNER = "成員3"


@router.get("/summary", summary="個人／家庭摘要")
@block_admin
@stub
def get_summary(
    me: User,
    scope: str | None = None,
    groupId: str | None = None,
    db: Session = Depends(get_db),
):
    """個人／家庭摘要

    GET /api/summary

    【這支做什麼】
        總覽與統計頁的所有數字：這個月的收入、支出、各分類、近 6 個月、近 3 年、存款目標燈號、每個人的這個月。
        scope=me 只算自己；scope=family 算「我看得到全部紀錄的人」（自己＋照看的人＋同家庭的其他家長）。
        ⚠️ 所有數字都從 transactions 加總，整個系統只有 services/analytics.py 加總錢——
           這支負責「決定算誰、算哪本帳」，加總交給 analytics.summary()（第三步）。
        ⚠️ 家庭模式：照看的孩子的收入不算進家庭收入（那多半是零用金，會重複算），支出要算；
           孩子的收入另外放在 wardIncome。
        ⚠️ 只加總「這些人記的」，不加帳本裡別人的——不然配偶記在共用帳本的錢會算成你的。

    【前端怎麼打】
        frontend/js/api.js 的 API.summary({ scope, groupId })
        總覽（我／全家）、統計頁、前端產生建議的備援都用它。前端檢查回應裡一定要有 income、expense、byCat、monthly、yearly。
        net、rate、byCat 的 name／color、savings 的衍生欄位前端補得出來；這支還是照下面回，有帶就用後端的。

    【誰能打】
        登入、沒被停權、不是平台管理員。上面的 @block_admin 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【查詢參數】
        參數     型別  說明
        scope    字串  me（預設）／family。其他值回 422。子女打 family 也只會算到自己（他看不到別人）
        groupId  字串  只算那一本帳；all 等於沒帶。要是我加入的帳本，不然 403
        · 期間一律是「台灣的這個月」。前端不送 period。

    【成功回應】狀態碼 200
        {"period": "2026-09", "scope": "family",
         "income": 68000, "expense": 41230, "count": 42,
         "wardIncome": 500, "allowance": 3000, "wardSpend": 1850,
         "savings": {"goal": 20000, "allowance": 48000, "used": 41230, "left": 6770, "ratio": 0.859,
                     "level": "near", "shortfall": 0, "actual": 26770,
                     "rule": {"warnAt": 0.8, "overAt": 1.0, "note": "可支配上限 = …"}},
         "byCat": [{"cat": "3", "amount": 18500}],
         "monthly": [{"m": "2026-04", "income": 68000, "expense": 39800}, …共 6 個月，最後一個是本月],
         "yearly": [{"y": "2024", "partial": false, "income": …, "expense": …}, …共 3 年，最後一個是今年],
         "members": [{"id": "3", "name": "王大明", "role": "parent", "avatar": "明", "avatarUrl": null,
                      "income": 68000, "expense": 41230, "savingsGoal": 20000, "allowance": 48000,
                      "savingsRatio": 0.859, "savingsLevel": "near", "shortfall": 0}]}
        欄位                   怎麼來的
        income                 這個月「收入要算的人」（不含照看的孩子）的收入
        expense                這個月所有要算的人的支出
        count                  這個月的筆數
        wardIncome／wardSpend  照看的孩子這個月的收入／支出（scope=me 時是 0）
        allowance              我給照看的孩子的零用金設定加總（scope=me 時是 0）
        savings                analytics.savings_status(收入, 支出, 存款目標)；目標是每個人最新的一筆加起來，選了帳本就用那本帳的
        savings.rule           門檻來自設定 SAVINGS_WARN_RATIO／SAVINGS_OVER_RATIO（跟前端 data.js 的 savingsRule 一致）
        members                每個人的這個月，各自的燈號——家庭整體達標不代表每個人都達標
        ⚠️ 帶了 groupId，每一個數字（包括 monthly、yearly、members）都只算那本帳。
        ⚠️ kind = transfer 不進任何加總。金額一律 Decimal，FastAPI 會轉成數字。

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                  detail
        403     groupId 是我沒加入的帳本  你不在這本帳裡
        422     scope 不是 me／family     scope 只能是 me 或 family

    【會用到的資料表】
        表                                                    讀／寫  用來做什麼
        guardianships、family_members、group_members、groups  讀      visible_scope()：看得到誰、看得到哪幾本帳
        guardianships                                         讀      我照看的孩子（收入不算進家庭收入）
        transactions                                          讀      所有數字的來源（在 analytics.summary 裡查）
        savings_goals                                         讀      每個人的存款目標（最新的一筆）
        allowances                                            讀      我給孩子的零用金設定
        users、family_members                                 讀      members 的名字、頭像、角色

    【每一步用的工具與資料庫方法】
        步驟      呼叫                                                          做什麼
        1 這個月  period.current_month(datetime.now(timezone(timedelta(hours=8))).date())  台灣的今天 → "2026-09"
        2 算誰    users, groups = visible_scope(me, db)                         看得到全部紀錄的人、我加入的帳本
                  crud.find(Guardianship, {"guardian_id": me.id, "ended_at__isnull": True}, fields="ward_id", db=db)  我照看的孩子
        4 加總    analytics.summary(db, people, earners, this_month, group_id)  回傳 income、expense、count、byCat、monthly、yearly、perUser
        5 目標    crud.find(SavingsGoal, {"user_id__in": people, "group_id": group_id}, order_by="id", db=db)  group_id 是 None 就是整體目標（IS NULL）；後面的蓋掉前面的
                  money.add(*goals.values())                                    全部加起來（沒有就是 0）
                  analytics.savings_status(收入, 支出, 目標)                    可支配上限、比例、燈號（除以 0 已經處理好）
        6 零用金  crud.find(Allowance, {"payer_id": me.id, "ward_id__in": kids, "period_key__isnull": True}, fields="amount", db=db)  我給每個孩子的設定
        7 每個人  images.to_data_uri(u.avatar_bytes, u.avatar_mime)             有大頭貼才轉成 data URI
        第三步    crud.find(Transaction, where, fields=("user_id", "category_id", "kind", "amount", "occurred_on"), db=db)  只拿需要的欄位，回傳 dict 清單
                  periods.recent_months(period, 6)                              近 6 個月，由舊到新
                  periods.is_incomplete_year("2026")                            今年還沒過完 → partial
                  money.ZERO／money.add(...)                                    Decimal 的 0 與加總；不要用 float

    【寫法步驟】
        1. 算出台灣的這個月
        2. 決定算誰：me = 只有自己；family = visible_scope 的人。照看的孩子從「收入要算的人」拿掉
        3. 有 groupId：要在我加入的帳本裡（403）
        4. analytics.summary 一次算好
        5. 存款目標（整體或那本帳的，每人最新一筆）→ savings_status，再掛上門檻 rule
        6. 零用金設定加總；孩子的收入、支出從 perUser 拿
        7. 每個人各自的燈號，組成 members
        8. 全部組起來回傳
        第三步 analytics.summary() 裡面：
        a. 一次查出「這三年、這些人、收入或支出」的明細（選了帳本就加 group_id）
        b. 一筆一筆分到桶子：本月的算進 perUser 與 byCat；收入要算的人（或支出）算進 monthly、yearly
        c. 合計 income（只加 earners）、expense（全部），byCat 由大到小
        ⚠️ 金額全程 Decimal（money 模組），不要轉 float 再加。

    【完整寫法】照下面三步改，改完這支就做好了
        第一步：把檔案最上面的 import 換成這樣（這個檔案每一支的第一步都一樣，換過一次就好）

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, Query
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import block_admin, visible_scope
            from app.models import Allowance, FamilyMember, Guardianship, SavingsGoal, User
            from app.routers._stub import not_ready, stub
            from app.services import analytics
            from app.toolkit import crud, errors, images, money, period
            from app.toolkit.config import settings
            from app.toolkit.db import get_db

        第二步：把整個 get_summary（從 @router.get 到 raise not_ready 那行）換成這段。
        注意 @stub 拿掉了；這段說明字串可以留著。

            @router.get("/summary", summary="個人／家庭摘要")
            @block_admin
            def get_summary(
                me: User,
                scope: str | None = None,
                groupId: str | None = None,
                db: Session = Depends(get_db),
            ):
                # 1. 期間：台灣的這個月
                this_month = period.current_month(datetime.now(timezone(timedelta(hours=8))).date())

                # 2. 要算誰：me 只有自己；family 是我看得到全部紀錄的人。照看的孩子收入不算進家庭收入
                scope = scope or "me"
                if scope not in ("me", "family"):
                    raise errors.unprocessable("scope 只能是 me 或 family")
                users, groups = visible_scope(me, db)
                wards = set(crud.find(Guardianship, {"guardian_id": me.id, "ended_at__isnull": True}, fields="ward_id", db=db))
                people = users if scope == "family" else {me.id}
                kids = [u for u in people if u in wards]
                earners = [u for u in people if u not in wards]

                # 3. 只算某一本帳：要是我加入的
                group_id = None
                if groupId and groupId != "all":
                    group_id = int(groupId) if groupId.isdigit() else 0
                    if group_id not in groups:
                        raise errors.forbidden("你不在這本帳裡")

                # 4. 加總（整個系統只有 analytics 加總錢）
                nums = analytics.summary(db, people, earners, this_month, group_id)
                per_user = nums["perUser"]

                # 5. 存款目標：選了帳本用那本帳的，沒選用整體的；每個人最新的一筆
                goals = {}
                for row in crud.find(SavingsGoal, {"user_id__in": people, "group_id": group_id}, order_by="id", db=db):
                    goals[row.user_id] = row.goal_amount
                savings = analytics.savings_status(nums["income"], nums["expense"], money.add(*goals.values()))
                savings["rule"] = {"warnAt": settings.savings_warn_ratio, "overAt": settings.savings_over_ratio,
                                   "note": catalog.SAVINGS_RULE_NOTE}

                # 6. 我給照看的孩子的零用金（設定，不是支出）
                allowance = money.ZERO
                if kids:
                    allowance = money.add(*crud.find(Allowance, {"payer_id": me.id, "ward_id__in": kids,
                                                                 "period_key__isnull": True}, fields="amount", db=db))

                # 7. 每個人的這個月，各自的燈號
                roles = {m.user_id: m.role for m in crud.find(FamilyMember, {"user_id__in": people, "status": "active"}, db=db)}
                members = []
                for u in crud.find(User, {"id__in": people}, order_by="id", db=db):
                    mine = per_user[u.id]
                    status = analytics.savings_status(mine["income"], mine["expense"], goals.get(u.id, 0))
                    members.append({
                        "id": str(u.id),
                        "name": u.display_name,
                        "role": roles.get(u.id),
                        "avatar": u.display_name[-1:],
                        "avatarUrl": images.to_data_uri(u.avatar_bytes, u.avatar_mime) if u.avatar_bytes else None,
                        "income": mine["income"],
                        "expense": mine["expense"],
                        "savingsGoal": goals.get(u.id, 0),
                        "allowance": status["allowance"],
                        "savingsRatio": status["ratio"],
                        "savingsLevel": status["level"],
                        "shortfall": status["shortfall"],
                    })

                # 8. 全部組起來
                return {
                    "period": this_month,
                    "scope": scope,
                    "income": nums["income"],
                    "expense": nums["expense"],
                    "count": nums["count"],
                    "wardIncome": money.add(*[per_user[u]["income"] for u in kids]),
                    "allowance": allowance,
                    "wardSpend": money.add(*[per_user[u]["expense"] for u in kids]),
                    "savings": savings,
                    "byCat": nums["byCat"],
                    "monthly": nums["monthly"],
                    "yearly": nums["yearly"],
                    "members": members,
                }

        第三步：打開 app/services/analytics.py，把 summary() 整個換成這段（GET /api/summary 與 POST /api/advices/generate 都用它；函式裡那三行 import 不用搬到檔案最上面）

            def summary(db: Any, users: list[int], earners: list[int], period: str, group_id: int | None = None) -> dict[str, Any]:
                '''GET /api/summary 的數字。users 是這次要算的人，earners 是收入要算進去的人（不含子女）。'''
                from datetime import date

                from app.models import Transaction
                from app.toolkit import crud, period as periods

                users, earners = set(users), set(earners)
                year = int(period[:4])
                months = periods.recent_months(period, 6)
                years = [str(year - 2), str(year - 1), str(year)]

                # a. 一次查出這三年、這些人記的收支（transfer 不算；選了帳本只算那本）
                where = {"user_id__in": users, "kind__in": ["income", "expense"],
                         "occurred_on__between": (date(year - 2, 1, 1), date(year, 12, 31))}
                if group_id is not None:
                    where["group_id"] = group_id
                rows = crud.find(Transaction, where, fields=("user_id", "category_id", "kind", "amount", "occurred_on"), db=db)

                # b. 一筆一筆分到桶子裡
                per_user = {u: {"income": money.ZERO, "expense": money.ZERO} for u in users}
                monthly = {m: {"income": money.ZERO, "expense": money.ZERO} for m in months}
                yearly = {y: {"income": money.ZERO, "expense": money.ZERO} for y in years}
                by_cat = {}
                count = 0
                for r in rows:
                    ym = r["occurred_on"].isoformat()[:7]
                    kind, amount = r["kind"], r["amount"]
                    if ym == period:
                        count += 1
                        per_user[r["user_id"]][kind] += amount
                        if kind == "expense":
                            by_cat[r["category_id"]] = by_cat.get(r["category_id"], money.ZERO) + amount
                    if kind == "income" and r["user_id"] not in earners:
                        continue                      # 子女的收入不算進家庭收入（多半是零用金，會重複算）
                    if ym in monthly:
                        monthly[ym][kind] += amount
                    yearly[ym[:4]][kind] += amount

                # c. 合計：收入只加 earners，支出加全部
                return {
                    "income": money.add(*[per_user[u]["income"] for u in users if u in earners]),
                    "expense": money.add(*[per_user[u]["expense"] for u in users]),
                    "count": count,
                    "byCat": [{"cat": str(c), "amount": a}
                              for c, a in sorted(by_cat.items(), key=lambda kv: kv[1], reverse=True)],
                    "monthly": [{"m": m, **monthly[m]} for m in months],
                    "yearly": [{"y": y, "partial": periods.is_incomplete_year(y), **yearly[y]} for y in years],
                    "perUser": per_user,
                }

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 GET /api/summary
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               什麼都不帶                        → 200，income／expense 是自己這個月的
               scope=family（家長，有照看孩子）  → 孩子的支出算進 expense，孩子的收入在 wardIncome
               groupId=一本我沒加入的帳          → 403
               scope=all                         → 422
        5. 自己記一筆 transfer → 任何數字都不能變
        6. 家用帳本裡配偶記的一筆 → 你的 scope=me 數字不能變
        7. 前端改成連你的後端（frontend/index.html 的 api-base），總覽「我／全家」切換、統計頁，數字要跟收支明細加起來一樣
        8. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "get_summary and 你的"，要全部通過
    """
    raise not_ready("GET /api/summary", OWNER)
