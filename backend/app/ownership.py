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
        domain="認證",
        branch="m1-auth",
        color="#6C9FFB",
        scope=(
            "負責「你是誰」。\n"
            "屬於他的：註冊登入登出、密碼、忘記密碼、JWT、工作階段、個人資料與大頭貼、介面主題。\n"
            "註冊只問名字、email、密碼；每月存款目標、理財習慣、主題在註冊後的個人化設定問，\n"
            "  走完（或全部跳過）用 PATCH /api/auth/me 的 onboarded 設 users.onboarded_at。\n"
            "忘記密碼：toolkit/password_reset.py 產一次性連結（只存雜湊、30 分鐘），toolkit/mailer.py 用 Brevo 寄出。\n"
            "⚠️ 申請重設時，有沒有這個帳號都回同一句話——不然這支就是帳號列舉工具。\n"
            "地基（資料庫連線、設定、依賴注入、密碼雜湊、JWT 實作）"
            "已經在 toolkit/ 裡寫好了，直接用就好，不用再造一次。\n"
            "停權也在這裡：平台管理員（master）可以停掉違規帳號。\n"
            "⚠️ **停權是關門，不是配鑰匙。** 他停得了人，但讀不到任何一筆帳——\n"
            "  一個能讀全系統消費明細的帳號，比家長越權嚴重得多。\n"
            "⚠️ 停權**不刪任何資料**：擋登入、擋寫入，紀錄全部留著。\n"
            "⚠️ 每一次停權都要寫進 audit_logs，而且要有理由。\n"
            "  沒有稽核的停權就是任意封鎖，被停的人也沒東西可以申訴。\n"
            "verify-password 給「重大操作前再確認一次」用："
            "驗證密碼但不發新的 token。⚠️ 一定要做速率限制，"
            "否則它就是一支免費的密碼嘗試器。\n"
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
            ("POST", "/api/auth/password-reset"),
            ("POST", "/api/auth/password-reset/confirm"),
            ("GET", "/api/auth/me/finance"),
            ("PUT", "/api/auth/me/finance"),
            ("POST", "/api/auth/verify-password"),
            ("GET", "/api/auth/sessions"),
            ("PATCH", "/api/auth/me"),
            ("PUT", "/api/auth/me/avatar"),
            ("DELETE", "/api/auth/me/avatar"),
            ("GET", "/api/admin/users"),
            ("POST", "/api/admin/users/{user_id}/suspend"),
            ("DELETE", "/api/admin/users/{user_id}/suspend"),
        ],
        files=[
            "app/routers/auth.py",
            "app/routers/admin.py",
            "app/models/user.py",
            "app/schemas/auth.py",
        ],
        shared=[
            "app/services/llm/client.py",
            "app/guards.py",
            "app/cli.py",
            "app/routers/_stub.py",
            "app/models/_types.py",
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
            "⚠️ 明細的**修改與刪除只有本人可以**，監管者不行——監管是唯讀的。\n"
            "  結算過的帳本裡的紀錄不能改、不能刪（409）。一次刪多筆（DELETE /api/transactions?ids=）全部成功或全部不動。\n"
            "新增一筆時要順手寫一則通知給監管者（成員4 的 notifications 表）。\n"
            "帳本也在這裡：一本帳就是「這筆算在哪」的容器，跟記帳同一個脈絡。\n"
            "常設帳本沒有結束；活動帳本有結束日，到了由建立者手動結算，之後唯讀（不能再記，回 409）。\n"
            "⚠️ 結算**不搬動任何一筆紀錄**，只是把那本帳標記結束。\n"
            "結算過的活動帳本可以封存（可復原）或移除（帳本不見、不能復原，紀錄一筆都不刪）。\n"
            "  規則在 toolkit/ledger.py。\n"
            "⚠️ 帳本成員是可見範圍的其中一條路，但規則不要自己寫——\n"
            "  一律呼叫 toolkit/scope.py，有測試擋著重寫。\n"
            "分類也在這裡：它是記帳時要選的欄位，統計只是拿它分組。\n"
            "不屬於他的：統計加總（那是成員3，前端和這裡都不做任何加總）。"
        ),
        routes=[
            ("GET", "/api/transactions"),
            ("POST", "/api/transactions"),
            ("PATCH", "/api/transactions/{tx_id}"),
            ("DELETE", "/api/transactions/{tx_id}"),
            ("DELETE", "/api/transactions"),
            ("POST", "/api/nlp/parse"),
            ("POST", "/api/nlp/parse-batch"),
            ("POST", "/api/nlp/confirm"),
            ("POST", "/api/nlp/confirm-batch"),
            ("GET", "/api/categories"),
            ("POST", "/api/categories"),
            ("GET", "/api/groups"),
            ("POST", "/api/groups"),
            ("PATCH", "/api/groups/{gid}"),
            ("DELETE", "/api/groups/{gid}"),
            ("POST", "/api/groups/{gid}/members"),
            ("DELETE", "/api/groups/{gid}/members/{user_id}"),
            ("POST", "/api/groups/{gid}/settle"),
            ("PATCH", "/api/groups/{gid}/notify"),
        ],
        files=[
            "app/routers/transactions.py",
            "app/routers/nlp.py",
            "app/routers/categories.py",
            "app/routers/groups.py",
            "app/models/category.py",
            "app/models/group.py",
            "app/schemas/group.py",
            "app/services/evaluation.py",
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
        domain="數字",
        branch="m3-analytics",
        color="#5FB8D9",
        scope=(
            "負責所有「算出來的東西」，以及把那些數字講成人話。\n"
            "屬於他的：月年統計、預算、每月存款目標、階段性提醒的門檻、財務建議。\n"
            "**整個系統只有這裡加總錢** —— 模型不算，前端只做衍生（結餘、比例、預算百分比）。\n"
            "  GET /api/stats、GET /api/savings-goal 已經拿掉：前端從 summary、savings-goals 自己取。\n"
            "每月存款目標可以**分群組設定**：不帶 groupId 是整體目標，帶了就是那個群組自己的目標。\n"
            "階段性提醒也在這裡：使用者自己設幾個百分比門檻（例如 50%／80%／100%），"
            "支出跨過門檻就發一則通知。\n"
            "⚠️ **算出要發通知是成員3，真的寫進 notifications 是成員4。**\n"
            "不屬於他的：明細的寫入（那是成員2）；決定要算哪些人（那是成員4 的 permission）。"
        ),
        routes=[
            ("GET", "/api/summary"),
            ("GET", "/api/budgets"),
            ("PUT", "/api/budgets"),
            ("PUT", "/api/savings-goal"),
            ("GET", "/api/savings-goals"),
            ("GET", "/api/alerts"),
            ("POST", "/api/alerts"),
            ("PATCH", "/api/alerts/{aid}"),
            ("DELETE", "/api/alerts/{aid}"),
            ("GET", "/api/advices"),
            ("POST", "/api/advices/generate"),
        ],
        files=[
            "app/routers/stats.py",
            "app/routers/alerts.py",
            "app/models/alert.py",
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
        domain="家庭",
        branch="m4-access",
        color="#6EE7B7",
        scope=(
            "負責「誰在這個家庭裡」以及「誰看得到誰的資料」。\n"
            "屬於他的：家庭、成員角色、家庭綁定（邀請碼與用帳號邀請）、監管關係、權限計算、"
            "唯讀監管檢視與即時通知、零用金、稽核紀錄。\n"
            "家庭綁定：家長建立家庭，用邀請碼或輸入對方 email 邀請家人加入。\n"
            "⚠️ 身分（家長／子女）由發邀請的家長決定，被邀請的人不能自己選。\n"
            "⚠️ 用帳號找人只接受完整 email，不做模糊搜尋，也不回任何財務資料。\n"
            "⚠️ 邀請碼只能用一次、七天過期、資料庫只存雜湊。工具在 toolkit/family.py。\n"
            "移出、退出、解散：家長只能移除子女，另一位家長只能自己退出；唯一的家長在家裡還有人時不能退出，\n"
            "  改用解散（DELETE /api/family，只有唯一的家長能解散）。\n"
            "角色：家長可以把子女設為家長；不能把另一位家長降成子女，只有他自己能調整。\n"
            "監管：家長按「開始照看」建立，監管人一定是自己；監管人或同家的家長可以解除，被照看的人不行。\n"
            "  規則都在 toolkit/family.py。\n"
            "⚠️ 離開不刪紀錄，但監管關係、共用帳本、他送出的邀請要在同一個交易裡一起收掉。\n"
            "⚠️ 監管是**唯讀**的：看得到，但不能改、不能刪，"
            "更不能登入對方的帳號。\n"
            "⚠️ **可見範圍是兩條路的聯集，過一條就看得到**：\n"
            "  A. 這筆是誰記的 → 自己 ＋ 我監管的人 ＋ 同家庭的其他家長，**跨所有帳本**\n"
            "     （家長之間互相看得到；家長看子女一樣要有監管關係）\n"
            "  B. 這筆在哪一本帳 → group_members（我在不在那本帳裡）\n"
            "  A 是監管：不該被帳本切斷，否則被監管的人另開一本帳就躲掉了。\n"
            "  B 是分享：把誰加進帳本，就是選擇讓他看到那一本。\n"
            "⚠️ 寫成 AND 就變回交集了，那是早期版本的錯。規則寫在 toolkit/scope.py。\n"
            "帳本本身（開、改、封存、結算、成員）屬於成員2——那是記帳的容器。\n"
            "成員4 只管**可見範圍怎麼算**，不管帳本的 CRUD。\n"
            "零用金也在這裡：家長每個月給某個被監管者多少錢。\n"
            "⚠️ **零用金是設定，不是一筆支出紀錄。**\n"
            "  家長記一筆「給小孩 3000」，小孩再把那 3000 花掉記成支出，\n"
            "  家庭總支出就會變成 6000——同一筆錢被算了兩次。\n"
            "  正確的算法是：**子女的支出算進家庭支出，子女的收入不算進家庭收入**，\n"
            "  零用金只拿來跟「他實際花了多少」做對照。\n"
            "不屬於他的：登入本身（那是成員1）。"
            "成員1 回答「你是誰」，成員4 回答「你能看到什麼」。"
        ),
        routes=[
            ("GET", "/api/family"),
            ("POST", "/api/family"),
            ("DELETE", "/api/family"),
            ("POST", "/api/family/invite"),
            ("POST", "/api/family/join"),
            ("GET", "/api/family/lookup"),
            ("GET", "/api/family/invites"),
            ("POST", "/api/family/invites"),
            ("POST", "/api/family/invites/{invite_id}/accept"),
            ("DELETE", "/api/family/invites/{invite_id}"),
            ("PATCH", "/api/family/members/{user_id}"),
            ("DELETE", "/api/family/members/{user_id}"),
            ("GET", "/api/guardianships"),
            ("POST", "/api/guardianships"),
            ("DELETE", "/api/guardianships/{gid}"),
            ("GET", "/api/notifications"),
            ("PATCH", "/api/notifications/{nid}"),
            ("PATCH", "/api/notifications"),
            ("GET", "/api/allowances"),
            ("PUT", "/api/allowance"),
            ("GET", "/api/audit"),
        ],
        files=[
            "app/routers/family.py",
            "app/routers/notifications.py",
            "app/models/family.py",
            "app/models/guardianship.py",
            "app/models/notification.py",
            "app/models/audit.py",
            "app/schemas/family.py",
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
        "backend": "地基已經做好（toolkit、guards、models）：每個人拿掉前幾支的 @stub、打得通",
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
    "三個層級各走一遍：平台 master / 家長 parent / 子女 child",
    "權限的**反向測試** —— 子女切不到「全家」、直接打全家的 summary 也要被擋，這比正向測試重要",
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
# 誰都不可以實作的路由。前端也沒有，列在這裡是為了讓「為什麼沒有」有地方可查。
# ---------------------------------------------------------------------------
NEVER_IMPLEMENT: list[tuple[str, str]] = [
    (
        "POST /api/auth/switch",
        "**任何一端都不可以實作這支。**\n"
        "前端曾經有一顆「切換身分」的示範鈕，已經連同這支路由一起拿掉了，"
        "換成真正的登入／登出。\n"
        "這不只是安全問題，更是產品決定：**管理者不可以進入子女的帳號**。\n"
        "監管的正當性建立在「看得到但碰不到」——能登入對方帳號的話，"
        "被監管者就無法信任自己的紀錄沒有被動過手腳。\n"
        "管理者要看子女的資料，走**唯讀的監管檢視**"
        "（帶 userId 查明細），不是換身分。\n"
        "列在這裡是為了讓「為什麼沒有這個功能」有地方可查——"
        "不然過幾週就會有人「順手補上」。",
    ),
]

# 舊名字。曾經的語意是「前端有、後端不用做」，
# 現在前端也沒有了，所以改叫 NEVER_IMPLEMENT。
FRONTEND_ONLY = NEVER_IMPLEMENT


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


def progress() -> dict[str, dict]:
    """
    比對「宣告要做的路由」與「實際掛上去的路由」，回傳每個人的進度。

    回傳
        dict: 鍵是成員代號，值是
            `{"done": [...], "todo": [...], "member": Member}`。

    注意
        **路由還沒寫不算錯誤**，那是正常的進度。
        這支的用途是讓大家隨時知道「還剩幾支」。
    """
    from app.main import app  # 延後匯入，避免循環相依
    from app.routers._stub import is_stub

    actual: set[tuple[str, str]] = set()
    for route in app.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if not methods or not path:
            continue
        # 掛上去但還是 @stub（回 501）的，算還沒做
        if is_stub(getattr(route, "endpoint", None)):
            continue
        for verb in methods:
            if verb not in ("HEAD", "OPTIONS"):
                actual.add((verb, path))

    out = {}
    for m in MEMBERS:
        done = [r for r in m.routes if r in actual]
        todo = [r for r in m.routes if r not in actual]
        out[m.key] = {"member": m, "done": done, "todo": todo}
    return out


def check() -> list[str]:
    """
    檢查分工定義本身有沒有矛盾，以及有沒有「程式裡有但沒人認領」的路由。

    回傳
        list[str]: 所有問題。空清單代表沒問題。

    注意
        **不檢查「宣告了但還沒寫」** —— 那是進度不是錯誤，用 progress() 看。
        這支只抓真正的矛盾：兩個人搶同一支、檔案重複認領、
        或是有人加了路由卻忘記在這裡登記。
    """
    from app.main import app

    problems: list[str] = []
    declared = all_routes()

    actual: set[tuple[str, str]] = set()
    for route in app.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if not methods or not path:
            continue
        for verb in methods:
            if verb not in ("HEAD", "OPTIONS"):
                actual.add((verb, path))

    for key in sorted(actual - set(declared) - set(SYSTEM_ROUTES)):
        problems.append(
            f"程式裡有但沒有人認領：{key[0]} {key[1]}"
            "（在 ownership.py 的 MEMBERS 裡加上去）"
        )

    seen: dict[str, str] = {}
    for m in MEMBERS:
        for f in m.files + m.shared:
            if f in seen:
                problems.append(f"檔案 {f} 同時屬於 {seen[f]} 和 {m.label}")
            seen[f] = m.label

    return problems


def main() -> int:
    # Windows 主控台預設 cp950，印不出某些字元會整個爆掉
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    total = sum(len(m.routes) for m in MEMBERS)
    print("=" * 70)
    print("分工與進度　（app/ownership.py 是唯一的事實來源）")
    print("=" * 70)

    prog = progress()
    all_done = 0
    for m in MEMBERS:
        p = prog[m.key]
        d, t = len(p["done"]), len(p["todo"])
        all_done += d
        bar = "█" * d + "░" * t
        print(f"\n{m.label} · {m.domain}    分支 {m.branch}")
        print(f"  {bar}  {d}/{d + t} 支")
        print(f"  {m.scope.splitlines()[0]}")
        if m.shared:
            print(f"  [共用] 別人會用到，要最先完成：{', '.join(m.shared)}")
        if t and t <= 12:
            print(f"  還沒寫：{', '.join(f'{v} {p2}' for v, p2 in p['todo'])}")

    print("\n" + "-" * 70)
    print(f"總進度　{all_done}/{total} 支　"
          f"({all_done * 100 // total if total else 0}%)")

    print("\n" + "=" * 70)
    problems = check()
    if problems:
        print(f"❌ 找到 {len(problems)} 個問題：")
        for p in problems:
            print("   -", p)
        return 1
    print("✅ 分工定義沒有矛盾")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
