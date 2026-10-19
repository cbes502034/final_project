"""測試報告共用的排版：HTML 片段 → Chrome 無頭模式印成 PDF。

深色底、全直角、蒂芬妮綠強調；每一頁上下留白靠 box-decoration-break: clone（@page 邊界設 0 才鋪得滿深色底）。
"""
from __future__ import annotations

import html
import os
import subprocess
import sys

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]

CSS = """
@page { size: A4; margin: 0; }
:root {
  --bg: #0b0f14; --panel: #111821; --line: #1f2a36; --ink: #e6edf3; --soft: #a9b6c3; --faint: #74828f;
  --accent: #0ABAB5; --hi: #2BFFE0; --ok: #3fd18b; --warn: #f2b84b; --bad: #ff6b6b; --info: #6cb6ff;
}
* { box-sizing: border-box; border-radius: 0 !important; }
html, body { background: var(--bg); margin: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { color: var(--ink); font-family: "Microsoft JhengHei", "Noto Sans TC", sans-serif; font-size: 10pt; line-height: 1.65; }
.doc { padding: 15mm 15mm 14mm; box-decoration-break: clone; -webkit-box-decoration-break: clone;
  background-image: linear-gradient(var(--line) 1px, transparent 1px), linear-gradient(90deg, var(--line) 1px, transparent 1px);
  background-size: 12mm 12mm; background-position: -1px -1px; }
.doc > * { position: relative; }
.cover { min-height: 250mm; display: flex; flex-direction: column; justify-content: space-between; page-break-after: always; }
.cover .eyebrow { color: var(--accent); letter-spacing: .18em; font-size: 9pt; font-family: Consolas, monospace; }
.cover h1 { font-size: 30pt; line-height: 1.25; margin: 6mm 0 4mm; color: #fff; }
.cover .lede { color: var(--soft); font-size: 11.5pt; max-width: 150mm; }
.meta { border: 1px solid var(--line); background: rgba(17,24,33,.92); padding: 5mm 6mm; display: grid; grid-template-columns: 34mm 1fr; gap: 2mm 6mm; font-size: 9.5pt; }
.meta b { color: var(--faint); font-weight: 400; }
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 3mm; margin: 6mm 0; }
.kpi { border: 1px solid var(--line); border-top: 2px solid var(--accent); background: rgba(17,24,33,.92); padding: 3.5mm 4mm; }
.kpi .v { font-family: Consolas, monospace; font-size: 18pt; color: #fff; line-height: 1.2; }
.kpi .k { color: var(--soft); font-size: 8.5pt; }
h2 { font-size: 15pt; color: #fff; margin: 9mm 0 3mm; padding-bottom: 1.5mm; border-bottom: 1px solid var(--accent); page-break-after: avoid; }
h2 .n { color: var(--accent); font-family: Consolas, monospace; margin-right: 3mm; }
h3 { font-size: 11.5pt; color: var(--hi); margin: 6mm 0 2mm; page-break-after: avoid; }
p { margin: 0 0 2.5mm; color: var(--ink); }
.soft { color: var(--soft); }
.small { font-size: 8.5pt; color: var(--soft); }
table { width: 100%; border-collapse: collapse; margin: 2mm 0 4mm; font-size: 8.8pt; background: rgba(17,24,33,.94); page-break-inside: auto; }
thead { display: table-header-group; }
tr { page-break-inside: avoid; }
th { text-align: left; color: var(--accent); font-weight: 700; border-bottom: 1px solid var(--accent); padding: 1.8mm 2mm; white-space: nowrap; }
td { border-bottom: 1px solid var(--line); padding: 1.8mm 2mm; vertical-align: top; color: var(--ink); }
td.num, th.num { text-align: right; font-family: Consolas, monospace; white-space: nowrap; }
td.mono { font-family: Consolas, monospace; font-size: 8.3pt; }
.tag { display: inline-block; padding: 0 1.6mm; border: 1px solid currentColor; font-size: 7.8pt; font-family: Consolas, monospace; white-space: nowrap; }
.p0 { color: var(--bad); } .p1 { color: var(--warn); } .p2 { color: var(--info); } .p3 { color: var(--soft); }
.ok { color: var(--ok); } .bad { color: var(--bad); } .warn { color: var(--warn); }
.note { border-left: 2px solid var(--accent); background: rgba(10,186,181,.07); padding: 3mm 4mm; margin: 3mm 0 4mm; color: var(--soft); page-break-inside: avoid; }
.note b { color: var(--ink); }
ul { margin: 0 0 3mm; padding-left: 5mm; } li { margin: 0 0 1mm; }
.split { display: grid; grid-template-columns: 1fr 1fr; gap: 4mm; }
.bar { height: 2.2mm; background: var(--line); position: relative; }
.bar i { position: absolute; left: 0; top: 0; bottom: 0; background: var(--accent); }
.break { page-break-before: always; }
.foot { margin-top: 8mm; color: var(--faint); font-size: 8pt; border-top: 1px solid var(--line); padding-top: 2mm; }
"""


def e(text: object) -> str:
    return html.escape(str(text))


def table(header: list[str], rows: list[list[str]], num_cols: tuple[int, ...] = (), widths: list[str] | None = None) -> str:
    """rows 的每一格是已經處理好的 HTML（要顯示純文字請先過 e()）。"""
    cols = ""
    if widths:
        cols = "<colgroup>" + "".join('<col style="width:%s">' % w for w in widths) + "</colgroup>"
    head = "".join('<th class="%s">%s</th>' % ("num" if i in num_cols else "", h) for i, h in enumerate(header))
    body = "".join("<tr>" + "".join('<td class="%s">%s</td>' % ("num" if i in num_cols else "", c)
                                    for i, c in enumerate(r)) + "</tr>" for r in rows)
    return '<table>%s<thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (cols, head, body)


def tag(text: str, cls: str) -> str:
    return '<span class="tag %s">%s</span>' % (cls, e(text))


def build(title: str, body: str, out_pdf: str) -> str:
    """把 body 包成完整頁面，印成 out_pdf。回傳 PDF 路徑。"""
    out_pdf = os.path.abspath(out_pdf)
    page = ('<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><title>%s</title><style>%s</style></head>'
            '<body><div class="doc">%s</div></body></html>') % (e(title), CSS, body)
    html_path = os.path.splitext(out_pdf)[0] + ".html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(page)
    chrome = next((c for c in CHROME_CANDIDATES if os.path.exists(c)), None)
    if not chrome:
        sys.exit("找不到 Chrome 或 Edge，印不了 PDF")
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    "--print-to-pdf=" + out_pdf, "file:///" + html_path.replace("\\", "/")],
                   check=True, capture_output=True)
    os.remove(html_path)
    return out_pdf
