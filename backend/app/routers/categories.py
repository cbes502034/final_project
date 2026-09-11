"""
分類體系。 ✦ 負責人：成員3（數字與建議）　✦ 分支：m3-analytics

===========================================================================
這個檔案負責哪些路由
===========================================================================
掛載前綴是 /api。

    方法   路徑           權限     用途
    ------------------------------------------------------
    GET   /categories    登入     分類體系（系統預設 + 家庭自訂）
    POST  /categories    master   新增家庭自訂分類

===========================================================================
為什麼分類歸成員3，不歸記帳？
===========================================================================
因為**分類體系是成員3 定義的**，而且它同時是統計分組的依據。
定義的人和提供 API 的人是同一個，才不會出現「改了定義但 API 沒跟著改」。

但這支路由的回傳值有**三個人**在用：

    成員2  要把分類清單寫進段落解析的 prompt
    成員3  統計要照分類分組
    成員4  評測要看分類的 Macro-F1

所以它是**第 1 週唯一要凍結的跨模組契約**。
成員3 定好之後就不要再動，要動先在群組講。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_master

router = APIRouter()


@router.get("/categories", summary="分類體系")
def list_categories(me=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    回傳系統預設 + 這個家庭自訂的分類。

    ⚠️ 這支路由的回傳值**成員2 和成員4 都會用到**：
    成員2 要把分類清單寫進模型的 prompt，成員4 產生建議時要用。
    分類體系由**成員3 定義**，是第 1 週唯一要凍結的跨模組契約。

    TODO(成員2): 實作。分類定義好之前先回傳寫死的預設清單也可以，
                 先讓前端串得起來比較重要
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員2 尚未實作")


@router.post("/categories", status_code=status.HTTP_201_CREATED, summary="新增自訂分類")
def create_category(me=Depends(require_master), db: Session = Depends(get_db)):
    """
    新增家庭自訂分類。只有 master 可以。

    ⚠️ 新增分類會影響模型的 prompt（分類清單變了），
    也會影響歷史統計的分組。**不要讓任何人隨便加。**

    TODO(成員2): 實作
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員2 尚未實作")
