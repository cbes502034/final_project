"""
認證相關的請求主體。

負責人：成員1（認證）　✦ 分支：m1-auth

⚠️ 欄位名字跟前端送的**一模一樣**（camelCase，例如 groupId），對照 docs/02-前後端串接契約.md。
   不要改成 snake_case——改了前端送來的欄位就對不上，FastAPI 會回 422。
⚠️ 修改類（*PatchIn）設 extra="forbid"：不認得的欄位直接擋，不要默默忽略。
"""

from __future__ import annotations


from pydantic import BaseModel, ConfigDict, Field


class RegisterIn(BaseModel):
    """註冊只問名字、email、密碼。

    ⚠️ 存款目標不在這裡（註冊後的個人化設定才問）。savingsGoal 留著欄位只是為了
       **路由能回 400 講清楚原因**——舊前端塞進來時，不要讓它默默被吃掉。
    """
    name: str = Field(min_length=1, max_length=30)
    email: str
    password: str
    savingsGoal: float | None = Field(default=None, description="不收：帶了回 400")


class LoginIn(BaseModel):
    email: str
    password: str


class RefreshIn(BaseModel):
    refreshToken: str


class LogoutIn(BaseModel):
    refreshToken: str | None = None


class PasswordChangeIn(BaseModel):
    oldPassword: str
    newPassword: str


class PasswordResetIn(BaseModel):
    email: str


class PasswordResetConfirmIn(BaseModel):
    token: str
    password: str


class VerifyPasswordIn(BaseModel):
    password: str


class ProfilePatchIn(BaseModel):
    """只送要改的欄位。onboarded 只收 true（註冊後的個人化設定走完）。"""
    model_config = ConfigDict(extra="forbid")
    displayName: str | None = None
    birthYear: int | None = None
    theme: str | None = None
    onboarded: bool | None = None


class AvatarIn(BaseModel):
    image: str = Field(description="data:image/jpeg;base64,...（前端已縮到 256×256）")


class FinanceIn(BaseModel):
    style: str | None = None
    goals: list[str] = []
    habits: list[str] = []
    note: str = ""


class SuspendIn(BaseModel):
    reason: str
