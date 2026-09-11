# 技術選型與 API 目錄

家庭記帳與財務控管系統｜四人 × 一個月

---

# 一、選型的三個前提

在談用什麼工具之前，先把限制寫清楚 —— 所有選擇都是從這三條推出來的：

| 限制 | 影響 |
|---|---|
| **只有一個月** | 不能有學習曲線陡的東西。每個新框架都要換算成「幾天學會」 |
| **四人中三人沒有專案經驗** | 工具要好上手、錯誤訊息要看得懂、出問題查得到中文資料 |
| **冠文有 FastAPI / Docker / Render 實戰經驗** | 後端主幹沿用他熟的，不要為了「更好」而換 |
| **沒有 GPU** | 模型只能用 API，或在 Colab 免費 T4 上微調小模型 |

**選型原則：能不加的就不加。** 每多一個相依，就多一個可能在最後一週爆炸的點。

---

# 二、工具清單

## 2-1　前端

| 工具 | 版本 | 用途 | 為什麼選它 |
|---|---|---|---|
| **原生 HTML / CSS / JS** | — | 整個前端 | 見下方說明 |
| **Noto Sans TC / Noto Serif TC** | Google Fonts | 字體 | 中文顯示品質，襯線標題是設計語言的一部分 |
| **Canvas API** | 瀏覽器內建 | 星空背景 | 無相依，四十行搞定 |
| **localStorage** | 瀏覽器內建 | mock 模式暫存 | 沒有後端時也能完整展示 |

### 為什麼不用 React / Vue

**這是一個要辯護的決定，不是省事。**

| 用 React 的好處 | 對本專案的實際影響 |
|---|---|
| 元件化、狀態管理 | 目前八個畫面已經寫完，重寫是純成本 |
| 生態系豐富 | 我們沒有要用第三方 UI 套件 |
| 履歷加分 | 冠文已有 React 經驗，其他三人沒有 |

| 用原生的代價 | 實際狀況 |
|---|---|
| 沒有元件複用 | 八個畫面規模還撐得住，函式化就夠 |
| 手寫 DOM 操作 | 已經封裝在 `app.js` 的 render 函式裡 |
| 沒有型別檢查 | 用 `js/api.js` 這一層集中管住資料形狀 |

**決定：維持原生。** 理由是時間 —— 三個沒有專案經驗的人要同時學 React、學 Vite、學 hooks，
再加上後端與模型，一個月做不完。**這個取捨要寫進報告，講成有意識的決定而不是能力不足。**

> 如果之後有時間，值得升級的是**打包**（Vite）而不是框架，
> 因為那只影響建置流程，不需要重寫畫面。

## 2-2　後端

| 工具 | 版本 | 用途 | 為什麼選它 |
|---|---|---|---|
| **FastAPI** | 0.115+ | Web 框架 | 冠文有實戰。自動產生 OpenAPI 文件，前後端對接時省掉很多口頭溝通 |
| **Uvicorn** | 0.34+ | ASGI 伺服器 | FastAPI 的標準搭配 |
| **Pydantic** | v2 | 請求／回應驗證 | **強制結構化輸出的關鍵**，LLM 回傳也用它驗 |
| **pydantic-settings** | 2.6+ | 環境變數管理 | 設定集中，不散落在各處 |
| **SQLAlchemy** | 2.0 | ORM | 2.0 的型別標註對新手比較友善 |
| **Alembic** | 1.14+ | 資料庫遷移 | 12 張表一定會改，沒有遷移工具會很痛苦 |
| **psycopg** | 3.2+ | PostgreSQL 驅動 | `[binary]` 版有預編譯輪檔，不用編譯 |
| **PyJWT** | 2.10+ | JWT 簽發驗證 | 比 python-jose 維護更活躍 |
| **passlib[bcrypt]** | 1.7+ | 密碼雜湊 | **絕不自己實作密碼雜湊** |
| **python-multipart** | 0.0.20+ | 表單登入 | OAuth2 密碼流程需要 |

### 為什麼不用 Django

Django 內建 admin 與 auth，聽起來很划算。但：

- 冠文的實戰經驗在 FastAPI，換框架等於放棄既有優勢
- Django 的 ORM 與 FastAPI 的 Pydantic 是兩套思維，混用會亂
- 本專案的 API 是給自己的前端用，不需要 Django 的完整後台

### Redis 要不要用

**建議第一版不用。** 原型設計裡列了 Redis，但實際盤點後：

| 原本想用 Redis 做的 | 沒有 Redis 的替代 |
|---|---|
| session 儲存 | `sessions` 資料表就夠，四人家庭規模不會有效能問題 |
| 快取統計結果 | 一個家庭幾百筆交易，直接查資料庫毫秒級 |
| LLM 回應快取 | 存進 `nlp_parses` 表反而更有用（同時是訓練資料） |

**多一個服務就多一個要維護、要部署、要除錯的東西。** 有時間再加。

## 2-3　LLM

| 工具 | 用途 | 說明 |
|---|---|---|
| **Anthropic API** | 一句話記帳的解析、財務建議生成 | 冠文履歷有實戰經驗（Tool Use 兩輪架構、強制結構化輸出） |
| **Pydantic** | 約束模型輸出格式 | 模型回傳的 JSON 一定要過 Pydantic 驗證才採用 |
| **Colab 免費 T4** | 微調（第二階段） | 沒有 GPU，只能靠免費雲端 |

### 第一版建議先不微調

| 做法 | 成本 | 預期效果 |
|---|---|---|
| **API + few-shot + 結構化輸出** | 低，一週內可上線 | 一次輸入完全正確率約 0.6–0.75 |
| API + 微調小模型 | 高，要標註 + 訓練 + 評測 | 目標 0.75+ |

**第一版先用 API 把系統跑起來**，收集 `nlp_parses` 的真實資料，第二階段再微調。
這樣即使微調來不及，系統仍然是完整可用的。

> **但評測不能省。** 就算不微調，也要交出「零樣本 vs few-shot」的對照數字，
> 那是本專題的量化成果。

## 2-4　開發與部署

| 工具 | 用途 |
|---|---|
| **Docker + Docker Compose** | 本機一鍵起 db + api + web，`docker compose up` |
| **PostgreSQL 16** | 資料庫。本機跑容器、線上用 Render 免費方案 |
| **Git / GitHub** | 版本控制。帳號 cbes502034 |
| **Render** | 部署。前端靜態站台走 CDN、後端 Python 服務、免費 PostgreSQL |
| **pytest** | 後端測試 |
| **httpx** | 測試用的 HTTP client（FastAPI TestClient 底層） |

---

# 三、專案目錄結構

```
final_project/
├── site/                        前端（純靜態，可直接發布）
│   ├── index.html
│   ├── css/
│   │   ├── tokens.css          設計權杖：星空底、藍紫色系、圓角
│   │   └── app.css             元件與八個畫面
│   └── js/
│       ├── stars.js            canvas 星空與流星
│       ├── data.js             模擬資料（mock 模式用）
│       ├── api.js         ★    唯一的資料入口，mock / http 兩轉接器
│       └── app.js              路由、畫面繪製、互動
│
├── api/                        後端
│   ├── app/
│   │   ├── main.py             入口，掛載路由與中介層
│   │   ├── core/
│   │   │   ├── config.py       環境變數（pydantic-settings）
│   │   │   ├── security.py     密碼雜湊、JWT 簽發驗證
│   │   │   └── deps.py         依賴注入：取得目前使用者、權限守門
│   │   ├── models/             SQLAlchemy 資料表定義（12 張）
│   │   ├── schemas/            Pydantic 請求／回應模型
│   │   ├── routers/            API 路由，一個檔案一組
│   │   │   ├── auth.py
│   │   │   ├── family.py
│   │   │   ├── transactions.py
│   │   │   ├── nlp.py     ★    一句話記帳
│   │   │   ├── stats.py
│   │   │   ├── budgets.py
│   │   │   └── advices.py
│   │   └── services/           商業邏輯，路由只負責接收與回傳
│   │       ├── llm.py     ★    Anthropic 呼叫、結構化輸出約束、重試
│   │       ├── permission.py   依角色與監管關係算出可見範圍
│   │       └── analytics.py    月年統計、預算使用率
│   ├── tests/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
│
├── docs/                       規格文件
├── docker-compose.yml          本機一鍵啟動
├── render.yaml                 部署設定
└── README.md
```

**分層原則：`routers` 只做接收與回傳，商業邏輯一律放 `services`。**
這樣測試時可以直接測 service，不必每次都起一個 HTTP 請求。

---

# 四、API 目錄清單

共 **38 條路由**。標示說明：

- **權限**：`公開` / `登入` / `master` / `監管者`
- ★ 記號代表與 LLM 直接相關

## 4-1　身分認證 `/api/auth`

| # | 方法 | 路徑 | 負責人 | 權限 | 用途 |
|---|---|---|---|---|---|
| 1 | POST | `/api/auth/register` | 成員1 | 公開 | 註冊。回傳 user + tokens |
| 2 | POST | `/api/auth/login` | 成員1 | 公開 | 登入。回傳 access + refresh token |
| 3 | POST | `/api/auth/refresh` | 成員1 | 公開 | 用 refresh token 換新的 access token |
| 4 | POST | `/api/auth/logout` | 成員1 | 登入 | 撤銷目前的 refresh token |
| 5 | POST | `/api/auth/logout-all` | 成員1 | 登入 | 撤銷所有裝置的 token |
| 6 | GET | `/api/auth/me` | 成員1 | 登入 | 目前使用者、家庭角色、被誰監管 |
| 7 | PATCH | `/api/auth/password` | 成員1 | 登入 | 修改密碼，同時讓其他 session 失效 |
| 8 | GET | `/api/auth/sessions` | 成員1 | 登入 | 列出有效的登入裝置 |
| 36 | PATCH | `/api/auth/me` | 成員1 | 登入 | 修改個人資料：顯示名稱、出生年 |
| 37 | PUT | `/api/auth/me/avatar` | 成員1 | 登入 | 上傳大頭貼。前端已縮到 256×256 |
| 38 | DELETE | `/api/auth/me/avatar` | 成員1 | 登入 | 移除大頭貼，改回顯示文字頭像 |

**回應範例 — `POST /api/auth/login`**

```json
{
  "accessToken": "eyJhbGciOi...",
  "refreshToken": "eyJhbGciOi...",
  "expiresIn": 1800,
  "user": { "id": 1, "displayName": "林建國", "role": "master" }
}
```

## 4-2　家庭與權限 `/api/family`

| # | 方法 | 路徑 | 負責人 | 權限 | 用途 |
|---|---|---|---|---|---|
| 9 | GET | `/api/family` | 成員4 | 登入 | 家庭資訊、成員清單、角色 |
| 10 | POST | `/api/family` | 成員4 | 登入 | 建立家庭，建立者成為 master |
| 11 | POST | `/api/family/invite` | 成員4 | master | 產生邀請碼 |
| 12 | POST | `/api/family/join` | 成員4 | 登入 | 用邀請碼加入家庭 |
| 13 | PATCH | `/api/family/members/{userId}` | 成員4 | master | 修改成員角色 |
| 14 | DELETE | `/api/family/members/{userId}` | 成員4 | master | 移除成員（標記 removed，不刪資料） |
| 15 | GET | `/api/guardianships` | 成員4 | 登入 | 監管關係。**被監管者也看得到** |
| 16 | POST | `/api/guardianships` | 成員4 | master | 建立監管關係 |
| 17 | DELETE | `/api/guardianships/{id}` | 成員4 | master | 解除監管（設 `ended_at`，不刪除） |

## 4-3　記帳 `/api/transactions`

| # | 方法 | 路徑 | 負責人 | 權限 | 用途 |
|---|---|---|---|---|---|
| 18 | GET | `/api/transactions` | 成員2 | 登入 | 明細。可帶 `userId` / `from` / `to` / `categoryId` / `kind` / `q` / `page` |
| 19 | POST | `/api/transactions` | 成員2 | 登入 | 手動新增。**單筆手動模式走這支**，不經過模型，寫入的 `source` 記成 `manual` |
| 20 | PATCH | `/api/transactions/{id}` | 成員2 | 本人或監管者 | 修改 |
| 21 | DELETE | `/api/transactions/{id}` | 成員2 | 本人 | 刪除 |
| 22 | GET | `/api/categories` | 成員3 | 登入 | 分類體系（系統預設 + 家庭自訂） |
| 23 | POST | `/api/categories` | 成員3 | master | 新增家庭自訂分類 |

**查詢參數的權限行為**：不帶 `userId` 時回傳「你看得到的所有人」；
帶 `userId` 但你沒有權限看那個人 → **回 403 而不是空陣列**（空陣列會讓人以為對方沒記帳）。

## 4-4　一句話記帳 ★ `/api/nlp`

| # | 方法 | 路徑 | 負責人 | 權限 | 用途 |
|---|---|---|---|---|---|
| 24 | POST | `/api/nlp/parse` | 成員2 ★ | 登入 | 單句：一句話 → 一筆。**只解析，不寫入** |
| 25 | POST | `/api/nlp/parse-batch` | 成員2 ★ | 登入 | **段落：一段話 → 切成 N 筆**。只解析，不寫入 |
| 26 | POST | `/api/nlp/confirm` | 成員2 ★ | 登入 | 單筆確認後寫入，同時記錄修正供評測。`source` 記成 `nlp`，只有經過模型的資料才走這支 |
| 27 | POST | `/api/nlp/confirm-batch` | 成員2 ★ | 登入 | 批次確認後一次寫入 N 筆 |

**段落解析比單句難的地方在「切分」**：模型要先判斷這段話裡有幾筆。
切錯（把兩筆合成一筆）比抽錯更難發現，所以**切分結果也要讓使用者確認** ——
畫面上每一列都標出它對應原句的哪一段。

缺欄位的處理：**直接標在該欄位上**（紅框 + 「必填」標記），
整列變色，補齊之前送出鈕停用。

**這兩支是整個系統的核心。** 分成兩步是刻意的 —— 模型不直接寫資料庫。

**請求 — `POST /api/nlp/parse`**

```json
{ "text": "今天午餐吃了120" }
```

**回應**

```json
{
  "raw": "今天午餐吃了120",
  "parsed": {
    "occurredOn": "2026-09-10",
    "amount": 120,
    "kind": "expense",
    "categoryId": 1,
    "merchant": null
  },
  "confidence": { "amount": 0.98, "occurredOn": 0.96, "kind": 0.97, "category": 0.94 },
  "note": "「今天」已換算成實際日期",
  "modelVer": "claude-haiku-4-5-20251001"
}
```

**請求 — `POST /api/nlp/confirm`**

```json
{
  "raw": "今天午餐吃了120",
  "parsed": { "occurredOn": "2026-09-10", "amount": 120, "kind": "expense", "categoryId": 1 },
  "corrected": { "categoryId": 4 },
  "parseId": 881
}
```

`corrected` 有值就表示使用者改過 —— **這筆會被存進 `nlp_parses.user_corrected`，
成為下一輪的訓練資料。這是本系統的資料飛輪。**

## 4-5　統計與預算

| # | 方法 | 路徑 | 負責人 | 權限 | 用途 |
|---|---|---|---|---|---|
| 28 | GET | `/api/summary` | 成員3 | 登入 | 摘要。`scope=me\|family`、`period=2026-09` |
| 29 | GET | `/api/stats` | 成員3 | 登入 | 統計。`periodType=month\|year`、`from`、`to` |
| 30 | GET | `/api/budgets` | 成員3 | 登入 | 預算與使用率 |
| 31 | PUT | `/api/budgets` | 成員3 | 本人或 master | 設定預算 |
| 32 | GET | `/api/savings-goal` | 成員3 | 登入 | **每月存款目標與達成狀態** |
| 33 | PUT | `/api/savings-goal` | 成員3 | 本人；未成年由 master | **設定每月存款目標**（註冊時也走這支） |

**存款目標的計算**

```
可支配上限 = 本月收入 − 每月存款目標
支出 / 可支配上限 = 使用率

使用率 < 80%   → 達標中
80% ~ 100%     → 接近上限
> 100%         → 存不到目標，跳警告並算出短少多少
```

註冊時就會請使用者填「每月想存多少」。目標改動**保留歷史不覆蓋**
（`savings_goals` 帶 `period_key`），否則回頭看會不知道當時的目標是多少。

## 4-6　財務建議 ★ `/api/advices`

| # | 方法 | 路徑 | 負責人 | 權限 | 用途 |
|---|---|---|---|---|---|
| 34 | GET | `/api/advices` | 成員3 | 登入 | 建議清單。`scope`、`period` |
| 35 | POST | `/api/advices/generate` | 成員3 ★ | master | 重新產生。**後端先算好數字再餵給模型** |

**產生流程（順序不能顛倒）**

```
1. analytics service 從資料庫算出所有數字
        ↓
2. 把「算好的數字」組成 prompt 的一部分
        ↓
3. 呼叫模型，要求它只做敘述與歸納
        ↓
4. Pydantic 驗證輸出格式
        ↓
5. 把數字存進 advices.basis_json（給使用者驗算用）
```

**模型不做任何算術。** 財務數字算錯會讓使用者做出錯誤決定，而模型本來就不擅長算術。

## 4-7　系統

| # | 方法 | 路徑 | 負責人 | 權限 | 用途 |
|---|---|---|---|---|---|
| 39 | GET | `/healthz` | 系統 | 公開 | 健康檢查（Render 用） |
| 40 | GET | `/docs` | 系統 | 公開 | FastAPI 自動產生的 OpenAPI 文件 |

---

# 五、前端如何接上

前端目前跑在 **mock 模式**，所有資料來自 `web/js/data.js`。
要切換到真後端，只要改 `site/index.html` 一行：

```html
<meta name="api-base" content="https://fambudget-backend.onrender.com">
```

留空 = mock 模式。填上網址 = 改用 `fetch` 打真後端。

**`frontend/js/api.js` 裡 `mockAdapter` 與 `httpAdapter` 的簽章完全一致**，
所以可以一支一支路由慢慢接 —— 後端做好哪支就改哪支，不必等全部完成。

---

# 六、分工與排程

## 6-1　單一事實來源

分工寫在 **`backend/app/ownership.py`**，不是寫在文件裡。

那個檔案是程式讀得到的，而且 `pytest` 會檢查它有沒有跟程式碼走散——
有人新增路由卻沒認領、或兩個人宣告同一支，測試就紅燈。

```bash
cd backend
python -m app.ownership      # 印出分工表並檢查一致性
```

**這份文件是從那個檔案抄過來的。兩邊不一致時，以那個檔案為準。**

## 6-2　四個領域

不是「一個做後端、一個做前端」，而是每人吃一條完整的功能模組——
從資料表、API、畫面，一路到該模組自己的 LLM。

| 成員 | 領域 | 分支 | 路由 | 資料表 | 畫面 | 該模組的 LLM |
|---|---|---|---|---|---|---|
| **成員1** | **認證與基礎建設** | `m1-auth` | 8 支 | `users` `sessions` | 註冊與登入 | 共用的模型呼叫層：逾時、重試、把模型回傳的 JSON 交給 Pydantic 驗證 |
| **成員2** | **記帳** | `m2-ledger` | 8 支 | `transactions` `accounts` `nlp_parses` | 段落記帳、單筆手動、缺欄位提示 | 段落切分策略、欄位抽取 prompt、few-shot 範例的挑選、低信心的判準 |
| **成員3** | **數字與建議** | `m3-analytics` | 10 支 | `categories` `budgets` `savings_goals` `advices` | 我的總覽、家庭總覽、統計圖表、超支警告、建議卡片 | 財務建議的 prompt 與邊界規則 |
| **成員4** | **家庭與可見範圍** | `m4-access` | 9 支 | `families` `family_members` `guardianships` `family_invites` `audit_logs` | 成員與權限 | 模型評測：建立人工標註的留出集、跑零樣本 vs few-shot 對照、算一次輸入完全正確率與分類 Macro-F1 |

### 切分原則

1. **一個領域＝一個完整的概念**，不是一堆零散的路由湊數
2. **一個檔案剛好一個主人** —— 四個人不會改到同一個檔案，git 幾乎不衝突
3. **會擋住別人的東西要盡量小**（`core/`、`permission.py`），才能最快解鎖別人
4. **每個人都要有一份 LLM 工作**

### 為什麼路由數不是 10 / 10 / 10 / 5 這種平均切法

因為**路由數不是工作量**，但它也不能差太多。這一版是 8 / 8 / 10 / 9，
差距控制在合理範圍，同時讓每個領域維持概念上的完整。

成員1 的路由最少（8 支），是刻意的：他同時扛著 `core/` 這個**所有人都要用的地基**。
路由少一點，他才能最快把地基做完，讓其他三個人動得了。

## 6-3　各領域的邊界

寫清楚「什麼不是我的」比寫「什麼是我的」更重要——功能衝突都發生在邊界上。

### 成員1 · 認證與基礎建設　`m1-auth`

負責「你是誰」以及整個後端的地基。
屬於他的：註冊登入登出、密碼、JWT、資料庫連線、設定管理、依賴注入、模型呼叫層。
不屬於他的：家庭角色與監管關係（那是成員4）。users 表存的是登入身分，family_members 表才是家庭角色，兩者刻意分開。

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

### 成員2 · 記帳　`m2-ledger`

負責「記一筆帳」這個動作，從文字進來到寫進資料庫。★ 這是整個系統的核心。
屬於他的：明細的增刪改查、段落解析、單句解析、確認後寫入、nlp_parses 的寫入。
不屬於他的：分類體系的定義與 /api/categories（那是成員3 —— 分類由成員3 定義，成員2 只是把清單寫進 prompt）；統計加總（那是成員3，前端和這裡都不做任何加總）。

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

### 成員3 · 數字與建議　`m3-analytics`

負責所有「算出來的東西」，以及把那些數字講成人話。
屬於他的：分類體系、月年統計、預算、每月存款目標、財務建議。
**整個系統只有這裡算錢** —— 路由不算、前端不算、模型更不算。
不屬於他的：明細的寫入（那是成員2）；決定要算哪些人（那是成員4 的 permission）。

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

### 成員4 · 家庭與可見範圍　`m4-access`

負責「誰在這個家庭裡」以及「誰看得到誰的資料」，另外扛模型評測。
屬於他的：家庭、成員角色、邀請碼、監管關係、權限計算、稽核紀錄、評測。
不屬於他的：登入本身（那是成員1）。成員1 回答「你是誰」，成員4 回答「你能看到什麼」。

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


## 6-4　六週排程

總長六週 = **實作四週 + 測試不到一週 + 報告簡報**。

⚠️ **後端線與模型線是並行的，不是接力。** 標註資料不用寫程式，
第 1 週就能開始 —— 那是唯一能跟後端開發平行的工作，
壓到第 3 週才做的話等於浪費了兩週產能。

| 週 | 主題 | 後端線 | 模型線 |
|---|---|---|---|
| **1** | 地基與標註同時開始 | `core/` 能動、每人前幾支路由打得通 | **標註 150 筆**（每人每天 1 小時） |
| **2** | 前後端串通 | 後端完成、**關掉 mock 畫面還能動** | 標註到 300 筆、Colab 環境跑通 |
| **3** | 基準線與第一輪微調 | 補洞、修 bug、**四人開始自己用** | few-shot 基準線 ＋ 第一輪 QLoRA |
| **4** | 第二輪微調 | 功能凍結 | 第二輪微調 ＋ 接回系統 |
| **5** | 測試 | 全系統測試、權限反向測試 | 評測數字定稿 |
| **6** | 報告與緩衝 | 報告、簡報 | 對照表、圖表 |

### 三條硬線

**第 2 週結束必須做到「關掉 mock 畫面還能動」。**
沒達到的話第 3 週不要碰微調，先把串接做完。

**第 3 週結束要有第一輪微調的數字。**
沒有的話第 4 週**放棄第二輪**，用 few-shot 版收尾。
一個穩定的 few-shot 系統 + 完整評測，
比一個微調到一半、展示會當機的系統好太多。

**第 4 週最後兩天不准改模型。**
留給「接回系統 + 確認沒壞」。測試週太短，不能拿來救火。

### 為什麼要兩輪微調

第一輪幾乎一定會讓你失望 —— 資料太少、參數沒調好、格式沒對齊。
做過的人都知道。**第二輪才是真的。**

這是報告裡「我們試了但沒成功」和「**0.42 → 0.61 → 0.79**」的差別。

而且第 3 週系統能用之後，四個人自己用一週收集到的**真實修正**，
正好餵給第二輪 —— 資料飛輪從投影片上的概念變成真的轉過一圈。

### 測試不能留到第 5 週

不到一週的測試週只夠「全系統走一遍 + 修小 bug」。
真正的測試要**邊做邊測**：每支路由寫完當下就用 `/docs` 試打，不要累積。

第 5 週要走過的清單：

1. 四個角色各走一遍：master / parent / member / 未成年
2. **權限的反向測試** —— 成員去打家庭總覽要被擋，這比正向測試重要
3. 段落記帳的邊界：缺欄位、低信心、切分錯誤、空輸入、超長輸入
4. 金額邊界：0、負數、小數、很大的數字
5. 年度統計的「未完整」標示有沒有出現
6. 帳號不存在與密碼錯誤，回的訊息要一樣
7. 批次寫入寫到一半失敗，要全部不寫

## 6-5　第 1 週的相依順序

這三件事會擋住別人，**要最優先完成**：

```
成員1  core/deps.py 的 get_current_user          ← 其他三人的每一支路由都要用
成員4  services/permission.py 的 visible_user_ids ← 成員2、成員3 的查詢要用
成員3  分類體系（GET /api/categories）            ← 成員2 寫 prompt、成員4 評測要用
```

前兩件可以平行做。**分類體系是唯一的跨模組契約**，成員3 定好就凍結，
要改先在群組講。

## 6-6　分支規則

每個人只在自己的分支上動自己清單裡的檔案。

```bash
git switch -c m2-ledger
```

沒有單一主人的檔案（`main.py`、`ownership.py`、各 `__init__.py`），
動之前要先講一聲。

## 6-7　分工心智圖

見 [`分工心智圖.svg`](分工心智圖.svg)。

可填寫的互動版在站上的[專題手冊](https://fambudget-web.onrender.com/docs/)，
四個人各自填名字、按儲存後可以複製分享連結給組員。

---

# 七、本機開發

```bash
# 一鍵起 db + api + web
docker compose up

# 前端  http://localhost:5174
# 後端  http://localhost:8000
# 文件  http://localhost:8000/docs
```

只跑前端（不需要後端也能完整展示）：

```bash
python -m http.server 5174 --directory frontend
```
