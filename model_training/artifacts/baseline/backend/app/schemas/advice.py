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


class AdviceItem(BaseModel):
    """模型寫回來的一則建議。**不是請求主體**：POST /api/advices/generate 拿它驗證模型的輸出。

    少欄位、level 不對、basis 是空的——這一則就不要存（模型寫的東西不能直接信）。
    """
    level: str = Field(pattern="^(ok|info|warn)$")
    title: str = Field(min_length=1, max_length=40)
    body: str = Field(min_length=1, max_length=300)
    basis: list[str] = Field(min_length=1, description="依據：每一條都要是算好的數字寫成的句子")
    suggest: list[str] = []
    conf: float = Field(default=0.8, ge=0, le=1)
