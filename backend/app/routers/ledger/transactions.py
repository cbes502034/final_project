"""
收支明細：查、記、改、刪。

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
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.guards import block_admin, current_user, own, visible_scope
from app.models import Category, Group, GroupMember, Guardianship, NlpParse, Notification, Transaction, User
from app.routers._stub import not_ready, stub
from app.schemas.transaction import TransactionIn, TransactionPatchIn
from app.toolkit import crud, errors, ledger, money, notify
from app.toolkit.db import get_db

router = APIRouter(tags=["記帳"])
OWNER = "成員2"


@router.get("/transactions", summary="收支明細")
@block_admin
# @stub
def list_transactions(
    me: User,
    request: Request,
    userId: str | None = None,
    groupId: str | None = None,
    from_: str | None = Query(None, alias="from"),
    to: str | None = None,
    categoryId: str | None = None,
    kind: str | None = None,
    source: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    """收支明細

    GET /api/transactions

    【這支做什麼】
        列出「我看得到的」收支明細，可以篩人、帳本、日期、分類、收支、來源、關鍵字。
        看得到的範圍是兩條路的「或」（聯集）：
            A. 這筆是誰記的：我自己、我照看的人、同家庭的另一位家長（跨所有帳本）
            B. 這筆記在哪本帳：我有加入的帳本
        ⚠️ 一定是「或」。寫成兩個條件都要成立（且），監管就能被「另外開一本帳」繞過。

    【前端怎麼打】
        frontend/js/api.js 的 API.transactions({ userId, groupId, from, to, categoryId, kind, source, q, page })
        用在：收支明細頁、總覽的「今天的紀錄」（from = to = 今天）、成員紀錄頁（userId = 那個人）。
        前端檢查回應裡一定要有 transactions 和 total。

    【誰能打】
        登入、沒被停權、不是平台管理員。上面的 @block_admin 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【查詢參數】（都放在網址 ? 後面，全部可以不帶）
        參數        型別  說明
        userId      字串  只看某個人。要是我查得到的人（看得到的人 ＋ 跟我同帳本的人），不然 403
        groupId     字串  只看某一本帳。all 等於沒帶。要是我加入的帳本，不然 403
        from／to    字串  日期範圍 YYYY-MM-DD，兩端都包含。程式裡叫 from_（from 是 Python 的保留字）
        categoryId  字串  只看某個分類
        kind        字串  income／expense／transfer。all 等於沒帶
        source      字串  manual／nlp／import。all 等於沒帶
        q           字串  關鍵字，比對店家與備註（不分大小寫）
        page        整數  第幾頁，從 1 開始，一頁 200 筆。0 或負數 FastAPI 自動回 422
        範例：GET /api/transactions?userId=3&from=2026-09-01&to=2026-09-30
        ⚠️ 不認得的參數（例如打錯成 user=3）要回 422，不要默默忽略——忽略的話「篩選沒生效」完全看不出來。
           所以函式多收一個 request，用 request.query_params 拿到網址上所有的參數名字來比。

    【成功回應】狀態碼 200
        {"transactions": [
           {"id": "12", "user": "3", "date": "2026-09-17", "amount": 320, "group": "5", "kind": "expense",
            "cat": "1", "source": "nlp", "merchant": "自助餐", "note": "午餐",
            "raw": "中午自助餐320", "parsed": {"conf": 0.97, "catConf": 0.95}}
         ],
         "total": 14}
        · 新的在前（日期新的在前；同一天，後記的在前）
        · total 是符合條件的「全部」筆數，不是這一頁的筆數
        · raw、parsed 只有段落記帳的才有意義；手動記的回 raw: ""、parsed: {"conf": 1, "catConf": 1}
        · 不用回 userName、catName、catColor，前端會自己用 user、cat 對照補上

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                     detail
        403     userId 是我查不到的人        你沒有權限看這個人的紀錄
        403     groupId 是我沒加入的帳本     你不在這本帳裡
        422     網址上有不認得的參數         不認得的篩選參數：user
        422     from／to 格式不對            日期要是 YYYY-MM-DD
        422     kind、source 不是清單裡的值  kind 只能是 income、expense 或 transfer
        ⚠️ 沒權限要回 403，不要回空陣列：回空的，畫面會以為「這個人這個月沒記帳」。

    【會用到的資料表】
        表                                                    讀／寫  用來做什麼
        guardianships、family_members、group_members、groups  讀      visible_scope() 幫你查：我看得到誰、看得到哪幾本帳
        group_members                                         讀      帶 userId 時：跟我同帳本的有誰
        transactions                                          讀      明細本身
        nlp_parses                                            讀      段落記帳的原句（raw_text）與信心度

    【每一步用的工具與資料庫方法】（crud 在 app/toolkit/crud.py，visible_scope 在 app/guards.py）
        步驟         呼叫                                                          做什麼
        1 擋怪參數   request.query_params                                          網址上所有的 ?參數，轉成 set 跟允許的清單相減
                     errors.unprocessable("…")                                     回 422
        2 可見範圍   users, groups = visible_scope(me, db)                         回傳兩個 set：看得到的人的 id、看得到的帳本 id
                     {"or": [{"user_id__in": users}, {"group_id__in": groups}]}    兩條路用 "or" 串起來
        3 擋 userId  crud.find(GroupMember, {"group_id__in": groups}, fields="user_id", db=db)  跟我同帳本的人，回傳 [3, 5, …]
                     errors.forbidden("…")                                         回 403
        5 篩日期     date.fromisoformat(from_)                                     字串轉日期，格式不對丟 ValueError
                     "occurred_on__gte"／"occurred_on__lte"                        大於等於／小於等於（兩端都包含）
                     {"or": [{"merchant__icontains": q}, {"note__icontains": q}]}  關鍵字：店家或備註包含（不分大小寫）
        6 查         crud.find(Transaction, where, order_by=("-occurred_on", "-id"), page=page, size=200, db=db)  帶 page 會回 {"items", "total", "page", "size", "pages"}
        7 原句       crud.find(NlpParse, {"transaction_id__in": [...]}, db=db)     這一頁裡有解析紀錄的那幾筆
        8 轉形狀     crud.to_dict(t, fields=(…), rename={…})                       id 轉字串、金額轉數字、欄位改成前端的名字
        ⚠️ where 裡已經有一個 "or"（可見範圍），關鍵字又要一個 "or"——dict 不能有兩個一樣的鍵，
           所以把它們都放進 "and" 的清單裡：{"and": [{"or": 可見範圍}, {"or": 關鍵字}]}。

    【寫法步驟】
        1. 擋掉網址上不認得的參數（422）
        2. visible_scope 拿到看得到的人與帳本，條件先放「A 或 B」
        3. 帶了 userId：要在「看得到的人」或「同帳本的人」裡面，不然 403；然後加上 user_id = 他
        4. 帶了 groupId：要在我加入的帳本裡，不然 403；然後加上 group_id = 那本
        5. 其他篩選：日期、分類、收支、來源、關鍵字
        6. 查一頁（新的在前）
        7. 段落記帳的那幾筆，一次把 nlp_parses 查回來
        8. 一筆一筆轉成前端要的樣子，回傳 transactions 與 total
        ⚠️ 這支只讀不寫，不用 db.commit()。

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import date, datetime, timezone

            from fastapi import APIRouter, Depends, Query, Request
            from sqlalchemy.orm import Session

            from app.guards import block_admin, current_user, own, visible_scope
            from app.models import Category, Group, GroupMember, Guardianship, NlpParse, Notification, Transaction, User
            from app.routers._stub import not_ready, stub
            from app.schemas.transaction import TransactionIn, TransactionPatchIn
            from app.toolkit import crud, errors, ledger, money, notify
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 不認得的查詢參數直接擋（默默忽略的話，篩選沒生效也看不出來）
            allowed = {"userId", "groupId", "from", "to", "categoryId", "kind", "source", "q", "page"}
            unknown = sorted(set(request.query_params) - allowed)
            if unknown:
                raise errors.unprocessable("不認得的篩選參數：" + "、".join(unknown))

            # 2. 我看得到的人、看得到的帳本；兩條路一定是「或」
            users, groups = visible_scope(me, db)
            where = {"and": [{"or": [{"user_id__in": users}, {"group_id__in": groups}]}]}

            # 3. 帶了 userId：要是我查得到的人，不然 403（不要回空陣列）
            if userId and userId != "all":
                target = int(userId) if userId.isdigit() else 0
                members = crud.find(GroupMember, {"group_id__in": groups}, fields="user_id", db=db)
                if target not in users and target not in members:
                    raise errors.forbidden("你沒有權限看這個人的紀錄")
                where["user_id"] = target

            # 4. 帶了 groupId：要是我加入的帳本
            if groupId and groupId != "all":
                group_id = int(groupId) if groupId.isdigit() else 0
                if group_id not in groups:
                    raise errors.forbidden("你不在這本帳裡")
                where["group_id"] = group_id

            # 5. 其他篩選
            try:
                if from_:
                    where["occurred_on__gte"] = date.fromisoformat(from_)
                if to:
                    where["occurred_on__lte"] = date.fromisoformat(to)
            except ValueError:
                raise errors.unprocessable("日期要是 YYYY-MM-DD") from None
            if categoryId:
                where["category_id"] = int(categoryId) if categoryId.isdigit() else 0
            if kind and kind != "all":
                if kind not in ("income", "expense", "transfer"):
                    raise errors.unprocessable("kind 只能是 income、expense 或 transfer")
                where["kind"] = kind
            if source and source != "all":
                if source not in ("manual", "nlp", "import"):
                    raise errors.unprocessable("source 只能是 manual、nlp 或 import")
                where["source"] = source
            if q and q.strip():
                word = q.strip()
                where["and"].append({"or": [{"merchant__icontains": word}, {"note__icontains": word}]})

            # 6. 查一頁：新的在前，一頁 200 筆
            result = crud.find(Transaction, where, order_by=("-occurred_on", "-id"), page=page, size=200, db=db)
            rows = result["items"]

            # 7. 段落記帳的那幾筆，一次把原句與信心度查回來
            parses = {}
            if rows:
                for p in crud.find(NlpParse, {"transaction_id__in": [t.id for t in rows]}, db=db):
                    parses[p.transaction_id] = p

            # 8. 轉成前端要的樣子
            out = []
            for t in rows:
                item = crud.to_dict(
                    t,
                    fields=("id", "user_id", "occurred_on", "amount", "group_id", "kind", "category_id", "source"),
                    rename={"user_id": "user", "occurred_on": "date", "group_id": "group", "category_id": "cat"},
                )
                item["merchant"] = t.merchant or ""
                item["note"] = t.note or ""
                p = parses.get(t.id)
                item["raw"] = p.raw_text if p else ""
                if p:
                    item["parsed"] = {"conf": float(p.confidence or 0), "catConf": float(p.cat_confidence or 0)}
                else:
                    item["parsed"] = {"conf": 1, "catConf": 1}
                out.append(item)
            return {"transactions": out, "total": result["total"]}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 GET /api/transactions
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               什麼都不帶                     → 200，只有自己、照看的人、同帳本的紀錄
               userId 填一個跟你毫無關係的人  → 403
               網址後面自己加 &user=3         → 422
               from=2026-09-01&to=2026-09-01  → 只剩那一天的
               q 填店家名字的一部分           → 只剩店家或備註有那幾個字的
        5. 照看孩子的家長登入，userId 填孩子 → 孩子記在任何一本帳的紀錄都看得到
        6. 前端改成連你的後端（frontend/index.html 的 api-base），收支明細頁的篩選一個一個試，結果要跟條件一致
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "list_transactions and 你的"，要全部通過
    """


    from datetime import date, datetime, timezone

    from fastapi import APIRouter, Depends, Query, Request
    from sqlalchemy.orm import Session

    from app.guards import block_admin, current_user, own, visible_scope
    from app.models import Category, Group, GroupMember, Guardianship, NlpParse, Notification, Transaction, User
    from app.routers._stub import not_ready, stub
    from app.schemas.transaction import TransactionIn, TransactionPatchIn
    from app.toolkit import crud, errors, ledger, money, notify
    from app.toolkit.db import get_db


    # 1. 不認得的查詢參數直接擋（默默忽略的話，篩選沒生效也看不出來）
    allowed = {"userId", "groupId", "from", "to", "categoryId", "kind", "source", "q", "page"}
    unknown = sorted(set(request.query_params) - allowed)
    if unknown:
        raise errors.unprocessable("不認得的篩選參數：" + "、".join(unknown))

    # 2. 我看得到的人、看得到的帳本；兩條路一定是「或」
    users, groups = visible_scope(me, db)
    where = {"and": [{"or": [{"user_id__in": users}, {"group_id__in": groups}]}]}

    # 3. 帶了 userId：要是我查得到的人，不然 403（不要回空陣列）
    if userId and userId != "all":
        target = int(userId) if userId.isdigit() else 0
        members = crud.find(GroupMember, {"group_id__in": groups}, fields="user_id", db=db)
        if target not in users and target not in members:
            raise errors.forbidden("你沒有權限看這個人的紀錄")
        where["user_id"] = target

    # 4. 帶了 groupId：要是我加入的帳本
    if groupId and groupId != "all":
        group_id = int(groupId) if groupId.isdigit() else 0
        if group_id not in groups:
            raise errors.forbidden("你不在這本帳裡")
        where["group_id"] = group_id

    # 5. 其他篩選
    try:
        if from_:
            where["occurred_on__gte"] = date.fromisoformat(from_)
        if to:
            where["occurred_on__lte"] = date.fromisoformat(to)
    except ValueError:
        raise errors.unprocessable("日期要是 YYYY-MM-DD") from None
    if categoryId:
        where["category_id"] = int(categoryId) if categoryId.isdigit() else 0
    if kind and kind != "all":
        if kind not in ("income", "expense", "transfer"):
            raise errors.unprocessable("kind 只能是 income、expense 或 transfer")
        where["kind"] = kind
    if source and source != "all":
        if source not in ("manual", "nlp", "import"):
            raise errors.unprocessable("source 只能是 manual、nlp 或 import")
        where["source"] = source
    if q and q.strip():
        word = q.strip()
        where["and"].append({"or": [{"merchant__icontains": word}, {"note__icontains": word}]})

    # 6. 查一頁：新的在前，一頁 200 筆
    result = crud.find(Transaction, where, order_by=("-occurred_on", "-id"), page=page, size=200, db=db)
    rows = result["items"]

    # 7. 段落記帳的那幾筆，一次把原句與信心度查回來
    parses = {}
    if rows:
        for p in crud.find(NlpParse, {"transaction_id__in": [t.id for t in rows]}, db=db):
            parses[p.transaction_id] = p

    # 8. 轉成前端要的樣子
    out = []
    for t in rows:
        item = crud.to_dict(
            t,
            fields=("id", "user_id", "occurred_on", "amount", "group_id", "kind", "category_id", "source"),
            rename={"user_id": "user", "occurred_on": "date", "group_id": "group", "category_id": "cat"},
        )
        item["merchant"] = t.merchant or ""
        item["note"] = t.note or ""
        p = parses.get(t.id)
        item["raw"] = p.raw_text if p else ""
        if p:
            item["parsed"] = {"conf": float(p.confidence or 0), "catConf": float(p.cat_confidence or 0)}
        else:
            item["parsed"] = {"conf": 1, "catConf": 1}
        out.append(item)
    return {"transactions": out, "total": result["total"]}
    # raise not_ready("GET /api/transactions", OWNER)


@router.post("/transactions", status_code=201, summary="手動新增一筆")
@block_admin
# @stub
def create_transaction(body: TransactionIn, me: User, db: Session = Depends(get_db)):
    


    from datetime import date, datetime, timezone

    from fastapi import APIRouter, Depends, Query, Request
    from sqlalchemy.orm import Session

    from app.guards import block_admin, current_user, own, visible_scope
    from app.models import Category, Group, GroupMember, Guardianship, NlpParse, Notification, Transaction, User
    from app.routers._stub import not_ready, stub
    from app.schemas.transaction import TransactionIn, TransactionPatchIn
    from app.toolkit import crud, errors, ledger, money, notify
    from app.toolkit.db import get_db

    # 1. 檢查日期格式
    try:
        occurred_on = date.fromisoformat(body.date)
    except ValueError:
        raise errors.unprocessable("日期要是 YYYY-MM-DD") from None

    # 2. 決定這筆記在哪本帳
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

    # 4. 新增一列 transactions（source 一定是 manual）
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
        "source": "manual",
    }, db=db)

    # 5. 新增通知
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

    # 6. 一起寫進資料庫，回傳成功回應
    db.commit()
    out = crud.to_dict(
        tx,
        fields=("id", "user_id", "occurred_on", "amount", "group_id", "kind", "category_id", "source"),
        rename={"user_id": "user", "occurred_on": "date", "group_id": "group", "category_id": "cat"},
    )
    out["merchant"] = tx.merchant or ""
    out["note"] = tx.note or ""
    out["raw"] = ""
    return out
    """手動新增一筆

    POST /api/transactions

    【這支做什麼】
        使用者在記帳頁用「單筆手動」填表記一筆。這支不經過模型：
        檢查資料 → 寫進 transactions → 通知該知道的人（照看他的家長、這本帳有開通知的成員）。

    【前端怎麼打】
        frontend/js/api.js 的 API.createTransaction(body)
        記帳頁「單筆手動」按下送出時呼叫。前端只檢查回應裡有沒有 id，其他欄位照下面「成功回應」回。

    【誰能打】
        登入、沒被停權、不是平台管理員。上面的 @block_admin 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【請求主體】body 是 TransactionIn（app/schemas/transaction.py），FastAPI 已經幫你檢查過型別
        欄位      型別  必填  說明
        date      字串  是    YYYY-MM-DD。只保證是字串，格式要自己檢查，不對回 422
        amount    數字  是    要大於 0。0 或負數 FastAPI 會自動回 422
        kind      字串  是    "expense"（支出）或 "income"（收入）。其他值 FastAPI 會自動回 422
        cat       字串  是    分類 id。要是系統分類或自己家的分類，而且收支要跟 kind 一樣
        merchant  字串  否    店家，沒填是空字串
        note      字串  否    備註，沒填是空字串
        groupId   字串  否    記在哪一本帳。沒填 = 自己加入的帳本裡，第一本還能記的
        範例：
            {"date": "2026-09-17", "amount": 120, "kind": "expense", "cat": "1", "merchant": "全家", "groupId": "5"}

    【成功回應】狀態碼 201
        {"id": "12", "user": "3", "date": "2026-09-17", "amount": 120, "group": "5",
         "kind": "expense", "cat": "1", "merchant": "全家", "note": "", "source": "manual", "raw": ""}
        · 所有 id 都要是字串（crud.to_dict 會自動轉）
        · 金額回數字 120，不是字串 "120.00"（crud.to_dict 會自動轉）
        · 不用回 userName、catName、catColor，前端會自己用 user、cat 對照補上

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                                      detail
        400     分類 id 不存在，或是別人家的分類              找不到這個分類
        400     分類的收支跟 kind 不一樣（支出選了薪資）      「薪資」是收入分類，跟這筆的收支對不上
        404     groupId 不存在、已經移除、或自己不在那本帳裡  找不到這本帳
        409     groupId 那本帳已經結算                        這本帳已經結算，不能再記新的帳。請換一本帳本
        409     沒填 groupId，而且一本能記的帳都沒有          你還沒有可以記帳的帳本，先到「帳本」開一本
        422     date 格式不對                                 日期要是 YYYY-MM-DD
        422     amount 小於等於 0、kind 不對                  （FastAPI 自動回，不用自己寫）
        ⚠️ 別人的帳本要回 404，不要回 403：回 403 等於告訴對方「這本帳存在」。

    【會用到的資料表】
        表             讀／寫  用來做什麼
        group_members  讀      我加入了哪幾本帳
        groups         讀      那本帳有沒有結算、封存、移除
        categories     讀      分類存不存在、是不是我家的、收支對不對
        guardianships  讀      誰在照看我（要通知他）
        transactions   寫      新增這一筆
        notifications  寫      每個要通知的人新增一列

    【每一步用的工具與資料庫方法】（crud 在 app/toolkit/crud.py，其他在 app/toolkit/ 同名檔案）
        步驟          呼叫                                                   做什麼
        1 檢查日期    date.fromisoformat(body.date)                          字串轉日期，格式不對丟 ValueError
                      errors.unprocessable("…")                              回 422
        2 決定帳本    crud.find(GroupMember, {"user_id": me.id}, fields="group_id", db=db)  查我加入的帳本 id，回傳 [5, 8, …]
                      crud.get(Group, where={"id": …, "id__in": …, "removed_at__isnull": True}, db=db)  查那一本；找不到回 None
                      crud.get(Group, where={…, "settled_at__isnull": True}, order_by="id", db=db)  沒填 groupId 時，找 id 最小、還能記的那本
                      ledger.require_open(group.settled_at)                  結算過就丟 ValueError
                      errors.not_found("…")／errors.conflict("…")            回 404／409
        3 檢查分類    crud.get(Category, where={"id": …, "or": [{"family_id__isnull": True}, {"family_id": me.family_id}]}, db=db)  查分類：系統的（family_id 是 NULL）或我家的，兩個條件用 "or" 串起來
                      errors.bad_request("…")                                回 400
        4 寫入明細    money.quantize(body.amount)                            120 → Decimal("120.00")
                      crud.save(Transaction, {…}, db=db)                     新增一列，回傳那一筆（已經有 id）
        5 寫入通知    crud.find(Guardianship, {"ward_id": me.id, "ended_at__isnull": True}, db=db)  查誰在照看我（還沒解除的）
                      crud.find(GroupMember, {"group_id": group.id}, db=db)  查這本帳的成員（有沒有開通知）
                      notify.recipients_for(tx, guardians, members)          算出要通知誰，回傳 [(user_id, 原因), …]
                      crud.save(Notification, [{…}, {…}], db=db)             一次新增很多列
        6 存檔、回傳  db.commit()                                            前面帶 db=db 的全部一起寫進去
                      crud.to_dict(tx, fields=(…), rename={…})               轉成前端要的樣子（id 轉字串、欄位改名）
        ⚠️ 為什麼每個 crud 都帶 db=db：不帶的話它會自己開連線、自己存檔，
           第 4 步存進去了、第 5 步卻失敗，就會留下「帳記了、通知沒發」的半套資料。

    【寫法步驟】
        1. 檢查日期格式
        2. 決定這筆記在哪本帳
           · 有填 groupId：找「我加入的、還沒移除的」那本 → 找不到回 404 → 結算過回 409
           · 沒填 groupId：找「我加入的、沒移除、沒封存、沒結算」裡 id 最小的那本 → 一本都沒有回 409
        3. 檢查分類：要存在、要是系統分類（family_id 是 NULL）或我家的、收支要跟 kind 一樣 → 不對回 400
        4. 新增一列 transactions：source 一定是 "manual"，金額用 money.quantize，店家與備註是空的就存 NULL
        5. 新增通知：照看我的家長 type 記 "ward_transaction"，這本帳有開通知的人記 "group_transaction"
        6. db.commit() 一起寫進資料庫，回傳成功回應
        ⚠️ 第 4、5 步的 crud.save 都帶 db=db：這樣它們不會各自存檔，要到第 6 步才一起寫進去。
           中間任何一步出錯，這一筆和通知都不會留下，不會出現「帳記了、通知沒發」的半套狀態。

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import date, datetime, timezone

            from fastapi import APIRouter, Depends, Query, Request
            from sqlalchemy.orm import Session

            from app.guards import block_admin, current_user, own, visible_scope
            from app.models import Category, Group, GroupMember, Guardianship, NlpParse, Notification, Transaction, User
            from app.routers._stub import not_ready, stub
            from app.schemas.transaction import TransactionIn, TransactionPatchIn
            from app.toolkit import crud, errors, ledger, money, notify
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 檢查日期格式
            try:
                occurred_on = date.fromisoformat(body.date)
            except ValueError:
                raise errors.unprocessable("日期要是 YYYY-MM-DD") from None

            # 2. 決定這筆記在哪本帳
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

            # 4. 新增一列 transactions（source 一定是 manual）
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
                "source": "manual",
            }, db=db)

            # 5. 新增通知
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

            # 6. 一起寫進資料庫，回傳成功回應
            db.commit()
            out = crud.to_dict(
                tx,
                fields=("id", "user_id", "occurred_on", "amount", "group_id", "kind", "category_id", "source"),
                rename={"user_id": "user", "occurred_on": "date", "group_id": "group", "category_id": "cat"},
            )
            out["merchant"] = tx.merchant or ""
            out["note"] = tx.note or ""
            out["raw"] = ""
            return out

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/transactions
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               正常記一筆                           → 201，回應裡有 id
               amount 填 0                          → 422
               cat 填一個收入分類，kind 填 expense  → 400
               groupId 填一本結算過的帳             → 409
               groupId 填一本你不在裡面的帳         → 404
        5. 照看你的家長登入，打 GET /api/notifications → 要看得到剛剛這一筆的通知
        6. 前端改成連你的後端（frontend/index.html 的 api-base），到記帳頁用「單筆手動」記一筆，收支明細要出現這一筆
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "create_transaction and 你的"，要全部通過
    """
    
    
    # raise not_ready("POST /api/transactions", OWNER)


@router.patch("/transactions/{tx_id}", summary="修改一筆")
@stub
def update_transaction(
    body: TransactionPatchIn,
    row=Depends(own(Transaction, "tx_id")),
    me: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """修改一筆

    PATCH /api/transactions/{tx_id}

    【這支做什麼】
        修改自己的一筆紀錄：只送改過的欄位，沒送的保持原樣（所以是 PATCH 不是 PUT）。
        可以改：date、amount、kind、cat、merchant、note、groupId。
        改的是段落記帳（source = nlp）的那筆時，改過的值另外記進 nlp_parses.user_corrected——
        那就是「模型抓錯了什麼」的標註，算模型正確率要用。

    【前端怎麼打】
        frontend/js/api.js 的 API.updateTransaction(id, patch)
        收支明細每一列的「修改」存檔時呼叫。前端檢查回應裡一定要有 id，拿回來的整筆直接換掉畫面上那一列。

    【誰能打】
        登入、沒被停權，而且這一筆是自己的。參數 row=Depends(own(Transaction, "tx_id")) 已經擋好了：
            沒登入 → 401；被停權 → 403
            {tx_id} 不是數字、或找不到這一筆 → 404「找不到這筆資料」
            這一筆的 user_id 不是我 → 403「這是別人的資料，你只能檢視」
        所以函式裡不用再檢查。row 就是那一筆（Transaction 物件），直接拿來用。
        另外收一個 me=Depends(current_user)（目前登入的人，User 物件）：檢查分類是不是我家的要用 me.family_id。
        ⚠️ 監管是唯讀的：家長看得到孩子的紀錄，但改不動——守衛只認「本人」。

    【請求主體】body 是 TransactionPatchIn（app/schemas/transaction.py），只送要改的
        欄位            型別  說明
        date            字串  YYYY-MM-DD
        amount          數字  大於 0（0 或負數 FastAPI 自動回 422）
        kind            字串  expense／income（其他值 FastAPI 自動回 422）
        cat             字串  分類 id，收支要對得上
        merchant／note  字串  壓掉連續空白，最多 100 字；空字串 = 清掉
        groupId         字串  換到另一本帳：要是我加入的、沒結算的
        範例：{"amount": 180, "cat": "1", "note": "午餐＋飲料"}
        · body.model_dump(exclude_unset=True) 只會拿到「有送來的」欄位——沒送的不會變成 None 把原本的值蓋掉。
        · 不認得的欄位（例如 source、user）FastAPI 直接回 422：TransactionPatchIn 設了 extra="forbid"。

    【成功回應】狀態碼 200
        改完的那一筆，形狀跟 GET /api/transactions 的一筆一樣，多一個 updatedAt：
        {"id": "12", "user": "3", "date": "2026-09-17", "amount": 180, "group": "5", "kind": "expense",
         "cat": "1", "source": "manual", "updatedAt": "2026-09-17T12:30:00+00:00",
         "merchant": "全家", "note": "午餐＋飲料", "raw": ""}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                                       detail
        400     什麼都沒送                                     沒有要改的欄位
        400     日期格式不對、cat 或 groupId 是空的、店家太長  （ledger.clean_patch 丟出來的那句話）
        400     分類找不到、或收支對不上                       找不到這個分類／「薪資」是收入分類，跟這筆的收支對不上
        403     別人的紀錄                                     這是別人的資料，你只能檢視（守衛回）
        403     groupId 換到我沒加入（或已移除）的帳本         你沒有加入這本帳
        404     找不到這一筆                                   找不到這筆資料（守衛回）
        409     這筆所在的帳本已經結算                         這本帳已經結算，裡面的紀錄不能再改或刪除
        409     groupId 換到已經結算的帳本                     這本帳已經結算，不能再記新的帳。請換一本帳本
        422     帶了不認得的欄位、amount ≤ 0、kind 不對        （FastAPI 自動回）

    【會用到的資料表】
        表             讀／寫  用來做什麼
        groups         讀      這筆所在的帳本、要換過去的帳本：結算了沒、移除了沒
        group_members  讀      要換過去的帳本，我在不在裡面
        categories     讀      新分類存不存在、收支對不對；只改收支時找「其他」
        transactions   寫      改這一筆，順便記 updated_at
        nlp_parses     讀＋寫  段落記帳的那筆：把改過的值記進 user_corrected

    【每一步用的工具與資料庫方法】
        步驟        呼叫                                                           做什麼
        1 整理欄位  body.model_dump(exclude_unset=True)                            只拿有送來的欄位，變成 dict
                    ledger.clean_patch(dict)                                       沒東西、不認得、格式不對 → 丟 ValueError；回傳清過的 dict（金額變 Decimal）
        2 能不能改  crud.get(Group, row.group_id, db=db)                           用主鍵拿這筆所在的帳本
                    ledger.require_editable(me.id, row.user_id, group.settled_at)  結算過丟 ValueError（本人檢查守衛已經做了）
        3 換帳本    crud.get(Group, where={"id": …, "removed_at__isnull": True}, db=db)  要換過去的那本（移除的當作不存在）
                    crud.exists(GroupMember, {"group_id": …, "user_id": me.id}, db=db)  我在不在裡面，回 True／False
                    ledger.require_open(target.settled_at)                         結算過丟 ValueError
        4 分類      crud.get(Category, where={"id": …, "or": [系統的, 我家的]}, db=db)  跟新增那支一樣的查法
                    crud.get(Category, where={"family_id__isnull": True, "kind": kind, "name": "其他"}, db=db)  只改收支時，換成那一邊的「其他」
        5 寫回      crud.save(Transaction, {"id": row.id, **changes}, db=db)       帶主鍵 = 改那一筆（row 物件也會跟著變）
        6 標註      crud.get(NlpParse, where={"transaction_id": row.id}, db=db)    這筆的解析紀錄
                    crud.save(NlpParse, {"id": parse.id, "user_corrected": {...}}, db=db)  記下使用者改成什麼
        7 存檔      db.commit()                                                    全部一起寫進去
                    crud.to_dict(row, fields=(…), rename={…, "updated_at": "updatedAt"})  轉成前端要的樣子
        ⚠️ user_corrected 是 JSON 欄位，放不進 Decimal：金額要先 float(...)。

    【寫法步驟】
        1. clean_patch 整理有送來的欄位（400）
        2. 這筆所在的帳本結算過 → 409
        3. 有 groupId 而且跟原本不同：要是我加入、沒移除的（403），還沒結算的（409）
        4. 決定分類：有送 cat 就檢查（400）；只改了收支沒送 cat，換成那一邊的「其他」
        5. 其他欄位照改，updated_at 設成現在，crud.save 寫回
        6. source 是 nlp：把改過的值合併進 nlp_parses.user_corrected
        7. db.commit()，回傳改完的那一筆

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import date, datetime, timezone

            from fastapi import APIRouter, Depends, Query, Request
            from sqlalchemy.orm import Session

            from app.guards import block_admin, current_user, own, visible_scope
            from app.models import Category, Group, GroupMember, Guardianship, NlpParse, Notification, Transaction, User
            from app.routers._stub import not_ready, stub
            from app.schemas.transaction import TransactionIn, TransactionPatchIn
            from app.toolkit import crud, errors, ledger, money, notify
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 整理要改的欄位：只拿有送來的，空的、格式不對的回 400
            try:
                patch = ledger.clean_patch(body.model_dump(exclude_unset=True))
            except ValueError as exc:
                raise errors.bad_request(str(exc)) from None

            # 2. 這筆所在的帳本結算過就不能改
            group = crud.get(Group, row.group_id, db=db)
            try:
                ledger.require_editable(me.id, row.user_id, group.settled_at)
            except ValueError as exc:
                raise errors.conflict(str(exc)) from None

            changes = {}

            # 3. 換帳本：要是我加入的、沒移除、沒結算的
            if "groupId" in patch:
                group_id = int(patch["groupId"]) if str(patch["groupId"]).isdigit() else 0
                if group_id != row.group_id:
                    target = crud.get(Group, where={"id": group_id, "removed_at__isnull": True}, db=db)
                    joined = crud.exists(GroupMember, {"group_id": group_id, "user_id": me.id}, db=db)
                    if target is None or not joined:
                        raise errors.forbidden("你沒有加入這本帳")
                    try:
                        ledger.require_open(target.settled_at)
                    except ValueError as exc:
                        raise errors.conflict(str(exc) + "。請換一本帳本") from None
                    changes["group_id"] = group_id

            # 4. 分類要跟收支對得上
            kind = patch.get("kind", row.kind)
            if "cat" in patch:
                category_id = int(patch["cat"]) if str(patch["cat"]).isdigit() else 0
                category = crud.get(Category, where={
                    "id": category_id,
                    "or": [{"family_id__isnull": True}, {"family_id": me.family_id}],
                }, db=db)
                if category is None:
                    raise errors.bad_request("找不到這個分類")
                if category.kind != kind:
                    side = "收入" if category.kind == "income" else "支出"
                    raise errors.bad_request("「%s」是%s分類，跟這筆的收支對不上" % (category.name, side))
                changes["category_id"] = category.id
            elif kind != row.kind:
                # 只改了收支、沒帶分類：換成那一邊的「其他」，不要留一個對不上的分類
                other = crud.get(Category, where={"family_id__isnull": True, "kind": kind,
                                                  "name": "其他" if kind == "expense" else "其他收入"}, db=db)
                if other is None:
                    raise errors.bad_request("改收支的時候請一起選分類")
                changes["category_id"] = other.id

            # 5. 其他欄位照改，寫回去
            if "date" in patch:
                changes["occurred_on"] = date.fromisoformat(patch["date"])
            if "amount" in patch:
                changes["amount"] = money.quantize(patch["amount"])
            if "kind" in patch:
                changes["kind"] = kind
            if "merchant" in patch:
                changes["merchant"] = patch["merchant"] or None
            if "note" in patch:
                changes["note"] = patch["note"] or None
            changes["updated_at"] = datetime.now(timezone.utc)
            crud.save(Transaction, {"id": row.id, **changes}, db=db)

            # 6. 段落記帳的那筆：改過的值記進 nlp_parses.user_corrected（模型抓錯的標註）
            parse = crud.get(NlpParse, where={"transaction_id": row.id}, db=db) if row.source == "nlp" else None
            if parse is not None:
                corrected = dict(parse.user_corrected or {})
                for key, value in patch.items():
                    if key != "groupId":
                        corrected[key] = float(value) if key == "amount" else value
                crud.save(NlpParse, {"id": parse.id, "user_corrected": corrected}, db=db)

            # 7. 一起寫進資料庫，回傳改完的那一筆
            db.commit()
            out = crud.to_dict(
                row,
                fields=("id", "user_id", "occurred_on", "amount", "group_id", "kind", "category_id", "source", "updated_at"),
                rename={"user_id": "user", "occurred_on": "date", "group_id": "group", "category_id": "cat",
                        "updated_at": "updatedAt"},
            )
            out["merchant"] = row.merchant or ""
            out["note"] = row.note or ""
            out["raw"] = parse.raw_text if parse else ""
            return out

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 PATCH /api/transactions/{tx_id}
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               只送 {"amount": 180}     → 200，其他欄位沒變，多了 updatedAt
               送 {"source": "manual"}  → 422
               送 {}                    → 400
               改別人的紀錄             → 403
               改結算過的帳本裡的紀錄   → 409
               只送 {"kind": "income"}  → 200，cat 變成「其他收入」
        5. 改一筆段落記帳記進來的，資料庫 nlp_parses 那一列的 user_corrected 要出現改過的欄位
        6. 前端改成連你的後端（frontend/index.html 的 api-base），收支明細某一列按「修改」，存檔後那一列要馬上變
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "update_transaction and 你的"，要全部通過
    """
    raise not_ready("PATCH /api/transactions/{tx_id}", OWNER)


@router.delete("/transactions/{tx_id}", summary="刪除一筆")
@stub
def delete_transaction(row=Depends(own(Transaction, "tx_id")), db: Session = Depends(get_db)):
    """刪除一筆

    DELETE /api/transactions/{tx_id}

    【這支做什麼】
        刪掉自己的一筆紀錄。結算過的帳本裡的不能刪。
        指向這一筆的資料要先處理：通知一起刪掉；解析紀錄（nlp_parses）留著當評測資料，只把連結拿掉。

    【前端怎麼打】
        frontend/js/api.js 的 API.deleteTransaction(id)
        收支明細每一列的「刪除」確認後呼叫。回 {"deleted": id} 或 204 前端都收。

    【誰能打】
        登入、沒被停權，而且這一筆是自己的。參數 row=Depends(own(Transaction, "tx_id")) 已經擋好了：
            沒登入 → 401；被停權 → 403
            {tx_id} 不是數字、或找不到這一筆 → 404「找不到這筆資料」
            這一筆的 user_id 不是我 → 403「這是別人的資料，你只能檢視」
        所以函式裡不用再檢查。row 就是那一筆（Transaction 物件），直接拿來用。
        ⚠️ 監管是唯讀的：家長看得到孩子的紀錄，但刪不掉——守衛只認「本人」。

    【路徑參數】{tx_id} 是要刪的那一筆的 id（字串），守衛已經換成那一筆，函式裡叫 row
        範例：DELETE /api/transactions/12

    【成功回應】狀態碼 200
        {"deleted": "12"}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                detail
        403     別人的紀錄              這是別人的資料，你只能檢視（守衛回）
        404     找不到這一筆            找不到這筆資料（守衛回）
        409     這筆所在的帳本已經結算  這本帳已經結算，裡面的紀錄不能再改或刪除

    【會用到的資料表】
        表             讀／寫    用來做什麼
        groups         讀        這筆所在的帳本結算了沒
        notifications  寫（刪）  指向這一筆的通知一起刪掉（外鍵）
        nlp_parses     寫（改）  transaction_id 改成 NULL，解析紀錄本身留著
        transactions   寫（刪）  刪這一筆

    【每一步用的工具與資料庫方法】
        步驟        呼叫                                                          做什麼
        1 能不能刪  crud.get(Group, row.group_id, db=db)                          這筆所在的帳本
                    ledger.require_editable(row.user_id, row.user_id, group.settled_at)  結算過丟 ValueError
        2 外鍵      crud.remove(Notification, {"transaction_id": row.id}, db=db)  刪掉符合條件的每一列，回傳刪了幾筆
                    crud.save(NlpParse, {"transaction_id": None}, where={"transaction_id": row.id}, db=db)  有 where = 改所有符合的
        3 刪除      crud.remove(Transaction, id=row.id, db=db)                    用主鍵刪一筆
                    db.commit()                                                   三件事一起寫進去
        ⚠️ 為什麼先處理通知：notifications.transaction_id 指向這一筆（外鍵），
           這一筆先刪的話資料庫會拒絕（PostgreSQL 一定會；SQLite 在這個專案也開了外鍵檢查）。
        ⚠️ 刪之前先把 row.id 存起來：刪掉之後就不要再讀 row 了。

    【寫法步驟】
        1. 帳本結算過 → 409
        2. 刪掉指向這一筆的通知；解析紀錄的連結改成 NULL
        3. 刪這一筆，db.commit()，回傳 {"deleted": id}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import date, datetime, timezone

            from fastapi import APIRouter, Depends, Query, Request
            from sqlalchemy.orm import Session

            from app.guards import block_admin, current_user, own, visible_scope
            from app.models import Category, Group, GroupMember, Guardianship, NlpParse, Notification, Transaction, User
            from app.routers._stub import not_ready, stub
            from app.schemas.transaction import TransactionIn, TransactionPatchIn
            from app.toolkit import crud, errors, ledger, money, notify
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 結算過的帳本裡的紀錄不能刪
            group = crud.get(Group, row.group_id, db=db)
            try:
                ledger.require_editable(row.user_id, row.user_id, group.settled_at)
            except ValueError as exc:
                raise errors.conflict(str(exc)) from None

            # 2. 先處理指向這一筆的資料（外鍵）：通知刪掉；解析紀錄留著當評測資料，只拿掉連結
            tx_id = row.id
            crud.remove(Notification, {"transaction_id": tx_id}, db=db)
            crud.save(NlpParse, {"transaction_id": None}, where={"transaction_id": tx_id}, db=db)

            # 3. 刪這一筆，一起寫進資料庫
            crud.remove(Transaction, id=tx_id, db=db)
            db.commit()
            return {"deleted": str(tx_id)}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 DELETE /api/transactions/{tx_id}
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               刪自己的一筆        → 200，回 {"deleted": "那個 id"}
               再刪一次同一筆      → 404
               刪別人的            → 403
               刪結算過的帳本裡的  → 409
        5. 前端改成連你的後端（frontend/index.html 的 api-base），收支明細某一列按「刪除」，那一列要不見
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "delete_transaction and 你的"，要全部通過
    """
    raise not_ready("DELETE /api/transactions/{tx_id}", OWNER)


@router.delete("/transactions", summary="一次刪多筆")
@block_admin
@stub
def delete_transactions(me: User, ids: str | None = None, db: Session = Depends(get_db)):
    """一次刪多筆

    DELETE /api/transactions

    【這支做什麼】
        一次刪很多筆：網址帶 ?ids=12,13,20。
        ⚠️ 全部成功或全部不動：其中一筆找不到、是別人的、或在結算過的帳本裡，就一筆都不刪。
           先把每一筆都檢查完，全部過了才在同一個交易裡刪。
        ⚠️ 沒帶 ids 一定要 400：被當成「不篩選」的話，就是把整本帳刪光。

    【前端怎麼打】
        frontend/js/api.js 的 API.deleteTransactions(ids)
        收支明細「選取多筆」→「刪除」時呼叫，ids 用逗號串起來放在網址上。前端檢查回應裡一定要有 deleted。

    【誰能打】
        登入、沒被停權、不是平台管理員。上面的 @block_admin 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【查詢參數】
        參數  型別  說明
        ids   字串  逗號分隔的 id，最多 100 筆。前後空白與重複的會被去掉
        範例：DELETE /api/transactions?ids=12,13,20
        為什麼不用 DELETE 帶主體：有些代理伺服器會把 DELETE 的主體丟掉。

    【成功回應】狀態碼 200
        {"deleted": ["12", "13", "20"]}
        · 照前端送來的順序（去掉重複之後）

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候              detail
        400     沒帶 ids、或是空的    沒有指定要刪哪幾筆
        400     超過 100 筆           一次最多刪 100 筆
        403     裡面有別人的          這是別人的紀錄，你只能檢視。這次一筆都沒有刪
        404     裡面有找不到的        找不到這筆紀錄：99
        409     裡面有結算過的帳本的  這本帳已經結算，裡面的紀錄不能再改或刪除。這次一筆都沒有刪

    【會用到的資料表】
        表             讀／寫        用來做什麼
        transactions   讀＋寫（刪）  先把這些筆全部查出來檢查，最後一起刪
        groups         讀            這些筆所在的帳本，哪幾本結算了
        notifications  寫（刪）      指向這些筆的通知
        nlp_parses     寫（改）      連結改成 NULL

    【每一步用的工具與資料庫方法】
        步驟        呼叫                                                           做什麼
        1 整理 ids  ledger.clean_ids(ids or "")                                    "12, 13,12" → ["12", "13"]；空的、超過 100 筆丟 ValueError
        2 一次查完  crud.find(Transaction, {"id__in": numbers}, db=db)             一次把這些筆都拿出來
                    crud.find(Group, {"id__in": …, "settled_at__isnull": False}, fields="id", db=db)  哪幾本已經結算（isnull False = 不是 NULL）
        3 逐筆檢查  ledger.require_editable(me.id, t.user_id, t.group_id in settled)  別人的丟 PermissionError，結算過的丟 ValueError
        4 一起刪    crud.remove(Notification, {"transaction_id__in": ids}, db=db)  刪通知
                    crud.save(NlpParse, {"transaction_id": None}, where={"transaction_id__in": ids}, db=db)  拿掉解析紀錄的連結
                    crud.remove(Transaction, {"id__in": ids, "user_id": me.id}, db=db)  刪明細（多加 user_id 當保險）
                    db.commit()                                                    到這裡才真的寫進去
        ⚠️ toolkit 的「權限不夠」例外（Forbidden）是 PermissionError 的一種，所以用 except PermissionError 接。
           它要寫在 except ValueError 前面或後面都可以——兩個是不同的例外，不會互相搶。

    【寫法步驟】
        1. clean_ids 整理（400）；每個 id 轉成整數，轉不動的當 0（一定找不到）
        2. 一次查出這些筆，以及它們所在的帳本裡哪幾本結算了
        3. 照前端的順序逐筆檢查：找不到 404、別人的 403、結算過的 409——有一筆不行就整批停下來
        4. 全部通過：刪通知、拿掉解析連結、刪明細，db.commit()
        5. 回傳 {"deleted": [...]}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from datetime import date, datetime, timezone

            from fastapi import APIRouter, Depends, Query, Request
            from sqlalchemy.orm import Session

            from app.guards import block_admin, current_user, own, visible_scope
            from app.models import Category, Group, GroupMember, Guardianship, NlpParse, Notification, Transaction, User
            from app.routers._stub import not_ready, stub
            from app.schemas.transaction import TransactionIn, TransactionPatchIn
            from app.toolkit import crud, errors, ledger, money, notify
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 整理要刪的 id：去空白、去重複；空的或太多回 400
            try:
                wanted = ledger.clean_ids(ids or "")
            except ValueError as exc:
                raise errors.bad_request(str(exc)) from None
            numbers = [int(x) if x.isdigit() else 0 for x in wanted]

            # 2. 一次查出這些筆，以及哪幾本帳已經結算
            rows = {t.id: t for t in crud.find(Transaction, {"id__in": numbers}, db=db)}
            group_ids = {t.group_id for t in rows.values()}
            settled = set(crud.find(Group, {"id__in": group_ids, "settled_at__isnull": False}, fields="id", db=db))

            # 3. 每一筆都檢查過；有一筆不行就整批不刪
            for raw, number in zip(wanted, numbers):
                t = rows.get(number)
                if t is None:
                    raise errors.not_found("找不到這筆紀錄：" + raw)
                try:
                    ledger.require_editable(me.id, t.user_id, t.group_id in settled)
                except PermissionError as exc:
                    raise errors.forbidden(str(exc) + "。這次一筆都沒有刪") from None
                except ValueError as exc:
                    raise errors.conflict(str(exc) + "。這次一筆都沒有刪") from None

            # 4. 全部通過，才在同一個交易裡刪
            tx_ids = list(rows)
            crud.remove(Notification, {"transaction_id__in": tx_ids}, db=db)
            crud.save(NlpParse, {"transaction_id": None}, where={"transaction_id__in": tx_ids}, db=db)
            crud.remove(Transaction, {"id__in": tx_ids, "user_id": me.id}, db=db)
            db.commit()
            return {"deleted": wanted}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 DELETE /api/transactions
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               ids=你自己的兩筆         → 200，兩筆都不見
               不帶 ids                 → 400
               ids=你的一筆,別人的一筆  → 403，而且你那一筆還在
               ids=你的一筆,99999       → 404，而且你那一筆還在
        5. 前端改成連你的後端（frontend/index.html 的 api-base），收支明細勾兩筆按「刪除」，兩筆一起不見
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "delete_transactions and 你的"，要全部通過
    """
    raise not_ready("DELETE /api/transactions", OWNER)
