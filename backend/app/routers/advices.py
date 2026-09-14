"""
財務建議。

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
from app.schemas.advice import GenerateIn
from app.toolkit.db import get_db

router = APIRouter(tags=["財務建議"])
OWNER = "成員3"


@router.get("/advices", summary="財務建議清單")
@block_admin
@stub
def list_advices(me: User, scope: str | None = None, db: Session = Depends(get_db)):
    """財務建議清單

    GET /api/advices

    子女拿不到全家的建議；家長的 family 範圍含他照看的人的個人建議。
    """
    raise not_ready("GET /api/advices", OWNER)


@router.post("/advices/generate", summary="產生這個月的建議")
@block_admin
@stub
def generate_advices(body: GenerateIn, me: User, db: Session = Depends(get_db)):
    """產生這個月的建議

    POST /api/advices/generate

    ⚠️ 順序：analytics 先算好數字 → services.llm.advice 只做敘述 → 驗證 → 存 advices（同月同範圍蓋掉舊的）。
    scope=family 只有家長。模型沒設定回 503，前端會用規則頂著（不會存）。
    """
    raise not_ready("POST /api/advices/generate", OWNER)
