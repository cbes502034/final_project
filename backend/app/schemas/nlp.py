"""
自然語言記帳的請求主體。

負責人：成員2（記帳）　✦ 分支：m2-ledger

⚠️ 欄位名字跟前端送的**一模一樣**（camelCase，例如 groupId），對照 docs/02-前後端串接契約.md。
   不要改成 snake_case——改了前端送來的欄位就對不上，FastAPI 會回 422。
⚠️ 修改類（*PatchIn）設 extra="forbid"：不認得的欄位直接擋，不要默默忽略。
"""

from __future__ import annotations


from pydantic import BaseModel, Field


class ParseIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class Confidence(BaseModel):
    date: float = 0
    amount: float = 0
    kind: float = 0
    cat: float = 0


class Original(BaseModel):
    """解析當下的原始結果。前端記下來、使用者怎麼改都不動它，確認時一起送回來。

    跟確認後的值不一樣的欄位，就是 nlp_parses.user_corrected（模型抓錯的標註）。
    ⚠️ by = "rules" 是後端還沒接上時前端規則解析的，**不能算成模型的成績**。
    ⚠️ 這是前端送來的值，只拿來當評測資料，不影響寫進 transactions 的內容。
    """
    by: str = Field(default="model", pattern="^(model|rules)$")
    date: str | None = None
    amount: float | None = None
    kind: str | None = None
    cat: str | None = None
    merchant: str = ""
    note: str = ""


class ConfirmIn(BaseModel):
    """單筆確認。raw 是原句，conf／catConf 是模型的信心度（寫進 nlp_parses）。"""
    date: str
    amount: float = Field(gt=0)
    kind: str = Field(pattern="^(expense|income)$")
    cat: str
    merchant: str = ""
    note: str = ""
    raw: str = ""
    conf: float = 0
    catConf: float = 0
    groupId: str | None = None
    orig: Original | None = None


class BatchItem(BaseModel):
    span: str = ""
    date: str
    amount: float = Field(gt=0)
    kind: str = Field(pattern="^(expense|income)$")
    cat: str
    merchant: str = ""
    note: str = ""
    conf: Confidence | None = None
    groupId: str | None = None
    orig: Original | None = None


class ConfirmBatchIn(BaseModel):
    """⚠️ 全部成功或全部不寫。"""
    items: list[BatchItem] = Field(min_length=1)
