"""
預算與每月存款目標。 ✦ 負責人：成員3（統計與預算）

===========================================================================
這個檔案負責哪些路由
===========================================================================
掛載前綴是 /api。

    編號  方法  路徑             權限                  用途
    --------------------------------------------------------------------
     30   GET  /budgets         登入                  預算與使用率
     31   PUT  /budgets         本人或 master         設定預算
     32   GET  /savings-goal    登入                  存款目標與達成狀態
     33   PUT  /savings-goal    本人；未成年由 master  設定存款目標

===========================================================================
為什麼是 PUT 不是 POST？
===========================================================================
- **POST** ＝「新增一筆」。打兩次會產生兩筆。
- **PUT**  ＝「把這個東西設定成這樣」。打兩次結果一樣。

「把九月的餐飲預算設成 8000」不管執行幾次，結果都是 8000，
所以用 PUT。這個性質叫做**冪等**。

這不只是名詞正確性的問題：網路不穩時前端可能會重送請求，
冪等的路由重送不會有副作用，非冪等的就會產生重複資料。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user

router = APIRouter()


@router.get("/budgets", summary="預算與使用率")
def get_budgets(me=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    回傳各分類的預算上限與目前用了多少。

    TODO(成員3): 回傳 [{ categoryId, limit, used, ratio }, ...]
                 ratio 由後端算好，前端只負責畫條
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員3 尚未實作")


@router.put("/budgets", summary="設定預算")
def set_budget(me=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    設定某個分類在某個月的預算上限。

    權限：本人可以設自己的；master 可以設全家的。
    未成年成員要設預算需要管理者核准（見權限矩陣）。

    TODO(成員3): 實作，記得做權限檢查
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員3 尚未實作")


@router.get("/savings-goal", summary="每月存款目標與達成狀態")
def get_savings_goal(me=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    回傳目標金額與目前的達成狀態（safe / near / over）。

    計算方式跟 /summary 裡的 savings 一樣，
    **這兩支一定要用 services/analytics.py 的同一個函式算**，
    不要各自實作一遍——否則哪天門檻改了，兩個畫面會顯示不同的結論。

    TODO(成員3): 實作
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員3 尚未實作")


@router.put("/savings-goal", summary="設定每月存款目標")
def set_savings_goal(me=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    設定「每月想存多少」。**註冊流程也是打這一支。**

    ===================================================================
    ⚠️ 改目標要新增一筆，不要覆蓋舊的
    ===================================================================
    `savings_goals` 表帶 `period_key`（例如 "2026-09"）。
    使用者九月把目標從 20000 改成 15000 時，
    **新增一筆 period_key='2026-09' 的紀錄，不要去改舊那筆。**

    為什麼？因為十月回頭看九月的達成狀況時，
    要知道「當時的目標是多少」。如果每次都覆蓋，歷史就不見了，
    你會用現在的目標去評斷過去的表現，那是錯的。

    另外要驗證：目標不能是負數，也不應該大於收入
    （目標比收入高的話，可支配上限是負的，使用率算出來會很奇怪）。

    TODO(成員3): 實作，記得驗證範圍並保留歷史
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員3 尚未實作")
