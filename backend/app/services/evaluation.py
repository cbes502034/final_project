"""
模型評測：留出集上的切分正確率、逐欄正確率、完全正確率、分類 Macro-F1、沒講金額時亂猜的比例、延遲。

領域：記帳；與家庭 的評測工作一起

    from app.services import evaluation

    report = evaluation.score(cases)      # cases：[{"gold": [...], "pred": [...], "seconds": 1.2, "error": ""}]
    print(evaluation.to_markdown({"Claude": report, "規則": base}))

每一筆（gold／pred 的 item）只比四欄：date（YYYY-MM-DD）、amount（數字或 None）、kind、cat（分類**名稱**）。
店家、備註是自由文字，不算分。

跑法見 tools/eval_nlp.py。留出集在 eval/heldout.jsonl。

⚠️ 留出集最好 100% 人工標註，否則量到的是「多像那個老師」而不是「多正確」。
   我們的留出集是 AI 產生、人工抽查（每一題的 checked 欄位），報告裡要寫清楚這一點。
⚠️ 線上資料：nlp_parses 的 user_corrected 有值的，就是模型抓錯、使用者改過的——可以補進下一版的留出集。
"""

from __future__ import annotations

from typing import Any

FIELDS = ("date", "amount", "kind", "cat")
NONE = "∅"          # 模型漏掉、或多切出來的那一筆，在 Macro-F1 裡當成一個「沒有分類」的類別


def exact_match_rate(pairs: list[tuple[dict[str, Any], dict[str, Any]]], fields: tuple[str, ...]) -> float:
    """(模型輸出, 正確答案) 的清單 → 指定欄位全部對的比例。"""
    if not pairs:
        return 0.0
    ok = sum(1 for pred, gold in pairs if all(same(f, pred.get(f), gold.get(f)) for f in fields))
    return ok / len(pairs)


def macro_f1(pairs: list[tuple[str, str]]) -> float:
    """(預測分類, 正確分類) → 各分類 F1 的平均。小類別跟大類別一樣重要，所以用 macro。"""
    labels = sorted({g for _, g in pairs} | {p for p, _ in pairs})
    if not labels:
        return 0.0
    scores = []
    for lab in labels:
        tp = sum(1 for p, g in pairs if p == lab and g == lab)
        fp = sum(1 for p, g in pairs if p == lab and g != lab)
        fn = sum(1 for p, g in pairs if p != lab and g == lab)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    return sum(scores) / len(scores)


def same(field: str, pred: Any, gold: Any) -> bool:
    """一欄對不對。金額用數值比（55 跟 55.0 一樣），其他照字串比；兩邊都是 None 也算對。"""
    if field == "amount":
        if pred is None or gold is None:
            return pred is None and gold is None
        try:
            return abs(float(pred) - float(gold)) < 0.005
        except (TypeError, ValueError):
            return False
    return (pred or None) == (gold or None)


def match_items(pred: list[dict[str, Any]], gold: list[dict[str, Any]]) -> list[tuple[dict | None, dict | None]]:
    """把模型切出來的幾筆跟正確答案配對。回傳 [(pred 或 None, gold 或 None)]。

    筆數一樣：照順序配（模型照原句順序切，這最準）。
    筆數不一樣：每一筆正確答案依序找「還沒配過、金額一樣」的，找不到再找「分類一樣」的；
    剩下沒配到的，模型多切的記 (pred, None)、漏掉的記 (None, gold)。
    """
    if len(pred) == len(gold):
        return list(zip(pred, gold))
    left = list(range(len(pred)))
    pairs: list[tuple[dict | None, dict | None]] = []
    for g in gold:
        pick = next((i for i in left if g.get("amount") is not None and same("amount", pred[i].get("amount"), g["amount"])),
                    None)
        if pick is None:
            pick = next((i for i in left if same("cat", pred[i].get("cat"), g.get("cat"))), None)
        if pick is None:
            pairs.append((None, g))
        else:
            left.remove(pick)
            pairs.append((pred[pick], g))
    pairs.extend((pred[i], None) for i in left)
    return pairs


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    v = sorted(values)
    k = (len(v) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def score(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """每一題 {"gold": [...], "pred": [...], "seconds": 秒數, "error": ""} → 一份成績單。

    叫不動（error 有值）的那一題算全錯：pred 當成空的。
    """
    n_cases = len(cases)
    errors = sum(1 for c in cases if c.get("error"))
    split_ok = case_ok = 0
    gold_items = 0
    field_ok = {f: 0 for f in FIELDS}
    item_ok = 0
    extra = 0
    cat_pairs: list[tuple[str, str]] = []
    null_gold = null_filled = 0
    for c in cases:
        gold = c.get("gold") or []
        pred = [] if c.get("error") else (c.get("pred") or [])
        if len(pred) == len(gold):
            split_ok += 1
        all_right = len(pred) == len(gold)
        for p, g in match_items(pred, gold):
            if g is None:
                extra += 1
                cat_pairs.append((p.get("cat") or NONE, NONE))
                continue
            gold_items += 1
            p = p or {}
            right = {f: same(f, p.get(f), g.get(f)) for f in FIELDS}
            for f in FIELDS:
                field_ok[f] += right[f]
            item_ok += all(right.values())
            all_right = all_right and all(right.values())
            cat_pairs.append((p.get("cat") or NONE, g.get("cat") or NONE))
            if g.get("amount") is None:
                null_gold += 1
                null_filled += p.get("amount") is not None
        case_ok += all_right
    seconds = [float(c["seconds"]) for c in cases if c.get("seconds") is not None and not c.get("error")]
    rate = (lambda a, b: round(a / b, 4) if b else None)
    return {
        "cases": n_cases,
        "items": gold_items,
        "errors": errors,
        "split_acc": rate(split_ok, n_cases),
        "case_exact": rate(case_ok, n_cases),
        "item_exact": rate(item_ok, gold_items),
        "field_acc": {f: rate(field_ok[f], gold_items) for f in FIELDS},
        "cat_macro_f1": round(macro_f1(cat_pairs), 4) if cat_pairs else None,
        "extra_items": extra,
        "no_amount": {"items": null_gold, "filled": null_filled, "hallucination": rate(null_filled, null_gold)},
        "latency_p50": round(_percentile(seconds, 0.5), 2) if seconds else None,
        "latency_p95": round(_percentile(seconds, 0.95), 2) if seconds else None,
    }


def by_tag(cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """依題目的 tags（multi、zh-num、rel-date…）分開算，報告裡看「哪一種句子最容易錯」。"""
    tags = sorted({t for c in cases for t in c.get("tags") or []})
    return {t: score([c for c in cases if t in (c.get("tags") or [])]) for t in tags}


ROWS = [
    ("題數", lambda r: r["cases"]),
    ("叫不動的題數", lambda r: r["errors"]),
    ("切分正確率（筆數對）", lambda r: r["split_acc"]),
    ("整題完全正確率", lambda r: r["case_exact"]),
    ("逐筆完全正確率", lambda r: r["item_exact"]),
    ("日期正確率", lambda r: r["field_acc"]["date"]),
    ("金額正確率", lambda r: r["field_acc"]["amount"]),
    ("收支正確率", lambda r: r["field_acc"]["kind"]),
    ("分類正確率", lambda r: r["field_acc"]["cat"]),
    ("分類 Macro-F1", lambda r: r["cat_macro_f1"]),
    ("多切出來的筆數", lambda r: r["extra_items"]),
    ("沒講金額卻填了數字", lambda r: r["no_amount"]["hallucination"]),
    ("延遲 p50（秒）", lambda r: r["latency_p50"]),
    ("延遲 p95（秒）", lambda r: r["latency_p95"]),
]


def to_markdown(reports: dict[str, dict[str, Any]]) -> str:
    """{"名稱": score() 的結果} → 一張 Markdown 對照表（直接貼進報告）。比例顯示成百分比。"""
    names = list(reports)
    lines = ["| 指標 | " + " | ".join(names) + " |", "|---|" + "---:|" * len(names)]
    for label, get in ROWS:
        cells = []
        for n in names:
            v = get(reports[n])
            if v is None:
                cells.append("—")
            elif isinstance(v, float) and label not in ("延遲 p50（秒）", "延遲 p95（秒）"):
                cells.append("%.1f%%" % (v * 100))
            else:
                cells.append(str(v))
        lines.append("| %s | %s |" % (label, " | ".join(cells)))
    return "\n".join(lines)
