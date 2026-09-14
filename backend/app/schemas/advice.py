"""
財務建議的請求主體。

負責人：成員3（數字）　✦ 分支：m3-analytics

⚠️ 欄位名字跟前端送的**一模一樣**（camelCase，例如 groupId），對照 docs/02-前後端串接契約.md。
   不要改成 snake_case——改了前端送來的欄位就對不上，FastAPI 會回 422。
⚠️ 修改類（*PatchIn）設 extra="forbid"：不認得的欄位直接擋，不要默默忽略。
"""

from __future__ import annotations


from pydantic import BaseModel, Field


class GenerateIn(BaseModel):
    """me：寫給自己的；family：全家（只有家長）。"""
    scope: str = Field(default="me", pattern="^(me|family)$")
