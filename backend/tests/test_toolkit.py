"""
工具箱的測試。

===========================================================================
為什麼工具箱一定要有測試
===========================================================================
`toolkit/` 的定位是「已經寫好、你直接用、不用讀懂內部」。
**那個承諾要有東西撐著**，不然四個人不敢用，還是會自己重寫一份。

這些測試同時也是**最好的使用範例** —— 想知道某支函式怎麼用，
看它的測試比看文件快。
"""

import os
from datetime import date
from decimal import Decimal

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-at-least-32-bytes-long")

import pytest  # noqa: E402

from app.toolkit import images, money, passwords, period, tokens  # noqa: E402


# ===========================================================================
# period —— 期間與日期
# ===========================================================================
def test_月份範圍_起訖都含():
    assert period.month_range("2026-09") == (date(2026, 9, 1), date(2026, 9, 30))


def test_二月會依閏年給對的天數():
    """月底不是寫死的 30 或 31，是用 calendar 算的。"""
    assert period.month_range("2024-02")[1] == date(2024, 2, 29)   # 閏年
    assert period.month_range("2025-02")[1] == date(2025, 2, 28)   # 平年


def test_月份移動會跨年():
    assert period.shift_month("2026-01", -1) == "2025-12"
    assert period.shift_month("2026-12", 2) == "2027-02"


def test_近幾個月是由舊到新():
    """順序錯了趨勢圖的時間軸就是反的。"""
    assert period.recent_months("2026-09", 3) == ["2026-07", "2026-08", "2026-09"]


def test_當年度會被標成未完整():
    """2026 只過了 9 個月，總支出當然比 2025 整年少，不標會誤導使用者。"""
    today = date(2026, 9, 11)
    assert period.is_incomplete_year("2026", today) is True
    assert period.is_incomplete_year("2025", today) is False


def test_期間格式錯誤會丟出可以轉成422的例外():
    with pytest.raises(period.InvalidPeriod):
        period.month_range("2026-13")
    with pytest.raises(period.InvalidPeriod):
        period.month_range("2026")


# ===========================================================================
# money —— 金額
# ===========================================================================
def test_金額轉換不會帶進浮點誤差():
    assert money.to_decimal("320.5") == Decimal("320.5")
    assert money.to_decimal(320.5) == Decimal("320.5")      # float 先轉字串
    assert money.to_decimal("1,200") == Decimal("1200")     # 逗號會被去掉


def test_加總不會出現浮點誤差():
    """0.1 + 0.2 用 float 會得到 0.30000000000000004。"""
    assert money.add("0.1", "0.2") == Decimal("0.3")


def test_四捨五入是一般人的直覺不是銀行家捨入():
    """Python 的 round(0.125, 2) 會得到 0.12，會讓對帳的人覺得系統算錯。"""
    assert money.quantize("0.125") == Decimal("0.13")


def test_分母為零不會爆掉():
    """收入 0 的月份是真的會出現的（學生、無收入成員）。"""
    assert money.ratio("100", "0") == Decimal("0")
    assert money.ratio("100", "0", default=Decimal("2")) == Decimal("2")


def test_負數金額可以被擋下來():
    """記帳金額永遠是正的，收支方向看 kind 欄位。"""
    with pytest.raises(money.InvalidAmount):
        money.to_decimal(-5, allow_negative=False)


def test_百分比():
    assert money.percent("41230", "48000") == Decimal("85.9")


# ===========================================================================
# passwords —— 密碼
# ===========================================================================
def test_同樣的密碼每次雜湊都不一樣():
    """因為有鹽。所以絕對不可以用 == 比對雜湊值。"""
    a = passwords.hash_password("abc12345")
    b = passwords.hash_password("abc12345")
    assert a != b
    assert passwords.verify_password("abc12345", a)
    assert passwords.verify_password("abc12345", b)


def test_錯誤的密碼驗不過():
    h = passwords.hash_password("abc12345")
    assert passwords.verify_password("wrong", h) is False


def test_壞掉的雜湊值不會讓登入路由500():
    assert passwords.verify_password("abc12345", "") is False
    assert passwords.verify_password("abc12345", "不是雜湊值") is False


def test_太弱的密碼會被擋():
    with pytest.raises(passwords.WeakPassword):
        passwords.hash_password("123")            # 太短
    with pytest.raises(passwords.WeakPassword):
        passwords.hash_password("12345678")       # 全部都是數字


# ===========================================================================
# tokens —— JWT
# ===========================================================================
def test_權杖可以發出來也解得開():
    t = tokens.make_access_token(7, extra={"role": "master"})
    payload = tokens.read_access_token(t)
    assert payload["sub"] == "7"
    assert payload["role"] == "master"


def test_refresh不能當成access用():
    """⚠️ 沒這個檢查的話，有效期 14 天的 refresh 就能繞過 30 分鐘的設計。"""
    t, _ = tokens.make_refresh_token(1)
    with pytest.raises(tokens.WrongTokenType):
        tokens.read_access_token(t)


def test_亂打的權杖會被擋下來():
    with pytest.raises(tokens.TokenError):
        tokens.read_token("這不是 JWT")


def test_指紋長度固定且不可逆():
    """sessions 表存這個，不是存 token 原文。"""
    t, _ = tokens.make_refresh_token(1)
    fp = tokens.fingerprint(t)
    assert len(fp) == 64
    assert fp == tokens.fingerprint(t)     # 同樣的輸入永遠同樣的輸出
    assert t not in fp                     # 看不出原文


# ===========================================================================
# images —— 大頭貼
# ===========================================================================
_JPEG = b"\xff\xd8\xff\xe0" + b"0" * 200
_PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 200


def test_看得出真正的圖片格式():
    assert images.sniff_type(_JPEG) == "image/jpeg"
    assert images.sniff_type(_PNG) == "image/png"


def test_改副檔名騙不過去():
    """⚠️ 這是這個模組存在的主要理由。"""
    fake = b"import os; os.system('rm -rf /')"
    assert images.sniff_type(fake) is None
    with pytest.raises(images.InvalidImage):
        images.validate_avatar(fake)


def test_太大的圖片會被擋():
    big = b"\xff\xd8\xff" + b"0" * (300 * 1024)
    with pytest.raises(images.InvalidImage):
        images.validate_avatar(big)


def test_data_uri可以來回轉換():
    uri = images.to_data_uri(_JPEG, "image/jpeg")
    assert uri.startswith("data:image/jpeg;base64,")
    data, mime = images.from_data_uri(uri)
    assert data == _JPEG
    assert mime == "image/jpeg"


def test_data_uri裡宣告的型別不可信():
    """
    使用者可以送 data:image/jpeg;base64,<一個腳本>。
    前面那段是他自己寫的，我們只信解出來之後的檔案開頭。
    """
    import base64

    evil = "data:image/jpeg;base64," + base64.b64encode(b"import os").decode()
    with pytest.raises(images.InvalidImage):
        images.from_data_uri(evil)
