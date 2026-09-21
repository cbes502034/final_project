# 家庭記帳與財務控管系統

四人 × 一個月的期末專題。以家庭為單位的記帳系統，用自然語言降低輸入摩擦，
用月／年兩個時間準據做財務控管。

| | |
|---|---|
| **線上系統** | <https://fambudget-web.onrender.com> |
| **專題手冊** | <https://fambudget-web.onrender.com/docs/> |
| **FastAPI 說明書** | <https://fambudget-web.onrender.com/docs/fastapi.html> ← 沒學過 FastAPI 先讀這份 |
| **RESTful 說明書** | <https://fambudget-web.onrender.com/docs/restful.html> |
| **檔案系統說明書** | <https://fambudget-web.onrender.com/docs/files.html> |
| **API 瀏覽** | <https://fambudget-web.onrender.com/docs/api.html> |
| **前後端串接契約** | `docs/02-前後端串接契約.md` ← 動工前一定要看 |
| **模型設計** | <https://fambudget-web.onrender.com/docs/model.html> |

---

## 目錄結構

```
final_project/
├── frontend/              前端：純靜態，無框架、無建置步驟
│   ├── index.html           系統本體（單頁 + hash 路由）
│   ├── css/                 tokens.css 設計權杖 · app.css 元件 · themes.css 八套主題
│   ├── js/
│   │   ├── api.js     ★     唯一的資料入口：mock／http 兩個轉接器 ＋ 前端代勞 ＋ 錯誤指出是哪一支
│   │   ├── app.js           畫面繪製與互動
│   │   ├── data.js          資料表草案與固定清單（分類、主題、角色）。沒有假資料
│   │   ├── notify.js        通知鈴鐺
│   │   ├── errbox.js        錯誤匣：後端沒給出正確結果的每一支
│   │   └── stars.js         canvas 星空背景
│   └── docs/                說明文件（也是靜態頁）
│       ├── index.html       專題手冊
│       ├── guide.html       操作說明
│       ├── fastapi.html     FastAPI 說明書
│       ├── restful.html     RESTful 說明書
│       ├── files.html       檔案系統說明書
│       ├── api.html         API 瀏覽
│       └── model.html       記帳模型設計
│
├── backend/               後端：FastAPI
│   ├── app/
│   │   ├── main.py          入口，只負責組裝
│   │   ├── ownership.py ★   分工的單一事實來源，pytest 會檢查它
│   │   ├── guards.py    ★   路由守衛（@login_required、own()、in_group()…）
│   │   ├── cli.py           python -m app.cli：init-env · check-config · init-db · make-admin
│   │   ├── catalog.py       固定清單（角色 · 權限表 · 理財選項 · 系統分類），正本是 data.js
│   │   ├── toolkit/     ★   寫好的工具：config · db · crud · tokens · passwords · scope · family …
│   │   ├── models/          20 張表（SQLAlchemy），跟 data.js 的 schema 逐欄對齊
│   │   ├── schemas/         請求主體（Pydantic，一個檔案一個主人）
│   │   ├── routers/         70 支路由，一組一個檔案；還沒做的回 501
│   │   └── services/
│   │       ├── llm/         client 已完成 · parse 成員2 · advice 成員3
│   │       ├── permission.py    成員4
│   │       ├── analytics.py     成員3
│   │       └── evaluation.py    評測指標
│   ├── alembic/             資料庫遷移（第一版 = 20 張表）
│   ├── tests/               含 routes/：每一支路由的驗收測試（說明裡的寫法也跑一遍）
│   ├── tools/               文件從程式產生：sync_spec.py · sync_schema.py · sync_mindmap.py
│   ├── .env.example         設定範本，依成員分段
│   ├── requirements.txt
│   ├── Dockerfile
│   └── README.md          ← 後端的詳細說明在這
│
├── docs/                  規格文件（Markdown / SVG）
├── run.py                 ★ 一鍵啟動：裝套件、建 .env、建表、同時起前後端
├── docker-compose.yml     本機用 PostgreSQL 跑整套
└── render.yaml            部署設定
```

**前端與後端完全分離**：前端是純靜態檔案，直接走 CDN；
後端是獨立的 Python 服務。兩者只透過 HTTP JSON 溝通，可以各自部署、各自改版。

---

## 本機開發

### 一鍵跑起來 ★

在**專案最外層**（跟 `backend/`、`frontend/` 同一層）打：

```bash
python run.py
```

第一次會自己做完這些：裝套件 → 建 `backend/.env`（含 JWT_SECRET）→ 建表 → 放入系統預設分類 →
同時起前端與後端。需要的只有 **Python 3.10 以上**，資料庫用 SQLite（`backend/dev.db`），什麼都不用裝。

| 服務 | 網址 |
|---|---|
| 前端 | <http://localhost:5174/?api=http://localhost:8000> |
| 後端 | <http://localhost:8000> |
| API 文件（可以直接試打） | <http://localhost:8000/docs> |

其他用法：

```bash
python run.py --front-only     # 只跑前端（mock 模式，不需要後端）
python run.py --reset          # 本機資料庫砍掉重建
python run.py --port 5555      # 換前端的埠號（後端用 --api-port）
```

⚠️ 前端不要用 VS Code 的 Live Server，也不要直接點開 `index.html`：
那樣後端的 CORS 會擋住，而且 `file://` 不算 localhost。一律用 `run.py` 起的 5174。

### 分開跑（想自己控制的時候）

```bash
python run.py --front-only                       # 前端

cd backend                                       # 後端
pip install -r requirements.txt
python -m app.cli init-env        # 建出 .env（順便產生 JWT_SECRET）
python -m app.cli check-config    # 看哪些還沒填、沒填會怎樣
alembic upgrade head              # 建表
python -m app.cli init-db         # 放入系統預設分類
uvicorn app.main:app --reload
```

### 看自己寫進去的資料

```bash
cd backend
python -m app.cli db                                   # 每張表各幾筆
python -m app.cli db "SELECT id, email FROM users"     # 只能查，不能改
```

### 用 PostgreSQL（跟正式環境一樣）

```bash
docker compose up
```

起一顆 PostgreSQL 16 ＋ 後端 ＋ 前端。本機開發不需要這一條，
`run.py` 的 SQLite 已經把外鍵檢查打開，行為一致。

---

## 前端怎麼切換到真後端

**本機開發用網址切就好，不要動任何檔案**（`frontend/index.html` 會被 commit，
有人不小心把 localhost 推上去，線上整站就連不到後端）：

```
http://localhost:5174/?api=http://localhost:8000    接自己的後端
http://localhost:5174/?api=                         切回 mock
```

切過一次就記在那台瀏覽器裡，之後開 <http://localhost:5174> 就好。
⚠️ 這個開關**只有頁面開在 localhost 時才生效** —— 線上網址吃這個參數的話，
別人寄一個 `?api=https://壞人的伺服器` 的連結過來就能把權杖騙走。

正式環境（Render 上的前端要連哪個後端）改 `frontend/index.html` 這一行：

```html
<meta name="api-base" content="https://fambudget-backend.onrender.com">
```

留空 = mock 模式（跑在瀏覽器裡的後端）。填上網址 = 全部改用 `fetch` 打真後端。

`frontend/js/api.js` 裡 `mock` 與 `http` 兩個轉接器的**簽章完全一致**，所以可以**一支一支路由慢慢接**：
後端還沒做的回 501，畫面會直接講「是哪一支、哪條路由、誰負責」，其他頁照常能用；
名稱、結餘、比例這些前端補得出來，後端可以不帶。這是四個人能平行動工的關鍵。
細節在 `docs/02-前後端串接契約.md` 的「已經定案的五件事」。

⚠️ 千萬不要填 `fambudget-api.onrender.com`——那個子網域是別人的服務。

---

## 部署

部署在 Render，設定全部寫在 `render.yaml`（Blueprint），推上 main 就會自動部署。

| 服務 | 型態 | 來源 | 說明 |
|---|---|---|---|
| `fambudget-web` | 靜態站台 | `./frontend` | 走 CDN。前端是 hash 路由，不需要 rewrite 規則 |
| `fambudget-backend` | Python 服務 | `./backend` | 先 `alembic upgrade head` 再 `uvicorn app.main:app`，健康檢查打 `/healthz` |
| `fambudget-db` | PostgreSQL | — | 免費方案 |

### 機密要在 Render 後台手動填

`render.yaml` 裡標了 `sync: false` 的變數**不會從 repo 同步**，
必須到 Render 後台的 Environment 頁面手動輸入：

| 變數 | 說明 |
|---|---|
| `JWT_SECRET` | 簽 JWT 用的密鑰。拿到它的人可以偽造任何人的登入權杖 |
| `MODEL_BASE_URL` | 我們自己微調的模型服務網址 |
| `MODEL_API_KEY` | 模型服務要驗證時的 token（公開的 Space 留空） |
| `BREVO_API_KEY` | 忘記密碼的寄信服務金鑰（Brevo 後台 → SMTP & API → API keys） |
| `MAIL_FROM` | 寄件信箱，要先在 Brevo 的 Senders 驗證過 |

**這些絕對不可以寫進 repo。** 一旦 commit 進 git 歷史，
就算之後刪掉也救不回來——必須重新產生一組。

### ⚠️ 這份 render.yaml 還沒生效，要先建立 Blueprint

目前線上那個站台是**用 Render 後台手動建立的**，跟這份 `render.yaml` 無關——
證據是裡面宣告的 `fambudget-backend` 與 `fambudget-db` **根本不存在**。

要讓它真的生效（後端和資料庫才會被自動建立），步驟如下。
**做完會換到新網址**，舊的 `llm-capstone-top20.onrender.com` 會停留在最後一次成功的建置。

1. **Render 後台 → New → Blueprint**
2. 選 `cbes502034/final_project` 這個 repo，分支 `main`
3. Render 會讀到這份 `render.yaml`，列出三個資源，確認一下：

   | 名稱 | 型態 | 來源 |
   |---|---|---|
   | `fambudget-web` | Static Site | `./frontend` |
   | `fambudget-backend` | Web Service (Python) | `./backend` |
   | `fambudget-db` | PostgreSQL | — |

4. 它會問你標 `sync: false` 的變數，**這些只有你填得了**：

   | 變數 | 填什麼 |
   |---|---|
   | `JWT_SECRET` | 隨機長字串。產生方式：`python -c "import secrets;print(secrets.token_urlsafe(48))"` |
   | `MODEL_BASE_URL` | **先留空**。模型還沒訓練完，留空時解析與建議的路由回 503，前端用規則頂著，畫面照常能用 |
   | `MODEL_API_KEY` | 公開的 Hugging Face Space 留空 |
   | `BREVO_API_KEY` | Brevo 的 API 金鑰。⚠️ 不能改用 Gmail SMTP：Render 免費方案擋掉了 SMTP 埠 |
   | `MAIL_FROM` | 在 Brevo 驗證過的寄件信箱。填好後本機先試寄：`python -m app.toolkit.mailer --to 你的信箱` |

5. Apply，等三個資源都變成 Live

建好之後的網址：

| | |
|---|---|
| 前端 | `https://fambudget-web.onrender.com` |
| 後端 | `https://fambudget-backend.onrender.com` |
| API 文件 | `https://fambudget-backend.onrender.com/docs` |

6. **確認新站台正常之後**，再回後台把舊的 `llm-capstone-top20` 服務刪掉。
   先確認再刪，不要反過來。

> **為什麼 render.yaml 裡沒有 rewrite 規則？**
> 舊設定有一條 `/*` → `/index.html`。我們的前端走 **hash 路由**（`#/entry`），
> 井號後面的東西根本不會送到伺服器，所以那條規則用不到；
> 而且它有機會把 `/docs/*.html` 這些真實檔案一起吃掉。已經移除。

### 靜態站台的資產版號

`frontend/index.html` 裡的 `?v=NN` 是給瀏覽器看的快取版號。
**改了 CSS 或 JS 一定要把這個數字往上加**，否則使用者的瀏覽器
會繼續用舊的快取檔案，你會以為部署沒生效。

---

## 分工

分工的**單一事實來源是 `backend/app/ownership.py`**，不是這份文件。
那個檔案是程式讀得到的，而且 `pytest` 會檢查它有沒有跟程式碼走散——
有人新增路由卻沒認領、或兩個人宣告同一支，測試就會紅燈。

```bash
cd backend
python -m app.ownership      # 印出分工表並檢查一致性
```

### 四個領域

| 成員 | 領域 | 分支 | 路由 | 獨佔檔案 | 共用元件（要最先完成） |
|---|---|---|---|---|---|
| **成員1** | **認證** | `m1-auth` | 19 支 | `routers/auth.py`<br>`routers/admin.py`<br>`models/user.py`<br>`schemas/auth.py` | `services/llm/client.py`<br>`guards.py`<br>`cli.py`<br>`routers/_stub.py`<br>`models/_types.py` |
| **成員2** | **記帳** | `m2-ledger` | 19 支 | `routers/transactions.py`<br>`routers/nlp.py`<br>`routers/categories.py`<br>`routers/groups.py`<br>`models/category.py`<br>`models/group.py`<br>`schemas/group.py`<br>`services/evaluation.py`<br>`models/transaction.py`<br>`models/nlp.py`<br>`schemas/transaction.py`<br>`schemas/nlp.py`<br>`services/llm/parse.py` | — |
| **成員3** | **數字** | `m3-analytics` | 11 支 | `routers/stats.py`<br>`routers/alerts.py`<br>`models/alert.py`<br>`routers/budgets.py`<br>`routers/advices.py`<br>`models/budget.py`<br>`models/advice.py`<br>`schemas/stats.py`<br>`schemas/advice.py`<br>`services/llm/advice.py` | `services/analytics.py` |
| **成員4** | **家庭** | `m4-access` | 21 支 | `routers/family.py`<br>`routers/notifications.py`<br>`models/family.py`<br>`models/guardianship.py`<br>`models/notification.py`<br>`models/audit.py`<br>`schemas/family.py` | `services/permission.py` |

### 切分原則

1. **一個領域＝一個完整的概念**，不是一堆零散的路由湊數
2. **一個檔案剛好一個主人**，四個人不會改到同一個檔案 → git 幾乎不衝突
3. **會擋住別人的東西要盡量小**（`guards.py`、`toolkit/`、`permission.py`），而且這一版已經先做好了
4. **每個人都要有一份 LLM 工作** —— 這是任務的硬性要求

### 各領域的邊界

#### 成員1 · 認證　`m1-auth`

負責「你是誰」。
屬於他的：註冊登入登出、密碼與忘記密碼、JWT、工作階段、個人資料與理財習慣，以及平台管理員的停權（停權擋的是登入，所以歸認證）。
地基（設定 `toolkit/config.py`、資料庫連線 `toolkit/db.py`、增刪改查 `toolkit/crud.py`、路由守衛 `guards.py`、模型呼叫層 `services/llm/client.py`、20 張表與 Alembic）**已經做好了**，他負責維護。
不屬於他的：家庭角色與監管關係（那是成員4）。users 表存的是登入身分，family_members 表才是家庭角色，兩者刻意分開。

**LLM 工作**：共用的模型呼叫層：逾時、重試、把模型回傳的 JSON 交給 Pydantic 驗證。成員2 和成員3 都會呼叫它，所以第 1 週要先做出來。

**路由（19 支）**

```
POST   /api/auth/register
POST   /api/auth/login
POST   /api/auth/refresh
POST   /api/auth/logout
POST   /api/auth/logout-all
GET    /api/auth/me
PATCH  /api/auth/password
POST   /api/auth/password-reset
POST   /api/auth/password-reset/confirm
GET    /api/auth/me/finance
PUT    /api/auth/me/finance
POST   /api/auth/verify-password
GET    /api/auth/sessions
PATCH  /api/auth/me
PUT    /api/auth/me/avatar
DELETE /api/auth/me/avatar
GET    /api/admin/users
POST   /api/admin/users/{user_id}/suspend
DELETE /api/admin/users/{user_id}/suspend
```

#### 成員2 · 記帳　`m2-ledger`

負責「記一筆帳」這個動作，從文字進來到寫進資料庫。★ 這是整個系統的核心。
屬於他的：明細的增刪改查、段落解析、單句解析、確認後寫入、nlp_parses 的寫入。
帳本（開、改、封存、結算、成員）與分類也在這裡：帳本是「這筆算在哪」的容器，分類是記帳時要選的欄位，統計只是拿它分組。
不屬於他的：統計加總（那是成員3，前端和這裡都不做任何加總）。

**LLM 工作**：段落切分策略、欄位抽取 prompt、few-shot 範例的挑選、低信心的判準。切分比抽欄位更難，而且切錯比抽錯更難發現。

**路由（19 支）**

```
GET    /api/transactions
POST   /api/transactions
PATCH  /api/transactions/{tx_id}
DELETE /api/transactions/{tx_id}
DELETE /api/transactions
POST   /api/nlp/parse
POST   /api/nlp/parse-batch
POST   /api/nlp/confirm
POST   /api/nlp/confirm-batch
GET    /api/categories
POST   /api/categories
GET    /api/groups
POST   /api/groups
PATCH  /api/groups/{gid}
DELETE /api/groups/{gid}
POST   /api/groups/{gid}/members
DELETE /api/groups/{gid}/members/{user_id}
POST   /api/groups/{gid}/settle
PATCH  /api/groups/{gid}/notify
```

#### 成員3 · 數字　`m3-analytics`

負責所有「算出來的東西」，以及把那些數字講成人話。
屬於他的：月年統計、預算、每月存款目標、階段性提醒的門檻、財務建議。
**整個系統只有這裡加總錢** —— 模型不算，前端只做衍生（結餘、比例、預算百分比）。
不屬於他的：明細的寫入（那是成員2）；決定要算哪些人（那是成員4 的 permission）。

**LLM 工作**：財務建議的 prompt 與邊界規則。順序不能顛倒：先用 analytics 算好數字，再餵給模型敘述，模型不做任何算術。

**路由（11 支）**

```
GET    /api/summary
GET    /api/budgets
PUT    /api/budgets
PUT    /api/savings-goal
GET    /api/savings-goals
GET    /api/alerts
POST   /api/alerts
PATCH  /api/alerts/{aid}
DELETE /api/alerts/{aid}
GET    /api/advices
POST   /api/advices/generate
```

#### 成員4 · 家庭　`m4-access`

負責「誰在這個家庭裡」以及「誰看得到誰的資料」，另外扛模型評測。
屬於他的：家庭（建立、解散）、成員角色、家庭綁定（邀請碼與用帳號邀請）、監管關係、權限計算、通知、零用金、稽核紀錄、評測。
不屬於他的：登入本身（那是成員1）。成員1 回答「你是誰」，成員4 回答「你能看到什麼」。

**LLM 工作**：模型評測：建立人工標註的留出集、跑零樣本 vs few-shot 對照、算一次輸入完全正確率與分類 Macro-F1。**留出集必須 100% 人工標註**，否則量到的是「多像那個老師」而不是「多正確」。

**路由（21 支）**

```
GET    /api/family
POST   /api/family
DELETE /api/family
POST   /api/family/invite
POST   /api/family/join
GET    /api/family/lookup
GET    /api/family/invites
POST   /api/family/invites
POST   /api/family/invites/{invite_id}/accept
DELETE /api/family/invites/{invite_id}
PATCH  /api/family/members/{user_id}
DELETE /api/family/members/{user_id}
GET    /api/guardianships
POST   /api/guardianships
DELETE /api/guardianships/{gid}
GET    /api/notifications
PATCH  /api/notifications/{nid}
PATCH  /api/notifications
GET    /api/allowances
PUT    /api/allowance
GET    /api/audit
```


### 分支規則

每個人只在自己的分支上動自己清單裡的檔案。

```bash
git switch -c m2-ledger      # 換成你自己的分支名稱
```

**要改別人的檔案，先在群組講一聲。** 下面這幾個檔案沒有單一主人，
動之前一樣要先講：

- `backend/app/main.py`
- `backend/app/ownership.py`
- `backend/app/models/__init__.py`
- `backend/app/schemas/__init__.py`
- `backend/app/routers/__init__.py`
- `backend/app/services/__init__.py`
- `backend/app/services/llm/__init__.py`

### 第 1 週的相依順序

原本會擋住別人的地基**已經做好了**，四個人第一天就能開工：

```
✅ 路由守衛         app/guards.py（@login_required、own()、in_group()、can_see_user()）
✅ 資料庫與增刪改查  app/toolkit/db.py、crud.py、models/（20 張表）、alembic/
✅ 可見範圍         app/guards.py 的 visible_scope()、services/permission.py 的 visible()
✅ 模型呼叫層       app/services/llm/client.py
```

還剩一件跨模組的事**要最優先**：

```
成員2  分類體系（GET /api/categories）  ← 成員2 寫 prompt、成員4 評測、成員3 統計分組都要用
```

### 六週排程

總長六週 = **實作四週 + 測試不到一週 + 報告簡報**。

⚠️ **後端線與模型線並行，不是接力。** 標註資料不用寫程式，第 1 週就能開始。

| 週 | 主題 | 後端線 | 模型線 |
|---|---|---|---|
| **1** | 地基與標註同時開始 | 地基已經做好（toolkit、guards、models）：每個人拿掉前幾支的 @stub、打得通 | 標註 150 筆（不用寫程式，每人每天 1 小時） |
| **2** | 前後端串通 | 後端完成，**關掉 mock 畫面還能動** | 標註到 300 筆、Colab 環境先跑通一次 |
| **3** | 基準線與第一輪微調 | 補洞、修 bug、**四個人開始自己用這個系統** | few-shot 基準線 ＋ 第一輪 QLoRA |
| **4** | 第二輪微調 | 功能凍結 | 第二輪微調（用第 3 週收集到的真實修正）＋ 接回系統 |
| **5** | 測試 | 全系統測試、四個角色各走一遍、權限反向測試 | 評測數字定稿 |
| **6** | 報告與緩衝 | 報告、簡報 | 對照表、圖表 |

**三條硬線**

- ⚠️ 硬檢查點：沒串通的話第 3 週不要碰微調，先把串接做完
- ⚠️ 硬切線：週末沒有第一輪的數字，第 4 週就放棄第二輪，用 few-shot 收尾
- ⚠️ 最後兩天不准改模型，留給「接回去 + 確認沒壞」

**測試不能留到第 5 週。** 每支路由寫完當下就用 `/docs` 試打，不要累積。
第 5 週要走過的清單：

1. 三個層級各走一遍：平台 master / 家長 parent / 子女 child
2. 權限的**反向測試** —— 子女切不到「全家」、直接打全家的 summary 也要被擋，這比正向測試重要
3. 段落記帳的邊界：缺欄位、低信心、切分錯誤、空輸入、超長輸入
4. 金額邊界：0、負數、小數、很大的數字
5. 年度統計的「未完整」標示有沒有出現
6. 帳號不存在與密碼錯誤，回的訊息要一樣
7. 批次寫入寫到一半失敗，要全部不寫（不可以留下半筆）

### 找到自己要做的事

```bash
cd backend && python -m app.ownership
```

會印出每個人負責哪幾支、已經做完幾支、還差哪幾支。
`app/ownership.py` 是分工的**唯一事實來源**——路由歸屬、分支名稱、
共用檔案、時程，全部在那一個檔案裡，`pytest` 會拿它去對文件。

**70 支路由已經全部掛好了**（`app/routers/`）：守衛、請求主體、說明字串都寫好，函式裡只有
`raise not_ready(...)`（回 501）。做一支 = 換成真的實作、拿掉 `@stub`。

**先讀那一支的說明字串**——它就是那一支的規格書，十一個段落：這支做什麼、前端怎麼打、誰能打、
請求、成功回應、錯誤回應、會用到的資料表、每一步用的工具與資料庫方法、寫法步驟、
**完整寫法**（可以直接貼上去的整段程式：import ＋ 整個函式）、做完怎麼確認。
照著改完，跑 `pytest tests/routes -k "函式名 and 你的"` 就知道對不對
（同一組測試也會拿說明裡的程式跑一遍，所以說明不會跟實作走散）。

增刪改查用 `app/toolkit/crud.py`、身分與權限用 `app/guards.py`、規則用 `app/toolkit/` 對應的模組——
都是測好的工具，直接用，不用重寫。每支路由的輸入輸出也寫在 `docs/02-前後端串接契約.md`。

### 誰都不可以實作的路由

- `POST /api/auth/switch`
  **任何管理身分登入他人的帳號。家長不行，平台管理員也不行。**
  前端曾經有一顆「切換身分」的按鈕，已經連同這支路由一起拿掉，換成真正的登入／登出。
  這不只是安全問題，更是產品決定：監管的正當性建立在「看得到但碰不到」——
  能登入對方帳號的話，被監管者就無法信任自己的紀錄沒有被動過手腳。
  監管者要看對方的資料，走**唯讀的監管檢視**（帶 `userId` 查明細）。
  `backend/tests/test_consistency.py` 會擋下任何把它加回來的修改。
