"""
產生微調用的訓練資料：ml/data/train.jsonl（跟 backend/eval/heldout.jsonl 同一種格式）。

領域：記帳（微調是加分項，上線用的是商業 API，見 docs/03-LLM實作規劃.md）

    python ml/make_data.py              # 預設 1500 題，固定亂數種子，每次產生的都一樣
    python ml/make_data.py --n 3000

做法：用模板組句子，答案在組的時候就知道，不用另外標註。
  · 日期：句子裡的時間詞用 backend/app/toolkit/dates.py 換算——跟上線時 postprocess 重算用的是同一支
  · 一段話好幾筆時，前面講的日期會延續到後面（「昨天早餐50，午餐100」兩筆都是昨天）
  · 金額有阿拉伯數字、中文口語（一百二、兩千三、一萬八）、帶單位（元、塊、NT$）、沒講（null）
  · 每一題的「今天」不一樣、分類 id 打亂，偶爾多一兩個家庭自訂分類：逼模型去讀 prompt 裡的分類清單，
    而不是背下「餐飲就是 1」

⚠️ 留出集（backend/eval/heldout.jsonl）是另外寫的，不是這支產生的；這裡會把跟留出集一模一樣的句子剔掉。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import random
import sys
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "ml-only-not-a-real-secret-at-least-32-bytes")

from app import catalog  # noqa: E402
from app.toolkit import dates  # noqa: E402

E, I = "expense", "income"

# 分類 → 說法。(說法, 店家候選)。店家空字串＝不帶店名
WORDS: dict[str, list[tuple[str, list[str]]]] = {
    "餐飲": [("早餐", ["", "全家", "7-11", "美而美"]), ("午餐", [""]), ("晚餐", [""]), ("宵夜", [""]),
           ("便當", ["", "全家", "7-11"]), ("咖啡", ["", "星巴克", "7-11", "路易莎"]), ("拿鐵", ["星巴克", "路易莎"]),
           ("手搖飲", [""]), ("珍奶", [""]), ("牛肉麵", [""]), ("滷肉飯", [""]), ("火鍋", [""]),
           ("早午餐", [""]), ("下午茶", ["", "85度C"]), ("雞排", [""]), ("麵包", ["", "85度C"]),
           ("飯糰", ["全家", "7-11"]), ("鍋貼", ["八方雲集"]), ("漢堡", ["麥當勞", "摩斯"])],
    "交通": [("加油", ["", "中油"]), ("捷運", [""]), ("公車", [""]), ("計程車", [""]), ("高鐵", [""]),
           ("台鐵", [""]), ("停車費", [""]), ("悠遊卡加值", ["", "7-11"]), ("Uber", [""]), ("國道通行費", [""])],
    "居住": [("房租", [""]), ("電費", [""]), ("水費", [""]), ("瓦斯費", [""]), ("管理費", [""]),
           ("網路費", ["", "中華電信"]), ("第四台", [""])],
    "日用品": [("衛生紙", ["", "全聯", "家樂福"]), ("洗衣精", ["", "全聯"]), ("牙膏", ["", "屈臣氏", "康是美"]),
            ("洗髮精", ["屈臣氏", "康是美", ""]), ("沐浴乳", ["", "全聯"]), ("垃圾袋", ["", "全聯"]),
            ("廚房紙巾", ["好市多", ""]), ("清潔劑", ["家樂福", ""])],
    "娛樂": [("電影", ["", "威秀"]), ("KTV", ["", "錢櫃"]), ("Netflix", [""]), ("Spotify", [""]),
           ("遊戲點數", ["", "7-11"]), ("演唱會門票", [""]), ("桌遊", [""]), ("保齡球", [""])],
    "教育": [("補習費", [""]), ("學費", [""]), ("參考書", ["", "誠品", "金石堂"]), ("文具", ["", "誠品"]),
           ("線上課程", [""]), ("英文家教", [""])],
    "醫療": [("掛號費", [""]), ("看牙醫", [""]), ("看診", [""]), ("感冒藥", ["", "大樹藥局"]), ("健檢", [""]),
           ("復健", [""]), ("眼科", [""])],
    "其他": [("運費", [""]), ("禮金", [""]), ("捐款", [""]), ("手機維修", [""]), ("寄包裹", ["", "7-11"])],
    "薪資": [("薪水入帳", [""]), ("領薪水", [""]), ("發薪水", [""]), ("月薪", [""])],
    "獎金": [("年終獎金", [""]), ("績效獎金", [""]), ("三節獎金", [""]), ("年終", [""])],
    "零用金": [("媽媽給零用錢", [""]), ("爸爸給零用金", [""]), ("阿嬤給零用錢", [""])],
    "其他收入": [("退款", ["", "蝦皮"]), ("賣二手書", [""]), ("中發票", [""]), ("利息", [""]), ("賣舊手機", [""])],
}
#: 金額範圍（元）
RANGE = {"餐飲": (25, 900), "交通": (15, 3000), "居住": (300, 25000), "日用品": (39, 1500), "娛樂": (99, 4000),
         "教育": (50, 30000), "醫療": (50, 3000), "其他": (30, 5000), "薪資": (20000, 80000),
         "獎金": (3000, 120000), "零用金": (100, 3000), "其他收入": (30, 8000)}
#: 每一個說法的金額範圍（元）。沒列的用上面分類的範圍。公車不會 1800、牙膏不會 1,118
WORD_RANGE = {
    "早餐": (30, 150), "午餐": (60, 400), "晚餐": (80, 1500), "宵夜": (50, 400), "便當": (70, 150),
    "咖啡": (35, 180), "拿鐵": (60, 180), "手搖飲": (35, 90), "珍奶": (45, 90), "牛肉麵": (120, 300),
    "滷肉飯": (30, 120), "火鍋": (300, 2500), "早午餐": (120, 400), "下午茶": (100, 600), "雞排": (60, 120),
    "麵包": (30, 300), "飯糰": (25, 60), "鍋貼": (50, 200), "漢堡": (60, 250),
    "加油": (100, 2000), "捷運": (20, 80), "公車": (15, 45), "計程車": (90, 650), "高鐵": (290, 1600),
    "台鐵": (30, 800), "停車費": (20, 300), "悠遊卡加值": (100, 1000), "Uber": (100, 700), "國道通行費": (20, 300),
    "房租": (6000, 30000), "電費": (500, 4000), "水費": (200, 1200), "瓦斯費": (300, 1500), "管理費": (500, 4000),
    "網路費": (400, 1500), "第四台": (400, 700),
    "衛生紙": (99, 499), "洗衣精": (99, 450), "牙膏": (59, 299), "洗髮精": (99, 399), "沐浴乳": (99, 399),
    "垃圾袋": (39, 150), "廚房紙巾": (99, 499), "清潔劑": (59, 299),
    "電影": (250, 700), "KTV": (300, 3000), "Netflix": (270, 490), "Spotify": (149, 268), "遊戲點數": (150, 3000),
    "演唱會門票": (1800, 6800), "桌遊": (150, 1500), "保齡球": (200, 800),
    "補習費": (2000, 15000), "學費": (5000, 60000), "參考書": (200, 900), "文具": (30, 500),
    "線上課程": (300, 6000), "英文家教": (800, 4000),
    "掛號費": (50, 250), "看牙醫": (150, 3000), "看診": (150, 600), "感冒藥": (100, 500), "健檢": (1500, 8000),
    "復健": (50, 400), "眼科": (150, 800),
    "運費": (40, 200), "禮金": (1200, 6600), "捐款": (100, 3000), "手機維修": (500, 5000), "寄包裹": (50, 200),
    "薪水入帳": (25000, 80000), "領薪水": (25000, 80000), "發薪水": (25000, 80000), "月薪": (28000, 90000),
    "年終獎金": (10000, 150000), "績效獎金": (3000, 50000), "三節獎金": (2000, 10000), "年終": (10000, 150000),
    "媽媽給零用錢": (100, 2000), "爸爸給零用金": (100, 2000), "阿嬤給零用錢": (200, 3000),
    "退款": (100, 5000), "賣二手書": (50, 800), "中發票": (200, 2000), "利息": (5, 900), "賣舊手機": (1500, 9000),
    "飼料": (300, 2500), "貓砂": (200, 900), "帶狗看獸醫": (500, 4000), "孝親費": (3000, 20000),
    "給爸媽的生活費": (3000, 20000),
}

#: 偶爾加進分類清單的家庭自訂分類，跟它們的說法
CUSTOM = {"寵物": [("飼料", ["", "寵物公園"]), ("貓砂", [""]), ("帶狗看獸醫", [""])],
          "孝親": [("孝親費", [""]), ("給爸媽的生活費", [""])]}
CUSTOM_RANGE = {"寵物": (100, 3000), "孝親": (2000, 20000)}

DATE_WORDS = ["今天", "昨天", "前天", "大前天", "上禮拜一", "上禮拜三", "上週五", "上禮拜六", "禮拜一", "禮拜二",
              "星期日", "這禮拜一"]
JOINERS = ["，", "，", "，", "、", "；", "然後", "，還有", "，接著", " "]

_DIG = "零一二三四五六七八九"


def _small(x: int, lead: bool) -> str:
    """0～9999 → 中文。lead：在最前面時「十五」不寫成「一十五」。"""
    out, zero = "", False
    for unit, name in ((1000, "千"), (100, "百"), (10, "十")):
        d, x = divmod(x, unit)
        if d:
            if zero:
                out, zero = out + "零", False
            if unit == 10 and d == 1 and not out and lead:
                out += "十"
            else:
                out += ("兩" if d == 2 and unit >= 100 else _DIG[d]) + name
        elif out:
            zero = True
    if x:
        out += ("零" if zero else "") + _DIG[x]
    return out


def zh(n: int) -> str:
    """整數 → 中文口語：55 → 五十五、120 → 一百二、2300 → 兩千三、18000 → 一萬八、405 → 四百零五。"""
    if n >= 10000:
        wan, rest = divmod(n, 10000)
        head = ("兩" if wan == 2 else _small(wan, True)) + "萬"
        if rest == 0:
            return head
        if rest % 1000 == 0:
            return head + _DIG[rest // 1000]                  # 一萬八（18000）
        return head + ("零" if rest < 1000 else "") + _small(rest, False)
    s = _small(n, True)
    if 100 <= n < 1000 and n % 100 and n % 10 == 0:
        return s[:-1]                                         # 一百二十 → 一百二
    if 1000 <= n < 10000 and n % 1000 and n % 100 == 0:
        s = s[:-1]                                            # 兩千三百 → 兩千三
        return s[:-1] + "二" if s.endswith("兩") else s       # 一千兩百 → 一千二，不是一千兩
    return s


def amount_text(rng: random.Random, n: int) -> str:
    style = rng.random()
    if style < 0.55:
        return str(n)
    if style < 0.70:
        return rng.choice(["%d元", "%d 元", "%d塊", "NT$%d", "$%d"]) % n
    if style < 0.78 and n >= 1000:
        return "{:,}".format(n)
    return zh(n) + rng.choice(["", "", "元", "塊"])


def pick_amount(rng: random.Random, cat: str, ranges: dict, word: str = "") -> int:
    lo, hi = WORD_RANGE.get(word, ranges[cat])
    n = rng.randint(lo, hi)
    r = rng.random()
    if n >= 10000:
        n = round(n, -3) if r < 0.6 else round(n, -2)
    elif n >= 1000:
        n = round(n, -2) if r < 0.75 else n
    elif n >= 100:
        n = round(n, -1) if r < 0.65 else n
    elif r < 0.5:
        n = 5 * round(n / 5)
    return min(max(n, lo), hi) if lo < 1000 else max(n, lo)


def clause(rng, cat, words, ranges, date_word, alone):
    """一小段話與它的答案（答案的日期之後再填）。alone：整段話只有這一筆（才可以在中間用逗號）。"""
    word, merchants = rng.choice(words[cat])
    merchant = rng.choice(merchants)
    kind = I if cat in ("薪資", "獎金", "零用金", "其他收入") else E
    no_amount = rng.random() < 0.08
    n = None if no_amount else pick_amount(rng, cat, ranges, word)
    amt = "" if no_amount else amount_text(rng, n)
    head = date_word or ""
    if kind == I:
        plain = ["{w}{a}", "{w} {a}"] + (["{w}，{a}"] if alone else [])
        if word in ("退款", "利息", "年終獎金", "績效獎金", "三節獎金", "年終"):
            plain += ["收到{w}{a}", "{w}入帳{a}"]               # 「收到薪水入帳」「收到媽媽給零用錢」不通順，不加
        body = rng.choice(plain)
        if merchant:
            body = "{m}" + body                                 # 蝦皮退款 3800
        if no_amount:
            body = rng.choice(["{w}", "{w}還沒看多少"])
    elif merchant and rng.random() < 0.7:
        body = rng.choice(["在{m}買{w}{a}", "{m}{w}{a}", "{m} {w} {a}", "去{m}買{w}花了{a}"])
        if no_amount:
            body = "在{m}買{w}"
    else:
        merchant = ""
        body = rng.choice(["{w}{a}", "{w} {a}", "{w}花了{a}", "{w}付了{a}"] + (["{w}，{a}"] if alone else []))
        if no_amount:
            body = rng.choice(["{w}", "{w}忘記多少錢", "{w}還沒算"])
    text = head + body.format(m=merchant, w=word, a=amt).strip()
    return text, {"amount": n, "kind": kind, "cat": cat, "merchant": merchant, "note": word}


def example(rng: random.Random, n_id: int) -> dict:
    today = date(2026, 1, 1) + timedelta(days=rng.randint(0, 364))
    words, ranges = dict(WORDS), dict(RANGE)
    custom = []
    if rng.random() < 0.25:
        custom = rng.sample(sorted(CUSTOM), k=rng.randint(1, 2))
        for c in custom:
            words[c], ranges[c] = CUSTOM[c], CUSTOM_RANGE[c]

    k = rng.choices([1, 2, 3, 4, 5], weights=[50, 25, 15, 7, 3])[0]
    cats = []
    for _ in range(k):
        pool = list(words)
        weights = [6 if c == "餐飲" else 3 if c in ("交通", "日用品") else 2 if c in custom else 1 for c in pool]
        cats.append(rng.choices(pool, weights=weights)[0])

    parts, items = [], []
    current = today.isoformat()
    for i, cat in enumerate(cats):
        date_word = None
        r = rng.random()
        if i == 0 and r < 0.35 or i > 0 and r < 0.12:
            r2 = rng.random()
            if r2 < 0.7:
                date_word = rng.choice(DATE_WORDS)
            elif r2 < 0.85:
                d = today - timedelta(days=rng.randint(1, 40))
                date_word = rng.choice(["%d/%d ", "%d月%d號", "%d月%d日"]) % (d.month, d.day)
            else:
                d = today - timedelta(days=rng.randint(1, 25))
                date_word = "%d號" % d.day
        text, gold = clause(rng, cat, words, ranges, date_word, alone=k == 1)
        if date_word:
            current = dates.find(date_word, today) or dates.resolve(date_word.strip(), today) or current
        gold["date"] = current
        gold["span"] = text
        parts.append(text)
        items.append(gold)

    sentence = parts[0]
    for p in parts[1:]:
        sentence += rng.choice(JOINERS) + p

    # 分類清單：系統的 12 個＋這一題的自訂分類，id 打亂（家庭自訂的 id 比較大）
    ids = rng.sample(range(1, 40), len(catalog.SYSTEM_CATEGORIES))
    categories = [{"id": str(ids[j]), "name": name, "kind": kind}
                  for j, (name, kind, _c, _i) in enumerate(catalog.SYSTEM_CATEGORIES)]
    for c in custom:
        categories.append({"id": str(rng.randint(40, 300)), "name": c, "kind": E})
    rng.shuffle(categories)
    return {"id": "t%05d" % n_id, "today": today.isoformat(), "text": sentence, "categories": categories,
            "items": items}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1500)
    ap.add_argument("--seed", type=int, default=20261014)
    ap.add_argument("--out", default=os.path.join(ROOT, "ml", "data", "train.jsonl"))
    args = ap.parse_args()

    heldout = set()
    with io.open(os.path.join(BACKEND, "eval", "heldout.jsonl"), encoding="utf-8") as f:
        for line in f:
            if line.strip():
                heldout.add(json.loads(line)["text"])

    rng = random.Random(args.seed)
    rows, seen, n = [], set(), 0
    while len(rows) < args.n:
        n += 1
        ex = example(rng, n)
        if ex["text"] in heldout or ex["text"] in seen:
            continue
        seen.add(ex["text"])
        rows.append(ex)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with io.open(args.out, "w", encoding="utf-8", newline="\n") as f:
        for ex in rows:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    multi = sum(1 for r in rows if len(r["items"]) > 1)
    print("寫了 %d 題到 %s（多筆 %d 題）" % (len(rows), args.out, multi))


if __name__ == "__main__":
    main()
