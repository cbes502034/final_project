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
| **沒有 GPU** | 在 Colab 免費 T4 上微調小模型，量化之後 CPU 就跑得動 |

**選型原則：能不加的就不加。** 每多一個相依，就多一個可能在最後一週爆炸的點。

---

# 二、工具清單

## 2-1　前端

| 工具 | 版本 | 用途 | 為什麼選它 |
|---|---|---|---|
| **原生 HTML / CSS / JS** | — | 整個前端 | 見下方說明 |
| **Noto Sans TC / Noto Serif TC** | Google Fonts | 字體 | 中文顯示品質，襯線標題是設計語言的一部分 |
| **Canvas API** | 瀏覽器內建 | 星空背景 | 無相依，四十行搞定 |
| **localStorage** | 瀏覽器內建 | mock 模式（跑在瀏覽器裡的後端）存資料 | 沒有後端時也能完整操作；不放任何假資料或範例帳號 |

### 為什麼不用 React / Vue

**這是一個要辯護的決定，不是省事。**

| 用 React 的好處 | 對本專案的實際影響 |
|---|---|
| 元件化、狀態管理 | 目前十四個畫面已經寫完，重寫是純成本 |
| 生態系豐富 | 我們沒有要用第三方 UI 套件 |
| 履歷加分 | 冠文已有 React 經驗，其他三人沒有 |

| 用原生的代價 | 實際狀況 |
|---|---|
| 沒有元件複用 | 十四個畫面規模還撐得住，函式化就夠 |
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
| **Alembic** | 1.14+ | 資料庫遷移 | 20 張表一定會改，沒有遷移工具會很痛苦 |
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
| **Qwen2.5-1.5B-Instruct** | 一句話記帳的解析、財務建議的敘述 | 自己微調的開源權重。選型與理由在專題手冊的「模型」那一頁 |
| **QLoRA ＋ Colab 免費 T4** | 微調 | 沒有 GPU，只能靠免費雲端；1.5B 一輪約一小時 |
| **GGUF ＋ llama.cpp（Hugging Face Space）** | 上線提供服務 | 量化成 q4 約 1 GB，CPU 跑得動；提供 OpenAI 相容的 `/v1/chat/completions` |
| **httpx** | 後端呼叫模型 | `services/llm/client.py` 已經寫好：逾時、重試、剝掉 ```json 包裝 |
| **Pydantic** | 約束模型輸出格式 | 模型回傳的 JSON 一定要過 Pydantic 驗證才採用 |

後端只認一個網址（`MODEL_BASE_URL`），**換模型不用改程式**：few-shot 基準線、第一輪、第二輪微調都是換網址。
商業 API（OpenAI 相容的）接得上同一支 client，可以拿來當對照組；課程重點是自己操作 LLM，**上線的模型用自己微調的**。

### 模型還沒好的時候

| 狀況 | 系統怎麼辦 |
|---|---|
| `MODEL_BASE_URL` 沒填、或模型服務叫不動 | 解析與建議的路由回 **503**；前端用規則頂著（解析：金額、中文數字、分類關鍵字；建議：用算好的數字寫成句子），畫面照常能用 |
| few-shot 基準線 | 同一顆 1.5B 不微調，只給範例。這就是對照表的第一列 |
| 微調後 | 換 `MODEL_BASE_URL`，其他程式碼一行都不用改 |

> **評測不能省。** 要交出「零樣本 vs few-shot vs 微調」的對照數字，那是本專題的量化成果。
> 評測工具在 `services/evaluation.py`（完全正確率、分類 Macro-F1）。

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
├── run.py                       ★ 一鍵啟動：裝套件、建 .env、建表、同時起前後端
├── frontend/                    前端（純靜態，可直接發布）
│   ├── index.html               <meta name="api-base"> 留空 = mock、填網址 = 真後端
│   ├── css/
│   │   ├── tokens.css           設計權杖：顏色、圓角、字體（預設的米白）
│   │   ├── app.css              元件與畫面，只准用變數
│   │   └── themes.css           另外七套主題
│   ├── js/
│   │   ├── data.js              資料表草案（schema）與固定清單（分類、主題、角色）。沒有假資料
│   │   ├── api.js          ★    唯一的資料入口：mock／http 兩個轉接器 ＋ 前端代勞 ＋ 錯誤指出是哪一支
│   │   ├── app.js               路由、畫面繪製、互動
│   │   ├── notify.js            通知鈴鐺（20 秒輪詢）
│   │   └── errbox.js            左下角那張表：打過的每一支，回應正確亮綠燈、出錯亮紅燈
│   └── docs/                    專題手冊（站上的 /docs/）
│
├── backend/
│   ├── app/
│   │   ├── main.py              入口：CORS、錯誤處理、掛上 routers/ 的每一組
│   │   ├── guards.py        ★   路由守衛：@login_required、@parent_required、own()、in_group()…
│   │   ├── cli.py               python -m app.cli：init-env、check-config、init-db、make-admin
│   │   ├── ownership.py         分工的單一事實來源（誰負責哪支路由、哪些檔案）
│   │   ├── catalog.py           固定清單（角色、權限表、理財選項、系統分類…），正本是 data.js
│   │   ├── toolkit/         ★   寫好的工具：config、db、crud（增刪改查）、tokens、passwords、scope、family…
│   │   ├── models/              20 張表（SQLAlchemy），欄位跟 data.js 的 schema 逐欄對齊
│   │   ├── schemas/             請求主體（Pydantic），欄位名字跟前端送的一樣
│   │   ├── routers/             70 支路由，一個領域一個資料夾。還沒做的回 501
│   │   │   ├── auth/            成員1 · 認證（auth.py、admin.py）　← 每個資料夾裡都有 README.md
│   │   │   ├── ledger/          成員2 · 記帳（transactions、nlp、categories、groups）
│   │   │   ├── analytics/       成員3 · 數字（stats、budgets、alerts、advices）
│   │   │   ├── access/          成員4 · 家庭（family、notifications）
│   │   │   └── _stub.py         共用：@stub 與 not_ready()
│   │   └── services/
│   │       ├── llm/client.py    模型呼叫層（已完成）
│   │       ├── llm/parse.py     記帳解析（成員2）
│   │       ├── llm/advice.py    財務建議（成員3）
│   │       ├── analytics.py     所有加總（成員3）
│   │       ├── permission.py    可見範圍（成員4）
│   │       └── evaluation.py    模型評測指標
│   ├── alembic/                 資料庫遷移（versions/ 第一版就是 20 張表）
│   ├── tests/                   pytest（routes/：每一支路由的驗收測試；fixtures/：假後端）
│   ├── tools/                   sync_spec.py、sync_schema.py、sync_mindmap.py、sync_devguide.py：文件從程式產生
│   ├── requirements.txt
│   ├── Dockerfile               啟動前先 alembic upgrade head
│   └── .env.example             設定範本，依成員分段
│
├── docs/                        規格文件
├── docker-compose.yml           本機用 PostgreSQL 跑整套（一般開發用 run.py 就夠）
├── render.yaml                  部署設定
└── README.md
```

**分層原則：`routers` 只做接收與回傳，規則放 `toolkit/`、加總與模型放 `services/`。**
這樣測試時可以直接測函式，不必每次都起一個 HTTP 請求。

---

# 四、API 目錄清單

共 **70 條路由**（另有 `/healthz`、`/docs` 兩支系統路由）。標示說明：

- **權限**：`公開` / `登入` / `本人` / `家長` / `監管者` / `建立者` / `平台管理員`
- ⚠️ `家長` 是**家庭**治理權限；`平台` 是系統管理員，只能停權與查稽核，讀不到任何財務資料。兩者完全分開。
- ★ 記號代表與 LLM 直接相關

## 4-1　身分認證 `/api/auth`

| # | 方法 | 路徑 | 負責人 | 權限 | 用途 |
|---|---|---|---|---|---|
| 1 | POST | `/api/auth/register` | 成員1 | 公開 | 註冊。只問名字、email、密碼，回傳 user + tokens（存款目標在註冊後的個人化設定） |
| 2 | POST | `/api/auth/login` | 成員1 | 公開 | 登入。回傳 access + refresh token |
| 3 | POST | `/api/auth/refresh` | 成員1 | 公開 | 用 refresh token 換新的 access token |
| 4 | POST | `/api/auth/logout` | 成員1 | 登入 | 撤銷目前的 refresh token |
| 5 | POST | `/api/auth/logout-all` | 成員1 | 登入 | 撤銷所有裝置的 token |
| 6 | GET | `/api/auth/me` | 成員1 | 登入 | 目前使用者、家庭角色、看得到誰、被誰監管 |
| 7 | PATCH | `/api/auth/password` | 成員1 | 登入 | 修改密碼，同時讓其他 session 失效。舊密碼不對回 400 |
| 74 | POST | `/api/auth/password-reset` | 成員1 | 公開 | 忘記密碼：寄一次性的重設連結（Brevo）。**有沒有這個帳號都回同一句話** |
| 75 | POST | `/api/auth/password-reset/confirm` | 成員1 | 公開 | 用信裡的 token 設新密碼。30 分鐘失效、只能用一次，成功後撤銷所有 sessions |
| 8 | GET | `/api/auth/me/finance` | 成員1 | 本人 | 我的理財習慣（財務建議的背景） |
| 9 | PUT | `/api/auth/me/finance` | 成員1 | 本人 | 改理財習慣。body: { style, goals[], habits[], note } |
| 10 | POST | `/api/auth/verify-password` | 成員1 | 本人 | 重大操作前再確認一次。不發新 token；不對回 400 |
| 11 | GET | `/api/auth/sessions` | 成員1 | 登入 | 列出有效的登入裝置 |
| 12 | PATCH | `/api/auth/me` | 成員1 | 登入 | 修改個人資料：顯示名稱、出生年、主題；個人化設定走完送 `onboarded: true` |
| 13 | PUT | `/api/auth/me/avatar` | 成員1 | 登入 | 上傳大頭貼。前端已縮到 256×256 |
| 14 | DELETE | `/api/auth/me/avatar` | 成員1 | 登入 | 移除大頭貼，改回顯示文字頭像 |
| 62 | GET | `/api/admin/users` | 成員1 | 平台管理員 | 帳號清單（停權用）。⚠️ 刻意不回傳任何金額 |
| 63 | POST | `/api/admin/users/{user_id}/suspend` | 成員1 | 平台管理員 | 停權一個帳號。body: { reason }，理由必填 |
| 64 | DELETE | `/api/admin/users/{user_id}/suspend` | 成員1 | 平台管理員 | 解除停權 |

**⚠️ 停權是關門，不是配鑰匙。**

平台管理員停得了違規帳號，但**讀不到任何一筆帳**。
一個能讀全系統消費明細的帳號，比家長越權嚴重得多——家長越權至少還在一個
看得見彼此的家庭裡，平台管理員的視角則沒有任何人看得到。
所以 `/api/admin/users` 只回身分欄位，`income`／`expense`／`savingsGoal` 一律不給；
不是前端藏起來，是後端真的不回。

另外三條界線：

- **停權不刪任何資料。** 擋登入、擋寫入，紀錄全部留著。停權是可以解除的。
- **理由必填**（少於 4 個字退回）。沒有理由的停權就是任意封鎖，被停的人也沒有東西可以申訴。
- **每一次停權與解除都要寫進 `audit_logs`。** 「誰放他回來的」跟「誰停的他」一樣重要。

權限判斷一律走 `toolkit/roles.py` 的 `require_platform()`，它的白名單只有
停權、解除停權、讀稽核三項——不要在路由裡自己寫 `if user.is_platform_admin`。


**回應範例 — `POST /api/auth/login`**

```json
{
  "accessToken": "eyJhbGciOi...",
  "refreshToken": "eyJhbGciOi...",
  "expiresIn": 1800,
  "user": { "id": "1", "name": "王大明", "email": "daming@wang.tw", "role": "parent",
            "familyId": "1", "avatar": "明", "avatarUrl": null,
            "onboardedAt": "2026-01-05T09:00:00+08:00", "theme": "sky", "savingsGoal": 20000 }
}
```

⚠️ ID 回字串（`crud.to_dict` 預設就轉）。每一支的完整形狀在 `02-前後端串接契約.md`。

## 4-2　家庭與權限 `/api/family`

| # | 方法 | 路徑 | 負責人 | 權限 | 用途 |
|---|---|---|---|---|---|
| 46 | GET | `/api/family` | 成員4 | 登入 | 家庭資訊、成員清單、角色 |
| 47 | POST | `/api/family` | 成員4 | 登入 | 建立家庭，建立的人成為家長。已經在家庭裡就不行 |
| 76 | DELETE | `/api/family` | 成員4 | 家長 | 解散家庭。**只有唯一的家長能解散**；每個人離開、紀錄都不刪 |
| 48 | POST | `/api/family/invite` | 成員4 | 家長 | 產生邀請碼。body: { role }，只能用一次、七天過期 |
| 49 | POST | `/api/family/join` | 成員4 | 登入 | 用邀請碼加入家庭 |
| 68 | GET | `/api/family/lookup` | 成員4 | 家長 | 用完整 email 找人，準備邀請他加入家庭 |
| 69 | GET | `/api/family/invites` | 成員4 | 登入 | 我收到的邀請、我們家送出去還沒回覆的、還有效的邀請碼 |
| 70 | POST | `/api/family/invites` | 成員4 | 家長 | 用帳號邀請。body: { userId, role } |
| 71 | POST | `/api/family/invites/{invite_id}/accept` | 成員4 | 被邀請的人 | 接受邀請，加入家庭 |
| 72 | DELETE | `/api/family/invites/{invite_id}` | 成員4 | 被邀請的人／家長 | 婉拒（被邀請的人）或取消（發邀請那一家的家長） |
| 50 | PATCH | `/api/family/members/{user_id}` | 成員4 | 家長 | 改角色。子女可以設為家長；**不能把另一位家長改成子女**，只能自己改（家裡要還有別的家長） |
| 51 | DELETE | `/api/family/members/{user_id}` | 成員4 | 家長／本人 | 家長把子女移出家庭；寫 `me` 就是自己退出。不刪資料 |
| 52 | GET | `/api/guardianships` | 成員4 | 登入 | 同一個家庭的監管關係。**被監管者也看得到** |
| 53 | POST | `/api/guardianships` | 成員4 | 家長 | 開始照看一個子女。body: { wardId }，**監管人一定是自己** |
| 54 | DELETE | `/api/guardianships/{gid}` | 成員4 | 監管者／同家庭的家長 | 停止照看（設 `ended_at`，不刪除）。被照看的人自己不能解除 |
| 55 | GET | `/api/notifications` | 成員4 | 登入 | 通知清單。帶 since 只拿新的 |
| 56 | PATCH | `/api/notifications/{nid}` | 成員4 | 本人 | 把一則標記成已讀 |
| 57 | PATCH | `/api/notifications` | 成員4 | 本人 | 整批標記已讀 |
| 25 | GET | `/api/groups` | 成員2 | 登入 | 我加入的群組（帳本） |
| 26 | POST | `/api/groups` | 成員2 | 登入 | 建立一個群組，建立者自動加入 |
| 27 | PATCH | `/api/groups/{gid}` | 成員2 | 建立者 | 改名稱、顏色、備註，或復原封存（`archived: false`） |
| 28 | DELETE | `/api/groups/{gid}` | 成員2 | 建立者 | 封存這本帳；`?permanent=true` 移除已結算的活動帳本（紀錄保留） |
| 29 | POST | `/api/groups/{gid}/members` | 成員2 | 建立者 | 把家人加進這本帳 |
| 30 | DELETE | `/api/groups/{gid}/members/{user_id}` | 成員2 | 建立者 | 把某個人移出這本帳 |
| 31 | POST | `/api/groups/{gid}/settle` | 成員2 | 本人（開帳本的人） | 結算活動帳本。之後唯讀，不能再往裡面記 |
| 32 | PATCH | `/api/groups/{gid}/notify` | 成員2 | 帳本成員 | 這本帳有動靜要不要通知我。body: { notify } |
| 58 | GET | `/api/allowances` | 成員4 | 登入 | 我每月給每個被監管者多少零用金 |
| 59 | PUT | `/api/allowance` | 成員4 | 監管者 | 設定零用金。body: { wardId, amount } |
| 65 | GET | `/api/audit` | 成員4 | 平台管理員 | 稽核紀錄：誰做了什麼。⚠️ 只記動作，不記金額 |

## 4-3　記帳 `/api/transactions`

| # | 方法 | 路徑 | 負責人 | 權限 | 用途 |
|---|---|---|---|---|---|
| 15 | GET | `/api/transactions` | 成員2 | 登入 | 明細。可帶 `userId` / `groupId` / `from` / `to` / `categoryId` / `kind` / `source` / `q` / `page`；不認得的參數回 422 |
| 16 | POST | `/api/transactions` | 成員2 | 登入 | 手動新增。**單筆手動模式走這支**，不經過模型，寫入的 `source` 記成 `manual` |
| 17 | PATCH | `/api/transactions/{tx_id}` | 成員2 | 本人 | 修改。只送要改的欄位；結算過的帳本裡的不能改（409） |
| 18 | DELETE | `/api/transactions/{tx_id}` | 成員2 | 本人 | 刪除一筆。結算過的帳本裡的不能刪（409） |
| 73 | DELETE | `/api/transactions` | 成員2 | 本人 | 一次刪多筆。`?ids=T1,T2`，最多 100 筆；**全部成功或全部不動** |
| 23 | GET | `/api/categories` | 成員2 | 登入 | 分類體系（系統預設 + 家庭自訂） |
| 24 | POST | `/api/categories` | 成員2 | 家長 | 新增家庭自訂分類。body: { name, kind }，1～10 字、同收支不重名 |

**查詢參數的權限行為**：不帶 `userId` 時回傳「你看得到的所有人」；
帶 `userId` 但你沒有權限看那個人 → **回 403 而不是空陣列**（空陣列會讓人以為對方沒記帳）。

## 4-4　一句話記帳 ★ `/api/nlp`

| # | 方法 | 路徑 | 負責人 | 權限 | 用途 |
|---|---|---|---|---|---|
| 19 | POST | `/api/nlp/parse` | 成員2 ★ | 登入 | 單句：一句話 → 一筆。**只解析，不寫入** |
| 20 | POST | `/api/nlp/parse-batch` | 成員2 ★ | 登入 | **段落：一段話 → 切成 N 筆**。只解析，不寫入 |
| 21 | POST | `/api/nlp/confirm` | 成員2 ★ | 登入 | 單筆確認後寫入，同時記錄修正供評測。`source` 記成 `nlp`，只有經過模型的資料才走這支 |
| 22 | POST | `/api/nlp/confirm-batch` | 成員2 ★ | 登入 | 批次確認後一次寫入 N 筆 |

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
  "matched": false,
  "out": { "date": "2026-09-10", "amount": 120, "kind": "expense", "cat": "1",
           "merchant": "", "conf": 0.98, "catConf": 0.94 },
  "note": "「今天」已換算成實際日期"
}
```

**請求 — `POST /api/nlp/confirm-batch`**（段落版，畫面實際在用的）

```json
{ "items": [ { "span": "今天午餐吃了120", "date": "2026-09-10", "amount": 120, "kind": "expense",
               "cat": "4", "merchant": "", "note": "",
               "orig": { "by": "model", "date": "2026-09-10", "amount": 120, "kind": "expense", "cat": "1" } } ] }
```

外層是使用者確認過的值，`orig` 是解析當下的原始結果。**兩邊不一樣的欄位存進 `nlp_parses.user_corrected`，
成為下一輪的訓練資料。這是本系統的資料飛輪。**（`orig.by` 是 `rules` 的是前端規則頂著的，不算模型的成績。）

## 4-5　統計與預算

| # | 方法 | 路徑 | 負責人 | 權限 | 用途 |
|---|---|---|---|---|---|
| 33 | GET | `/api/summary` | 成員3 | 登入 | 摘要。`scope=me\|family`、`period=2026-09`、`groupId`。統計頁唯一的來源 |
| 35 | GET | `/api/budgets` | 成員3 | 登入 | 預算與使用率 |
| 36 | PUT | `/api/budgets` | 成員3 | 本人 | 設定自己的分類預算。body: { cat, limit, period }，`limit: 0` = 拿掉 |
| 38 | PUT | `/api/savings-goal` | 成員3 | 本人 | **設定每月存款目標**（註冊後的個人化設定也走這支）。⚠️ 只有本人能設，監管者不能代設 |
| 39 | GET | `/api/savings-goals` | 成員3 | 登入 | 我的每月存款目標：不分群組的整體目標 ＋ 每個群組各自的 |
| 40 | GET | `/api/alerts` | 成員3 | 登入 | 我設定的階段性提醒門檻 |
| 41 | POST | `/api/alerts` | 成員3 | 本人 | 新增一個門檻（百分比 1~200） |
| 42 | PATCH | `/api/alerts/{aid}` | 成員3 | 本人 | 改百分比、或暫時關掉 |
| 43 | DELETE | `/api/alerts/{aid}` | 成員3 | 本人 | 刪掉一個門檻 |

**存款目標的計算**

```
可支配上限 = 本月收入 − 每月存款目標
支出 / 可支配上限 = 使用率

使用率 < 80%   → 達標中
80% ~ 100%     → 接近上限
> 100%         → 存不到目標，跳警告並算出短少多少
```

建好帳號之後的「個人化設定」第一步就會問「每月想存多少」（可以跳過，之後在個人資料改）。目標改動**保留歷史不覆蓋**
（`savings_goals` 帶 `period_key`），否則回頭看會不知道當時的目標是多少。

## 4-6　財務建議 ★ `/api/advices`

| # | 方法 | 路徑 | 負責人 | 權限 | 用途 |
|---|---|---|---|---|---|
| 44 | GET | `/api/advices` | 成員3 | 登入 | 建議清單。`scope`、`period` |
| 45 | POST | `/api/advices/generate` | 成員3 ★ | 登入（全家限家長） | 產生這個月的建議。body: { scope }。**後端先算好數字再餵給模型** |

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
| 66 | GET | `/healthz` | 系統 | 公開 | 健康檢查（Render 用） |
| 67 | GET | `/docs` | 系統 | 公開 | FastAPI 自動產生的 OpenAPI 文件 |

---

# 五、前端如何接上

前端的 `frontend/js/api.js` 有兩個轉接器，**簽章完全一致**：

| 模式 | 什麼時候 | 資料在哪 |
|---|---|---|
| **mock** | `<meta name="api-base">` 留空 | 跑在瀏覽器裡的後端，規則跟契約一樣，資料存在 `localStorage`。**沒有任何假資料或範例帳號**，從註冊開始 |
| **http** | 填上後端網址 | 全部改用 `fetch` 打真後端，不會混著用 mock |

```html
<meta name="api-base" content="https://fambudget-backend.onrender.com">
```

切到 http 之後，後端還沒做的路由回 501，**畫面會直接講是哪一支、哪條路由、誰負責**，其他頁照常能用；
有四支（`nlp/parse`、`nlp/parse-batch`、`advices/generate`、`auth/sessions`）前端還會先頂著。
所以可以一支一支慢慢接，不必等全部完成。名稱、結餘、比例、預算百分比這些前端補得出來，後端可以不帶——
細節在 `02-前後端串接契約.md` 的「已經定案的五件事」。

## 5-1　每一支路由的規格，寫在那一支的說明字串裡

`backend/app/routers/` 底下（一個領域一個資料夾）的 70 支路由，每一支的說明字串都有同樣的十一個段落：

```
【這支做什麼】【前端怎麼打】【誰能打】【請求主體／查詢參數】【成功回應】【錯誤回應】
【會用到的資料表】【每一步用的工具與資料庫方法】【寫法步驟】【完整寫法】【做完怎麼確認】
```

【完整寫法】的第二步是**要貼上去的程式**（只有函式內容，有的還有第三步：要一起換掉的服務函式）。
做法只有兩個動作：刪掉 `@stub`、把 `raise not_ready(...)` 那一行換成第二步——
裝飾器、參數、import 都已經放好最終版本；【做完怎麼確認】列出要在 `/docs` 上試哪幾種情況、結果應該是什麼。

這不是「文件另外寫一份」：`backend/tests/routes/` 會把說明字串裡的程式抓出來實際跑一遍
（每個測試跑兩次：**[說明]** 與 **[你的]**），所以說明跟實作不會走散——走散了 `pytest` 就紅燈。

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
| **成員1** | **認證** | `m1-auth` | 19 支 | `users` `sessions` | 註冊與登入、個人資料與大頭貼 | 共用的模型呼叫層：逾時、重試、把模型回傳的 JSON 交給 Pydantic 驗證 |
| **成員2** | **記帳** | `m2-ledger` | 19 支 | `transactions` `accounts` `nlp_parses` | 段落記帳、單筆手動、缺欄位提示 | 段落切分策略、欄位抽取 prompt、few-shot 範例的挑選、低信心的判準 |
| **成員3** | **數字** | `m3-analytics` | 11 支 | `categories` `budgets` `savings_goals` `advices` `alert_rules` | 總覽（我／全家）、統計圖表、超支警告、建議卡片 | 財務建議的 prompt 與邊界規則 |
| **成員4** | **家庭** | `m4-access` | 21 支 | `families` `family_members` `guardianships` `family_invites` `audit_logs` `notifications` `groups` `group_members` `allowances` | 成員與權限、成員紀錄（唯讀）、監管通知、群組 | 模型評測：建立人工標註的留出集、跑零樣本 vs few-shot 對照、算一次輸入完全正確率與分類 Macro-F1 |

### 切分原則

1. **一個領域＝一個完整的概念**，不是一堆零散的路由湊數
2. **一個檔案剛好一個主人** —— 四個人不會改到同一個檔案，git 幾乎不衝突
3. **會擋住別人的東西要盡量小**（`guards.py`、`toolkit/`、`permission.py`），而且這一版已經先做好了
4. **每個人都要有一份 LLM 工作**

### 為什麼路由數不是 10 / 10 / 10 / 5 這種平均切法

因為**路由數不是工作量**，但它也不能差太多。這一版是 19 / 19 / 11 / 21，
差距控制在合理範圍，同時讓每個領域維持概念上的完整。

成員3 的路由最少，是刻意的：他那一條的重量不在路由數，而在**整個系統只有他算錢**，
加上財務建議的 prompt 與邊界規則。一支 `/api/summary` 背後是全站的加總邏輯，
跟一支 `/api/auth/logout` 不是同一個量級。

成員1 看起來最多，但其中有一整組是同形狀的個人資料與工作階段路由；
他真正吃重的地方也不在路由，而在**所有人都要用的地基**（設定、資料庫、增刪改查、路由守衛）——
這一版已經先做好了，他負責維護。

**所以這張表上的數字只用來確認「沒有人被塞了兩倍的東西」，不拿來當工作量。**

## 6-3　各領域的邊界

寫清楚「什麼不是我的」比寫「什麼是我的」更重要——功能衝突都發生在邊界上。

### 成員1 · 認證　`m1-auth`

負責「你是誰」以及整個後端的地基。
屬於他的：註冊登入登出、密碼與忘記密碼、JWT、工作階段、個人資料與理財習慣，以及平台管理員的停權（停權擋的是登入，所以歸認證）。
地基（設定 `toolkit/config.py`、資料庫連線 `toolkit/db.py`、增刪改查 `toolkit/crud.py`、路由守衛 `guards.py`、模型呼叫層 `services/llm/client.py`、20 張表與 Alembic）**已經做好了**，他負責維護。
不屬於他的：家庭角色與監管關係（那是成員4）。users 表存的是登入身分，family_members 表才是家庭角色，兩者刻意分開。

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

### 成員2 · 記帳　`m2-ledger`

負責「記一筆帳」這個動作，從文字進來到寫進資料庫。★ 這是整個系統的核心。
屬於他的：明細的增刪改查、段落解析、單句解析、確認後寫入、nlp_parses 的寫入。
帳本（開、改、封存、結算、成員）與分類也在這裡：帳本是「這筆算在哪」的容器，分類是記帳時要選的欄位，統計只是拿它分組。
不屬於他的：統計加總（那是成員3，前端和這裡都不做任何加總）。

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

### 成員3 · 數字　`m3-analytics`

負責所有「算出來的東西」，以及把那些數字講成人話。
屬於他的：月年統計、預算、每月存款目標、階段性提醒的門檻、財務建議。
**整個系統只有這裡加總錢** —— 模型不算，前端只做衍生（結餘、比例、預算百分比）。
不屬於他的：明細的寫入（那是成員2）；決定要算哪些人（那是成員4 的 permission）。

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

### 成員4 · 家庭　`m4-access`

負責「誰在這個家庭裡」以及「誰看得到誰的資料」，另外扛模型評測。
屬於他的：家庭（建立、解散）、成員角色、家庭綁定（邀請碼與用帳號邀請）、監管關係、權限計算、通知、零用金、稽核紀錄、評測。
不屬於他的：登入本身（那是成員1）。成員1 回答「你是誰」，成員4 回答「你能看到什麼」。

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


## 6-4　六週排程

總長六週 = **實作四週 + 測試不到一週 + 報告簡報**。

⚠️ **後端線與模型線是並行的，不是接力。** 標註資料不用寫程式，
第 1 週就能開始 —— 那是唯一能跟後端開發平行的工作，
壓到第 3 週才做的話等於浪費了兩週產能。

| 週 | 主題 | 後端線 | 模型線 |
|---|---|---|---|
| **1** | 地基與標註同時開始 | 地基已經做好（toolkit、guards、models）：每個人拿掉前幾支的 `@stub`、打得通 | **標註 150 筆**（每人每天 1 小時） |
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

1. 三個層級各走一遍：平台 master / 家長 parent / 子女 child
2. **權限的反向測試** —— 子女切不到「全家」、直接打全家的 summary 也要被擋，這比正向測試重要
3. 段落記帳的邊界：缺欄位、低信心、切分錯誤、空輸入、超長輸入
4. 金額邊界：0、負數、小數、很大的數字
5. 年度統計的「未完整」標示有沒有出現
6. 帳號不存在與密碼錯誤，回的訊息要一樣
7. 批次寫入寫到一半失敗，要全部不寫

## 6-5　第 1 週的相依順序

原本會擋住別人的地基**已經做好了**，四個人第一天就能開工：

```
✅ 路由守衛        app/guards.py（@login_required、own()、in_group()、can_see_user()）
✅ 資料庫與增刪改查 app/toolkit/db.py、crud.py、models/（20 張表）、alembic/
✅ 可見範圍        app/guards.py 的 visible_scope()、services/permission.py 的 visible()
✅ 模型呼叫層      app/services/llm/client.py
```

還剩一件跨模組的事**要最優先**：

```
成員2  分類體系（GET /api/categories）  ← 成員2 寫 prompt、成員4 評測、成員3 統計分組都要用
```

系統預設分類跟 `data.js` 一致，`python -m app.cli init-db` 會放進去。**分類清單是唯一要凍結的跨模組契約**，
要改先在群組講。

## 6-6　分支規則

每個人只在自己的分支上動自己清單裡的檔案。

```bash
git switch -c m2-ledger
```

沒有單一主人的檔案（`main.py`、`ownership.py`、各 `__init__.py`），
動之前要先講一聲。

## 6-7　分工心智圖

見 [`分工心智圖.svg`](分工心智圖.svg)。它跟手冊裡的互動版都由 `python backend/tools/sync_mindmap.py` 產生：
路由數從 `ownership.py` 算、資料表從各人名下的 `models/` 讀，**不要手改**（pytest 會檢查）。

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

只跑前端（不需要後端也能完整操作，資料存在瀏覽器裡）：

```bash
python -m http.server 5174 --directory frontend
```
