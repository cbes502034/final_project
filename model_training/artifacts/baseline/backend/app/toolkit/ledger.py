"""
帳本的生命週期：記帳、結算、封存、移除；還有紀錄的修改與刪除。

負責人：成員2（記帳）

===========================================================================
四個狀態
===========================================================================
    使用中    可以記帳、改設定、加減人
    已結算    活動帳本才有。唯讀：不能再記新的帳、不能改成員
    已封存    收起來不用。紀錄都在，隨時可以復原
    已移除    結算過的活動帳本才能移除。帳本不見、不能復原——**紀錄不刪**

===========================================================================
⚠️ 移除的是「帳本」，不是紀錄
===========================================================================
紀錄是記帳的人的。移除之後每一筆仍在他自己的收支明細與統計裡，
過去月份的數字不會變（groups.removed_at 有值，transactions 一筆都不動）。
會變的只有「靠這本帳才看得到別人紀錄」的那條路——帳本不在了，那條路就斷了。

為什麼不做成真的刪除：
  * 共用帳本裡有別人記的帳，建立者一刪就把家人的資料刪了
  * 九月的支出總額會憑空變少，跟「過去月份維持當時的數字」衝突

===========================================================================
怎麼用
===========================================================================
    from app.toolkit import ledger

    ledger.require_open(group.settled_at)          # 新增一筆之前；結算過就丟 ValueError → 409
    ledger.require_removable(me, group.created_by, group.settled_at, group.removed_at)

    # 修改、刪除紀錄
    patch = ledger.clean_patch(body)               # PATCH 的主體：只收看得懂的欄位
    ledger.require_editable(me, tx.user_id, group.settled_at)
    ids = ledger.clean_ids(request.query_params.get("ids"))   # DELETE /api/transactions?ids=…

===========================================================================
⚠️ 改紀錄、刪紀錄的三條規則
===========================================================================
  1. 只有記的人本人。監管是唯讀的，家長看得到不等於改得動（403）
  2. 結算過的帳本裡的紀錄不能改、不能刪（409）——結算就是對過帳了，
     改一筆，大家已經對好的數字就不對了
  3. 一次刪多筆是**全部成功或全部不動**。十筆裡有一筆是別人的，
     一筆都不刪，不要刪到一半才告訴使用者「有些沒刪掉」
"""

from __future__ import annotations

from .scope import Forbidden

__all__ = ["require_open", "require_removable",
           "EDITABLE", "MAX_BATCH", "clean_patch", "require_editable", "clean_ids"]

#: PATCH /api/transactions/{id} 可以改的欄位。
#: ⚠️ 沒有 source、user：來源是「怎麼記進來的」，不是使用者可以改的屬性；
#:    改 user 等於把自己的帳塞給別人。
EDITABLE = ("date", "amount", "kind", "cat", "merchant", "note", "groupId")

#: 一次最多刪幾筆。網址有長度上限，而且沒有人真的需要一次勾一百筆以上
MAX_BATCH = 100


def require_open(settled_at: object) -> None:
    """往這本帳記一筆之前的檢查：結算過的帳本唯讀。

    >>> require_open(None)
    >>> require_open("2026-09-14")
    Traceback (most recent call last):
    ...
    ValueError: 這本帳已經結算，不能再記新的帳
    """
    if settled_at:
        raise ValueError("這本帳已經結算，不能再記新的帳")


def require_removable(me: object, owner: object, settled_at: object, removed_at: object) -> None:
    """移除帳本之前的檢查。

    只有建立者；只有結算過的（還在用的帳本請用封存，封存可以復原）。

    >>> require_removable("U1", "U1", "2026-09-14", None)
    >>> require_removable("U1", "U1", None, None)
    Traceback (most recent call last):
    ...
    ValueError: 只有結算過的活動帳本可以移除；還在用的帳本請改用封存
    """
    if removed_at:
        raise ValueError("這本帳已經移除了")
    if me != owner:
        raise Forbidden("只有建立這本帳的人可以移除")
    if not settled_at:
        raise ValueError("只有結算過的活動帳本可以移除；還在用的帳本請改用封存")


def clean_patch(body: object) -> dict:
    """PATCH 主體的欄位檢查。回傳清過的 dict，只含有帶來的欄位。

    ⚠️ 不認得的欄位直接丟錯，不要默默忽略——
    前端送了 ``source`` 以為改得動，結果什麼都沒發生，那是最難抓的錯。

    >>> clean_patch({"amount": "120", "note": " 午餐 "})
    {'amount': Decimal('120'), 'note': '午餐'}
    >>> clean_patch({"source": "manual"})
    Traceback (most recent call last):
    ...
    ValueError: 不認得的欄位：source
    """
    from datetime import date

    from .money import InvalidAmount, to_decimal

    if not isinstance(body, dict) or not body:
        raise ValueError("沒有要改的欄位")
    unknown = [k for k in body if k not in EDITABLE]
    if unknown:
        raise ValueError("不認得的欄位：" + "、".join(str(k) for k in unknown))

    out: dict = {}
    for key, value in body.items():
        if key == "amount":
            try:
                amount = to_decimal(value, allow_negative=False)
            except InvalidAmount:
                raise ValueError("金額要是大於 0 的數字") from None
            if amount <= 0:
                raise ValueError("金額要是大於 0 的數字")
            out[key] = amount
        elif key == "date":
            try:
                out[key] = date.fromisoformat(str(value)).isoformat()
            except ValueError:
                raise ValueError("日期格式要是 YYYY-MM-DD") from None
        elif key == "kind":
            if value not in ("expense", "income"):
                raise ValueError("收支只能是 expense 或 income")
            out[key] = value
        elif key in ("merchant", "note"):
            text = " ".join(str(value or "").split())
            if len(text) > 100:
                raise ValueError("店家和備註最多 100 個字")
            out[key] = text
        else:                                   # cat、groupId：存不存在要查資料庫，這裡只擋空值
            if value in (None, ""):
                raise ValueError(key + " 不能是空的")
            out[key] = value
    return out


def require_editable(me: object, owner: object, settled_at: object) -> None:
    """改或刪一筆紀錄之前的檢查。

    >>> require_editable("U1", "U1", None)
    >>> require_editable("U1", "U1", "2026-09-14")
    Traceback (most recent call last):
    ...
    ValueError: 這本帳已經結算，裡面的紀錄不能再改或刪除
    """
    if me != owner:
        raise Forbidden("這是別人的紀錄，你只能檢視")
    if settled_at:
        raise ValueError("這本帳已經結算，裡面的紀錄不能再改或刪除")


def clean_ids(raw: object, limit: int = MAX_BATCH) -> list[str]:
    """``?ids=T1,T2`` 或 list → 去掉空白與重複、保留順序的 id 清單。

    ⚠️ 空的一定要丟錯。``DELETE /api/transactions`` 沒帶 ids
    如果被當成「不篩選」，就是把這個人的帳整本刪光。

    >>> clean_ids("T1, T2,T1")
    ['T1', 'T2']
    >>> clean_ids("")
    Traceback (most recent call last):
    ...
    ValueError: 沒有指定要刪哪幾筆
    """
    items = raw.split(",") if isinstance(raw, str) else list(raw or [])
    out: list[str] = []
    for item in items:
        key = str(item).strip()
        if key and key not in out:
            out.append(key)
    if not out:
        raise ValueError("沒有指定要刪哪幾筆")
    if len(out) > limit:
        raise ValueError("一次最多刪 %d 筆" % limit)
    return out
