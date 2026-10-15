"""
模型評測：留出集、零樣本 vs few-shot 對照、完全正確率與分類 Macro-F1。

負責人：成員2（記帳；與成員4 的評測工作一起）　✦ 分支：m2-ledger

⚠️ 留出集必須 100% 人工標註，否則量到的是「多像那個老師」而不是「多正確」。
資料來源：nlp_parses（raw_text、parsed_json、user_corrected）。user_corrected 有值的就是模型抓錯的標註。
"""

from __future__ import annotations

from typing import Any


def exact_match_rate(pairs: list[tuple[dict[str, Any], dict[str, Any]]], fields: tuple[str, ...]) -> float:
    """(模型輸出, 正確答案) 的清單 → 指定欄位全部對的比例。"""
    if not pairs:
        return 0.0
    ok = sum(1 for pred, gold in pairs if all(pred.get(f) == gold.get(f) for f in fields))
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
