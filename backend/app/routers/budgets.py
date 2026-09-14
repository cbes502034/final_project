"""
預算與每月存款目標。

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
from app.schemas.stats import BudgetIn, SavingsGoalIn
from app.toolkit.db import get_db

router = APIRouter(tags=["預算與存款目標"])
OWNER = "成員3"


@router.get("/budgets", summary="預算與已花")
@block_admin
@stub
def list_budgets(me: User, groupId: str | None = None, db: Session = Depends(get_db)):
    """預算與已花

    GET /api/budgets

    used 一律從明細算；pct／over 前端會自己算。
    """
    raise not_ready("GET /api/budgets", OWNER)


@router.put("/budgets", summary="設定預算（limit 0 = 拿掉）")
@block_admin
@stub
def set_budget(body: BudgetIn, me: User, db: Session = Depends(get_db)):
    """設定預算（limit 0 = 拿掉）

    PUT /api/budgets

    只設自己的；只能設在支出分類。
    """
    raise not_ready("PUT /api/budgets", OWNER)


@router.put("/savings-goal", summary="設定每月存款目標")
@block_admin
@stub
def set_savings_goal(body: SavingsGoalIn, me: User, db: Session = Depends(get_db)):
    """設定每月存款目標

    PUT /api/savings-goal

    ⚠️ 只有本人能設（roles.require_set_goal）；改動新增一列不覆蓋（period_key）。
    """
    raise not_ready("PUT /api/savings-goal", OWNER)


@router.get("/savings-goals", summary="整體＋各帳本的存款目標")
@block_admin
@stub
def list_savings_goals(me: User, db: Session = Depends(get_db)):
    """整體＋各帳本的存款目標

    GET /api/savings-goals

    回 {goals: [{groupId, groupName, goal}]}，groupId null 是整體。
    """
    raise not_ready("GET /api/savings-goals", OWNER)
