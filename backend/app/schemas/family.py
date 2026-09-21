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
    """監管人一定是自己。

    ⚠️ guardianId 留著欄位只是為了**路由能回 403 講清楚原因**——帶了別人的 id，
       等於替別的家長決定他要看誰，不要讓它默默被吃掉。
    """
    wardId: str
    guardianId: str | None = Field(default=None, description="不收：帶了別人的 id 回 403")


class AllowanceIn(BaseModel):
    wardId: str
    amount: float = Field(ge=0)


class ReadOneIn(BaseModel):
    read: bool = True


class ReadAllIn(BaseModel):
    readUntil: str | None = None
