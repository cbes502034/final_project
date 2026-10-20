"""
自然語言記帳：一句話 → 一筆、一段話 → 好幾筆。**只解析，不寫入。**

領域：記帳

流程（三支函式，訓練用的 notebook 也 import 同一套）：
  1. build_prompt()  組 system 與 prompt：規則、今天日期、分類清單（模型只能從這裡挑）、一組範例
  2. 叫模型         client.complete_json(..., tool=RECORD_TOOL)：模型用 record_transactions 工具交出結果
                    （function calling；服務不支援工具呼叫時，模型回同樣格式的 JSON 也接得住）
  3. postprocess()  一筆一筆跟原句對事實（模型說的不算，原句寫的才算）：
                    · 日期：span 裡的時間詞用 toolkit/dates 重算；這一段沒講、前面講過，就沿用前面的（「昨天停車100，晚餐350」）
                    · 金額：> 0；span 裡完全沒有數字就一定是 None（不准猜）；跟原句的數字（含「1.2 萬」）對不上，信心度壓低
                    · 分類在清單裡而且收支對得上
                    · span、店家要真的出現在原句裡；找不到的店家清掉、找不到的 span 整筆標出來
                    · 備註只留「買了什麼」（item_of）：連接詞、主詞、時間、店家、金額、動詞都不要
  4. apply_habits() 路由再照這個人以前的改法調整分類（他把「文具」從日用品改成教育過，下次就先用教育）
                    抽不到的欄位設成 None、放進 missing，前端會標紅要使用者補

模型沒設定或叫不動（ModelError）→ 路由回 503，前端用規則頂著。

回傳形狀跟前端的 mock 一樣（docs/02-前後端串接契約.md 的 POST /api/nlp/parse-batch）：
    {"raw": 原文, "items": [{"seq", "span", "date", "amount", "kind", "cat", "merchant", "note",
                            "conf": {"date", "amount", "kind", "cat"}, "missing": [...], "hint": ""}], "note": ""}

⚠️ 訓練與上線的 prompt 必須一字不差。改 build_prompt() 就要重新產生訓練資料（ml/build_sft.py）。
⚠️ 切分比抽欄位難，而且切錯比抽錯更難發現——每一筆都要帶 span（對應原句的哪一段）。
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from app.services.llm import client

MODEL_UNAVAILABLE = "模型服務還沒接上，先用前端的規則解析"

#: span 在原句裡找不到時，這一筆每一欄的信心度最多剩這麼多（前端會標出來）
INVENTED_CONF = 0.3
INVENTED_HINT = "原句裡找不到這一段，可能是模型自己加的，請確認要不要留"

#: 有這些字才可能講了金額；一個都沒有，金額一定是 None
_NUMERAL = re.compile(r"[0-9０-９零〇一二兩三四五六七八九十百千萬壹貳參肆伍陸柒捌玖拾佰仟]")
#: 原句寫的阿拉伯數字，後面可能跟著「萬」：「1.2 萬」= 12000
_WRITTEN = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(萬)?")
#: 「全家一起吃火鍋」的全家是一家人，不是便利商店
_WHOLE_FAMILY = re.compile(r"全家(?:一起|人|大小|都|去|出遊)")

# ---------------------------------------------------------------------------
# 備註只留「買了什麼」（使用者 2026-10-20：「接著去學校買了10元自動鉛筆」整句當備註，前綴是不需要的）
# ---------------------------------------------------------------------------
_CONNECT = re.compile(r"^(?:接著|然後|之後|後來|再來|最後|首先|順便|另外|還有|以及|加上|再|又|也|先|和|跟)+")
_WHO = re.compile(r"^(?:我們|我|他們|他|她|全家人|家裡|小孩|孩子|老婆|老公|媽媽|爸爸)")
_TIME = re.compile(r"(?:今天|昨天|前天|大前天|明天|今早|今晚|昨晚|早上|上午|中午|下午|傍晚|晚上|半夜|凌晨|剛剛|剛才"
                   r"|上禮拜[一二三四五六日天]?|上週[一二三四五六日天]?|這禮拜[一二三四五六日天]?"
                   r"|禮拜[一二三四五六日天]|星期[一二三四五六日天]|週[一二三四五六日天]"
                   r"|\d{1,2}[/月]\d{1,2}[日號]?|\d{1,2}[日號])")
_MONEY = re.compile(r"(?:NT\$|\$)?\d[\d,]*(?:\.\d+)?萬?(?:元|塊錢|塊|圓)?"
                    r"|[零〇一二兩三四五六七八九十百千萬]+(?:元|塊錢|塊)"
                    r"|[零〇一二兩三四五六七八九]*[十百千萬][零〇一二兩三四五六七八九十百千萬]*")
_VERB = re.compile(r"買了|買|吃了|吃|喝了|喝|花了|花|付了|付|繳了|繳|叫了|點了|訂了|搭了|搭|坐了|坐|租了|租|收到|領了|領|賣了|賣")
_UNIT = re.compile(r"^(?:一|兩|二|三|四|五|幾)?(?:個|杯|份|瓶|包|盒|張|碗|條|罐|支|本|件|雙|台|次)")
_GO = re.compile(r"^(?:去|到|在|跑去|跑到)")


def _looks_raw(note: str, span: str) -> bool:
    """備註看起來是整段原句（有數字、太長、跟原句一樣、開頭是連接詞／主詞／時間）。"""
    flat = re.sub(r"\s+", "", note)
    return (flat == re.sub(r"\s+", "", span) or bool(re.search(r"\d", flat)) or len(flat) > 10
            or bool(_CONNECT.match(flat) or _WHO.match(flat) or _TIME.match(flat)))


def item_of(note: str, span: str, merchant: str = "") -> str:
    """備註整理成「買了什麼」：連接詞、主詞、時間、店家、金額、動詞都拿掉。

    模型給的備註已經乾淨（「奶茶」「加油」）就照用；看起來是整段原句、或沒給，才從原句整理。
    「吃飯」「加油」這種動作本身就是項目的，留著動詞。整理不出來回空字串（前端顯示分類）。

    >>> item_of("接著去學校買了10元自動鉛筆", "接著去學校買了10元自動鉛筆")
    '自動鉛筆'
    >>> item_of("", "我晚上去7-11買了10元奶茶", "7-11")
    '奶茶'
    >>> item_of("奶茶", "我晚上去7-11買了10元奶茶", "7-11")
    '奶茶'
    >>> item_of("", "中午跟同事吃飯320")
    '吃飯'
    >>> item_of("", "昨天全聯買衛生紙199", "全聯")
    '衛生紙'
    >>> item_of("", "加油1200")
    '加油'
    >>> item_of("", "買了一杯珍奶60")
    '珍奶'
    >>> item_of("", "小孩補習費四千五")
    '補習費'
    >>> item_of("", "去看電影花了560")
    '看電影'
    """
    note = str(note or "").strip()
    if note and not _looks_raw(note, span):
        return note[:20]
    s = re.sub(r"\s+", "", note or span or "")
    if merchant:
        s = s.replace(re.sub(r"\s+", "", merchant), "")
    s = _TIME.sub("", _MONEY.sub("", s))
    verbs = list(_VERB.finditer(s))
    if verbs:
        v = verbs[-1]
        rest = _UNIT.sub("", s[v.end():])
        if len(rest) >= 2:
            s = rest                                   # 買了自動鉛筆 → 自動鉛筆
        elif rest:
            s = v.group(0).rstrip("了") + rest          # 吃飯 → 吃飯（只剩一個字：動作本身就是項目）
        else:
            s = s[:v.start()]                          # 去看電影花了 → 去看電影
    for _ in range(3):
        s = _GO.sub("", _WHO.sub("", _CONNECT.sub("", s)))
    s = re.sub(r"^[的，,、。]+|[的，,、。]+$", "", s)
    return s[:20] if len(s) >= 2 else ""


#: 模型唯一要交的東西。每一欄都 required、但允許 null：強迫模型對每一欄表態，「沒講」要明確寫 null。
RECORD_TOOL: dict[str, Any] = {
    "name": "record_transactions",
    "description": "把使用者的一段話切成一筆一筆的收支交出來。抽不到的欄位填 null，不要猜。",
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["span", "date", "amount", "kind", "cat", "merchant", "note", "conf"],
                    "properties": {
                        "span": {"type": "string", "description": "原句裡對應這一筆的那一段，一字不改"},
                        "date": {"type": ["string", "null"],
                                 "description": "YYYY-MM-DD。沒講日期就是今天；「昨天」「9/17」要換算"},
                        "amount": {"type": ["number", "null"],
                                   "description": "正數；中文數字要換成阿拉伯數字；沒講金額就 null，不要猜"},
                        "kind": {"type": ["string", "null"], "description": "expense（支出）或 income（收入）"},
                        "cat": {"type": ["string", "null"], "description": "分類清單裡的 id，挑不出來就 null"},
                        "merchant": {"type": "string", "description": "店家，例如 全家、全聯；沒有就空字串"},
                        "note": {"type": "string", "description": "買了什麼，例如 早餐、加油；沒有就空字串"},
                        "conf": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["date", "amount", "kind", "cat"],
                            "properties": {k: {"type": "number"} for k in ("date", "amount", "kind", "cat")},
                            "description": "四個欄位各自的信心度，0 到 1",
                        },
                    },
                },
            }
        },
    },
}


def build_prompt(text: str, categories: list[dict[str, Any]], today: str) -> tuple[str, str]:
    """(system, prompt)。訓練資料（ml/build_sft.py）也用這一支，所以改這裡要重新產生訓練資料。"""
    rules = [
        "你是記帳助理，把使用者的一段話切成一筆一筆的收支，用 record_transactions 工具交出結果；"
        "不能用工具時，就只回同樣格式的 JSON，不要任何說明文字。",
        "每一筆要有 span（原句裡對應的那一段）、date（YYYY-MM-DD）、amount（正數）、",
        "kind（expense 或 income）、cat（下面分類清單裡的 id）、merchant（店家，沒有就空字串）、",
        "note（備註，沒有就空字串）、conf（date、amount、kind、cat 各一個 0 到 1 的信心度）。",
        "抽不到的欄位填 null，不要猜。「昨天」「前天」要換算成日期。",
        "「全家」「全聯」「7-11」是店名，不是家人。退款、薪水、獎金、零用錢是收入。",
        "今天是 " + today + "。分類清單：",
    ]
    for c in categories:
        rules.append("  %s：%s（%s）" % (c["id"], c["name"], "收入" if c["kind"] == "income" else "支出"))
    ids = {c["name"]: c["id"] for c in categories}
    example = {"items": [
        {"span": "早上買早餐55", "date": today, "amount": 55, "kind": "expense", "cat": ids.get("餐飲", ""),
         "merchant": "", "note": "早餐", "conf": {"date": 0.9, "amount": 0.99, "kind": 0.97, "cat": 0.9}},
        {"span": "晚上加油", "date": today, "amount": None, "kind": "expense", "cat": ids.get("交通", ""),
         "merchant": "", "note": "加油", "conf": {"date": 0.9, "amount": 0, "kind": 0.95, "cat": 0.85}},
    ]}
    prompt = "\n".join([
        "範例輸入：早上買早餐55，晚上加油",
        "範例輸出：" + json.dumps(example, ensure_ascii=False),
        "輸入：" + text,
        "輸出：",
    ])
    return "\n".join(rules), prompt


def written_amounts(span: str) -> set[float]:
    """原句這一段寫出來的阿拉伯數字（「1.2 萬」算成 12000）。

    >>> sorted(written_amounts("房租 1.2 萬")), sorted(written_amounts("加油 1,250")), written_amounts("早餐五十五")
    ([12000.0], [1250.0], set())
    """
    out = set()
    for m in _WRITTEN.finditer(span or ""):
        value = float(m.group(1).replace(",", ""))
        out.add(round(value * 10000, 2) if m.group(2) else value)
    return out


def postprocess(data: Any, categories: list[dict[str, Any]], today: str, text: str = "") -> list[dict[str, Any]]:
    """模型交回來的東西 → 前端要的 items。不合理的欄位設成 None、放進 missing。

    text 是使用者打的原句：有給的話，span 與店家要真的出現在裡面（訓練用的 notebook 不給也能跑）。
    """
    from app.toolkit import dates, money

    raw_items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(raw_items, list):
        raise client.ModelError("模型回來的格式不對")

    def score(value):
        try:
            return min(1.0, max(0.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    kinds = {str(c["id"]): c["kind"] for c in categories}
    names = {str(c["name"]) for c in categories}
    source = re.sub(r"\s+", "", text or "")
    last_said = None                 # 前面幾筆講過的日期：這一筆沒講，就沿用它
    items = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        missing = []
        conf = raw.get("conf") if isinstance(raw.get("conf"), dict) else {}
        conf = {k: score(conf.get(k)) for k in ("date", "amount", "kind", "cat")}
        span = str(raw.get("span") or "")[:100]

        # 日期：只收 YYYY-MM-DD。span 裡明講了「昨天」「上禮拜三」這種時間詞，就以確定的換算為準——
        # 模型最常錯的就是差一天，而這種錯使用者幾乎看不出來
        try:
            day = date.fromisoformat(str(raw.get("date"))).isoformat()
        except ValueError:
            day = None
        said = dates.find(span, today)
        if said and said != day:
            day = said
            conf["date"] = max(conf["date"], 0.9)
        elif not said and last_said and last_said != today and day in (None, today):
            # 「昨天停車費100，晚餐350」：晚餐那一段沒講日期，是沿用前面的「昨天」，不是今天
            day = last_said
            conf["date"] = min(max(conf["date"], 0.7), 0.8)
        if said:
            last_said = said
        if day is None:
            missing.append("date")

        try:
            amount = money.to_decimal(raw.get("amount"), allow_negative=False)
        except money.InvalidAmount:
            amount = None
        if span and not _NUMERAL.search(span):
            amount = None                # 這一段連一個數字都沒有：模型填的金額一定是猜的
        if amount is None or amount <= 0:
            amount = None
            conf["amount"] = 0.0
            missing.append("amount")
        else:
            # 原句裡寫的是阿拉伯數字，金額卻對不上任何一個：很可能抄錯，信心度壓低讓前端標黃
            written = written_amounts(span)
            if written and round(float(amount), 2) not in written:
                conf["amount"] = min(conf["amount"], 0.5)

        kind = raw.get("kind") if raw.get("kind") in ("expense", "income") else None
        if kind is None:
            missing.append("kind")
        cat = str(raw.get("cat") or "")
        if cat not in kinds or (kind is not None and kinds[cat] != kind):
            cat = None
            missing.append("cat")

        # 店家要真的出現在原句裡；「全家一起」的全家是一家人
        merchant = str(raw.get("merchant") or "").strip()[:50]
        if merchant and source and re.sub(r"\s+", "", merchant) not in source:
            merchant = ""
        if merchant == "全家" and _WHOLE_FAMILY.search(span):
            merchant = ""
        # 備註填成分類名稱（「麥當勞」備註「餐飲」）不帶任何資訊
        note = str(raw.get("note") or "").strip()[:100]
        if note in names and note not in span:
            note = ""
        # 備註只留「買了什麼」：模型偶爾把整段原句當備註（「接著去學校買了10元自動鉛筆」），整理成「自動鉛筆」
        note = item_of(note, span, merchant)

        # span 在原句裡找不到：這一筆可能是模型自己加的
        invented = bool(source) and bool(span) and re.sub(r"\s+", "", span) not in source
        if invented:
            conf = {k: min(v, INVENTED_CONF) for k, v in conf.items()}
        items.append({
            "seq": len(items) + 1,
            "span": span,
            "date": day,
            "amount": float(amount) if amount is not None else None,
            "kind": kind,
            "cat": cat,
            "merchant": merchant,
            "note": note,
            "conf": conf,
            "missing": missing,
            "hint": INVENTED_HINT if invented else ("這一筆有欄位抽不到，補上才能存" if missing else ""),
        })
    return items


def _habit_key(text: object) -> str:
    return re.sub(r"\s+", "", str(text or "")).lower()


def habits(rows: Any) -> dict[str, str]:
    """這個人改過分類的紀錄 → {品項: 他改成的分類 id}。

    rows 是 [(parsed_json, user_corrected), ...]，新的在前（同一個品項以最新的改法為準）。
    品項用模型當時抽出來的備註與店家（「文具」「全聯」）。

    >>> habits([({"note": "文具", "merchant": ""}, {"cat": "6"}), ({"note": "文具"}, {"cat": "4"}), ({"note": "早餐"}, {"amount": 60})])
    {'文具': '6'}
    """
    out: dict[str, str] = {}
    for parsed, corrected in rows or []:
        if not isinstance(corrected, dict) or not corrected.get("cat"):
            continue
        parsed = parsed if isinstance(parsed, dict) else {}
        for word in (parsed.get("note"), parsed.get("merchant")):
            key = _habit_key(word)
            if key and key not in out:
                out[key] = str(corrected["cat"])
    return out


def apply_habits(items: list[dict[str, Any]], habit: dict[str, str],
                 categories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """解析結果照使用者的習慣改分類：備註或店家對得上、而且收支對得上，才換，並在 hint 講出來。

    ⚠️ 習慣只改分類，不碰金額與日期——那兩個一定要以原句為準。
    """
    kinds = {str(c["id"]): c["kind"] for c in categories}
    names = {str(c["id"]): c["name"] for c in categories}
    for it in items:
        for word in (it.get("note"), it.get("merchant")):
            cat = habit.get(_habit_key(word))
            if not cat or cat not in kinds or cat == it.get("cat"):
                continue
            if it.get("kind") not in (None, kinds[cat]):
                continue
            it["cat"] = cat
            it["conf"] = {**(it.get("conf") or {}), "cat": max(float((it.get("conf") or {}).get("cat") or 0), 0.9)}
            it["missing"] = [m for m in it.get("missing") or [] if m != "cat"]
            if it.get("hint") != INVENTED_HINT and not it["missing"]:
                it["hint"] = "照你之前的改法，分類用「%s」" % names[cat]
            break
    return items


def parse_batch(text: str, categories: list[dict[str, Any]], today: str) -> dict[str, Any]:
    '''一段話 → 好幾筆。模型沒設定丟 client.ModelError（路由轉 503）。'''
    if not client.is_configured():
        raise client.ModelError(MODEL_UNAVAILABLE)
    system, prompt = build_prompt(text, categories, today)
    data = client.complete_json(prompt, system=system, max_tokens=1024, tool=RECORD_TOOL)
    items = postprocess(data, categories, today, text)
    return {"raw": text, "items": items,
            "note": "這段話被切成 %d 筆。切分本身也是模型的判斷，請對照原句檢查。" % len(items)}


def parse_one(text: str, categories: list[dict[str, Any]], today: str) -> dict[str, Any]:
    '''一句話 → 一筆。跟 parse_batch 用同一套 prompt，拿第一筆。'''
    result = parse_batch(text, categories, today)
    if not result["items"]:
        raise client.ModelError("模型沒有從這句話解析出任何一筆")
    return result["items"][0]
