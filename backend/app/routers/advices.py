"""
財務建議。 ✦ 負責人：成員4（財務建議）

===========================================================================
這個檔案負責哪些路由
===========================================================================
掛載前綴是 /api。

    編號  方法   路徑                權限    用途
    ------------------------------------------------------------------
     34   GET   /advices            登入    建議清單
     35   POST  /advices/generate   master  重新產生 ★ 會呼叫模型

===========================================================================
這個模組唯一要記住的一條規則：模型不做算術
===========================================================================
產生建議的順序**不能顛倒**：

    1. services/analytics.py 從資料庫把所有數字算出來
    2. 把「算好的數字」組進 prompt
    3. 呼叫模型，要求它**只做敘述與歸納**
    4. Pydantic 驗證模型回傳的格式
    5. 把數字存進 advices.basis_json，給使用者驗算用

為什麼？因為語言模型本來就不擅長算術，
而**財務數字算錯會讓使用者做出錯誤決定**。
模型拿到的是結果不是原始資料，它連算錯的機會都沒有。

===========================================================================
建議的邊界規則（要寫進 prompt 當硬約束）
===========================================================================
    金額一律由資料庫計算      模型不擅長算術
    每條建議都要附依據        使用者要能自己驗算，不能是黑盒子
    不提供投資／保險／稅務建議  那是受規範的專業意見，超出系統範圍
    不對個人做價值判斷        只描述數字與趨勢，不說「你太浪費」
    未成年的建議同時送監管者    監管是設計目的，但必須雙方都看得到
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_master

router = APIRouter()


@router.get("/advices", summary="財務建議清單")
def list_advices(
    scope: str = Query("me", description="me 或 family"),
    period: str | None = Query(None, description="哪個月，格式 2026-09"),
    me=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    列出已經產生好的建議。**這支不呼叫模型**，只是從資料庫讀。

    每一條要帶：

        title       建議標題
        body        內容
        level       good / info / warn 三級
        basisJson   這條建議是根據哪些數字算出來的

    `basisJson` 一定要回傳給前端顯示。使用者要能自己驗算，
    看到「你這個月餐飲超支 2,400」時，能展開看到是怎麼算出來的。
    **沒有依據的建議就是黑盒子，使用者不會信。**

    TODO(成員4): 實作
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員4 尚未實作")


@router.post("/advices/generate", summary="重新產生建議 ★ 呼叫模型")
def generate_advices(me=Depends(require_master), db: Session = Depends(get_db)):
    """
    重新產生這個月的財務建議。

    請嚴格照檔案最上面那五步的順序做，**第 1 步和第 3 步不能對調**。

    這支路由會比較慢（要等模型回應），所以：

    - 一定要設逾時（`settings.model_timeout_seconds`）
    - 前端要顯示載入中的狀態
    - 失敗時回明確的錯誤訊息，不要讓前端一直轉圈

    ⚠️ 未成年成員的建議產生後，**要同時讓監管者看得到**。
    這是設計目的之一，不是額外功能。

    TODO(成員4): 1. analytics.build_basis() 算數字
                 2. 組 prompt（把邊界規則寫進去）
                 3. llm.generate_advice() 呼叫模型
                 4. Pydantic 驗證輸出格式
                 5. 寫進 advices 表，basis_json 存第 1 步的數字
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員4 尚未實作")
