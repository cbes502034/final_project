"""
統計摘要。

負責人：成員3（數字）　✦ 分支：m3-analytics

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

from app.guards import block_admin
from app.models import User
from app.routers._stub import not_ready, stub
from app.toolkit.db import get_db

router = APIRouter(tags=["統計"])
OWNER = "成員3"


@router.get("/summary", summary="個人／家庭摘要")
@block_admin
@stub
def get_summary(
    me: User,
    scope: str | None = None,
    groupId: str | None = None,
    db: Session = Depends(get_db),
):
    """個人／家庭摘要

    GET /api/summary

    services.analytics.summary(...)。後端只要回 income、expense、byCat、monthly、yearly（加總從明細算）；
    net／rate／savings.* 前端會自己算（前端代勞），想回也可以。家庭模式子女的收入不算進家庭收入。
    """
    raise not_ready("GET /api/summary", OWNER)
