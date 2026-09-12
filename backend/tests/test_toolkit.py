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

from app.toolkit import (  # noqa: E402
    alerts, scope, roles, images, money, passwords, period, tokens,
)


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


# ===========================================================================
# alerts —— 階段性提醒的門檻
# ===========================================================================
def test_百分比是捨去不是四捨五入():
    """79.9% 還沒到 80%，不可以提前響。"""
    assert alerts.usage_percent(3995, 5000) == 79
    assert alerts.usage_percent(4000, 5000) == 80


def test_可支配上限是零的時候不會炸():
    """收入還沒入帳、或存款目標比收入高的月份，上限會是 0 或負數。"""
    assert alerts.usage_percent(100, 0) == alerts.MAX_PERCENT
    assert alerts.usage_percent(0, 0) == 0
    assert alerts.usage_percent(500, -200) == alerts.MAX_PERCENT


def test_一次跨過好幾個門檻要全部回傳():
    """80% 的時候記一筆大的直接跳到 105%，85 和 100 都該通知。"""
    assert alerts.crossed(78, 105, [60, 85, 100]) == [85, 100]


def test_本來就在門檻以上不會重複觸發():
    """90% 再記一筆變 92%，`92 >= 85` 還是成立——但那不算新跨過。"""
    assert alerts.crossed(90, 92, [60, 85, 100]) == []


def test_剛好踩到門檻算跨過():
    assert alerts.crossed(79, 80, [80]) == [80]


def test_同一個月只響一次():
    """使用者在 80% 附近來回記帳、刪除、再記，不該被連環轟炸。"""
    assert alerts.should_fire(80, 78, 90, None, "2026-09") is True
    assert alerts.should_fire(80, 78, 90, "2026-09", "2026-09") is False
    # 下個月重新開始
    assert alerts.should_fire(80, 78, 90, "2026-08", "2026-09") is True


def test_門檻要在合理範圍():
    assert alerts.validate_percent("80") == 80
    for bad in (0, 201, -5, "八十", None):
        with pytest.raises(alerts.InvalidThreshold):
            alerts.validate_percent(bad)


def test_重複的門檻會被去掉():
    """留著的話同一次跨越會發兩則一模一樣的通知。"""
    assert alerts.normalize(["100", 60, 85, 60, 100]) == [60, 85, 100]


def test_下一個門檻():
    assert alerts.next_threshold(72, [60, 85, 100]) == 85
    assert alerts.next_threshold(100, [60, 85, 100]) is None


# ===========================================================================
# scope —— 可見範圍的兩道篩選
# ===========================================================================
_G = [
    {"guardian_id": "U1", "ward_id": "U3"},
    {"guardian_id": "U1", "ward_id": "U4"},
    {"guardian_id": "U2", "ward_id": "U4"},
]
_M = [
    {"group_id": "G1", "user_id": "U1"},
    {"group_id": "G1", "user_id": "U3"},
    {"group_id": "G3", "user_id": "U3"},
]


def test_可見範圍只看監管關係不看角色():
    """家長沒有例外：沒指派監管誰，就只看得到自己。"""
    assert scope.visible_users("U1", _G) == {"U1", "U3", "U4"}
    assert scope.visible_users("U2", _G) == {"U2", "U4"}


def test_被監管的人看不到任何別人():
    """監管是單向的——你看得到我，不代表我看得到你。"""
    assert scope.visible_users("U3", _G) == {"U3"}


def test_沒有任何監管關係時只看得到自己():
    assert scope.visible_users("U9", []) == {"U9"}


def test_群組是第二道獨立的篩選():
    assert scope.visible_groups("U1", _M) == {"G1"}
    assert scope.visible_groups("U3", _M) == {"G1", "G3"}


def test_兩道都要過才看得到():
    """
    我監管 U3，但 U3 在 G3（我沒加入）記的帳不該出現在我的清單上。
    只做一道篩選就會漏掉這種情況。
    """
    rows = [
        {"user_id": "U3", "group_id": "G1"},   # 兩道都過
        {"user_id": "U3", "group_id": "G3"},   # 人可以，帳本不行
        {"user_id": "U2", "group_id": "G1"},   # 帳本可以，人不行
    ]
    users = scope.visible_users("U1", _G)
    groups = scope.visible_groups("U1", _M)
    assert scope.filter_rows(rows, users, groups) == [
        {"user_id": "U3", "group_id": "G1"}
    ]


def test_沒權限要丟例外不是回空的():
    """回空陣列的話，前端分不出「這個人沒記帳」和「你不能看」。"""
    users = scope.visible_users("U3", _G)
    scope.require_user("U3", users)                 # 自己，不該丟
    with pytest.raises(scope.Forbidden):
        scope.require_user("U1", users)
    with pytest.raises(scope.Forbidden):
        scope.require_group("G2", scope.visible_groups("U3", _M))


def test_欄位名稱長短都吃得下():
    """ORM 是 guardian_id，mock 是 guardian，測試不該為此寫兩套。"""
    short = [{"guardian": "U1", "ward": "U3"}]
    assert scope.visible_users("U1", short) == {"U1", "U3"}


# ===========================================================================
# roles —— 角色能做哪些治理動作
# ===========================================================================
#
# 這個模組的全部重點是一句話：
# 角色決定「能做什麼」，監管關係決定「看得到誰」，兩者不交叉。


def test_master_不是家庭角色():
    """家庭裡只有家長與子女。

    早期版本把「家裡權限最高的人」也叫 master，於是一個家庭有三種角色。
    但 master 現在是平台管理員——混在一起的話，
    任何一個家長都會變成能停權別人家使用者的人。
    """
    assert roles.FAMILY_ROLES == ("parent", "child")
    assert roles.is_family_role("parent")
    assert roles.is_family_role("child")
    assert not roles.is_family_role("master")
    assert not roles.is_family_role("member")


def test_治理動作只有家長能做():
    assert roles.can_govern("parent", "invite_member")
    assert not roles.can_govern("child", "invite_member")
    assert roles.can_govern("parent", "create_guardianship")
    assert not roles.can_govern("child", "create_guardianship")


def test_開帳本不分角色():
    """記帳的分類方式是個人的事，不該由家裡的階級決定。"""
    assert roles.can_govern("parent", "create_group")
    assert roles.can_govern("child", "create_group")


def test_不認得的動作一律擋掉():
    """寧可擋掉打錯字的呼叫，也不要查不到就放行。

    放行的那種寫法會讓漏掉的權限檢查看起來像正常運作——
    那是最難發現的一種壞法。
    """
    assert not roles.can_govern("parent", "invite_membre")
    assert not roles.can_govern("parent", "")
    with pytest.raises(scope.Forbidden):
        roles.require_govern("parent", "delete_everything")


def test_治理動作裡沒有任何一項是看資料():
    """可見範圍只能來自 guardianships，不然「誰看得到我」就列不出來了。"""
    for action in roles.GOVERN_ACTIONS:
        for bad in ("view_transactions", "read_ledger", "see_user"):
            assert action != bad
    # view_family_overview 是「有沒有這個功能」，不是「看得到誰」——
    # 進去之後看得到哪幾個人，仍然要過 scope 那一關
    assert roles.can_govern("parent", "view_family_overview")


def test_代設存款目標看的是監管關係不是年齡():
    """系統只提供功能，幾歲該被管是那一家自己的事。

    而且年齡會變——用它當權限依據，權限就會在某個生日當天自己改變。
    """
    assert roles.can_set_goal_for("U1", "U1", _G)      # 自己一定可以
    assert roles.can_set_goal_for("U1", "U3", _G)      # U1 監管 U3
    assert roles.can_set_goal_for("U1", "U4", _G)
    assert not roles.can_set_goal_for("U1", "U2", _G)  # 沒監管關係就不行
    assert not roles.can_set_goal_for("U3", "U4", _G)

    with pytest.raises(scope.Forbidden):
        roles.require_set_goal("U3", "U4", _G)


def test_家長身分本身不給代設的權力():
    """是家長也不能改任何人的目標——要先有那條監管關係。"""
    assert not roles.can_set_goal_for("U2", "U3", _G)


def test_平台管理員只能停權與查稽核():
    assert roles.can_platform("suspend_user", True)
    assert roles.can_platform("unsuspend_user", True)
    assert roles.can_platform("read_audit_log", True)


def test_平台管理員讀不到任何財務資料():
    """停權是關門，不是配鑰匙。

    跟「管理人員不可以進入子女的帳號」是同一條原則。一個能讀全系統
    消費明細的帳號，比家長越權嚴重得多——家長至少還在 guardianships
    表上留下痕跡、被監管的人看得到。
    """
    for action in ("read_transactions", "view_ledger", "impersonate_user",
                   "read_user", "join_family"):
        assert not roles.can_platform(action, True)
        with pytest.raises(scope.Forbidden):
            roles.require_platform(action, True)


def test_不是平台管理員就什麼都不能做():
    assert not roles.can_platform("suspend_user", False)
    assert not roles.can_platform("suspend_user", None)
    with pytest.raises(scope.Forbidden):
        roles.require_platform("suspend_user", False)
