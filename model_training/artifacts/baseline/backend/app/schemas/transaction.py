"""
收支明細與分類的請求主體。

負責人：成員2（記帳）　✦ 分支：m2-ledger

⚠️ 欄位名字跟前端送的**一模一樣**（camelCase，例如 groupId），對照 docs/02-前後端串接契約.md。
   不要改成 snake_case——改了前端送來的欄位就對不上，FastAPI 會回 422。
⚠️ 修改類（*PatchIn）設 extra="forbid"：不認得的欄位直接擋，不要默默忽略。
"""

from __future__ import annotations


from pydantic import BaseModel, ConfigDict, Field


class TransactionIn(BaseModel):
    """手動新增一筆。amount 永遠是正數，收支方向看 kind。"""
    date: str = Field(description="YYYY-MM-DD")
    amount: float = Field(gt=0)
    kind: str = Field(pattern="^(expense|income)$")
    cat: str
    merchant: str = ""
    note: str = ""
    groupId: str | None = None


class TransactionPatchIn(BaseModel):
    """修改一筆：只送要改的。規則在 toolkit/ledger.py 的 clean_patch（EDITABLE 那幾個欄位）。"""
    model_config = ConfigDict(extra="forbid")
    date: str | None = None
    amount: float | None = Field(default=None, gt=0)
    kind: str | None = Field(default=None, pattern="^(expense|income)$")
    cat: str | None = None
    merchant: str | None = None
    note: str | None = None
    groupId: str | None = None


class CategoryIn(BaseModel):
    """家庭自訂分類（家長）。"""
    name: str = Field(min_length=1, max_length=10)
    kind: str = Field(pattern="^(expense|income)$")
