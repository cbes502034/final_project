# -*- coding: utf-8 -*-
"""把四份「開發說明」寫進各自的路由資料夾。

    python backend/tools/sync_devguide.py          # 寫回檔案
    python backend/tools/sync_devguide.py --check  # 只檢查，不寫（測試用）

產出：
    app/routers/auth/README.md        成員1
    app/routers/ledger/README.md      成員2
    app/routers/analytics/README.md   成員3
    app/routers/access/README.md      成員4

檔名用 README.md 是因為 GitHub 與大部分編輯器點進資料夾時會自動把它渲染出來——
組員打開自己的資料夾就看得到，不用有人提醒他「記得去讀那份文件」。

⚠️ 為什麼用程式產生，而不是手寫四份。

四份的「怎麼啟動、怎麼測試、怎麼看資料」是同一件事，手寫四份一定會走散：
有人改了啟動指令，只會記得改自己在看的那一份。所以共通的部分只寫一次
（下面的 COMMON），每個人不一樣的地方從 app/ownership.py 長出來。
test_consistency.py 會用 --check 把它釘死，忘了跑就會紅。

要改內容請改這個檔案，不要直接改產出的 README.md。
"""
import argparse
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
REPO = os.path.dirname(BACKEND)

sys.path.insert(0, BACKEND)

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "sync-devguide-only-not-a-real-secret-0000")

from app.ownership import MEMBERS  # noqa: E402

#: 每個人的路由資料夾、對應的測試檔、建議的起手式。
#: 這三樣是編輯內容（不是事實來源），所以寫在這裡而不是 ownership.py。
PLAN = {
    "m1": {
        "pkg": "auth",
        "tests": ["tests/routes/test_auth.py"],
        "first": [
            ("POST /api/auth/register", "沒有它就沒有帳號，剩下 69 支都沒得測"),
            ("POST /api/auth/login", "**其他三個人被你擋住**——登入不能用，他們連自己的頁面都打不開"),
            ("GET /api/auth/me", "前端每次開頁面都先打這一支"),
        ],
        "why_first": "你是四個人裡唯一會擋住別人的：**登入沒做完，另外三個人看不到自己的頁面**。"
                     "先把註冊、登入、取得自己三支打通，其他人就能開工了。",
        "eval": "你的模型工作是**共用的呼叫層**，不是模型本身，所以「評估」評的是它夠不夠耐操：\n"
                "\n"
                "1. 模型服務沒設定（`MODEL_BASE_URL` 留空）→ 回 `None`，路由回 503，不可以讓整支炸掉\n"
                "2. 模型逾時、回 500、回一段不是 JSON 的字 → 都要變成同一種 `ModelError`，"
                "呼叫的人（成員2、成員3）只要處理一種例外\n"
                "3. 模型回的 JSON 少欄位、型別不對 → Pydantic 擋下來，**不可以讓髒資料進資料庫**\n"
                "4. 重試幾次、每次間隔多久，要有數字，而且要能在報告裡說明為什麼是這個數字",
    },
    "m2": {
        "pkg": "ledger",
        "tests": ["tests/routes/test_transactions.py", "tests/routes/test_nlp.py",
                  "tests/routes/test_groups.py"],
        "first": [
            ("GET /api/categories", "**成員3 分組、成員4 評測、你自己寫 prompt 都要用**，最先做"),
            ("GET /api/transactions", "做完就看得到畫面，後面每一支都靠它驗收"),
            ("POST /api/transactions", "先讓手動記帳能寫進去，再回頭做段落解析"),
        ],
        "why_first": "分類清單（`GET /api/categories`）是**跨三個人的相依**：成員3 統計要拿它分組、"
                     "成員4 評測要拿它當標籤、你自己寫 prompt 也要把分類名稱餵進去。第一週就要做完。",
        "eval": "你的模型工作是**段落切分與欄位抽取**。評估的重點順序不要弄反：\n"
                "\n"
                "1. **切分比抽欄位難，而且切錯更難發現**——把兩筆合成一筆，金額看起來還是「合理的數字」\n"
                "2. 所以每一列都要回 `span`（它對應原句的哪一段），人才驗得出來切對沒有\n"
                "3. 抽不到的欄位回 `null` 並放進 `missing`，**不要猜**——猜錯會直接變成一筆錯帳\n"
                "4. 低信心的判準要有數字（`conf` 多少以下算低），而且要能說明怎麼訂出來的\n"
                "\n"
                "⚠️ 留出集的標註由成員4 做（他負責評測），你負責的是 prompt 與 few-shot 範例怎麼挑。",
    },
    "m3": {
        "pkg": "analytics",
        "tests": ["tests/routes/test_analytics.py"],
        "first": [
            ("GET /api/summary", "總覽與統計兩頁都靠它；做完畫面立刻活起來"),
            ("GET /api/budgets", "同一套加總邏輯的延伸，順手就做完了"),
            ("GET /api/savings-goals", "存錢目標，個人資料頁在等"),
        ],
        "why_first": "`services/analytics.py` 是你的共用元件，`GET /api/summary` 就是它的第一個出口。"
                     "先把加總寫對，後面的預算、提醒、建議全部是拿同一批數字換個形狀。",
        "eval": "你的模型工作是**財務建議**。順序不能顛倒，這是評估時最容易被問的一題：\n"
                "\n"
                "1. `analytics.py` 從資料庫算出所有數字 → 2. 把**算好的**數字交給模型只做敘述 →\n"
                "3. Pydantic 驗證 → 4. 存進 advices\n"
                "\n"
                "**模型不做任何算術。** 評估要拿得出證據：\n"
                "\n"
                "· 建議裡出現的每一個數字，都能在 `basis` 裡對回 summary 的哪一欄\n"
                "· 同一批數字跑兩次，講法可以不同，**數字不可以不同**\n"
                "· 模型叫不動時回 503（不是 500），前端才知道要不要自己頂著",
    },
    "m4": {
        "pkg": "access",
        "tests": ["tests/routes/test_family.py"],
        "first": [
            ("GET /api/family", "前端每一頁的「我 / 全家」切換都要它"),
            ("POST /api/family", "沒有家庭就沒有成員、沒有監管，後面全部卡住"),
            ("POST /api/family/invite", "邀請碼做完，四個人就能互相加成一家測試"),
        ],
        "why_first": "`services/permission.py` 是你的共用元件（成員2、成員3 查資料都會用到可見範圍）。"
                     "建立家庭與邀請做完之後，你們四個人才有辦法互相加成一家人來測。",
        "eval": "你的模型工作是**評測**，而且是四個人裡唯一產出數字的：\n"
                "\n"
                "1. **留出集必須 100% 人工標註**——用模型標出來的答案去評模型，"
                "量到的是「多像那個老師」，不是「多正確」\n"
                "2. 零樣本 vs few-shot 要跑同一份留出集，才比得出來\n"
                "3. 兩個指標：**一次輸入完全正確率**（整句的每一欄都對才算對）與**分類 Macro-F1**\n"
                "4. Macro（不是 Micro）：筆數少的分類不能被餐飲、交通洗掉\n"
                "\n"
                "工具在 `app/services/evaluation.py`（那個檔案掛在成員2 名下，要動先講一聲）。",
    },
}

HEAD = """# %(label)s · %(domain)s — 開發說明

> **這份講「怎麼動手」。每一支路由要做什麼、收什麼、回什麼，寫在那一支自己的說明字串裡**
> （就在這個資料夾的 .py 檔案裡），這裡不重複。
>
> 由 `backend/tools/sync_devguide.py` 從 `app/ownership.py` 產生，**不要直接改這個檔案**。

---

## 0. 你負責什麼

| | |
|---|---|
| 領域 | %(domain)s |
| 路由 | **%(n)d 支** |
| 分支 | `%(branch)s` |
| 你的資料夾 | `backend/app/routers/%(pkg)s/` |

%(scope)s

**你獨佔的檔案**（別人不會動，你也只動這些）：

%(files)s
%(shared)s
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
| 帳號 | `%(pkg)s@fambudget.tw` |
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
git switch -c %(branch)s
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

**① 打開 `backend/app/routers/%(pkg)s/` 裡的檔案，找到那一支。**

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
%(pytest_mine)s
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

> %(llm)s

%(eval)s

---

## 7. 先做哪幾支

%(why_first)s

| 順序 | 路由 | 為什麼先做 |
|---|---|---|
%(first_rows)s

做完這幾支之後，剩下的可以照自己的節奏推。

---

## 8. 卡住的時候

| 症狀 | 原因與解法 |
|---|---|
| 啟動時 `ValidationError: database_url Field required` | `backend/.env` 沒建立。跑 `python run.py`，或 `cd backend && python -m app.cli init-env` |
| 畫面 console 出現 `blocked by CORS policy` | 前端的網址不在 `ALLOWED_ORIGINS` 裡。用 `run.py` 起的網址就不會遇到 |
| 路由回 501 | 那支還沒實作（`@stub` 還在）。**這是正常的，不是 bug** |
| 畫面說「後端出錯（HTTP 500）」 | 你的路由丟了沒接住的例外。完整追蹤在 uvicorn 的視窗裡。規則類的錯誤請用 `toolkit/errors.py` 轉成 400／403／409 |
| 埠號被占用 | 上一次的視窗沒關。`netstat -ano \\| findstr :8000` 找出來，或 `python run.py --port 5555 --api-port 8001` |
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
"""


def _bullets(items, empty="（沒有）"):
    if not items:
        return "- %s\n" % empty
    return "".join("- `%s`\n" % f for f in items)


def render(m):
    plan = PLAN[m.key]
    # ownership.py 是寫給「讀分工表的人」看的，所以用第三人稱；
    # 這一份是寫給本人看的，換成第二人稱才讀得順。
    scope = m.scope.strip().replace("屬於他的：", "屬於你的：")
    shared = ""
    if m.shared:
        shared = ("\n**別人會等你的共用元件**（要最先完成）：\n\n%s"
                  % _bullets(m.shared))
    mine = " ".join(plan["tests"])
    first_rows = "\n".join(
        "| %d | `%s` | %s |" % (i + 1, route, why)
        for i, (route, why) in enumerate(plan["first"]))
    return HEAD % {
        "label": m.label,
        "domain": m.domain,
        "n": len(m.routes),
        "branch": m.branch,
        "pkg": plan["pkg"],
        "scope": scope,
        "files": _bullets(m.files),
        "shared": shared,
        "pytest_mine": "pytest %s -q                 # 只跑你這一塊" % mine,
        "llm": m.llm.replace("\n", "\n> "),
        "eval": plan["eval"],
        "why_first": plan["why_first"],
        "first_rows": first_rows,
    }


def main():
    ap = argparse.ArgumentParser(description="產生四份開發說明")
    ap.add_argument("--check", action="store_true", help="只檢查有沒有走散，不寫檔")
    args = ap.parse_args()

    stale = []
    for m in MEMBERS:
        rel = os.path.join("app", "routers", PLAN[m.key]["pkg"], "README.md")
        path = os.path.join(BACKEND, rel)
        want = render(m)
        have = io.open(path, encoding="utf-8").read() if os.path.exists(path) else None
        if args.check:
            if have != want:
                stale.append(rel.replace(os.sep, "/"))
            continue
        io.open(path, "w", encoding="utf-8", newline="\n").write(want)
        print("寫好 backend/%s" % rel.replace(os.sep, "/"))

    if args.check and stale:
        print("跟 ownership.py 走散了：%s\n跑 python backend/tools/sync_devguide.py 重新產生"
              % "、".join(stale))
        return 1
    if args.check:
        print("四份開發說明都是最新的")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())
