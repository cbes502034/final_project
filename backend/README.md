# backend — FastAPI 後端

> 第一次碰 FastAPI？**先讀站上的 [FastAPI 說明書](https://fambudget-web.onrender.com/docs/fastapi.html)**，
> 那份是從零開始教的。這份 README 假設你已經讀過了。

---

> **動工前先讀 [`../docs/02-前後端串接契約.md`](../docs/02-前後端串接契約.md)。**
> 那份寫清楚每一支路由「前端送什麼、你要吐什麼、前端拿去幹嘛」，
> 而且是從前端程式實際跑出來的，不是手寫的。
> 裡面開頭有**四件已經定案的事**（ID 回字串、人身上不放收支、前端代勞、錯誤怎麼回），先讀那一段。

## 三十秒跑起來

```bash
cd backend
pip install -r requirements.txt
python -m app.cli init-env        # 從 .env.example 建出 .env，順便產生 JWT_SECRET
python -m app.cli check-config    # 列出每一段設定填了沒、沒填會怎樣
alembic upgrade head              # 建表（本機沒有 PostgreSQL：DATABASE_URL 先填 sqlite:///./dev.db）
python -m app.cli init-db         # 放入系統預設分類
uvicorn app.main:app --reload
```

打開 <http://localhost:8000/docs> ——
FastAPI 自動產生的互動式文件，**可以直接在上面送出請求試打**，
不需要寫前端，也不需要 Postman。70 支路由都在上面，還沒做的回 501。

看自己剛剛寫進去的資料（不用裝任何工具）：

```bash
python -m app.cli db                                       # 每張表各幾筆
python -m app.cli db "SELECT id, email FROM users"         # 只能查，不能改
```

跑測試：

```bash
pytest
```

---

## 目錄怎麼看

```
backend/
├── app/
│   ├── main.py            ← 入口。只負責組裝（CORS、錯誤處理、掛上 routers/ 的每一組）
│   ├── guards.py          ← 路由守衛：沒登入、被停權、角色不對、不是自己的資料，路由裡一行都不會跑
│   ├── cli.py             ← 小工具指令：init-env、check-config、init-db、make-admin、db
│   ├── ownership.py       ← 分工的單一事實來源
│   ├── catalog.py         ← 固定清單：角色、權限表、理財選項、系統分類（正本是 frontend/js/data.js）
│   │
│   ├── toolkit/           ← 寫好、測好的工具，直接用
│   │   ├── config.py        設定（依成員分段）
│   │   ├── db.py            資料庫連線：get_db、session_scope、@db_transaction
│   │   ├── crud.py          增刪改查：get、find、save、remove、to_dict
│   │   ├── errors.py        錯誤回應（400／401／403／404／409／422／501／503）
│   │   ├── deps.py          從 JWT 取出登入者、分頁參數
│   │   ├── tokens.py · passwords.py · password_reset.py · mailer.py
│   │   ├── scope.py         可見範圍的規則（監管 ∪ 同帳本）
│   │   ├── family.py · roles.py · ledger.py · alerts.py · notify.py
│   │   └── period.py · money.py · images.py · profile.py · theme.py
│   │
│   ├── models/            ← 資料庫長什麼樣（SQLAlchemy，20 張表，跟 data.js 的 schema 逐欄對齊）
│   ├── schemas/           ← API 收什麼（Pydantic），欄位名字跟前端送的一樣
│   ├── routers/           ← 路由。**一個領域一個資料夾，開自己那一個就好**
│   │                        每個資料夾裡都有 README.md，寫你那一塊怎麼開發
│   │   ├── auth/            成員1 · 認證     auth.py、admin.py
│   │   ├── ledger/          成員2 · 記帳     transactions.py、nlp.py、categories.py、groups.py
│   │   ├── analytics/       成員3 · 數字     stats.py、budgets.py、alerts.py、advices.py
│   │   ├── access/          成員4 · 家庭     family.py、notifications.py
│   │   └── _stub.py         共用：@stub 與 not_ready()（還沒做的回 501）
│   └── services/          ← 加總與模型：analytics、llm/（client、parse、advice）、permission、evaluation
│
├── alembic/               ← 資料庫結構的版本控制（versions/ 第一版就是 20 張表）
├── alembic.ini            ← ⚠️ 只能有英文（Windows 的 alembic 用 cp950 讀它）
├── tests/                 ← pytest；fixtures/ 放測試用的一家人與假後端
├── tools/                 ← sync_spec.py、sync_schema.py、sync_mindmap.py、sync_devguide.py：文件從程式產生
├── requirements.txt
├── Dockerfile             ← 啟動前先 alembic upgrade head
└── .env.example           ← 設定範本，依成員分段，機密一律留空
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

`routers/` 只做三件事：收請求、（守衛）驗權限、回結果。
規則寫在 `toolkit/`（例如 `family.require_can_dissolve()`），加總與模型寫在 `services/`。

這樣做測試時可以直接呼叫函式，
不必每次都起一個完整的 HTTP 請求，快很多也好寫很多。

---

## 寫一支路由的完整樣子

打開自己的檔案，找到那一支，**先讀它的說明字串**（那是這一支的規格書，最後兩段是「完整寫法」與「做完怎麼確認」），
再把 `raise not_ready(...)` 換掉、拿掉 `@stub`：

```python
from app.guards import parent_required
from app.models import FamilyMember, Guardianship
from app.toolkit import crud, errors, family
from app.toolkit.db import session_scope

@router.delete("/family", summary="解散家庭（唯一的家長）")
@parent_required                                  # ← 守衛：沒登入 401、不是家長 403，下面不用再判斷
def dissolve_family(me: User, db: Session = Depends(get_db)):
    others = crud.count(FamilyMember, {"family_id": me.family_id, "role": "parent",
                                       "status": "active", "user_id__ne": me.id}, db=db)
    try:
        family.require_can_dissolve(me.family_role, others)     # ← 規則在 toolkit，不在路由裡
    except ValueError as exc:
        raise errors.conflict(str(exc)) from exc

    with session_scope(db):                                    # ← 一起成功或一起失敗
        people = crud.find(FamilyMember, {"family_id": me.family_id, "status": "active"}, fields="user_id", db=db)
        crud.remove(Guardianship, {"or": [{"guardian_id__in": people}, {"ward_id__in": people}],
                                   "ended_at__isnull": True}, soft="ended_at", db=db)
        crud.save(FamilyMember, {"status": "removed"}, where={"family_id": me.family_id}, db=db)
        ...                                                    # 帳本互相移出、邀請作廢（契約那一節列了全部）
        db.commit()
    return {"dissolved": True, "released": len(people)}
```

### 增刪改查：`toolkit/crud.py`

五支就夠，**參數決定做什麼**（跟 MineMarket 的 `getUser({"token": t}, "token")` 同一個想法，但不綁表、不手拼 SQL）：

| 想做的事 | 寫法 |
|---|---|
| 拿一筆／只拿一個欄位 | `get(User, 3)`、`get(User, where={"email": e}, fields="id")` |
| 找不到直接回 404 | `get(Group, gid, missing=errors.not_found("找不到這本帳"))` |
| 篩選、排序、分頁 | `find(Transaction, {"user_id__in": users, "occurred_on__between": (a, b)}, order_by="-occurred_on", page=2, size=50)` |
| 只數筆數 | `find(Transaction, {"user_id": 3}, count=True)` 或 `count(...)` |
| 新增一筆／很多筆 | `save(Group, {...})`、`save(Transaction, [{...}, {...}])` |
| 改一筆／改很多筆 | `save(User, {"id": 3, "theme": "sky"})`、`save(Group, {"archived_at": now}, where={"id": 9})` |
| 有就改、沒有就新增 | `save(Budget, {"limit_amount": 8000}, where={...}, upsert=True)` |
| 刪除／軟刪除 | `remove(Transaction, {"id__in": ids, "user_id": me.id})`、`remove(Group, id=9, soft="archived_at")` |
| 回給前端 | `to_dict(tx, rename={"occurred_on": "date", "category_id": "cat"})`（id 轉字串、藏密碼雜湊） |

條件運算子：`__gte` `__gt` `__lte` `__lt` `__ne` `__in` `__notin` `__contains` `__icontains` `__startswith` `__endswith` `__isnull` `__between`，
還有 `{"or": [...]}`。欄位名字打錯直接丟 `ValueError` 講出是哪張表哪個欄位；**沒有條件的修改與刪除會被擋**（`allow_all=True` 才放行）。

每一支都收 `db=`：不傳就自己開交易、做完 commit；傳了就用你的、不 commit，交給外面決定（好幾步要一起成功時）。

### 路由守衛：`guards.py`

參考 MineMarket 的 `AuthDecorator.py`。擋下來回 401／403／404，路由裡的程式一行都不會跑：

| 守衛 | 擋什麼 |
|---|---|
| `@login_required` | 沒登入、token 壞掉、帳號不存在（401）；被停權（403） |
| `@guest_only` | 已經登入（400）。註冊用 |
| `@parent_required`／`@family_required` | 不是家長／還沒有家庭（403） |
| `@protect(family=False)` | 已經在家庭裡（409）。建立家庭用 |
| `@admin_required`／`@block_admin` | 不是平台管理員／是平台管理員（403）——管理員讀不到任何財務資料 |
| `Depends(own(Transaction, "tx_id"))` | 這一筆不是我的（403）、找不到（404）。回傳那一筆 |
| `Depends(in_group("gid", owner=True))` | 我不在這本帳裡、不是建立者（403）、帳本被移除（404） |
| `Depends(can_see_user("user_id"))` | 監管、同家庭家長、同帳本都不是（403） |
| `Depends(token_required())` | 重設密碼連結找不到、過期、用過（一律同一句 400） |

守衛會把 `me.family_id`、`me.family_role` 掛好，路由不用再查一次。
⚠️ 裝飾器寫在 `@router.xxx` 的**下面**。

### 設定：`.env`

`python -m app.cli init-env` 會從 `.env.example` 建出 `.env`。檔案依成員分段，**改自己那一段就好**；
機密（`JWT_SECRET`、`BREVO_API_KEY`、`MODEL_BASE_URL`、`MODEL_API_KEY`、`MAIL_FROM`）在 Render 後台填，**不可以 commit**。
程式裡一律 `from app.toolkit.config import settings`，不要自己讀 `os.environ`。

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
| **成員1** | **認證** | `m1-auth` | 19 支 | `routers/auth/auth.py`<br>`routers/auth/admin.py`<br>`models/user.py`<br>`schemas/auth.py` | `services/llm/client.py`<br>`guards.py`<br>`cli.py`<br>`routers/_stub.py`<br>`models/_types.py` |
| **成員2** | **記帳** | `m2-ledger` | 19 支 | `routers/ledger/transactions.py`<br>`routers/ledger/nlp.py`<br>`routers/ledger/categories.py`<br>`routers/ledger/groups.py`<br>`models/category.py`<br>`models/group.py`<br>`schemas/group.py`<br>`services/evaluation.py`<br>`models/transaction.py`<br>`models/nlp.py`<br>`schemas/transaction.py`<br>`schemas/nlp.py`<br>`services/llm/parse.py` | — |
| **成員3** | **數字** | `m3-analytics` | 11 支 | `routers/analytics/stats.py`<br>`routers/analytics/alerts.py`<br>`models/alert.py`<br>`routers/analytics/budgets.py`<br>`routers/analytics/advices.py`<br>`models/budget.py`<br>`models/advice.py`<br>`schemas/stats.py`<br>`schemas/advice.py`<br>`services/llm/advice.py` | `services/analytics.py` |
| **成員4** | **家庭** | `m4-access` | 21 支 | `routers/access/family.py`<br>`routers/access/notifications.py`<br>`models/family.py`<br>`models/guardianship.py`<br>`models/notification.py`<br>`models/audit.py`<br>`schemas/family.py` | `services/permission.py` |

### 切分原則

1. **一個領域＝一個完整的概念**，不是一堆零散的路由湊數
2. **一個檔案剛好一個主人**，四個人不會改到同一個檔案 → git 幾乎不衝突
3. **會擋住別人的東西要盡量小**（`guards.py`、`toolkit/`、`permission.py`），而且這一版已經先做好了
4. **每個人都要有一份 LLM 工作** —— 這是任務的硬性要求

### 各領域的邊界

#### 成員1 · 認證　`m1-auth`

負責「你是誰」。
屬於他的：註冊登入登出、密碼與忘記密碼、JWT、工作階段、個人資料與理財習慣，以及平台管理員的停權（停權擋的是登入，所以歸認證）。
地基（設定 `toolkit/config.py`、資料庫連線 `toolkit/db.py`、增刪改查 `toolkit/crud.py`、路由守衛 `guards.py`、模型呼叫層 `services/llm/client.py`、20 張表與 Alembic）**已經做好了**，他負責維護。
不屬於他的：家庭角色與監管關係（那是成員4）。users 表存的是登入身分，family_members 表才是家庭角色，兩者刻意分開。

**LLM 工作**：共用的模型呼叫層：逾時、重試、把模型回傳的 JSON 交給 Pydantic 驗證。成員2 和成員3 都會呼叫它，所以第 1 週要先做出來。

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

#### 成員2 · 記帳　`m2-ledger`

負責「記一筆帳」這個動作，從文字進來到寫進資料庫。★ 這是整個系統的核心。
屬於他的：明細的增刪改查、段落解析、單句解析、確認後寫入、nlp_parses 的寫入。
帳本（開、改、封存、結算、成員）與分類也在這裡：帳本是「這筆算在哪」的容器，分類是記帳時要選的欄位，統計只是拿它分組。
不屬於他的：統計加總（那是成員3，前端和這裡都不做任何加總）。

**LLM 工作**：段落切分策略、欄位抽取 prompt、few-shot 範例的挑選、低信心的判準。切分比抽欄位更難，而且切錯比抽錯更難發現。

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

#### 成員3 · 數字　`m3-analytics`

負責所有「算出來的東西」，以及把那些數字講成人話。
屬於他的：月年統計、預算、每月存款目標、階段性提醒的門檻、財務建議。
**整個系統只有這裡加總錢** —— 模型不算，前端只做衍生（結餘、比例、預算百分比）。
不屬於他的：明細的寫入（那是成員2）；決定要算哪些人（那是成員4 的 permission）。

**LLM 工作**：財務建議的 prompt 與邊界規則。順序不能顛倒：先用 analytics 算好數字，再餵給模型敘述，模型不做任何算術。

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

#### 成員4 · 家庭　`m4-access`

負責「誰在這個家庭裡」以及「誰看得到誰的資料」，另外扛模型評測。
屬於他的：家庭（建立、解散）、成員角色、家庭綁定（邀請碼與用帳號邀請）、監管關係、權限計算、通知、零用金、稽核紀錄、評測。
不屬於他的：登入本身（那是成員1）。成員1 回答「你是誰」，成員4 回答「你能看到什麼」。

**LLM 工作**：模型評測：建立人工標註的留出集、跑零樣本 vs few-shot 對照、算一次輸入完全正確率與分類 Macro-F1。**留出集必須 100% 人工標註**，否則量到的是「多像那個老師」而不是「多正確」。

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

原本會擋住別人的地基**已經做好了**，四個人第一天就能開工：

```
✅ 路由守衛         app/guards.py（@login_required、own()、in_group()、can_see_user()）
✅ 資料庫與增刪改查  app/toolkit/db.py、crud.py、models/（20 張表）、alembic/
✅ 可見範圍         app/guards.py 的 visible_scope()、services/permission.py 的 visible()
✅ 模型呼叫層       app/services/llm/client.py
```

還剩一件跨模組的事**要最優先**：

```
成員2  分類體系（GET /api/categories）  ← 成員2 寫 prompt、成員4 評測、成員3 統計分組都要用
```

### 六週排程

總長六週 = **實作四週 + 測試不到一週 + 報告簡報**。

⚠️ **後端線與模型線並行，不是接力。** 標註資料不用寫程式，第 1 週就能開始。

| 週 | 主題 | 後端線 | 模型線 |
|---|---|---|---|
| **1** | 地基與標註同時開始 | 地基已經做好（toolkit、guards、models）：每個人拿掉前幾支的 @stub、打得通 | 標註 150 筆（不用寫程式，每人每天 1 小時） |
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

1. 三個層級各走一遍：平台 master / 家長 parent / 子女 child
2. 權限的**反向測試** —— 子女切不到「全家」、直接打全家的 summary 也要被擋，這比正向測試重要
3. 段落記帳的邊界：缺欄位、低信心、切分錯誤、空輸入、超長輸入
4. 金額邊界：0、負數、小數、很大的數字
5. 年度統計的「未完整」標示有沒有出現
6. 帳號不存在與密碼錯誤，回的訊息要一樣
7. 批次寫入寫到一半失敗，要全部不寫（不可以留下半筆）

### 找到自己要做的事

```bash
cd backend && python -m app.ownership
```

會印出每個人負責哪幾支、已經做完幾支、還差哪幾支。
`app/ownership.py` 是分工的**唯一事實來源**——路由歸屬、分支名稱、
共用檔案、時程，全部在那一個檔案裡，`pytest` 會拿它去對文件。

**70 支路由已經全部掛好了**（`app/routers/` 底下，一個領域一個資料夾）：守衛、請求主體、說明字串都寫好，函式裡只有
`raise not_ready(...)`（回 501）。做一支 = 換成真的實作、拿掉 `@stub`。

**先讀那一支的說明字串**——它就是那一支的規格書，十一個段落：這支做什麼、前端怎麼打、誰能打、
請求、成功回應、錯誤回應、會用到的資料表、每一步用的工具與資料庫方法、寫法步驟、
**完整寫法**（可以直接貼上去的整段程式：import ＋ 整個函式）、做完怎麼確認。
照著改完，跑 `pytest tests/routes -k "函式名 and 你的"` 就知道對不對
（同一組測試也會拿說明裡的程式跑一遍，所以說明不會跟實作走散）。

增刪改查用 `app/toolkit/crud.py`、身分與權限用 `app/guards.py`、規則用 `app/toolkit/` 對應的模組——
都是測好的工具，直接用，不用重寫。每支路由的輸入輸出也寫在 `docs/02-前後端串接契約.md`。

### 誰都不可以實作的路由

- `POST /api/auth/switch`
  **任何管理身分登入他人的帳號。家長不行，平台管理員也不行。**
  前端曾經有一顆「切換身分」的按鈕，已經連同這支路由一起拿掉，換成真正的登入／登出。
  這不只是安全問題，更是產品決定：監管的正當性建立在「看得到但碰不到」——
  能登入對方帳號的話，被監管者就無法信任自己的紀錄沒有被動過手腳。
  監管者要看對方的資料，走**唯讀的監管檢視**（帶 `userId` 查明細）。
  `backend/tests/test_consistency.py` 會擋下任何把它加回來的修改。

## 環境變數

完整說明寫在 `app/toolkit/config.py` 每一個欄位的 `description`，下面是摘要（✅ = 必填，沒填服務起不來）：

| 段落 | 變數 | 必填 | 說明 |
|---|---|---|---|
| 共用 | `APP_ENV` |  | 預設 `development`。development / production。production 時 db 不印 SQL、錯誤訊息不帶內部細節。 |
| 共用 | `DATABASE_URL` | ✅ | PostgreSQL 連線字串。格式：postgresql+psycopg://使用者:密碼@主機:埠號/資料庫名稱 |
| 共用 | `DB_ECHO` |  | 預設 `False`。True 會把送出的 SQL 印出來，除錯用。正式環境不要開。 |
| 共用 | `DB_POOL_SIZE` |  | 預設 `5`。連線池大小。Render 免費 PostgreSQL 同時連線數很少，不要開太大。SQLite 會忽略。 |
| 共用 | `ALLOWED_ORIGINS` |  | 預設 `http://localhost:5174`。允許哪些前端網域來打這個 API，逗號分隔。填錯前端會被瀏覽器的 CORS 擋住。 |
| 成員1 | `JWT_SECRET` | ✅ | 簽 JWT 用的密鑰。這是整個系統最敏感的一個值——拿到它的人可以偽造任何人的登入權杖。 |
| 成員1 | `JWT_ALGORITHM` |  | 預設 `HS256`。 |
| 成員1 | `ACCESS_TOKEN_MINUTES` |  | 預設 `30`。access token 有效期（分鐘）。刻意設短：外洩時損害只持續這麼久，前端會自動續期。 |
| 成員1 | `REFRESH_TOKEN_DAYS` |  | 預設 `14`。refresh token 有效期（天）。存在 sessions 表，可以撤銷。 |
| 成員1 | `BREVO_API_KEY` |  | Brevo 的 API 金鑰（Brevo 後台 → SMTP & API → API keys），忘記密碼寄信用。**不可以 commit**。 |
| 成員1 | `MAIL_FROM` |  | 寄件信箱。一定要先在 Brevo 的 Senders 驗證過，不然信會被拒絕。 |
| 成員1 | `MAIL_FROM_NAME` |  | 預設 `家庭記帳`。收件人看到的寄件人名稱。 |
| 成員1 | `APP_BASE_URL` |  | 預設 `https://fambudget-web.onrender.com`。前端網址。重設密碼信裡的連結會長成「這個網址/#/reset/token」。本機改成 http://localhost:5174。 |
| 成員1 | `ADMIN_EMAILS` |  | 平台管理員的 email，逗號分隔。`python -m app.cli make-admin` 會把這些帳號設成平台管理員。 |
| 成員2 | `MODEL_BASE_URL` |  | 我們自己微調的 Qwen2.5-1.5B 模型服務網址（GGUF + llama.cpp，跑在 Hugging Face Space）。 |
| 成員2 | `MODEL_API_KEY` |  | 模型服務要驗證時用（例如私有的 Hugging Face Space 的 token）。公開的就留空。**不可以 commit**。 |
| 成員2 | `MODEL_NAME` |  | 預設 `qwen2.5-1.5b-fambudget`。寫進 nlp_parses.model_ver，換模型才分得開成績。 |
| 成員2 | `MODEL_TIMEOUT_SECONDS` |  | 預設 `30.0`。呼叫模型的逾時秒數。一定要設——模型卡住時，沒有逾時的 API 會跟著一起卡死。 |
| 成員3 | `ADVICE_MODEL_NAME` |  | 產生財務建議用的模型名稱（寫進 advices.model_ver）。留空就跟記帳用同一個模型服務。 |
| 成員3 | `SAVINGS_WARN_RATIO` |  | 預設 `0.8`。支出達可支配上限的幾成算「接近上限」。前端 data.js 的 savingsRule 要一致。 |
| 成員3 | `SAVINGS_OVER_RATIO` |  | 預設 `1.0`。幾成算「超過」。 |
| 成員4 | `INVITE_TTL_DAYS` |  | 預設 `7`。邀請與邀請碼幾天後失效。產生時呼叫 family.expires_at(days=settings.invite_ttl_days)。 |

`MODEL_BASE_URL` 留空時 `services/llm/client.py` 回 `None`：解析與建議的路由回 **503**，前端用規則頂著，畫面照常能用。
這是刻意的：第 1 週模型還沒訓練完，但前端已經要串了。等模型好了把網址填上去，其他程式碼一行都不用改。

寄信用 **Brevo 的 HTTP API**，不是 SMTP——Render 免費方案擋掉了 25／465／587 埠，
用 smtplib 在本機會通、部署上去就永遠逾時。填好金鑰後先試寄一封給自己：

```bash
python -m app.toolkit.mailer --to 你的信箱@gmail.com
```

`.env` 已經寫進 `.gitignore`，**不會被 commit**。
Render 上的機密是在後台手動填的（`render.yaml` 裡標 `sync: false` 的那幾個）。

平台管理員不能自己註冊：先用一般方式註冊，再跑

```bash
python -m app.cli make-admin 那個人的信箱      # 或把信箱寫進 ADMIN_EMAILS 再跑 make-admin
```

---

## 資料庫結構變更（Alembic）

建表／升到最新（部署時 Render 與 Docker 都會在啟動前自動跑這一行）：

```bash
alembic upgrade head
alembic -x url=sqlite:///./dev.db upgrade head      # 臨時對別顆資料庫跑
```

改了 `models/` 底下的欄位之後（**三處一起改**：`frontend/js/data.js` 的 schema → `models/` → 遷移）：

```bash
alembic revision --autogenerate -m "what changed"   # 說明用英文，檔名才不會變成亂碼
alembic upgrade head
```

**產生出來的檔案一定要自己打開看過再套用。** autogenerate 不是萬能的，
改欄位型別、改名稱這類操作它常常會產生錯的東西（例如把「改名」
判斷成「刪掉舊的、加一個新的」，那會把資料全部弄丟）。

`tests/test_backend_core.py` 會檢查兩件事：models 跟 data.js 的 schema 逐欄一致、
遷移建出來的表跟 models 一模一樣。漏改一處就紅燈。

---

## 常見問題

**前端 console 出現 `blocked by CORS policy`**
→ `ALLOWED_ORIGINS` 沒填對。網址要完整（含 `https://`），結尾不要加斜線。

**啟動時噴 `ValidationError: database_url Field required`**
→ `.env` 沒建立，或是少了必填變數。先跑 `python -m app.cli init-env`，再 `check-config`。這是 `config.py` 刻意的設計：
**寧可在啟動時就失敗，也不要等使用者按下按鈕才發現設定是空的。**

**路由回 501**
→ 那支還沒實作（還標著 `@stub`）。回應裡就寫著路由與負責人，前端畫面也會講。這是正常的，不是 bug。

**畫面寫「後端出錯（HTTP 500）：系統發生錯誤…」**
→ 路由裡丟出了沒接住的例外。開發環境的訊息後面會附上例外的類型與內容，完整的追蹤在 uvicorn 的 log 裡；
正式環境（`APP_ENV=production`）只回一句話，不會把表名、SQL 送出去。規則類的錯誤請用 `toolkit/errors.py` 轉成 400／403／409。

**`alembic` 指令噴 `UnicodeDecodeError: 'cp950'`**
→ 有人在 `alembic.ini` 裡寫了中文。那個檔案只能有英文，說明寫在 `alembic/env.py`。

**本機沒有 PostgreSQL**
→ 不用裝。`.env` 預設就是 `DATABASE_URL=sqlite:///./dev.db`（外鍵檢查已經打開，行為跟 PostgreSQL 一致）。
測試用的是記憶體裡的 SQLite，正式環境（Render）才是 PostgreSQL。
想在本機也用 PostgreSQL：`docker compose up`，再照 `.env.example` 裡註解的那一行改 `DATABASE_URL`。

**想砍掉資料重來**
→ 在專案最外層 `python run.py --reset`（只對 SQLite 有效）。

**改了程式但沒生效**
→ 確認啟動時有加 `--reload`。
