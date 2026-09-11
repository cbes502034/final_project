"""
收支明細與分類。 ✦ 負責人：成員2（記帳）　✦ 分支：m2-ledger

===========================================================================
這個檔案負責哪些路由
===========================================================================
掛載前綴是 /api。

    方法    路徑                   權限          用途
    ------------------------------------------------------------------
    GET    /transactions          登入          明細（可篩選、分頁）
    POST   /transactions          登入          手動新增（不經過模型）
    PATCH  /transactions/{id}     本人或監管者  修改
    DELETE /transactions/{id}     本人          刪除

分類體系（/api/categories）**不在這裡** —— 那是成員3 的 routers/categories.py。
分類由成員3 定義，成員2 只是把清單寫進 prompt。

===========================================================================
第 19 支和 /api/nlp/confirm 的差別 —— 這題很容易搞混
===========================================================================
兩支都會寫進 transactions，但**來源必須分清楚**：

    POST /api/transactions      →  source = 'manual'   單筆手動，沒經過模型
    POST /api/nlp/confirm       →  source = 'nlp'      經過模型解析並確認

為什麼一定要分？因為 `nlp_parses` 那張表是我們算模型正確率的依據。
如果手動資料也被當成模型產出記進去，分母就錯了，整份評測報告都不能看。

（這在前端原型階段真的發生過：單筆手動借用了 nlp/confirm，
結果手動填的資料被貼上「段落記帳」標籤，來源篩選也篩不到。）
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user

router = APIRouter()


@router.get("/transactions", summary="收支明細")
def list_transactions(
    user_id: int | None = Query(None, description="只看某個人的。不帶＝看我有權限看的所有人"),
    date_from: str | None = Query(None, alias="from", description="起始日期 YYYY-MM-DD"),
    date_to: str | None = Query(None, alias="to", description="結束日期 YYYY-MM-DD"),
    category_id: int | None = Query(None, description="只看某個分類"),
    kind: str | None = Query(None, description="income 或 expense"),
    source: str | None = Query(None, description="nlp 或 manual"),
    q: str | None = Query(None, description="關鍵字，比對店家與備註"),
    page: int = Query(1, ge=1, description="第幾頁，從 1 開始"),
    me=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    查詢收支明細。

    上面那一長串參數叫做**查詢參數**，就是網址問號後面的東西：

        /api/transactions?kind=expense&from=2026-09-01&page=2

    你只要在函式參數宣告，FastAPI 就會自動幫你取出來、轉型別、驗證。
    `Query(None, ...)` 的 None 是預設值（代表可有可無），
    `ge=1` 是「大於等於 1」，有人傳 `page=0` 它會自己回 422。
    `description` 會顯示在 /docs 上，等於順手把文件寫好了。

    `alias="from"` 是因為 `from` 是 Python 的保留字不能當變數名，
    所以變數叫 `date_from`，但對外的網址參數仍然是 `from`。

    ===================================================================
    ⚠️ 這支路由最重要的是權限，不是查詢
    ===================================================================
    **不帶 user_id** → 回傳「我看得到的所有人」
        自己 + 我監管的人；如果我是 master 就是全家。
        這段邏輯寫在 services/permission.py，不要在這裡重寫一遍。

    **帶了 user_id 但我沒權限看那個人** → **回 403，不要回空陣列**
        回空陣列的話，使用者會以為「對方這個月沒記帳」，
        而不是「我看不到」。這兩件事差很多，不能混為一談。

    TODO(成員2): 1. 用 services/permission.py 的 visible_user_ids() 算出可見範圍
                 2. 依參數組 query
                 3. 分頁（建議一頁 50 筆）
                 4. 回傳 { "transactions": [...], "total": n }
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員2 尚未實作")


@router.post("/transactions", status_code=status.HTTP_201_CREATED, summary="手動新增")
def create_transaction(me=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    手動記一筆帳。**不經過模型**，`source` 記成 `manual`。

    金額欄位在資料庫是 `NUMERIC(14,2)`，**不是浮點數**。
    浮點數在二進位下無法精確表示 0.1 這種值，
    累加幾千筆之後會出現 `12345.670000000002` 這種結果。
    財務系統不能接受這個，所以一律用 NUMERIC / Decimal。

    TODO(成員2): 實作
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員2 尚未實作")


@router.patch("/transactions/{tx_id}", summary="修改一筆")
def update_transaction(tx_id: int, me=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    修改既有紀錄。本人或監管者可以改。

    ⚠️ **一定要先確認這筆是不是你有權限動的**。
    只憑 `tx_id` 就改下去，等於任何人只要改個數字就能修改別人的帳。
    這種漏洞叫做「不安全的直接物件引用」，是很常見的新手錯誤。

    TODO(成員2): 先查出這筆的 user_id，用 permission.py 確認權限，再更新
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員2 尚未實作")


@router.delete("/transactions/{tx_id}", summary="刪除一筆")
def delete_transaction(tx_id: int, me=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    刪除紀錄。**只有本人可以刪，監管者不行。**

    監管者看得到，但不能替人刪帳——那會讓被監管者無法信任這份紀錄。

    TODO(成員2): 實作，權限檢查同上
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員2 尚未實作")
