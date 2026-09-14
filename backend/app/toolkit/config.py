"""
設定集中管理。**所有環境變數都在這裡讀進來**，其他檔案一律 `from app.toolkit.config import settings`。

✦ 負責人：成員1（認證與基礎建設）　✦ 分支：m1-auth
✦ 各段的設定歸誰管，下面用分隔線標出來；**改自己那一段就好，別人的段落先在群組講一聲**。

===========================================================================
怎麼設定（只要做一次）
===========================================================================
    cd backend
    python -m app.cli init-env      # 從 .env.example 複製出 .env，順便產生一組 JWT_SECRET
    python -m app.cli check-config  # 看哪些還沒填、哪些功能因此會退回假資料

值寫在 `backend/.env`（已經在 .gitignore，不會被 commit）。
Render 上沒有 .env，是在後台的 Environment 頁面填，名字跟這裡一模一樣（大寫）。

===========================================================================
為什麼要有這個檔案？
===========================================================================
新手最常見的寫法是把設定散在各處：

    # ❌ 不要這樣寫
    conn = psycopg.connect("postgresql://user:password@localhost/db")
    SECRET = "my-secret-key"

1. **密碼寫死在程式碼裡**，一 push 到 GitHub 就外洩了
2. 本機、正式環境要用不同的值，到處改很容易漏掉
3. 想知道「這個專案總共需要哪些設定」時，得翻遍整個專案

pydantic-settings 的做法是：把所有設定寫成一個類別的欄位，
它會自動去環境變數或 .env 檔案裡找對應的值，**必填的找不到就在啟動時報錯**——
而不是等到使用者按下登入按鈕的那一刻才發現 JWT_SECRET 是空的。

⚠️ 前端要連哪個後端，不在這裡：改 `frontend/index.html` 的 `<meta name="api-base">`。
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    每一個欄位對應一個環境變數（不分大小寫：`database_url` ⇄ `DATABASE_URL`）。
    有預設值的可以不設；沒有預設值的**一定要設，不然服務起不來**。
    """

    model_config = SettingsConfigDict(
        env_file=".env",           # 本機開發時從 backend/.env 讀
        env_file_encoding="utf-8",
        extra="ignore",            # .env 裡有多餘的變數就忽略，不要報錯
        # pydantic 預設保留 model_ 開頭的名字；我們的 MODEL_BASE_URL 等是「模型服務」的設定，不是撞名
        protected_namespaces=("settings_",),
    )

    # =======================================================================
    # 共用（成員1 維護；四個人都會用到，改之前先講）
    # =======================================================================
    app_env: str = Field(
        default="development",
        description="development / production。production 時 db 不印 SQL、錯誤訊息不帶內部細節。",
    )
    database_url: str = Field(
        description=(
            "PostgreSQL 連線字串。格式：postgresql+psycopg://使用者:密碼@主機:埠號/資料庫名稱\n"
            "本機沒有 PostgreSQL 時可以先用 sqlite:///./dev.db（toolkit/db.py 兩種都支援），"
            "但正式環境一定是 PostgreSQL。"
        )
    )
    db_echo: bool = Field(default=False, description="True 會把送出的 SQL 印出來，除錯用。正式環境不要開。")
    db_pool_size: int = Field(
        default=5,
        description="連線池大小。Render 免費 PostgreSQL 同時連線數很少，不要開太大。SQLite 會忽略。",
    )
    allowed_origins: str = Field(
        default="http://localhost:5174",
        description="允許哪些前端網域來打這個 API，逗號分隔。填錯前端會被瀏覽器的 CORS 擋住。",
    )

    # =======================================================================
    # 成員1　認證：登入、JWT、忘記密碼寄信、平台管理員
    # =======================================================================
    jwt_secret: str = Field(
        description=(
            "簽 JWT 用的密鑰。這是整個系統最敏感的一個值——拿到它的人可以偽造任何人的登入權杖。\n"
            "**絕對不可以 commit**。產生：python -c \"import secrets;print(secrets.token_urlsafe(48))\""
        )
    )
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = Field(
        default=30,
        description="access token 有效期（分鐘）。刻意設短：外洩時損害只持續這麼久，前端會自動續期。",
    )
    refresh_token_days: int = Field(default=14, description="refresh token 有效期（天）。存在 sessions 表，可以撤銷。")
    brevo_api_key: str = Field(
        default="",
        description=(
            "Brevo 的 API 金鑰（Brevo 後台 → SMTP & API → API keys），忘記密碼寄信用。**不可以 commit**。\n"
            "⚠️ 不能改用 SMTP：Render 免費方案擋掉了 25／465／587 埠，見 toolkit/mailer.py。"
        ),
    )
    mail_from: str = Field(default="", description="寄件信箱。一定要先在 Brevo 的 Senders 驗證過，不然信會被拒絕。")
    mail_from_name: str = Field(default="家庭記帳", description="收件人看到的寄件人名稱。")
    app_base_url: str = Field(
        default="https://fambudget-web.onrender.com",
        description="前端網址。重設密碼信裡的連結會長成 <這個網址>/#/reset/<token>。本機改成 http://localhost:5174。",
    )
    admin_emails: str = Field(
        default="",
        description=(
            "平台管理員的 email，逗號分隔。`python -m app.cli make-admin` 會把這些帳號設成平台管理員。\n"
            "⚠️ 平台管理員只能停權與看稽核，讀不到任何人的帳。"
        ),
    )

    # =======================================================================
    # 成員2　記帳：自然語言解析用的模型服務
    # =======================================================================
    model_base_url: str = Field(
        default="",
        description=(
            "我們自己微調的 Qwen2.5-1.5B 模型服務網址（GGUF + llama.cpp，跑在 Hugging Face Space）。\n"
            "留空時 services/llm/client.py 回 None，解析改用規則、前端也會自己頂著，前後端照樣串得起來。"
        ),
    )
    model_api_key: str = Field(
        default="",
        description="模型服務要驗證時用（例如私有的 Hugging Face Space 的 token）。公開的就留空。**不可以 commit**。",
    )
    model_name: str = Field(default="qwen2.5-1.5b-fambudget", description="寫進 nlp_parses.model_ver，換模型才分得開成績。")
    model_timeout_seconds: float = Field(
        default=30.0,
        description="呼叫模型的逾時秒數。一定要設——模型卡住時，沒有逾時的 API 會跟著一起卡死。",
    )

    # =======================================================================
    # 成員3　數字：財務建議
    # =======================================================================
    advice_model_name: str = Field(
        default="",
        description="產生財務建議用的模型名稱（寫進 advices.model_ver）。留空就跟記帳用同一個模型服務。",
    )
    savings_warn_ratio: float = Field(default=0.8, description="支出達可支配上限的幾成算「接近上限」。前端 data.js 的 savingsRule 要一致。")
    savings_over_ratio: float = Field(default=1.0, description="幾成算「超過」。")

    # =======================================================================
    # 成員4　家庭：邀請、通知
    # =======================================================================
    invite_ttl_days: int = Field(
        default=7,
        description="邀請與邀請碼幾天後失效。產生時呼叫 family.expires_at(days=settings.invite_ttl_days)。",
    )

    # -----------------------------------------------------------------------
    @field_validator("jwt_secret")
    @classmethod
    def _secret_must_be_long_enough(cls, v: str) -> str:
        """
        JWT 密鑰太短的話，攻擊者暴力破解得出來，就能偽造任何人的登入權杖。
        RFC 7518 建議 HMAC-SHA256 的密鑰至少 32 個位元組，所以在**啟動時**就擋下來。
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
        """逗號分隔的字串 → 清單（CORSMiddleware 要的是清單）。"""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def admin_email_list(self) -> list[str]:
        return [e.strip().lower() for e in self.admin_emails.split(",") if e.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    def report(self) -> list[tuple[str, str, str]]:
        """每一段設定的狀態：(段落, 變數, 狀態說明)。`python -m app.cli check-config` 用。"""
        rows = []

        def flag(section, name, ok, missing_msg, ok_msg="已設定"):
            rows.append((section, name.upper(), ("✓ " + ok_msg) if ok else "✗ " + missing_msg))

        flag("共用", "database_url", bool(self.database_url), "必填，服務起不來")
        flag("共用", "allowed_origins", bool(self.allowed_origins_list), "前端會被 CORS 擋住")
        flag("成員1", "jwt_secret", bool(self.jwt_secret), "必填，服務起不來")
        flag("成員1", "brevo_api_key", bool(self.brevo_api_key), "忘記密碼寄不出信")
        flag("成員1", "mail_from", bool(self.mail_from), "忘記密碼寄不出信")
        flag("成員1", "admin_emails", bool(self.admin_email_list), "沒有平台管理員（可以之後再設）")
        flag("成員2", "model_base_url", bool(self.model_base_url), "記帳解析改用規則（前後端照樣能串）")
        flag("成員3", "advice_model_name", True, "",
             ok_msg=("已設定" if self.advice_model_name else "留空：跟記帳用同一個模型服務"))
        flag("成員4", "invite_ttl_days", self.invite_ttl_days > 0, "要大於 0", ok_msg="邀請 %d 天後失效" % self.invite_ttl_days)
        return rows


# 整個專案共用同一個 settings 物件：
#     from app.toolkit.config import settings
settings = Settings()  # type: ignore[call-arg]
