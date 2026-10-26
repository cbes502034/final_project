"""
所有「算出來的數字」。**整個系統只有這裡加總錢**——路由不算、模型不算，前端只做衍生（結餘、比例）。

領域：數字（共用元件：家庭 的通知門檻、建議都會呼叫）

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


def expected_income(db: Any, users: list[int], period: str, personal_only: bool = False) -> dict[int, dict[str, Any]]:
    """每個人這個月的「預計收入」：{user_id: {"amount": Decimal, "basis": 怎麼來的, "months": 用了幾個月}}。不估的人不在裡面。

    為什麼要有：月底才領薪水、日薪、打工、接案的人，月初還沒有收入，「收入 − 每月想存」一開始就是負的，
    首頁變成「超出計畫」、提醒一直響。所以可花上限的收入一律用 max(這個月已入帳, 預計收入)——
    入帳前先照預計的算，入帳後（或賺得比預計多）就是實際的，不會重複算。**算法全系統只有這一條**，
    使用者在個人資料選的只是「預計收入從哪裡來」（users.income_mode）：
        auto    最近 3 個完整月份裡、有記帳的那幾個月的平均收入（basis="average"）；收入不固定的人也適用。
                還沒有任何一個這樣的月份時，用他自己填的起始估計 expected_income（basis="estimate"）
        fixed   固定月薪：就是 expected_income（basis="fixed"）
        actual  只算已入帳，不估
    ⚠️ 沒記帳的月份不算進平均（剛開始用的人，之前幾個月是「沒記」不是「沒收入」）；
       有記帳但沒有收入的月份要算（收入不固定就是會這樣），平均才不會灌水。

    >>> expected_income(db, [daming.id], "2026-10")     # 固定月薪 31,000
    {daming.id: {'amount': Decimal('31000.00'), 'basis': 'fixed', 'months': 0}}
    """
    from app.models import Transaction, User
    from app.toolkit import crud, period as periods

    users = list(users)
    if not users:
        return {}
    people = crud.find(User, {"id__in": users}, fields=("id", "income_mode", "expected_income"), db=db)
    auto = [p["id"] for p in people if (p["income_mode"] or "auto") == "auto"]
    seen: dict[int, set] = {}
    earned: dict[int, Decimal] = {}
    if auto:
        months = periods.recent_months(periods.shift_month(period, -1), 3)        # 上個月往前 3 個月
        start, end = periods.month_range(months[0])[0], periods.month_range(months[-1])[1]
        where = {"is_snapshot": False, "user_id__in": auto, "kind__in": ["income", "expense"],
                 "occurred_on__between": (start, end)}
        if personal_only:
            from app.services.financial_context import personal_ids
            where["group_id__in"] = personal_ids(db, auto)
        for t in crud.find(Transaction, where,
                           fields=("user_id", "kind", "amount", "occurred_on"), db=db):
            seen.setdefault(t["user_id"], set()).add(t["occurred_on"].isoformat()[:7])
            if t["kind"] == "income":
                earned[t["user_id"]] = earned.get(t["user_id"], money.ZERO) + t["amount"]
    out: dict[int, dict[str, Any]] = {}
    for p in people:
        mode = p["income_mode"] or "auto"
        own = money.to_decimal(p["expected_income"] or 0)
        months_seen = len(seen.get(p["id"], ()))
        if mode == "fixed" and own > 0:
            out[p["id"]] = {"amount": own, "basis": "fixed", "months": 0}
        elif mode == "auto" and months_seen and earned.get(p["id"], money.ZERO) > 0:
            out[p["id"]] = {"amount": money.quantize(earned[p["id"]] / months_seen, 0), "basis": "average",
                            "months": months_seen}
        elif mode == "auto" and own > 0:
            out[p["id"]] = {"amount": own, "basis": "estimate", "months": 0}
    return out


def pending_income(expected: dict[str, Any] | None, counted: Any) -> Decimal:
    """預計收入裡「還沒入帳」的部分：max(0, 預計 − 已經算進收入的)。沒有預計就是 0。

    加進可花上限的就是這個差額，所以已入帳的不會被算兩次；入帳超過預計就是 0。

    >>> pending_income({"amount": Decimal("31000")}, Decimal("0"))
    Decimal('31000')
    >>> pending_income({"amount": Decimal("31000")}, Decimal("33500"))
    Decimal('0')
    """
    if not expected:
        return money.ZERO
    return max(money.ZERO, money.to_decimal(expected["amount"]) - money.to_decimal(counted or 0))


def summary(db: Any, users: list[int], earners: list[int], period: str, group_id: int | None = None, personal_only: bool = False) -> dict[str, Any]:
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
    else:
        where["is_snapshot"] = False
        if personal_only:
            from app.services.financial_context import personal_ids
            where["group_id__in"] = personal_ids(db, users)
    rows = crud.find(Transaction, where, fields=("id", "user_id", "category_id", "kind", "amount", "occurred_on"), db=db)
    # 家長給孩子的零用金，兩個人都在這次要算的人裡（家庭模式）：只是家裡的錢換手，不算支出
    from app.services.allowance_ledger import internal_transfer_ids
    skip = internal_transfer_ids(db, users) if group_id is None else set()
    if skip:
        rows = [r for r in rows if r["id"] not in skip]

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


def pocket_money(db: Any, users: list[int], period: str, personal_only: bool = False) -> dict[int, Any]:
    """被照看的人這個月「還沒記到的零用金」：{user_id: 金額}。可支配上限要把它加進收入。

    孩子多半沒有薪水，家長在「零用金」設了 3,000，孩子卻不一定會自己記一筆「收入：零用金」。
    沒記的話，可支配上限 = 0 − 存款目標，花一塊錢就變「超出計畫」——這不合理，孩子看了也只會被嚇到。
    所以：零用金 = max(家長的設定, 這個月自己記的「零用金」收入)，補上的是兩者的差額，有記就不會重複算。
    只算還在照看中的家長設的（停止照看之後，那筆設定不再算數）。

    >>> pocket_money(db, [kid.id], "2026-10")   # 家長設 3,000、孩子記了 1,000
    {kid.id: Decimal('2000')}
    """
    from app.models import Allowance, Category, Guardianship, Transaction
    from app.toolkit import crud, period as periods

    users = list(users)
    if not users:
        return {}
    pairs = {(g["guardian_id"], g["ward_id"]) for g in crud.find(
        Guardianship, {"ward_id__in": users, "ended_at__isnull": True}, fields=("guardian_id", "ward_id"), db=db)}
    setting: dict[int, Any] = {}
    for a in crud.find(Allowance, {"ward_id__in": users, "period_key__isnull": True},
                       fields=("payer_id", "ward_id", "amount"), db=db):
        if (a["payer_id"], a["ward_id"]) in pairs:
            setting[a["ward_id"]] = setting.get(a["ward_id"], money.ZERO) + a["amount"]
    if not setting:
        return {}
    cat_ids = crud.find(Category, {"name": "零用金", "kind": "income", "family_id__isnull": True}, fields="id", db=db)
    start, end = periods.month_range(period)
    recorded: dict[int, Any] = {}
    if cat_ids:
        where = {"is_snapshot": False, "user_id__in": list(setting), "kind": "income", "category_id__in": cat_ids,
                 "occurred_on__between": (start, end)}
        if personal_only:
            from app.services.financial_context import personal_ids
            where["group_id__in"] = personal_ids(db, users)
        for t in crud.find(Transaction, where, fields=("user_id", "amount"), db=db):
            recorded[t["user_id"]] = recorded.get(t["user_id"], money.ZERO) + t["amount"]
    out = {}
    for u, amount in setting.items():
        extra = amount - recorded.get(u, money.ZERO)
        if extra > 0:
            out[u] = extra
    return out
