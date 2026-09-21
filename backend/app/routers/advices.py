"""
財務建議。

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
from app.schemas.advice import GenerateIn
from app.toolkit.db import get_db

router = APIRouter(tags=["財務建議"])
OWNER = "成員3"


@router.get("/advices", summary="財務建議清單")
@block_admin
@stub
def list_advices(me: User, scope: str | None = None, db: Session = Depends(get_db)):
    """財務建議清單

    GET /api/advices

    【這支做什麼】
        列出已經產生、存起來的財務建議，外加固定的邊界規則（rules）。
        scope=me：只回寫給我本人的。
        scope=family：全家的建議 ＋ 我看得到的人（照看的孩子、同家庭的另一位家長）的個人建議。
        ⚠️ 子女拿不到全家的建議——那幾則是寫給家長看的，裡面會點名。所以 family 只給家長、而且看得到別人的時候。

    【前端怎麼打】
        frontend/js/api.js 的 API.advices({ scope })
        財務建議頁（我／全家）、總覽的建議卡。前端檢查回應裡一定要有 advices。userName 前端會自己補。

    【誰能打】
        登入、沒被停權、不是平台管理員。上面的 @block_admin 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【查詢參數】
        參數   型別  說明
        scope  字串  me（預設）／family。不是家長、或看不到別人時，family 跟 me 一樣

    【成功回應】狀態碼 200
        {"advices": [
           {"id": "9", "scope": "user", "user": "3", "period": "2026-09", "level": "warn",
            "title": "快用完這個月可以花的", "body": "已經用掉 86%，剩 6,770 元。",
            "basis": ["收入 68,000 − 每月想存 20,000 ＝ 可以花 48,000"],
            "suggest": ["接下來兩週先暫停非必要的娛樂"], "conf": 0.9, "generatedAt": "2026-09-14 21:05"}
         ],
         "rules": [{"rule": "金額一律由資料庫計算", "why": "…"}]}
        · scope 是 "family"（家庭層級，user 是 null）或 "user"（寫給某個人）
        · ⚠️ basis 是字串陣列，不是物件：資料庫的 basis_json 存 {"lines": [句子…], "numbers": {算好的數字}}，回 lines
        · generatedAt 是台灣時間 "YYYY-MM-DD HH:MM"；新的在前
        · rules 是固定清單（app/catalog.py 的 ADVICE_RULES，跟 data.js 的 adviceRules 一樣）

    【錯誤回應】
        只有守衛的 401／403，這支本身不會出錯。

    【會用到的資料表】
        表                                                    讀／寫  用來做什麼
        guardianships、family_members、group_members、groups  讀      visible_scope()：我看得到誰
        advices                                               讀      建議本身

    【每一步用的工具與資料庫方法】
        步驟        呼叫                                         做什麼
        1 看得到誰  users, _ = visible_scope(me, db)             只要人，不要帳本（用 _ 接住不用的那個）
                    {"or": [{"user_id__in": others}, {"user_id__isnull": True, "family_id": me.family_id}]}  別人的個人建議，或我們家的家庭建議
        2 查        crud.find(Advice, where, order_by=("-generated_at", "id"), db=db)  新的在前；同一次產生的照原本順序
        3 時間      at.astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")  UTC 轉台灣時間再排成字串
                    a.generated_at.replace(tzinfo=timezone.utc)  SQLite 讀回來的時間沒有時區，補上 UTC（PostgreSQL 本來就有）

    【寫法步驟】
        1. visible_scope 拿到看得到的人，扣掉自己就是「別人」
        2. scope=family、我是家長、而且有別人：條件是「別人的個人建議，或我們家的家庭建議」；不然只查我自己的
        3. 新的在前，一則一則轉成前端要的樣子（basis 拿 lines、時間轉台灣時間）
        4. 回傳 {"advices", "rules"}
        ⚠️ 只讀不寫，不用 db.commit()。

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：把檔案最上面的 import 換成這樣（這個檔案每一支的第一步都一樣，換過一次就好）

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, Query
            from fastapi.encoders import jsonable_encoder
            from pydantic import ValidationError
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import block_admin, visible_scope
            from app.models import Advice, Category, Guardianship, SavingsGoal, User
            from app.routers._stub import not_ready, stub
            from app.schemas.advice import AdviceItem, GenerateIn
            from app.services import analytics
            from app.services.llm import advice, client
            from app.toolkit import crud, errors, money, period, profile
            from app.toolkit.config import settings
            from app.toolkit.db import get_db

        第二步：把整個 list_advices（從 @router.get 到 raise not_ready 那行）換成這段。
        注意 @stub 拿掉了；這段說明字串可以留著。

            @router.get("/advices", summary="財務建議清單")
            @block_admin
            def list_advices(me: User, scope: str | None = None, db: Session = Depends(get_db)):
                # 1. family：我看得到的別人的個人建議＋我們家的家庭建議（只給家長；子女拿不到）
                users, _ = visible_scope(me, db)
                others = [u for u in users if u != me.id]
                if scope == "family" and me.family_role == "parent" and others:
                    where = {"or": [{"user_id__in": others},
                                    {"user_id__isnull": True, "family_id": me.family_id}]}
                else:
                    where = {"user_id": me.id}

                # 2. 新的在前
                rows = crud.find(Advice, where, order_by=("-generated_at", "id"), db=db)

                # 3. 轉成前端要的樣子：basis 回句子陣列、時間轉台灣時間
                tw = timezone(timedelta(hours=8))
                out = []
                for a in rows:
                    at = a.generated_at if a.generated_at.tzinfo else a.generated_at.replace(tzinfo=timezone.utc)
                    out.append({
                        "id": str(a.id),
                        "scope": "family" if a.user_id is None else "user",
                        "user": str(a.user_id) if a.user_id else None,
                        "period": a.period_key,
                        "level": a.level,
                        "title": a.title,
                        "body": a.body,
                        "basis": (a.basis_json or {}).get("lines", []),
                        "suggest": a.suggestions_json or [],
                        "conf": float(a.confidence or 0),
                        "generatedAt": at.astimezone(tw).strftime("%Y-%m-%d %H:%M"),
                    })
                return {"advices": out, "rules": catalog.ADVICE_RULES}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 GET /api/advices
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               scope=me                        → 只有寫給自己的
               家長（有照看孩子）scope=family  → 家庭建議＋孩子的個人建議，沒有自己的
               子女 scope=family               → 跟 scope=me 一樣
        5. 前端改成連你的後端（frontend/index.html 的 api-base），財務建議頁「我／全家」切換，內容要對
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "list_advices and 你的"，要全部通過
    """
    raise not_ready("GET /api/advices", OWNER)


@router.post("/advices/generate", summary="產生這個月的建議")
@block_admin
@stub
def generate_advices(body: GenerateIn, me: User, db: Session = Depends(get_db)):
    """產生這個月的建議

    POST /api/advices/generate

    【這支做什麼】
        產生這個月的財務建議，存起來，回傳新的那幾則。
        ⚠️ 順序不能換：
            1. services/analytics.py 先從資料庫算好數字（跟 GET /api/summary 同一個來源）
            2. services/llm/advice.py 把數字交給模型「只做敘述」——任何數字都不能由模型產生（第三步）
            3. 用 AdviceItem（app/schemas/advice.py）驗證模型寫回來的每一則，不合格的丟掉
            4. 存進 advices：同一個月、同一個範圍再產生，先刪掉舊的，不要疊出兩份
        模型沒設定、叫不動、或還沒做好時回 503，前端會用同一批數字在畫面上寫幾則頂著（不會存）。

    【前端怎麼打】
        frontend/js/api.js 的 API.generateAdvices({ scope })
        財務建議頁「產生這個月的建議」（我／全家）。前端檢查回應裡一定要有 advices。

    【誰能打】
        登入、沒被停權、不是平台管理員。上面的 @block_admin 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）
        scope=family 另外要是家長、而且看得到家人（visible_scope 不只自己），不然 403。

    【請求主體】body 是 GenerateIn（app/schemas/advice.py）
        欄位   型別  必填  說明
        scope  字串  否    me（預設）／family。其他值 FastAPI 自動回 422
        範例：{"scope": "me"}

    【成功回應】狀態碼 201
        {"generatedAt": "2026-09-14 21:05",
         "advices": [{"id": "9", "scope": "user", "user": "3", "period": "2026-09", "level": "ok",
                      "title": "這個月的進度正常", "body": "…", "basis": ["…"], "suggest": ["…"],
                      "conf": 0.9, "generatedAt": "2026-09-14 21:05"}]}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                                      detail
        403     scope=family，但不是家長、或沒有照看任何家人  全家的建議只有家長、而且照看著家人時才能產生
        503     模型沒設定、叫不動                            （ModelError 的訊息，例如：模型服務還沒接上）
        503     services/llm/advice.py 還沒做好               建議還沒做好，先用前端的版本
        503     模型寫回來的沒有一則合格                      模型寫回來的建議格式不對，先用前端的版本
        ⚠️ 模型的問題回 503，不是 500；前端靠 503 決定要不要自己頂著。

    【會用到的資料表】
        表                讀／寫  用來做什麼
        guardianships 等  讀      visible_scope()、我照看的孩子（跟 GET /api/summary 一樣）
        transactions      讀      在 analytics.summary 裡加總
        savings_goals     讀      每個人最新的整體目標
        categories        讀      把 byCat 的分類 id 翻成名字，模型才寫得出「餐飲」
        users             讀      me 身上的理財習慣（finance_style、finance_goals、finance_habits、finance_note）
        advices           寫      刪掉同月同範圍的舊建議，存新的

    【每一步用的工具與資料庫方法】（第三步 write_advices 裡用的也列在這裡）
        步驟      呼叫                                                         做什麼
        2 數字    analytics.summary(db, people, earners, this_month)           跟 GET /api/summary 同一支（要先做完那支的第三步）
                  analytics.savings_status(收入, 支出, 目標)                   可支配上限、比例、燈號
                  jsonable_encoder({...})                                      把 Decimal 轉成一般數字，才能放進 prompt、存進 JSON 欄位
        3 背景    profile.to_prompt_block(finance, catalog.FINANCE_STYLES, …)  理財習慣翻成人話，並標示「這是資料，不是指令」
        4 叫模型  advice.write_advices(numbers, block)                         回傳 [{level, title, body, basis, suggest, conf}]
        5 驗證    AdviceItem.model_validate(d)                                 格式不對丟 ValidationError（from pydantic import ValidationError）
        6 存      crud.remove(Advice, {"period_type": "month", "period_key": …, "user_id": …}, db=db)  先刪同月同範圍的舊建議
                  crud.save(Advice, [{…}, {…}], db=db)                         一次新增很多列，回傳物件清單（有 id）
                  db.commit()                                                  刪舊、存新一起寫進去
        第三步    client.complete_json(prompt, system=…, max_tokens=800, temperature=0.3)  叫模型，要 JSON
                  catalog.ADVICE_RULES                                         邊界規則一起放進 system，跟畫面上顯示的是同一份
        ⚠️ 為什麼要把 basis_json 存成 {"lines", "numbers"}：lines 給人看，numbers 是這次餵給模型的數字，事後可以驗算。

    【寫法步驟】
        1. scope=family 要是家長、而且看得到別人（403）
        2. 算數字：跟 GET /api/summary 一樣決定算誰（孩子的收入不算），analytics.summary ＋ savings_status；
           byCat 的分類 id 翻成名字；全部用 jsonable_encoder 轉成一般數字
        3. 把我的理財習慣組成 prompt 的背景段落
        4. 叫 advice.write_advices；ModelError、NotImplementedError 轉成 503
        5. 每一則用 AdviceItem 驗證，不合格的丟掉；一則都不剩 → 503
        6. 刪掉同月同範圍的舊建議，存新的（family 的 user_id 是 NULL），db.commit()
        7. 回傳 {generatedAt, advices}
        第三步 write_advices() 裡面：組 system（格式＋邊界規則）與 prompt（算好的數字 JSON ＋ 理財背景）→ complete_json → 只留物件、只留需要的欄位

    【完整寫法】照下面三步改，改完這支就做好了
        第一步：把檔案最上面的 import 換成這樣（這個檔案每一支的第一步都一樣，換過一次就好）

            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, Depends, Query
            from fastapi.encoders import jsonable_encoder
            from pydantic import ValidationError
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import block_admin, visible_scope
            from app.models import Advice, Category, Guardianship, SavingsGoal, User
            from app.routers._stub import not_ready, stub
            from app.schemas.advice import AdviceItem, GenerateIn
            from app.services import analytics
            from app.services.llm import advice, client
            from app.toolkit import crud, errors, money, period, profile
            from app.toolkit.config import settings
            from app.toolkit.db import get_db

        第二步：把整個 generate_advices（從 @router.post 到 raise not_ready 那行）換成這段。
        注意 @stub 拿掉了、多了 status_code=201；這段說明字串可以留著。

            @router.post("/advices/generate", status_code=201, summary="產生這個月的建議")
            @block_admin
            def generate_advices(body: GenerateIn, me: User, db: Session = Depends(get_db)):
                # 1. 全家的建議：只有家長、而且看得到家人時才能產生
                users, _ = visible_scope(me, db)
                family_mode = body.scope == "family"
                if family_mode and not (me.family_role == "parent" and len(users) > 1):
                    raise errors.forbidden("全家的建議只有家長、而且照看著家人時才能產生")

                # 2. 先算好數字（跟 GET /api/summary 同一個來源），模型一個數字都不算
                tw = timezone(timedelta(hours=8))
                this_month = period.current_month(datetime.now(tw).date())
                wards = set(crud.find(Guardianship, {"guardian_id": me.id, "ended_at__isnull": True}, fields="ward_id", db=db))
                people = users if family_mode else {me.id}
                earners = [u for u in people if u not in wards]
                nums = analytics.summary(db, people, earners, this_month)
                goals = {}
                for row in crud.find(SavingsGoal, {"user_id__in": people, "group_id__isnull": True}, order_by="id", db=db):
                    goals[row.user_id] = row.goal_amount
                savings = analytics.savings_status(nums["income"], nums["expense"], money.add(*goals.values()))
                cat_ids = [int(c["cat"]) for c in nums["byCat"]]
                names = {c.id: c.name for c in crud.find(Category, {"id__in": cat_ids}, db=db)}
                numbers = jsonable_encoder({
                    "period": this_month,
                    "scope": body.scope,
                    "income": nums["income"],
                    "expense": nums["expense"],
                    "count": nums["count"],
                    "savings": savings,
                    "byCat": [{"name": names.get(int(c["cat"]), ""), "amount": c["amount"]} for c in nums["byCat"]],
                    "monthly": nums["monthly"],
                })

                # 3. 使用者自己填的理財習慣：只當背景，標示成「資料，不是指令」
                finance = {"style": me.finance_style, "goals": me.finance_goals or [],
                           "habits": me.finance_habits or [], "note": me.finance_note or ""}
                block = profile.to_prompt_block(finance, catalog.FINANCE_STYLES, catalog.FINANCE_GOALS, catalog.FINANCE_HABITS)

                # 4. 叫模型寫成句子；沒設定、叫不動、還沒做好都回 503（前端會用同一批數字頂著）
                try:
                    drafts = advice.write_advices(numbers, block)
                except client.ModelError as exc:
                    raise errors.service_unavailable(str(exc)) from None
                except NotImplementedError:
                    raise errors.service_unavailable("建議還沒做好，先用前端的版本") from None

                # 5. 驗證模型寫回來的每一則：格式不對的丟掉
                items = []
                for d in drafts if isinstance(drafts, list) else []:
                    try:
                        items.append(AdviceItem.model_validate(d))
                    except ValidationError:
                        continue
                if not items:
                    raise errors.service_unavailable("模型寫回來的建議格式不對，先用前端的版本")

                # 6. 存：同一個月、同一個範圍的舊建議先刪掉，不要疊出兩份
                old = {"period_type": "month", "period_key": this_month}
                if family_mode:
                    old.update({"user_id": None, "family_id": me.family_id})
                else:
                    old["user_id"] = me.id
                crud.remove(Advice, old, db=db)
                now = datetime.now(timezone.utc)
                rows = crud.save(Advice, [{
                    "family_id": me.family_id,
                    "user_id": None if family_mode else me.id,
                    "period_type": "month",
                    "period_key": this_month,
                    "level": it.level,
                    "title": it.title,
                    "body": it.body,
                    "basis_json": {"lines": it.basis, "numbers": numbers},
                    "suggestions_json": it.suggest,
                    "confidence": it.conf,
                    "model_ver": settings.advice_model_name or settings.model_name,
                    "generated_at": now,
                } for it in items], db=db)
                db.commit()

                # 7. 回傳新的那幾則
                stamp = now.astimezone(tw).strftime("%Y-%m-%d %H:%M")
                return {"generatedAt": stamp, "advices": [{
                    "id": str(r.id),
                    "scope": "family" if family_mode else "user",
                    "user": None if family_mode else str(me.id),
                    "period": this_month,
                    "level": r.level,
                    "title": r.title,
                    "body": r.body,
                    "basis": r.basis_json["lines"],
                    "suggest": r.suggestions_json,
                    "conf": float(r.confidence),
                    "generatedAt": stamp,
                } for r in rows]}

        第三步：打開 app/services/llm/advice.py，把 write_advices() 整個換成這段（函式裡那兩行 import 不用搬到檔案最上面）

            def write_advices(numbers: dict[str, Any], finance_block: str = "") -> list[dict[str, Any]]:
                '''numbers 是 analytics 算好的數字。回傳 [{level, title, body, basis, suggest, conf}]。'''
                import json

                from app import catalog

                if not client.is_configured():
                    raise client.ModelError("模型服務還沒接上")

                # a. 組 prompt：格式、邊界規則、算好的數字、使用者的理財背景
                system = chr(10).join([
                    "你是家庭記帳的財務助理。根據使用者「已經算好的數字」寫 2 到 4 則建議，只回 JSON，不要其他文字。",
                    '格式：{"advices": [{"level": "ok、info、warn 其中一個", "title": "20 字內", "body": "80 字內",',
                    '"basis": ["依據：用下面給的數字寫成的算式"], "suggest": ["具體可以做的事"], "conf": 0 到 1 的數字}]}',
                    "任何數字都只能照抄下面給的，不可以自己計算或編造。",
                    "規則：",
                ] + ["- " + r["rule"] for r in catalog.ADVICE_RULES])
                prompt = chr(10).join([
                    "【算好的數字（JSON）】",
                    json.dumps(numbers, ensure_ascii=False),
                    finance_block,
                    "請寫建議：",
                ])

                # b. 叫模型
                data = client.complete_json(prompt, system=system, max_tokens=800, temperature=0.3)
                items = data.get("advices") if isinstance(data, dict) else data
                if not isinstance(items, list):
                    raise client.ModelError("模型回來的格式不對")

                # c. 只留物件、只留需要的欄位（每一欄的檢查在路由裡用 AdviceItem 做）
                keys = ("level", "title", "body", "basis", "suggest", "conf")
                return [{k: it[k] for k in keys if k in it} for it in items if isinstance(it, dict)]

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/advices/generate
        3. 按右上角 Authorize，貼上登入拿到的 accessToken；backend/.env 的 MODEL_BASE_URL 先留空
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               {"scope": "me"}（MODEL_BASE_URL 留空）  → 503
               子女 {"scope": "family"}                → 403
        5. MODEL_BASE_URL 填好、重開 uvicorn，再試 {"scope": "me"} → 201，basis 裡的數字要跟 GET /api/summary 一樣
        6. 同一個月再產生一次 → GET /api/advices 不會出現兩份
        7. 前端改成連你的後端（frontend/index.html 的 api-base），財務建議頁按「產生這個月的建議」，出現新的建議卡片
        8. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "generate_advices and 你的"，要全部通過
    """
    raise not_ready("POST /api/advices/generate", OWNER)
