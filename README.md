# 家庭記帳與財務控管系統

四人 × 一個月的期末專題。以家庭為單位的記帳系統，用自然語言降低輸入摩擦，
用月／年兩個時間準據做財務控管。

| | |
|---|---|
| **線上系統** | <https://fambudget-web.onrender.com> |
| **專題手冊** | <https://fambudget-web.onrender.com/docs/> |
| **FastAPI 說明書** | <https://fambudget-web.onrender.com/docs/fastapi.html> ← 沒學過 FastAPI 先讀這份 |
| **API 瀏覽** | <https://fambudget-web.onrender.com/docs/api.html> |
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
│   │   ├── core/            設定 · 資料庫 · 認證 · 依賴注入
│   │   ├── models/          SQLAlchemy 資料表（13 張）
│   │   ├── schemas/         Pydantic 請求／回應
│   │   ├── routers/         路由，一個檔案一組
│   │   └── services/        商業邏輯
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
<meta name="api-base" content="https://fambudget-api.onrender.com">
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
| `fambudget-api` | Python 服務 | `./backend` | `uvicorn app.main:app`，健康檢查打 `/healthz` |
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
證據是裡面宣告的 `fambudget-api` 與 `fambudget-db` **根本不存在**。

要讓它真的生效（後端和資料庫才會被自動建立），步驟如下。
**做完會換到新網址**，舊的 `llm-capstone-top20.onrender.com` 會停留在最後一次成功的建置。

1. **Render 後台 → New → Blueprint**
2. 選 `cbes502034/final_project` 這個 repo，分支 `main`
3. Render 會讀到這份 `render.yaml`，列出三個資源，確認一下：

   | 名稱 | 型態 | 來源 |
   |---|---|---|
   | `fambudget-web` | Static Site | `./frontend` |
   | `fambudget-api` | Web Service (Python) | `./backend` |
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
| 後端 | `https://fambudget-api.onrender.com` |
| API 文件 | `https://fambudget-api.onrender.com/docs` |

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

每人吃一條完整的功能模組，從資料表、API、畫面一路到該模組自己的 LLM。

| 成員 | 領域 | 路由編號 |
|---|---|---|
| 成員1 | 帳號與權限（另含大家共用的 `core/`、模型呼叫層、權限計算） | 1–17 |
| 成員2 | 記帳 ★ 系統核心 | 18–27 |
| 成員3 | 統計與預算（分類體系由這裡定義，第 1 週要凍結） | 28–33 |
| 成員4 | 財務建議（另含全系統評測） | 34–35 |

詳細分工與三週排程見[專題手冊](https://fambudget-web.onrender.com/docs/)。

### 找到自己要做的事

```bash
grep -rn "TODO(成員2)" backend/app/
```

每個 TODO 底下都寫了要做哪幾步、為什麼那樣做、坑在哪裡。
