"""
平台管理：停權與解除停權。

負責人：成員1（認證）　✦ 分支：m1-auth

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

from app.guards import admin_required
from app.models import User
from app.routers._stub import not_ready, stub
from app.schemas.auth import SuspendIn
from app.toolkit.db import get_db

router = APIRouter(tags=["平台管理"])
OWNER = "成員1"


@router.get("/admin/users", summary="帳號清單（停權用）")
@admin_required
@stub
def admin_list_users(me: User, db: Session = Depends(get_db)):
    """帳號清單（停權用）

    GET /api/admin/users

    ⚠️ 只回 id／名字／email／角色／停權狀態，不回任何金額。
    """
    raise not_ready("GET /api/admin/users", OWNER)


@router.post("/admin/users/{user_id}/suspend", summary="停權")
@admin_required
@stub
def suspend_user(user_id: str, body: SuspendIn, me: User, db: Session = Depends(get_db)):
    """停權

    POST /api/admin/users/{user_id}/suspend

    roles.clean_suspend_reason；不能停平台管理員（roles.require_suspendable）；寫 audit_logs。
    """
    raise not_ready("POST /api/admin/users/{user_id}/suspend", OWNER)


@router.delete("/admin/users/{user_id}/suspend", summary="解除停權")
@admin_required
@stub
def unsuspend_user(user_id: str, me: User, db: Session = Depends(get_db)):
    """解除停權

    DELETE /api/admin/users/{user_id}/suspend

    suspended_at 設 NULL；一樣寫 audit_logs。
    """
    raise not_ready("DELETE /api/admin/users/{user_id}/suspend", OWNER)
