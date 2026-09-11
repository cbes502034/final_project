"""
統計。 ✦ 負責人：成員3（統計與預算）

===========================================================================
這個檔案負責哪些路由
===========================================================================
掛載前綴是 /api。

    編號  方法  路徑        權限  用途
    ------------------------------------------------------------
     28   GET  /summary    登入  個人／家庭摘要（總覽頁用）
     29   GET  /stats      登入  月或年統計（統計頁用）

===========================================================================
這個模組的鐵則：所有金額都在這裡算，前端一個數字都不准自己加
===========================================================================
前端自己加總看起來比較快，但只要有**兩個地方各自加總**，
數字對不起來只是時間問題。

這個專案在原型階段就踩過一次：
「我的總覽」用明細加總算出 19,970，
「家庭總覽」用成員表算出 41,230，同一個人同一個月出現兩個支出數字。

所以：**API 回傳什麼，前端就顯示什麼，不做任何運算。**
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user

router = APIRouter()


@router.get("/summary", summary="個人／家庭摘要")
def summary(
    scope: str = Query("me", description="me＝只看自己，family＝看全家"),
    period: str | None = Query(None, description="哪個月，格式 2026-09。不帶就是本月"),
    me=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    總覽頁的所有數字都從這支來。

    要回傳的東西：

        income      本期收入
        expense     本期支出
        net         結餘（收入 − 支出）
        rate        儲蓄率（結餘 ÷ 收入）
        count       筆數
        savings     存款目標的達成狀態（見下）

    ===================================================================
    存款目標怎麼算
    ===================================================================
        可支配上限 = 本期收入 − 每月存款目標
        使用率     = 支出 ÷ 可支配上限

        使用率 < 80%     → level = "safe"  達標中
        80% ~ 100%       → level = "near"  接近上限
        > 100%           → level = "over"  存不到目標

    `level` 要由**後端算好再回傳**，不要回原始數字讓前端自己判斷門檻——
    否則哪天門檻要從 80% 改成 75%，前端後端都要改，一定會有人漏掉。

    ⚠️ `scope=family` 時，除了全家總數，**還要逐人回傳各自的狀態**。
    原因是聚合統計會蓋掉個人的問題：結餘多的成員會把其他人的超支蓋過去，
    家庭整體顯示「安全」，但實際上有三個人存不到自己的目標。
    **只看總數會漏掉真正需要被提醒的人。**

    TODO(成員3): 1. 用 services/permission.py 決定要算哪些人
                 2. 用 services/analytics.py 算數字
                 3. 回傳形狀對照 frontend/js/api.js 的 summary()
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員3 尚未實作")


@router.get("/stats", summary="月或年統計")
def stats(
    period_type: str = Query("month", alias="periodType", description="month 或 year"),
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
    me=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    統計頁的資料：分類佔比、趨勢對照。

    要回傳：

        byCat       各分類的金額與佔比（畫圓環圖用）
        trend       近 6 個月或近 3 年的收支對照（畫趨勢圖用）
        income/expense/net

    ⚠️ **當年度的年統計一定要標示「未完整」**，回傳時加一個
    `incomplete: true` 的旗標。

    為什麼？因為 2026 年才過了 9 個月，總支出當然比 2025 整年少。
    使用者看到「今年支出變少了」會誤以為自己變節省了，
    實際上只是年度還沒過完。**這種誤導比沒有這個功能更糟。**

    TODO(成員3): 實作。年統計記得回 incomplete 旗標
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員3 尚未實作")
