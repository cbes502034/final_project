"""
階段性提醒：算出「這次支出跨過了哪幾個門檻」。

負責人：成員3（數字與建議）｜通知的寫入是成員4

===========================================================================
這個工具在解什麼問題
===========================================================================
使用者可以自己設幾個百分比門檻，例如 60%／85%／100%。
每次記一筆帳，支出佔「可支配上限」的比例會往上走，
跨過哪一個門檻，就要發一則通知。

聽起來只是 `if percent >= threshold`，但那樣寫會有三個 bug：

1. **每記一筆都會重發。**
   已經 90% 了，再記一筆變 92%，`92 >= 85` 還是成立，於是又響一次。
   → 要比較的是「這次之前」和「這次之後」，跨過的當下才算。

2. **一次跨過好幾個門檻只響一次。**
   80% 的時候記了一筆大的，直接跳到 105%，
   85% 和 100% 兩個門檻都該通知，不能只挑一個。

3. **下個月要重新開始。**
   門檻在九月響過了，十月支出歸零再爬上來，還是要響。
   → 用 `fired_period`（'2026-09'）記住上次是哪個月響的。

===========================================================================
怎麼用
===========================================================================
    from app.toolkit import alerts, money

    before = alerts.usage_percent(spent_before, allowance)   # 78
    after  = alerts.usage_percent(spent_after,  allowance)   # 103

    for rule in rules:                       # 使用者設的門檻，從 alert_rules 查
        if not alerts.should_fire(rule.percent, before, after,
                                  rule.fired_period, period_key):
            continue
        建立通知(rule)                        # ← 成員4 的 notifications
        rule.fired_period = period_key       # 記住這個月響過了

想一次拿到所有跨過的門檻：

    hit = alerts.crossed(before, after, [60, 85, 100])       # [85, 100]

===========================================================================
可支配上限是什麼
===========================================================================
    可支配上限 = 本月收入 − 每月存款目標

支出超過上限，就代表這個月存不到原本設定的金額。
所以百分比算的是「花掉可支配額度的幾成」，不是「花掉收入的幾成」。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Sequence

from .money import to_decimal

__all__ = [
    "InvalidThreshold",
    "MIN_PERCENT",
    "MAX_PERCENT",
    "validate_percent",
    "normalize",
    "usage_percent",
    "crossed",
    "should_fire",
    "next_threshold",
    "describe",
]


class InvalidThreshold(ValueError):
    """門檻不是 1~200 之間的整數。"""


# 0% 沒有意義（一開始就成立），超過 200% 也沒有意義（早就該提醒了）
MIN_PERCENT = 1
MAX_PERCENT = 200


def validate_percent(value: object) -> int:
    """把使用者輸入的門檻轉成 1~200 的整數，不合法就丟 InvalidThreshold。

    >>> validate_percent("80")
    80
    >>> validate_percent(0)
    Traceback (most recent call last):
    app.toolkit.alerts.InvalidThreshold: 門檻要在 1 到 200 之間，收到 0
    """
    try:
        n = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise InvalidThreshold(f"門檻要是整數，收到 {value!r}") from None
    if n < MIN_PERCENT or n > MAX_PERCENT:
        raise InvalidThreshold(f"門檻要在 {MIN_PERCENT} 到 {MAX_PERCENT} 之間，收到 {n}")
    return n


def normalize(values: Iterable[object]) -> list[int]:
    """整理一串門檻：驗證、去重、由小到大。

    重複的門檻會讓同一次跨越發兩則一模一樣的通知，所以這裡去掉。

    >>> normalize(["100", 60, 85, 60])
    [60, 85, 100]
    """
    return sorted({validate_percent(v) for v in values})


def usage_percent(spent: object, allowance: object) -> int:
    """支出佔可支配上限的百分比，無條件捨去成整數。

    ⚠️ 上限是 0 或負數時（收入還沒入帳、或存款目標比收入還高），
    除法會炸。這裡的約定是：

    * 上限 <= 0 且已經有支出 → 回 MAX_PERCENT（就是超支到底了）
    * 上限 <= 0 且還沒支出   → 回 0

    >>> usage_percent(4100, 5000)
    82
    >>> usage_percent(100, 0)
    200
    >>> usage_percent(0, 0)
    0
    """
    spent_d = to_decimal(spent)
    allow_d = to_decimal(allowance)
    if allow_d <= 0:
        return MAX_PERCENT if spent_d > 0 else 0
    pct = spent_d / allow_d * Decimal(100)
    return int(pct)  # 捨去：79.9% 還沒到 80%，不該提前響


def crossed(before: int, after: int, thresholds: Sequence[int]) -> list[int]:
    """這次支出「新跨過」的門檻，由小到大。

    判準是 `before < t <= after`：
    等號放在 after 這邊，剛好踩到 80% 算跨過；
    before 用嚴格小於，所以本來就已經在 80% 以上的不會重算。

    >>> crossed(78, 103, [60, 85, 100])
    [85, 100]
    >>> crossed(85, 92, [60, 85, 100])
    []
    >>> crossed(79, 80, [80])
    [80]
    """
    return [t for t in sorted(set(thresholds)) if before < t <= after]


def should_fire(
    threshold: int,
    before: int,
    after: int,
    fired_period: str | None,
    period: str,
) -> bool:
    """這個門檻這次該不該發通知。

    兩個條件都要成立：

    1. 這次真的跨過了這個門檻（`before < threshold <= after`）
    2. 這個月還沒為它發過（`fired_period != period`）

    第 2 點是「同一個月只響一次」的那道閘。少了它，使用者在
    80% 附近來回記帳、刪除、再記，就會被連環轟炸。

    >>> should_fire(80, 78, 90, None, "2026-09")
    True
    >>> should_fire(80, 78, 90, "2026-09", "2026-09")
    False
    >>> should_fire(80, 78, 90, "2026-08", "2026-09")
    True
    """
    if fired_period == period:
        return False
    return bool(crossed(before, after, [threshold]))


def next_threshold(current: int, thresholds: Sequence[int]) -> int | None:
    """還沒到的下一個門檻，沒有就回 None。畫面上拿來提示「再花多少就會提醒你」。

    >>> next_threshold(72, [60, 85, 100])
    85
    >>> next_threshold(100, [60, 85, 100])
    """
    for t in sorted(set(thresholds)):
        if t > current:
            return t
    return None


def describe(threshold: int, spent: object, allowance: object, scope: str = "") -> str:
    """通知上那句話。金額格式交給 money.fmt，這裡只組字。

    >>> describe(85, 4250, 5000, "家用")
    '家用 已用掉可支配額度的 85%（NT$ 4,250 / NT$ 5,000）'
    >>> describe(100, 5200, 5000)
    '已用掉可支配額度的 100%（NT$ 5,200 / NT$ 5,000）'
    """
    from .money import fmt

    head = f"{scope} " if scope else ""
    return (
        f"{head}已用掉可支配額度的 {threshold}%"
        f"（{fmt(spent)} / {fmt(allowance)}）"
    )
