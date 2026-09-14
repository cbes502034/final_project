"""
自然語言記帳：解析（不寫入）與確認後寫入。

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

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.guards import block_admin
from app.models import User
from app.routers._stub import not_ready, stub
from app.schemas.nlp import ConfirmBatchIn, ConfirmIn, ParseIn
from app.toolkit.db import get_db

router = APIRouter(tags=["段落記帳"])
OWNER = "成員2"


@router.post("/nlp/parse", summary="單句解析（不寫入）")
@block_admin
@stub
def parse_one(body: ParseIn, me: User, db: Session = Depends(get_db)):
    """單句解析（不寫入）

    POST /api/nlp/parse

    services.llm.parse.parse_one(text)；模型沒設定或叫不動回 503（前端會用規則頂著）。
    """
    raise not_ready("POST /api/nlp/parse", OWNER)


@router.post("/nlp/parse-batch", summary="段落解析（不寫入）")
@block_admin
@stub
def parse_batch(body: ParseIn, me: User, db: Session = Depends(get_db)):
    """段落解析（不寫入）

    POST /api/nlp/parse-batch

    services.llm.parse.parse_batch(text)；回 {raw, items: [{seq, span, date, amount, kind, cat, merchant, conf, missing, hint}], note}。
    """
    raise not_ready("POST /api/nlp/parse-batch", OWNER)


@router.post("/nlp/confirm", summary="單筆確認後寫入")
@block_admin
@stub
def confirm_one(body: ConfirmIn, me: User, db: Session = Depends(get_db)):
    """單筆確認後寫入

    POST /api/nlp/confirm

    source = nlp；同時寫 nlp_parses（raw、model_output = orig、user_corrected = 跟 orig 不一樣的欄位）。
    """
    raise not_ready("POST /api/nlp/confirm", OWNER)


@router.post("/nlp/confirm-batch", summary="批次確認後一次寫入")
@block_admin
@stub
def confirm_batch(body: ConfirmBatchIn, me: User, db: Session = Depends(get_db)):
    """批次確認後一次寫入

    POST /api/nlp/confirm-batch

    ⚠️ 全部成功或全部不寫（同一個交易）；回 {created: 幾筆}。
    每一筆同時寫 nlp_parses：raw = span、model_output = orig、user_corrected = 跟 orig 不一樣的欄位；
    orig.by == "rules"（前端規則頂著的）不算模型的成績。第一筆的 groupId 決定記進哪本帳。
    """
    raise not_ready("POST /api/nlp/confirm-batch", OWNER)
