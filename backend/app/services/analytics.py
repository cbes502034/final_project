"""
統計計算。 ✦ 負責人：成員3（數字與建議）　✦ 分支：m3-analytics

===========================================================================
這個檔案是整個系統唯一算錢的地方
===========================================================================
路由不算、前端不算、模型更不算。**只有這裡算。**

理由很簡單：同一個數字只要有兩個地方算得出來，
就一定會有對不起來的那一天。這個專案在原型階段已經發生過一次。

成員3 產生財務建議時，也是先呼叫這裡把數字算好，再餵給模型——
同一個人，所以不會有「算法改了但建議沒跟著改」的問題。
"""

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

# 超支警告的門檻。刻意寫在這裡當常數，不要散在程式碼裡——
# 哪天要從 80% 改成 75%，只要改這一行
WARN_RATIO = Decimal("0.80")   # 用掉可支配額度的八成 → 提醒
OVER_RATIO = Decimal("1.00")   # 超過 → 警告


def savings_status(income: Decimal, expense: Decimal, goal: Decimal) -> dict[str, Any]:
    """
    算出存款目標的達成狀態。

        可支配上限 = 收入 − 存款目標
        使用率     = 支出 ÷ 可支配上限

        使用率 < 80%    → safe  達標中
        80% ~ 100%      → near  接近上限
        > 100%          → over  存不到目標

    ⚠️ **可支配上限可能是 0 或負數**（目標訂得比收入還高）。
    直接除下去會丟出 ZeroDivisionError，整支 API 回 500。
    下面有處理這個情況，不要把它拿掉。

    回傳的 `level` 讓前端直接用，前端不要自己判斷門檻。

    TODO(成員3): 確認邊界情況的行為符合預期，補上單元測試
    """
    allowance = income - goal
    if allowance > 0:
        ratio = expense / allowance
    else:
        # 可支配上限 <= 0：只要有花錢就是超支
        ratio = Decimal("2") if expense > 0 else Decimal("0")

    if ratio >= OVER_RATIO:
        level = "over"
    elif ratio >= WARN_RATIO:
        level = "near"
    else:
        level = "safe"

    return {
        "goal": goal,
        "allowance": allowance,
        "used": expense,
        "left": allowance - expense,
        "ratio": ratio,
        "level": level,
        "shortfall": max(Decimal("0"), expense - allowance),
        "actual": income - expense,   # 這個月實際存得下來多少
    }


def period_summary(db: Session, user_ids: list[int], period: str) -> dict[str, Any]:
    """
    算某一群人在某個月的收支摘要。

    `user_ids` 從 services/permission.py 的 `visible_user_ids()` 來，
    **不要在這裡自己判斷權限**——這個檔案只負責算數學。
    職責分開之後，權限規則改了不必動這裡，算法改了不必動權限。

    TODO(成員3): SELECT SUM(amount) FROM transactions
                 WHERE user_id IN (...) AND date BETWEEN ... GROUP BY kind
                 記得用 Decimal，不要用 float
    """
    raise NotImplementedError("TODO：成員3 尚未實作")


def by_category(db: Session, user_ids: list[int], period: str) -> list[dict[str, Any]]:
    """
    各分類的金額與佔比，畫圓環圖用。

    TODO(成員3): 佔比在這裡算好再回傳，前端只負責畫
    """
    raise NotImplementedError("TODO：成員3 尚未實作")


def build_basis(db: Session, user_ids: list[int], period: str) -> dict[str, Any]:
    """
    把要餵給模型的數字全部算好，打包成一個 dict。 ✦ routers/advices.py 會呼叫這支

    ⚠️ 這支的回傳值有兩個用途，兩個都很重要：

    1. 組進 prompt 給模型看（模型只讀數字，不算數字）
    2. **原封不動存進 `advices.basis_json`**，讓使用者可以驗算

    第 2 點是「每條建議都要附依據」這條規則的實作。
    使用者看到建議時能展開看到「這是根據哪些數字得出的」，
    沒有依據的建議就是黑盒子，使用者不會信。

    TODO(成員3): 決定要放哪些數字進去。建議至少包含
                 收入、支出、結餘、儲蓄率、各分類佔比、
                 預算使用率、存款目標達成狀態、跟上個月的比較
    """
    raise NotImplementedError("TODO：成員3 尚未實作")
