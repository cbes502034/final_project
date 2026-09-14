"""
收支明細：查、記、改、刪。

負責人：成員2（記帳）　✦ 分支：m2-ledger

===========================================================================
現在每一支都回 501（後端還沒做這一支），**守衛與主體模型已經接好**
===========================================================================
要做的事：把函式裡的 `raise not_ready(...)` 換成真的實作，然後拿掉 `@stub`。
* 誰能打這一支：已經由守衛擋好（看 @xxx_required 或 Depends(...)），不用自己再判斷身分
* 前端送什麼、要回什麼：docs/02-前後端串接契約.md 同名的章節
* 增刪改查：app/toolkit/crud.py（find／get／save／remove／to_dict）
* 規則（誰可以、什麼時候不行）：app/toolkit/ 對應的模組，函式說明裡寫了拿來怎麼用
* 回傳的 id 要轉成字串（crud.to_dict 預設就會轉）

`python -m app.ownership` 會列出每個人還剩幾支（有 @stub 的算還沒做）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.guards import block_admin, own
from app.models import Transaction, User
from app.routers._stub import not_ready, stub
from app.schemas.transaction import TransactionIn, TransactionPatchIn
from app.toolkit.db import get_db

router = APIRouter(tags=["記帳"])
OWNER = "成員2"


@router.get("/transactions", summary="收支明細")
@block_admin
@stub
def list_transactions(
    me: User,
    userId: str | None = None,
    groupId: str | None = None,
    from_: str | None = Query(None, alias="from"),
    to: str | None = None,
    categoryId: str | None = None,
    kind: str | None = None,
    source: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    """收支明細

    GET /api/transactions

    users, groups = visible_scope(me, db)；條件一定是 or_（監管 ∪ 同帳本）。帶 userId 但沒權限回 403 不回空陣列。
    回 {transactions, total}；userName／catName／catColor 可以不帶（前端代勞）。
    """
    raise not_ready("GET /api/transactions", OWNER)


@router.post("/transactions", summary="手動新增一筆")
@block_admin
@stub
def create_transaction(body: TransactionIn, me: User, db: Session = Depends(get_db)):
    """手動新增一筆

    POST /api/transactions

    source 一定是 manual；帳本結算過回 409（ledger.require_open）；寫通知給監管者（notify.recipients_for）。
    """
    raise not_ready("POST /api/transactions", OWNER)


@router.patch("/transactions/{tx_id}", summary="修改一筆")
@stub
def update_transaction(
    body: TransactionPatchIn,
    row=Depends(own(Transaction, "tx_id")),
    db: Session = Depends(get_db),
):
    """修改一筆

    PATCH /api/transactions/{tx_id}

    守衛已經確認是本人的（row 就是那一筆）。ledger.clean_patch → require_editable（結算過 409）；nlp 來源的把新值寫進 nlp_parses.user_corrected。
    """
    raise not_ready("PATCH /api/transactions/{tx_id}", OWNER)


@router.delete("/transactions/{tx_id}", summary="刪除一筆")
@stub
def delete_transaction(row=Depends(own(Transaction, "tx_id")), db: Session = Depends(get_db)):
    """刪除一筆

    DELETE /api/transactions/{tx_id}

    結算過的帳本回 409。回 {deleted: id}。
    """
    raise not_ready("DELETE /api/transactions/{tx_id}", OWNER)


@router.delete("/transactions", summary="一次刪多筆")
@block_admin
@stub
def delete_transactions(me: User, ids: str | None = None, db: Session = Depends(get_db)):
    """一次刪多筆

    DELETE /api/transactions

    ledger.clean_ids（空的 400）；每一筆 require_editable；全部過了才在同一個交易裡刪。回 {deleted: [...]}。
    """
    raise not_ready("DELETE /api/transactions", OWNER)
