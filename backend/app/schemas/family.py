"""
家庭、邀請、監管、零用金、通知的請求主體。

負責人：成員4（家庭）　✦ 分支：m4-access

⚠️ 欄位名字跟前端送的**一模一樣**（camelCase，例如 groupId），對照 docs/02-前後端串接契約.md。
   不要改成 snake_case——改了前端送來的欄位就對不上，FastAPI 會回 422。
⚠️ 修改類（*PatchIn）設 extra="forbid"：不認得的欄位直接擋，不要默默忽略。
"""

from __future__ import annotations


from pydantic import BaseModel, Field


class FamilyIn(BaseModel):
    name: str = Field(min_length=1, max_length=20)


class InviteCodeIn(BaseModel):
    """⚠️ 身分由家長決定，拿到碼的人不能自己選。"""
    role: str = Field(pattern="^(parent|child)$")


class JoinIn(BaseModel):
    code: str


class InviteIn(BaseModel):
    userId: str
    role: str = Field(pattern="^(parent|child)$")


class RolePatchIn(BaseModel):
    role: str = Field(pattern="^(parent|child)$")


class GuardianshipIn(BaseModel):
    """監管人一定是自己；guardianId 不收（替別的家長建立監管等於替他決定要看誰）。"""
    wardId: str


class AllowanceIn(BaseModel):
    wardId: str
    amount: float = Field(ge=0)


class ReadOneIn(BaseModel):
    read: bool = True


class ReadAllIn(BaseModel):
    readUntil: str | None = None
