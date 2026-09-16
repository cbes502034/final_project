# -*- coding: utf-8 -*-
"""把文件裡的路由清單，從 ownership.py 重新產生一次。

    python backend/tools/sync_spec.py          # 寫回檔案
    python backend/tools/sync_spec.py --check  # 只檢查，不寫（測試用）

⚠️ 為什麼要有這支程式，而不是「記得去改文件」。

分工總表、各領域的路由清單，跟 ownership.py 講的是同一件事，
而且被抄進了三份文件（docs/01、README.md、backend/README.md），還有 frontend/js/api.js 開頭的路由清單。
只要是同一件事被寫在好幾個地方，它就一定會走散——而且真的走散過：
ownership.py 已經 17/18/13/15 了，三份文件全部還停在 8/8/10/9，整整差了一倍。
沒有人是不小心的，是**人本來就不適合維護跨檔案的數字**。

所以這裡的做法是：ownership.py 是唯一的事實，文件由它長出來。
test_consistency.py 會用 --check 把這件事釘死，忘了跑就會紅。
"""
import argparse
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
REPO = os.path.dirname(BACKEND)

#: 抄著路由清單的文件。多一份就加在這裡，不要讓它自己長。
TARGETS = (
    os.path.join("docs", "01-tech-stack-and-api.md"),
    "README.md",
    os.path.join("backend", "README.md"),
)

sys.path.insert(0, BACKEND)


def _routes_block(m):
    """一個領域的路由清單，方法靠左對齊成一欄。"""
    width = max(len(v) for v, _ in m.routes)
    return "\n".join("%-*s %s" % (width, v, p) for v, p in m.routes)


def render(text, name="文件"):
    """回傳把數字與清單都對齊過的新內文。找不到該有的段落就直接結束。"""
    from app.ownership import MEMBERS

    # ---- 分工總表的「路由」欄 ----
    for m in MEMBERS:
        text, hits = re.subn(
            r"(\| \*\*%s\*\* \| \*\*%s\*\* \| `%s` \| )\d+( 支 \|)"
            % (re.escape(m.label), re.escape(m.domain), re.escape(m.branch)),
            lambda mo, n=len(m.routes): mo.group(1) + str(n) + mo.group(2),
            text,
        )
        if hits != 1:
            raise SystemExit("%s 的分工總表裡，%s 應該剛好一列，找到 %d 列" % (name, m.label, hits))

    # ---- 「為什麼不是平均切法」那段的比例（只有 docs/01 有） ----
    text = re.sub(
        r"這一版是 [\d /]+，",
        "這一版是 " + " / ".join(str(len(m.routes)) for m in MEMBERS) + "，",
        text,
    )

    # ---- 每個領域的「**路由（N 支）**」與底下的程式碼區塊 ----
    for m in MEMBERS:
        # 標題可能是 ### 也可能是 ####，錨在行首
        hm = re.search(r"(?m)^#{2,4} %s · %s" % (re.escape(m.label), re.escape(m.domain)), text)
        if not hm:
            raise SystemExit("%s 裡找不到「%s · %s」這一段" % (name, m.label, m.domain))
        i = hm.start()
        # 這一段到下一個同級或更高的標題為止，不要波及下一個領域
        nm = re.compile(r"(?m)^#{2,4} ").search(text, hm.end())
        j = nm.start() if nm else len(text)
        seg = text[i:j]

        block = "**路由（%d 支）**\n\n```\n%s\n```" % (len(m.routes), _routes_block(m))
        # ⚠️ 用 subn 數「有沒有找到」，不要拿「內容有沒有變」來判斷——
        #    文件已經是最新的時候內容本來就不會變，那不是錯誤。
        new_seg, hits = re.subn(
            r"\*\*路由（\d+ 支）\*\*\n\n```\n.*?\n```",
            lambda _mo: block,
            seg,
            flags=re.S,
        )
        if hits != 1:
            raise SystemExit("%s 的「%s · %s」應該剛好有一個路由區塊，找到 %d 個"
                             % (name, m.label, m.domain, hits))
        text = text[:i] + new_seg + text[j:]

    return text


# ---------------------------------------------------------------------------
# frontend/js/api.js 開頭的「後端契約」清單
# ---------------------------------------------------------------------------
API_JS = os.path.join("frontend", "js", "api.js")
API_JS_START = "   後端契約"
API_JS_END = "   ============================================================ */\n(function (global) {"


def render_api_js(text):
    """換掉 api.js 開頭的路由清單：路由與負責人照 ownership.py，說明取自各路由的 summary。"""
    # 只是要讀路由的 summary，不會連資料庫；設定沒填的話給一組假的讓 app 載得起來
    os.environ.setdefault("DATABASE_URL", "sqlite://")
    os.environ.setdefault("JWT_SECRET", "sync-spec-only-not-a-real-secret-00000")
    from app.main import app
    from app.ownership import MEMBERS

    summary = {}
    for r in app.routes:
        for v in getattr(r, "methods", None) or ():
            summary[(v, getattr(r, "path", ""))] = getattr(r, "summary", "") or ""
    lines = [
        "   後端契約（由 backend/tools/sync_spec.py 從 ownership.py 產生，不要手改）\n",
        "   每一支的完整形狀：docs/02-前後端串接契約.md；前端函式與路由的對照：本檔的 FN。\n",
    ]
    for m in MEMBERS:
        lines.append("\n   %s · %s（%d 支）\n" % (m.label, m.domain, len(m.routes)))
        width = max(7 + len(p) for _, p in m.routes)          # 方法欄固定 6 格 + 1 個空白
        for v, p in m.routes:
            head = "%-6s %s" % (v, p)
            lines.append("   %-*s  %s\n" % (width + 1, head, summary.get((v, p), "")))
    lines.append("\n   另外 GET /healthz（健康檢查）、GET /docs（自動文件）前端不會用到。\n")
    a = text.index(API_JS_START)
    b = text.index(API_JS_END)
    return text[:a] + "".join(lines) + text[b:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="只比對，不寫回。不一致就以非零結束")
    args = ap.parse_args()

    stale = []
    for rel in TARGETS:
        path = os.path.join(REPO, rel)
        old = io.open(path, encoding="utf-8").read()
        new = render(old, rel)
        if old == new:
            continue
        stale.append(rel)
        if not args.check:
            io.open(path, "w", encoding="utf-8", newline="").write(new)

    path = os.path.join(REPO, API_JS)
    old = io.open(path, encoding="utf-8").read()
    new = render_api_js(old)
    if old != new:
        stale.append(API_JS)
        if not args.check:
            io.open(path, "w", encoding="utf-8", newline="").write(new)

    if not stale:
        print("文件與 api.js 的路由清單都跟 ownership.py 一致")
        return 0
    if args.check:
        print("這些文件落後了，請跑 python backend/tools/sync_spec.py：\n  "
              + "\n  ".join(stale))
        return 1
    print("已更新：\n  " + "\n  ".join(stale))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
