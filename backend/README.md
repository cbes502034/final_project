# backend — FastAPI 後端

> 第一次碰 FastAPI？**先讀站上的 [FastAPI 說明書](https://fambudget-web.onrender.com/docs/fastapi.html)**，
> 那份是從零開始教的。這份 README 假設你已經讀過了。

---

## 三十秒跑起來

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env          # 然後把 .env 裡的值填一填
uvicorn app.main:app --reload
```

打開 <http://localhost:8000/docs> ——
FastAPI 自動產生的互動式文件，**可以直接在上面送出請求試打**，
不需要寫前端，也不需要 Postman。

跑測試：

```bash
pytest
```

---

## 目錄怎麼看

```
backend/
├── app/
│   ├── main.py            ← 入口。只負責組裝，不寫商業邏輯
│   │
│   ├── core/              ← 核心設施。換一個題目也能整包搬走
│   │   ├── config.py        環境變數集中管理
│   │   ├── database.py      資料庫連線與 session
│   │   ├── security.py      密碼雜湊、JWT 簽發驗證
│   │   └── deps.py          依賴注入：取得登入者、權限守門
│   │
│   ├── models/            ← 資料庫長什麼樣（SQLAlchemy，13 張表）
│   ├── schemas/           ← API 進出長什麼樣（Pydantic）
│   ├── routers/           ← 路由。只負責收送，一個檔案一組
│   └── services/          ← 商業邏輯。真正做事的地方
│
├── alembic/               ← 資料庫結構變更的版本控制
├── tests/
├── requirements.txt
├── Dockerfile
└── .env.example
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

`routers/` 只做三件事：收請求、驗權限、回結果。
真正的計算與規則寫在 `services/`。

這樣做測試時可以直接呼叫 service 函式，
不必每次都起一個完整的 HTTP 請求，快很多也好寫很多。

---

## 誰負責哪一塊

分工的**單一事實來源是 `app/ownership.py`**，不是這份文件。
那個檔案是程式讀得到的，而且 `pytest` 會檢查它有沒有跟程式碼走散——
有人新增路由卻沒認領、或兩個人宣告同一支，測試就會紅燈。

```bash
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
- `app/ownership.py`
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

### 找到自己要做的事

```bash
grep -rn "TODO(成員2)" app/
```

每個 TODO 底下都寫了要做哪幾步、為什麼那樣做、坑在哪裡。

### 前端專用、後端不實作的路由

- `POST /api/auth/switch`
  示範模式的切換身分鈕。**後端絕對不可以實作這支** —— 讓任何人任意切換身分等於把整套權限系統作廢。接上真後端之後，這個鈕要換成正常的登入登出。

---

## 環境變數

| 變數 | 必填 | 說明 |
|---|---|---|
| `DATABASE_URL` | ✅ | PostgreSQL 連線字串 |
| `JWT_SECRET` | ✅ | 簽 JWT 用的密鑰。**絕對不可以 commit** |
| `ALLOWED_ORIGINS` | | 允許哪些前端網域，逗號分隔 |
| `MODEL_BASE_URL` | | 我們自己微調的模型服務網址。**留空會回假資料** |
| `ACCESS_TOKEN_MINUTES` | | access token 有效期，預設 30 分鐘 |
| `REFRESH_TOKEN_DAYS` | | refresh token 有效期，預設 14 天 |

`MODEL_BASE_URL` 留空時 `services/llm/parse.py` 會回傳**形狀正確的假資料**。
這是刻意的：第 1 週模型還沒訓練完，但前端已經要串了。
等模型好了把網址填上去，其他程式碼一行都不用改。

`.env` 已經寫進 `.gitignore`，**不會被 commit**。
Render 上的 `JWT_SECRET` 和 `MODEL_BASE_URL` 是在後台手動填的
（`render.yaml` 裡標 `sync: false` 的那兩個）。

---

## 資料庫結構變更（Alembic）

改了 `models/` 底下的欄位之後：

```bash
alembic revision --autogenerate -m "說明這次改了什麼"
alembic upgrade head
```

**產生出來的檔案一定要自己打開看過再套用。** autogenerate 不是萬能的，
改欄位型別、改名稱這類操作它常常會產生錯的東西（例如把「改名」
判斷成「刪掉舊的、加一個新的」，那會把資料全部弄丟）。

---

## 常見問題

**前端 console 出現 `blocked by CORS policy`**
→ `ALLOWED_ORIGINS` 沒填對。網址要完整（含 `https://`），結尾不要加斜線。

**啟動時噴 `ValidationError: database_url Field required`**
→ `.env` 沒建立，或是少了必填變數。這是 `config.py` 刻意的設計：
**寧可在啟動時就失敗，也不要等使用者按下按鈕才發現設定是空的。**

**路由回 501**
→ 那支還沒實作，去找對應的 `TODO`。這是正常的，不是 bug。

**改了程式但沒生效**
→ 確認啟動時有加 `--reload`。
