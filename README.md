# 家庭記帳與財務控管系統

四人 × 一個月的期末專題。以家庭為單位的記帳系統，用自然語言降低輸入摩擦，
用月／年兩個時間準據做財務控管。

| | |
|---|---|
| **線上系統** | <https://fambudget-web.onrender.com> |
| **專題手冊** | <https://fambudget-web.onrender.com/docs/> |
| **FastAPI 說明書** | <https://fambudget-web.onrender.com/docs/fastapi.html> ← 沒學過 FastAPI 先讀這份 |
| **RESTful 說明書** | <https://fambudget-web.onrender.com/docs/restful.html> |
| **API 瀏覽** | <https://fambudget-web.onrender.com/docs/api.html> |
| **前後端串接契約** | `docs/02-前後端串接契約.md` ← 動工前一定要看 |
| **模型設計** | <https://fambudget-web.onrender.com/docs/model.html> |

---

## 目錄結構

```
final_project/
├── frontend/              前端：純靜態，無框架、無建置步驟
│   ├── index.html           系統本體（單頁 + hash 路由）
│   ├── css/                 tokens.css 設計權杖 · app.css 元件
│   ├── js/
│   │   ├── api.js     ★     唯一的資料入口，mock / http 兩個轉接器
│   │   ├── app.js           畫面繪製與互動
│   │   ├── data.js          示範資料（mock 模式用）
│   │   └── stars.js         canvas 星空背景
│   └── docs/                說明文件（也是靜態頁）
│       ├── index.html       專題手冊
│       ├── fastapi.html     FastAPI 說明書
│       ├── api.html         API 瀏覽
│       └── model.html       記帳模型設計
│
├── backend/               後端：FastAPI
│   ├── app/
│   │   ├── main.py          入口，只負責組裝
│   │   ├── ownership.py ★   分工的單一事實來源，pytest 會檢查它
│   │   ├── core/            設定 · 資料庫 · 認證 · 依賴注入
│   │   ├── models/          SQLAlchemy 資料表（一個檔案一個主人）
│   │   ├── schemas/         Pydantic 請求／回應（一個檔案一個主人）
│   │   ├── routers/         路由，一組一個檔案
│   │   └── services/
│   │       ├── llm/         client 成員1 · parse 成員2 · advice 成員3
│   │       ├── permission.py    成員4
│   │       ├── analytics.py     成員3
│   │       └── evaluation.py    成員4
│   ├── tests/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── README.md          ← 後端的詳細說明在這
│
├── docs/                  規格文件（Markdown / SVG）
├── docker-compose.yml     本機一鍵起整套
└── render.yaml            部署設定
```

**前端與後端完全分離**：前端是純靜態檔案，直接走 CDN；
後端是獨立的 Python 服務。兩者只透過 HTTP JSON 溝通，可以各自部署、各自改版。

---

## 本機開發

### 只跑前端（不需要後端也能完整展示）

```bash
python -m http.server 5174 --directory frontend
```

打開 <http://localhost:5174>。前端預設跑在 **mock 模式**，
資料來自 `frontend/js/data.js`，所有功能都能操作。

### 只跑後端

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

打開 <http://localhost:8000/docs> 就是可以直接試打的 API 文件。

### 一鍵起整套（資料庫 + 後端 + 前端）

```bash
docker compose up
```

| 服務 | 網址 |
|---|---|
| 前端 | <http://localhost:5174> |
| 後端 | <http://localhost:8000> |
| API 文件 | <http://localhost:8000/docs> |
| PostgreSQL | `localhost:5432` |

---

## 前端怎麼切換到真後端

改 `frontend/index.html` 這一行就好：

```html
<meta name="api-base" content="https://fambudget-backend.onrender.com">
```

留空 = mock 模式（讀 `data.js`）。填上網址 = 改用 `fetch` 打真後端。

`frontend/js/api.js` 裡 `mock` 與 `http` 兩個轉接器的**簽章完全一致**，
所以可以**一支一支路由慢慢接** —— 後端做好哪支就改哪支，不必等全部完成。
這是四個人能平行動工的關鍵。

---

## 部署

部署在 Render，設定全部寫在 `render.yaml`（Blueprint），推上 main 就會自動部署。

| 服務 | 型態 | 來源 | 說明 |
|---|---|---|---|
| `fambudget-web` | 靜態站台 | `./frontend` | 走 CDN。前端是 hash 路由，不需要 rewrite 規則 |
| `fambudget-backend` | Python 服務 | `./backend` | `uvicorn app.main:app`，健康檢查打 `/healthz` |
| `fambudget-db` | PostgreSQL | — | 免費方案 |

### 兩個機密要在 Render 後台手動填

`render.yaml` 裡標了 `sync: false` 的兩個變數**不會從 repo 同步**，
必須到 Render 後台的 Environment 頁面手動輸入：

| 變數 | 說明 |
|---|---|
| `JWT_SECRET` | 簽 JWT 用的密鑰。拿到它的人可以偽造任何人的登入權杖 |
| `MODEL_BASE_URL` | 我們自己微調的模型服務網址 |

**這兩個絕對不可以寫進 repo。** 一旦 commit 進 git 歷史，
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

4. 它會問你兩個標 `sync: false` 的變數，**這兩個只有你填得了**：

   | 變數 | 填什麼 |
   |---|---|
   | `JWT_SECRET` | 隨機長字串。產生方式：`python -c "import secrets;print(secrets.token_urlsafe(48))"` |
   | `MODEL_BASE_URL` | **先留空**。模型還沒訓練完，留空時後端會回傳形狀正確的假資料 |

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
| **成員1** | **認證與基礎建設** | `m1-auth` | 8 支 | `routers/auth.py`<br>`models/user.py`<br>`schemas/auth.py` | `core/config.py`<br>`core/database.py`<br>`core/security.py`<br>`core/deps.py`<br>`services/llm/client.py` |
| **成員2** | **記帳** | `m2-ledger` | 8 支 | `routers/transactions.py`<br>`routers/nlp.py`<br>`models/transaction.py`<br>`models/nlp.py`<br>`schemas/transaction.py`<br>`schemas/nlp.py`<br>`services/llm/parse.py` | — |
| **成員3** | **數字與建議** | `m3-analytics` | 10 支 | `routers/categories.py`<br>`routers/stats.py`<br>`routers/budgets.py`<br>`routers/advices.py`<br>`models/budget.py`<br>`models/advice.py`<br>`schemas/stats.py`<br>`schemas/advice.py`<br>`services/llm/advice.py` | `services/analytics.py` |
| **成員4** | **家庭與可見範圍** | `m4-access` | 9 支 | `routers/family.py`<br>`models/family.py`<br>`models/audit.py`<br>`schemas/family.py`<br>`services/evaluation.py` | `services/permission.py` |

### 切分原則

1. **一個領域＝一個完整的概念**，不是一堆零散的路由湊數
2. **一個檔案剛好一個主人**，四個人不會改到同一個檔案 → git 幾乎不衝突
3. **會擋住別人的東西要盡量小**（`core/`、`permission.py`），才能最快完成解鎖別人
4. **每個人都要有一份 LLM 工作** —— 這是任務的硬性要求

### 各領域的邊界

#### 成員1 · 認證與基礎建設　`m1-auth`

負責「你是誰」以及整個後端的地基。
屬於他的：註冊登入登出、密碼、JWT、資料庫連線、設定管理、依賴注入、模型呼叫層。
不屬於他的：家庭角色與監管關係（那是成員4）。users 表存的是登入身分，family_members 表才是家庭角色，兩者刻意分開。

**LLM 工作**：共用的模型呼叫層：逾時、重試、把模型回傳的 JSON 交給 Pydantic 驗證。成員2 和成員3 都會呼叫它，所以第 1 週要先做出來。

**路由（8 支）**

```
POST    /api/auth/register
POST    /api/auth/login
POST    /api/auth/refresh
POST    /api/auth/logout
POST    /api/auth/logout-all
GET     /api/auth/me
PATCH   /api/auth/password
GET     /api/auth/sessions
```

#### 成員2 · 記帳　`m2-ledger`

負責「記一筆帳」這個動作，從文字進來到寫進資料庫。★ 這是整個系統的核心。
屬於他的：明細的增刪改查、段落解析、單句解析、確認後寫入、nlp_parses 的寫入。
不屬於他的：分類體系的定義與 /api/categories（那是成員3 —— 分類由成員3 定義，成員2 只是把清單寫進 prompt）；統計加總（那是成員3，前端和這裡都不做任何加總）。

**LLM 工作**：段落切分策略、欄位抽取 prompt、few-shot 範例的挑選、低信心的判準。切分比抽欄位更難，而且切錯比抽錯更難發現。

**路由（8 支）**

```
GET     /api/transactions
POST    /api/transactions
PATCH   /api/transactions/{tx_id}
DELETE  /api/transactions/{tx_id}
POST    /api/nlp/parse
POST    /api/nlp/parse-batch
POST    /api/nlp/confirm
POST    /api/nlp/confirm-batch
```

#### 成員3 · 數字與建議　`m3-analytics`

負責所有「算出來的東西」，以及把那些數字講成人話。
屬於他的：分類體系、月年統計、預算、每月存款目標、財務建議。
**整個系統只有這裡算錢** —— 路由不算、前端不算、模型更不算。
不屬於他的：明細的寫入（那是成員2）；決定要算哪些人（那是成員4 的 permission）。

**LLM 工作**：財務建議的 prompt 與邊界規則。順序不能顛倒：先用 analytics 算好數字，再餵給模型敘述，模型不做任何算術。

**路由（10 支）**

```
GET     /api/categories
POST    /api/categories
GET     /api/summary
GET     /api/stats
GET     /api/budgets
PUT     /api/budgets
GET     /api/savings-goal
PUT     /api/savings-goal
GET     /api/advices
POST    /api/advices/generate
```

#### 成員4 · 家庭與可見範圍　`m4-access`

負責「誰在這個家庭裡」以及「誰看得到誰的資料」，另外扛模型評測。
屬於他的：家庭、成員角色、邀請碼、監管關係、權限計算、稽核紀錄、評測。
不屬於他的：登入本身（那是成員1）。成員1 回答「你是誰」，成員4 回答「你能看到什麼」。

**LLM 工作**：模型評測：建立人工標註的留出集、跑零樣本 vs few-shot 對照、算一次輸入完全正確率與分類 Macro-F1。**留出集必須 100% 人工標註**，否則量到的是「多像那個老師」而不是「多正確」。

**路由（9 支）**

```
GET     /api/family
POST    /api/family
POST    /api/family/invite
POST    /api/family/join
PATCH   /api/family/members/{user_id}
DELETE  /api/family/members/{user_id}
GET     /api/guardianships
POST    /api/guardianships
DELETE  /api/guardianships/{gid}
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

```
成員1  core/deps.py（get_current_user）        ← 其他三人的每一支路由都要用
成員4  services/permission.py（visible_user_ids） ← 成員2、成員3 的查詢要用
成員3  分類體系（GET /api/categories）          ← 成員2 寫 prompt、成員4 評測要用
```

**這三件事要最優先完成。** 前兩件可以平行做，做完其他人才動得了。

### 六週排程

總長六週 = **實作四週 + 測試不到一週 + 報告簡報**。

⚠️ **後端線與模型線並行，不是接力。** 標註資料不用寫程式，第 1 週就能開始。

| 週 | 主題 | 後端線 | 模型線 |
|---|---|---|---|
| **1** | 地基與標註同時開始 | core/ 能動、每個人的前幾支路由打得通 | 標註 150 筆（不用寫程式，每人每天 1 小時） |
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

1. 四個角色各走一遍：master / parent / member / 未成年
2. 權限的**反向測試** —— 成員去打家庭總覽要被擋，這比正向測試重要
3. 段落記帳的邊界：缺欄位、低信心、切分錯誤、空輸入、超長輸入
4. 金額邊界：0、負數、小數、很大的數字
5. 年度統計的「未完整」標示有沒有出現
6. 帳號不存在與密碼錯誤，回的訊息要一樣
7. 批次寫入寫到一半失敗，要全部不寫（不可以留下半筆）

### 找到自己要做的事

```bash
grep -rn "TODO(成員2)" backend/app/
```

每個 TODO 底下都寫了要做哪幾步、為什麼那樣做、坑在哪裡。

### 前端專用、後端不實作的路由

- `POST /api/auth/switch`
  示範模式的切換身分鈕。**後端絕對不可以實作這支** —— 讓任何人任意切換身分等於把整套權限系統作廢。接上真後端之後，這個鈕要換成正常的登入登出。
