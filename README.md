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
| **LLM 實作規劃** | `docs/03-LLM實作規劃.md` ← 模型線的每一步、誰做、怎麼算過關 |

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
│   │   ├── routers/         70 支路由，**一個領域一個資料夾**；還沒做的回 501
│   │   │   ├── auth/        認證（登入那幾支已經做好）　← 每個資料夾裡都有 README.md
│   │   │   ├── ledger/      記帳
│   │   │   ├── analytics/   數字
│   │   │   └── access/      家庭
│   │   └── services/
│   │       ├── llm/         client 已完成 · parse 記帳 · advice 數字
│   │       ├── permission.py    家庭
│   │       ├── analytics.py     數字
│   │       └── evaluation.py    評測指標
│   ├── alembic/             資料庫遷移（第一版 = 20 張表）
│   ├── tests/               含 routes/：每一支路由的驗收測試（說明裡的寫法也跑一遍）
│   ├── tools/               文件從程式產生：sync_spec.py · sync_schema.py · sync_mindmap.py · sync_devguide.py
│   ├── .env.example         設定範本，依成員分段
│   ├── requirements.txt
│   ├── Dockerfile
│   └── README.md          ← 後端的詳細說明在這
│
├── docs/                  規格文件（Markdown / SVG）
├── run.py                 ★ 一鍵啟動：裝套件、建 .env、建表、同時起前後端
├── docker-compose.yml     本機的 PostgreSQL（db）；run.py 會自己開
└── render.yaml            部署設定
```

**前端與後端完全分離**：前端是純靜態檔案，直接走 CDN；
後端是獨立的 Python 服務。兩者只透過 HTTP JSON 溝通，可以各自部署、各自改版。

---

## 本機開發

### 一鍵跑起來 ★

需要先裝好兩樣東西：

| | |
|---|---|
| **Python 3.10 以上** | <https://www.python.org/downloads/>，安裝時勾 Add python.exe to PATH |
| **Docker Desktop** | <https://www.docker.com/products/docker-desktop/>。本機的資料庫跟正式環境一樣是 **PostgreSQL**，跑在 Docker 裡。**每次開發前先把 Docker Desktop 打開** |

然後在**專案最外層**（跟 `backend/`、`frontend/` 同一層）打：

```bash
python run.py
```

第一次會自己做完這些：裝套件 → 建 `backend/.env`（含 JWT_SECRET）→ 用 Docker 開 PostgreSQL →
建表 → 放入系統預設分類與開發用帳號 → 同時起前端與後端。

| 服務 | 網址 |
|---|---|
| 前端 | <http://localhost:5174/?api=http://localhost:8000> |
| 後端 | <http://localhost:8000> |
| API 文件（可以直接試打） | <http://localhost:8000/docs> |

**開發用帳號**（`run.py` 會自動建好，密碼一律 `abcd1234`）：

| 帳號 | 誰用 |
|---|---|
| `auth@fambudget.tw` | 認證 |
| `ledger@fambudget.tw` | 記帳 |
| `analytics@fambudget.tw` | 數字 |
| `access@fambudget.tw` | 家庭 |
| `admin@fambudget.tw` | 平台管理員 |

密碼改壞了就 `cd backend && python -m app.cli seed-team` 重設。
⚠️ 只在自己的電腦上：`APP_ENV=production` 時那個指令會直接拒絕。

其他用法：

```bash
python run.py --front-only     # 只跑前端（mock 模式，不需要後端，也不需要 Docker）
python run.py --reset          # 本機資料庫砍掉重建（docker compose down -v）
python run.py --port 5555      # 換前端的埠號（後端用 --api-port）
```

⚠️ 前端不要用 VS Code 的 Live Server，也不要直接點開 `index.html`：
那樣後端的 CORS 會擋住，而且 `file://` 不算 localhost。一律用 `run.py` 起的 5174。

關掉 `run.py`（Ctrl+C）不會關掉 PostgreSQL，資料也都還在，下次開很快。要關它：`docker compose stop db`。

**資料庫會自動建好嗎？** 會，只要 Docker Desktop 是打開的：

| 你的狀況 | `python run.py` 會怎麼做 |
|---|---|
| **第一次**，Docker 開著 | 下載 PostgreSQL → 建好資料庫（容器 `fambudget-db-1`）→ 建資料表 → 放入預設分類與開發帳號。大約 1～2 分鐘，要有網路 |
| **之後每次**，Docker 開著 | 沿用同一顆資料庫，**不會重建**，上次的資料都還在。十幾秒就起來 |
| 裝了 Docker，**但沒打開** | 停在第 3 步，提醒你先打開 Docker Desktop |
| **沒裝 Docker** | 停在第 3 步，給你 Docker Desktop 的下載網址 |
| **以前跑過 `run.py`**（`backend/.env` 還寫著舊的 SQLite） | 自動換成 PostgreSQL 並印出說明，之後就需要 Docker。舊資料留在 `backend/dev.db`，不會再用到 |

每個人的資料庫只在自己的電腦上，跟其他組員、跟線上網站都無關。

**開發帳號每次都一樣**：每次 `python run.py` 都會把那五個帳號重設回原樣（密碼、名字、主題、
平台管理員身分、停權狀態），所以測「改密碼」「停權」時改到它們，下次啟動就會恢復。
它們記的帳、家庭、帳本不會被動到。

### 分開跑（想自己控制的時候）

```bash
python run.py --front-only                       # 前端

docker compose up -d --wait db                   # 資料庫（PostgreSQL）
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
python -m app.cli db transactions                      # 那張表最新的 10 筆
python -m app.cli db "SELECT id, email FROM users"     # 自己寫查詢（只能查，不能改）
```

### 資料庫：本機跟正式環境都是 PostgreSQL

| | 用什麼 |
|---|---|
| 本機開發 | PostgreSQL 16，Docker 裡的 `db`（`docker-compose.yml`），`run.py` 會自己開 |
| 正式環境（Render） | PostgreSQL，`render.yaml` 自動接上 |
| `pytest` | 記憶體裡的 SQLite：每個測試一份、跑得快、不需要 Docker |

本機跟線上用同一種資料庫，本機寫得對，部署上去就一樣對。
（70 支照說明字串做好的參考後端，接 PostgreSQL 跑過 70 支路由的完整掃描，0 個問題。）

⚠️ 不要直接打 `docker compose up`（不加 `db`）：那會連同 compose 裡的後端、前端一起起來，
跟 `run.py` 搶 8000 與 5174 埠。

### Docker Desktop 一打開就跳「An unexpected error occurred」

錯誤訊息裡有 `initializing Inference manager` 或 `dockerInference` 的話，是 Docker 內建的 AI 功能
（Docker AI／Model Runner）在這台電腦上建不了它要用的通訊檔。我們的專案用不到這個功能，把它關掉就好：

1. 按 **Quit** 關掉 Docker Desktop（**不要**按 Reset to factory defaults，那會清掉所有 Docker 資料）
2. 用記事本打開 `%APPDATA%\Docker\settings-store.json`
3. 把 `"EnableDockerAI": true` 改成 `"EnableDockerAI": false`，存檔
4. 把 `%LOCALAPPDATA%\Docker\run` 這個資料夾改名（例如 `run.old`），Docker 會自己建新的
5. 重新打開 Docker Desktop

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

## 領域與分工

| 領域 | 資料夾 | 路由 |
|---|---|---|
| 認證 | `backend/app/routers/auth/` | 19 支 |
| 記帳 | `backend/app/routers/ledger/` | 19 支 |
| 數字 | `backend/app/routers/analytics/` | 11 支 |
| 家庭 | `backend/app/routers/access/` | 21 支 |

路由屬於哪個領域，寫在 `backend/app/ownership.py`（`python -m app.ownership` 會印出各領域的完成度）。

**最後一週的分工與時程**在 `docs/04-最後一週分工.md`，每個人的任務檔在 `docs/分工/`。

### 誰都不可以實作的路由

- `POST /api/auth/switch`
  **任何管理身分登入他人的帳號。家長不行，平台管理員也不行。**
  前端曾經有一顆「切換身分」的按鈕，已經連同這支路由一起拿掉，換成真正的登入／登出。
  這不只是安全問題，更是產品決定：監管的正當性建立在「看得到但碰不到」——
  能登入對方帳號的話，被監管者就無法信任自己的紀錄沒有被動過手腳。
  監管者要看對方的資料，走**唯讀的監管檢視**（帶 `userId` 查明細）。
  `backend/tests/test_consistency.py` 會擋下任何把它加回來的修改。
