"""
分類體系。

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

from app.guards import block_admin, parent_required
from app.models import User
from app.routers._stub import not_ready, stub
from app.schemas.transaction import CategoryIn
from app.toolkit.db import get_db

router = APIRouter(tags=["分類體系"])
OWNER = "成員2"


@router.get("/categories", summary="分類（系統預設＋我們家自訂）")
@block_admin
@stub
def list_categories(me: User, db: Session = Depends(get_db)):
    """分類（系統預設＋我們家自訂）

    GET /api/categories

    family_id IS NULL 或 = me.family_id；回 {categories: [{id, name, kind, color, icon, custom}]}。
    """
    raise not_ready("GET /api/categories", OWNER)


@router.post("/categories", summary="新增家庭自訂分類")
@parent_required
@stub
def create_category(body: CategoryIn, me: User, db: Session = Depends(get_db)):
    """新增家庭自訂分類

    POST /api/categories

    只有家長（守衛擋好）；名稱 1～10 字（422）、同 kind 跟系統或我們家已有的重名回 409。
    回新的分類：custom=true、familyId、color 一律 cat-other、icon 取第一個字。
    """
    raise not_ready("POST /api/categories", OWNER)
