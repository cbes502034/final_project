"""固定收入自動入帳：存錢計畫選了「固定金額」，到了入帳日自動在個人帳本記一筆收入。

只有固定金額會記
    「自動估」是最近幾個月的平均，只是先拿來算可花上限的預估，不是真的有錢進來，
    記成一筆帳等於把猜的數字當事實，所以不記。「只算已入帳」本來就不估，也不記。

什麼時候記
    users.income_pay_day（1~28）那天；沒設就是每月 1 日。系統沒有排程：當天或之後
    第一次發請求時補記（guards.current_user 每次請求都會呼叫 settle_due）。

不重複
    users.income_posted_period 記著「這個月處理過了」：記過、略過、或記了之後被刪掉，都不會再補。
    入帳日之前自己已經記了同一個分類的收入、金額不少於設定值 → 略過，不再多記一筆。
    改了金額或入帳日：這個月自動記的那一筆如果還沒被手動改過，就跟著新設定（sync_settings）——
    設定時常常是先填金額、再選日期，不能讓先存的那一下就把日期定死。手動改過的那一筆不動。

可花上限的算法不用動：max(這個月已入帳, 預計收入) —— 記了之後已入帳就等於預計，不會加兩次。
"""
from __future__ import annotations

from app.models import Category, Notification, Transaction
from app.services import allowance_ledger
from app.services.allowance_ledger import pay_date
from app.toolkit import crud, money, period as periods

SOURCE = "income_auto"


def _category(db, income_type) -> int:
    name = "薪資" if income_type in (None, "salary", "commission") else "其他收入"
    cat = crud.get(Category, where={"name": name, "kind": "income", "family_id__isnull": True}, db=db)
    if cat is None:
        cat = crud.save(Category, {"name": name, "kind": "income", "color": "cat-daily", "sort_order": 99}, db=db)
    return cat.id


def settle_due(db, user) -> None:
    if (getattr(user, "income_mode", None) or "auto") != "fixed" or not user.expected_income:
        return
    day = allowance_ledger.today()                  # 透過模組叫：測試換日期時才換得到
    period = day.isoformat()[:7]
    if user.income_posted_period == period:
        return
    when = pay_date(period, user.income_pay_day)
    if when > day:
        return
    from app.services.personal_ledger import ensure_personal

    amount = money.quantize(user.expected_income)
    cat = _category(db, user.income_type)
    start, end = periods.month_range(period)
    already = money.add(*crud.find(Transaction, {
        "user_id": user.id, "kind": "income", "category_id": cat, "is_snapshot": False,
        "occurred_on__between": (start, end)}, fields="amount", db=db))
    if already < amount:
        crud.save(Transaction, {
            "user_id": user.id, "group_id": ensure_personal(db, user).id, "family_id": getattr(user, "family_id", None),
            "category_id": cat, "kind": "income", "amount": amount, "occurred_on": when,
            "note": "固定收入（自動入帳）", "source": SOURCE}, db=db)
        crud.save(Notification, {"recipient_id": user.id, "type": "income", "payload_json": {
            "amount": float(amount), "period": period, "date": when.isoformat()}}, db=db)
    from app.models import User
    crud.save(User, {"id": user.id, "income_posted_period": period}, db=db)
    db.commit()


def sync_settings(db, user) -> None:
    """剛改了收入設定（PATCH /api/auth/me）：這個月自動記的那筆還沒被手動改過，就照新的金額與入帳日；
    新的入帳日還沒到 → 先拿掉，到了那天再記。不是固定金額了 → 也拿掉。由呼叫者 commit。"""
    day = allowance_ledger.today()
    period = day.isoformat()[:7]
    if user.income_posted_period != period:
        return
    start, end = periods.month_range(period)
    row = crud.get(Transaction, where={"user_id": user.id, "source": SOURCE, "updated_at__isnull": True,
                                       "occurred_on__between": (start, end)}, db=db)
    if row is None:
        return
    when = pay_date(period, user.income_pay_day)
    fixed = (user.income_mode or "auto") == "fixed" and user.expected_income
    if fixed and when <= day:
        crud.save(Transaction, {"id": row.id, "amount": money.quantize(user.expected_income), "occurred_on": when}, db=db)
        return
    crud.remove(Transaction, id=row.id, db=db)
    from app.models import User
    crud.save(User, {"id": user.id, "income_posted_period": None}, db=db)
