"""
自然語言記帳：解析（不寫入）與確認後寫入。

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
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.guards import block_admin
from app.models import Category, Group, GroupMember, Guardianship, NlpParse, Notification, Transaction, User
from app.routers._stub import not_ready, stub
from app.schemas.nlp import ConfirmBatchIn, ConfirmIn, ParseIn
from app.services.llm import client, parse
from app.toolkit import crud, errors, ledger, money, notify
from app.toolkit.config import settings
from app.toolkit.db import get_db

router = APIRouter(tags=["段落記帳"])
OWNER = "成員2"


@router.post("/nlp/parse", summary="單句解析（不寫入）")
@block_admin
@stub
def parse_one(body: ParseIn, me: User, db: Session = Depends(get_db)):
    """單句解析（不寫入）

    POST /api/nlp/parse

    【這支做什麼】
        一句話 → 一筆（例如「早餐55」）。**只解析，不寫資料庫**，使用者確認後才走 POST /api/nlp/confirm 寫入。
        路由只做三件事：整理輸入、把分類清單與今天日期交給模型、把結果轉成前端要的形狀。
        真正叫模型的是 app/services/llm/parse.py 的 parse_one()（第三步）。

    【前端怎麼打】
        frontend/js/api.js 的 API.nlpParse(text)
        目前沒有畫面在用（段落版已經涵蓋），優先序可以排在最後。前端檢查回應裡一定要有 out。
        這支回 503（模型叫不動）時，前端會用自己的規則解析頂著，畫面照常能用。
        回 501（還沒做）不頂：後端沒做，前端就該做不到。

    【誰能打】
        登入、沒被停權、不是平台管理員。上面的 @block_admin 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【請求主體】body 是 ParseIn（app/schemas/nlp.py）
        欄位  型別  必填  說明
        text  字串  是    1～500 字。空字串、超過 500 字 FastAPI 自動回 422；全是空白要自己擋
        範例：{"text": "早餐55"}

    【成功回應】狀態碼 200
        {"raw": "早餐55", "matched": false, "note": "",
         "out": {"date": "2026-09-17", "amount": 55, "kind": "expense", "cat": "1",
                 "merchant": "", "conf": 0.99, "catConf": 0.9}}
        · out.conf 是金額的信心度、out.catConf 是分類的信心度（0～1）
        · 抽不到的欄位是 null，不要猜一個值
        · matched 固定 false（保留給「完全對到範例句」用）

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                                                     detail
        422     text 全是空白                                                先寫一句話
        503     模型沒設定（MODEL_BASE_URL 空的）、叫不動、回來的東西看不懂  模型服務還沒接上，先用前端的規則解析
        503     services/llm/parse.py 還沒做好（NotImplementedError）        模型解析還沒做好，先用前端的規則解析
        ⚠️ 模型的問題回 503，不是 500：那是外部服務的問題，不是我們的程式壞了，前端也靠 503 決定要不要自己頂著。

    【會用到的資料表】
        表          讀／寫  用來做什麼
        categories  讀      系統分類＋我們家的分類，交給模型挑（模型只能回清單裡的 id）
        （不寫任何表）

    【每一步用的工具與資料庫方法】
        步驟        呼叫                                               做什麼
        2 分類清單  crud.find(Category, {"or": [{"family_id__isnull": True}, {"family_id": me.family_id}]}, order_by="id", db=db)  系統的＋我們家的分類
                    datetime.now(timezone(timedelta(hours=8))).date()  台灣的今天（伺服器在 UTC，早上 8 點前還是昨天）
        3 叫模型    parse.parse_one(text, catalog, today)              回傳一筆 {date, amount, kind, cat, merchant, note, conf: {…}, missing, hint}
                    except client.ModelError                           模型沒設定、叫不動、格式不對
                    errors.service_unavailable("…")                    回 503

    【寫法步驟】
        1. 去掉頭尾空白，空的回 422
        2. 查分類清單（系統的＋我們家的），轉成 [{id, name, kind}]；算出台灣的今天
        3. 叫 parse.parse_one；ModelError、NotImplementedError 都轉成 503
        4. 轉成 {raw, matched, note, out}，out.conf 放金額信心度、out.catConf 放分類信心度
        ⚠️ 這支一行資料庫都不寫。寫入只發生在使用者按下確認之後。
        ⚠️ 第三步的 parse_one() 直接拿 parse_batch() 的第一筆：要先做 POST /api/nlp/parse-batch 的第三步。

    【完整寫法】照下面三步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import date, datetime, timedelta, timezone

            from fastapi import APIRouter, Depends
            from sqlalchemy.orm import Session

            from app.guards import block_admin
            from app.models import Category, Group, GroupMember, Guardianship, NlpParse, Notification, Transaction, User
            from app.routers._stub import not_ready, stub
            from app.schemas.nlp import ConfirmBatchIn, ConfirmIn, ParseIn
            from app.services.llm import client, parse
            from app.toolkit import crud, errors, ledger, money, notify
            from app.toolkit.config import settings
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 全是空白不算一句話
            text = body.text.strip()
            if not text:
                raise errors.unprocessable("先寫一句話")

            # 2. 分類清單（系統的＋我們家的）與台灣的今天，交給模型
            cats = crud.find(Category, {"or": [{"family_id__isnull": True}, {"family_id": me.family_id}]},
                             order_by="id", db=db)
            catalog = [{"id": str(c.id), "name": c.name, "kind": c.kind} for c in cats]
            today = datetime.now(timezone(timedelta(hours=8))).date().isoformat()

            # 3. 叫模型；沒設定、叫不動、還沒做好都回 503（前端會用規則頂著）
            try:
                item = parse.parse_one(text, catalog, today)
            except client.ModelError as exc:
                raise errors.service_unavailable(str(exc)) from None
            except NotImplementedError:
                raise errors.service_unavailable("模型解析還沒做好，先用前端的規則解析") from None

            # 4. 轉成前端要的形狀（不寫資料庫）
            conf = item.get("conf") or {}
            return {
                "raw": text,
                "matched": False,
                "note": "",
                "out": {
                    "date": item.get("date"),
                    "amount": item.get("amount"),
                    "kind": item.get("kind"),
                    "cat": item.get("cat"),
                    "merchant": item.get("merchant") or "",
                    "conf": conf.get("amount", 0),
                    "catConf": conf.get("cat", 0),
                },
            }

        第三步：打開 app/services/llm/parse.py，把 parse_one() 整個換成這段（一句話就是只有一筆的段落，直接拿 parse_batch 的第一筆）

            def parse_one(text: str, categories: list[dict[str, Any]], today: str) -> dict[str, Any]:
                '''一句話 → 一筆。跟 parse_batch 用同一套 prompt，拿第一筆。'''
                result = parse_batch(text, categories, today)
                if not result["items"]:
                    raise client.ModelError("模型沒有從這句話解析出任何一筆")
                return result["items"][0]

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/nlp/parse
        3. 按右上角 Authorize，貼上登入拿到的 accessToken；backend/.env 的 MODEL_BASE_URL 先留空
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               text 填「早餐55」（MODEL_BASE_URL 留空）  → 503
               text 填三個空白                           → 422
        5. 把 MODEL_BASE_URL 填成模型服務的網址、重開 uvicorn，再試「早餐55」→ 200，out.amount 是 55、out.cat 是「餐飲」的 id
        6. 資料庫 transactions、nlp_parses 都不能多出任何一列
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "parse_one and u4f60" -v，要全部通過
           （u4f60 是標籤「你的」的跳脫碼。pytest 會把中文標籤轉成跳脫碼，
            -k 直接打中文比不到任何測試，會印出 0 selected）
    """
    raise not_ready("POST /api/nlp/parse", OWNER)


@router.post("/nlp/parse-batch", summary="段落解析（不寫入）")
@block_admin
@stub
def parse_batch(body: ParseIn, me: User, db: Session = Depends(get_db)):
    """段落解析（不寫入）

    POST /api/nlp/parse-batch

    【這支做什麼】
        ★ 系統核心：一段話 → 好幾筆（例如「早上買早餐55，中午吃飯320，晚上加油1200」）。
        **只解析，不寫資料庫**，使用者在畫面上檢查、修改之後，才由 POST /api/nlp/confirm-batch 寫入。
        路由只做：整理輸入、把分類清單與今天日期交給模型、回傳結果。
        真正組 prompt、叫模型、驗證欄位的是 app/services/llm/parse.py 的 parse_batch()（第三步）。

    【前端怎麼打】
        frontend/js/api.js 的 API.nlpParseBatch(text)
        記帳頁「段落記帳」按下解析時呼叫。前端檢查回應裡一定要有 items，然後：
            · 一筆一列畫成可以改的表格；span 顯示成「原句『…』」讓人檢查切分
            · missing 裡有哪一欄，那一格就標紅、加「必填」；有任何一筆缺欄位，送出鈕就停用
            · conf 某一欄小於 0.85，那一格標黃並顯示百分比；hint 顯示在原句下面
        這支回 503 時，前端會用自己的規則切分頂著（寫入還是走後端）。501 不頂，照實壞掉。

    【誰能打】
        登入、沒被停權、不是平台管理員。上面的 @block_admin 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【請求主體】body 是 ParseIn（app/schemas/nlp.py）
        欄位  型別  必填  說明
        text  字串  是    1～500 字。空字串、超過 500 字 FastAPI 自動回 422；全是空白要自己擋
        範例：{"text": "早上買早餐55，中午跟同事吃飯320，晚上加油"}

    【成功回應】狀態碼 200
        {"raw": "早上買早餐55，…", "matched": false,
         "items": [
           {"seq": 1, "span": "早上買早餐55", "date": "2026-09-17", "amount": 55, "kind": "expense",
            "cat": "1", "merchant": "", "note": "早餐",
            "conf": {"date": 0.93, "amount": 0.99, "kind": 0.97, "cat": 0.88}, "missing": [], "hint": ""},
           {"seq": 3, "span": "晚上加油", "date": "2026-09-17", "amount": null, "kind": "expense",
            "cat": "2", "merchant": "", "note": "加油",
            "conf": {"date": 0.9, "amount": 0, "kind": 0.95, "cat": 0.85}, "missing": ["amount"],
            "hint": "這一筆有欄位抽不到，補上才能存"}
         ],
         "note": "這段話被切成 3 筆。切分本身也是模型的判斷，請對照原句檢查。"}
        · ⚠️ 抽不到就回 null ＋ 放進 missing，不要猜一個數字：空白使用者一定會發現，猜錯的他可能直接送出
        · ⚠️ cat 一定要是清單裡真的存在的 id；模型自己編的名字，前端的下拉選單找不到
        · conf 是「逐欄」的，不是整筆一個分數

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                                detail
        422     text 全是空白                           先寫一段話
        503     模型沒設定、叫不動、回來的不是要的格式  （ModelError 的訊息，例如：模型服務還沒接上，先用前端的規則解析）
        503     services/llm/parse.py 還沒做好          模型解析還沒做好，先用前端的規則解析

    【會用到的資料表】
        表          讀／寫  用來做什麼
        categories  讀      系統分類＋我們家的分類，交給模型挑
        （不寫任何表）

    【每一步用的工具與資料庫方法】（第三步 parse_batch 裡用的也列在這裡）
        步驟        呼叫                                                     做什麼
        2 分類清單  crud.find(Category, {"or": [系統的, 我們家的]}, order_by="id", db=db)  模型只能從這裡挑
        3 叫模型    parse.parse_batch(text, catalog, today)                  回傳 {raw, items, note}
        第三步      client.is_configured()                                   MODEL_BASE_URL 有沒有填
                    client.complete_json(prompt, system=…, max_tokens=1024)  送出去、等回應、把 JSON 解出來；叫不動或不是 JSON 丟 ModelError
                    json.dumps(example, ensure_ascii=False)                  範例轉成 JSON 字串放進 prompt（中文照原樣放，不要變成一串編碼）
                    date.fromisoformat(…)                                    日期格式不對丟 ValueError → 放進 missing
                    money.to_decimal(…, allow_negative=False)                金額轉 Decimal；不是數字、負數丟 InvalidAmount → 放進 missing
                    chr(10)                                                  換行字元。說明字串裡不方便寫反斜線，所以用 chr(10).join([...]) 把幾行接起來

    【寫法步驟】
        1. 去掉頭尾空白，空的回 422
        2. 查分類清單，轉成 [{id, name, kind}]；算出台灣的今天
        3. 叫 parse.parse_batch；ModelError、NotImplementedError 都轉成 503
        4. 回傳 {raw, matched: false, items, note}
        第三步 parse_batch() 裡面：
        a. 組 prompt：規則（只回 JSON、抽不到填 null）、今天日期、分類清單、一組「輸入 → 輸出」的範例（few-shot）
        b. client.complete_json 叫模型
        c. 一筆一筆驗證：日期、金額（> 0）、收支、分類（要在清單裡、收支要對得上）；不對的欄位設成 null、放進 missing
        d. 信心度夾在 0～1 之間；span、店家、備註截長度
        ⚠️ 我們的模型是自己微調的：訓練時如果用了別的 prompt 格式，a 的 prompt 換成訓練時那一套，b、c 不用動。
        ⚠️ 驗證那一段不能省：模型回什麼都有可能，沒驗證就交給前端，壞掉的是使用者的帳。

    【完整寫法】照下面三步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import date, datetime, timedelta, timezone

            from fastapi import APIRouter, Depends
            from sqlalchemy.orm import Session

            from app.guards import block_admin
            from app.models import Category, Group, GroupMember, Guardianship, NlpParse, Notification, Transaction, User
            from app.routers._stub import not_ready, stub
            from app.schemas.nlp import ConfirmBatchIn, ConfirmIn, ParseIn
            from app.services.llm import client, parse
            from app.toolkit import crud, errors, ledger, money, notify
            from app.toolkit.config import settings
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 全是空白不算一段話
            text = body.text.strip()
            if not text:
                raise errors.unprocessable("先寫一段話")

            # 2. 分類清單（系統的＋我們家的）與台灣的今天，交給模型
            cats = crud.find(Category, {"or": [{"family_id__isnull": True}, {"family_id": me.family_id}]},
                             order_by="id", db=db)
            catalog = [{"id": str(c.id), "name": c.name, "kind": c.kind} for c in cats]
            today = datetime.now(timezone(timedelta(hours=8))).date().isoformat()

            # 3. 叫模型；沒設定、叫不動、還沒做好都回 503（前端會用規則頂著）
            try:
                result = parse.parse_batch(text, catalog, today)
            except client.ModelError as exc:
                raise errors.service_unavailable(str(exc)) from None
            except NotImplementedError:
                raise errors.service_unavailable("模型解析還沒做好，先用前端的規則解析") from None

            # 4. 回傳（不寫資料庫）
            return {"raw": text, "matched": False, "items": result["items"], "note": result.get("note", "")}

        第三步：打開 app/services/llm/parse.py，把 parse_batch() 整個換成這段（函式最上面那三行 import 放在函式裡，檔案最上面不用動）

            def parse_batch(text: str, categories: list[dict[str, Any]], today: str) -> dict[str, Any]:
                '''一段話 → 好幾筆。模型沒設定丟 client.ModelError（路由轉 503）。'''
                import json
                from datetime import date

                from app.toolkit import money

                if not client.is_configured():
                    raise client.ModelError(MODEL_UNAVAILABLE)

                # a. 組 prompt：規則、今天日期、分類清單（模型只能從這裡挑）、一組範例
                rules = [
                    "你是記帳助理，把使用者的一段話切成一筆一筆的收支，只回 JSON，不要任何說明文字。",
                    "每一筆要有 span（原句裡對應的那一段）、date（YYYY-MM-DD）、amount（正數）、",
                    "kind（expense 或 income）、cat（下面分類清單裡的 id）、merchant（店家，沒有就空字串）、",
                    "note（備註，沒有就空字串）、conf（date、amount、kind、cat 各一個 0 到 1 的信心度）。",
                    "抽不到的欄位填 null，不要猜。「昨天」「前天」要換算成日期。",
                    "今天是 " + today + "。分類清單：",
                ]
                for c in categories:
                    rules.append("  %s：%s（%s）" % (c["id"], c["name"], "收入" if c["kind"] == "income" else "支出"))
                ids = {c["name"]: c["id"] for c in categories}
                example = {"items": [
                    {"span": "早上買早餐55", "date": today, "amount": 55, "kind": "expense", "cat": ids.get("餐飲", ""),
                     "merchant": "", "note": "早餐", "conf": {"date": 0.9, "amount": 0.99, "kind": 0.97, "cat": 0.9}},
                    {"span": "晚上加油", "date": today, "amount": None, "kind": "expense", "cat": ids.get("交通", ""),
                     "merchant": "", "note": "加油", "conf": {"date": 0.9, "amount": 0, "kind": 0.95, "cat": 0.85}},
                ]}
                prompt = chr(10).join([
                    "範例輸入：早上買早餐55，晚上加油",
                    "範例輸出：" + json.dumps(example, ensure_ascii=False),
                    "輸入：" + text,
                    "輸出：",
                ])

                # b. 叫模型（逾時、重試、剝掉 JSON 外面的包裝，client 都做好了）
                data = client.complete_json(prompt, system=chr(10).join(rules), max_tokens=1024)
                raw_items = data.get("items") if isinstance(data, dict) else None
                if not isinstance(raw_items, list):
                    raise client.ModelError("模型回來的格式不對")

                # c. 一筆一筆驗證：抽不到、不合理的欄位設成 None，放進 missing
                def score(value):
                    try:
                        return min(1.0, max(0.0, float(value)))
                    except (TypeError, ValueError):
                        return 0.0

                kinds = {c["id"]: c["kind"] for c in categories}
                items = []
                for raw in raw_items:
                    if not isinstance(raw, dict):
                        continue
                    missing = []
                    try:
                        day = date.fromisoformat(str(raw.get("date"))).isoformat()
                    except ValueError:
                        day = None
                        missing.append("date")
                    try:
                        amount = money.to_decimal(raw.get("amount"), allow_negative=False)
                    except money.InvalidAmount:
                        amount = None
                    if amount is None or amount <= 0:
                        amount = None
                        missing.append("amount")
                    kind = raw.get("kind") if raw.get("kind") in ("expense", "income") else None
                    if kind is None:
                        missing.append("kind")
                    cat = str(raw.get("cat") or "")
                    if cat not in kinds or (kind is not None and kinds[cat] != kind):
                        cat = None
                        missing.append("cat")
                    conf = raw.get("conf") if isinstance(raw.get("conf"), dict) else {}
                    items.append({
                        "seq": len(items) + 1,
                        "span": str(raw.get("span") or "")[:100],
                        "date": day,
                        "amount": float(amount) if amount is not None else None,
                        "kind": kind,
                        "cat": cat,
                        "merchant": str(raw.get("merchant") or "")[:50],
                        "note": str(raw.get("note") or "")[:100],
                        "conf": {k: score(conf.get(k)) for k in ("date", "amount", "kind", "cat")},
                        "missing": missing,
                        "hint": "這一筆有欄位抽不到，補上才能存" if missing else "",
                    })
                return {"raw": text, "items": items,
                        "note": "這段話被切成 %d 筆。切分本身也是模型的判斷，請對照原句檢查。" % len(items)}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/nlp/parse-batch
        3. 按右上角 Authorize，貼上登入拿到的 accessToken；backend/.env 的 MODEL_BASE_URL 先留空
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               text 填「早餐55，午餐120」（MODEL_BASE_URL 留空）  → 503
               text 填三個空白                                    → 422
        5. MODEL_BASE_URL 填好、重開 uvicorn，再試同一段 → 200，items 有兩筆，cat 都是「餐飲」的 id
        6. 試一段沒有金額的「晚上加油」→ 那一筆 amount 是 null、missing 有 "amount"
        7. 前端改成連你的後端（frontend/index.html 的 api-base），記帳頁「段落記帳」貼一段話按解析，表格要照 missing、conf 標紅標黃
        8. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "parse_batch and u4f60" -v，要全部通過
           （u4f60 是標籤「你的」的跳脫碼。pytest 會把中文標籤轉成跳脫碼，
            -k 直接打中文比不到任何測試，會印出 0 selected）
    """
    raise not_ready("POST /api/nlp/parse-batch", OWNER)


@router.post("/nlp/confirm", status_code=201, summary="單筆確認後寫入")
@block_admin
@stub
def confirm_one(body: ConfirmIn, me: User, db: Session = Depends(get_db)):
    """單筆確認後寫入

    POST /api/nlp/confirm

    【這支做什麼】
        單句版的確認寫入：使用者確認（或改過）解析結果之後，寫進 transactions，source 記 "nlp"。
        跟 POST /api/transactions 幾乎一樣（帳本、分類、通知的規則都一樣），多做一件事：
        寫一列 nlp_parses——原句、模型當下的輸出（orig）、使用者改了哪些欄位（user_corrected）。
        那就是模型的評測資料（資料飛輪的入口）。

    【前端怎麼打】
        frontend/js/api.js 的 API.nlpConfirm(body)
        目前沒有畫面在用（段落版已經涵蓋）。回應是新建立的那一筆，形狀跟收支明細的一筆一樣。

    【誰能打】
        登入、沒被停權、不是平台管理員。上面的 @block_admin 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【請求主體】body 是 ConfirmIn（app/schemas/nlp.py）
        欄位                                              型別  必填  說明
        date／amount／kind／cat／merchant／note／groupId  |     跟 POST /api/transactions 一模一樣（使用者確認後的值）
        raw                                               字串  否    原句，寫進 nlp_parses.raw_text
        conf                                              數字  否    模型對金額的信心度（0～1）
        catConf                                           數字  否    模型對分類的信心度（0～1）
        orig                                              物件  否    解析當下的原始結果 {by, date, amount, kind, cat, merchant, note}；by 是 "model" 或 "rules"
        範例：
            {"date": "2026-09-17", "amount": 60, "kind": "expense", "cat": "1", "raw": "早餐55",
             "conf": 0.99, "catConf": 0.9,
             "orig": {"by": "model", "date": "2026-09-17", "amount": 55, "kind": "expense", "cat": "1"}}
        ⚠️ orig 是前端送來的，只當評測資料，**不影響**寫進 transactions 的內容。
        ⚠️ orig.by 是 "rules"：那是後端還沒接上時前端規則解析的，不能算成模型的成績——model_ver 記 "rules"，算正確率時濾掉。

    【成功回應】狀態碼 201
        {"id": "12", "user": "3", "date": "2026-09-17", "amount": 60, "group": "5", "kind": "expense",
         "cat": "1", "source": "nlp", "merchant": "", "note": "", "raw": "早餐55",
         "parsed": {"conf": 0.99, "catConf": 0.9}}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                                          detail
        400     分類找不到、或收支對不上                          找不到這個分類／「薪資」是收入分類，跟這筆的收支對不上
        404     groupId 不存在、移除、或我不在裡面                找不到這本帳
        409     groupId 那本已經結算                              這本帳已經結算，不能再記新的帳。請換一本帳本
        409     沒帶 groupId，也沒有能記的帳本                    你還沒有可以記帳的帳本，先到「帳本」開一本
        422     date 格式不對                                     日期要是 YYYY-MM-DD
        422     amount ≤ 0、kind 不對、orig.by 不是 model／rules  （FastAPI 自動回）

    【會用到的資料表】
        表                     讀／寫  用來做什麼
        group_members、groups  讀      決定記在哪本帳（同 POST /api/transactions）
        categories             讀      分類檢查
        guardianships          讀      誰在照看我（要通知）
        transactions           寫      新增這一筆，source = "nlp"
        nlp_parses             寫      原句、模型輸出、使用者改了什麼、信心度、模型版本
        notifications          寫      通知照看我的人、這本帳有開通知的人

    【每一步用的工具與資料庫方法】（跟 POST /api/transactions 一樣的就不重複，只列多出來的）
        步驟        呼叫                                                  做什麼
        5 評測資料  body.orig.model_dump()                                orig 轉成 dict（沒送是 None）
                    {k: v for k, v in final.items() if orig.get(k) != v}  使用者改過的欄位＝跟 orig 不一樣的那幾個；一樣都沒改就存 None
                    settings.model_name                                   模型版本（backend/.env 的 MODEL_NAME），換模型才分得開成績
                    crud.save(NlpParse, {…}, db=db)                       新增一列解析紀錄，transaction_id 指向剛剛那一筆

    【寫法步驟】
        1. 檢查日期（422）
        2. 決定帳本（同 POST /api/transactions：404／409）
        3. 檢查分類（400）
        4. 新增 transactions，source = "nlp"
        5. 新增 nlp_parses：raw_text = raw、parsed_json = orig、user_corrected = 改過的欄位、
           confidence = conf、cat_confidence = catConf、model_ver = orig.by 是 rules 就記 "rules"，不然記模型名稱
        6. 新增通知（同 POST /api/transactions）
        7. db.commit()，回傳這一筆（多帶 raw 與 parsed）
        ⚠️ 全部帶 db=db，最後才 commit：交易、解析紀錄、通知要嘛一起成功、要嘛一起不見。

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import date, datetime, timedelta, timezone

            from fastapi import APIRouter, Depends
            from sqlalchemy.orm import Session

            from app.guards import block_admin
            from app.models import Category, Group, GroupMember, Guardianship, NlpParse, Notification, Transaction, User
            from app.routers._stub import not_ready, stub
            from app.schemas.nlp import ConfirmBatchIn, ConfirmIn, ParseIn
            from app.services.llm import client, parse
            from app.toolkit import crud, errors, ledger, money, notify
            from app.toolkit.config import settings
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 檢查日期格式
            try:
                occurred_on = date.fromisoformat(body.date)
            except ValueError:
                raise errors.unprocessable("日期要是 YYYY-MM-DD") from None

            # 2. 決定這筆記在哪本帳（規則跟 POST /api/transactions 一樣）
            my_groups = crud.find(GroupMember, {"user_id": me.id}, fields="group_id", db=db)
            if body.groupId:
                group_id = int(body.groupId) if body.groupId.isdigit() else 0
                group = crud.get(Group, where={"id": group_id, "id__in": my_groups,
                                               "removed_at__isnull": True}, db=db)
                if group is None:
                    raise errors.not_found("找不到這本帳")
                try:
                    ledger.require_open(group.settled_at)
                except ValueError as exc:
                    raise errors.conflict(str(exc) + "。請換一本帳本") from None
            else:
                group = crud.get(Group, where={"id__in": my_groups, "removed_at__isnull": True,
                                               "archived_at__isnull": True, "settled_at__isnull": True},
                                 order_by="id", db=db)
                if group is None:
                    raise errors.conflict("你還沒有可以記帳的帳本，先到「帳本」開一本")

            # 3. 檢查分類
            category_id = int(body.cat) if body.cat.isdigit() else 0
            category = crud.get(Category, where={
                "id": category_id,
                "or": [{"family_id__isnull": True}, {"family_id": me.family_id}],
            }, db=db)
            if category is None:
                raise errors.bad_request("找不到這個分類")
            if category.kind != body.kind:
                side = "收入" if category.kind == "income" else "支出"
                raise errors.bad_request("「%s」是%s分類，跟這筆的收支對不上" % (category.name, side))

            # 4. 新增一列 transactions（source 一定是 nlp）
            tx = crud.save(Transaction, {
                "user_id": me.id,
                "group_id": group.id,
                "family_id": me.family_id,
                "category_id": category.id,
                "kind": body.kind,
                "amount": money.quantize(body.amount),
                "occurred_on": occurred_on,
                "merchant": body.merchant.strip() or None,
                "note": body.note.strip() or None,
                "source": "nlp",
            }, db=db)

            # 5. 新增一列 nlp_parses：模型當下怎麼解析、使用者改了哪些欄位
            final = {"date": body.date, "amount": body.amount, "kind": body.kind, "cat": body.cat,
                     "merchant": body.merchant, "note": body.note}
            orig = body.orig.model_dump() if body.orig else None
            corrected = None
            if orig is not None:
                corrected = {k: v for k, v in final.items() if orig.get(k) != v} or None
            crud.save(NlpParse, {
                "transaction_id": tx.id,
                "user_id": me.id,
                "raw_text": body.raw,
                "parsed_json": orig,
                "user_corrected": corrected,
                "confidence": body.conf,
                "cat_confidence": body.catConf,
                "model_ver": "rules" if orig and orig["by"] == "rules" else settings.model_name,
            }, db=db)

            # 6. 新增通知（跟 POST /api/transactions 一樣）
            guardians = crud.find(Guardianship, {"ward_id": me.id, "ended_at__isnull": True}, db=db)
            members = crud.find(GroupMember, {"group_id": group.id}, db=db)
            rows = []
            for user_id, reason in notify.recipients_for(tx, guardians, members):
                rows.append({
                    "recipient_id": user_id,
                    "actor_id": me.id,
                    "transaction_id": tx.id,
                    "type": "ward_transaction" if reason == notify.GUARDIAN else "group_transaction",
                    "payload_json": {"reason": reason},
                })
            if rows:
                crud.save(Notification, rows, db=db)

            # 7. 一起寫進資料庫，回傳這一筆
            db.commit()
            out = crud.to_dict(
                tx,
                fields=("id", "user_id", "occurred_on", "amount", "group_id", "kind", "category_id", "source"),
                rename={"user_id": "user", "occurred_on": "date", "group_id": "group", "category_id": "cat"},
            )
            out["merchant"] = tx.merchant or ""
            out["note"] = tx.note or ""
            out["raw"] = body.raw
            out["parsed"] = {"conf": body.conf, "catConf": body.catConf}
            return out

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/nlp/confirm
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               正常送一筆（帶 raw、orig）       → 201，source 是 "nlp"
               amount 改成跟 orig 不一樣再送    → 201，nlp_parses 那一列的 user_corrected 只有 amount
               orig.by 填 "rules"               → 201，nlp_parses 那一列的 model_ver 是 "rules"
               cat 填收入分類、kind 填 expense  → 400
        5. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "confirm_one and u4f60" -v，要全部通過
           （u4f60 是標籤「你的」的跳脫碼。pytest 會把中文標籤轉成跳脫碼，
            -k 直接打中文比不到任何測試，會印出 0 selected）
    """
    raise not_ready("POST /api/nlp/confirm", OWNER)


@router.post("/nlp/confirm-batch", status_code=201, summary="批次確認後一次寫入")
@block_admin
@stub
def confirm_batch(body: ConfirmBatchIn, me: User, db: Session = Depends(get_db)):
    """批次確認後一次寫入

    POST /api/nlp/confirm-batch

    【這支做什麼】
        段落記帳的確認寫入：使用者檢查、修改完整張表，按「確認並寫入 N 筆」，這支一次寫進去。
        ⚠️ 全部成功或全部不寫：先把每一筆都檢查完，再在同一個交易裡寫。
           寫到第 3 筆才失敗的話，前 2 筆已經進去了，使用者看到「寫入失敗」會再按一次——變成重複記帳。
        每一筆同時寫一列 nlp_parses（原句 span、模型當下的輸出 orig、使用者改了哪些欄位）。

    【前端怎麼打】
        frontend/js/api.js 的 API.nlpConfirmBatch(items)
        記帳頁「確認並寫入 N 筆」按下去時呼叫，主體是 {"items": [...]}。回 {"created": N}，前端清掉表格、重拿明細。

    【誰能打】
        登入、沒被停權、不是平台管理員。上面的 @block_admin 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【請求主體】body 是 ConfirmBatchIn（app/schemas/nlp.py）：{"items": [BatchItem, …]}，至少一筆
        BatchItem 欄位                           型別  必填  說明
        span                                     字串  否    原句裡對應的那一段，寫進 nlp_parses.raw_text
        date／amount／kind／cat／merchant／note  |     使用者確認後的值，規則同 POST /api/transactions
        conf                                     物件  否    {date, amount, kind, cat} 各欄信心度
        groupId                                  字串  否    **只看第一筆的**：整批記進同一本帳；沒帶就記進第一本還能記的
        orig                                     物件  否    解析當下的原始結果，by 是 "model" 或 "rules"
        範例：
            {"items": [{"span": "早上買早餐55", "date": "2026-09-17", "amount": 55, "kind": "expense", "cat": "1",
                        "groupId": "5", "conf": {"date": 0.9, "amount": 0.99, "kind": 0.97, "cat": 0.9},
                        "orig": {"by": "model", "date": "2026-09-17", "amount": 55, "kind": "expense", "cat": "8"}}]}
        · 前端還會多送 seq、missing、hint，BatchItem 沒有這幾欄，FastAPI 會直接忽略（不是 PatchIn，沒有 extra="forbid"）
        · 空的 items FastAPI 自動回 422

    【成功回應】狀態碼 201
        {"created": 3}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                                     detail
        400     第 N 筆的分類找不到、或收支對不上            第 2 筆：找不到這個分類
        404     第一筆的 groupId 不存在、移除、或我不在裡面  找不到這本帳
        409     那本帳已經結算／一本能記的都沒有             （同 POST /api/transactions）
        422     第 N 筆的日期格式不對                        第 2 筆的日期要是 YYYY-MM-DD
        422     items 是空的、某一筆 amount ≤ 0、kind 不對   （FastAPI 自動回）
        · 有任何一筆錯，整批一筆都不寫。訊息講清楚是第幾筆，使用者才知道要改哪一列。

    【會用到的資料表】
        表                     讀／寫  用來做什麼
        group_members、groups  讀      決定整批記在哪本帳
        categories             讀      一次查出系統的＋我們家的分類，逐筆比對
        guardianships          讀      誰在照看我
        transactions           寫      每一筆一列，source = "nlp"
        nlp_parses             寫      每一筆一列評測資料
        notifications          寫      每一筆 × 每個要通知的人

    【每一步用的工具與資料庫方法】
        步驟    呼叫                                                       做什麼
        1 帳本  body.items[0].groupId                                      只看第一筆的 groupId
                crud.get(Group, where={…}, db=db)／ledger.require_open(…)  同 POST /api/transactions
        2 分類  {c.id: c for c in crud.find(Category, {"or": [系統的, 我們家的]}, db=db)}  一次查完做成對照表，不要每一筆查一次
                enumerate(body.items, 1)                                   一邊跑一邊數第幾筆（從 1 開始），錯誤訊息要用
        3 寫入  crud.save(Transaction, {…}, db=db)                         每一筆一列（還沒 commit）
                crud.save(NlpParse, {…}, db=db)                            每一筆一列評測資料
                notify.recipients_for(tx, guardians, members)              每一筆要通知誰；照看我的人、帳本成員只要查一次
                crud.save(Notification, rows, db=db)                       通知最後一次存
        4 存檔  db.commit()                                                全部檢查、全部寫好，最後才 commit

    【寫法步驟】
        1. 用第一筆的 groupId 決定帳本（404／409）
        2. 一次查出分類對照表；逐筆檢查日期（422）與分類（400），錯了馬上停——這時候還一筆都沒寫
        3. 查一次照看我的人、這本帳的成員
        4. 逐筆寫 transactions（source = nlp）＋ nlp_parses，收集要發的通知
        5. 一次寫通知，db.commit()，回傳 {"created": 筆數}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import date, datetime, timedelta, timezone

            from fastapi import APIRouter, Depends
            from sqlalchemy.orm import Session

            from app.guards import block_admin
            from app.models import Category, Group, GroupMember, Guardianship, NlpParse, Notification, Transaction, User
            from app.routers._stub import not_ready, stub
            from app.schemas.nlp import ConfirmBatchIn, ConfirmIn, ParseIn
            from app.services.llm import client, parse
            from app.toolkit import crud, errors, ledger, money, notify
            from app.toolkit.config import settings
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 決定整批記在哪本帳：只看第一筆的 groupId
            wanted = body.items[0].groupId
            my_groups = crud.find(GroupMember, {"user_id": me.id}, fields="group_id", db=db)
            if wanted:
                group_id = int(wanted) if wanted.isdigit() else 0
                group = crud.get(Group, where={"id": group_id, "id__in": my_groups,
                                               "removed_at__isnull": True}, db=db)
                if group is None:
                    raise errors.not_found("找不到這本帳")
                try:
                    ledger.require_open(group.settled_at)
                except ValueError as exc:
                    raise errors.conflict(str(exc) + "。請換一本帳本") from None
            else:
                group = crud.get(Group, where={"id__in": my_groups, "removed_at__isnull": True,
                                               "archived_at__isnull": True, "settled_at__isnull": True},
                                 order_by="id", db=db)
                if group is None:
                    raise errors.conflict("你還沒有可以記帳的帳本，先到「帳本」開一本")

            # 2. 每一筆先檢查完；有一筆不對，整批一筆都不寫
            cats = {c.id: c for c in crud.find(Category, {
                "or": [{"family_id__isnull": True}, {"family_id": me.family_id}]}, db=db)}
            checked = []
            for n, item in enumerate(body.items, 1):
                try:
                    occurred_on = date.fromisoformat(item.date)
                except ValueError:
                    raise errors.unprocessable("第 %d 筆的日期要是 YYYY-MM-DD" % n) from None
                category = cats.get(int(item.cat) if item.cat.isdigit() else 0)
                if category is None:
                    raise errors.bad_request("第 %d 筆：找不到這個分類" % n)
                if category.kind != item.kind:
                    side = "收入" if category.kind == "income" else "支出"
                    raise errors.bad_request("第 %d 筆：「%s」是%s分類，跟這筆的收支對不上" % (n, category.name, side))
                checked.append((item, occurred_on, category))

            # 3. 全部過了才寫：每一筆一列 transactions ＋ 一列 nlp_parses
            guardians = crud.find(Guardianship, {"ward_id": me.id, "ended_at__isnull": True}, db=db)
            members = crud.find(GroupMember, {"group_id": group.id}, db=db)
            notes = []
            for item, occurred_on, category in checked:
                tx = crud.save(Transaction, {
                    "user_id": me.id,
                    "group_id": group.id,
                    "family_id": me.family_id,
                    "category_id": category.id,
                    "kind": item.kind,
                    "amount": money.quantize(item.amount),
                    "occurred_on": occurred_on,
                    "merchant": item.merchant.strip() or None,
                    "note": item.note.strip() or None,
                    "source": "nlp",
                }, db=db)
                final = {"date": item.date, "amount": item.amount, "kind": item.kind, "cat": item.cat,
                         "merchant": item.merchant, "note": item.note}
                orig = item.orig.model_dump() if item.orig else None
                corrected = None
                if orig is not None:
                    corrected = {k: v for k, v in final.items() if orig.get(k) != v} or None
                conf = item.conf.model_dump() if item.conf else {}
                crud.save(NlpParse, {
                    "transaction_id": tx.id,
                    "user_id": me.id,
                    "raw_text": item.span,
                    "parsed_json": orig,
                    "user_corrected": corrected,
                    "confidence": conf.get("amount"),
                    "cat_confidence": conf.get("cat"),
                    "model_ver": "rules" if orig and orig["by"] == "rules" else settings.model_name,
                }, db=db)
                for user_id, reason in notify.recipients_for(tx, guardians, members):
                    notes.append({
                        "recipient_id": user_id,
                        "actor_id": me.id,
                        "transaction_id": tx.id,
                        "type": "ward_transaction" if reason == notify.GUARDIAN else "group_transaction",
                        "payload_json": {"reason": reason},
                    })

            # 4. 通知一次寫，全部一起存進資料庫
            if notes:
                crud.save(Notification, notes, db=db)
            db.commit()
            return {"created": len(checked)}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/nlp/confirm-batch
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               送兩筆正確的                  → 201，{"created": 2}，明細多兩筆、source 都是 nlp
               第二筆的 cat 填收入分類       → 400「第 2 筆：…」，而且第一筆也沒寫進去
               第二筆的 date 填 9/17         → 422「第 2 筆的日期…」
               第一筆帶一本結算過的 groupId  → 409
        5. 照看你的家長打 GET /api/notifications → 兩筆各一則通知
        6. 前端改成連你的後端（frontend/index.html 的 api-base），記帳頁貼一段話、解析、改一格、按「確認並寫入」，收支明細要出現那幾筆
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "confirm_batch and u4f60" -v，要全部通過
           （u4f60 是標籤「你的」的跳脫碼。pytest 會把中文標籤轉成跳脫碼，
            -k 直接打中文比不到任何測試，會印出 0 selected）
    """
    raise not_ready("POST /api/nlp/confirm-batch", OWNER)
