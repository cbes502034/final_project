"""
金額處理。財務系統的金額一律走這裡，不要用 float。

===========================================================================
為什麼不能用 float
===========================================================================
浮點數在二進位下沒辦法精確表示 0.1、0.2 這種十進位小數：

    >>> 0.1 + 0.2
    0.30000000000000004

單筆看不出來，累加幾千筆之後你會得到 12345.670000000002，
或是「收入 − 支出 ≠ 結餘」差了幾分錢。**財務系統不能接受這個。**

正確做法是用 Decimal，而且資料庫欄位用 NUMERIC(14, 2)。
SQLAlchemy 查出來就會是 Decimal，全程不要碰 float。

===========================================================================
這個工具的三個責任
===========================================================================
1. **安全地把各種輸入轉成 Decimal**（前端傳來的可能是字串、整數、甚至 None）
2. **除法不會炸**（分母為零是家常便飯：收入 0 的月份算儲蓄率）
3. **統一的四捨五入規則**（Python 預設是銀行家捨入，會讓會計看不懂）
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

__all__ = [
    "InvalidAmount",
    "ZERO",
    "CENT",
    "to_decimal",
    "quantize",
    "add",
    "ratio",
    "percent",
    "fmt",
]

ZERO = Decimal("0")
CENT = Decimal("0.01")


class InvalidAmount(ValueError):
    """
    輸入沒辦法轉成金額時丟出。

    路由收到這個例外應該轉成 HTTP 422，不是 500——
    那是使用者送錯資料，不是我們的程式壞了。
    """


def to_decimal(value, *, allow_negative: bool = True) -> Decimal:
    """
    把任何輸入安全地轉成 Decimal。

    參數
        value: 要轉換的值。接受 int、str、Decimal、float。
            float 會先轉成字串再轉 Decimal，避免帶進二進位誤差。
        allow_negative (bool): 是否允許負數。記帳金額通常要設 False，
            因為收支方向是用 kind 欄位表示的，金額本身應該永遠是正的。

    回傳
        Decimal: 轉換後的值。

    丟出
        InvalidAmount: 值是 None、空字串、不是數字、
            或 allow_negative=False 時傳了負數。

    範例
        >>> to_decimal("320")
        Decimal('320')
        >>> to_decimal(320.5)               # float 先轉字串，不會有誤差
        Decimal('320.5')
        >>> to_decimal("1,200")             # 逗號會被去掉
        Decimal('1200')
        >>> to_decimal(-5, allow_negative=False)
        Traceback (most recent call last):
        InvalidAmount: 金額不可以是負數，收到的是 -5

    注意
        傳 float 進來雖然會被正確處理，但**上游就不要產生 float**。
        這個轉換是最後一道防線，不是讓你放心用 float 的許可證。
    """
    if value is None:
        raise InvalidAmount("金額不可以是空的")
    if isinstance(value, Decimal):
        d = value
    else:
        text = str(value).strip().replace(",", "").replace("　", "")
        if not text:
            raise InvalidAmount("金額不可以是空字串")
        try:
            d = Decimal(text)
        except InvalidOperation as exc:
            raise InvalidAmount(f"這不是有效的金額：{value!r}") from exc
    if not d.is_finite():
        raise InvalidAmount(f"金額不可以是無限大或 NaN：{value!r}")
    if not allow_negative and d < 0:
        raise InvalidAmount(f"金額不可以是負數，收到的是 {value}")
    return d


def quantize(value, places: int = 2) -> Decimal:
    """
    四捨五入到指定小數位，用**一般人認知的四捨五入**。

    參數
        value: 要處理的值，會先經過 to_decimal。
        places (int): 保留幾位小數，預設 2。

    回傳
        Decimal: 處理後的值。

    丟出
        InvalidAmount: value 轉不成 Decimal。

    範例
        >>> quantize("320.455")
        Decimal('320.46')
        >>> quantize("0.125")              # 一般四捨五入 → 0.13
        Decimal('0.13')

    注意
        **Python 的 round() 用的是銀行家捨入**（0.125 會變成 0.12），
        那在統計上比較準，但會讓對帳的人覺得系統算錯。
        這裡刻意用 ROUND_HALF_UP，跟一般人的直覺一致。
    """
    d = to_decimal(value)
    exp = Decimal(1).scaleb(-places)
    return d.quantize(exp, rounding=ROUND_HALF_UP)


def add(*values) -> Decimal:
    """
    把多個金額加起來，過程全程 Decimal。

    參數
        *values: 任意多個金額。None 會被當成 0 跳過。

    回傳
        Decimal: 總和。沒有任何值時回傳 0。

    丟出
        InvalidAmount: 其中某個值轉不成 Decimal。

    範例
        >>> add("320", 55, None, Decimal("1200"))
        Decimal('1575')
    """
    total = ZERO
    for v in values:
        if v is None:
            continue
        total += to_decimal(v)
    return total


def ratio(part, whole, default: Decimal | None = None) -> Decimal:
    """
    算比例（0 ~ 1 之間的小數），**分母是零也不會爆掉**。

    參數
        part: 分子。
        whole: 分母。
        default (Decimal | None): 分母是 0 時回傳什麼。
            傳 None 就回傳 0。

    回傳
        Decimal: part / whole，或分母為 0 時的 default。

    丟出
        InvalidAmount: 參數轉不成 Decimal。

    範例
        >>> ratio("41230", "48000")
        Decimal('0.8589583333333333333333333333')
        >>> ratio("100", "0")              # 不會丟 ZeroDivisionError
        Decimal('0')
        >>> ratio("100", "0", default=Decimal("2"))
        Decimal('2')

    注意
        這支存在的理由：儲蓄率 = 結餘 ÷ 收入，
        而**收入為 0 的月份是真的會出現的**（學生、無收入的家庭成員）。
        直接除下去整支 API 就 500 了。
    """
    p, w = to_decimal(part), to_decimal(whole)
    if w == 0:
        return ZERO if default is None else default
    return p / w


def percent(part, whole, places: int = 1, default: Decimal | None = None) -> Decimal:
    """
    算百分比（0 ~ 100），分母是零也不會爆掉。

    參數
        part: 分子。
        whole: 分母。
        places (int): 保留幾位小數，預設 1。
        default (Decimal | None): 分母為 0 時的比例值（注意是比例不是百分比）。

    回傳
        Decimal: 百分比數值，例如 85.9 代表 85.9%。

    範例
        >>> percent("41230", "48000")
        Decimal('85.9')
        >>> percent("1", "3", places=2)
        Decimal('33.33')
    """
    return quantize(ratio(part, whole, default) * 100, places)


def fmt(value, symbol: str = "NT$ ") -> str:
    """
    把金額格式化成畫面上顯示的樣子。

    參數
        value: 金額。
        symbol (str): 前綴符號，不要就傳空字串。

    回傳
        str: 加了千分位的字串。小數是 .00 時會省略小數點。

    範例
        >>> fmt("41230")
        'NT$ 41,230'
        >>> fmt("320.5")
        'NT$ 320.50'
        >>> fmt("-1200", symbol="")
        '-1,200'

    注意
        這支是給**後端要產生文字時**用的（例如財務建議的內文）。
        一般的 API 回應請直接回數字，讓前端自己格式化——
        回字串的話前端就沒辦法拿去算或排序了。
    """
    d = to_decimal(value)
    if d == d.to_integral_value():
        return f"{symbol}{int(d):,}"
    return f"{symbol}{quantize(d):,.2f}"
