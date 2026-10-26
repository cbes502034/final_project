"""零用金自動記帳：家長給出去的錢，兩邊各記一筆，並通知孩子。

一對帳
    家長的個人帳本記一筆支出「給零用金」，孩子的個人帳本記一筆收入「零用金」，
    兩筆的 source 都是 "allowance"，用 allowance_payments 的一列綁在一起。
    兩位家長都給，就是兩對帳、兩則通知；孩子那筆的備註寫著是哪位家長給的。

什麼時候發
    每位家長各自設發放日（1~28）；沒設就是每月 1 日，跟帳本換月同一天。
    系統沒有排程：發放日當天或之後，家長或孩子第一次打開系統時補發
    （guards.current_user 每次請求都會呼叫 settle_due）。
    同一位家長、同一個孩子、同一個月只會有一列，資料庫的唯一鍵擋重複。

改金額、刪掉
    這個月已經發了才改金額 → 改原本那一對，不新增；孩子收到「調整」通知。
    家長刪掉自己那筆 → 孩子那筆一起刪，這個月記成取消（不會再補發），孩子收到通知。
    孩子那筆不能自己改或刪；家長那筆只能改金額、日期、備註。

家庭的數字
    家長給孩子是家裡的錢換手，不是花掉。家庭模式把家長那筆「給零用金」排除
    （internal_transfer_ids），孩子真的花掉時才算家庭支出，不會算兩次。
    家長自己的個人總覽照樣算支出——錢確實從他身上出去了。

所有改動都在呼叫者的交易裡；settle_due 自己會 commit（它跑在守衛裡，路由不一定會 commit）。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

from app.models import (Allowance, AllowancePayment, Category, FamilyMember, Guardianship,
                        Notification, Transaction, User)
from app.toolkit import crud, money

SOURCE = "allowance"
PAYER_CAT, WARD_CAT = "給零用金", "零用金"
TW = timezone(timedelta(hours=8))


def today() -> date:
    return datetime.now(TW).date()


def pay_date(period: str, pay_day: int | None) -> date:
    """'2026-10' 的發放日。沒設就是 1 日。"""
    y, m = int(period[:4]), int(period[5:7])
    return date(y, m, min(max(int(pay_day or 1), 1), 28))


def _category(db, name: str, kind: str) -> int:
    cat = crud.get(Category, where={"name": name, "kind": kind, "family_id__isnull": True}, db=db)
    if cat is None:                       # 還沒跑遷移的資料庫：補上，不要讓發零用金整個失敗
        cat = crud.save(Category, {"name": name, "kind": kind, "color": "cat-transit", "sort_order": 99}, db=db)
    return cat.id


def _names(db, *ids) -> dict:
    return {u.id: u.display_name for u in crud.find(User, {"id__in": list(ids)}, db=db)}


def _family(db, user_id: int):
    return crud.get(FamilyMember, where={"user_id": user_id, "status": "active"}, fields="family_id", db=db)


def _notify(db, payer_id: int, ward_id: int, action: str, amount, period: str, prev=None) -> None:
    payload = {"action": action, "amount": float(amount), "period": period,
               "payerName": _names(db, payer_id).get(payer_id, "")}
    if prev is not None:
        payload["prev"] = float(prev)
    crud.save(Notification, {"recipient_id": ward_id, "actor_id": payer_id, "type": "allowance",
                             "payload_json": payload}, db=db)


def _pay(db, setting, period: str) -> None:
    from app.services.personal_ledger import ensure_personal

    payer, ward = crud.get(User, setting.payer_id, db=db), crud.get(User, setting.ward_id, db=db)
    when = pay_date(period, setting.pay_day)
    amount = money.quantize(setting.amount)
    payer_tx = crud.save(Transaction, {
        "user_id": payer.id, "group_id": ensure_personal(db, payer).id, "family_id": _family(db, payer.id),
        "category_id": _category(db, PAYER_CAT, "expense"), "kind": "expense", "amount": amount,
        "occurred_on": when, "note": "給%s的零用金" % ward.display_name, "source": SOURCE}, db=db)
    ward_tx = crud.save(Transaction, {
        "user_id": ward.id, "group_id": ensure_personal(db, ward).id, "family_id": _family(db, ward.id),
        "category_id": _category(db, WARD_CAT, "income"), "kind": "income", "amount": amount,
        "occurred_on": when, "note": "%s給的零用金" % payer.display_name, "source": SOURCE}, db=db)
    crud.save(AllowancePayment, {"payer_id": payer.id, "ward_id": ward.id, "period_key": period,
                                 "amount": amount, "payer_tx_id": payer_tx.id, "ward_tx_id": ward_tx.id,
                                 "status": "paid"}, db=db)
    _notify(db, payer.id, ward.id, "paid", amount, period)


def _due_settings(db, where: dict, period: str, day: date) -> list:
    settings = crud.find(Allowance, {"period_key__isnull": True, **where}, db=db)
    if not settings:
        return []
    active = {(g.guardian_id, g.ward_id) for g in crud.find(
        Guardianship, {"ward_id__in": [s.ward_id for s in settings], "ended_at__isnull": True}, db=db)}
    done = {(p.payer_id, p.ward_id) for p in crud.find(
        AllowancePayment, {"period_key": period, "ward_id__in": [s.ward_id for s in settings]}, db=db)}
    return [s for s in settings if (s.payer_id, s.ward_id) in active
            and (s.payer_id, s.ward_id) not in done and pay_date(period, s.pay_day) <= day]


def settle_due(db, user) -> None:
    """到了發放日還沒發的，現在補發。user 是家長（給的）或孩子（收的）都會觸發。"""
    if not getattr(user, "family_id", None):
        return
    day = today()
    period = day.isoformat()[:7]
    due = _due_settings(db, {"or": [{"payer_id": user.id}, {"ward_id": user.id}]}, period, day)
    if not due:
        return
    try:
        for setting in due:
            _pay(db, setting, period)
        db.commit()
    except IntegrityError:
        db.rollback()                       # 同一時間另一個請求已經發了：那邊算數


def sync_setting(db, payer_id: int, ward_id: int) -> None:
    """家長剛改了零用金設定：已發的這個月照新金額調整原本那一對；到期還沒發的現在發。"""
    period = today().isoformat()[:7]
    setting = crud.get(Allowance, where={"payer_id": payer_id, "ward_id": ward_id, "period_key__isnull": True}, db=db)
    paid = crud.get(AllowancePayment, where={"payer_id": payer_id, "ward_id": ward_id, "period_key": period}, db=db)
    if setting is None:
        return
    if paid is None:
        if _due_settings(db, {"payer_id": payer_id, "ward_id": ward_id}, period, today()):
            _pay(db, setting, period)
        return
    amount = money.quantize(setting.amount)
    if paid.status != "paid" or paid.amount == amount:
        return
    prev = paid.amount
    now = datetime.now(timezone.utc)
    for tx_id in (paid.payer_tx_id, paid.ward_tx_id):
        if tx_id:
            crud.save(Transaction, {"id": tx_id, "amount": amount, "updated_at": now}, db=db)
    crud.save(AllowancePayment, {"id": paid.id, "amount": amount, "updated_at": now}, db=db)
    _notify(db, payer_id, ward_id, "adjusted", amount, period, prev)


def check_edit(row, patch: dict | None = None) -> None:
    """改或刪零用金那一對之前：孩子那筆不能動；家長那筆只能改金額、日期、備註。丟 ValueError。"""
    if getattr(row, "source", None) != SOURCE:
        return
    if row.kind == "income":
        raise ValueError("這筆是家長給的零用金，要調整請找家長")
    if patch and set(patch) - {"amount", "date", "note"}:
        raise ValueError("零用金只能改金額、日期或備註")


def after_update(db, row, prev_amount) -> None:
    """家長改了自己那筆：孩子那筆跟著改，金額有變就通知孩子。"""
    if getattr(row, "source", None) != SOURCE or row.kind != "expense":
        return
    paid = crud.get(AllowancePayment, where={"payer_tx_id": row.id}, db=db)
    if paid is None:
        return
    now = datetime.now(timezone.utc)
    if paid.ward_tx_id:
        crud.save(Transaction, {"id": paid.ward_tx_id, "amount": row.amount, "occurred_on": row.occurred_on,
                                "updated_at": now}, db=db)
    if money.quantize(row.amount) != money.quantize(prev_amount):
        crud.save(AllowancePayment, {"id": paid.id, "amount": row.amount, "updated_at": now}, db=db)
        _notify(db, paid.payer_id, paid.ward_id, "adjusted", row.amount, paid.period_key, prev_amount)


def before_delete(db, rows) -> None:
    """家長刪了自己那筆：孩子那筆一起刪、這個月記成取消，通知孩子。"""
    ids = [r.id for r in rows if getattr(r, "source", None) == SOURCE and r.kind == "expense"]
    if not ids:
        return
    now = datetime.now(timezone.utc)
    for paid in crud.find(AllowancePayment, {"payer_tx_id__in": ids}, db=db):
        if paid.ward_tx_id:
            crud.remove(Notification, {"transaction_id": paid.ward_tx_id}, db=db)
            crud.remove(Transaction, id=paid.ward_tx_id, db=db)
        crud.save(AllowancePayment, {"id": paid.id, "status": "cancelled", "payer_tx_id": None,
                                     "ward_tx_id": None, "updated_at": now}, db=db)
        _notify(db, paid.payer_id, paid.ward_id, "cancelled", paid.amount, paid.period_key)


def internal_transfer_ids(db, people) -> set:
    """家長那筆「給零用金」，而且收錢的孩子也在 people 裡：家庭內換手，家庭的數字不算。"""
    people = list(people)
    if len(people) < 2:
        return set()
    return {p.payer_tx_id for p in crud.find(AllowancePayment, {
        "payer_id__in": people, "ward_id__in": people, "status": "paid", "payer_tx_id__isnull": False}, db=db)}
