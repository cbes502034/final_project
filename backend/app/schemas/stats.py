"""
預算、存款目標、提醒門檻的請求主體。

負責人：成員3（數字）　✦ 分支：m3-analytics

⚠️ 欄位名字跟前端送的**一模一樣**（camelCase，例如 groupId），對照 docs/02-前後端串接契約.md。
   不要改成 snake_case——改了前端送來的欄位就對不上，FastAPI 會回 422。
⚠️ 修改類（*PatchIn）設 extra="forbid"：不認得的欄位直接擋，不要默默忽略。
"""

from __future__ import annotations


from pydantic import BaseModel, ConfigDict, Field


class BudgetIn(BaseModel):
    """limit 0 = 拿掉這個分類的預算。"""
    cat: str
    limit: float = Field(ge=0)
    period: str = Field(default="month", pattern="^(month|year)$")


class SavingsGoalIn(BaseModel):
    """⚠️ 只有本人能設（userId 不是自己回 403）。帶 groupId 是那本帳自己的目標。"""
    userId: str | None = None
    goal: float = Field(ge=0)
    groupId: str | None = None


class AlertIn(BaseModel):
    percent: int = Field(ge=1, le=200)
    groupId: str | None = None


class AlertPatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    percent: int | None = Field(default=None, ge=1, le=200)
    enabled: bool | None = None
