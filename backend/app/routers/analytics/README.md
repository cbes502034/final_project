# 成員3 · 數字 — 開發說明

> **這份講「怎麼動手」。每一支路由要做什麼、收什麼、回什麼，寫在那一支自己的說明字串裡**
> （就在這個資料夾的 .py 檔案裡），這裡不重複。
>
> 由 `backend/tools/sync_devguide.py` 從 `app/ownership.py` 產生，**不要直接改這個檔案**。

---

## 0. 你負責什麼

| | |
|---|---|
| 領域 | 數字 |
| 路由 | **11 支** |
| 分支 | `m3-analytics` |
| 你的資料夾 | `backend/app/routers/analytics/` |

負責所有「算出來的東西」，以及把那些數字講成人話。
屬於你的：月年統計、預算、每月存款目標、階段性提醒的門檻、財務建議。
**整個系統只有這裡加總錢** —— 模型不算，前端只做衍生（結餘、比例、預算百分比）。
  GET /api/stats、GET /api/savings-goal 已經拿掉：前端從 summary、savings-goals 自己取。
每月存款目標可以**分群組設定**：不帶 groupId 是整體目標，帶了就是那個群組自己的目標。
階段性提醒也在這裡：使用者自己設幾個百分比門檻（例如 50%／80%／100%），支出跨過門檻就發一則通知。
⚠️ **算出要發通知是成員3，真的寫進 notifications 是成員4。**
不屬於你的：明細的寫入（那是成員2）；決定要算哪些人（那是成員4 的 permission）。

**你獨佔的檔案**（別人不會動，你也只動這些）：

- `app/routers/analytics/__init__.py`
- `app/routers/analytics/stats.py`
- `app/routers/analytics/alerts.py`
- `app/models/alert.py`
- `app/routers/analytics/budgets.py`
- `app/routers/analytics/advices.py`
- `app/models/budget.py`
- `app/models/advice.py`
- `app/schemas/stats.py`
- `app/schemas/advice.py`
- `app/services/llm/advice.py`


**別人會等你的共用元件**（要最先完成）：

- `app/services/analytics.py`

---

## 1. 第一次：把環境跑起來

先裝好兩樣東西：**Python 3.10 以上**、**Docker Desktop**（本機的資料庫跟正式環境一樣是 PostgreSQL，跑在 Docker 裡）。
每次開發前先把 Docker Desktop 打開，然後在**專案最外層**（跟 `backend/`、`frontend/` 同一層）：

```bash
python run.py
```

第一次會自己裝套件、建 `backend/.env`、用 Docker 開 PostgreSQL、建資料表、放入系統預設分類與開發用帳號，
然後把前後端一起起來：

| | 網址 |
|---|---|
| 前端 | <http://localhost:5174/?api=http://localhost:8000> |
| **API 文件（你最常用的）** | <http://localhost:8000/docs> |

⚠️ 前端不要用 VS Code 的 Live Server，也不要直接點開 `index.html`——
後端的 CORS 會擋住，而且 `file://` 不算 localhost。一律用 `run.py` 起的那個網址。

停掉：在那個視窗按 `Ctrl+C`。

### 資料庫會自動建好嗎

會，只要 **Docker Desktop 是打開的**。不用自己裝 PostgreSQL，也不用設定任何東西：

| 你的狀況 | `python run.py` 會怎麼做 |
|---|---|
| **第一次**，Docker 開著 | 下載 PostgreSQL → 建好資料庫（容器 `fambudget-db-1`）→ 建資料表 → 放入預設分類與開發帳號。大約 1～2 分鐘，要有網路 |
| **之後每次**，Docker 開著 | 沿用同一顆資料庫，**不會重建**，上次的資料都還在。十幾秒就起來 |
| 裝了 Docker，**但沒打開** | 停在第 3 步，提醒你先打開 Docker Desktop |
| **沒裝 Docker** | 停在第 3 步，給你 Docker Desktop 的下載網址 |

這顆資料庫只在你自己的電腦上，跟其他組員、跟線上網站都無關。
關掉 `run.py` 不會關掉它，資料也都還在；想清空重來就 `python run.py --reset`。

### 你的帳號

`run.py` 會自動建好五個開發用帳號，**你的是這一個**：

| | |
|---|---|
| 帳號 | `analytics@fambudget.tw` |
| 密碼 | `abcd1234` |

五個帳號全組都一樣，每個人的電腦上都有同樣這五個，密碼都是 `abcd1234`：

| 帳號 | 誰用 |
|---|---|
| `auth@fambudget.tw` | 成員1 · 認證 |
| `ledger@fambudget.tw` | 成員2 · 記帳 |
| `analytics@fambudget.tw` | 成員3 · 數字 |
| `access@fambudget.tw` | 成員4 · 家庭 |
| `admin@fambudget.tw` | 平台管理員（測 admin/ 那三支用） |

要測家庭、監管、權限的時候，就拿它們在自己的資料庫裡互相加成一家人。

⚠️ **每次 `python run.py`，這五個帳號都會被重設回原樣**：密碼、名字、主題、平台管理員身分、停權狀態。
所以你在測「改密碼」「停權」這類功能時改到它們，下次啟動就會恢復——這是刻意的，
免得帳號被測壞之後登不進去。它們身上的其他資料（記的帳、家庭、帳本）不會被動到。
不想重啟、只想馬上把帳號重設回來的話：

```bash
cd backend
python -m app.cli seed-team
```

⚠️ 這幾個帳號**只在自己的電腦上**，而且 `APP_ENV=production` 時指令會直接拒絕——
密碼是公開寫在文件裡的，正式環境有這種帳號等於沒有密碼。

---

## 2. 開自己的分支

```bash
git switch -c m3-analytics
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

**① 打開 `backend/app/routers/analytics/` 裡的檔案，找到那一支。**

**② 讀它的說明字串——那就是這一支的規格書**，十一個段落：

```
【這支做什麼】【前端怎麼打】【誰能打】【請求】【成功回應】【錯誤回應】
【會用到的資料表】【每一步用的工具與資料庫方法】【寫法步驟】
【完整寫法】  ← 第二步就是要貼上去的程式
【做完怎麼確認】
```

**③ 刪掉那一支上面的 `@stub`，再把 `raise not_ready(...)` 那一行換成【完整寫法】的第二步。**

就這兩個動作。裝飾器、函式名稱、參數、說明字串、檔案最上面的 import **都已經是最終版本，不用動**
（第一步只是讓你對照 import 長什麼樣，已經放好了）。
⚠️ 說明字串不要刪：測試會檢查每一支都要有它，刪了會紅燈。
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
python -m app.cli db transactions                           # 那張表最新的 10 筆（第一行就是欄位名稱）
python -m app.cli db "SELECT id, email FROM users"          # 自己寫查詢
```

只能查（`SELECT` / `WITH`），不能改——免得一行 `DELETE` 把自己的資料清掉。

**② API 文件頁試打** <http://localhost:8000/docs>

先打 `POST /api/auth/login` 拿到 `accessToken`，按右上角 **Authorize** 貼進去，
之後每一支都會帶著身分。**這是你最常用的驗收方式。**

**③ 前端畫面** <http://localhost:5174/?api=http://localhost:8000>

真的長什麼樣。你那一支還沒做的時候，畫面會直接說「後端還沒做這一支（HTTP 501）」
和負責人。左下角那張表會列出這一頁打過的每一支：**你那一支做對了就亮綠燈**，
還沒做或出錯是紅燈（可以整個複製）。做完一支、重新整理，看它有沒有變綠。

### 資料庫本身

| | |
|---|---|
| 你本機的 | **PostgreSQL 16**，跑在 Docker 裡（`docker-compose.yml` 的 `db`），`python run.py` 會自己開 |
| 正式環境 | PostgreSQL（Render 上的 `fambudget-db`） |
| 跑測試時 | 記憶體裡的 SQLite，每個測試一份、跑得快、不需要 Docker，也不會動到你的資料 |

本機跟正式環境是同一種資料庫，所以本機寫得對，上去也會對。
**開發前先把 Docker Desktop 打開**，不然 `python run.py` 會停在「啟動資料庫」那一步並告訴你。

資料存在 Docker 的 volume 裡，關掉 `run.py`、甚至重開機都還在。

```bash
python run.py --reset      # 資料亂了，清空重建（只影響你本機）
docker compose stop db     # 不寫程式的時候想把 PostgreSQL 關掉（在專案最外層跑）
```

想用圖形介面看資料的話：DBeaver、pgAdmin、VS Code 的 PostgreSQL 擴充套件都可以，連線資訊是
`localhost:5432`，資料庫 `fambudget`，帳號 `fambudget`，密碼 `devpassword`（只在你電腦上，不是機密）。

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
pytest tests/routes/test_analytics.py -q                 # 只跑你這一塊
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

> 財務建議的 prompt 與邊界規則。順序不能顛倒：先用 analytics 算好數字，再餵給模型敘述，模型不做任何算術。

你的模型工作是**財務建議**。順序不能顛倒，這是評估時最容易被問的一題：

1. `analytics.py` 從資料庫算出所有數字 → 2. 把**算好的**數字交給模型只做敘述 →
3. Pydantic 驗證 → 4. 存進 advices

**模型不做任何算術。** 評估要拿得出證據：

· 建議裡出現的每一個數字，都能在 `basis` 裡對回 summary 的哪一欄
· 同一批數字跑兩次，講法可以不同，**數字不可以不同**
· 模型叫不動時回 503（不是 500），前端才知道要不要自己頂著

---

## 7. 先做哪幾支

`services/analytics.py` 是你的共用元件，`GET /api/summary` 就是它的第一個出口。先把加總寫對，後面的預算、提醒、建議全部是拿同一批數字換個形狀。

| 順序 | 路由 | 為什麼先做 |
|---|---|---|
| 1 | `GET /api/summary` | 總覽與統計兩頁都靠它；做完畫面立刻活起來 |
| 2 | `GET /api/budgets` | 同一套加總邏輯的延伸，順手就做完了 |
| 3 | `GET /api/savings-goals` | 存錢目標，個人資料頁在等 |

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

**還是卡住**：把左下角那張表的「複製全部」貼到群組，裡面有函式、路由、狀態碼、負責人。

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
