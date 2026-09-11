"""
分工的單一事實來源。 ✦ 全組共用，改這裡之前先在群組講一聲

===========================================================================
這個檔案是幹嘛的
===========================================================================
「誰負責哪些路由、哪些檔案」這件事，如果寫在四個地方
（README、專題手冊、API 瀏覽頁、各檔案的檔頭），
遲早會有一份忘記更新，然後就開始有人改到別人的東西。

所以只在這裡寫一次，其他地方都從這裡推出來，
並且用 `python -m app.ownership` 檢查程式碼有沒有跟這份定義走散。

===========================================================================
怎麼用
===========================================================================
    cd backend
    python -m app.ownership          # 印出分工表，並檢查一致性

檢查項目：
  1. 每一支實際掛上去的路由，都有明確的負責人
  2. 每一位負責人宣告的路由，程式裡真的存在
  3. 沒有兩個人同時宣告同一支路由
  4. 每個 .py 檔案剛好屬於一個人
"""

from __future__ import annotations

import sys

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Member:
    """一位成員的完整責任範圍。"""

    key: str
    """程式裡用的代號，也是分支名稱的前綴。"""

    label: str
    """人看的編號，例如「成員1」。"""

    domain: str
    """領域名稱。一句話講完他負責什麼。"""

    branch: str
    """他的 git 分支名稱。只能在這個分支上動下面列的檔案。"""

    scope: str
    """這個領域的邊界：什麼算他的、什麼不算。寫清楚是為了避免功能衝突。"""

    color: str
    """在心智圖與文件裡代表他的顏色。"""

    routes: list[tuple[str, str]] = field(default_factory=list)
    """(HTTP 方法, 路徑) 的清單。這是唯一的路由歸屬定義。"""

    files: list[str] = field(default_factory=list)
    """他獨佔的檔案。**其他人不要改這些檔案。**"""

    shared: list[str] = field(default_factory=list)
    """他負責、但別人會用的共用元件。這些要最優先完成。"""

    llm: str = ""
    """他那一份的 LLM 工作。四個人都有，這是任務的硬性要求。"""


# ===========================================================================
# 分工定義
# ---------------------------------------------------------------------------
# 切分原則：
#   1. 一個領域＝一個完整的概念，不是一堆零散的路由
#   2. 一個檔案剛好一個主人，四個人不會改到同一個檔案
#   3. 會擋住別人的東西（core、permission）要盡量小，才能最快完成
#   4. 每個人都要有一份 LLM 工作
# ===========================================================================
MEMBERS: list[Member] = [
    Member(
        key="m1",
        label="成員1",
        domain="認證與基礎建設",
        branch="m1-auth",
        color="#6C9FFB",
        scope=(
            "負責「你是誰」以及整個後端的地基。\n"
            "屬於他的：註冊登入登出、密碼、JWT、資料庫連線、設定管理、依賴注入、模型呼叫層。\n"
            "不屬於他的：家庭角色與監管關係（那是成員4）。"
            "users 表存的是登入身分，family_members 表才是家庭角色，兩者刻意分開。"
        ),
        routes=[
            ("POST", "/api/auth/register"),
            ("POST", "/api/auth/login"),
            ("POST", "/api/auth/refresh"),
            ("POST", "/api/auth/logout"),
            ("POST", "/api/auth/logout-all"),
            ("GET", "/api/auth/me"),
            ("PATCH", "/api/auth/password"),
            ("GET", "/api/auth/sessions"),
        ],
        files=[
            "app/routers/auth.py",
            "app/models/user.py",
            "app/schemas/auth.py",
        ],
        shared=[
            "app/core/config.py",
            "app/core/database.py",
            "app/core/security.py",
            "app/core/deps.py",
            "app/services/llm/client.py",
        ],
        llm=(
            "共用的模型呼叫層：逾時、重試、把模型回傳的 JSON 交給 Pydantic 驗證。"
            "成員2 和成員3 都會呼叫它，所以第 1 週要先做出來。"
        ),
    ),
    Member(
        key="m2",
        label="成員2",
        domain="記帳",
        branch="m2-ledger",
        color="#8B7CF0",
        scope=(
            "負責「記一筆帳」這個動作，從文字進來到寫進資料庫。★ 這是整個系統的核心。\n"
            "屬於他的：明細的增刪改查、段落解析、單句解析、確認後寫入、nlp_parses 的寫入。\n"
            "不屬於他的：分類體系的定義與 /api/categories（那是成員3 —— "
            "分類由成員3 定義，成員2 只是把清單寫進 prompt）；"
            "統計加總（那是成員3，前端和這裡都不做任何加總）。"
        ),
        routes=[
            ("GET", "/api/transactions"),
            ("POST", "/api/transactions"),
            ("PATCH", "/api/transactions/{tx_id}"),
            ("DELETE", "/api/transactions/{tx_id}"),
            ("POST", "/api/nlp/parse"),
            ("POST", "/api/nlp/parse-batch"),
            ("POST", "/api/nlp/confirm"),
            ("POST", "/api/nlp/confirm-batch"),
        ],
        files=[
            "app/routers/transactions.py",
            "app/routers/nlp.py",
            "app/models/transaction.py",
            "app/models/nlp.py",
            "app/schemas/transaction.py",
            "app/schemas/nlp.py",
            "app/services/llm/parse.py",
        ],
        llm=(
            "段落切分策略、欄位抽取 prompt、few-shot 範例的挑選、低信心的判準。"
            "切分比抽欄位更難，而且切錯比抽錯更難發現。"
        ),
    ),
    Member(
        key="m3",
        label="成員3",
        domain="數字與建議",
        branch="m3-analytics",
        color="#5FB8D9",
        scope=(
            "負責所有「算出來的東西」，以及把那些數字講成人話。\n"
            "屬於他的：分類體系、月年統計、預算、每月存款目標、財務建議。\n"
            "**整個系統只有這裡算錢** —— 路由不算、前端不算、模型更不算。\n"
            "不屬於他的：明細的寫入（那是成員2）；決定要算哪些人（那是成員4 的 permission）。"
        ),
        routes=[
            ("GET", "/api/categories"),
            ("POST", "/api/categories"),
            ("GET", "/api/summary"),
            ("GET", "/api/stats"),
            ("GET", "/api/budgets"),
            ("PUT", "/api/budgets"),
            ("GET", "/api/savings-goal"),
            ("PUT", "/api/savings-goal"),
            ("GET", "/api/advices"),
            ("POST", "/api/advices/generate"),
        ],
        files=[
            "app/routers/categories.py",
            "app/routers/stats.py",
            "app/routers/budgets.py",
            "app/routers/advices.py",
            "app/models/budget.py",
            "app/models/advice.py",
            "app/schemas/stats.py",
            "app/schemas/advice.py",
            "app/services/llm/advice.py",
        ],
        shared=[
            "app/services/analytics.py",
        ],
        llm=(
            "財務建議的 prompt 與邊界規則。"
            "順序不能顛倒：先用 analytics 算好數字，再餵給模型敘述，模型不做任何算術。"
        ),
    ),
    Member(
        key="m4",
        label="成員4",
        domain="家庭與可見範圍",
        branch="m4-access",
        color="#6EE7B7",
        scope=(
            "負責「誰在這個家庭裡」以及「誰看得到誰的資料」，另外扛模型評測。\n"
            "屬於他的：家庭、成員角色、邀請碼、監管關係、權限計算、稽核紀錄、評測。\n"
            "不屬於他的：登入本身（那是成員1）。"
            "成員1 回答「你是誰」，成員4 回答「你能看到什麼」。"
        ),
        routes=[
            ("GET", "/api/family"),
            ("POST", "/api/family"),
            ("POST", "/api/family/invite"),
            ("POST", "/api/family/join"),
            ("PATCH", "/api/family/members/{user_id}"),
            ("DELETE", "/api/family/members/{user_id}"),
            ("GET", "/api/guardianships"),
            ("POST", "/api/guardianships"),
            ("DELETE", "/api/guardianships/{gid}"),
        ],
        files=[
            "app/routers/family.py",
            "app/models/family.py",
            "app/models/audit.py",
            "app/schemas/family.py",
            "app/services/evaluation.py",
        ],
        shared=[
            "app/services/permission.py",
        ],
        llm=(
            "模型評測：建立人工標註的留出集、跑零樣本 vs few-shot 對照、"
            "算一次輸入完全正確率與分類 Macro-F1。"
            "**留出集必須 100% 人工標註**，否則量到的是「多像那個老師」而不是「多正確」。"
        ),
    ),
]

# ---------------------------------------------------------------------------
# 六週排程。這也是單一事實來源，文件都從這裡抄。
#
# 總長六週 = 實作四週 + 測試不到一週 + 報告簡報。
# 後端線與模型線**並行**，不是做完後端才開始模型——
# 標註資料不用寫程式，第 1 週就能開始，這是唯一能跟後端平行的工作。
# ---------------------------------------------------------------------------
SCHEDULE: list[dict[str, str]] = [
    {
        "week": "第 1 週",
        "theme": "地基與標註同時開始",
        "backend": "core/ 能動、每個人的前幾支路由打得通",
        "model": "標註 150 筆（不用寫程式，每人每天 1 小時）",
        "gate": "",
    },
    {
        "week": "第 2 週",
        "theme": "前後端串通",
        "backend": "後端完成，**關掉 mock 畫面還能動**",
        "model": "標註到 300 筆、Colab 環境先跑通一次",
        "gate": "⚠️ 硬檢查點：沒串通的話第 3 週不要碰微調，先把串接做完",
    },
    {
        "week": "第 3 週",
        "theme": "基準線與第一輪微調",
        "backend": "補洞、修 bug、**四個人開始自己用這個系統**",
        "model": "few-shot 基準線 ＋ 第一輪 QLoRA",
        "gate": "⚠️ 硬切線：週末沒有第一輪的數字，第 4 週就放棄第二輪，用 few-shot 收尾",
    },
    {
        "week": "第 4 週",
        "theme": "第二輪微調",
        "backend": "功能凍結",
        "model": "第二輪微調（用第 3 週收集到的真實修正）＋ 接回系統",
        "gate": "⚠️ 最後兩天不准改模型，留給「接回去 + 確認沒壞」",
    },
    {
        "week": "第 5 週",
        "theme": "測試",
        "backend": "全系統測試、四個角色各走一遍、權限反向測試",
        "model": "評測數字定稿",
        "gate": "",
    },
    {
        "week": "第 6 週",
        "theme": "報告與緩衝",
        "backend": "報告、簡報",
        "model": "對照表、圖表",
        "gate": "",
    },
]

# 測試週只有不到一週，不夠做完整測試。**要邊做邊測**：
# 每支路由寫完當下就用 /docs 試打，不要累積到最後。
TEST_CHECKLIST: list[str] = [
    "四個角色各走一遍：master / parent / member / 未成年",
    "權限的**反向測試** —— 成員去打家庭總覽要被擋，這比正向測試重要",
    "段落記帳的邊界：缺欄位、低信心、切分錯誤、空輸入、超長輸入",
    "金額邊界：0、負數、小數、很大的數字",
    "年度統計的「未完整」標示有沒有出現",
    "帳號不存在與密碼錯誤，回的訊息要一樣",
    "批次寫入寫到一半失敗，要全部不寫（不可以留下半筆）",
]

# ---------------------------------------------------------------------------
# 沒有單一主人的檔案。要改這些請先在群組講一聲。
# ---------------------------------------------------------------------------
SHARED_FILES: list[str] = [
    "app/main.py",           # 只有 include_router，新增路由組時才會動
    "app/ownership.py",      # 就是這個檔案
    "app/models/__init__.py",
    "app/schemas/__init__.py",
    "app/routers/__init__.py",
    "app/services/__init__.py",
    "app/services/llm/__init__.py",
]

# ---------------------------------------------------------------------------
# 前端專用、後端不會實作的路由。
# ---------------------------------------------------------------------------
FRONTEND_ONLY: list[tuple[str, str]] = [
    (
        "POST /api/auth/switch",
        "示範模式的切換身分鈕。**後端絕對不可以實作這支** —— "
        "讓任何人任意切換身分等於把整套權限系統作廢。"
        "接上真後端之後，這個鈕要換成正常的登入登出。",
    ),
]

# ---------------------------------------------------------------------------
# 系統路由，不歸任何人，FastAPI 或 Render 自己提供。
# ---------------------------------------------------------------------------
SYSTEM_ROUTES: list[tuple[str, str]] = [
    ("GET", "/healthz"),          # 我們寫的，給 Render 做健康檢查
    # 下面四支是 FastAPI 自己掛的，我們一行都沒寫
    ("GET", "/docs"),             # 互動式 API 文件
    ("GET", "/docs/oauth2-redirect"),
    ("GET", "/redoc"),            # 另一種版型的文件
    ("GET", "/openapi.json"),     # 規格本體，上面兩頁都是讀它畫出來的
]


def owner_of(method: str, path: str) -> Member | None:
    """查一支路由是誰的。"""
    for m in MEMBERS:
        if (method.upper(), path) in m.routes:
            return m
    return None


def all_routes() -> dict[tuple[str, str], Member]:
    """所有有主人的路由。鍵是 (方法, 路徑)。"""
    out: dict[tuple[str, str], Member] = {}
    for m in MEMBERS:
        for r in m.routes:
            if r in out:
                raise ValueError(
                    f"路由 {r[0]} {r[1]} 同時被 {out[r].label} 和 {m.label} 宣告"
                )
            out[r] = m
    return out


def check() -> list[str]:
    """
    比對這份定義與實際掛上去的路由，回傳所有對不上的地方。

    回傳空清單代表完全一致。
    """
    from app.main import app  # 延後匯入，避免循環相依

    problems: list[str] = []
    declared = all_routes()

    actual: set[tuple[str, str]] = set()
    for route in app.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if not methods or not path:
            continue
        for verb in methods:
            if verb in ("HEAD", "OPTIONS"):
                continue
            actual.add((verb, path))

    system = set(SYSTEM_ROUTES)

    for key in sorted(actual - set(declared) - system):
        problems.append(f"程式裡有但沒有人認領：{key[0]} {key[1]}")
    for key in sorted(set(declared) - actual):
        problems.append(f"{declared[key].label} 宣告了但程式裡沒有：{key[0]} {key[1]}")

    seen: dict[str, str] = {}
    for m in MEMBERS:
        for f in m.files + m.shared:
            if f in seen:
                problems.append(f"檔案 {f} 同時屬於 {seen[f]} 和 {m.label}")
            seen[f] = m.label

    return problems


def main() -> int:
    # Windows 的主控台預設是 cp950，印不出 ⚠ 這類字元會整個爆掉。
    # 這裡強制轉成 UTF-8；轉不了就算了，下面的字還是印得出來。
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    total = sum(len(m.routes) for m in MEMBERS)
    print("=" * 68)
    print("分工定義　（app/ownership.py 是唯一的事實來源）")
    print("=" * 68)
    for m in MEMBERS:
        print(f"\n{m.label} · {m.domain}    分支 {m.branch}    {len(m.routes)} 支路由")
        print(f"  {m.scope.splitlines()[0]}")
        if m.shared:
            print(f"  [共用] 別人會用到，要最先完成：{', '.join(m.shared)}")
    print(f"\n路由合計：{total} 支 + 系統 {len(SYSTEM_ROUTES)} 支 = {total + len(SYSTEM_ROUTES)}")

    print("\n" + "=" * 68)
    problems = check()
    if problems:
        print(f"❌ 找到 {len(problems)} 個對不上的地方：")
        for p in problems:
            print("   -", p)
        return 1
    print("✅ 程式碼與分工定義完全一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
