# 成員1 · 認證 — 開發說明

> **這份講「怎麼動手」。每一支路由要做什麼、收什麼、回什麼，寫在那一支自己的說明字串裡**
> （就在這個資料夾的 .py 檔案裡），這裡不重複。
>
> 由 `backend/tools/sync_devguide.py` 從 `app/ownership.py` 產生，**不要直接改這個檔案**。

---

## 0. 你負責什麼

| | |
|---|---|
| 領域 | 認證 |
| 路由 | **19 支** |
| 分支 | `m1-auth` |
| 你的資料夾 | `backend/app/routers/auth/` |

負責「你是誰」。
屬於你的：註冊登入登出、密碼、忘記密碼、JWT、工作階段、個人資料與大頭貼、介面主題。
註冊只問名字、email、密碼；每月存款目標、理財習慣、主題在註冊後的個人化設定問，
  走完（或全部跳過）用 PATCH /api/auth/me 的 onboarded 設 users.onboarded_at。
忘記密碼：toolkit/password_reset.py 產一次性連結（只存雜湊、30 分鐘），toolkit/mailer.py 用 Brevo 寄出。
⚠️ 申請重設時，有沒有這個帳號都回同一句話——不然這支就是帳號列舉工具。
地基（資料庫連線、設定、依賴注入、密碼雜湊、JWT 實作）已經在 toolkit/ 裡寫好了，直接用就好，不用再造一次。
停權也在這裡：平台管理員（master）可以停掉違規帳號。
⚠️ **停權是關門，不是配鑰匙。** 他停得了人，但讀不到任何一筆帳——
  一個能讀全系統消費明細的帳號，比家長越權嚴重得多。
⚠️ 停權**不刪任何資料**：擋登入、擋寫入，紀錄全部留著。
⚠️ 每一次停權都要寫進 audit_logs，而且要有理由。
  沒有稽核的停權就是任意封鎖，被停的人也沒東西可以申訴。
verify-password 給「重大操作前再確認一次」用：驗證密碼但不發新的 token。⚠️ 一定要做速率限制，否則它就是一支免費的密碼嘗試器。
不屬於你的：家庭角色與監管關係（那是成員4）。users 表存的是登入身分，family_members 表才是家庭角色，兩者刻意分開。

**你獨佔的檔案**（別人不會動，你也只動這些）：

- `app/routers/auth/__init__.py`
- `app/routers/auth/auth.py`
- `app/routers/auth/admin.py`
- `app/models/user.py`
- `app/schemas/auth.py`


**別人會等你的共用元件**（要最先完成）：

- `app/services/llm/client.py`
- `app/guards.py`
- `app/cli.py`
- `app/routers/_stub.py`
- `app/models/_types.py`

---

## 1. 第一次：把環境跑起來

在**專案最外層**（跟 `backend/`、`frontend/` 同一層）：

```bash
python run.py
```

第一次會自己裝套件、建 `backend/.env`、建資料表、放入系統預設分類，然後把前後端一起起來：

| | 網址 |
|---|---|
| 前端 | <http://localhost:5174/?api=http://localhost:8000> |
| **API 文件（你最常用的）** | <http://localhost:8000/docs> |

⚠️ 前端不要用 VS Code 的 Live Server，也不要直接點開 `index.html`——
後端的 CORS 會擋住，而且 `file://` 不算 localhost。一律用 `run.py` 起的那個網址。

停掉：在那個視窗按 `Ctrl+C`。

### 你的帳號

`run.py` 會自動建好五個開發用帳號，**你的是這一個**：

| | |
|---|---|
| 帳號 | `auth@fambudget.tw` |
| 密碼 | `abcd1234` |

另外四個是 `auth@` `ledger@` `analytics@` `access@` `admin@`（密碼一樣），
要測家庭、監管、權限的時候就拿它們互相加成一家人。

密碼忘了、或自己改壞了，重跑一次就會重設回來：

```bash
cd backend
python -m app.cli seed-team
```

⚠️ 這幾個帳號**只在自己的電腦上**，而且 `APP_ENV=production` 時指令會直接拒絕——
密碼是公開寫在文件裡的，正式環境有這種帳號等於沒有密碼。

---

## 2. 開自己的分支

```bash
git switch -c m1-auth
```

只動自己資料夾裡的檔案。要改別人的、或改 `app/main.py`、`app/ownership.py`
這種沒有單一主人的檔案，**先在群組講一聲**。

---

## 3. 做一支路由：五步

```bash
cd backend
python -m app.ownership        # 看自己還差哪幾支
```

> **登入那幾支（`app/routers/auth/auth.py`）已經先做好了**，所以你一開始就登得進去、
> 看得到自己的頁面，不用等別人。其他人的路由還沒做的話，畫面上會說是哪一支、誰負責。

**① 打開 `backend/app/routers/auth/` 裡的檔案，找到那一支。**

**② 讀它的說明字串——那就是這一支的規格書**，十一個段落：

```
【這支做什麼】【前端怎麼打】【誰能打】【請求】【成功回應】【錯誤回應】
【會用到的資料表】【每一步用的工具與資料庫方法】【寫法步驟】
【完整寫法】  ← 可以直接貼上去的整段程式（import ＋ 整個函式）
【做完怎麼確認】
```

**③ 把 `raise not_ready(...)` 換成【完整寫法】的第二步，然後拿掉 `@stub`。**

第一步是這個檔案最上面的 import 區塊（同一個檔案裡每一支都一樣，貼一次就好）。
有第三步的話，那是要換掉的 service 函式，照著換。

**④ 存檔。** uvicorn 會自己重載，不用重開。

**⑤ 到 <http://localhost:8000/docs> 把那一支點開、按 Try it out、送出。**
不用寫前端、不用 Postman。說明字串最後一段【做完怎麼確認】寫了要看什麼。

> 說明字串裡的程式**有測試在跑**（`tests/routes/`），所以它不會跟實作走散——
> 貼上去是對的，不是參考用的虛擬碼。

---

## 4. 怎麼看到自己寫進去的資料

三種，由快到慢：

**① 直接查資料庫**（最快，不用裝任何工具）

```bash
cd backend
python -m app.cli db                                        # 每張表各幾筆
python -m app.cli db "SELECT id, email FROM users"
python -m app.cli db "SELECT * FROM transactions ORDER BY id DESC LIMIT 5"
```

只能查（`SELECT` / `PRAGMA` / `WITH`），不能改——免得一行 `DELETE` 把自己的資料清掉。

**② API 文件頁試打** <http://localhost:8000/docs>

先打 `POST /api/auth/login` 拿到 `accessToken`，按右上角 **Authorize** 貼進去，
之後每一支都會帶著身分。**這是你最常用的驗收方式。**

**③ 前端畫面** <http://localhost:5174/?api=http://localhost:8000>

真的長什麼樣。你那一支還沒做的時候，畫面會直接說「後端還沒做這一支（HTTP 501）」
和負責人，左下角的錯誤匣還會把這一輪所有出錯的呼叫列出來（可以整個複製）。

### 資料庫本身

| | |
|---|---|
| 你本機的 | SQLite，就是 `backend/dev.db` 這個檔案 |
| 正式環境 | PostgreSQL（Render 上的 `fambudget-db`） |
| 跑測試時 | 記憶體裡的 SQLite，每個測試一份，不會污染你的 dev.db |

兩種資料庫的差異都吃在 `app/toolkit/db.py`（SQLite 的外鍵檢查已經打開），
所以本機寫得對，上去也會對。

```bash
python run.py --reset      # 資料亂了，砍掉重建（只影響你本機）
```

**改資料表結構**要走 Alembic，不可以手動改資料庫：

```bash
cd backend
alembic revision --autogenerate -m "what changed"   # 說明用英文，檔名才不會變亂碼
alembic upgrade head
```

⚠️ 產生出來的檔案**一定要自己打開看過**再套用。autogenerate 常把「改欄位名稱」
判斷成「刪掉舊的、加一個新的」，那會把資料全部弄丟。
而且欄位要**三處一起改**：`frontend/js/data.js` 的 schema → `models/` → 遷移檔，
`tests/test_backend_core.py` 會檢查三邊一致。

---

## 5. 怎麼測試

```bash
cd backend
pytest                                    # 全部（別人的也會跑，確認你沒弄壞）
pytest tests/routes/test_auth.py -q                 # 只跑你這一塊
```

`tests/routes/` 的每一個情境都會跑**兩次**：

| 對象 | 意思 |
|---|---|
| `[說明]` | 拿**說明字串裡的【完整寫法】**去跑。這半邊本來就會過 |
| `[你的]` | 跑**你真的寫的那一支**。還標著 `@stub` 時自動跳過，拿掉之後就開始跑 |

所以做完一支之後，只要看 `[你的]` 那半邊有沒有綠就好：

```bash
pytest tests/routes -k "你的" -q
```

⚠️ **不要等到最後才測。** 每做完一支就跑一次，累積起來才找不到是哪一步壞的。

---

## 6. 你的 LLM 工作與評估

> 共用的模型呼叫層：逾時、重試、把模型回傳的 JSON 交給 Pydantic 驗證。成員2 和成員3 都會呼叫它，所以第 1 週要先做出來。

你的模型工作是**共用的呼叫層**，不是模型本身，所以「評估」評的是它夠不夠耐操：

1. 模型服務沒設定（`MODEL_BASE_URL` 留空）→ 回 `None`，路由回 503，不可以讓整支炸掉
2. 模型逾時、回 500、回一段不是 JSON 的字 → 都要變成同一種 `ModelError`，呼叫的人（成員2、成員3）只要處理一種例外
3. 模型回的 JSON 少欄位、型別不對 → Pydantic 擋下來，**不可以讓髒資料進資料庫**
4. 重試幾次、每次間隔多久，要有數字，而且要能在報告裡說明為什麼是這個數字

---

## 7. 先做哪幾支

你是四個人裡唯一會擋住別人的：**登入沒做完，另外三個人看不到自己的頁面**。先把註冊、登入、取得自己三支打通，其他人就能開工了。

| 順序 | 路由 | 為什麼先做 |
|---|---|---|
| 1 | `POST /api/auth/register` | 沒有它就沒有帳號，剩下 69 支都沒得測 |
| 2 | `POST /api/auth/login` | **其他三個人被你擋住**——登入不能用，他們連自己的頁面都打不開 |
| 3 | `GET /api/auth/me` | 前端每次開頁面都先打這一支 |

做完這幾支之後，剩下的可以照自己的節奏推。

---

## 8. 卡住的時候

| 症狀 | 原因與解法 |
|---|---|
| 啟動時 `ValidationError: database_url Field required` | `backend/.env` 沒建立。跑 `python run.py`，或 `cd backend && python -m app.cli init-env` |
| 畫面 console 出現 `blocked by CORS policy` | 前端的網址不在 `ALLOWED_ORIGINS` 裡。用 `run.py` 起的網址就不會遇到 |
| 路由回 501 | 那支還沒實作（`@stub` 還在）。**這是正常的，不是 bug** |
| 畫面說「後端出錯（HTTP 500）」 | 你的路由丟了沒接住的例外。完整追蹤在 uvicorn 的視窗裡。規則類的錯誤請用 `toolkit/errors.py` 轉成 400／403／409 |
| 埠號被占用 | 上一次的視窗沒關。`netstat -ano \| findstr :8000` 找出來，或 `python run.py --port 5555 --api-port 8001` |
| `alembic` 噴 `UnicodeDecodeError: 'cp950'` | 有人在 `alembic.ini` 裡寫了中文。那個檔案只能有英文 |
| 改了程式沒生效 | `run.py` 起的 uvicorn 有 `--reload`，存檔就會重載；沒反應就看那個視窗有沒有錯誤 |

**還是卡住**：把左下角錯誤匣的「複製全部」貼到群組，裡面有函式、路由、狀態碼、負責人。

---

## 你會用到的工具（都寫好測好了，不要重寫）

| 想做的事 | 用哪個 |
|---|---|
| 增刪改查 | `app/toolkit/crud.py` 的 `get` `find` `save` `remove` `count` `to_dict` |
| 擋身分與權限 | `app/guards.py` 的 `@login_required` `@parent_required` `Depends(own(...))` … |
| 回錯誤 | `app/toolkit/errors.py` 的 `bad_request()` `forbidden()` `not_found()` `conflict()` |
| 好幾步要一起成功 | `app/toolkit/db.py` 的 `session_scope(db)` |
| 金額、月份、可見範圍 | `toolkit/money.py`、`period.py`、`scope.py` |

完整清單與例子在 [`backend/README.md`](../../../README.md)，
每一支路由的輸入輸出在 [`docs/02-前後端串接契約.md`](../../../../docs/02-前後端串接契約.md)。
