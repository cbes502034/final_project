"""
所有「算出來的數字」。**整個系統只有這裡加總錢**——路由不算、模型不算，前端只做衍生（結餘、比例）。

負責人：成員3（數字）　✦ 分支：m3-analytics（共用元件：成員4 的通知門檻、建議都會呼叫）

已經可以直接用的：savings_status()——存款目標的判斷，前端、提醒、建議都用同一套。
要做的：summary()——照 docs/02-前後端串接契約.md 的 GET /api/summary 形狀，從 transactions 加總。
  ⚠️ 家庭模式：子女的收入不算進家庭收入（那多半是零用金，會重複算），支出要算
  ⚠️ 只加總「這些人記的」（可見範圍 A），不要加帳本裡別人的（B）——那會把配偶的錢算成你的
  ⚠️ 金額一律 Decimal（toolkit/money.py），不要 float
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.toolkit import money
from app.toolkit.config import settings


def savings_status(income: Any, expense: Any, goal: Any) -> dict[str, Any]:
    """可支配上限 = 收入 − 每月想存；支出 ÷ 上限決定 safe／near／over。

    >>> savings_status(50000, 42000, 10000)["level"]
    'over'
    """
    inc, exp, g = money.to_decimal(income or 0), money.to_decimal(expense or 0), money.to_decimal(goal or 0)
    allowance = inc - g
    if allowance > 0:
        ratio = exp / allowance
    else:
        ratio = Decimal(2) if exp > 0 else Decimal(0)
    level = "over" if ratio >= Decimal(str(settings.savings_over_ratio)) else (
        "near" if ratio >= Decimal(str(settings.savings_warn_ratio)) else "safe")
    return {
        "goal": g, "allowance": allowance, "used": exp, "left": allowance - exp,
        "ratio": money.quantize(ratio, 4), "level": level,
        "shortfall": max(Decimal(0), exp - allowance), "actual": inc - exp,
    }


def summary(db: Any, users: list[int], earners: list[int], period: str, group_id: int | None = None) -> dict[str, Any]:
    '''GET /api/summary 的數字。users 是這次要算的人，earners 是收入要算進去的人（不含子女）。'''
    from datetime import date

    from app.models import Transaction
    from app.toolkit import crud, period as periods

    users, earners = set(users), set(earners)
    year = int(period[:4])
    months = periods.recent_months(period, 6)
    years = [str(year - 2), str(year - 1), str(year)]

    # a. 一次查出這三年、這些人記的收支（transfer 不算；選了帳本只算那本）
    where = {"user_id__in": users, "kind__in": ["income", "expense"],
             "occurred_on__between": (date(year - 2, 1, 1), date(year, 12, 31))}
    if group_id is not None:
        where["group_id"] = group_id
    rows = crud.find(Transaction, where, fields=("user_id", "category_id", "kind", "amount", "occurred_on"), db=db)

    # b. 一筆一筆分到桶子裡
    per_user = {u: {"income": money.ZERO, "expense": money.ZERO} for u in users}
    monthly = {m: {"income": money.ZERO, "expense": money.ZERO} for m in months}
    yearly = {y: {"income": money.ZERO, "expense": money.ZERO} for y in years}
    by_cat = {}
    count = 0
    for r in rows:
        ym = r["occurred_on"].isoformat()[:7]
        kind, amount = r["kind"], r["amount"]
        if ym == period:
            count += 1
            per_user[r["user_id"]][kind] += amount
            if kind == "expense":
                by_cat[r["category_id"]] = by_cat.get(r["category_id"], money.ZERO) + amount
        if kind == "income" and r["user_id"] not in earners:
            continue                      # 子女的收入不算進家庭收入（多半是零用金，會重複算）
        if ym in monthly:
            monthly[ym][kind] += amount
        yearly[ym[:4]][kind] += amount

    # c. 合計：收入只加 earners，支出加全部
    return {
        "income": money.add(*[per_user[u]["income"] for u in users if u in earners]),
        "expense": money.add(*[per_user[u]["expense"] for u in users]),
        "count": count,
        "byCat": [{"cat": str(c), "amount": a}
                  for c, a in sorted(by_cat.items(), key=lambda kv: kv[1], reverse=True)],
        "monthly": [{"m": m, **monthly[m]} for m in months],
        "yearly": [{"y": y, "partial": periods.is_incomplete_year(y), **yearly[y]} for y in years],
        "perUser": per_user,
    }
