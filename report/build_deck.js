// 報告簡報產生器：node report/build_deck.js → report/家庭記帳_期末報告.pptx
//
// 數字全部從 report/data/facts.json 讀（python report/collect.py 產生），截圖在 report/assets/（report/screenshot.py）。
// 模型評測跑完、測試重跑之後：python report/collect.py && node report/build_deck.js，簡報就更新了。
//
// 版型：16:9 寬版；深藍封面與結尾、白底內容頁；截圖放在白色圓角框裡（整份的視覺母題）。
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const Fi = require("react-icons/fi");
const { applyTheme } = require("./lib/apply_theme.js");

const HERE = __dirname;
const facts = JSON.parse(fs.readFileSync(path.join(HERE, "data", "facts.json"), "utf8"));
const asset = (n) => path.join(HERE, "assets", n);
const OUT = path.join(HERE, "家庭記帳_期末報告.pptx");

const THEME = {
  name: "FamBudget",
  headFontFace: "Microsoft JhengHei",
  bodyFontFace: "Microsoft JhengHei",
  colors: {
    dk1: "16233F", lt1: "FFFFFF", dk2: "0B2A5B", lt2: "EEF3FA",
    accent1: "1F5FBF", accent2: "13A07A", accent3: "E8663D", accent4: "F2B33D",
    accent5: "6B7A99", accent6: "9DBDF0", hlink: "1F5FBF", folHlink: "6B7A99",
  },
};
const HEX = THEME.colors;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "家庭記帳 FamBudget 期末報告";
pres.author = "冠文、宇傑、明樺、囷洧";
const C = pres.SchemeColor;
const W = 13.333;

// ---------------------------------------------------------------- 版型
pres.defineSlideMaster({
  title: "TITLE_DARK",
  background: { color: C.text2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.9, y: 2.0, w: 11.5, h: 1.3, fontSize: 54, bold: true, color: C.background1, valign: "bottom", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.9, y: 3.45, w: 11.5, h: 0.8, fontSize: 24, color: C.accent6, valign: "top", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "meta", type: "body", x: 0.9, y: 6.2, w: 11.5, h: 0.5, fontSize: 16, color: C.accent6, valign: "middle", align: "left", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: C.background1 },
  margin: [0.4, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.1, h: 0.8, fontSize: 32, bold: true, color: C.text2, valign: "middle", align: "left", margin: 0 }, text: "" } },
    { text: { text: "家庭記帳 FamBudget", options: { x: 0.6, y: 7.02, w: 6, h: 0.3, fontSize: 10, color: C.accent5, margin: 0 } } },
  ],
  slideNumber: { x: 12.25, y: 7.02, w: 0.5, h: 0.3, fontSize: 10, color: C.accent5, align: "right" },
});
pres.defineSlideMaster({
  title: "SECTION_DARK",
  background: { color: C.text2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.9, y: 2.6, w: 11.5, h: 1.1, fontSize: 44, bold: true, color: C.background1, valign: "bottom", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.9, y: 3.85, w: 11.5, h: 1.0, fontSize: 20, color: C.accent6, valign: "top", align: "left", margin: 0 }, text: "" } },
  ],
});

// ---------------------------------------------------------------- 小工具
const iconCache = {};
async function icon(name, hex) {
  const key = name + hex;
  if (!iconCache[key]) {
    const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Fi[name], { color: "#" + hex, size: 256 }));
    const png = await sharp(Buffer.from(svg)).png().toBuffer();
    iconCache[key] = "image/png;base64," + png.toString("base64");
  }
  return iconCache[key];
}
const shadow = () => ({ type: "outer", color: HEX.dk2, opacity: 0.14, blur: 10, offset: 3, angle: 90 });

async function iconCircle(slide, name, x, y, d, fill, fg, id) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { color: fill }, objectName: id + "-circle" });
  const p = d * 0.26;
  slide.addImage({ data: await icon(name, fg), x: x + p, y: y + p, w: d - 2 * p, h: d - 2 * p, objectName: id + "-icon" });
}
function card(slide, x, y, w, h, id, fill) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: 0.14, fill: { color: fill || C.background2 }, line: { color: fill || C.background2 }, objectName: id,
  });
}
/** 截圖放進白色圓角框（整份的視覺母題）。給寬度，高度照圖的比例。 */
function shot(slide, file, x, y, w, ratio, id) {
  const h = w / ratio;
  const pad = 0.09;
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: x - pad, y: y - pad, w: w + 2 * pad, h: h + 2 * pad, rectRadius: 0.12,
    fill: { color: C.background1 }, line: { color: "D6E0EE", width: 0.75 }, shadow: shadow(), objectName: id + "-frame",
  });
  slide.addImage({ path: asset(file), x, y, w, h, objectName: id });
  return h;
}
function text(slide, t, o) {
  slide.addText(t, Object.assign({ isTextBox: true, margin: 0, fontSize: 15, color: C.text1, valign: "top" }, o));
}
function arrow(slide, x, y, w, id, color) {
  slide.addShape(pres.shapes.LINE, { x, y, w, h: 0, line: { color: color || C.accent5, width: 2, endArrowType: "triangle" }, objectName: id });
}
function down(slide, x, y, h, id) {
  slide.addShape(pres.shapes.LINE, { x, y, w: 0, h, line: { color: C.accent5, width: 2, endArrowType: "triangle" }, objectName: id });
}
const pct = (v) => (v === null || v === undefined ? "—" : (v * 100).toFixed(1) + "%");
const fmt = (n) => Number(n).toLocaleString("en-US");
const hdrCell = (t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: THEME.colors.dk2 }, valign: "middle" } });

// ---------------------------------------------------------------- 評測的系統（規則放第一個）
const systems = Object.keys(facts.eval).sort((a, b) => (a === "rules" ? -1 : b === "rules" ? 1 : a.localeCompare(b)));
const sysName = (k) => (k === "rules" ? "前端規則（基準）" : facts.eval[k].model);
const modelSystems = systems.filter((k) => k !== "rules");

async function build() {
  // ============================================================ 開場
  pres.addSection({ title: "開場" });
  let s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "開場" });
  s.addText("家庭記帳 FamBudget", { placeholder: "title" });
  s.addText("說一段話就記好帳、全家看得到彼此的家庭財務系統", { placeholder: "body" });
  s.addText("冠文・宇傑・明樺・囷洧　｜　2026 年 10 月　｜　LLM 應用期末專題", { placeholder: "meta" });
  s.addNotes("大家好，我們的題目是家庭記帳 FamBudget。一句話：使用者說一段話，系統用大型語言模型切成好幾筆帳，家人之間依權限看得到彼此，財務建議的每一個數字都有出處。");

  // ---- 問題
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "開場" });
  s.addText("記帳難在三件事", { placeholder: "title" });
  const pains = [
    ["FiEdit3", C.accent1, "懶得一筆一筆填", "早餐、午餐、加油……每一筆都要選日期、分類、填金額，三天就放棄。",
      "說一段話，模型切成好幾筆、欄位自動填好，人只要檢查"],
    ["FiUsers", C.accent2, "家人各記各的", "爸媽各有一本帳、孩子的零用錢沒人知道，全家花多少錢沒人說得出來。",
      "家庭、帳本、照看孩子；誰看得到誰由權限決定"],
    ["FiTrendingUp", C.accent3, "建議沒有根據", "叫 AI 給理財建議，它可能隨口編一個數字，使用者根本無法驗算。",
      "數字全部由資料庫算，模型只寫句子，每個數字都要找得到出處"],
  ];
  for (let i = 0; i < 3; i++) {
    const [ic, col, head, pain, ours] = pains[i];
    const x = 0.6 + i * 4.1;
    card(s, x, 1.55, 3.85, 5.1, "pain-card-" + i);
    await iconCircle(s, ic, x + 0.35, 1.9, 0.8, col, HEX.lt1, "pain-" + i);
    text(s, head, { x: x + 0.35, y: 2.95, w: 3.15, h: 0.5, fontSize: 22, bold: true, color: C.text2 });
    text(s, pain, { x: x + 0.35, y: 3.55, w: 3.15, h: 1.4, fontSize: 15, color: C.accent5 });
    text(s, "我們的做法", { x: x + 0.35, y: 5.0, w: 3.15, h: 0.35, fontSize: 13, bold: true, color: col });
    text(s, ours, { x: x + 0.35, y: 5.35, w: 3.15, h: 1.1, fontSize: 15, color: C.text1 });
  }
  s.addNotes("記帳 App 很多，但大家還是記不下去。我們觀察到三個問題：輸入太麻煩、家人各記各的、AI 建議沒有根據。後面每一段都對應其中一個問題。");

  // ---- 成果數字
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "開場" });
  s.addText("做出來的東西", { placeholder: "title" });
  const stats = [
    [String(facts.routes_total), "支 API", "認證 %d・記帳 %d・數字 %d・家庭 %d".replace("%d", facts.routes["認證"]).replace("%d", facts.routes["記帳"]).replace("%d", facts.routes["數字"]).replace("%d", facts.routes["家庭"]), C.accent1],
    [String(facts.tables), "張資料表", "PostgreSQL，Alembic 管遷移", C.accent1],
    [fmt(facts.tests), "個自動測試", "全部通過，每一支路由都有驗收測試", C.accent2],
    [facts.e2e ? facts.e2e.passed + "/" + facts.e2e.total : "—", "端到端步驟", "真的伺服器、真的資料庫走完四個領域", C.accent2],
    [String(facts.heldout.cases), "題留出集", "量 AI 解析的成績；另有 " + fmt(facts.train.cases) + " 題微調資料", C.accent3],
  ];
  for (let i = 0; i < stats.length; i++) {
    const [big, unit, sub, col] = stats[i];
    const x = 0.6 + i * 2.46;
    card(s, x, 1.7, 2.26, 3.5, "stat-" + i);
    text(s, big, { x: x + 0.25, y: 2.05, w: 1.9, h: 1.1, fontSize: 48, bold: true, color: col, fontFace: "Calibri" });
    text(s, unit, { x: x + 0.25, y: 3.15, w: 1.9, h: 0.45, fontSize: 18, bold: true, color: C.text2 });
    text(s, sub, { x: x + 0.25, y: 3.7, w: 1.85, h: 1.3, fontSize: 14, color: C.accent5 });
  }
  text(s, "前端：純靜態網頁（HTML／CSS／JS）　後端：FastAPI　資料庫：PostgreSQL　部署：Render　模型：Claude／OpenAI／開源模型（Ollama、Hugging Face）",
    { x: 0.6, y: 5.65, w: 12.1, h: 0.8, fontSize: 15, color: C.accent5 });
  s.addNotes("先講成果。70 支 API、20 張表、735 個自動測試全部通過，還有一個端到端測試，用真的伺服器把四個領域走一遍，全部通過。AI 解析有 101 題的留出集來量成績。");

  // ============================================================ 系統
  pres.addSection({ title: "系統" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "系統" });
  s.addText("系統架構：前後端分離，模型可以換", { placeholder: "title" });
  const box = async (x, y, w, h, ic, title, lines, col, id) => {
    card(s, x, y, w, h, id);
    await iconCircle(s, ic, x + 0.25, y + 0.25, 0.62, col, HEX.lt1, id);
    text(s, title, { x: x + 1.0, y: y + 0.25, w: w - 1.2, h: 0.62, fontSize: 18, bold: true, color: C.text2, valign: "middle" });
    text(s, lines, { x: x + 0.3, y: y + 1.0, w: w - 0.5, h: h - 1.1, fontSize: 14, color: C.text1 });
  };
  await box(0.6, 1.6, 2.9, 2.6, "FiMonitor", "瀏覽器", "手機、電腦都能用\n（RWD：375／768／1280 寬都測過）", C.accent5, "arch-browser");
  await box(4.0, 1.6, 3.2, 2.6, "FiLayout", "前端", "純靜態網頁\napi.js 是唯一的資料入口\n後端沒做好的功能不顯示假資料", C.accent1, "arch-front");
  await box(7.7, 1.6, 5.0, 2.6, "FiServer", "後端 FastAPI", "", C.accent1, "arch-back");
  const doms = [["認證", facts.routes["認證"]], ["記帳", facts.routes["記帳"]], ["數字", facts.routes["數字"]], ["家庭", facts.routes["家庭"]]];
  for (let i = 0; i < 4; i++) {
    const x = 8.0 + i * 1.15;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 2.65, w: 1.0, h: 1.2, rectRadius: 0.1, fill: { color: C.background1 }, line: { color: C.accent6, width: 1 }, objectName: "dom-" + i });
    text(s, doms[i][0], { x, y: 2.75, w: 1.0, h: 0.45, fontSize: 16, bold: true, color: C.accent1, align: "center" });
    text(s, doms[i][1] + " 支", { x, y: 3.2, w: 1.0, h: 0.4, fontSize: 13, color: C.accent5, align: "center" });
  }
  arrow(s, 3.55, 2.9, 0.4, "arch-a1");
  arrow(s, 7.25, 2.9, 0.4, "arch-a2");
  await box(7.7, 4.85, 2.35, 1.85, "FiDatabase", "資料庫", "PostgreSQL\n" + facts.tables + " 張表", C.accent2, "arch-db");
  await box(10.35, 4.85, 2.35, 1.85, "FiCpu", "模型服務", "Claude／OpenAI\n或自架開源模型", C.accent3, "arch-model");
  down(s, 8.85, 4.25, 0.55, "arch-a3");
  down(s, 11.5, 4.25, 0.55, "arch-a4");
  card(s, 0.6, 4.85, 6.6, 1.85, "arch-note", "F7F9FC");
  text(s, [
    { text: "部署在 Render：", options: { bold: true, color: C.text2 } },
    { text: "前端靜態站、後端、資料庫各一個服務。\n", options: {} },
    { text: "模型可以換：", options: { bold: true, color: C.text2 } },
    { text: "設定檔改 MODEL_PROVIDER 就能在 Claude、OpenAI、自己的模型之間切換，程式不用動。\n", options: {} },
    { text: "模型叫不動：", options: { bold: true, color: C.text2 } },
    { text: "後端回 503，前端改用規則解析，系統照常能用。", options: {} },
  ], { x: 0.9, y: 5.05, w: 6.1, h: 1.55, fontSize: 14, color: C.text1, paraSpaceAfter: 4 });
  s.addNotes("架構是前後端分離。前端是純靜態網頁，所有資料都經過 api.js 這一個入口。後端用 FastAPI，依領域分成認證、記帳、數字、家庭四塊。模型服務可以換，叫不動的時候系統不會壞，前端會退回規則解析。");

  // ---- 首頁
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "系統" });
  s.addText("首頁：一眼看到這個月還可以花多少", { placeholder: "title" });
  shot(s, "home.png", 0.7, 1.5, 7.9, 1.6, "shot-home");
  const callouts = [
    ["FiSmile", "嗨，名字＋家庭", "像銀行 App 一樣先打招呼，下面寫是哪個家庭的誰"],
    ["FiPieChart", "這個月還可以花", "收入 − 每月想存＝可支配；用掉幾成一條進度條看完"],
    ["FiGrid", "常用功能", "記一筆、明細、帳本、統計、建議，一格一個入口"],
    ["FiSmartphone", "手機也能用", "版面在手機寬度重新排，沒有左右捲動"],
  ];
  for (let i = 0; i < callouts.length; i++) {
    const y = 1.55 + i * 1.3;
    await iconCircle(s, callouts[i][0], 9.05, y, 0.6, C.accent1, HEX.lt1, "home-c" + i);
    text(s, callouts[i][1], { x: 9.8, y: y - 0.02, w: 2.95, h: 0.4, fontSize: 17, bold: true, color: C.text2 });
    text(s, callouts[i][2], { x: 9.8, y: y + 0.4, w: 2.95, h: 0.8, fontSize: 13, color: C.accent5 });
  }
  s.addNotes("這是登入後的首頁。最重要的數字是「這個月還可以花多少」：收入減掉每月想存的錢，就是可以花的上限。右邊是常用功能。整個網站在手機上也能用。");

  // ---- 明細與統計
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "系統" });
  s.addText("收支明細與統計", { placeholder: "title" });
  shot(s, "entry.png", 0.7, 1.55, 5.85, 1.6, "shot-entry");
  shot(s, "stats.png", 6.8, 1.55, 5.85, 1.6, "shot-stats");
  text(s, [{ text: "收支明細　", options: { bold: true, color: C.text2 } },
    { text: "依帳本、收支、來源（段落記帳／手動）篩選；可以改、可以多選刪除", options: {} }],
  { x: 0.7, y: 5.45, w: 5.85, h: 0.9, fontSize: 14, color: C.text1 });
  text(s, [{ text: "統計　", options: { bold: true, color: C.text2 } },
    { text: "按月收支對照、近六個月趨勢、錢花在哪（分類比例）；全家模式看加總", options: {} }],
  { x: 6.8, y: 5.45, w: 5.85, h: 0.9, fontSize: 14, color: C.text1 });
  s.addNotes("左邊是收支明細，每一筆都標了來源，看得出是段落記帳還是手動記的。右邊是統計，按月對照、近六個月的趨勢，還有錢花在哪。");

  // ---- 家庭與權限
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "系統" });
  s.addText("家庭與權限：誰看得到誰，由後端決定", { placeholder: "title" });
  shot(s, "members.png", 0.7, 1.55, 5.6, 1.6, "shot-members");
  text(s, "邀請碼只顯示一次、可以命名、有效期 7 天、沒用的可以刪；家長可以「照看」孩子並設零用金。",
    { x: 0.7, y: 5.3, w: 5.6, h: 0.9, fontSize: 14, color: C.accent5 });
  const Y = "✓", N = "—";
  const hdr = (t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.text2 }, align: "center", valign: "middle" } });
  const cell = (t, first) => ({ text: t, options: { color: t === Y ? C.accent2 : first ? C.text1 : C.accent5, bold: t === Y, align: first ? "left" : "center", valign: "middle" } });
  const rows = [
    [hdr("能做的事"), hdr("家長"), hdr("子女"), hdr("平台管理員")],
    ["看自己的帳", Y, Y, N], ["看照看中孩子的帳", Y, N, N], ["看全家的總覽", Y, "自己的", N],
    ["產生邀請碼、設零用金", Y, N, N], ["停權帳號、看稽核紀錄", N, N, Y], ["讀任何人的帳", N, N, N],
  ].map((r, i) => (i === 0 ? r : r.map((t, j) => cell(t, j === 0))));
  s.addTable(rows, { x: 6.75, y: 1.55, w: 5.95, colW: [2.75, 1.0, 1.0, 1.2], rowH: 0.55, fontSize: 14,
    border: { type: "solid", color: "D6E0EE", pt: 0.75 }, fill: { color: C.background1 }, objectName: "perm-table" });
  card(s, 6.75, 5.6, 5.95, 0.95, "perm-note", "FFF4EC");
  text(s, "家長不能切換成孩子的帳號、平台管理員讀不到任何人的帳——刻意不做，不是沒做完。",
    { x: 7.0, y: 5.72, w: 5.5, h: 0.75, fontSize: 14, color: C.text1, valign: "middle" });
  s.addNotes("家庭功能的重點是權限。這張表是後端實際的規則：家長看得到照看中孩子的帳，子女看不到家長的；平台管理員只能停權和看稽核，讀不到任何人的帳。家長切換成孩子帳號這個功能，我們刻意不做。");

  // ---- 資料庫
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "系統" });
  s.addText("資料庫：" + facts.tables + " 張表，依四個領域分", { placeholder: "title" });
  const dbcols = [
    ["認證", C.accent1, [["users", "使用者"], ["accounts", "登入帳號"], ["sessions", "登入中的裝置"], ["password_resets", "重設密碼"], ["audit_logs", "稽核紀錄"]]],
    ["記帳", C.accent2, [["transactions", "收支明細"], ["categories", "分類"], ["groups", "帳本"], ["group_members", "帳本成員"], ["nlp_parses", "AI 解析紀錄"]]],
    ["數字", C.accent3, [["budgets", "預算"], ["savings_goals", "存款目標"], ["alert_rules", "提醒門檻"], ["advices", "財務建議"]]],
    ["家庭", C.accent5, [["families", "家庭"], ["family_members", "家庭成員"], ["family_invites", "邀請"], ["guardianships", "照看關係"], ["allowances", "零用金"], ["notifications", "通知"]]],
  ];
  for (let i = 0; i < 4; i++) {
    const [dom, col, tbls] = dbcols[i];
    const x = 0.6 + i * 3.08;
    card(s, x, 1.55, 2.88, 5.1, "db-col-" + i);
    text(s, dom, { x: x + 0.3, y: 1.75, w: 2.3, h: 0.5, fontSize: 20, bold: true, color: col });
    tbls.forEach(([t, zh], j) => {
      const y = 2.4 + j * 0.68;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.25, y, w: 2.38, h: 0.56, rectRadius: 0.08, fill: { color: C.background1 }, line: { color: "D6E0EE", width: 0.75 }, objectName: "tbl-" + t });
      text(s, [{ text: t, options: { fontFace: "Consolas", fontSize: 12, color: C.text1, breakLine: true } }, { text: zh, options: { fontSize: 11, color: C.accent5 } }],
        { x: x + 0.38, y: y + 0.04, w: 2.15, h: 0.5, valign: "middle" });
    });
  }
  s.addNotes("資料庫一共 20 張表，跟 API 一樣依四個領域分。nlp_parses 會記下每一次 AI 解析的原始結果與使用者改了什麼，之後可以拿來當評測與訓練資料。");

  // ============================================================ AI 功能
  pres.addSection({ title: "AI 功能" });
  s = pres.addSlide({ masterName: "SECTION_DARK", sectionTitle: "AI 功能" });
  s.addText("兩個 AI 功能", { placeholder: "title" });
  s.addText("段落記帳（抽取）與財務建議（生成）——模型只做語意判斷，能用程式確定的都不交給模型", { placeholder: "body" });
  s.addNotes("接下來是 AI 的部分。整份設計只有一個原則：模型只做語意判斷，凡是能用程式確定的東西，都不交給模型。");

  // ---- 段落記帳流程
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "AI 功能" });
  s.addText("段落記帳：一段話變成好幾筆", { placeholder: "title" });
  const steps = [
    ["FiMessageSquare", "一段話", "「昨天全聯買衛生紙199，晚上加油」"],
    ["FiFileText", "組 prompt", "規則＋今天日期＋這個家的分類清單＋一組範例"],
    ["FiCpu", "模型用工具交出", "record_transactions：每一筆每一欄都要表態，沒講就填 null"],
    ["FiShield", "程式逐欄驗證", "日期重算、金額對原句、分類要在清單裡"],
    ["FiCheckCircle", "人確認才寫入", "缺的標紅、沒把握的標黃，按確認才存"],
  ];
  for (let i = 0; i < steps.length; i++) {
    const x = 0.6 + i * 2.5;
    card(s, x, 1.5, 2.25, 2.75, "step-" + i);
    await iconCircle(s, steps[i][0], x + 0.25, 1.72, 0.62, i === 2 ? C.accent3 : C.accent1, HEX.lt1, "step-ic-" + i);
    text(s, steps[i][1], { x: x + 0.25, y: 2.45, w: 1.85, h: 0.45, fontSize: 17, bold: true, color: C.text2 });
    text(s, steps[i][2], { x: x + 0.25, y: 2.92, w: 1.85, h: 1.25, fontSize: 14, color: C.accent5 });
    if (i < steps.length - 1) arrow(s, x + 2.27, 2.87, 0.21, "step-a-" + i);
  }
  const exRows = [[hdrCell("原句的那一段"), hdrCell("日期"), hdrCell("金額"), hdrCell("分類"), hdrCell("畫面上")],
    ["昨天全聯買衛生紙199", "10/14（程式依「昨天」算）", "199", "日用品", "正常"],
    ["晚上加油", "10/15", "（沒講）", "交通", "金額標紅、補上才能送"]].map((r, i) => (i === 0 ? r : r.map((t) => ({ text: t, options: { color: C.text1 } }))));
  s.addTable(exRows, { x: 0.6, y: 4.5, w: 12.1, colW: [3.0, 2.9, 1.5, 1.5, 3.2], rowH: 0.36, fontSize: 13,
    border: { type: "solid", color: "D6E0EE", pt: 0.75 }, fill: { color: C.background1 }, objectName: "parse-example" });
  card(s, 0.6, 5.75, 12.1, 1.0, "tool-why", "F7F9FC");
  text(s, [
    { text: "為什麼用工具呼叫（function calling），不是叫模型「回 JSON」？\n", options: { bold: true, color: C.text2, fontSize: 15 } },
    { text: "工具的參數有 JSON Schema 約束：每一欄都 required、不收多的欄位，Claude 的 strict 模式保證格式一定對。模型要嘛交出合格的結構，要嘛交不出來——不會有「JSON 少一個括號」這種錯。", options: {} },
  ], { x: 0.9, y: 5.83, w: 11.5, h: 0.88, fontSize: 13, color: C.text1 });
  s.addNotes("段落記帳分五步。第三步是唯一交給模型的：用 record_transactions 這個工具把好幾筆交出來。為什麼用工具呼叫？因為參數有 schema 約束，格式由服務端保證。");

  // ---- 段落記帳畫面
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "AI 功能" });
  s.addText("解析結果：人一眼看得出哪裡要補", { placeholder: "title" });
  shot(s, "parse.png", 0.7, 1.5, 7.9, 1.6, "shot-parse");
  const pc = [
    ["FiCornerDownRight", C.accent1, "原句對照", "每一筆都標出是原句的哪一段（span），切錯一眼就看得到"],
    ["FiAlertCircle", C.accent3, "缺的標紅", "沒講金額就是空的、標「必填」，不會猜一個數字；補上才能送出"],
    ["FiPercent", C.accent4, "沒把握的標黃", "每一欄各自有信心度，低於 85% 標黃顯示百分比"],
    ["FiCloudOff", C.accent5, "模型叫不動也能用", "後端回 503 時，前端改用規則切分，寫入照樣走後端"],
  ];
  for (let i = 0; i < pc.length; i++) {
    const y = 1.55 + i * 1.3;
    await iconCircle(s, pc[i][0], 9.05, y, 0.6, pc[i][1], HEX.lt1, "parse-c" + i);
    text(s, pc[i][2], { x: 9.8, y: y - 0.02, w: 2.95, h: 0.4, fontSize: 17, bold: true, color: C.text2 });
    text(s, pc[i][3], { x: 9.8, y: y + 0.4, w: 2.95, h: 0.85, fontSize: 13, color: C.accent5 });
  }
  s.addNotes("這是解析完的畫面。每一筆都對照原句的哪一段；沒講金額的那一格是空的、標紅，使用者一定會發現，比猜一個錯的數字安全。");

  // ---- 模型 vs 程式
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "AI 功能" });
  s.addText("模型負責理解，程式負責確定的事", { placeholder: "title" });
  const two = [
    ["FiCpu", C.accent3, "交給模型（語意判斷）", ["把一段話切成幾筆", "「全家」是店名還是家人", "「退款」「賣二手」是收入", "從分類清單挑最像的那一個", "沒講的欄位老實填 null"]],
    ["FiCode", C.accent1, "交給程式（確定的計算）", ["「昨天」「上禮拜三」「9/17」「28號」換成日期", "金額跟原句的數字對不上 → 信心度壓到 50%", "分類一定要在清單裡、收支要對得上", "金額 > 0，抽不到放進 missing", "確認後才寫資料庫（全部成功或全部不寫）"]],
  ];
  for (let i = 0; i < 2; i++) {
    const [ic, col, head, items] = two[i];
    const x = 0.6 + i * 6.15;
    card(s, x, 1.55, 5.95, 3.95, "split-" + i);
    await iconCircle(s, ic, x + 0.35, 1.8, 0.7, col, HEX.lt1, "split-ic-" + i);
    text(s, head, { x: x + 1.25, y: 1.8, w: 4.4, h: 0.7, fontSize: 20, bold: true, color: C.text2, valign: "middle" });
    s.addText(items.map((t, j) => ({ text: t, options: { bullet: true, breakLine: j < items.length - 1 } })),
      { x: x + 0.35, y: 2.75, w: 5.3, h: 2.6, fontSize: 15, color: C.text1, paraSpaceAfter: 8, valign: "top", isTextBox: true, margin: 0 });
  }
  card(s, 0.6, 5.75, 12.1, 0.9, "date-why", "FFF4EC");
  text(s, "為什麼日期不給模型算：模型最常錯的就是差一天，而這種錯使用者幾乎不會發現，月統計卻已經跑掉。",
    { x: 0.9, y: 5.85, w: 11.5, h: 0.7, fontSize: 15, color: C.text1, valign: "middle" });
  s.addNotes("這張是整個設計的核心。左邊是模型擅長的語意判斷；右邊是可以用程式算死的東西。例如句子裡寫上禮拜三，模型就算給錯日期，程式也會依原句重算。");

  // ---- 財務建議
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "AI 功能" });
  s.addText("財務建議：每一個數字都要找得到出處", { placeholder: "title" });
  const adv = [["資料庫算數字", "收入、支出、各分類、可支配上限"], ["先算好比例", "支出佔收入、用掉幾成、各分類佔比"],
    ["模型只寫句子", "結構化輸出；理財習慣標成「資料，不是指令」"], ["檢查數字出處", "找不到出處的那一則，信心度壓到 30%"]];
  for (let i = 0; i < adv.length; i++) {
    const x = 0.6 + i * 3.1;
    card(s, x, 1.55, 2.85, 1.75, "adv-" + i);
    text(s, adv[i][0], { x: x + 0.3, y: 1.75, w: 2.3, h: 0.45, fontSize: 17, bold: true, color: i === 2 ? C.accent3 : C.text2 });
    text(s, adv[i][1], { x: x + 0.3, y: 2.25, w: 2.35, h: 0.95, fontSize: 13, color: C.accent5 });
    if (i < adv.length - 1) arrow(s, x + 2.88, 2.42, 0.19, "adv-a-" + i);
  }
  const ex = [
    ["FiCheckCircle", C.accent2, "有出處，照常顯示", "「這個月已經用掉 86% 的可支配上限」", "86% 是程式先算好的比例 → 信心度照模型給的"],
    ["FiAlertTriangle", C.accent3, "沒出處，標成要自己驗算", "「照這樣一年會花 103,200 元」", "103,200 是模型自己乘出來的 → 信心度 30%，畫面標出來"],
  ];
  for (let i = 0; i < 2; i++) {
    const [ic, col, head, quote, why] = ex[i];
    const x = 0.6 + i * 6.15;
    card(s, x, 3.6, 5.95, 2.1, "adv-ex-" + i, i ? "FFF4EC" : "EAF7F2");
    await iconCircle(s, ic, x + 0.3, 3.8, 0.55, col, HEX.lt1, "adv-ex-ic-" + i);
    text(s, head, { x: x + 1.05, y: 3.8, w: 4.6, h: 0.55, fontSize: 17, bold: true, color: C.text2, valign: "middle" });
    text(s, quote, { x: x + 0.3, y: 4.5, w: 5.4, h: 0.5, fontSize: 16, color: C.text1, italic: true });
    text(s, why, { x: x + 0.3, y: 5.0, w: 5.4, h: 0.6, fontSize: 13, color: C.accent5 });
  }
  text(s, "邊界規則：不給投資、保險、稅務建議；不對個人做價值判斷（不說「你太浪費」）；使用者填的理財習慣只當背景。",
    { x: 0.6, y: 5.95, w: 12.1, h: 0.7, fontSize: 14, color: C.text1 });
  s.addNotes("財務建議的原則是數字由資料庫算，模型只寫句子。模型寫回來之後，程式會把每一個數字拿去比對出處。像一年會花十萬三千二這種模型自己乘出來的數字，就會被標成要自己驗算。");

  // ============================================================ 評測與測試
  pres.addSection({ title: "評測與測試" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "評測與測試" });
  s.addText("怎麼量 AI 解析的成績", { placeholder: "title" });
  const tags = Object.entries(facts.heldout.tags);
  s.addChart(pres.charts.BAR, [{ name: "題數", labels: tags.map((t) => t[0]), values: tags.map((t) => t[1]) }], {
    x: 0.6, y: 1.5, w: 6.2, h: 5.2, barDir: "bar", chartColors: [HEX.accent1],
    showTitle: true, title: "留出集 " + facts.heldout.cases + " 題（" + facts.heldout.items + " 筆）的題型", titleFontSize: 15, titleColor: HEX.dk2, titleFontFace: "+mn-lt",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11, dataLabelColor: HEX.accent5, dataLabelFontFace: "+mn-lt",
    catAxisLabelColor: HEX.dk1, catAxisLabelFontSize: 12, catAxisLabelFontFace: "+mn-lt", catAxisOrientation: "maxMin",
    valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false, barGapWidthPct: 45,
    objectName: "chart-tags",
  });
  const metrics = [["切分正確率", "切出來的筆數跟答案一樣"], ["整題完全正確", "筆數對、每一筆四欄都對"], ["日期／金額／收支／分類", "逐欄正確率"],
    ["分類 Macro-F1", "小分類跟大分類一樣重要"], ["沒講金額卻填數字", "幻覺率：答案是空的、模型卻給了數字"], ["延遲", "p50／p95 秒數"]];
  text(s, "看什麼", { x: 7.2, y: 1.55, w: 5.5, h: 0.45, fontSize: 18, bold: true, color: C.text2 });
  metrics.forEach(([m, d], i) => {
    const y = 2.1 + i * 0.62;
    text(s, [{ text: m + "　", options: { bold: true, color: C.text1 } }, { text: d, options: { color: C.accent5 } }], { x: 7.2, y, w: 5.5, h: 0.55, fontSize: 14 });
  });
  card(s, 7.2, 5.95, 5.5, 0.75, "eval-note", "F7F9FC");
  text(s, "答案由 AI 產生，再用程式獨立驗算金額、日期、收支（0 錯）；人工抽查 " + facts.heldout.checked + " 題。",
    { x: 7.4, y: 6.0, w: 5.15, h: 0.65, fontSize: 12, color: C.accent5, valign: "middle" });
  s.addNotes("我們用 101 題、125 筆的留出集來量解析的成績，題型包含一段多筆、中文數字、相對日期、沒講金額這些難點。只比日期、金額、收支、分類四欄。");

  // ---- 評測結果
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "評測與測試" });
  s.addText(modelSystems.length ? "評測結果：模型 vs 前端規則" : "評測結果：前端規則的基準線", { placeholder: "title" });
  const M = [["切分", (r) => r.split_acc], ["整題完全正確", (r) => r.case_exact], ["日期", (r) => r.field_acc.date],
    ["金額", (r) => r.field_acc.amount], ["分類", (r) => r.field_acc.cat], ["分類 Macro-F1", (r) => r.cat_macro_f1]];
  const series = systems.map((k) => ({ name: sysName(k), labels: M.map((m) => m[0]), values: M.map((m) => +((m[1](facts.eval[k].report) || 0) * 100).toFixed(1)) }));
  const palette = [HEX.accent5, HEX.accent1, HEX.accent2, HEX.accent3];
  s.addChart(pres.charts.BAR, series, {
    x: 0.6, y: 1.5, w: modelSystems.length ? 12.1 : 7.6, h: 5.2, barDir: "col", barGrouping: "clustered", chartColors: palette.slice(0, series.length),
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11, dataLabelColor: HEX.dk1, dataLabelFontFace: "+mn-lt", dataLabelFormatCode: "0.0",
    catAxisLabelColor: HEX.dk1, catAxisLabelFontSize: 13, catAxisLabelFontFace: "+mn-lt",
    valAxisMinVal: 0, valAxisMaxVal: 100, valAxisLabelColor: HEX.accent5, valAxisLabelFontSize: 11, valAxisLabelFontFace: "+mn-lt",
    valGridLine: { color: "E3E9F2", size: 0.75 }, catGridLine: { style: "none" },
    showLegend: series.length > 1, legendPos: "t", legendFontSize: 12, legendFontFace: "+mn-lt", legendColor: HEX.dk1,
    showTitle: true, title: "正確率（%）", titleFontSize: 14, titleColor: HEX.dk2, titleFontFace: "+mn-lt", barGapWidthPct: 60,
    objectName: "chart-eval",
  });
  if (!modelSystems.length) {
    card(s, 8.6, 1.6, 4.1, 5.05, "eval-pending", "F7F9FC");
    await iconCircle(s, "FiClock", 8.9, 1.9, 0.6, C.accent4, HEX.dk1, "eval-pending-ic");
    text(s, "模型的成績待補", { x: 9.65, y: 1.92, w: 2.9, h: 0.55, fontSize: 18, bold: true, color: C.text2, valign: "middle" });
    text(s, "規則已經能做到整題完全正確 " + pct(facts.eval.rules.report.case_exact) + "，但錯在模型最擅長的地方：沒見過的說法、相對日期、口語。\n\n" +
      "模型那一欄：在 backend/ 跑\npython tools/eval_nlp.py --label <名稱>\n再跑 report/collect.py 與 build_deck.js，這張圖會自動多一欄。",
    { x: 8.9, y: 2.75, w: 3.55, h: 3.8, fontSize: 13, color: C.text1 });
  }
  s.addNotes("這是評測結果。前端規則的整題完全正確率是 " + pct(facts.eval.rules.report.case_exact) + "。" +
    (modelSystems.length ? "加上模型之後……（依圖說明各欄差異）" : "模型的成績在填好模型設定後跑同一支評測腳本就會補上。"));

  // ---- 錯誤分析
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "評測與測試" });
  const focus = modelSystems.length ? modelSystems[0] : "rules";
  s.addText(focus === "rules" ? "規則錯在哪：這就是需要模型的原因" : "錯誤分析：" + sysName(focus) + " 錯在哪", { placeholder: "title" });
  const seen = new Set();
  const picks = [];
  for (const m of facts.eval[focus].misses) {
    const kind = m.what.slice(0, 2);
    if (seen.has(kind)) continue;
    seen.add(kind);
    picks.push(m);
    if (picks.length >= 5) break;
  }
  const why = { "分類": "沒見過的說法（Uber、Netflix、星巴克）只能猜「其他」", "切成": "「1,250」的逗號被當成兩筆的分隔", "收支": "「賣舊書」「中發票」是收入，規則當成支出",
    "日期": "「上禮拜三」「大前天」「10/1」規則算不出來", "金額": "「155 公車」的 155 被當成金額" };
  const trows = [[hdr("句子"), hdr("錯在哪"), hdr("原因")]].concat(picks.map((p) => [
    { text: p.text, options: { color: C.text1, valign: "middle" } },
    { text: p.what.replace(/expense/g, "支出").replace(/income/g, "收入"), options: { color: C.accent3, valign: "middle" } },
    { text: why[p.what.slice(0, 2)] || "", options: { color: C.accent5, valign: "middle" } },
  ]));
  s.addTable(trows, { x: 0.6, y: 1.55, w: 12.1, colW: [3.6, 4.0, 4.5], rowH: 0.72, fontSize: 13,
    border: { type: "solid", color: "D6E0EE", pt: 0.75 }, fill: { color: C.background1 }, objectName: "miss-table" });
  card(s, 0.6, 6.0, 12.1, 0.75, "miss-take", "F7F9FC");
  text(s, focus === "rules" ? "這幾類錯是模型擅長的語意判斷（沒見過的說法、收入還是支出、哪些數字才是金額）；日期再由程式依原句重算兜底。"
    : "錯誤集中在哪一種題型，看 eval/results 裡的 by_tag；日期類的錯由程式依原句重算兜底。",
  { x: 0.9, y: 6.05, w: 11.5, h: 0.65, fontSize: 14, color: C.text1, valign: "middle" });
  s.addNotes("這幾題是" + (focus === "rules" ? "規則" : sysName(focus)) + "錯的例子，每一種錯誤類型挑一題。");

  // ---- 微調
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "評測與測試" });
  s.addText("加分項：微調自己的小模型當對照組", { placeholder: "title" });
  const ft = [["FiDatabase", "產生訓練資料", fmt(facts.train.cases) + " 題，一半是一段多筆"], ["FiCopy", "轉成對話格式", "prompt 直接用上線那一支，一字不差"],
    ["FiZap", "Colab 免費 T4", "Unsloth QLoRA 微調 Qwen2.5-1.5B"], ["FiPackage", "轉 GGUF", "q4_k_m，約 1 GB"], ["FiCloud", "上線服務", "Ollama 或 Hugging Face Space"],
    ["FiBarChart2", "同一份題目評分", "跟商業 API、規則放在同一張圖"]];
  for (let i = 0; i < ft.length; i++) {
    const x = 0.6 + i * 2.05;
    card(s, x, 1.5, 1.85, 2.7, "ft-" + i);
    await iconCircle(s, ft[i][0], x + 0.25, 1.72, 0.58, i === 2 ? C.accent3 : C.accent1, HEX.lt1, "ft-ic-" + i);
    text(s, ft[i][1], { x: x + 0.2, y: 2.45, w: 1.55, h: 0.7, fontSize: 15, bold: true, color: C.text2 });
    text(s, ft[i][2], { x: x + 0.2, y: 3.15, w: 1.55, h: 1.0, fontSize: 13, color: C.accent5 });
  }
  const pts = [["分類 id 每題打亂", "逼模型讀 prompt 裡的清單，不是背「餐飲＝1」。每個家庭的自訂分類 id 都不一樣。"],
    ["只學回答", "prompt 很長（規則＋分類＋工具定義），loss 不花在背 prompt 上。"],
    ["訓練跟上線一字不差", "訓練資料直接 import 上線的 build_prompt；改了 prompt，測試會紅燈提醒重產資料。"]];
  pts.forEach(([h, d], i) => {
    const x = 0.6 + i * 4.1;
    card(s, x, 4.5, 3.85, 2.2, "ft-pt-" + i, "F7F9FC");
    text(s, h, { x: x + 0.3, y: 4.7, w: 3.3, h: 0.45, fontSize: 18, bold: true, color: C.text2 });
    text(s, d, { x: x + 0.3, y: 5.2, w: 3.3, h: 1.4, fontSize: 15, color: C.text1 });
  });
  s.addNotes("微調是加分項。資料用模板產生 1500 題，prompt 跟上線用的是同一支函式。設計上最重要的一點是分類 id 每題打亂，讓模型學會讀清單。");

  // ---- 測試
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "評測與測試" });
  s.addText("測試：自動測試＋真的伺服器走一遍", { placeholder: "title" });
  card(s, 0.6, 1.55, 3.7, 2.4, "test-unit");
  text(s, fmt(facts.tests), { x: 0.9, y: 1.75, w: 3.2, h: 1.0, fontSize: 48, bold: true, color: C.accent2, fontFace: "Calibri" });
  text(s, "個自動測試，全部通過", { x: 0.9, y: 2.75, w: 3.2, h: 0.45, fontSize: 17, bold: true, color: C.text2 });
  text(s, "每一支路由都有驗收測試，模型呼叫層、日期換算、資料品質也有", { x: 0.9, y: 3.2, w: 3.2, h: 0.7, fontSize: 12, color: C.accent5 });
  card(s, 0.6, 4.2, 3.7, 2.45, "test-e2e");
  text(s, facts.e2e ? facts.e2e.passed + "/" + facts.e2e.total : "—", { x: 0.9, y: 4.4, w: 3.2, h: 1.0, fontSize: 48, bold: true, color: C.accent2, fontFace: "Calibri" });
  text(s, "端到端步驟通過", { x: 0.9, y: 5.4, w: 3.2, h: 0.45, fontSize: 17, bold: true, color: C.text2 });
  const bd = facts.e2e ? facts.e2e.by_domain : {};
  text(s, Object.keys(bd).map((k) => k + " " + bd[k].passed + "/" + bd[k].total).join("　"), { x: 0.9, y: 5.85, w: 3.2, h: 0.7, fontSize: 12, color: C.accent5 });
  text(s, "端到端測試驗到的幾件事", { x: 4.75, y: 1.55, w: 8, h: 0.5, fontSize: 18, bold: true, color: C.text2 });
  const checks = ["沒登入打 API 一律 401", "子女看不到家長的帳（403）", "外人改不了別人的帳", "平台管理員讀不到任何人的帳",
    "邀請碼用過、刪掉就不能再用", "結算後的活動帳本不能再記", "改密碼後其他裝置被登出", "段落確認寫入：全部成功或全部不寫",
    "跨過提醒門檻，鈴鐺出現提醒", "停權的人登不進去，解除後恢復"];
  for (let i = 0; i < checks.length; i++) {
    const col = i % 2, row = Math.floor(i / 2);
    const x = 4.75 + col * 4.0, y = 2.2 + row * 0.86;
    await iconCircle(s, "FiCheck", x, y, 0.42, C.accent2, HEX.lt1, "chk-" + i);
    text(s, checks[i], { x: x + 0.55, y: y - 0.02, w: 3.35, h: 0.46, fontSize: 14, color: C.text1, valign: "middle" });
  }
  s.addNotes("測試分兩層。735 個自動測試在每次改程式時跑；端到端測試則是真的開一台伺服器、用全新的資料庫，從註冊一路走到停權，85 個步驟全部通過。右邊是其中幾個跟安全有關的檢查。");

  // ============================================================ 結語
  pres.addSection({ title: "結語" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "結語" });
  s.addText("限制與下一步", { placeholder: "title" });
  const lim = [
    "留出集與訓練資料由 AI 產生；程式驗算過金額、日期、收支，但句型比真人整齊",
    modelSystems.length ? "模型評測只跑了 " + modelSystems.length + " 個模型，樣本 " + facts.heldout.cases + " 題" : "模型的成績還沒跑，簡報上只有規則的基準線",
    "免費主機會休眠：第一次開要等一下；CPU 跑開源模型一段話要十幾秒",
    "財務建議沒有標準答案，只能用規則檢查（數字出處、邊界）加上人看",
  ];
  const nxt = ["把使用者改過的解析（nlp_parses.user_corrected）收進下一版留出集與訓練資料",
    "微調模型與商業 API 在同一張表比較，決定哪一個上線", "建議加上「跟上個月比」的趨勢敘述（數字一樣由資料庫先算）", "家長端的零用金超支即時通知"];
  const col2 = [["FiAlertTriangle", C.accent3, "限制", lim], ["FiArrowRight", C.accent1, "下一步", nxt]];
  for (let i = 0; i < 2; i++) {
    const [ic, col, head, items] = col2[i];
    const x = 0.6 + i * 6.15;
    card(s, x, 1.55, 5.95, 5.1, "lim-" + i);
    await iconCircle(s, ic, x + 0.35, 1.8, 0.65, col, HEX.lt1, "lim-ic-" + i);
    text(s, head, { x: x + 1.2, y: 1.8, w: 4.4, h: 0.65, fontSize: 20, bold: true, color: C.text2, valign: "middle" });
    s.addText(items.map((t, j) => ({ text: t, options: { bullet: true, breakLine: j < items.length - 1 } })),
      { x: x + 0.35, y: 2.75, w: 5.3, h: 3.7, fontSize: 17, color: C.text1, paraSpaceAfter: 16, valign: "top", isTextBox: true, margin: 0 });
  }
  s.addNotes("最後是限制與下一步。最重要的限制是資料由 AI 產生；下一步是把使用者真的改過的解析收回來，變成真實的評測與訓練資料。");

  s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "結語" });
  s.addText("謝謝聆聽", { placeholder: "title" });
  s.addText("Q & A", { placeholder: "body" });
  s.addText("github.com/cbes502034/final_project　｜　fambudget-web.onrender.com", { placeholder: "meta" });
  s.addNotes("謝謝大家，歡迎提問。");

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("寫好了：" + OUT);
}

build().catch((e) => { console.error(e); process.exit(1); });
