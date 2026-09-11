"""
期間與日期。把「2026-09」這種字串換算成可以丟進 SQL 的日期範圍。

===========================================================================
為什麼需要這個工具
===========================================================================
統計功能到處都要做同一件事：把使用者選的月份換成查詢用的起訖日期。

自己寫會踩到的坑：

    二月是 28 還是 29 天？          閏年
    月底是 30 還是 31？             四月 30、五月 31
    跨年怎麼算？                    2026-12 的下一個月是 2027-01
    邊界要含還是不含？              12/31 23:59 的紀錄算不算這個月

這些每個人各寫一次，就會有四種不同的錯法。統一在這裡處理。

===========================================================================
統一的約定
===========================================================================
**所有回傳的範圍都是「起訖都含」（closed interval）。**

    month_range("2026-09")  →  (2026-09-01, 2026-09-30)

所以 SQL 要寫成 `BETWEEN start AND end`，或是
`occurred_on >= start AND occurred_on <= end`。

**不要**寫成 `< 下個月一號`，兩種寫法混用遲早會少算或多算一天。
"""

from __future__ import annotations

import calendar
import re
from datetime import date

__all__ = [
    "InvalidPeriod",
    "current_month",
    "current_year",
    "is_month",
    "is_year",
    "month_range",
    "year_range",
    "period_range",
    "shift_month",
    "recent_months",
    "recent_years",
    "is_incomplete_year",
]

_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")
_YEAR_RE = re.compile(r"^(\d{4})$")


class InvalidPeriod(ValueError):
    """
    期間字串的格式不對時丟出。

    路由收到這個例外時，應該轉成 HTTP 422（格式錯誤），不是 500。
    可以直接用 toolkit.errors.unprocessable() 包裝。
    """


def current_month(today: date | None = None) -> str:
    """
    取得本月的期間字串。

    參數
        today (date | None): 用來當「今天」的日期。傳 None 就用系統日期。
            **測試時一定要傳**，不然測試會隨著日期改變而時好時壞。

    回傳
        str: 例如 "2026-09"

    範例
        >>> current_month(date(2026, 9, 11))
        '2026-09'
    """
    d = today or date.today()
    return f"{d.year:04d}-{d.month:02d}"


def current_year(today: date | None = None) -> str:
    """
    取得今年的期間字串。

    參數
        today (date | None): 同 current_month。

    回傳
        str: 例如 "2026"
    """
    d = today or date.today()
    return f"{d.year:04d}"


def is_month(period: str) -> bool:
    """
    判斷這個字串是不是月份格式（YYYY-MM）。

    參數
        period (str): 待檢查的字串。

    回傳
        bool: 格式正確且月份在 1~12 之間才是 True。

    範例
        >>> is_month("2026-09"), is_month("2026-13"), is_month("2026")
        (True, False, False)
    """
    m = _MONTH_RE.match(period or "")
    return bool(m) and 1 <= int(m.group(2)) <= 12


def is_year(period: str) -> bool:
    """
    判斷這個字串是不是年份格式（YYYY）。

    參數
        period (str): 待檢查的字串。

    回傳
        bool
    """
    return bool(_YEAR_RE.match(period or ""))


def month_range(period: str) -> tuple[date, date]:
    """
    把月份字串換成起訖日期。**起訖都含。**

    參數
        period (str): "YYYY-MM"，例如 "2026-09"。

    回傳
        tuple[date, date]: (該月第一天, 該月最後一天)

    丟出
        InvalidPeriod: 格式不對，或月份不在 1~12。

    範例
        >>> month_range("2026-09")
        (datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
        >>> month_range("2024-02")          # 閏年，月底是 29
        (datetime.date(2024, 2, 1), datetime.date(2024, 2, 29))

    注意
        月底用 calendar.monthrange 算，不是寫死 30 或 31。
    """
    m = _MONTH_RE.match(period or "")
    if not m:
        raise InvalidPeriod(f"月份格式要是 YYYY-MM，收到的是 {period!r}")
    year, month = int(m.group(1)), int(m.group(2))
    if not 1 <= month <= 12:
        raise InvalidPeriod(f"月份要在 01~12 之間，收到的是 {period!r}")
    last = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def year_range(period: str) -> tuple[date, date]:
    """
    把年份字串換成起訖日期。**起訖都含。**

    參數
        period (str): "YYYY"，例如 "2026"。

    回傳
        tuple[date, date]: (1月1日, 12月31日)

    丟出
        InvalidPeriod: 格式不對。

    範例
        >>> year_range("2026")
        (datetime.date(2026, 1, 1), datetime.date(2026, 12, 31))
    """
    if not is_year(period):
        raise InvalidPeriod(f"年份格式要是 YYYY，收到的是 {period!r}")
    y = int(period)
    return date(y, 1, 1), date(y, 12, 31)


def period_range(period: str) -> tuple[str, date, date]:
    """
    自動判斷是月還是年，回傳型別與起訖日期。

    路由收到 `period` 參數時用這支，不必自己判斷格式。

    參數
        period (str): "YYYY-MM" 或 "YYYY"。

    回傳
        tuple[str, date, date]: ("month" 或 "year", 起, 訖)

    丟出
        InvalidPeriod: 兩種格式都不符合。

    範例
        >>> period_range("2026-09")[0]
        'month'
        >>> period_range("2026")[0]
        'year'
    """
    if is_month(period):
        s, e = month_range(period)
        return "month", s, e
    if is_year(period):
        s, e = year_range(period)
        return "year", s, e
    raise InvalidPeriod(f"期間要是 YYYY-MM 或 YYYY，收到的是 {period!r}")


def shift_month(period: str, delta: int) -> str:
    """
    往前或往後移動幾個月，自動處理跨年。

    參數
        period (str): "YYYY-MM"。
        delta (int): 正數往後、負數往前。

    回傳
        str: 移動後的月份字串。

    丟出
        InvalidPeriod: 格式不對。

    範例
        >>> shift_month("2026-09", -1)
        '2026-08'
        >>> shift_month("2026-01", -1)      # 跨年
        '2025-12'
        >>> shift_month("2026-12", 2)
        '2027-02'
    """
    m = _MONTH_RE.match(period or "")
    if not m:
        raise InvalidPeriod(f"月份格式要是 YYYY-MM，收到的是 {period!r}")
    year, month = int(m.group(1)), int(m.group(2))
    total = year * 12 + (month - 1) + delta
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def recent_months(period: str, count: int) -> list[str]:
    """
    取得包含自己在內、往前數 count 個月的清單，**由舊到新排序**。

    畫近 6 個月的趨勢圖時用這支。

    參數
        period (str): 最後一個月，"YYYY-MM"。
        count (int): 要幾個月，至少 1。

    回傳
        list[str]: 由舊到新。長度等於 count。

    丟出
        InvalidPeriod: 格式不對。
        ValueError: count 小於 1。

    範例
        >>> recent_months("2026-09", 3)
        ['2026-07', '2026-08', '2026-09']

    注意
        回傳的順序是**舊 → 新**，直接丟進圖表就是正確的時間軸方向。
    """
    if count < 1:
        raise ValueError(f"count 至少要是 1，收到的是 {count}")
    return [shift_month(period, -i) for i in range(count - 1, -1, -1)]


def recent_years(period: str, count: int) -> list[str]:
    """
    取得包含自己在內、往前數 count 年的清單，由舊到新。

    參數
        period (str): 最後一年，"YYYY"。
        count (int): 要幾年，至少 1。

    回傳
        list[str]: 由舊到新。

    丟出
        InvalidPeriod: 格式不對。
        ValueError: count 小於 1。

    範例
        >>> recent_years("2026", 3)
        ['2024', '2025', '2026']
    """
    if count < 1:
        raise ValueError(f"count 至少要是 1，收到的是 {count}")
    if not is_year(period):
        raise InvalidPeriod(f"年份格式要是 YYYY，收到的是 {period!r}")
    y = int(period)
    return [f"{y - i:04d}" for i in range(count - 1, -1, -1)]


def is_incomplete_year(period: str, today: date | None = None) -> bool:
    """
    判斷這個年度是不是還沒結束。

    ⚠️ **年度統計一定要用這支標示「未完整」。**

    2026 年才過了 9 個月，總支出當然比 2025 整年少。
    使用者看到「今年支出變少了」會誤以為自己變節省了——
    **這種誤導比沒有這個功能更糟。**

    參數
        period (str): "YYYY"。
        today (date | None): 用來當「今天」的日期，測試時要傳。

    回傳
        bool: 這一年還沒過完就是 True。未來的年份也算 True。

    範例
        >>> is_incomplete_year("2026", date(2026, 9, 11))
        True
        >>> is_incomplete_year("2025", date(2026, 9, 11))
        False
    """
    if not is_year(period):
        raise InvalidPeriod(f"年份格式要是 YYYY，收到的是 {period!r}")
    d = today or date.today()
    return int(period) >= d.year
