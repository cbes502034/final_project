"""
設定集中管理。所有環境變數都在這裡讀進來。

✦ 負責人：成員1（認證與基礎建設）　✦ 分支：m1-auth
✦ **這是共用元件，四個人都會用到，第 1 週要最優先完成**

===========================================================================
為什麼要有這個檔案？
===========================================================================
新手最常見的寫法是把設定散在各處：

    # ❌ 不要這樣寫
    conn = psycopg.connect("postgresql://user:password@localhost/db")
    SECRET = "my-secret-key"

這有三個問題：
1. **密碼寫死在程式碼裡**，一 push 到 GitHub 就外洩了
2. 本機、正式環境要用不同的值，到處改很容易漏掉
3. 想知道「這個專案總共需要哪些設定」時，得翻遍整個專案

pydantic-settings 的做法是：把所有設定寫成一個類別的欄位，
它會自動去環境變數或 .env 檔案裡找對應的值，找不到就報錯。

**「找不到就報錯」很重要**——服務會在啟動的當下就掛掉並告訴你少了什麼，
而不是等到使用者按下登入按鈕的那一刻才發現 JWT_SECRET 是空的。
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    這個類別的每一個欄位，都對應一個環境變數。

    名字的對應是不分大小寫的：欄位 `database_url` 會去找環境變數 `DATABASE_URL`。
    有寫預設值的（例如 `access_token_minutes: int = 30`）代表可以不設；
    沒寫預設值的（例如 `database_url: str`）代表**一定要設，不然服務起不來**。
    """

    model_config = SettingsConfigDict(
        env_file=".env",           # 本機開發時從這個檔案讀
        env_file_encoding="utf-8",
        extra="ignore",            # .env 裡有多餘的變數就忽略，不要報錯
    )

    # ---------- 資料庫 ----------
    database_url: str = Field(
        description=(
            "PostgreSQL 連線字串。格式："
            "postgresql+psycopg://使用者:密碼@主機:埠號/資料庫名稱\n"
            "中間的 +psycopg 是告訴 SQLAlchemy 用哪個驅動程式連資料庫。"
        )
    )

    # ---------- 認證 ----------
    jwt_secret: str = Field(
        description=(
            "簽 JWT 用的密鑰。這是整個系統最敏感的一個值——"
            "拿到它的人可以偽造任何人的登入權杖。\n"
            "**絕對不可以 commit 進 repo**，Render 上是在後台手動填入的。"
        )
    )
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = Field(
        default=30,
        description=(
            "access token 的有效期，單位是分鐘。\n"
            "刻意設短：萬一權杖外洩，損害只持續 30 分鐘。"
            "使用者不會因此一直被登出，因為過期時前端會自動用 refresh token 換一張新的。"
        ),
    )
    refresh_token_days: int = Field(
        default=14,
        description="refresh token 的有效期，單位是天。這張存在資料庫裡，可以主動撤銷。",
    )

    # ---------- 前端來源 ----------
    allowed_origins: str = Field(
        default="http://localhost:5174",
        description=(
            "允許哪些網域的前端來打這個 API，多個用逗號隔開。\n"
            "這是 CORS 設定，填錯前端會被瀏覽器擋住。"
        ),
    )

    # ---------- 模型服務 ----------
    model_base_url: str = Field(
        default="",
        description=(
            "我們自己微調的 Qwen2.5-1.5B 模型服務網址"
            "（GGUF + llama.cpp，跑在 Hugging Face Space 上）。\n"
            "留空時 services/llm/parse.py 會回傳假資料，讓前後端可以先串起來，"
            "不必等模型訓練完。"
        ),
    )
    model_timeout_seconds: float = Field(
        default=30.0,
        description=(
            "呼叫模型的逾時秒數。\n"
            "一定要設——沒有逾時的話，模型服務卡住時，"
            "我們的 API 會跟著一起卡死，最後整個服務沒有回應。"
        ),
    )

    @field_validator("jwt_secret")
    @classmethod
    def _secret_must_be_long_enough(cls, v: str) -> str:
        """
        JWT 密鑰太短的話，攻擊者暴力破解得出來，就能偽造任何人的登入權杖。

        RFC 7518 建議 HMAC-SHA256 的密鑰至少 32 個位元組。
        這裡在**啟動時**就擋下來，而不是等出事才發現。

        產生一組：
            python -c "import secrets;print(secrets.token_urlsafe(48))"
        """
        if len(v.encode("utf-8")) < 32:
            raise ValueError(
                f"JWT_SECRET 太短了（目前 {len(v.encode('utf-8'))} 個位元組，"
                "至少要 32 個）。產生方式："
                'python -c "import secrets;print(secrets.token_urlsafe(48))"'
            )
        return v

    @property
    def allowed_origins_list(self) -> list[str]:
        """
        把逗號分隔的字串拆成清單，順便去掉前後空白。

        因為環境變數只能存字串，但 CORSMiddleware 要的是清單，
        所以在這裡轉換一次，其他地方直接用這個屬性就好。
        """
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


# 整個專案共用同一個 settings 物件。
# 在別的檔案裡這樣用：
#     from app.toolkit.config import settings
#     print(settings.database_url)
settings = Settings()  # type: ignore[call-arg]
