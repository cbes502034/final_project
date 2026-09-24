"""
分類體系。

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
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import catalog
from app.guards import block_admin, parent_required
from app.models import Category, User
from app.routers._stub import not_ready, stub
from app.schemas.transaction import CategoryIn
from app.toolkit import crud, errors
from app.toolkit.db import get_db

router = APIRouter(tags=["分類體系"])
OWNER = "成員2"


@router.get("/categories", summary="分類（系統預設＋我們家自訂）")
@block_admin
# @stub
def list_categories(me: User, db: Session = Depends(get_db)):
    """分類（系統預設＋我們家自訂）

    GET /api/categories

    【這支做什麼】
        回傳我能用的分類：系統預設的（family_id 是 NULL）＋ 我們家自訂的。別人家的自訂分類不回。
        ⚠️ 這份清單是跨模組的契約：記帳的下拉選單、模型挑分類（成員2）、評測（成員4）都用它。

    【前端怎麼打】
        frontend/js/api.js 的 API.categories()
        記帳頁與修改紀錄的分類下拉、前端補 catName／catColor 的對照表。前端檢查回應裡一定要有 categories。
        前端拿一次就快取起來；新增分類、加入或離開家庭之後會自己重拿。

    【誰能打】
        登入、沒被停權、不是平台管理員。上面的 @block_admin 已經擋好了：
            沒登入 → 401；被停權、或是平台管理員 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【請求參數】沒有

    【成功回應】狀態碼 200
        {"categories": [
           {"id": "1", "name": "餐飲", "kind": "expense", "color": "cat-food", "icon": "食", "custom": false},
           {"id": "13", "name": "寵物", "kind": "expense", "color": "cat-other", "icon": "寵", "custom": true, "familyId": "2"}
         ]}
        · color 是代號（cat-food），不是色碼；實際顏色由前端的 CSS 決定
        · icon 是一個中文字。資料表沒有 icon 欄：系統分類的字在 app/catalog.py 的 CATEGORY_ICONS，自訂分類取名稱第一個字
        · 自訂分類才有 familyId，custom 是 true

    【錯誤回應】
        只有守衛的 401／403，這支本身不會出錯。

    【會用到的資料表】
        表          讀／寫  用來做什麼
        categories  讀      系統分類＋我們家的分類

    【每一步用的工具與資料庫方法】
        步驟    呼叫                                            做什麼
        1 查    crud.find(Category, {"or": [{"family_id__isnull": True}, {"family_id": me.family_id}]}, order_by="id", db=db)  系統的或我們家的；還沒有家庭時 family_id 是 None，只會拿到系統的
        2 圖示  catalog.CATEGORY_ICONS.get(c.name, c.name[:1])  系統分類查表，查不到用第一個字
        ⚠️ {"family_id": None} 在 crud 裡就是 IS NULL，所以沒有家庭的人不會意外拿到別人家的分類。

    【寫法步驟】
        1. 查系統的＋我們家的分類，照 id 排（系統分類先建，所以會在前面）
        2. 一個一個轉成 {id, name, kind, color, icon, custom}，自訂的多帶 familyId
        3. 回傳 {"categories": [...]}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from fastapi import APIRouter, Depends
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import block_admin, parent_required
            from app.models import Category, User
            from app.routers._stub import not_ready, stub
            from app.schemas.transaction import CategoryIn
            from app.toolkit import crud, errors
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 系統預設（family_id 是 NULL）＋ 我們家自訂的
            rows = crud.find(Category, {"or": [{"family_id__isnull": True}, {"family_id": me.family_id}]},
                             order_by="id", db=db)

            # 2. 轉成前端要的樣子；圖示字：系統分類查表，自訂分類取第一個字
            out = []
            for c in rows:
                custom = c.family_id is not None
                item = {
                    "id": str(c.id),
                    "name": c.name,
                    "kind": c.kind,
                    "color": c.color or "cat-other",
                    "icon": c.name[:1] if custom else catalog.CATEGORY_ICONS.get(c.name, c.name[:1]),
                    "custom": custom,
                }
                if custom:
                    item["familyId"] = str(c.family_id)
                out.append(item)
            return {"categories": out}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 GET /api/categories
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               還沒有家庭的人            → 只有 12 個系統分類
               家長新增「寵物」之後再打  → 多一個 custom: true 的「寵物」
               別的家庭的人打            → 看不到「寵物」
        5. 前端改成連你的後端（frontend/index.html 的 api-base），記帳頁的分類下拉要看得到系統分類與我們家的分類
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "list_categories and 你的"，要全部通過
    """

    from fastapi import APIRouter, Depends
    from sqlalchemy.orm import Session

    from app import catalog
    from app.guards import block_admin, parent_required
    from app.models import Category, User
    from app.routers._stub import not_ready, stub
    from app.schemas.transaction import CategoryIn
    from app.toolkit import crud, errors
    from app.toolkit.db import get_db

    # 1. 系統預設（family_id 是 NULL）＋ 我們家自訂的
    rows = crud.find(Category, {"or": [{"family_id__isnull": True}, {"family_id": me.family_id}]},
                        order_by="id", db=db)

    # 2. 轉成前端要的樣子；圖示字：系統分類查表，自訂分類取第一個字
    out = []
    for c in rows:
        custom = c.family_id is not None
        item = {
            "id": str(c.id),
            "name": c.name,
            "kind": c.kind,
            "color": c.color or "cat-other",
            "icon": c.name[:1] if custom else catalog.CATEGORY_ICONS.get(c.name, c.name[:1]),
            "custom": custom,
        }
        if custom:
            item["familyId"] = str(c.family_id)
        out.append(item)
    return {"categories": out}
    # raise not_ready("GET /api/categories", OWNER)


@router.post("/categories", status_code=201, summary="新增家庭自訂分類")
@parent_required
# @stub
def create_category(body: CategoryIn, me: User, db: Session = Depends(get_db)):
    """新增家庭自訂分類

    POST /api/categories

    【這支做什麼】
        家長新增一個「我們家」的分類（例如「寵物」），全家共用。
        新增之後前端會重拿分類清單，記帳頁的下拉立刻看得到。

    【前端怎麼打】
        frontend/js/api.js 的 API.createCategory({ name, kind })
        家庭成員頁「家庭自訂分類」（只有家長看得到）按新增時呼叫。

    【誰能打】
        登入、沒被停權、而且是家長。上面的 @parent_required 已經擋好了：
            沒登入 → 401；被停權、不是家長（子女、還沒有家庭、平台管理員）→ 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（這裡一定有值）
            me.family_role   一定是 'parent'

    【請求主體】body 是 CategoryIn（app/schemas/transaction.py）
        欄位  型別  必填  說明
        name  字串  是    1～10 字（FastAPI 先擋一次）；去頭尾空白、壓掉連續空白之後還要是 1～10 字
        kind  字串  是    expense／income，其他值 FastAPI 自動回 422
        範例：{"name": "寵物", "kind": "expense"}

    【成功回應】狀態碼 201
        {"id": "13", "name": "寵物", "kind": "expense", "color": "cat-other", "icon": "寵",
         "custom": true, "familyId": "2"}
        · color 一律 cat-other，icon 取名稱第一個字

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                                detail
        403     不是家長、還沒有家庭                    只有家長可以做這件事（守衛回）
        409     同一個收支裡，系統或我們家已經有同名的  已經有「寵物」這個分類了
        422     名稱整理完是空的或超過 10 字            分類名稱要 1～10 個字
        422     kind 不是 expense／income               （FastAPI 自動回）

    【會用到的資料表】
        表          讀／寫  用來做什麼
        categories  讀＋寫  檢查有沒有重名；新增一列（family_id = 我們家）

    【每一步用的工具與資料庫方法】
        步驟        呼叫                                                        做什麼
        1 整理名稱  " ".join(body.name.split())                                 去頭尾空白、連續空白壓成一格
        2 重名      crud.exists(Category, {"kind": …, "name": …, "or": [系統的, 我們家的]}, db=db)  有沒有任何一列符合，回 True／False
        3 新增      crud.save(Category, {"family_id": me.family_id, …}, db=db)  新增一列，回傳那一列（有 id）
                    db.commit()                                                 寫進去
        ⚠️ 只比「系統的＋我們家的」：跟別人家比的話，等於告訴使用者別的家庭有哪些分類。

    【寫法步驟】
        1. 整理名稱，空的或超過 10 字回 422
        2. 同一個收支裡，系統或我們家已經有同名的 → 409
        3. 新增一列：family_id = 我們家、color = cat-other
        4. db.commit()，回傳新的分類

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            from fastapi import APIRouter, Depends
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import block_admin, parent_required
            from app.models import Category, User
            from app.routers._stub import not_ready, stub
            from app.schemas.transaction import CategoryIn
            from app.toolkit import crud, errors
            from app.toolkit.db import get_db

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 整理名稱：去頭尾空白、壓掉連續空白
            name = " ".join(body.name.split())
            if not name or len(name) > 10:
                raise errors.unprocessable("分類名稱要 1～10 個字")

            # 2. 同一個收支裡，系統或我們家已經有同名的就擋
            if crud.exists(Category, {
                "kind": body.kind,
                "name": name,
                "or": [{"family_id__isnull": True}, {"family_id": me.family_id}],
            }, db=db):
                raise errors.conflict("已經有「%s」這個分類了" % name)

            # 3. 新增一列：我們家的分類，顏色一律 cat-other
            c = crud.save(Category, {"family_id": me.family_id, "name": name, "kind": body.kind,
                                     "color": "cat-other"}, db=db)
            db.commit()
            return {"id": str(c.id), "name": c.name, "kind": c.kind, "color": c.color, "icon": name[:1],
                    "custom": True, "familyId": str(me.family_id)}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/categories
        3. 按右上角 Authorize，貼上「家長」登入拿到的 accessToken
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               {"name": "寵物", "kind": "expense"}                  → 201，custom 是 true
               再送一次一樣的                                       → 409
               {"name": "餐飲", "kind": "expense"}（跟系統的重名）  → 409
               {"name": "   ", "kind": "expense"}                   → 422
               子女的 token                                         → 403
        5. 前端改成連你的後端（frontend/index.html 的 api-base），家庭成員頁新增一個分類，記帳頁的下拉要馬上看得到
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "create_category and 你的"，要全部通過
    """


    from fastapi import APIRouter, Depends
    from sqlalchemy.orm import Session

    from app import catalog
    from app.guards import block_admin, parent_required
    from app.models import Category, User
    from app.routers._stub import not_ready, stub
    from app.schemas.transaction import CategoryIn
    from app.toolkit import crud, errors
    from app.toolkit.db import get_db


    # 1. 整理名稱：去頭尾空白、壓掉連續空白
    name = " ".join(body.name.split())
    if not name or len(name) > 10:
        raise errors.unprocessable("分類名稱要 1～10 個字")

    # 2. 同一個收支裡，系統或我們家已經有同名的就擋
    if crud.exists(Category, {
        "kind": body.kind,
        "name": name,
        "or": [{"family_id__isnull": True}, {"family_id": me.family_id}],
    }, db=db):
        raise errors.conflict("已經有「%s」這個分類了" % name)

    # 3. 新增一列：我們家的分類，顏色一律 cat-other
    c = crud.save(Category, {"family_id": me.family_id, "name": name, "kind": body.kind,
                                "color": "cat-other"}, db=db)
    db.commit()
    return {"id": str(c.id), "name": c.name, "kind": c.kind, "color": c.color, "icon": name[:1],
            "custom": True, "familyId": str(me.family_id)}
    # raise not_ready("POST /api/categories", OWNER)
