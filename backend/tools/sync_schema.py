# -*- coding: utf-8 -*-
"""把手冊的「各表欄位」那一大段，從 frontend/js/data.js 的 schema 重新產生。

    python backend/tools/sync_schema.py          # 寫回 frontend/docs/index.html
    python backend/tools/sync_schema.py --check  # 只檢查，不寫（測試用）

⚠️ 為什麼要有這支：資料表的欄位同時寫在三個地方——
   data.js 的 schema（正本）、手冊那一大段 HTML、app/models/ 的 SQLAlchemy 類別。
   手改 HTML 一定會漏，漏過好幾次（master_id、notifications、removed_at）。
   所以 HTML 由這支產生；models 則由 tests/test_backend_core.py 逐欄對齊。

需要 node（讀 data.js）。
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
HANDBOOK = os.path.join(REPO, "frontend", "docs", "index.html")
SPEC = os.path.join(REPO, "docs", "01-tech-stack-and-api.md")


def load_schema():
    """用 node 讀 data.js，回傳 (schema, relations)。"""
    script = ("global.window = { __FAMBUDGET_TODAY__: '2026-09-10' };"
              "require(process.argv[1]);"
              "process.stdout.write(JSON.stringify({ schema: window.DATA.schema, relations: window.DATA.relations }));")
    out = subprocess.run(["node", "-e", script, os.path.join(REPO, "frontend", "js", "data.js")],
                         capture_output=True, check=True)
    d = json.loads(out.stdout.decode("utf-8"))
    return d["schema"], d["relations"]


def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_block(schema):
    parts = []
    for i, t in enumerate(schema):
        rows = "".join(
            '<tr><td class="mono"><b>%s</b></td><td class="mono" style="color:var(--accent)">%s</td><td>%s</td></tr>'
            % (name, typ, esc(note)) for name, typ, note in t["cols"])
        parts.append(
            '<details class="acc"%s><summary class="acc__h"><code class="acc__code">%s</code>'
            '<span class="acc__t">%s</span><span class="acc__n">%d 欄</span></summary>'
            '<div class="acc__b"><p class="acc__note">%s</p><div class="tw" style="margin-top:10px"><table><thead><tr>'
            '<th>欄位</th><th>型別</th><th>說明</th></tr></thead><tbody>%s</tbody></table></div></div></details>'
            % (" open" if i == 0 else "", t["t"], esc(t["label"]), len(t["cols"]), esc(t["note"]), rows))
    return '<div class="accs">' + "".join(parts) + "</div>"


def render(handbook, spec, schema, relations):
    n_tables = len(schema)
    n_fk = len(relations)                    # data.js 的 relations：表與表之間的關聯
    a = handbook.index('<div class="accs">')
    b = handbook.index('\n\n      <h3 class="sub">五個設計重點</h3>', a)
    handbook = handbook[:a] + render_block(schema) + handbook[b:]
    handbook = re.sub(r"\d+ 張表、\d+ 條外鍵關聯。", "%d 張表、%d 條外鍵關聯。" % (n_tables, n_fk), handbook)
    handbook = re.sub(r"\d+ 張表一定會改", "%d 張表一定會改" % n_tables, handbook)
    handbook = re.sub(r'<span class="layer__s">\d+ 張表 · Alembic 遷移</span>',
                      '<span class="layer__s">%d 張表 · Alembic 遷移</span>' % n_tables, handbook)
    handbook = re.sub(r"(\d+ API · )\d+( TABLES)", lambda m: m.group(1) + str(n_tables) + m.group(2), handbook)
    spec = re.sub(r"\d+ 張表一定會改", "%d 張表一定會改" % n_tables, spec)
    return handbook, spec


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    schema, relations = load_schema()
    handbook = io.open(HANDBOOK, encoding="utf-8").read()
    spec = io.open(SPEC, encoding="utf-8").read()
    new_handbook, new_spec = render(handbook, spec, schema, relations)
    stale = [p for p, old, new in ((HANDBOOK, handbook, new_handbook), (SPEC, spec, new_spec)) if old != new]
    if args.check:
        if stale:
            print("跟 data.js 的 schema 對不上，跑 python backend/tools/sync_schema.py：" + "、".join(stale))
            return 1
        print("手冊的資料表跟 data.js 一致")
        return 0
    for path, new in ((HANDBOOK, new_handbook), (SPEC, new_spec)):
        io.open(path, "w", encoding="utf-8", newline="").write(new)
    print("已更新：" + ("、".join(os.path.relpath(p, REPO) for p in stale) if stale else "（沒有變）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
