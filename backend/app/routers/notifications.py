"""
通知。

負責人：成員4（家庭）　✦ 分支：m4-access

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
from app.models import Notification, User
from app.routers._stub import not_ready, stub
from app.schemas.family import ReadAllIn, ReadOneIn
from app.toolkit.db import get_db

router = APIRouter(tags=["通知"])
OWNER = "成員4"


@router.get("/notifications", summary="通知清單（輪詢）")
@block_admin
@stub
def list_notifications(
    me: User,
    since: str | None = None,
    unreadOnly: bool = False,
    db: Session = Depends(get_db),
):
    """通知清單（輪詢）

    GET /api/notifications

    WHERE recipient_id = 我；帶 since 只回更新的；回 {notifications, unread, maxId}。
    """
    raise not_ready("GET /api/notifications", OWNER)


@router.patch("/notifications/{nid}", summary="一則標記已讀")
@stub
def read_notification(
    body: ReadOneIn,
    row=Depends(own(Notification, "nid", "recipient_id")),
    db: Session = Depends(get_db),
):
    """一則標記已讀

    PATCH /api/notifications/{nid}

    body {read: true}；只能標自己的通知（recipient_id = 我）；回 {id, readAt}。
    """
    raise not_ready("PATCH /api/notifications/{nid}", OWNER)


@router.patch("/notifications", summary="整批標記已讀")
@block_admin
@stub
def read_notifications(body: ReadAllIn, me: User, db: Session = Depends(get_db)):
    """整批標記已讀

    PATCH /api/notifications

    只標到 readUntil 那一則，不要把之後才進來的也標掉。
    """
    raise not_ready("PATCH /api/notifications", OWNER)
