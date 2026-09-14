"""
階段性提醒門檻。

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

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.guards import block_admin, own
from app.models import AlertRule, User
from app.routers._stub import not_ready, stub
from app.schemas.stats import AlertIn, AlertPatchIn
from app.toolkit.db import get_db

router = APIRouter(tags=["提醒"])
OWNER = "成員3"


@router.get("/alerts", summary="我設的提醒門檻")
@block_admin
@stub
def list_alerts(me: User, db: Session = Depends(get_db)):
    """我設的提醒門檻

    GET /api/alerts

    回 {alerts: [...]}。
    """
    raise not_ready("GET /api/alerts", OWNER)


@router.post("/alerts", summary="新增門檻")
@block_admin
@stub
def create_alert(body: AlertIn, me: User, db: Session = Depends(get_db)):
    """新增門檻

    POST /api/alerts

    alerts.validate_percent；同一個 (user, group, percent) 重複回 409。
    """
    raise not_ready("POST /api/alerts", OWNER)


@router.patch("/alerts/{aid}", summary="改門檻或暫停")
@stub
def update_alert(
    body: AlertPatchIn,
    row=Depends(own(AlertRule, "aid")),
    db: Session = Depends(get_db),
):
    """改門檻或暫停

    PATCH /api/alerts/{aid}

    關掉用 enabled=false，不要刪。
    """
    raise not_ready("PATCH /api/alerts/{aid}", OWNER)


@router.delete("/alerts/{aid}", summary="刪門檻")
@stub
def delete_alert(row=Depends(own(AlertRule, "aid")), db: Session = Depends(get_db)):
    """刪門檻

    DELETE /api/alerts/{aid}
    """
    raise not_ready("DELETE /api/alerts/{aid}", OWNER)
