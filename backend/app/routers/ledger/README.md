# 成員2 · 記帳 — 開發說明

> **這份講「怎麼動手」。每一支路由要做什麼、收什麼、回什麼，寫在那一支自己的說明字串裡**
> （就在這個資料夾的 .py 檔案裡），這裡不重複。
>
> 由 `backend/tools/sync_devguide.py` 從 `app/ownership.py` 產生，**不要直接改這個檔案**。

---

## 0. 你負責什麼

| | |
|---|---|
| 領域 | 記帳 |
| 路由 | **19 支** |
| 分支 | `m2-ledger` |
| 你的資料夾 | `backend/app/routers/ledger/` |

負責「記一筆帳」這個動作，從文字進來到寫進資料庫。★ 這是整個系統的核心。
屬於你的：明細的增刪改查、段落解析、單句解析、確認後寫入、nlp_parses 的寫入。
⚠️ 明細的**修改與刪除只有本人可以**，監管者不行——監管是唯讀的。
  結算過的帳本裡的紀錄不能改、不能刪（409）。一次刪多筆（DELETE /api/transactions?ids=）全部成功或全部不動。
新增一筆時要順手寫一則通知給監管者（成員4 的 notifications 表）。
帳本也在這裡：一本帳就是「這筆算在哪」的容器，跟記帳同一個脈絡。
常設帳本沒有結束；活動帳本有結束日，到了由建立者手動結算，之後唯讀（不能再記，回 409）。
⚠️ 結算**不搬動任何一筆紀錄**，只是把那本帳標記結束。
結算過的活動帳本可以封存（可復原）或移除（帳本不見、不能復原，紀錄一筆都不刪）。
  規則在 toolkit/ledger.py。
⚠️ 帳本成員是可見範圍的其中一條路，但規則不要自己寫——
  一律呼叫 toolkit/scope.py，有測試擋著重寫。
分類也在這裡：它是記帳時要選的欄位，統計只是拿它分組。
不屬於你的：統計加總（那是成員3，前端和這裡都不做任何加總）。

**你獨佔的檔案**（別人不會動，你也只動這些）：

- `app/routers/ledger/__init__.py`
- `app/routers/ledger/transactions.py`
- `app/routers/ledger/nlp.py`
- `app/routers/ledger/categories.py`
- `app/routers/ledger/groups.py`
- `app/models/category.py`
- `app/models/group.py`
- `app/schemas/group.py`
- `app/services/evaluation.py`
- `app/models/transaction.py`
- `app/models/nlp.py`
- `app/schemas/transaction.py`
- `app/schemas/nlp.py`
- `app/services/llm/parse.py`


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
| **以前跑過 `run.py`**（`backend/.env` 還寫著舊的 SQLite） | 自動換成 PostgreSQL 並印出說明，之後就需要 Docker。舊資料留在 `backend/dev.db`，不會再用到 |

這顆資料庫只在你自己的電腦上，跟其他組員、跟線上網站都無關。
關掉 `run.py` 不會關掉它，資料也都還在；想清空重來就 `python run.py --reset`。

### 你的帳號

`run.py` 會自動建好五個開發用帳號，**你的是這一個**：

| | |
|---|---|
| 帳號 | `ledger@fambudget.tw` |
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
git switch -c m2-ledger
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

**① 打開 `backend/app/routers/ledger/` 裡的檔案，找到那一支。**

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
pytest tests/routes/test_transactions.py tests/routes/test_nlp.py tests/routes/test_groups.py -q                 # 只跑你這一塊
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

> 段落切分策略、欄位抽取 prompt、few-shot 範例的挑選、低信心的判準。切分比抽欄位更難，而且切錯比抽錯更難發現。

你的模型工作是**段落切分與欄位抽取**。評估的重點順序不要弄反：

1. **切分比抽欄位難，而且切錯更難發現**——把兩筆合成一筆，金額看起來還是「合理的數字」
2. 所以每一列都要回 `span`（它對應原句的哪一段），人才驗得出來切對沒有
3. 抽不到的欄位回 `null` 並放進 `missing`，**不要猜**——猜錯會直接變成一筆錯帳
4. 低信心的判準要有數字（`conf` 多少以下算低），而且要能說明怎麼訂出來的

⚠️ 留出集的標註由成員4 做（他負責評測），你負責的是 prompt 與 few-shot 範例怎麼挑。

---

## 7. 先做哪幾支

分類清單（`GET /api/categories`）是**跨三個人的相依**：成員3 統計要拿它分組、成員4 評測要拿它當標籤、你自己寫 prompt 也要把分類名稱餵進去。第一週就要做完。

| 順序 | 路由 | 為什麼先做 |
|---|---|---|
| 1 | `GET /api/categories` | **成員3 分組、成員4 評測、你自己寫 prompt 都要用**，最先做 |
| 2 | `GET /api/transactions` | 做完就看得到畫面，後面每一支都靠它驗收 |
| 3 | `POST /api/transactions` | 先讓手動記帳能寫進去，再回頭做段落解析 |

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
