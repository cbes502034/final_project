# -*- coding: utf-8 -*-
"""分工心智圖：docs/分工心智圖.svg 與手冊第 10 節的互動版，從同一份內容產生。

    python backend/tools/sync_mindmap.py          # 寫回兩個檔案
    python backend/tools/sync_mindmap.py --check  # 只檢查，不寫（測試用）

⚠️ 為什麼要有這支：心智圖同時畫在兩個地方（SVG 圖檔、手冊裡的互動版），
   而且兩份都是手改的——SVG 停在「8／8／10／9 支」「core/ 設定」好幾天沒人發現。
   現在：
     · 路由數   從 app/ownership.py 算
     · 資料表   從每位成員名下的 app/models/*.py 讀 __tablename__
     · API、畫面、LLM 工作的摘要  寫在下面的 BRANCHES（改分工時跟著改這裡）
"""
import argparse
import importlib
import io
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
REPO = os.path.dirname(BACKEND)
SVG = os.path.join(REPO, "docs", "分工心智圖.svg")
HANDBOOK = os.path.join(REPO, "frontend", "docs", "index.html")

sys.path.insert(0, BACKEND)
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "sync-mindmap-only-not-a-real-secret-0000")

#: 每位成員除了「資料表」以外的分支。(名稱, 是不是那個模組的 LLM 工作, 項目)
#: 項目前面加 ⚑ = 第 1 週要凍結的跨模組契約。一項最多 15 個中文字寬（英數算半個），手冊的版面才放得下。
BRANCHES = {
    "m1": [
        ("API", False, ["註冊／登入／登出", "密碼與忘記密碼（寄信）", "個人資料與理財習慣", "登入裝置", "平台管理員停權"]),
        ("畫面", False, ["註冊與登入", "個人化設定", "忘記與重設密碼", "個人資料", "平台管理"]),
        ("共用", False, ["設定與資料庫連線", "增刪改查 crud", "路由守衛 guards", "資料表與 Alembic"]),
        ("LLM", True, ["模型呼叫層（逾時、重試）", "回傳 JSON 交給 Pydantic"]),
    ],
    "m2": [
        ("API", False, ["明細增刪改查", "nlp 單句／段落解析", "nlp 確認寫入", "⚑ 分類體系", "帳本：開、封存、結算"]),
        ("畫面", False, ["段落記帳", "單筆手動", "收支明細", "帳本"]),
        ("LLM", True, ["段落切分策略", "欄位抽取 prompt", "低信心判準"]),
    ],
    "m3": [
        ("API", False, ["摘要與統計", "預算與存款目標", "階段性提醒", "財務建議"]),
        ("畫面", False, ["總覽（我／全家）", "統計圖表", "建議卡片"]),
        ("LLM", True, ["建議生成 prompt", "邊界規則"]),
    ],
    "m4": [
        ("API", False, ["家庭綁定與解散", "成員角色", "監管關係與零用金", "通知", "稽核紀錄"]),
        ("畫面", False, ["家庭成員與邀請", "成員紀錄（唯讀）", "通知鈴鐺"]),
        ("LLM", True, ["留出集人工標註", "零樣本 vs few-shot", "正確率與 Macro-F1"]),
    ],
}

MAX_LEAF = 15


def _width(s):
    """版面寬度：中文一個字算 1，英數與空白算 0.55。"""
    return sum(0.55 if ord(ch) < 128 else 1 for ch in s)


def load():
    """[(member, [(分支, is_llm, [項目]), ...]), ...]；資料表從 models 讀。"""
    from app import models
    from app.ownership import MEMBERS

    order = list(models.TABLES)                          # 照 app/models/__init__.py 的順序
    out = []
    for m in MEMBERS:
        tables = []
        for f in m.files + m.shared:
            if not re.match(r"app/models/[a-z]\w*\.py$", f):
                continue
            mod = importlib.import_module(f[:-3].replace("/", "."))
            for obj in vars(mod).values():
                name = getattr(obj, "__tablename__", None)
                if name and getattr(obj, "__module__", "") == mod.__name__ and name not in tables:
                    tables.append(name)
        tables.sort(key=order.index)
        branches = [("資料表", False, tables)] + BRANCHES[m.key]
        for _, _, items in branches:
            for it in items:
                if _width(it) > MAX_LEAF:
                    raise SystemExit("心智圖的「%s」超過 %d 個字，手冊版面放不下" % (it, MAX_LEAF))
        out.append((m, branches))
    return out


# ---------------------------------------------------------------------------
# SVG
# ---------------------------------------------------------------------------
W = 1000
COL_ROOT, ROOT_W = 12, 180
COL_MEM, MEM_W = 252, 200
COL_CAT = 500
COL_LEAF = 640
LEAF_H, CAT_GAP, MEM_GAP, PAD = 28, 16, 44, 28
SANS = "Noto Sans TC, PingFang TC, Microsoft JhengHei, sans-serif"
SERIF = "Noto Serif TC, Songti TC, Georgia, serif"
WARN = "#FBBF6E"


def _esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _pill(g):
    """分支藥丸的寬度（連線從它的右緣出發）。"""
    return _width(g["k"]) * 14 + 26 + (12 if g["llm"] else 0)


def _edge(x1, y1, x2, y2, c, w, op):
    mx = (x1 + x2) / 2
    return ('<path d="M %.1f %.1f C %.1f %.1f, %.1f %.1f, %.1f %.1f" fill="none" '
            'stroke="%s" stroke-width="%s" opacity="%s" stroke-linecap="round"/>'
            % (x1, y1, mx, y1, mx, y2, x2, y2, c, w, op))


def render_svg(data):
    y = PAD
    tree = []
    for mi, (m, branches) in enumerate(data):
        if mi:
            y += MEM_GAP
        groups = []
        for gi, (k, llm, items) in enumerate(branches):
            if gi:
                y += CAT_GAP
            nodes = []
            for it in items:
                nodes.append({"t": it, "y": y + LEAF_H / 2})
                y += LEAF_H
            groups.append({"k": k, "llm": llm, "items": nodes, "y": (nodes[0]["y"] + nodes[-1]["y"]) / 2})
        tree.append({"m": m, "groups": groups, "y": (groups[0]["y"] + groups[-1]["y"]) / 2})
    H = int(y + PAD + 24)
    root_y = (tree[0]["y"] + tree[-1]["y"]) / 2

    p = ['<rect width="%d" height="%d" fill="url(#bg)"/>' % (W, H)]
    rnd = random.Random(7)                              # 固定種子：每次產生的星星一樣，--check 才比得出來
    for _ in range(130):
        p.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="#E2EAFF" opacity="%.2f"/>'
                 % (rnd.uniform(0, W), rnd.uniform(0, H), rnd.choice([0.6, 0.9, 1.3]), rnd.uniform(0.08, 0.42)))

    for t in tree:
        c = t["m"].color
        p.append(_edge(COL_ROOT + ROOT_W, root_y, COL_MEM, t["y"], c, 2.4, .7))
        for g in t["groups"]:
            gc = WARN if g["llm"] else c
            p.append(_edge(COL_MEM + MEM_W, t["y"], COL_CAT, g["y"], gc, 1.6, .5))
            cw = _pill(g)
            for n in g["items"]:
                p.append(_edge(COL_CAT + cw, g["y"], COL_LEAF, n["y"], gc, 1, .3))

    p.append('<rect x="%d" y="%.1f" width="%d" height="72" rx="18" fill="url(#root)"/>' % (COL_ROOT, root_y - 36, ROOT_W))
    for dy, line in ((-6, "家庭記帳與"), (20, "財務控管系統")):
        p.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="17" font-weight="700" fill="#fff" '
                 'font-family="%s">%s</text>' % (COL_ROOT + ROOT_W / 2, root_y + dy, SERIF, line))

    for t in tree:
        m, c = t["m"], t["m"].color
        p.append('<rect x="%d" y="%.1f" width="%d" height="60" rx="14" fill="#0C1119" stroke="%s" stroke-width="2"/>'
                 % (COL_MEM, t["y"] - 30, MEM_W, c))
        p.append('<rect x="%d" y="%.1f" width="3" height="60" rx="1.5" fill="%s"/>' % (COL_MEM, t["y"] - 30, c))
        p.append('<text x="%d" y="%.1f" font-size="11.5" fill="%s" font-family="%s" opacity=".9">%s　·　%d 支路由</text>'
                 % (COL_MEM + 14, t["y"] - 10, c, SANS, m.label, len(m.routes)))
        p.append('<text x="%d" y="%.1f" font-size="16" font-weight="700" fill="#ECEEF4" font-family="%s">%s</text>'
                 % (COL_MEM + 14, t["y"] + 11, SERIF, _esc(m.domain)))
        p.append('<text x="%d" y="%.1f" text-anchor="end" font-size="10" fill="#565D70" '
                 'font-family="ui-monospace, monospace">%s</text>' % (COL_MEM + MEM_W - 12, t["y"] + 24, m.branch))
        for g in t["groups"]:
            gc = WARN if g["llm"] else c
            label = g["k"] + (" ★" if g["llm"] else "")
            cw = _pill(g)
            p.append('<rect x="%d" y="%.1f" width="%.1f" height="26" rx="13" fill="%s" fill-opacity="%s" '
                     'stroke="%s" stroke-opacity=".65" stroke-width="1.2"/>'
                     % (COL_CAT, g["y"] - 13, cw, gc, ".22" if g["llm"] else ".09", gc))
            p.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="12.5" font-weight="600" fill="#ECEEF4" '
                     'font-family="%s">%s</text>' % (COL_CAT + cw / 2, g["y"] + 4.5, SANS, label))
            for n in g["items"]:
                flag = n["t"].startswith("⚑")
                p.append('<circle cx="%d" cy="%.1f" r="2.6" fill="%s" opacity=".7"/>' % (COL_LEAF, n["y"], gc))
                p.append('<text x="%d" y="%.1f" font-size="12.5" fill="%s" font-family="%s">%s</text>'
                         % (COL_LEAF + 10, n["y"] + 4.5, WARN if flag else "#A7ADBD", SANS, _esc(n["t"])))

    total = sum(len(m.routes) for m, _ in data)
    p.append('<text x="%d" y="%d" font-size="11.5" fill="#565D70" font-family="%s">'
             '★ 該模組自己的 LLM 工作　·　⚑ 第 1 週要凍結的跨模組契約　·　共 %d 支路由</text>'
             % (COL_ROOT, H - 30, SANS, total))
    p.append('<text x="%d" y="%d" font-size="11.5" fill="#565D70" font-family="%s">'
             '一個檔案剛好一個主人　·　由 backend/tools/sync_mindmap.py 從 ownership.py 與 models/ 產生，不要手改</text>'
             % (COL_ROOT, H - 12, SANS))

    defs = ('<radialGradient id="bg" cx="46%" cy="40%" r="76%">'
            '<stop offset="0%" stop-color="#151C36"/><stop offset="54%" stop-color="#0A0E1C"/>'
            '<stop offset="100%" stop-color="#05060A"/></radialGradient>'
            '<linearGradient id="root" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0%" stop-color="#6C9FFB"/><stop offset="100%" stop-color="#8B7CF0"/></linearGradient>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d">'
            '<defs>%s</defs>%s</svg>' % (W, H, W, H, defs, "".join(p)))


# ---------------------------------------------------------------------------
# 手冊的互動版（只換 TREE 這一段資料，排版程式不動）
# ---------------------------------------------------------------------------
def _js(s):
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def render_tree(data):
    rows = []
    for m, branches in data:
        groups = []
        for k, llm, items in branches:
            cells = []
            for it in items:
                if it.startswith("⚑"):
                    cells.append("{ t: %s, flag: true }" % _js(it[1:].strip() + " ⚑"))
                else:
                    cells.append(_js(it))
            groups.append("      { k: %s%s, items: [%s] }" % (_js(k), ", llm: true" if llm else "", ", ".join(cells)))
        rows.append("    { dom: %s, c: 'var(--%s)', api: '%d 支', branch: %s, groups: [\n%s\n    ]}"
                    % (_js(m.domain), m.key, len(m.routes), _js(m.branch), ",\n".join(groups)))
    return "  var TREE = [\n" + ",\n".join(rows) + "\n  ];"


def patch_handbook(text, data):
    a = text.index("  var TREE = [")
    b = text.index("\n  ];", a) + len("\n  ];")
    return text[:a] + render_tree(data) + text[b:]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    data = load()

    svg_now = io.open(SVG, encoding="utf-8").read() if os.path.exists(SVG) else ""
    hb_now = io.open(HANDBOOK, encoding="utf-8").read()
    svg_new, hb_new = render_svg(data), patch_handbook(hb_now, data)

    stale = [p for p, now, new in ((SVG, svg_now, svg_new), (HANDBOOK, hb_now, hb_new)) if now != new]
    if args.check:
        if stale:
            print("心智圖跟 ownership.py／models 不一致，請跑 python backend/tools/sync_mindmap.py：")
            for p in stale:
                print("  " + os.path.relpath(p, REPO))
            return 1
        print("心智圖跟 ownership.py／models 一致")
        return 0
    io.open(SVG, "w", encoding="utf-8", newline="").write(svg_new)
    io.open(HANDBOOK, "w", encoding="utf-8", newline="").write(hb_new)
    for p in stale:
        print("已更新：" + os.path.relpath(p, REPO))
    if not stale:
        print("心智圖本來就是最新的")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())
