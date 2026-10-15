# backend — FastAPI 後端

> 第一次碰 FastAPI？**先讀站上的 [FastAPI 說明書](https://fambudget-web.onrender.com/docs/fastapi.html)**，
> 那份是從零開始教的。這份 README 假設你已經讀過了。

---

> **動工前先讀 [`../docs/02-前後端串接契約.md`](../docs/02-前後端串接契約.md)。**
> 那份寫清楚每一支路由「前端送什麼、你要吐什麼、前端拿去幹嘛」，
> 而且是從前端程式實際跑出來的，不是手寫的。
> 裡面開頭有**四件已經定案的事**（ID 回字串、人身上不放收支、前端代勞、錯誤怎麼回），先讀那一段。

## 三十秒跑起來

```bash
cd backend
pip install -r requirements.txt
python -m app.cli init-env        # 從 .env.example 建出 .env，順便產生 JWT_SECRET
python -m app.cli check-config    # 列出每一段設定填了沒、沒填會怎樣
docker compose up -d --wait db    # 開 PostgreSQL（在專案最外層跑；要先打開 Docker Desktop）
alembic upgrade head              # 建表
python -m app.cli init-db         # 放入系統預設分類
uvicorn app.main:app --reload
```

打開 <http://localhost:8000/docs> ——
FastAPI 自動產生的互動式文件，**可以直接在上面送出請求試打**，
不需要寫前端，也不需要 Postman。70 支路由都在上面，還沒做的回 501。

看自己剛剛寫進去的資料（不用裝任何工具）：

```bash
python -m app.cli db                                       # 每張表各幾筆
python -m app.cli db "SELECT id, email FROM users"         # 只能查，不能改
```

跑測試：

```bash
pytest
```

---

## 目錄怎麼看

```
backend/
├── app/
│   ├── main.py            ← 入口。只負責組裝（CORS、錯誤處理、掛上 routers/ 的每一組）
│   ├── guards.py          ← 路由守衛：沒登入、被停權、角色不對、不是自己的資料，路由裡一行都不會跑
│   ├── cli.py             ← 小工具指令：init-env、check-config、init-db、make-admin、db
│   ├── ownership.py       ← 分工的單一事實來源
│   ├── catalog.py         ← 固定清單：角色、權限表、理財選項、系統分類（正本是 frontend/js/data.js）
│   │
│   ├── toolkit/           ← 寫好、測好的工具，直接用
│   │   ├── config.py        設定（依成員分段）
│   │   ├── db.py            資料庫連線：get_db、session_scope、@db_transaction
│   │   ├── crud.py          增刪改查：get、find、save、remove、to_dict
│   │   ├── errors.py        錯誤回應（400／401／403／404／409／422／501／503）
│   │   ├── deps.py          從 JWT 取出登入者、分頁參數
│   │   ├── tokens.py · passwords.py · password_reset.py · mailer.py
│   │   ├── scope.py         可見範圍的規則（監管 ∪ 同帳本）
│   │   ├── family.py · roles.py · ledger.py · alerts.py · notify.py
│   │   └── period.py · money.py · images.py · profile.py · theme.py
│   │
│   ├── models/            ← 資料庫長什麼樣（SQLAlchemy，20 張表，跟 data.js 的 schema 逐欄對齊）
│   ├── schemas/           ← API 收什麼（Pydantic），欄位名字跟前端送的一樣
│   ├── routers/           ← 路由。**一個領域一個資料夾，開自己那一個就好**
│   │                        每個資料夾裡都有 README.md，寫你那一塊怎麼開發
│   │   ├── auth/            認證     auth.py、admin.py
│   │   ├── ledger/          記帳     transactions.py、nlp.py、categories.py、groups.py
│   │   ├── analytics/       數字     stats.py、budgets.py、alerts.py、advices.py
│   │   ├── access/          家庭     family.py、notifications.py
│   │   └── _stub.py         共用：@stub 與 not_ready()（還沒做的回 501）
│   └── services/          ← 加總與模型：analytics、llm/（client、parse、advice）、permission、evaluation
│
├── alembic/               ← 資料庫結構的版本控制（versions/ 第一版就是 20 張表）
├── alembic.ini            ← ⚠️ 只能有英文（Windows 的 alembic 用 cp950 讀它）
├── tests/                 ← pytest；fixtures/ 放測試用的一家人與假後端
├── tools/                 ← eval_nlp.py、rules_baseline.js：評測；sync_schema.py：文件從程式產生
├── eval/                  ← 留出集與評測結果
├── requirements.txt
├── Dockerfile             ← 啟動前先 alembic upgrade head
└── .env.example           ← 設定範本，依成員分段，機密一律留空
```

### 為什麼 models 和 schemas 要分開？

這是新手最容易搞混的一點。

| | 回答的問題 | 例子 |
|---|---|---|
| `models/` | **資料庫裡存什麼** | `User` 有 `password_hash` 欄位 |
| `schemas/` | **API 收送什麼** | `UserResponse` **沒有** `password_hash` |

分開的好處立刻就看得到：使用者資料表一定要存密碼雜湊，
但任何一支 API 的回應都不該把它送出去。
兩者分開之後，你不可能「不小心」把密碼雜湊回傳給前端——
因為 response model 裡根本沒有那一欄。

### 為什麼 routers 不寫邏輯？

`routers/` 只做三件事：收請求、（守衛）驗權限、回結果。
規則寫在 `toolkit/`（例如 `family.require_can_dissolve()`），加總與模型寫在 `services/`。

這樣做測試時可以直接呼叫函式，
不必每次都起一個完整的 HTTP 請求，快很多也好寫很多。

---

## 寫一支路由的完整樣子

打開自己的檔案，找到那一支，**先讀它的說明字串**（那是這一支的規格書，最後兩段是「完整寫法」與「做完怎麼確認」），
再刪掉 `@stub`、把 `raise not_ready(...)` 那一行換成說明字串的第二步。做完長這樣：

```python
from app.guards import parent_required
from app.models import FamilyMember, Guardianship
from app.toolkit import crud, errors, family
from app.toolkit.db import session_scope

@router.delete("/family", summary="解散家庭（唯一的家長）")
@parent_required                                  # ← 守衛：沒登入 401、不是家長 403，下面不用再判斷
def dissolve_family(me: User, db: Session = Depends(get_db)):
    others = crud.count(FamilyMember, {"family_id": me.family_id, "role": "parent",
                                       "status": "active", "user_id__ne": me.id}, db=db)
    try:
        family.require_can_dissolve(me.family_role, others)     # ← 規則在 toolkit，不在路由裡
    except ValueError as exc:
        raise errors.conflict(str(exc)) from exc

    with session_scope(db):                                    # ← 一起成功或一起失敗
        people = crud.find(FamilyMember, {"family_id": me.family_id, "status": "active"}, fields="user_id", db=db)
        crud.remove(Guardianship, {"or": [{"guardian_id__in": people}, {"ward_id__in": people}],
                                   "ended_at__isnull": True}, soft="ended_at", db=db)
        crud.save(FamilyMember, {"status": "removed"}, where={"family_id": me.family_id}, db=db)
        ...                                                    # 帳本互相移出、邀請作廢（契約那一節列了全部）
        db.commit()
    return {"dissolved": True, "released": len(people)}
```

### 增刪改查：`toolkit/crud.py`

五支就夠，**參數決定做什麼**（跟 MineMarket 的 `getUser({"token": t}, "token")` 同一個想法，但不綁表、不手拼 SQL）：

| 想做的事 | 寫法 |
|---|---|
| 拿一筆／只拿一個欄位 | `get(User, 3)`、`get(User, where={"email": e}, fields="id")` |
| 找不到直接回 404 | `get(Group, gid, missing=errors.not_found("找不到這本帳"))` |
| 篩選、排序、分頁 | `find(Transaction, {"user_id__in": users, "occurred_on__between": (a, b)}, order_by="-occurred_on", page=2, size=50)` |
| 只數筆數 | `find(Transaction, {"user_id": 3}, count=True)` 或 `count(...)` |
| 新增一筆／很多筆 | `save(Group, {...})`、`save(Transaction, [{...}, {...}])` |
| 改一筆／改很多筆 | `save(User, {"id": 3, "theme": "sky"})`、`save(Group, {"archived_at": now}, where={"id": 9})` |
| 有就改、沒有就新增 | `save(Budget, {"limit_amount": 8000}, where={...}, upsert=True)` |
| 刪除／軟刪除 | `remove(Transaction, {"id__in": ids, "user_id": me.id})`、`remove(Group, id=9, soft="archived_at")` |
| 回給前端 | `to_dict(tx, rename={"occurred_on": "date", "category_id": "cat"})`（id 轉字串、藏密碼雜湊） |

條件運算子：`__gte` `__gt` `__lte` `__lt` `__ne` `__in` `__notin` `__contains` `__icontains` `__startswith` `__endswith` `__isnull` `__between`，
還有 `{"or": [...]}`。欄位名字打錯直接丟 `ValueError` 講出是哪張表哪個欄位；**沒有條件的修改與刪除會被擋**（`allow_all=True` 才放行）。

每一支都收 `db=`：不傳就自己開交易、做完 commit；傳了就用你的、不 commit，交給外面決定（好幾步要一起成功時）。

### 路由守衛：`guards.py`

參考 MineMarket 的 `AuthDecorator.py`。擋下來回 401／403／404，路由裡的程式一行都不會跑：

| 守衛 | 擋什麼 |
|---|---|
| `@login_required` | 沒登入、token 壞掉、帳號不存在（401）；被停權（403） |
| `@guest_only` | 已經登入（400）。註冊用 |
| `@parent_required`／`@family_required` | 不是家長／還沒有家庭（403） |
| `@protect(family=False)` | 已經在家庭裡（409）。建立家庭用 |
| `@admin_required`／`@block_admin` | 不是平台管理員／是平台管理員（403）——管理員讀不到任何財務資料 |
| `Depends(own(Transaction, "tx_id"))` | 這一筆不是我的（403）、找不到（404）。回傳那一筆 |
| `Depends(in_group("gid", owner=True))` | 我不在這本帳裡、不是建立者（403）、帳本被移除（404） |
| `Depends(can_see_user("user_id"))` | 監管、同家庭家長、同帳本都不是（403） |
| `Depends(token_required())` | 重設密碼連結找不到、過期、用過（一律同一句 400） |

守衛會把 `me.family_id`、`me.family_role` 掛好，路由不用再查一次。
⚠️ 裝飾器寫在 `@router.xxx` 的**下面**。

### 設定：`.env`

`python -m app.cli init-env` 會從 `.env.example` 建出 `.env`。檔案依成員分段，**改自己那一段就好**；
機密（`JWT_SECRET`、`BREVO_API_KEY`、`MODEL_API_KEY`、`ADVICE_API_KEY`、`MAIL_FROM`）在 Render 後台填，**不可以 commit**。
程式裡一律 `from app.toolkit.config import settings`，不要自己讀 `os.environ`。

---

## 領域

| 領域 | 資料夾 | 路由 |
|---|---|---|
| 認證 | `app/routers/auth/` | 19 支 |
| 記帳 | `app/routers/ledger/` | 19 支 |
| 數字 | `app/routers/analytics/` | 11 支 |
| 家庭 | `app/routers/access/` | 21 支 |

路由屬於哪個領域寫在 `app/ownership.py`，`python -m app.ownership` 會印出各領域的完成度、檢查有沒有路由沒歸屬。

**最後一週的分工與時程**在 `../docs/04-最後一週分工.md`，每個人的任務檔在 `../docs/分工/`。

### 誰都不可以實作的路由

- `POST /api/auth/switch`
  **任何管理身分登入他人的帳號。家長不行，平台管理員也不行。**
  前端曾經有一顆「切換身分」的按鈕，已經連同這支路由一起拿掉，換成真正的登入／登出。
  這不只是安全問題，更是產品決定：監管的正當性建立在「看得到但碰不到」——
  能登入對方帳號的話，被監管者就無法信任自己的紀錄沒有被動過手腳。
  監管者要看對方的資料，走**唯讀的監管檢視**（帶 `userId` 查明細）。
  `backend/tests/test_consistency.py` 會擋下任何把它加回來的修改。

---

## 環境變數

完整說明寫在 `app/toolkit/config.py` 每一個欄位的 `description`，下面是摘要（✅ = 必填，沒填服務起不來）：

| 段落 | 變數 | 必填 | 說明 |
|---|---|---|---|
| 共用 | `APP_ENV` |  | 預設 `development`。development / production。production 時 db 不印 SQL、錯誤訊息不帶內部細節。 |
| 共用 | `DATABASE_URL` | ✅ | PostgreSQL 連線字串。格式：postgresql+psycopg://使用者:密碼@主機:埠號/資料庫名稱 |
| 共用 | `DB_ECHO` |  | 預設 `False`。True 會把送出的 SQL 印出來，除錯用。正式環境不要開。 |
| 共用 | `DB_POOL_SIZE` |  | 預設 `5`。連線池大小。Render 免費 PostgreSQL 同時連線數很少，不要開太大。SQLite 會忽略。 |
| 共用 | `ALLOWED_ORIGINS` |  | 預設 `http://localhost:5174`。允許哪些前端網域來打這個 API，逗號分隔。填錯前端會被瀏覽器的 CORS 擋住。 |
| 認證 | `JWT_SECRET` | ✅ | 簽 JWT 用的密鑰。這是整個系統最敏感的一個值——拿到它的人可以偽造任何人的登入權杖。 |
| 認證 | `JWT_ALGORITHM` |  | 預設 `HS256`。 |
| 認證 | `ACCESS_TOKEN_MINUTES` |  | 預設 `30`。access token 有效期（分鐘）。刻意設短：外洩時損害只持續這麼久，前端會自動續期。 |
| 認證 | `REFRESH_TOKEN_DAYS` |  | 預設 `14`。refresh token 有效期（天）。存在 sessions 表，可以撤銷。 |
| 認證 | `BREVO_API_KEY` |  | Brevo 的 API 金鑰（Brevo 後台 → SMTP & API → API keys），忘記密碼寄信用。**不可以 commit**。 |
| 認證 | `MAIL_FROM` |  | 寄件信箱。一定要先在 Brevo 的 Senders 驗證過，不然信會被拒絕。 |
| 認證 | `MAIL_FROM_NAME` |  | 預設 `家庭記帳`。收件人看到的寄件人名稱。 |
| 認證 | `APP_BASE_URL` |  | 預設 `https://fambudget-web.onrender.com`。前端網址。重設密碼信裡的連結會長成「這個網址/#/reset/token」。本機改成 http://localhost:5174。 |
| 認證 | `ADMIN_EMAILS` |  | 平台管理員的 email，逗號分隔。`python -m app.cli make-admin` 會把這些帳號設成平台管理員。 |
| 記帳 | `MODEL_PROVIDER` |  | 預設 `openai`。`anthropic`＝Claude（官方套件）；`openai`＝OpenAI 或任何 OpenAI 相容服務（含我們微調後放在 Hugging Face Space 的模型）。 |
| 記帳 | `MODEL_BASE_URL` |  | `openai` 才要填：`https://api.openai.com` 或 Space 的網址（不含 /v1）。Claude 留空。 |
| 記帳 | `MODEL_API_KEY` |  | 商業 API 的金鑰，或私有 Space 的 token。**不可以 commit**。 |
| 記帳 | `MODEL_NAME` |  | 預設 `qwen2.5-1.5b-fambudget`。用 Claude 而沒改（不是 claude- 開頭）時自動換成 `claude-opus-5-5`。寫進 nlp_parses.model_ver。 |
| 記帳 | `MODEL_EFFORT` |  | 預設 `low`。只有 Claude 用：思考深度。解析是抽欄位，low 最快。 |
| 記帳 | `MODEL_MAX_TOKENS` |  | 預設 `0`（用程式各處給的長度）。本機跑推理型模型（Ollama 的 deepseek-r1）會先想一大段，要調高，例如 `4096`。 |
| 記帳 | `MODEL_TIMEOUT_SECONDS` |  | 預設 `30.0`，商業 API 建議 `60`。一定要設——模型卡住時，沒有逾時的 API 會跟著一起卡死。 |
| 數字 | `ADVICE_PROVIDER`、`ADVICE_BASE_URL`、`ADVICE_API_KEY`、`ADVICE_MODEL_NAME` |  | 財務建議想用另一組模型時才填；每一個留空就沿用上面記帳那一組。`ADVICE_API_KEY` **不可以 commit**。 |
| 數字 | `ADVICE_EFFORT` |  | 預設 `medium`。只有 Claude 用：建議要寫成人話，比解析多想一點。 |
| 數字 | `SAVINGS_WARN_RATIO` |  | 預設 `0.8`。支出達可支配上限的幾成算「接近上限」。前端 data.js 的 savingsRule 要一致。 |
| 數字 | `SAVINGS_OVER_RATIO` |  | 預設 `1.0`。幾成算「超過」。 |
| 家庭 | `INVITE_TTL_DAYS` |  | 預設 `7`。邀請與邀請碼幾天後失效。產生時呼叫 family.expires_at(days=settings.invite_ttl_days)。 |

模型服務沒設定時（Claude 沒填金鑰、OpenAI 相容的沒填網址）`services/llm/client.py` 回 `None`：解析與建議的路由回 **503**，前端用規則頂著，畫面照常能用。三種填法（Claude／OpenAI／我們微調的模型）見 `docs/03-LLM實作規劃.md` 第 2 節，換來換去程式碼一行都不用改。

寄信用 **Brevo 的 HTTP API**，不是 SMTP——Render 免費方案擋掉了 25／465／587 埠，
用 smtplib 在本機會通、部署上去就永遠逾時。填好金鑰後先試寄一封給自己：

```bash
python -m app.toolkit.mailer --to 你的信箱@gmail.com
```

`.env` 已經寫進 `.gitignore`，**不會被 commit**。
Render 上的機密是在後台手動填的（`render.yaml` 裡標 `sync: false` 的那幾個）。

平台管理員不能自己註冊：先用一般方式註冊，再跑

```bash
python -m app.cli make-admin 那個人的信箱      # 或把信箱寫進 ADMIN_EMAILS 再跑 make-admin
```

---

## 資料庫結構變更（Alembic）

建表／升到最新（部署時 Render 與 Docker 都會在啟動前自動跑這一行）：

```bash
alembic upgrade head
alembic -x url=sqlite:///./dev.db upgrade head      # 臨時對別顆資料庫跑
```

改了 `models/` 底下的欄位之後（**三處一起改**：`frontend/js/data.js` 的 schema → `models/` → 遷移）：

```bash
alembic revision --autogenerate -m "what changed"   # 說明用英文，檔名才不會變成亂碼
alembic upgrade head
```

**產生出來的檔案一定要自己打開看過再套用。** autogenerate 不是萬能的，
改欄位型別、改名稱這類操作它常常會產生錯的東西（例如把「改名」
判斷成「刪掉舊的、加一個新的」，那會把資料全部弄丟）。

`tests/test_backend_core.py` 會檢查兩件事：models 跟 data.js 的 schema 逐欄一致、
遷移建出來的表跟 models 一模一樣。漏改一處就紅燈。

---

## 常見問題

**前端 console 出現 `blocked by CORS policy`**
→ `ALLOWED_ORIGINS` 沒填對。網址要完整（含 `https://`），結尾不要加斜線。

**啟動時噴 `ValidationError: database_url Field required`**
→ `.env` 沒建立，或是少了必填變數。先跑 `python -m app.cli init-env`，再 `check-config`。這是 `config.py` 刻意的設計：
**寧可在啟動時就失敗，也不要等使用者按下按鈕才發現設定是空的。**

**路由回 501**
→ 那支還沒實作（還標著 `@stub`）。回應裡就寫著路由與負責人，前端畫面也會講。這是正常的，不是 bug。

**畫面寫「後端出錯（HTTP 500）：系統發生錯誤…」**
→ 路由裡丟出了沒接住的例外。開發環境的訊息後面會附上例外的類型與內容，完整的追蹤在 uvicorn 的 log 裡；
正式環境（`APP_ENV=production`）只回一句話，不會把表名、SQL 送出去。規則類的錯誤請用 `toolkit/errors.py` 轉成 400／403／409。

**`alembic` 指令噴 `UnicodeDecodeError: 'cp950'`**
→ 有人在 `alembic.ini` 裡寫了中文。那個檔案只能有英文，說明寫在 `alembic/env.py`。

**本機的資料庫是什麼**
→ 跟正式環境一樣是 PostgreSQL 16，跑在 Docker 裡（專案最外層 `docker-compose.yml` 的 `db`）。
不用另外裝 PostgreSQL，只要裝 Docker Desktop、開發前先打開它，`python run.py` 會自己把資料庫開起來。
`pytest` 例外：用的是記憶體裡的 SQLite，每個測試一份、跑得快、不需要 Docker（`toolkit/db.py` 兩種都支援）。

**`python run.py` 說 Docker 沒有在執行**
→ 打開 Docker Desktop，等它顯示「Engine running」再跑一次。
Docker Desktop 一打開就跳 `Inference manager` 的錯誤：看最外層 README 的「Docker Desktop 一打開就跳錯誤」。

**想砍掉資料重來**
→ 在專案最外層 `python run.py --reset`（會 `docker compose down -v` 把資料庫清空重建）。

**改了程式但沒生效**
→ 確認啟動時有加 `--reload`。
