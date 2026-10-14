"""
把記帳句子裡的時間詞換成日期：「昨天」「上禮拜三」「9/17」「17號」→ YYYY-MM-DD。

領域：記帳

    from app.toolkit import dates

    dates.resolve("昨天", "2026-10-02")       # "2026-10-01"
    dates.resolve("28號", "2026-10-02")       # "2026-09-28"（還沒到的日子算上個月）
    dates.resolve("上禮拜三", "2026-10-02")   # "2026-09-23"
    dates.resolve("早餐", "2026-10-02")       # None：認不出來

    dates.find("昨天晚餐120", "2026-10-02")  # "2026-10-01"：在一整句裡找第一個時間詞

⚠️ 為什麼不讓模型自己算：日期算錯差一天，使用者幾乎不會發現，月統計卻已經跑掉。
   模型負責「把時間詞抽出來」，換算交給這裡——這是確定的計算，不是語意判斷。
⚠️ 「今天」以呼叫的人傳進來的 today 為準（台灣時間），這裡不讀系統時鐘，測試才測得準。
"""

from __future__ import annotations

import re
from datetime import date, timedelta

__all__ = ["resolve", "find"]

_REL = {"今天": 0, "今日": 0, "昨天": -1, "昨日": -1, "前天": -2, "前日": -2, "大前天": -3, "明天": 1}
_WEEK = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
_DIGIT = {"零": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _num(s: str) -> int | None:
    """「17」「十七」「二十一」「三十」→ 整數。認不出來回 None。"""
    s = s.strip()
    if s.isdigit():
        return int(s)
    if not s or any(ch not in _DIGIT and ch != "十" for ch in s):
        return None
    if "十" not in s:
        return _DIGIT[s] if len(s) == 1 else None
    left, _, right = s.partition("十")
    tens = _DIGIT.get(left, None) if left else 1
    ones = _DIGIT.get(right, None) if right else 0
    if tens is None or ones is None:
        return None
    return tens * 10 + ones


def _safe(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def resolve(expr: str | None, today: str | date) -> str | None:
    """時間詞 → YYYY-MM-DD；認不出來回 None。"""
    if expr is None:
        return None
    t = today if isinstance(today, date) else date.fromisoformat(str(today))
    s = re.sub(r"\s+", "", str(expr))
    if not s:
        return None

    # 已經是日期
    try:
        return date.fromisoformat(s).isoformat()
    except ValueError:
        pass

    # 今天、昨天、前天……（「大前天」要比「前天」先比）
    for word in sorted(_REL, key=len, reverse=True):
        if s.startswith(word):
            return (t + timedelta(days=_REL[word])).isoformat()

    # 上禮拜三／上週三／上星期三、這禮拜五、禮拜一、週日
    m = re.match(r"^(上上|上|這|本)?(?:個)?(禮拜|週|周|星期)([一二三四五六日天])", s)
    if m:
        target = _WEEK[m.group(3)]
        this_monday = t - timedelta(days=t.weekday())
        weeks_back = {"上上": 2, "上": 1}.get(m.group(1) or "", 0)
        d = this_monday - timedelta(weeks=weeks_back) + timedelta(days=target)
        if not m.group(1) and d > t:            # 只說「禮拜五」而今天才禮拜三：指的是上一個禮拜五
            d -= timedelta(weeks=1)
        return d.isoformat()

    # 9/17、9-17、9月17日、九月十七號
    m = re.match(r"^(\d{1,2}|[一二三四五六七八九十]+)(?:[/\-]|月)(\d{1,2}|[一二三四五六七八九十]+)(?:日|號)?", s)
    if m:
        mo, dd = _num(m.group(1)), _num(m.group(2))
        if mo and dd:
            d = _safe(t.year, mo, dd)
            if d and d > t:                       # 還沒到的日子：去年
                d = _safe(t.year - 1, mo, dd)
            return d.isoformat() if d else None

    # 17號、17日、十七號（這個月；還沒到就算上個月）
    m = re.match(r"^(\d{1,2}|[一二三四五六七八九十]+)(?:號|日)", s)
    if m:
        dd = _num(m.group(1))
        if dd:
            d = _safe(t.year, t.month, dd)
            if d is None or d > t:
                first = t.replace(day=1) - timedelta(days=1)
                d = _safe(first.year, first.month, dd)
            return d.isoformat() if d else None

    return None


#: find() 只認這幾種開頭：不會跟一般用字撞在一起的時間詞
#: （「一日遊」「生日」的「日」太常見，在整句裡找時「17日」不認、「17號」才認）
_FIND = re.compile(
    r"大前天|前天|昨天|昨日|今天|今日|明天"
    r"|(?:上上|上|這|本)(?:個)?(?:禮拜|週|周|星期)[一二三四五六日天]"
    r"|(?:禮拜|星期)[一二三四五六日天]"
    r"|(?<!\d)\d{1,2}/\d{1,2}(?!\d)"
    r"|(?<![\d一二三四五六七八九十])(?:\d{1,2}|[一二三四五六七八九十]+)月(?:\d{1,2}|[一二三四五六七八九十]+)[日號]"
    r"|(?<![\d月])\d{1,2}號"
)


def find(text: str | None, today: str | date) -> str | None:
    """在一整句裡找第一個時間詞並換算；句子裡沒有時間詞回 None。

    跟 resolve 的差別：resolve 吃「已經抽出來的時間詞」，find 吃「整句話」，
    所以只認不會誤判的寫法（例如「17號」認、「17日」不認，因為「一日遊」）。
    """
    if not text:
        return None
    for m in _FIND.finditer(re.sub(r"\s+", "", str(text))):
        day = resolve(m.group(0), today)
        if day:
            return day
    return None
