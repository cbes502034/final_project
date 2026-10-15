"""
評測：配對、成績單、留出集本身的格式、評測腳本跑得起來（用假模型，不花錢）。

領域：記帳
"""

import io
import json
import os
import sys

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-at-least-32-bytes-long")

import pytest  # noqa: E402

from app import catalog  # noqa: E402
from app.services import evaluation  # noqa: E402

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELDOUT = os.path.join(BACKEND, "eval", "heldout.jsonl")


def it(amount, cat="餐飲", date="2026-10-14", kind="expense"):
    return {"date": date, "amount": amount, "kind": kind, "cat": cat}


def test_筆數一樣照順序配_不一樣用金額再用分類找():
    a, b, c = it(55), it(120), it(1200, "交通")
    assert evaluation.match_items([a, b], [a, b]) == [(a, a), (b, b)]
    pairs = evaluation.match_items([c, a], [a, b, c])
    assert pairs == [(a, a), (None, b), (c, c)]
    extra = it(9, "其他")
    assert evaluation.match_items([a, extra, b], [a, b]) == [(a, a), (b, b), (extra, None)]


def test_金額用數值比_兩邊都是_None_也算對():
    assert evaluation.same("amount", 55, 55.0)
    assert evaluation.same("amount", None, None)
    assert not evaluation.same("amount", 0, None)
    assert evaluation.same("cat", "", None)


def test_成績單():
    cases = [
        {"gold": [it(55), it(1200, "交通")], "pred": [it(55), it(1200, "交通")], "seconds": 1.0, "error": ""},
        {"gold": [it(None)], "pred": [it(80)], "seconds": 3.0, "error": ""},                # 沒講金額卻填了
        {"gold": [it(95)], "pred": [it(95, "其他")], "seconds": 2.0, "error": ""},          # 分類錯
        {"gold": [it(30), it(60)], "pred": [], "seconds": 9.0, "error": "模型服務回 502"},  # 叫不動
    ]
    r = evaluation.score(cases)
    assert (r["cases"], r["items"], r["errors"]) == (4, 6, 1)
    assert r["split_acc"] == 0.75 and r["case_exact"] == 0.25
    assert r["item_exact"] == round(2 / 6, 4)
    assert r["field_acc"]["amount"] == round(3 / 6, 4) and r["field_acc"]["cat"] == 0.5
    assert r["no_amount"] == {"items": 1, "filled": 1, "hallucination": 1.0}
    assert r["latency_p50"] == 2.0                                   # 叫不動的不算延遲
    md = evaluation.to_markdown({"A": r})
    assert "| 整題完全正確率 | 25.0% |" in md and "| 延遲 p50（秒） | 2.0 |" in md


def test_留出集的格式():
    """每一題：id 不重複、日期是 YYYY-MM-DD、分類是系統分類的名稱、收支跟分類對得上。"""
    from datetime import date

    kinds = {n: k for n, k, _c, _i in catalog.SYSTEM_CATEGORIES}
    rows = [json.loads(line) for line in io.open(HELDOUT, encoding="utf-8") if line.strip()]
    assert len(rows) >= 100
    assert len({r["id"] for r in rows}) == len(rows)
    assert len({r["text"] for r in rows}) == len(rows)
    for r in rows:
        date.fromisoformat(r["today"])
        assert r["items"], r["id"]
        for g in r["items"]:
            date.fromisoformat(g["date"])
            assert g["cat"] in kinds and kinds[g["cat"]] == g["kind"], r["id"]
            assert g["amount"] is None or g["amount"] > 0, r["id"]
        assert isinstance(r["checked"], bool) and r["source"] in ("ai", "human")


def test_留出集的日期答案_跟_toolkit_dates_算的一樣():
    """句子裡有時間詞的題目，答案要跟確定的換算一致——不然是答案標錯了。"""
    from app.toolkit import dates

    for r in (json.loads(line) for line in io.open(HELDOUT, encoding="utf-8") if line.strip()):
        if len(r["items"]) != 1:
            continue
        said = dates.find(r["text"], r["today"])
        assert r["items"][0]["date"] == (said or r["today"]), r["id"]


def test_評測腳本_用假模型跑得完(monkeypatch, tmp_path, capsys):
    sys.path.insert(0, os.path.join(BACKEND, "tools"))
    cwd = os.getcwd()
    try:
        import eval_nlp
    finally:
        os.chdir(cwd)
    from app.services.llm import client, parse

    def fake(text, categories, today):
        if "加油" in text:
            raise client.ModelError("模型服務回 502")
        return {"items": [{"span": text, "date": today, "amount": 55, "kind": "expense", "cat": "1"}]}

    monkeypatch.setattr(client, "is_configured", lambda: True)
    monkeypatch.setattr(parse, "parse_batch", fake)
    out = tmp_path / "fake.json"
    monkeypatch.setattr(sys, "argv", ["eval_nlp.py", "--set", HELDOUT, "--limit", "3", "--label", "fake",
                                      "--out", str(out)])
    eval_nlp.main()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["label"] == "fake" and data["report"]["cases"] == 3
    assert data["cases"][0]["pred"][0]["cat"] == "餐飲"               # id 換回名稱
    assert data["report"]["errors"] == 1                               # 第 3 題「晚上加油1200」叫不動
    assert "| 題數 | 3 |" in capsys.readouterr().out


# ===========================================================================
# 資料本身的品質：答案要對得上句子（留出集、微調的訓練資料都檢查）
# ===========================================================================
def _zh_table():
    sys.path.insert(0, os.path.join(os.path.dirname(BACKEND), "ml"))
    from make_data import zh

    table = {}
    for n in range(1, 200001):
        table.setdefault(zh(n), n)
    return table


def _amounts(text, table):
    import re

    t = text.replace("7-11", "")
    found = set()
    for m in re.finditer(r"(\d[\d,]*(?:\.\d+)?)\s*(萬)?", t):
        v = float(m.group(1).replace(",", ""))
        found.add(v * 10000 if m.group(2) else v)
    for m in re.finditer(r"[零一二兩三四五六七八九十百千萬]+", t):
        if m.group(0) in table:
            found.add(float(table[m.group(0)]))
    return found


def test_每一題的金額都在句子裡找得到():
    """答案寫 1200、句子卻是「一千」——這種標錯量出來的成績就是錯的。"""
    table = _zh_table()
    for r in (json.loads(line) for line in io.open(HELDOUT, encoding="utf-8") if line.strip()):
        found = _amounts(r["text"], table)
        for g in r["items"]:
            assert g["amount"] is None or float(g["amount"]) in found, (r["id"], r["text"], g["amount"])


def test_訓練資料的答案對得上句子():
    """ml/data/train.jsonl：金額在 span 裡、收支跟分類一致、span 是原句的一段、有時間詞的那一筆日期跟換算一樣。"""
    from app.toolkit import dates

    table = _zh_table()
    kinds = {n: k for n, k, _c, _i in catalog.SYSTEM_CATEGORIES}
    path = os.path.join(os.path.dirname(BACKEND), "ml", "data", "train.jsonl")
    for r in (json.loads(line) for line in io.open(path, encoding="utf-8") if line.strip()):
        names = {c["name"]: c["kind"] for c in r["categories"]}
        for g in r["items"]:
            assert g["span"] in r["text"], r["id"]
            assert names[g["cat"]] == g["kind"] and kinds.get(g["cat"], g["kind"]) == g["kind"], r["id"]
            assert g["amount"] is None or float(g["amount"]) in _amounts(g["span"], table), (r["id"], g["span"])
            said = dates.find(g["span"], r["today"])
            assert said is None or g["date"] == said, (r["id"], g["span"], g["date"], said)
