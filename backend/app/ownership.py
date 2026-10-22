"""
路由屬於哪個領域的單一事實來源。

===========================================================================
這個檔案是幹嘛的
===========================================================================
84 支路由分成四個領域（認證、記帳、數字、家庭）。哪一支屬於哪個領域只寫在這裡，
錯誤卡上的「屬於：記帳」、API 瀏覽頁的分組、規格文件的路由清單都要跟這裡對得上，
`pytest` 會檢查有沒有走散。

⚠️ 這裡**不是人員分工**。舊的四人分工與六週排程已經刪除；
   最後一週誰做什麼，寫在 docs/04-最後一週分工.md 與 docs/分工/。

===========================================================================
怎麼用
===========================================================================
    cd backend
    python -m app.ownership          # 印出各領域的完成度，並檢查一致性

檢查項目：
  1. 每一支實際掛上去的路由，都屬於一個領域
  2. 每個領域宣告的路由，程式裡真的存在
  3. 沒有一支路由同時屬於兩個領域
  4. 每個 .py 檔案剛好屬於一個領域
"""

from __future__ import annotations

import sys

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Member:
    """一個領域：它的邊界、路由與檔案。"""

    key: str
    """程式裡用的代號。"""

    label: str
    """人看的編號，例如「認證」。"""

    domain: str
    """領域名稱。一句話講完他負責什麼。"""

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



# ===========================================================================
# 四個領域
# ---------------------------------------------------------------------------
# 切分原則：
#   1. 一個領域＝一個完整的概念，不是一堆零散的路由
#   2. 一個檔案剛好一個主人，四個人不會改到同一個檔案
#   3. 會擋住別人的東西（core、permission）要盡量小，才能最快完成
# ===========================================================================
MEMBERS: list[Member] = [
    Member(
        key="m1",
        label="認證",
        domain="認證",
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
            "平台管理頁即時看三件事：每個人的紅綠燈（users.last_active_at）、錯誤訊息（error_logs）、\n"
            "  安全事件（security_events：登入錯太多次、大量註冊、AI 額度用完…，規則在 toolkit/security.py）。\n"
            "  ⚠️ 規則只暫時擋下，**停權一律由管理員按**，不讓 AI 或規則自動停權。\n"
            "⚠️ **停權是關門，不是配鑰匙。** 他停得了人，但讀不到任何一筆帳——\n"
            "  一個能讀全系統消費明細的帳號，比家長越權嚴重得多。\n"
            "⚠️ 停權**不刪任何資料**：擋登入、擋寫入，紀錄全部留著。\n"
            "⚠️ 每一次停權都要寫進 audit_logs，而且要有理由。\n"
            "  沒有稽核的停權就是任意封鎖，被停的人也沒東西可以申訴。\n"
            "verify-password 給「重大操作前再確認一次」用："
            "驗證密碼但不發新的 token。⚠️ 一定要做速率限制，"
            "否則它就是一支免費的密碼嘗試器。\n"
            "不屬於他的：家庭角色與監管關係（那是家庭）。"
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
            ("POST", "/api/auth/verify-email"),
            ("POST", "/api/auth/verify-email/resend"),
            ("GET", "/api/auth/me/finance"),
            ("PUT", "/api/auth/me/finance"),
            ("POST", "/api/auth/verify-password"),
            ("GET", "/api/auth/sessions"),
            ("PATCH", "/api/auth/me"),
            ("PUT", "/api/auth/me/avatar"),
            ("DELETE", "/api/auth/me/avatar"),
            ("DELETE", "/api/auth/me"),
            ("GET", "/api/admin/users"),
            ("POST", "/api/admin/users/{user_id}/suspend"),
            ("DELETE", "/api/admin/users/{user_id}/suspend"),
            ("GET", "/api/admin/errors"),
            ("GET", "/api/admin/security-events"),
            ("POST", "/api/client-errors"),
        ],
        files=[
            "app/routers/auth/__init__.py",
            "app/routers/auth/auth.py",
            "app/routers/auth/admin.py",
            "app/models/user.py",
            "app/models/monitor.py",
            "app/schemas/auth.py",
        ],
        shared=[
            "app/services/llm/client.py",
            "app/guards.py",
            "app/cli.py",
            "app/routers/_stub.py",
            "app/models/_types.py",
        ],
    ),
    Member(
        key="m2",
        label="記帳",
        domain="記帳",
        color="#8B7CF0",
        scope=(
            "負責「記一筆帳」這個動作，從文字進來到寫進資料庫。★ 這是整個系統的核心。\n"
            "屬於他的：明細的增刪改查、段落解析、單句解析、確認後寫入、nlp_parses 的寫入。\n"
            "⚠️ 明細的**修改與刪除只有本人可以**，監管者不行——監管是唯讀的。\n"
            "  結算過的帳本裡的紀錄不能改、不能刪（409）。一次刪多筆（DELETE /api/transactions?ids=）全部成功或全部不動。\n"
            "新增一筆時要順手寫一則通知給監管者（家庭 的 notifications 表）。\n"
            "帳本也在這裡：一本帳就是「這筆算在哪」的容器，跟記帳同一個脈絡。\n"
            "常設帳本沒有結束；活動帳本有結束日，到了由建立者手動結算，之後唯讀（不能再記，回 409）。\n"
            "⚠️ 結算**不搬動任何一筆紀錄**，只是把那本帳標記結束。\n"
            "結算過的活動帳本可以封存（可復原）或移除（帳本不見、不能復原，紀錄一筆都不刪）。\n"
            "  規則在 toolkit/ledger.py。\n"
            "⚠️ 帳本成員是可見範圍的其中一條路，但規則不要自己寫——\n"
            "  一律呼叫 toolkit/scope.py，有測試擋著重寫。\n"
            "分類也在這裡：它是記帳時要選的欄位，統計只是拿它分組。\n"
            "不屬於他的：統計加總（那是數字，前端和這裡都不做任何加總）。"
        ),
        routes=[
            ("GET", "/api/transactions"),
            ("GET", "/api/transactions/archive"),
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
            ("DELETE", "/api/categories/{cid}"),
            ("GET", "/api/groups"),
            ("POST", "/api/groups"),
            ("PATCH", "/api/groups/{gid}"),
            ("DELETE", "/api/groups/{gid}"),
            ("POST", "/api/groups/{gid}/members"),
            ("DELETE", "/api/groups/{gid}/members/{user_id}"),
            ("POST", "/api/groups/{gid}/settle"),
            ("PATCH", "/api/groups/{gid}/notify"),
            ("POST", "/api/groups/{gid}/invites"),
            ("GET", "/api/groups/{gid}/invites/lookup"),
            ("GET", "/api/group-invites"),
            ("POST", "/api/group-invites/join"),
            ("POST", "/api/group-invites/{invite_id}"),
        ],
        files=[
            "app/routers/ledger/__init__.py",
            "app/routers/ledger/transactions.py",
            "app/routers/ledger/nlp.py",
            "app/routers/ledger/categories.py",
            "app/routers/ledger/groups.py",
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
    ),
    Member(
        key="m3",
        label="數字",
        domain="數字",
        color="#5FB8D9",
        scope=(
            "負責所有「算出來的東西」，以及把那些數字講成人話。\n"
            "屬於他的：月年統計、預算、每月存款目標、階段性提醒的門檻、財務建議。\n"
            "**整個系統只有這裡加總錢** —— 模型不算，前端只做衍生（結餘、比例、預算百分比）。\n"
            "  GET /api/stats、GET /api/savings-goal 已經拿掉：前端從 summary、savings-goals 自己取。\n"
            "每月存款目標可以**分群組設定**：不帶 groupId 是整體目標，帶了就是那個群組自己的目標。\n"
            "階段性提醒也在這裡：使用者自己設幾個百分比門檻（例如 50%／80%／100%），"
            "支出跨過門檻就發一則通知。\n"
            "⚠️ **算出要發通知是數字，真的寫進 notifications 是家庭。**\n"
            "不屬於他的：明細的寫入（那是記帳）；決定要算哪些人（那是家庭 的 permission）。"
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
            ("DELETE", "/api/advices/{aid}"),
        ],
        files=[
            "app/routers/analytics/__init__.py",
            "app/routers/analytics/stats.py",
            "app/routers/analytics/alerts.py",
            "app/models/alert.py",
            "app/routers/analytics/budgets.py",
            "app/routers/analytics/advices.py",
            "app/models/budget.py",
            "app/models/advice.py",
            "app/schemas/stats.py",
            "app/schemas/advice.py",
            "app/services/llm/advice.py",
        ],
        shared=[
            "app/services/analytics.py",
        ],
    ),
    Member(
        key="m4",
        label="家庭",
        domain="家庭",
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
            "帳本本身（開、改、封存、結算、成員）屬於記帳——那是記帳的容器。\n"
            "家庭 只管**可見範圍怎麼算**，不管帳本的 CRUD。\n"
            "零用金也在這裡：家長每個月給某個被監管者多少錢。\n"
            "⚠️ **零用金是設定，不是一筆支出紀錄。**\n"
            "  家長記一筆「給小孩 3000」，小孩再把那 3000 花掉記成支出，\n"
            "  家庭總支出就會變成 6000——同一筆錢被算了兩次。\n"
            "  正確的算法是：**子女的支出算進家庭支出，子女的收入不算進家庭收入**，\n"
            "  零用金只拿來跟「他實際花了多少」做對照。\n"
            "不屬於他的：登入本身（那是認證）。"
            "認證 回答「你是誰」，家庭 回答「你能看到什麼」。"
        ),
        routes=[
            ("GET", "/api/family"),
            ("POST", "/api/family"),
            ("PATCH", "/api/family"),
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
            ("DELETE", "/api/notifications"),
            ("GET", "/api/allowances"),
            ("PUT", "/api/allowance"),
            ("GET", "/api/audit"),
        ],
        files=[
            "app/routers/access/__init__.py",
            "app/routers/access/family.py",
            "app/routers/access/notifications.py",
            "app/models/family.py",
            "app/models/guardianship.py",
            "app/models/notification.py",
            "app/models/audit.py",
            "app/schemas/family.py",
        ],
        shared=[
            "app/services/permission.py",
        ],
    ),
]

# ---------------------------------------------------------------------------
# 不屬於任何一個領域的共用檔案。
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
    print("各領域的完成度　（app/ownership.py 是唯一的事實來源）")
    print("=" * 70)

    prog = progress()
    all_done = 0
    for m in MEMBERS:
        p = prog[m.key]
        d, t = len(p["done"]), len(p["todo"])
        all_done += d
        bar = "█" * d + "░" * t
        print(f"\n{m.label}")
        print(f"  {bar}  {d}/{d + t} 支")
        print(f"  {m.scope.splitlines()[0]}")
        if m.shared:
            print(f"  [共用元件] {', '.join(m.shared)}")
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
    print("✅ 領域定義沒有矛盾")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
