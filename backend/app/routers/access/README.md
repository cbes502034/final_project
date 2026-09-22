# 成員4 · 家庭 — 開發說明

> **這份講「怎麼動手」。每一支路由要做什麼、收什麼、回什麼，寫在那一支自己的說明字串裡**
> （就在這個資料夾的 .py 檔案裡），這裡不重複。
>
> 由 `backend/tools/sync_devguide.py` 從 `app/ownership.py` 產生，**不要直接改這個檔案**。

---

## 0. 你負責什麼

| | |
|---|---|
| 領域 | 家庭 |
| 路由 | **21 支** |
| 分支 | `m4-access` |
| 你的資料夾 | `backend/app/routers/access/` |

負責「誰在這個家庭裡」以及「誰看得到誰的資料」。
屬於你的：家庭、成員角色、家庭綁定（邀請碼與用帳號邀請）、監管關係、權限計算、唯讀監管檢視與即時通知、零用金、稽核紀錄。
家庭綁定：家長建立家庭，用邀請碼或輸入對方 email 邀請家人加入。
⚠️ 身分（家長／子女）由發邀請的家長決定，被邀請的人不能自己選。
⚠️ 用帳號找人只接受完整 email，不做模糊搜尋，也不回任何財務資料。
⚠️ 邀請碼只能用一次、七天過期、資料庫只存雜湊。工具在 toolkit/family.py。
移出、退出、解散：家長只能移除子女，另一位家長只能自己退出；唯一的家長在家裡還有人時不能退出，
  改用解散（DELETE /api/family，只有唯一的家長能解散）。
角色：家長可以把子女設為家長；不能把另一位家長降成子女，只有他自己能調整。
監管：家長按「開始照看」建立，監管人一定是自己；監管人或同家的家長可以解除，被照看的人不行。
  規則都在 toolkit/family.py。
⚠️ 離開不刪紀錄，但監管關係、共用帳本、他送出的邀請要在同一個交易裡一起收掉。
⚠️ 監管是**唯讀**的：看得到，但不能改、不能刪，更不能登入對方的帳號。
⚠️ **可見範圍是兩條路的聯集，過一條就看得到**：
  A. 這筆是誰記的 → 自己 ＋ 我監管的人 ＋ 同家庭的其他家長，**跨所有帳本**
     （家長之間互相看得到；家長看子女一樣要有監管關係）
  B. 這筆在哪一本帳 → group_members（我在不在那本帳裡）
  A 是監管：不該被帳本切斷，否則被監管的人另開一本帳就躲掉了。
  B 是分享：把誰加進帳本，就是選擇讓他看到那一本。
⚠️ 寫成 AND 就變回交集了，那是早期版本的錯。規則寫在 toolkit/scope.py。
帳本本身（開、改、封存、結算、成員）屬於成員2——那是記帳的容器。
成員4 只管**可見範圍怎麼算**，不管帳本的 CRUD。
零用金也在這裡：家長每個月給某個被監管者多少錢。
⚠️ **零用金是設定，不是一筆支出紀錄。**
  家長記一筆「給小孩 3000」，小孩再把那 3000 花掉記成支出，
  家庭總支出就會變成 6000——同一筆錢被算了兩次。
  正確的算法是：**子女的支出算進家庭支出，子女的收入不算進家庭收入**，
  零用金只拿來跟「他實際花了多少」做對照。
不屬於你的：登入本身（那是成員1）。成員1 回答「你是誰」，成員4 回答「你能看到什麼」。

**你獨佔的檔案**（別人不會動，你也只動這些）：

- `app/routers/access/__init__.py`
- `app/routers/access/family.py`
- `app/routers/access/notifications.py`
- `app/models/family.py`
- `app/models/guardianship.py`
- `app/models/notification.py`
- `app/models/audit.py`
- `app/schemas/family.py`


**別人會等你的共用元件**（要最先完成）：

- `app/services/permission.py`

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
| 帳號 | `access@fambudget.tw` |
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
git switch -c m4-access
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

**① 打開 `backend/app/routers/access/` 裡的檔案，找到那一支。**

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
python -m app.cli db "SELECT id, email FROM users"
python -m app.cli db "SELECT * FROM transactions ORDER BY id DESC LIMIT 5"
```

只能查（`SELECT` / `PRAGMA` / `WITH`），不能改——免得一行 `DELETE` 把自己的資料清掉。

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
pytest tests/routes/test_family.py -q                 # 只跑你這一塊
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

> 模型評測：建立人工標註的留出集、跑零樣本 vs few-shot 對照、算一次輸入完全正確率與分類 Macro-F1。**留出集必須 100% 人工標註**，否則量到的是「多像那個老師」而不是「多正確」。

你的模型工作是**評測**，而且是四個人裡唯一產出數字的：

1. **留出集必須 100% 人工標註**——用模型標出來的答案去評模型，量到的是「多像那個老師」，不是「多正確」
2. 零樣本 vs few-shot 要跑同一份留出集，才比得出來
3. 兩個指標：**一次輸入完全正確率**（整句的每一欄都對才算對）與**分類 Macro-F1**
4. Macro（不是 Micro）：筆數少的分類不能被餐飲、交通洗掉

工具在 `app/services/evaluation.py`（那個檔案掛在成員2 名下，要動先講一聲）。

---

## 7. 先做哪幾支

`services/permission.py` 是你的共用元件（成員2、成員3 查資料都會用到可見範圍）。建立家庭與邀請做完之後，你們四個人才有辦法互相加成一家人來測。

| 順序 | 路由 | 為什麼先做 |
|---|---|---|
| 1 | `GET /api/family` | 前端每一頁的「我 / 全家」切換都要它 |
| 2 | `POST /api/family` | 沒有家庭就沒有成員、沒有監管，後面全部卡住 |
| 3 | `POST /api/family/invite` | 邀請碼做完，四個人就能互相加成一家測試 |

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
