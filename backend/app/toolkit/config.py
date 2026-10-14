"""
設定集中管理。**所有環境變數都在這裡讀進來**，其他檔案一律 `from app.toolkit.config import settings`。

✦ 領域：認證與基礎建設
✦ 各段的設定歸誰管，下面用分隔線標出來；**改自己那一段就好，別人的段落先在群組講一聲**。

===========================================================================
怎麼設定（只要做一次）
===========================================================================
    cd backend
    python -m app.cli init-env      # 從 .env.example 複製出 .env，順便產生一組 JWT_SECRET
    python -m app.cli check-config  # 看哪些還沒填、沒填的功能會怎樣（例如解析改用規則頂著）

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

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: MODEL_PROVIDER=anthropic 而 MODEL_NAME 沒改（不是 claude- 開頭）時用這一顆
CLAUDE_DEFAULT = "claude-opus-5-5"


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
    # 共用（認證 維護；四個人都會用到，改之前先講）
    # =======================================================================
    app_env: str = Field(
        default="development",
        description="development / production。production 時 db 不印 SQL、錯誤訊息不帶內部細節。",
    )
    database_url: str = Field(
        description=(
            "PostgreSQL 連線字串。格式：postgresql+psycopg://使用者:密碼@主機:埠號/資料庫名稱\n"
            "本機是 Docker 裡的那一顆（python run.py 會自己開），正式環境由 render.yaml 自動接上。"
            "測試用記憶體裡的 SQLite（toolkit/db.py 兩種都支援）。"
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
    # 認證　認證：登入、JWT、忘記密碼寄信、平台管理員
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
    # 記帳　記帳：自然語言解析的模型服務（財務建議沒另外設定時也用這一組）
    # =======================================================================
    model_provider: str = Field(
        default="openai",
        description=(
            "要打哪一種模型服務。\n"
            "  openai     OpenAI 相容的 /v1/chat/completions：OpenAI、我們微調後放在 Hugging Face Space 的\n"
            "             llama-server、Colab 上臨時開的服務都走這條（MODEL_BASE_URL 必填）\n"
            "  anthropic  Claude，用官方的 anthropic 套件（MODEL_API_KEY 必填，MODEL_BASE_URL 留空）"
        ),
    )
    model_base_url: str = Field(
        default="",
        description=(
            "OpenAI 相容服務的網址，例如 https://api.openai.com 或 Hugging Face Space 的網址（不含 /v1）。\n"
            "MODEL_PROVIDER=anthropic 時留空。\n"
            "都沒設定時 services/llm/client.py 回 None：解析與建議的路由回 503，前端用規則頂著。"
        ),
    )
    model_api_key: str = Field(
        default="",
        description="模型服務的金鑰（OpenAI／Anthropic 的 API key，或私有 Space 的 token）。**不可以 commit**。",
    )
    model_name: str = Field(
        default="qwen2.5-1.5b-fambudget",
        description=(
            "要用的模型名稱，也會寫進 nlp_parses.model_ver，換模型才分得開成績。\n"
            "MODEL_PROVIDER=anthropic 而這裡沒改（不是 claude- 開頭）時，自動用 claude-opus-5-5。"
        ),
    )
    model_effort: str = Field(
        default="low",
        description="只有 Claude 用：思考的深度（low／medium／high／xhigh／max）。記帳解析是抽欄位，low 就夠，也最快。",
    )
    model_timeout_seconds: float = Field(
        default=30.0,
        description="呼叫模型的逾時秒數。一定要設——模型卡住時，沒有逾時的 API 會跟著一起卡死。",
    )

    # =======================================================================
    # 數字　數字：財務建議、儲蓄目標
    # =======================================================================
    # 財務建議可以用另一組模型設定；每一欄留空就沿用上面記帳那一組。
    # 典型用法：記帳換成我們微調的模型（Space），建議繼續用商業 API。
    advice_provider: str = Field(default="", description="建議用的 MODEL_PROVIDER。留空＝跟記帳一樣。")
    advice_base_url: str = Field(default="", description="建議用的 MODEL_BASE_URL。留空＝跟記帳一樣。")
    advice_api_key: str = Field(default="", description="建議用的 MODEL_API_KEY。留空＝跟記帳一樣。**不可以 commit**。")
    advice_model_name: str = Field(
        default="",
        description="建議用的模型名稱（寫進 advices.model_ver）。留空＝跟記帳一樣。",
    )
    advice_effort: str = Field(default="medium", description="只有 Claude 用：建議要寫成人話，比解析多想一點。")

    savings_warn_ratio: float = Field(default=0.8, description="支出達可支配上限的幾成算「接近上限」。前端 data.js 的 savingsRule 要一致。")
    savings_over_ratio: float = Field(default=1.0, description="幾成算「超過」。")

    # =======================================================================
    # 家庭　家庭：邀請、通知
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

    @model_validator(mode="after")
    def _claude_needs_a_claude_model(self) -> "Settings":
        """用 Claude 卻沒改 MODEL_NAME：換成 CLAUDE_DEFAULT。

        不在這裡換的話，nlp_parses.model_ver、advices.model_ver 會記成 qwen2.5-1.5b-fambudget，
        報告裡「哪個模型的成績」就對不上了。
        """
        if self.model_provider.strip().lower() == "anthropic" and not self.model_name.startswith("claude-"):
            self.model_name = CLAUDE_DEFAULT
        if (self.advice_provider.strip().lower() == "anthropic"
                and not (self.advice_model_name or self.model_name).startswith("claude-")):
            self.advice_model_name = CLAUDE_DEFAULT
        return self

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
        flag("認證", "jwt_secret", bool(self.jwt_secret), "必填，服務起不來")
        flag("認證", "brevo_api_key", bool(self.brevo_api_key), "忘記密碼寄不出信")
        flag("認證", "mail_from", bool(self.mail_from), "忘記密碼寄不出信")
        flag("認證", "admin_emails", bool(self.admin_email_list), "沒有平台管理員（可以之後再設）")
        ready = bool(self.model_api_key) if self.model_provider == "anthropic" else bool(self.model_base_url)
        flag("記帳", "model_api_key" if self.model_provider == "anthropic" else "model_base_url", ready,
             "記帳解析改用規則（前後端照樣能串）", ok_msg="已設定（%s）" % self.model_provider)
        own = any((self.advice_provider, self.advice_base_url, self.advice_api_key, self.advice_model_name))
        flag("數字", "advice_*", True, "",
             ok_msg=("另外設定了一組" if own else "留空：跟記帳用同一個模型服務"))
        flag("家庭", "invite_ttl_days", self.invite_ttl_days > 0, "要大於 0", ok_msg="邀請 %d 天後失效" % self.invite_ttl_days)
        return rows


# 整個專案共用同一個 settings 物件：
#     from app.toolkit.config import settings
settings = Settings()  # type: ignore[call-arg]
