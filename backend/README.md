# backend — FastAPI 後端

> 第一次碰 FastAPI？**先讀站上的 [FastAPI 說明書](https://llm-capstone-top20.onrender.com/docs/fastapi.html)**，
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

| 成員 | 領域 | 主要檔案 | 路由編號 |
|---|---|---|---|
| **成員1** | 帳號與權限 | `routers/auth.py`、`routers/family.py`、`core/*`、`services/permission.py`、`services/llm.py` | 1–17 |
| **成員2** | 記帳 | `routers/transactions.py`、`routers/nlp.py` ★ | 18–27 |
| **成員3** | 統計與預算 | `routers/stats.py`、`routers/budgets.py`、`services/analytics.py` | 28–33 |
| **成員4** | 財務建議 | `routers/advices.py` | 34–35 |

★ `routers/nlp.py` 是整個系統的核心。

**成員1 另外負責兩個大家共用的檔案**（`core/` 與 `services/llm.py`、
`services/permission.py`），這兩塊在第 1 週要優先完成，
因為其他三個人都要靠它們。

---

## 找到自己要做的事

所有待辦都用 `TODO(負責人)` 標記，直接搜尋就好：

```bash
grep -rn "TODO(成員2)" app/
```

每個 TODO 底下都寫了要做哪幾步、為什麼要那樣做、常見的坑在哪裡。

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

`MODEL_BASE_URL` 留空時 `services/llm.py` 會回傳**形狀正確的假資料**。
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
