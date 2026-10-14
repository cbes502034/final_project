"""toolkit/dates.py：記帳句子裡的時間詞換成日期。今天固定是 2026-10-02（禮拜五）。"""

import pytest

from app.toolkit import dates

TODAY = "2026-10-02"


@pytest.mark.parametrize("expr, want", [
    ("2026-09-17", "2026-09-17"),
    ("今天", "2026-10-02"),
    ("昨天", "2026-10-01"),
    ("前天", "2026-09-30"),
    ("大前天", "2026-09-29"),          # 要比「前天」先比到
    ("昨天晚上", "2026-10-01"),        # 後面多的字不影響
    ("9/17", "2026-09-17"),
    ("9月17日", "2026-09-17"),
    ("九月十七號", "2026-09-17"),
    ("12/25", "2025-12-25"),           # 還沒到的日子算去年
    ("1號", "2026-10-01"),
    ("28號", "2026-09-28"),            # 還沒到的日子算上個月
    ("二十一號", "2026-09-21"),
    ("上禮拜三", "2026-09-23"),
    ("上週一", "2026-09-21"),
    ("這禮拜一", "2026-09-28"),
    ("禮拜一", "2026-09-28"),
    ("禮拜六", "2026-09-26"),          # 只說禮拜六、今天才禮拜五：上一個禮拜六
    ("星期日", "2026-09-27"),
])
def test_認得的時間詞(expr, want):
    assert dates.resolve(expr, TODAY) == want


@pytest.mark.parametrize("expr", [None, "", "早餐", "2/30", "32號", "上禮拜"])
def test_認不出來就回_None_不要猜(expr):
    assert dates.resolve(expr, TODAY) is None


def test_today_可以傳_date():
    from datetime import date
    assert dates.resolve("昨天", date(2026, 3, 1)) == "2026-02-28"


@pytest.mark.parametrize("text, want", [
    ("昨天晚餐120", "2026-10-01"),
    ("早餐55，大前天加油800", "2026-09-29"),
    ("上禮拜三看電影300", "2026-09-23"),
    ("9/17 全聯 600", "2026-09-17"),
    ("九月十七號買鞋", "2026-09-17"),
    ("28號繳電費", "2026-09-28"),
])
def test_find_在整句裡找時間詞(text, want):
    assert dates.find(text, TODAY) == want


@pytest.mark.parametrize("text", [None, "", "早餐55", "一日遊1200", "生日蛋糕500", "155號公車15"])
def test_find_沒有時間詞或容易誤判的寫法回_None(text):
    assert dates.find(text, TODAY) is None
