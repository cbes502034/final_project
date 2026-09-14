"""
帳本的請求主體。

負責人：成員2（記帳）　✦ 分支：m2-ledger

⚠️ 欄位名字跟前端送的**一模一樣**（camelCase，例如 groupId），對照 docs/02-前後端串接契約.md。
   不要改成 snake_case——改了前端送來的欄位就對不上，FastAPI 會回 422。
⚠️ 修改類（*PatchIn）設 extra="forbid"：不認得的欄位直接擋，不要默默忽略。
"""

from __future__ import annotations


from pydantic import BaseModel, ConfigDict, Field


class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    color: str | None = None
    kind: str = Field(default="standing", pattern="^(standing|temp)$")
    endsOn: str | None = Field(default=None, description="活動帳本（temp）必填，YYYY-MM-DD")
    note: str = ""


class GroupPatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=20)
    color: str | None = None
    note: str | None = None


class GroupMemberIn(BaseModel):
    userId: str


class NotifyIn(BaseModel):
    notify: bool
