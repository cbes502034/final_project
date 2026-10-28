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
// 可以帶一個檔名另存（PowerPoint 開著舊檔、或不想蓋掉手動修改的時候）：node report/build_deck.js 新檔名.pptx
// 三種版本：
//   node build_deck.js          重點版：開場 3 頁、四個領域各 3 頁、結語 3 頁 → 家庭記帳_期末報告.pptx
//   node build_deck.js --demo   產品展示：照完整流程影片用一輪，畫面為主（15 頁）→ 家庭記帳_產品展示.pptx
//   node build_deck.js --demo2  產品介紹 v2：同一輪、講得更細（畫面標 ①②③ 逐一說明，26 頁）→ 家庭記帳_產品展示_v2.pptx
//   node build_deck.js --full   完整版：每個畫面、評測細節、每一輪測試都有 → 家庭記帳_期末報告_完整版.pptx
const FULL = process.argv.includes("--full");
const DEMO2 = process.argv.includes("--demo2");
const DEMO = process.argv.includes("--demo") || DEMO2;   // v2 沿用產品展示的頁面與版型
const outArg = process.argv.slice(2).find((a) => !a.startsWith("--"));
const OUT = outArg ? path.resolve(outArg)
  : path.join(HERE, DEMO2 ? "家庭記帳_產品展示_v2.pptx" : DEMO ? "家庭記帳_產品展示.pptx" : FULL ? "家庭記帳_期末報告_完整版.pptx" : "家庭記帳_期末報告.pptx");

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
/** 封面與結尾的網站 QR code：白底卡片，深色底上也掃得到。 */
function qr(slide, x, y, id) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 2.3, h: 2.75, rectRadius: 0.12, fill: { color: "FFFFFF" }, line: { color: "FFFFFF" }, objectName: id + "-card" });
  slide.addImage({ path: asset("qr_site.png"), x: x + 0.2, y: y + 0.15, w: 1.9, h: 1.9, objectName: id });
  slide.addText([{ text: "掃描開啟網站", options: { bold: true, breakLine: true } }, { text: "fambudget-web.onrender.com", options: { fontSize: 9 } }],
    { x: x + 0.1, y: y + 2.08, w: 2.1, h: 0.6, fontSize: 12, color: "16233F", align: "center", valign: "middle", margin: 0, objectName: id + "-cap" });
}
/** 右上角的小標籤：重點版寫「領域 n／4・認證」，產品展示寫「步驟 n／6・記帳」，看得出現在講到哪裡 */
function pillTag(slide, label) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 10.85, y: 0.52, w: 1.85, h: 0.46, rectRadius: 0.23,
    fill: { color: "EEF3FA" }, line: { color: "D6E0EE", width: 0.75 }, objectName: "pill-tag" });
  slide.addText(label, { x: 10.85, y: 0.52, w: 1.85, h: 0.46, fontSize: 12, bold: true,
    color: "1F5FBF", align: "center", valign: "middle", margin: 0, objectName: "pill-tag-text" });
}
const pct = (v) => (v === null || v === undefined ? "—" : (v * 100).toFixed(1) + "%");
const fmt = (n) => Number(n).toLocaleString("en-US");
const hdrCell = (t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: THEME.colors.dk2 }, valign: "middle" } });

// ---------------------------------------------------------------- 評測的系統（規則放第一個）
const systems = Object.keys(facts.eval).sort((a, b) => (a === "rules" ? -1 : b === "rules" ? 1 : a.localeCompare(b)));
const sysName = (k) => (k === "rules" ? "前端規則（基準）" : facts.eval[k].model);
const modelSystems = systems.filter((k) => k !== "rules");

async function build() {
  let s;
  let SEC = "開場";
  const DOMAIN_NO = { "認證": 1, "記帳": 2, "數字": 3, "家庭": 4 };
  const STEP_NO = { "開始使用": 1, "記帳": 2, "活動": 3, "家庭": 4, "回顧": 5, "手機": 6 };
  const slide = (master) => {
    const sl = pres.addSlide({ masterName: master, sectionTitle: SEC });
    if (master === "CONTENT") {
      if (DEMO && STEP_NO[SEC]) pillTag(sl, "步驟 " + STEP_NO[SEC] + "／6・" + SEC);
      else if (!DEMO && !FULL && DOMAIN_NO[SEC]) pillTag(sl, "領域 " + DOMAIN_NO[SEC] + "／4・" + SEC);
    }
    return sl;
  };
  const S = {};

  S.cover = async () => {
    s = slide("TITLE_DARK");
    s.addText("家庭記帳 FamBudget", { placeholder: "title" });
    s.addText("說一段話就記好帳、全家看得到彼此的家庭財務系統", { placeholder: "body" });
    s.addText("冠文・宇傑・明樺・囷洧　｜　2026 年 10 月　｜　LLM 應用期末專題", { placeholder: "meta" });
    qr(s, 10.35, 0.75, "qr-cover");
    s.addNotes("大家好，我們的題目是家庭記帳 FamBudget。一句話：使用者說一段話，系統用大型語言模型切成好幾筆帳，家人之間依權限看得到彼此，財務建議的每一個數字都有出處。");
  };

  S.problem = async () => {
    // ---- 問題
    s = slide("CONTENT");
    s.addText("記帳難在三件事", { placeholder: "title" });
    const pains = [
      ["FiEdit3", C.accent1, "懶得一筆一筆填", "早餐、午餐、加油……每一筆都要選日期、分類、填金額，三天就放棄。",
        "說一段話，模型切成好幾筆、欄位自動填好，人只要檢查"],
      ["FiUsers", C.accent2, "家人各記各的", "爸媽各有一本帳、孩子的零用錢沒人知道，全家花多少錢沒人說得出來。",
        "家庭、活動、照看孩子；誰看得到誰由權限決定"],
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
  };

  S.stats = async () => {
    // ---- 成果數字
    s = slide("CONTENT");
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
    s.addNotes("先講成果。" + facts.routes_total + " 支 API、" + facts.tables + " 張表、" + fmt(facts.tests) + " 個自動測試全部通過；端到端測試用真的伺服器把四個領域走一遍，" +
      (facts.e2e ? facts.e2e.passed + " 個步驟全部通過" : "") + "。AI 解析有 " + facts.heldout.cases + " 題的留出集來量成績。");
  };

  S.arch = async () => {
    s = slide("CONTENT");
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
  };

  S.home = async () => {
    // ---- 首頁
    s = slide("CONTENT");
    s.addText("首頁：一眼看到這個月還可以花多少", { placeholder: "title" });
    shot(s, "home.png", 0.7, 1.5, 7.9, 1.6, "shot-home");
    const callouts = [
      ["FiSmile", "嗨，名字＋家庭", "像銀行 App 一樣先打招呼，下面寫是哪個家庭的誰"],
      ["FiPieChart", "這個月還可以花", "收入 − 每月想存；月薪設了入帳日會自動記一筆，入帳前先照預計的算"],
      ["FiGrid", "常用功能", "記一筆、個人帳本、活動管理、財務狀況與建議，一格一個入口"],
      ["FiLayers", "下方面板", "分頁切換、在面板裡捲動；第一頁是今天的紀錄，格式跟明細一樣"],
    ];
    for (let i = 0; i < callouts.length; i++) {
      const y = 1.55 + i * 1.3;
      await iconCircle(s, callouts[i][0], 9.05, y, 0.6, C.accent1, HEX.lt1, "home-c" + i);
      text(s, callouts[i][1], { x: 9.8, y: y - 0.02, w: 2.95, h: 0.4, fontSize: 17, bold: true, color: C.text2 });
      text(s, callouts[i][2], { x: 9.8, y: y + 0.4, w: 2.95, h: 0.8, fontSize: 13, color: C.accent5 });
    }
    s.addNotes("這是登入後的首頁。最重要的數字是「這個月還可以花多少」：收入減掉每月想存的錢，就是可以花的上限；月薪設了入帳日，到了那天會自動記一筆收入。右邊是常用功能。下面是一個分頁面板，第一頁一定是今天的紀錄，格式跟明細一樣，內容在面板裡捲動，整頁不會被拉長。");
  };

  S.entry = async () => {
    // ---- 明細與統計
    s = slide("CONTENT");
    s.addText("收支明細與統計", { placeholder: "title" });
    shot(s, "entry.png", 0.7, 1.55, 5.85, 1.6, "shot-entry");
    shot(s, "stats.png", 6.8, 1.55, 5.85, 1.6, "shot-stats");
    text(s, [{ text: "收支明細　", options: { bold: true, color: C.text2 } },
      { text: "依活動、收支、來源（段落記帳／手動／自動入帳）篩選；可以改、可以多選刪除；過去的月份自動收進年月包裹", options: {} }],
    { x: 0.7, y: 5.45, w: 5.85, h: 0.9, fontSize: 14, color: C.text1 });
    text(s, [{ text: "統計　", options: { bold: true, color: C.text2 } },
      { text: "按月收支對照、近六個月趨勢、錢花在哪（分類比例）；全家模式看加總", options: {} }],
    { x: 6.8, y: 5.45, w: 5.85, h: 0.9, fontSize: 14, color: C.text1 });
    s.addNotes("左邊是收支明細，每一筆都標了來源，看得出是段落記帳還是手動記的。右邊是統計，按月對照、近六個月的趨勢，還有錢花在哪。");
  };

  S.family = async () => {
    // ---- 家庭與權限
    s = slide("CONTENT");
    s.addText("家庭與權限：誰看得到誰，由後端決定", { placeholder: "title" });
    shot(s, "members.png", 0.7, 1.55, 5.6, 1.6, "shot-members");
    text(s, "邀請碼只顯示一次、有效期 7 天；家長「照看」孩子、設零用金，到了發放日自動記一對帳並通知孩子。",
      { x: 0.7, y: 5.3, w: 5.6, h: 0.9, fontSize: 14, color: C.accent5 });
    const Y = "✓", N = "—";
    const hdr = (t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.text2 }, align: "center", valign: "middle" } });
    const cell = (t, first) => ({ text: t, options: { color: t === Y ? C.accent2 : first ? C.text1 : C.accent5, bold: t === Y, align: first ? "left" : "center", valign: "middle" } });
    const rows = [
      [hdr("能做的事"), hdr("家長"), hdr("子女"), hdr("平台管理員")],
      ["看自己的帳", Y, Y, N], ["看照看中孩子的帳", Y, N, N], ["看家庭的帳務", Y, N, N],
      ["產生邀請碼、設零用金", Y, N, N], ["停權、看帳號狀態與安全事件", N, N, Y], ["讀任何人的帳", N, N, N],
    ].map((r, i) => (i === 0 ? r : r.map((t, j) => cell(t, j === 0))));
    s.addTable(rows, { x: 6.75, y: 1.55, w: 5.95, colW: [2.75, 1.0, 1.0, 1.2], rowH: 0.55, fontSize: 14,
      border: { type: "solid", color: "D6E0EE", pt: 0.75 }, fill: { color: C.background1 }, objectName: "perm-table" });
    card(s, 6.75, 5.6, 5.95, 0.95, "perm-note", "FFF4EC");
    text(s, "家長不能切換成孩子的帳號、平台管理員讀不到任何人的帳——刻意不做，不是沒做完。",
      { x: 7.0, y: 5.72, w: 5.5, h: 0.75, fontSize: 14, color: C.text1, valign: "middle" });
    s.addNotes("家庭功能的重點是權限。這張表是後端實際的規則：家長看得到照看中孩子的帳，子女看不到家長的，也不看家庭的帳務；平台管理員只能停權、看帳號狀態與安全事件，讀不到任何人的帳。家長切換成孩子帳號這個功能，我們刻意不做。");
  };

  S.activity = async () => {
    // ---- 活動：個人底下的小帳本（10/26–27 的改版）
    s = slide("CONTENT");
    s.addText("活動：個人底下的小帳本", { placeholder: "title" });
    shot(s, "activity_home.png", 0.7, 1.5, 7.9, 1.6, "shot-activity");
    const acts = [
      ["FiFileText", "這個活動是什麼", "主卡放建立者寫的說明、期間、成員、筆數、目標金額"],
      ["FiCalendar", "開始日與預先規劃", "開始日在以後的先放「預先規劃」，到了那天自動上架並通知成員"],
      ["FiLock", "設定只有建立者能改", "名稱、說明、期間、顏色、目標金額；成員看得到但不能改"],
      ["FiUserPlus", "邀請朋友", "完整 email 或只能用一次的邀請碼；不影響家庭關係"],
      ["FiLogOut", "退出可以合併", "把自己記的幾筆複製到個人帳本；活動裡的原紀錄留著"],
    ];
    for (let i = 0; i < acts.length; i++) {
      const y = 1.5 + i * 1.04;
      await iconCircle(s, acts[i][0], 9.05, y, 0.56, C.accent1, HEX.lt1, "act-c" + i);
      text(s, acts[i][1], { x: 9.75, y: y - 0.04, w: 3.0, h: 0.4, fontSize: 16, bold: true, color: C.text2 });
      text(s, acts[i][2], { x: 9.75, y: y + 0.36, w: 3.0, h: 0.62, fontSize: 12, color: C.accent5 });
    }
    text(s, [{ text: "三種視角　", options: { bold: true, color: C.text2 } },
      { text: "個人＝自己的總帳本；活動＝個人底下的小帳本，各有自己的總覽；家庭＝合併看全家，加上長期目標。活動裡記的帳只算在活動，退出時選「合併」才算進個人。", options: {} }],
    { x: 0.7, y: 6.6, w: 7.9, h: 0.6, fontSize: 12, color: C.text1 });
    s.addNotes("活動是個人底下的小帳本，旅行、搬家、聚餐都可以開一個。活動首頁的主卡放的是「這個活動是什麼」：建立者寫的一句說明、期間、成員、筆數和目標金額，不另外讓使用者填目的。開始日可以選以前或以後，訂在以後的會先放在預先規劃，到了那天自動放進活動選單並通知每位成員。為了避免混亂，活動的設定只有建立者能改，成員看得到但不能動。");
  };

  S.account = async () => {
    // ---- 帳號與資料
    s = slide("CONTENT");
    s.addText("帳號與資料：點了驗證信才開始，登記的都能刪", { placeholder: "title" });
    text(s, "註冊流程", { x: 0.6, y: 1.5, w: 6, h: 0.45, fontSize: 18, bold: true, color: C.text2 });
    const reg = [
      ["FiUserPlus", "填資料", "名字、email、密碼"],
      ["FiMail", "回登入頁去收信", "這時還沒登入，email 先幫他填好"],
      ["FiLogIn", "點信裡的按鈕", "第一次點就直接登入；連結 24 小時有效"],
      ["FiSliders", "個人化設定", "每月想存多少、理財習慣、主題；沒驗證的進不來"],
      ["FiCompass", "新手導覽", "照畫面上看得到的東西帶一遍"],
    ];
    for (let i = 0; i < reg.length; i++) {
      const x = 0.6 + i * 2.5;
      card(s, x, 2.05, 2.25, 2.05, "reg-" + i);
      await iconCircle(s, reg[i][0], x + 0.25, 2.25, 0.55, i === 2 ? C.accent3 : C.accent1, HEX.lt1, "reg-ic-" + i);
      text(s, reg[i][1], { x: x + 0.25, y: 2.88, w: 1.9, h: 0.42, fontSize: 15, bold: true, color: C.text2 });
      text(s, reg[i][2], { x: x + 0.25, y: 3.3, w: 1.9, h: 0.72, fontSize: 12, color: C.accent5 });
      if (i < reg.length - 1) arrow(s, x + 2.27, 2.95, 0.21, "reg-a-" + i);
    }
    text(s, "登記的資料都能刪", { x: 0.6, y: 4.35, w: 6, h: 0.45, fontSize: 18, bold: true, color: C.text2 });
    const delRows = [[hdrCell("資料"), hdrCell("怎麼刪"), hdrCell("刪了之後")],
      ["收支明細", "每列刪除，或多選一次刪", "數字、統計跟著重算"],
      ["財務建議", "展開後「刪除這則建議」", "6 秒內可以按「復原」；全家的只有家長能刪"],
      ["通知", "每則右邊的 ×、「清除已讀」", "只刪自己收到的"],
      ["自訂分類", "標籤後面的 ×（要再輸入密碼）", "用它記的帳改到「其他」，不會消失"],
      ["帳號本身", "個人資料最下面（密碼＋確認碼）", "帳全部刪掉、email 空出來；還在家庭裡要先退出"],
    ].map((r, i) => (i === 0 ? r : r.map((t, j) => ({ text: t, options: { color: j ? C.text1 : C.text2, bold: !j } }))));
    s.addTable(delRows, { x: 0.6, y: 4.85, w: 12.1, colW: [1.9, 4.2, 6.0], rowH: 0.3, fontSize: 12,
      border: { type: "solid", color: "D6E0EE", pt: 0.75 }, fill: { color: C.background1 }, objectName: "del-table" });
    s.addNotes("帳號這一塊有兩個重點。第一，註冊完不會直接登入：畫面回到登入頁、請他去收信，點了信裡的按鈕才登入，接著做個人化設定和新手導覽；還沒驗證的人進不了設定。第二，使用者登記的東西都能自己刪：收支、建議、通知、自訂分類，連帳號本身都可以。刪分類不會讓帳消失，會改到「其他」；刪帳號要再輸入密碼和確認碼，還在家庭裡的要先退出，才不會讓家人的帳本少一個人卻沒人知道。");
  };

  S.admin = async () => {
    // ---- 平台管理
    s = slide("CONTENT");
    s.addText("平台管理：即時看狀態，規則先擋、人來決定", { placeholder: "title" });
    shot(s, "admin.png", 0.7, 1.5, 7.9, 1.6, "shot-admin");
    const adm = [
      ["FiActivity", C.accent2, "紅綠燈", "每個帳號在不在線上，每 10 秒更新；按了登出馬上變紅燈"],
      ["FiAlertOctagon", C.accent3, "錯誤訊息", "後端的 5xx、使用者畫面上出的錯即時列出；使用者只看到白話，技術細節只到這裡"],
      ["FiShield", C.accent1, "規則先擋", "同一帳號 15 分鐘錯 5 次鎖 15 分鐘、同一來源大量註冊、AI 每人每日額度"],
      ["FiUserX", C.accent5, "停權由人按", "規則只暫時擋下、時間到自己解開；要不要停權由管理員決定，每一次都寫稽核"],
    ];
    for (let i = 0; i < adm.length; i++) {
      const y = 1.55 + i * 1.3;
      await iconCircle(s, adm[i][0], 9.05, y, 0.6, adm[i][1], HEX.lt1, "adm-c" + i);
      text(s, adm[i][2], { x: 9.8, y: y - 0.02, w: 2.95, h: 0.4, fontSize: 17, bold: true, color: C.text2 });
      text(s, adm[i][3], { x: 9.8, y: y + 0.4, w: 2.95, h: 0.85, fontSize: 13, color: C.accent5 });
    }
    text(s, "管理員一樣讀不到任何人的帳：這一頁只有身分欄位、狀態與次數（停權是關門，不是配鑰匙）。",
      { x: 0.7, y: 6.62, w: 7.9, h: 0.3, fontSize: 11, color: C.accent5 });
    s.addNotes("這是平台管理員的畫面。上面是即時的數字，左邊每個帳號一個燈號，右邊是被規則擋下的安全事件。規則都是數次數，例如同一個帳號十五分鐘錯五次密碼就先鎖十五分鐘；帳號不存在也一樣鎖，才不會洩漏帳號在不在。規則只暫時擋，要不要停權由管理員決定。我們刻意不讓 AI 自動封鎖：這些都是明確的事實，用規則判斷最準，AI 只會多出誤判跟費用。");
  };

  S.db = async () => {
    // ---- 資料庫
    s = slide("CONTENT");
    s.addText("資料庫：" + facts.tables + " 張表，依四個領域分", { placeholder: "title" });
    const dbcols = [
      ["認證", C.accent1, [["users", "使用者"], ["sessions", "登入中的裝置"], ["password_resets", "重設密碼"], ["security_events", "安全事件"], ["error_logs", "錯誤紀錄"]]],
      ["記帳", C.accent2, [["transactions", "收支明細"], ["accounts", "帳戶（錢包）"], ["categories", "分類"], ["groups", "活動與個人帳本"], ["group_members", "活動成員"], ["nlp_parses", "AI 解析紀錄"]]],
      ["數字", C.accent3, [["budgets", "預算"], ["savings_goals", "存款目標"], ["alert_rules", "提醒門檻"], ["advices", "財務建議"]]],
      ["家庭", C.accent5, [["families", "家庭"], ["family_members", "家庭成員"], ["family_invites", "邀請"], ["guardianships", "照看關係"], ["allowances", "零用金"], ["notifications", "通知"], ["audit_logs", "稽核紀錄"]]],
    ];
    for (let i = 0; i < 4; i++) {
      const [dom, col, tbls] = dbcols[i];
      const x = 0.6 + i * 3.08;
      card(s, x, 1.55, 2.88, 5.1, "db-col-" + i);
      text(s, dom, { x: x + 0.3, y: 1.75, w: 2.3, h: 0.5, fontSize: 20, bold: true, color: col });
      tbls.forEach(([t, zh], j) => {
        const y = 2.35 + j * 0.6;
        s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.25, y, w: 2.38, h: 0.52, rectRadius: 0.08, fill: { color: C.background1 }, line: { color: "D6E0EE", width: 0.75 }, objectName: "tbl-" + t });
        text(s, [{ text: t, options: { fontFace: "Consolas", fontSize: 12, color: C.text1, breakLine: true } }, { text: zh, options: { fontSize: 11, color: C.accent5 } }],
          { x: x + 0.38, y: y + 0.02, w: 2.15, h: 0.48, valign: "middle" });
      });
    }
    s.addNotes("資料庫一共 " + facts.tables + " 張表，跟 API 一樣依四個領域分。nlp_parses 會記下每一次 AI 解析的原始結果與使用者改了什麼，之後可以拿來當評測與訓練資料；security_events 與 error_logs 是平台管理頁即時看的兩張表，都不放任何金額。");
  };

  S.aiDivider = async () => {
    s = slide("SECTION_DARK");
    s.addText("兩個 AI 功能", { placeholder: "title" });
    s.addText("段落記帳（抽取）與財務建議（生成）——模型只做語意判斷，能用程式確定的都不交給模型", { placeholder: "body" });
    s.addNotes("接下來是 AI 的部分。整份設計只有一個原則：模型只做語意判斷，凡是能用程式確定的東西，都不交給模型。");
  };

  S.paraFlow = async () => {
    // ---- 段落記帳流程
    s = slide("CONTENT");
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
  };

  S.paraScreen = async () => {
    // ---- 段落記帳畫面
    s = slide("CONTENT");
    s.addText("解析結果：人一眼看得出哪裡要補", { placeholder: "title" });
    shot(s, "parse.png", 0.7, 1.5, 7.9, 1.6, "shot-parse");
    text(s, "截圖：本機沒接模型時的備援結果（標紅、標黃的方式跟接模型時一樣；線上接的是 Claude）",
      { x: 0.7, y: 6.62, w: 7.9, h: 0.3, fontSize: 11, color: C.accent5 });
    const pc = [
      ["FiCornerDownRight", C.accent1, "只留項目、附原句", "備註只寫買了什麼，例如「自動鉛筆」；原句那一段小字附在下面，切錯一眼就看得到"],
      ["FiAlertCircle", C.accent3, "缺的標紅", "沒講金額就是空的、標「必填」，不會猜一個數字；補上才能送出"],
      ["FiPercent", C.accent4, "沒把握的標黃", "每一欄各自有信心度，低於 85% 標黃顯示百分比"],
      ["FiCloudOff", C.accent5, "模型叫不動也能用", "後端回 503 時先用簡易規則拆好、畫面上講清楚，寫入照樣走後端"],
    ];
    for (let i = 0; i < pc.length; i++) {
      const y = 1.55 + i * 1.3;
      await iconCircle(s, pc[i][0], 9.05, y, 0.6, pc[i][1], HEX.lt1, "parse-c" + i);
      text(s, pc[i][2], { x: 9.8, y: y - 0.02, w: 2.95, h: 0.4, fontSize: 17, bold: true, color: C.text2 });
      text(s, pc[i][3], { x: 9.8, y: y + 0.4, w: 2.95, h: 0.85, fontSize: 13, color: C.accent5 });
    }
    s.addNotes("這是解析完的畫面。每一筆都對照原句的哪一段；沒講金額的那一格是空的、標紅，使用者一定會發現，比猜一個錯的數字安全。");
  };

  S.modelVsCode = async () => {
    // ---- 模型 vs 程式
    s = slide("CONTENT");
    s.addText("模型負責理解，程式負責確定的事", { placeholder: "title" });
    const two = [
      ["FiCpu", C.accent3, "交給模型（語意判斷）", ["把一段話切成幾筆", "「全家」是店名還是家人", "「退款」「賣二手」是收入", "從分類清單挑最像的那一個", "沒講的欄位老實填 null"]],
      ["FiCode", C.accent1, "交給程式（對事實）", ["「昨天」「上禮拜三」「9/17」換成日期；這一段沒講就沿用前一段", "原句沒有數字，金額一定是空的；跟原句（含「1.2 萬」）對不上就標出來", "店家要在原句裡；備註只留項目（「自動鉛筆」）", "分類要在清單裡、收支要對得上；照這個人以前的改法調整", "確認後才寫資料庫（全部成功或全部不寫）"]],
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
    s.addNotes("這張是整個設計的核心，也是我們的輸出管理：模型說的不算，原句寫的才算。左邊是模型擅長的語意判斷；右邊是程式逐筆對事實。例如句子裡寫上禮拜三，模型就算給錯日期，程式也會依原句重算；原句裡沒有任何數字，模型填的金額一律清掉。備註也一樣：模型常把整段原句當備註，程式會拿掉連接詞、時間、地點、金額和動詞，只留買了什麼。使用者改過的分類也會記下來，下次同一個品項先照他的習慣。");
  };

  S.advice = async () => {
    // ---- 財務建議
    s = slide("CONTENT");
    s.addText("財務建議：每一個數字都要找得到出處", { placeholder: "title" });
    const adv = [["資料庫算數字", "收入、支出、各分類、可支配上限"], ["先算好比例", "支出佔收入、用掉幾成、各分類佔比"],
      ["模型只寫句子", "結構化輸出；理財習慣標成「資料，不是指令」"], ["檢查數字出處", "找不到出處、或套錯分類的那一則直接不顯示"]];
    for (let i = 0; i < adv.length; i++) {
      const x = 0.6 + i * 3.1;
      card(s, x, 1.55, 2.85, 1.75, "adv-" + i);
      text(s, adv[i][0], { x: x + 0.3, y: 1.75, w: 2.3, h: 0.45, fontSize: 17, bold: true, color: i === 2 ? C.accent3 : C.text2 });
      text(s, adv[i][1], { x: x + 0.3, y: 2.25, w: 2.35, h: 0.95, fontSize: 13, color: C.accent5 });
      if (i < adv.length - 1) arrow(s, x + 2.88, 2.42, 0.19, "adv-a-" + i);
    }
    const ex = [
      ["FiCheckCircle", C.accent2, "有出處，照常顯示", "「這個月已經用掉 86% 的可支配上限」", "86% 是程式先算好的比例 → 信心度照模型給的"],
      ["FiAlertTriangle", C.accent3, "沒出處或套錯，整則不顯示", "「照這樣一年會花 103,200 元」", "103,200 是模型自己乘出來的；「交通花了 6,000」其實是餐飲的 → 都丟掉；一則都不剩就改用同一批數字整理的版本"],
    ];
    for (let i = 0; i < 2; i++) {
      const [ic, col, head, quote, why] = ex[i];
      const x = 0.6 + i * 6.15;
      card(s, x, 3.6, 5.95, 2.1, "adv-ex-" + i, i ? "FFF4EC" : "EAF7F2");
      await iconCircle(s, ic, x + 0.3, 3.8, 0.55, col, HEX.lt1, "adv-ex-ic-" + i);
      text(s, head, { x: x + 1.05, y: 3.8, w: 4.6, h: 0.55, fontSize: 17, bold: true, color: C.text2, valign: "middle" });
      text(s, quote, { x: x + 0.3, y: 4.5, w: 5.4, h: 0.5, fontSize: 16, color: C.text1, italic: true });
      text(s, why, { x: x + 0.3, y: 5.0, w: 5.4, h: 0.65, fontSize: 12.5, color: C.accent5 });
    }
    text(s, "邊界規則：不給投資、保險、稅務建議；不對個人做價值判斷（不說「你太浪費」）；使用者填的理財習慣只當背景。",
      { x: 0.6, y: 5.95, w: 12.1, h: 0.7, fontSize: 14, color: C.text1 });
    s.addNotes("財務建議的原則是數字由資料庫算，模型只寫句子。模型寫回來之後，程式會把每一個數字拿去比對出處，也檢查有沒有套錯分類。像一年會花十萬三千二這種模型自己乘出來的數字，那一則就不顯示——以前是壓低信心度，但畫面上沒有顯示信心度，錯的數字照樣被當成事實，所以改成直接不要。上線實測時，每一則建議的數字我們都手算對過，11 個數字全對。");
  };

  S.evalHow = async () => {
    s = slide("CONTENT");
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
    text(s, "答案由 AI 產生，再用程式獨立驗算金額、日期、收支（0 錯）" + (facts.heldout.checked ? "；人工抽查 " + facts.heldout.checked + " 題。" : "。"),
      { x: 7.4, y: 6.0, w: 5.15, h: 0.65, fontSize: 12, color: C.accent5, valign: "middle" });
    s.addNotes("我們用 101 題、125 筆的留出集來量解析的成績，題型包含一段多筆、中文數字、相對日期、沒講金額這些難點。只比日期、金額、收支、分類四欄。");
  };

  S.evalResult = async () => {
    // ---- 評測結果
    s = slide("CONTENT");
    s.addText(modelSystems.length ? "評測結果：同一份 " + facts.heldout.cases + " 題，三套系統" : "評測結果：前端規則的基準線", { placeholder: "title" });
    const M = [["切分", (r) => r.split_acc], ["整題完全正確", (r) => r.case_exact], ["日期", (r) => r.field_acc.date],
      ["金額", (r) => r.field_acc.amount], ["分類", (r) => r.field_acc.cat], ["分類 Macro-F1", (r) => r.cat_macro_f1]];
    const series = systems.map((k) => ({ name: sysName(k), labels: M.map((m) => m[0]), values: M.map((m) => +((m[1](facts.eval[k].report) || 0) * 100).toFixed(1)) }));
    const palette = [HEX.accent5, HEX.accent1, HEX.accent2, HEX.accent3];
    s.addChart(pres.charts.BAR, series, {
      x: 0.6, y: 1.5, w: 7.6, h: 5.2, barDir: "col", barGrouping: "clustered", chartColors: palette.slice(0, series.length),
      showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11, dataLabelColor: HEX.dk1, dataLabelFontFace: "+mn-lt", dataLabelFormatCode: "0.0",
      catAxisLabelColor: HEX.dk1, catAxisLabelFontSize: 13, catAxisLabelFontFace: "+mn-lt",
      valAxisMinVal: 0, valAxisMaxVal: 115, valAxisMajorUnit: 20, valAxisLabelColor: HEX.accent5, valAxisLabelFontSize: 11, valAxisLabelFontFace: "+mn-lt",
      valGridLine: { color: "E3E9F2", size: 0.75 }, catGridLine: { style: "none" },
      showLegend: series.length > 1, legendPos: "b", legendFontSize: 12, legendFontFace: "+mn-lt", legendColor: HEX.dk1,
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
    if (modelSystems.length) {
      // 右邊：每一個模型一張小卡，數字跟規則並排
      const rr = facts.eval.rules.report;
      const live = modelSystems.find((k) => /live/.test(k)) || modelSystems[0];
      const small = modelSystems.find((k) => k !== live);
      const L = facts.eval[live].report, S = small ? facts.eval[small].report : null;
      card(s, 8.6, 1.6, 4.1, 5.05, "eval-side", "F7F9FC");
      text(s, "數字背後", { x: 8.9, y: 1.8, w: 3.6, h: 0.45, fontSize: 18, bold: true, color: C.text2 });
      const trio = (f) => pct(f(L)) + "（線上）／" + pct(f(rr)) + "（規則）" + (S ? "／" + pct(f(S)) + "（1.5B）" : "");
      const side = [
        ["整題完全正確", trio((r) => r.case_exact)],
        ["分類 Macro-F1", trio((r) => r.cat_macro_f1)],
        ["沒講金額卻填數字", trio((r) => r.no_amount.hallucination)],
        ["每句要等", L.latency_p50 + " 秒（線上 p50，p95 " + L.latency_p95 + "）" + (S ? "；1.5B 本機 " + S.latency_p50 + " 秒" : "")],
      ];
      side.forEach(([k, v], i) => {
        text(s, k, { x: 8.9, y: 2.35 + i * 0.75, w: 3.6, h: 0.3, fontSize: 12, color: C.accent5 });
        text(s, v, { x: 8.9, y: 2.63 + i * 0.75, w: 3.6, h: 0.45, fontSize: 12.5, bold: true, color: C.text1 });
      });
      text(s, "線上量的是上線那一套：Claude＋輸出管理（程式逐筆對原句）。⚠️ 題目由 AI 產生、句型比真人整齊，100% 不代表不會錯。",
        { x: 8.9, y: 5.4, w: 3.6, h: 1.15, fontSize: 12, color: C.text1 });
    }
    s.addNotes("這是評測結果，三套系統用同一份 " + facts.heldout.cases + " 題。前端規則的整題完全正確率是 " + pct(facts.eval.rules.report.case_exact) + "。" +
      (modelSystems.length
        ? "線上那一套是 Claude 加上我們的輸出管理，直接打部署好的 API 量的，整題完全正確 " +
          pct((facts.eval[modelSystems.find((k) => /live/.test(k)) || modelSystems[0]]).report.case_exact) +
          "。本機的 1.5B 小模型零樣本只有 " + pct((facts.eval[modelSystems.find((k) => !/live/.test(k))] || facts.eval[modelSystems[0]]).report.case_exact) +
          "，分類幾乎亂挑，每句還要等二三十秒。要提醒的是，題目是 AI 產生的，比真人說話整齊，所以一百分不代表不會錯；上線後使用者改過的解析，會收回來當新的題目。"
        : "模型的成績在填好模型設定後跑同一支評測腳本就會補上。"));
  };

  S.errors = async () => {
    // ---- 錯誤分析
    s = slide("CONTENT");
    const focus = modelSystems.find((k) => facts.eval[k].misses.length) || "rules";
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
    const why = focus === "rules"
      ? { "分類": "沒見過的說法（Uber、Netflix、星巴克）只能猜「其他」", "切成": "「1,250」的逗號被當成兩筆的分隔", "收支": "「賣舊書」「中發票」是收入，規則當成支出",
        "日期": "「上禮拜三」「大前天」「10/1」規則算不出來", "金額": "「155 公車」的 155 被當成金額" }
      : { "分類": "不會照分類清單挑，常挑到不相干的分類", "切成": "把一筆切成兩筆，或把兩筆併成一筆", "收支": "收支沒填或填反",
        "日期": "整筆欄位都沒交出來（有時間詞的日期由程式依原句重算）", "金額": "金額漏抄或抄錯；沒講金額時反而自己補一個" };
    const trows = [[hdr("句子"), hdr("錯在哪"), hdr("原因")]].concat(picks.map((p) => [
      { text: p.text, options: { color: C.text1, valign: "middle" } },
      { text: p.what.replace(/expense/g, "支出").replace(/income/g, "收入").replace(/None/g, "（沒填）"), options: { color: C.accent3, valign: "middle" } },
      { text: why[p.what.slice(0, 2)] || "", options: { color: C.accent5, valign: "middle" } },
    ]));
    s.addTable(trows, { x: 0.6, y: 1.55, w: 12.1, colW: [3.6, 4.0, 4.5], rowH: 0.72, fontSize: 13,
      border: { type: "solid", color: "D6E0EE", pt: 0.75 }, fill: { color: C.background1 }, objectName: "miss-table" });
    card(s, 0.6, 6.0, 12.1, 0.75, "miss-take", "F7F9FC");
    text(s, focus === "rules" ? "這幾類錯是模型擅長的語意判斷（沒見過的說法、收入還是支出、哪些數字才是金額）；日期再由程式依原句重算兜底。"
      : "小模型零樣本：分類幾乎亂挑、沒講金額一半會自己補數字，還會把原句轉成簡體。所以上線用 Claude（同一份題目全對），小模型留作微調的對照組。",
    { x: 0.9, y: 6.05, w: 11.5, h: 0.65, fontSize: 14, color: C.text1, valign: "middle" });
    s.addNotes("這幾題是" + (focus === "rules" ? "規則" : sysName(focus)) + "錯的例子，每一種錯誤類型挑一題。線上那一套在這份題目沒有錯題，所以這裡看小模型錯在哪，說明為什麼不能拿它直接上線。");
  };

  S.finetune = async () => {
    // ---- 微調
    s = slide("CONTENT");
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
  };

  S.tests = async () => {
    // ---- 測試
    s = slide("CONTENT");
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
    s.addNotes("測試分兩層。" + fmt(facts.tests) + " 個自動測試在每次改程式時跑；端到端測試則是真的開一台伺服器、用全新的資料庫，從註冊一路走到停權，" +
      (facts.e2e ? facts.e2e.passed + " 個步驟全部通過" : "") + "。右邊是其中幾個跟安全有關的檢查。");
  };

  S.live = async () => {
    // ---- 上線實測
    s = slide("CONTENT");
    s.addText("上線實測：測試工程師與使用者各走一遍", { placeholder: "title" });
    const qa = [
      ["26", "個問題找到並修正", "兩輪合計 P0 2、P1 10、P2 9、P3 5；每一個都重新部署、到線上再驗一次", C.accent3],
      ["4 / 4", "過期後關閉存取", "驗證信、重設密碼、邀請碼、登入權杖：時間到真的用不了", C.accent1],
      ["11 / 11", "建議裡的數字全對", "每一則財務建議的數字都拿帳上的資料手算對過", C.accent2],
      ["0", "三種寬度橫向溢出", "375／768／1280 寬，24 個畫面逐一量過", C.accent2],
    ];
    for (let i = 0; i < qa.length; i++) {
      const [big, unit, sub, col] = qa[i];
      const x = 0.6 + i * 3.08;
      card(s, x, 1.55, 2.88, 2.7, "qa-" + i);
      text(s, big, { x: x + 0.3, y: 1.75, w: 2.4, h: 0.9, fontSize: 40, bold: true, color: col, fontFace: "Calibri" });
      text(s, unit, { x: x + 0.3, y: 2.65, w: 2.4, h: 0.4, fontSize: 16, bold: true, color: C.text2 });
      text(s, sub, { x: x + 0.3, y: 3.1, w: 2.35, h: 1.05, fontSize: 12.5, color: C.accent5 });
    }
    card(s, 0.6, 4.5, 6.0, 2.15, "qa-user");
    text(s, "使用者評分（17 個功能，滿分 100）", { x: 0.9, y: 4.65, w: 5.5, h: 0.4, fontSize: 16, bold: true, color: C.text2 });
    text(s, [{ text: "57.6 → 85.7", options: { bold: true, color: C.accent2, fontSize: 30, fontFace: "Calibri", breakLine: true } },
      { text: "低於 60 分的功能 7 個 → 0 個；修正後最低 80 分。家長、子女各用一個帳號在正式網站上把每個功能實際用過。", options: { fontSize: 13, color: C.accent5 } }],
    { x: 0.9, y: 5.1, w: 5.5, h: 1.45 });
    card(s, 6.85, 4.5, 5.85, 2.15, "qa-files", "F7F9FC");
    text(s, "交付的佐證", { x: 7.15, y: 4.65, w: 5.3, h: 0.4, fontSize: 16, bold: true, color: C.text2 });
    s.addText(["線上測試報告（PDF，每個問題附重現步驟與修正後的驗證）", "使用者評分與改善建議（PDF）", "完整流程影片（在本機從空帳號開始，約 6 分鐘，游標標出每一次點擊）", "AI 線上評測結果與資料庫核對查詢"].map((t, j, a) => ({ text: t, options: { bullet: true, breakLine: j < a.length - 1 } })),
      { x: 7.15, y: 5.1, w: 5.35, h: 1.45, fontSize: 13, color: C.text1, paraSpaceAfter: 4, valign: "top", isTextBox: true, margin: 0 });
    s.addNotes("自動測試之外，我們在部署好的正式網站上，用測試工程師的角度把每個功能實測一遍：收得到的信、寫進資料庫的資料、過期之後關不關得掉、AI 的每一個數字對不對。兩輪一共找到 26 個問題，全部修正、重新部署，再到線上驗一次；第二輪補的是平台管理、防濫用、註冊收信、刪除功能和 AI 的備註。接著換成一般使用者的角度逐項打分，平均從 57.6 分到 85.7 分，低於六十分的功能歸零。");
  };

  S.round3 = async () => {
    // 第三輪：使用者本人看過畫面之後的回饋（10/21）
    s = slide("CONTENT");
    s.addText("第三輪：照使用者的話把畫面收乾淨", { placeholder: "title" });
    shot(s, "groups.png", 0.7, 1.5, 6.9, 1.6, "shot-groups");
    const third = [
      ["FiBookOpen", "帳本只剩一份清單", "不分常設、活動；一顆「開一本帳」，結束日選填"],
      ["FiFilter", "收入、支出各自點進去", "點本月收入只看收入、點支出只看支出"],
      ["FiHome", "寫家庭的名字", "常用功能那格寫「林家」，不寫「家庭帳本」"],
      ["FiDroplet", "主題自己一頁", "八套排成卡片，按一下就換"],
      ["FiEyeOff", "用不到的不掛著", "搜尋、帳本切換只在用得到的頁面出現"],
      ["FiMail", "沒驗證信箱不能登入", "登入給提示；管理頁標「待驗證」，連結過期就從後台消失"],
    ];
    for (let i = 0; i < third.length; i++) {
      const y = 1.45 + i * 0.9;
      await iconCircle(s, third[i][0], 8.0, y, 0.55, C.accent1, HEX.lt1, "third-c" + i);
      text(s, third[i][1], { x: 8.7, y: y - 0.04, w: 4.05, h: 0.4, fontSize: 16, bold: true, color: C.text2 });
      text(s, third[i][2], { x: 8.7, y: y + 0.36, w: 4.05, h: 0.5, fontSize: 12.5, color: C.accent5 });
    }
    s.addNotes("前兩輪是我們用測試帳號替使用者走一遍；第三輪是使用者本人打開網站，指出看了會困惑的地方。共同點是同一件事講太多遍、用不到的東西一直掛著。我們照他的話收乾淨：帳本只剩一份清單、收入支出各自點進去、首頁寫家庭的名字、主題自己一頁、搜尋和帳本切換只在用得到的頁面出現。另外補上信箱驗證的把關：沒點驗證信的帳號不能登入並給提示；平台管理頁把這類帳號標成「待驗證」，驗證連結過期就從後台消失，跟能不能登入同步。");
  };

  S.round4 = async () => {
    // 第四輪：組員改版（活動、個人大帳本）之後，使用者逐項看過再提的規格（10/26–27）
    s = slide("CONTENT");
    s.addText("第四輪：活動與家庭的細節", { placeholder: "title" });
    shot(s, "home_panel.png", 0.7, 1.5, 6.9, 1.6, "shot-home-panel");
    const fourth = [
      ["FiDollarSign", "零用金自動記帳", "發放日自動記一對帳；改金額只調原本那對，家長刪了孩子那筆一起刪"],
      ["FiBell", "通知即時進鈴鐺", "家庭與活動邀請、零用金、目標金額、活動開始"],
      ["FiTrendingUp", "固定收入自動入帳", "月薪設入帳日就自動記；入帳前先照預計的算"],
      ["FiTarget", "目標金額全員共用", "只有建立者訂；到了通知全部成員"],
      ["FiClock", "開始日與預先規劃", "結束日不能早於今天或開始日；以後才開始的到日上架"],
      ["FiLayers", "總覽下方面板", "今天的紀錄（同明細）｜預算｜家庭的每個人，面板裡捲動"],
    ];
    for (let i = 0; i < fourth.length; i++) {
      const y = 1.45 + i * 0.9;
      await iconCircle(s, fourth[i][0], 8.0, y, 0.55, C.accent1, HEX.lt1, "fourth-c" + i);
      text(s, fourth[i][1], { x: 8.7, y: y - 0.04, w: 4.05, h: 0.4, fontSize: 16, bold: true, color: C.text2 });
      text(s, fourth[i][2], { x: 8.7, y: y + 0.36, w: 4.05, h: 0.5, fontSize: 12.5, color: C.accent5 });
    }
    text(s, "原則：不讓使用者填「目的」或多餘的設定，資訊都從帳本裡來；同一件事不講兩遍。",
      { x: 0.7, y: 6.05, w: 6.9, h: 0.6, fontSize: 13, color: C.accent5 });
    s.addNotes("第四輪是組員把帳本改成活動、加上個人大帳本之後，使用者逐項看過再提的規格。零用金到了發放日自動記一對帳，改金額只調原本那一對；所有通知都即時進鈴鐺；月薪設了入帳日就自動記；活動的目標金額全員共用、只有建立者能改；活動可以先規劃、到了開始日才上架；總覽下方整合成一個分頁面板，第一頁是今天的紀錄，格式跟明細一樣。原則是不讓使用者填多餘的設定，資訊都從帳本來。");
  };

  S.limits = async () => {
    s = slide("CONTENT");
    s.addText("限制與下一步", { placeholder: "title" });
    const lim = [
      "留出集與訓練資料由 AI 產生；程式驗算過金額、日期、收支，但句型比真人整齊——線上那一套全對，不代表真人說的話都對",
      "微調的小模型還沒跑同一份題目；本機 1.5B 零樣本只有 " + (modelSystems.find((k) => !/live/.test(k)) ? pct(facts.eval[modelSystems.find((k) => !/live/.test(k))].report.case_exact) : "—"),
      "財務建議沒有標準答案，只能用規則檢查（數字出處、套錯分類、邊界）加上人看",
      "防濫用的規則只看次數：換來源的攻擊只擋得住「同一個帳號錯太多次」那一條",
      "免費主機會休眠：第一次開要等一下",
    ];
    const nxt = ["把使用者改過的解析（nlp_parses.user_corrected）收進下一版留出集與訓練資料",
      "微調模型跑同一份題目，跟線上那一套放在同一張表比較", "建議加上「跟上個月比」的趨勢敘述（數字一樣由資料庫先算）",
      "家庭改版做到哪裡（下一頁）"];
    const col2 = [["FiAlertTriangle", C.accent3, "限制", lim], ["FiArrowRight", C.accent1, "下一步", nxt]];
    for (let i = 0; i < 2; i++) {
      const [ic, col, head, items] = col2[i];
      const x = 0.6 + i * 6.15;
      card(s, x, 1.55, 5.95, 5.1, "lim-" + i);
      await iconCircle(s, ic, x + 0.35, 1.8, 0.65, col, HEX.lt1, "lim-ic-" + i);
      text(s, head, { x: x + 1.2, y: 1.8, w: 4.4, h: 0.65, fontSize: 20, bold: true, color: C.text2, valign: "middle" });
      s.addText(items.map((t, j) => ({ text: t, options: { bullet: true, breakLine: j < items.length - 1 } })),
        { x: x + 0.35, y: 2.75, w: 5.3, h: 3.7, fontSize: 15, color: C.text1, paraSpaceAfter: 10, valign: "top", isTextBox: true, margin: 0 });
    }
    s.addNotes("最後是限制與下一步。最重要的限制是資料由 AI 產生；下一步是把使用者真的改過的解析收回來，變成真實的評測與訓練資料。");
  };

  S.redo = async () => {
    // 家庭改版做到哪裡：原本規劃的「開放式家庭」（docs/06）跟使用者後來定的規格對照
    s = slide("CONTENT");
    s.addText("家庭改版：已完成的與決定不做的", { placeholder: "title" });
    const redo = [
      ["FiCheckCircle", C.accent2, "已完成：活動取代帳本", "活動有自己的邀請（帳號或邀請碼）；成員可退出並把自己的明細合併到個人帳本；設定只有建立者能改"],
      ["FiCheckCircle", C.accent2, "已完成：三種視角", "個人大帳本＋年月包裹；活動有自己的總覽與目標金額；家庭看合併總覽與長期目標"],
      ["FiCheckCircle", C.accent2, "已完成：自動記帳與通知", "零用金、固定收入到日自動記帳；邀請、零用金、目標金額、活動開始都即時進鈴鐺"],
      ["FiMinusCircle", C.accent3, "決定不做：成員一律平等", "保留家長／子女與照看——零用金與對孩子的保護都靠它；子女看不到家庭帳務，可以自己退出家庭"],
      ["FiMinusCircle", C.accent3, "決定不做：分帳、花費上限", "分帳不屬於記帳；活動只用一個目標金額提醒，存錢或控制花費由使用者自己解讀"],
    ];
    for (let i = 0; i < redo.length; i++) {
      const [ic, col, head, body] = redo[i];
      const y = 1.5 + i * 1.02;
      card(s, 0.6, y, 12.1, 0.9, "redo-" + i);
      await iconCircle(s, ic, 0.8, y + 0.15, 0.6, col, HEX.lt1, "redo-ic-" + i);
      text(s, head, { x: 1.6, y: y + 0.1, w: 3.2, h: 0.7, fontSize: 17, bold: true, color: C.text2, valign: "middle" });
      text(s, body, { x: 4.8, y: y + 0.08, w: 7.7, h: 0.74, fontSize: 13, color: C.text1, valign: "middle" });
    }
    s.addNotes("這是家庭改版做到哪裡。原本規劃的是開放式家庭；實際做下來，活動取代了帳本、加上個人大帳本與三種視角，零用金和固定收入到日自動記帳，所有通知即時進鈴鐺。有兩件是使用者看過之後決定不做的：成員一律平等——保留家長、子女與照看，因為零用金和對孩子的保護都靠它；還有分帳和花費上限——分帳不屬於記帳，活動只用一個目標金額提醒。");
  };

  S.thanks = async () => {
    s = slide("TITLE_DARK");
    s.addText("謝謝聆聽", { placeholder: "title" });
    s.addText("Q & A", { placeholder: "body" });
    s.addText("github.com/cbes502034/final_project　｜　fambudget-web.onrender.com", { placeholder: "meta" });
    qr(s, 10.35, 0.75, "qr-end");
    s.addNotes("謝謝大家，歡迎提問。");
  };

  /** 左邊一張截圖、右邊幾行「圖示＋標題＋說明」：重點版的新頁都用這個版型 */
  const shotWithPoints = async (file, items, id, ratio) => {
    shot(s, file, 0.7, 1.5, 6.9, ratio || 1.6, "shot-" + id);
    const gap = items.length > 5 ? 0.9 : 1.02;
    for (let i = 0; i < items.length; i++) {
      const y = 1.45 + i * gap;
      await iconCircle(s, items[i][0], 8.0, y, 0.55, C.accent1, HEX.lt1, id + "-c" + i);
      text(s, items[i][1], { x: 8.7, y: y - 0.04, w: 4.05, h: 0.4, fontSize: 16, bold: true, color: C.text2 });
      text(s, items[i][2], { x: 8.7, y: y + 0.36, w: 4.05, h: 0.55, fontSize: 12.5, color: C.accent5 });
    }
  };

  // ---- 認證：帳號安全（技術）
  S.security = async () => {
    s = slide("CONTENT");
    s.addText("帳號安全：每一道關卡都在後端", { placeholder: "title" });
    await shotWithPoints("danger.png", [
      ["FiKey", "登入權杖", "JWT：30 分鐘的 access token＋refresh token；改密碼後其他裝置全部登出"],
      ["FiLock", "密碼只存雜湊", "不存明碼；忘記密碼寄 30 分鐘有效的重設連結（Brevo）"],
      ["FiMail", "沒驗證不能登入", "點了驗證信才開始；連結過期就失效"],
      ["FiAlertOctagon", "防濫用", "登入失敗、註冊都有次數上限；被擋下的寫進安全事件"],
      ["FiShield", "權限守衛", "每支路由先檢查登入、停權、身分；前端藏按鈕不算權限"],
      ["FiTrash2", "危險動作再確認", "刪除要再輸入自己的密碼；刪帳號另外要確認碼"],
    ], "sec");
    text(s, "左圖：刪除一筆帳之前，要輸入自己的密碼。", { x: 0.7, y: 5.95, w: 6.9, h: 0.4, fontSize: 12, color: C.accent5 });
    s.addNotes("帳號安全的每一道關卡都在後端。登入用 JWT，access token 30 分鐘、搭配 refresh token，改了密碼其他裝置會被登出。密碼只存雜湊；忘記密碼用 Brevo 寄 30 分鐘有效的重設連結。沒點驗證信不能登入。登入失敗和註冊有次數上限，被擋下來的會寫進安全事件，平台管理員看得到。每支路由都先過權限守衛，前端把按鈕藏起來只是介面，不算權限。刪除這類危險動作，要再輸入自己的密碼。");
  };

  // ---- 數字：統計、預算與提醒
  S.budget = async () => {
    s = slide("CONTENT");
    s.addText("統計、預算與提醒", { placeholder: "title" });
    await shotWithPoints("stats.png", [
      ["FiBarChart2", "收支對照", "按月、按年；近六個月的趨勢"],
      ["FiPieChart", "錢花在哪", "分類比例，跟總覽、明細同一個來源"],
      ["FiSliders", "分類預算", "替常花的分類設上限；總覽面板第二頁看用了幾成"],
      ["FiBell", "階段性提醒", "自己設門檻（例如 50%、80%），跨過就進鈴鐺"],
      ["FiTarget", "存錢與目標金額", "每月想存多少；活動的目標金額全員共用，到了通知"],
    ], "bud");
    s.addNotes("數字這個領域負責算錢。統計頁看收支對照、近六個月的趨勢和錢花在哪，數字跟總覽、明細是同一個來源。預算是替常花的分類設上限；提醒的門檻由使用者自己設，跨過就進鈴鐺。另外還有每月想存多少，以及活動的目標金額。");
  };

  // ---- 家庭：照看與零用金
  S.allowance = async () => {
    s = slide("CONTENT");
    s.addText("照看與零用金：到了發放日自動記帳", { placeholder: "title" });
    await shotWithPoints("allowance.png", [
      ["FiUserPlus", "邀請家人", "完整 email 或 7 天有效的邀請碼；送出前先選身分"],
      ["FiEye", "開始照看", "家長按「開始照看」才看得到孩子的帳；孩子看得到是誰在照看"],
      ["FiDollarSign", "零用金自動記帳", "發放日自動記一對帳：家長一筆支出、孩子一筆收入"],
      ["FiEdit3", "改了只調原本那對", "家長改金額或刪掉，孩子那筆跟著動；孩子不能改刪"],
      ["FiLogOut", "子女可以退出家庭", "只離開家庭，自己的帳都還在"],
    ], "alw");
    s.addNotes("家庭這邊，家長用完整的 email 或 7 天有效的邀請碼邀請家人。孩子加入之後，家長按開始照看，才看得到孩子的帳，孩子也看得到是誰在照看。零用金到了發放日自動記一對帳：家長那邊一筆支出、孩子那邊一筆收入，並通知孩子；家長改金額只調原本那一對，孩子不能自己改刪。");
  };

  // ---- 家庭：即時通知與到期任務（技術）
  S.notify = async () => {
    s = slide("CONTENT");
    s.addText("即時通知與到期任務", { placeholder: "title" });
    await shotWithPoints("kid_bell.png", [
      ["FiBell", "通知都進鈴鐺", "邀請、零用金、固定收入、目標金額、活動開始、孩子記帳"],
      ["FiRefreshCw", "每 5 秒更新", "用 since 只拿新的；做完會產生通知的動作立刻再問一次"],
      ["FiClock", "沒有排程器", "到期的事在有人打開系統時補做：零用金、固定收入、目標金額、活動開始"],
      ["FiCopy", "不會重複", "唯一鍵＋帶條件的 UPDATE：同時好幾個請求只會寫一次"],
      ["FiFileText", "留下紀錄", "家庭裡的重要動作寫進稽核紀錄"],
    ], "ntf");
    s.addNotes("所有通知都即時進鈴鐺。前端每 5 秒問一次，用 since 只拿新的。技術上比較特別的是：免費主機沒有排程器，所以零用金、固定收入、目標金額、活動開始這些到期的事，是在有人打開系統時補做的。打開頁面會同時進來好幾個請求，所以用資料表的唯一鍵和帶條件的 UPDATE，確保同一件事只寫一次。");
  };

  // ---- 技術重點（完整版才有；重點版拆進各領域）
  S.tech = async () => {
    s = slide("CONTENT");
    s.addText("技術重點：規則寫在一個地方，前後端不會走散", { placeholder: "title" });
    const tech = [
      ["FiShield", C.accent1, "權限在後端", "每支路由先過守衛：有沒有登入、被停權、是不是成員或建立者。前端藏按鈕只是介面，真正的檢查在 API（401／403）"],
      ["FiDatabase", C.accent1, "資料表與遷移", "SQLAlchemy 定義 " + facts.tables + " 張表、Alembic 管遷移；部署時先把資料表升到最新版再啟動，不用手動改資料庫"],
      ["FiRepeat", C.accent2, "沒有排程器的到期任務", "零用金、固定收入、目標金額、活動開始，都在有人打開系統時補做；帶條件的 UPDATE 讓同時進來的請求不會重複寫"],
      ["FiKey", C.accent2, "帳號安全", "JWT（30 分鐘＋refresh）、密碼雜湊、驗證信、登入失敗次數限制；刪除這類動作要再輸入密碼"],
      ["FiFileText", C.accent3, "文件就是規格", "每支路由的說明字串寫著完整寫法；測試同時跑「說明裡的程式」和「實際的路由」，兩邊一起過才算數"],
      ["FiLayout", C.accent3, "前端一個入口", "純靜態網頁，api.js 是唯一的資料入口（示範資料與真後端同一套介面）；手機、平板、電腦三種寬度都驗過"],
    ];
    for (let i = 0; i < tech.length; i++) {
      const [ic, col, head, body] = tech[i];
      const x = 0.6 + (i % 3) * 4.1, y = 1.55 + Math.floor(i / 3) * 2.6;
      card(s, x, y, 3.85, 2.4, "tech-" + i);
      await iconCircle(s, ic, x + 0.3, y + 0.3, 0.6, col, HEX.lt1, "tech-ic-" + i);
      text(s, head, { x: x + 1.05, y: y + 0.3, w: 2.65, h: 0.6, fontSize: 17, bold: true, color: C.text2, valign: "middle" });
      text(s, body, { x: x + 0.3, y: y + 1.05, w: 3.3, h: 1.25, fontSize: 12.5, color: C.text1 });
    }
    s.addNotes("這頁是技術上的重點：權限一律在後端判斷；資料表用 SQLAlchemy 定義、Alembic 管遷移；沒有排程器，到期的事在有人打開系統時補做；文件就是規格，測試會同時跑說明裡的程式和實際的路由；前端只有 api.js 一個資料入口。");
  };

  // ---- 未來展望
  S.future = async () => {
    s = slide("CONTENT");
    s.addText("未來展望", { placeholder: "title" });
    const future = [
      ["FiCpu", C.accent1, "AI 更準、更省", ["使用者改過的解析收回來，變成真實的評測與微調資料", "微調的小模型上線，降低商業 API 的成本", "建議加上跟上個月比的趨勢與異常提醒"]],
      ["FiCamera", C.accent2, "記帳更省事", ["拍收據、讀電子發票載具自動入帳", "說一句話就變成段落記帳", "房租、訂閱這類固定支出到日自動記"]],
      ["FiSmartphone", C.accent3, "變成手機 App", ["PWA：加到主畫面、沒網路也能先記", "推播通知取代每 5 秒問一次", "用排程器取代「打開系統時補做」"]],
      ["FiHeart", C.accent4, "家庭與理財教育", ["子女的存錢任務與零用金目標", "家庭長期目標拆成每個月的進度", "活動支援多幣別，出國旅行也能記"]],
    ];
    for (let i = 0; i < future.length; i++) {
      const [ic, col, head, items] = future[i];
      const x = 0.6 + i * 3.08;
      card(s, x, 1.55, 2.88, 4.55, "future-" + i);
      await iconCircle(s, ic, x + 0.3, 1.85, 0.7, col, HEX.lt1, "future-ic-" + i);
      text(s, head, { x: x + 0.3, y: 2.75, w: 2.4, h: 0.5, fontSize: 19, bold: true, color: C.text2 });
      s.addText(items.map((t, j) => ({ text: t, options: { bullet: true, breakLine: j < items.length - 1 } })),
        { x: x + 0.3, y: 3.35, w: 2.4, h: 2.6, fontSize: 13.5, color: C.text1, paraSpaceAfter: 8, valign: "top", isTextBox: true, margin: 0 });
    }
    card(s, 0.6, 6.3, 12.1, 0.55, "future-line", "F7F9FC");
    text(s, "方向：從「記得下去」，走到「看得懂自己的錢、全家一起做得到」。",
      { x: 0.9, y: 6.33, w: 11.5, h: 0.5, fontSize: 15, bold: true, color: C.text2, valign: "middle" });
    s.addNotes("最後是未來展望，分四個方向。AI 方面，把使用者真的改過的解析收回來，變成真實的評測和微調資料，讓自己的小模型上線、降低成本。記帳方面，拍收據、讀電子發票載具，讓記帳更省事。產品方面，做成可以加到主畫面的 PWA，用推播取代輪詢、用排程器取代現在的補做。家庭方面，加上子女的存錢任務，讓這套系統也能拿來教孩子理財。");
  };

  // ============================================================ 產品展示（--demo）
  // 照完整流程影片走一輪：畫面為主、說明一兩句。截圖是 record_demo.py --trial --snaps 同一輪拍的（report/assets/demo/）
  const D = (n) => "demo/" + n + ".png";

  /** 一張大圖，右邊三四點說明 */
  const demoSingle = async (file, points, note) => {
    shot(s, D(file), 0.6, 1.45, 8.4, 1.6, "demo-" + file);
    for (let i = 0; i < points.length; i++) {
      const y = 1.55 + i * 1.12;
      await iconCircle(s, "FiCheck", 9.35, y + 0.04, 0.42, C.accent2, HEX.lt1, "demo-pt-" + i);
      text(s, points[i], { x: 9.9, y, w: 2.85, h: 1.0, fontSize: 15, color: C.text1 });
    }
    if (note) text(s, note, { x: 9.35, y: 5.95, w: 3.4, h: 0.75, fontSize: 10.5, color: C.accent5 });
  };
  /** 兩張圖並排，各一句說明 */
  const demoDouble = async (f1, f2, l1, l2, note) => {
    shot(s, D(f1), 0.6, 1.5, 5.95, 1.6, "demo-" + f1);
    shot(s, D(f2), 6.78, 1.5, 5.95, 1.6, "demo-" + f2);
    text(s, l1, { x: 0.6, y: 5.45, w: 5.95, h: 0.9, fontSize: 15, color: C.text1 });
    text(s, l2, { x: 6.78, y: 5.45, w: 5.95, h: 0.9, fontSize: 15, color: C.text1 });
    if (note) text(s, note, { x: 0.6, y: 6.45, w: 12.1, h: 0.4, fontSize: 10.5, color: C.accent5 });
  };

  S.dCover = async () => {
    s = slide("TITLE_DARK");
    s.addText("家庭記帳 FamBudget", { placeholder: "title" });
    s.addText("產品展示：從一個空帳號開始，完整用一輪", { placeholder: "body" });
    s.addText("冠文・宇傑・明樺・囷洧　｜　2026 年 10 月　｜　LLM 應用期末專題", { placeholder: "meta" });
    qr(s, 10.35, 0.75, "qr-cover");
    s.addNotes("大家好，我們是家庭記帳 FamBudget。今天不講程式，直接帶大家從一個空帳號開始，把這個產品完整用一輪。");
  };

  S.dFlow = async () => {
    s = slide("CONTENT");
    s.addText("完整用一輪：六個步驟", { placeholder: "title" });
    shot(s, D("landing"), 0.6, 1.5, 6.6, 1.6, "demo-landing");
    const steps = [
      ["FiUserPlus", "開始使用", "註冊、收驗證信、設定收入與存錢"],
      ["FiEdit3", "記帳", "說一句話，AI 幫你拆成好幾筆"],
      ["FiMap", "活動", "旅行、聚餐各記各的，也能先規劃"],
      ["FiUsers", "家庭", "邀請家人、照看孩子，零用金自動記"],
      ["FiPieChart", "回顧", "錢花在哪；AI 財務建議，數字都有出處"],
      ["FiSmartphone", "手機", "同一套功能，手機上一樣好用"],
    ];
    for (let i = 0; i < steps.length; i++) {
      const y = 1.45 + i * 0.86;
      await iconCircle(s, steps[i][0], 7.6, y, 0.58, C.accent1, HEX.lt1, "flow-" + i);
      text(s, (i + 1) + "　" + steps[i][1], { x: 8.35, y: y - 0.04, w: 4.4, h: 0.38, fontSize: 16, bold: true, color: C.text2 });
      text(s, steps[i][2], { x: 8.35, y: y + 0.33, w: 4.4, h: 0.4, fontSize: 12.5, color: C.accent5 });
    }
    s.addNotes("這是還沒登入時看到的首頁。接下來照這六個步驟走：開始使用、記帳、活動、家庭、回顧，最後看手機版。");
  };

  S.dStart = async () => {
    s = slide("CONTENT");
    s.addText("開始使用：註冊後一步一步設定", { placeholder: "title" });
    await demoDouble("register", "setup",
      "註冊只要名字、email、密碼；點了驗證信才開始用。",
      "設定收入怎麼來、每個月想存多少；月薪設了入帳日，到了就自動記一筆。");
    s.addNotes("註冊只要名字、email 和密碼，點了驗證信就直接登入。接著一步一步設定：收入怎麼來、每個月想存多少。月薪設了入帳日，到了那天會自動記一筆收入。");
  };

  S.dHome = async () => {
    s = slide("CONTENT");
    s.addText("打開就知道：這個月還可以花多少", { placeholder: "title" });
    await demoSingle("home", ["收入 − 每月想存＝這個月可以花的", "月薪已經自動記進來", "常用功能一格一個入口", "第一次進來會問要不要導覽"]);
    s.addNotes("設定好之後的總覽。最大的數字是這個月還可以花多少：收入減掉每月想存的。月薪已經自動記進來了。右邊是常用功能。");
  };

  S.dParse = async () => {
    s = slide("CONTENT");
    s.addText("一句話，記好幾筆", { placeholder: "title" });
    await demoSingle("parse", ["打一段平常講話的句子", "AI 拆成好幾筆，日期、金額、分類都填好", "每一筆看過、可以改，按確認才寫入"]);
    s.addNotes("記帳最麻煩的是一筆一筆填。這裡直接打一段平常講話的句子，例如「早餐蛋餅 45，捷運 30，午餐便當 95」，AI 把它拆成好幾筆、欄位都填好，看過沒問題再按確認寫入。");
  };

  // AI 記帳有多準：數字從評測結果帶入（report/data/facts.json），不手打
  S.dParseAI = async () => {
    s = slide("CONTENT");
    s.addText("AI 記帳：準、快，最後由你確認", { placeholder: "title" });
    const live = (facts.eval[Object.keys(facts.eval).find((k) => /live/.test(k))] || {}).report;
    const rules = facts.eval.rules.report;
    const big = live ? [
      [pct(live.case_exact), "整題完全正確", "同一份 " + facts.heldout.cases + " 題；只用規則是 " + pct(rules.case_exact), C.accent2],
      [live.latency_p50 + " 秒", "一句話解析完", "大部分在 " + live.latency_p95 + " 秒內", C.accent1],
      [pct(live.no_amount.hallucination), "沒講金額卻亂填", "沒講的就留空，讓你自己補", C.accent3],
    ] : [];
    for (let i = 0; i < big.length; i++) {
      const [v, k, sub, col] = big[i];
      const x = 0.6 + i * 4.1;
      card(s, x, 1.5, 3.85, 2.25, "ai-big-" + i);
      text(s, v, { x: x + 0.3, y: 1.65, w: 3.3, h: 0.95, fontSize: 44, bold: true, color: col, fontFace: "Calibri" });
      text(s, k, { x: x + 0.3, y: 2.6, w: 3.3, h: 0.45, fontSize: 18, bold: true, color: C.text2 });
      text(s, sub, { x: x + 0.3, y: 3.08, w: 3.3, h: 0.55, fontSize: 13, color: C.accent5 });
    }
    const how = [
      ["FiMessageCircle", "聽得懂口語", "「昨天」「上禮拜三」、中文數字、店名都認得，一段話裡有幾筆就拆幾筆"],
      ["FiCheckSquare", "程式再對一次", "AI 給的每一筆，程式逐筆對回原句；金額、日期對不上就不採用"],
      ["FiUserCheck", "你說了算", "每一筆都能改，按確認才寫入；改過的都有記錄，之後拿來讓 AI 更準"],
    ];
    for (let i = 0; i < how.length; i++) {
      const x = 0.6 + i * 4.1;
      card(s, x, 4.05, 3.85, 2.6, "ai-how-" + i, "F7F9FC");
      await iconCircle(s, how[i][0], x + 0.3, 4.3, 0.6, C.accent1, HEX.lt1, "ai-how-ic-" + i);
      text(s, how[i][1], { x: x + 1.05, y: 4.3, w: 2.65, h: 0.6, fontSize: 17, bold: true, color: C.text2, valign: "middle" });
      text(s, how[i][2], { x: x + 0.3, y: 5.1, w: 3.3, h: 1.4, fontSize: 13.5, color: C.text1 });
    }
    text(s, "測試題目由 AI 產生、句子比真人說話整齊，100% 不代表不會錯；所以每一筆最後都由你確認。",
      { x: 0.6, y: 6.68, w: 12.1, h: 0.3, fontSize: 10.5, color: C.accent5 });
    s.addNotes("AI 記帳準不準，我們用同一份 " + facts.heldout.cases + " 題來量：上線用的 AI 整題完全正確 " + (live ? pct(live.case_exact) : "") +
      "，只用規則是 " + pct(rules.case_exact) + "；一句話大約 " + (live ? live.latency_p50 : "") + " 秒就拆好。沒講金額的時候，AI 不會自己亂填。" +
      "AI 給的每一筆，程式還會逐筆對回原句再確認一次；最後每一筆都由使用者看過、按確認才寫入。");
  };

  S.dToday = async () => {
    s = slide("CONTENT");
    s.addText("今天記了什麼，一眼看完", { placeholder: "title" });
    await demoDouble("today", "danger",
      "總覽下方的面板：第一頁是今天的紀錄，格式跟明細一樣，可以直接改、刪。",
      "刪除前要輸入自己的密碼，不會一不小心就刪掉。");
    s.addNotes("記完回到總覽，下方的面板第一頁就是今天的紀錄，格式跟明細一樣，可以直接修改或刪除。刪除要輸入自己的密碼，避免誤刪。");
  };

  S.dActivity1 = async () => {
    s = slide("CONTENT");
    s.addText("活動：旅行、聚餐各記各的", { placeholder: "title" });
    await demoDouble("create", "planned",
      "填名稱和一句說明；開始日預設今天，結束日選填。",
      "開始日訂在以後就是「預先規劃」：到了那天才放進活動選單，並通知成員。");
    s.addNotes("活動是個人底下的小帳本，旅行、聚餐都可以開一個。填名稱和一句說明就好。開始日可以訂在以後，這樣會先放在預先規劃，到了那天才放進活動選單，並通知每位成員。");
  };

  S.dActivity2 = async () => {
    s = slide("CONTENT");
    s.addText("活動總覽：一張卡看懂這個活動", { placeholder: "title" });
    await demoDouble("settings", "activity",
      "設定建立後都能改、只有建立者能改；可以訂目標金額、邀請朋友。",
      "說明、期間、成員、筆數、目標進度，一張卡看完。");
    s.addNotes("點開活動可以改設定，但只有建立者能改，避免大家各改各的。可以訂一個目標金額、邀請朋友加入。切到活動之後，總覽的主卡就是這個活動的說明、期間、成員、筆數和目標進度。");
  };

  S.dFamily = async () => {
    s = slide("CONTENT");
    s.addText("家庭：邀請家人一起記", { placeholder: "title" });
    await demoDouble("family", "kid_invite",
      "用完整 email 找到人，選身分（子女／家長）再送出。",
      "對方的總覽最上面就是邀請，按「加入」就進這個家庭。");
    s.addNotes("接著建立家庭、邀請家人。用完整的 email 找到人，選好身分再送出。換成孩子的帳號，總覽最上面就是邀請，按加入就進來了。");
  };

  S.dAllowance = async () => {
    s = slide("CONTENT");
    s.addText("零用金：到了發放日自動記帳", { placeholder: "title" });
    await demoDouble("allowance", "kid_bell",
      "家長照看孩子，設定每月零用金和發放日。",
      "孩子那邊自動多一筆收入，鈴鐺馬上通知。");
    s.addNotes("家長按開始照看之後，可以設定每月零用金和發放日。到了發放日，系統自動記一對帳：家長一筆支出、孩子一筆收入，孩子的鈴鐺也馬上收到通知。");
  };

  S.dStats = async () => {
    s = slide("CONTENT");
    s.addText("回顧：錢花在哪", { placeholder: "title" });
    await demoSingle("stats", ["收支對照：按月、按年", "近六個月的趨勢", "錢花在哪：各分類比例", "數字跟總覽、明細同一個來源"]);
    s.addNotes("回顧的第一步是統計：收支對照、近六個月的趨勢，還有錢花在哪。這些數字跟總覽、明細是同一個來源。");
  };

  S.dAdvice = async () => {
    s = slide("CONTENT");
    s.addText("AI 財務建議：每個數字都找得到出處", { placeholder: "title" });
    await demoSingle("advice", ["按一下，AI 依這個月的帳寫建議", "數字由資料庫先算好，AI 只把它寫成好懂的句子", "每個數字都附算式；檢查不過的那則不顯示", "不推薦投資、保險"]);
    s.addNotes("接著按一下產生建議。這裡的設計是：數字全部由資料庫先算好，AI 只負責把它寫成好懂的句子；每一個數字都附上算式，找得到出處，檢查不通過的那一則就不顯示。AI 也不會推薦投資或保險。");
  };

  S.dMobile = async () => {
    s = slide("CONTENT");
    s.addText("手機也能用", { placeholder: "title" });
    const r = 375 / 812;
    shot(s, D("mobile"), 0.9, 1.45, 2.45, r, "demo-mobile");
    shot(s, D("mobile2"), 3.75, 1.45, 2.45, r, "demo-mobile2");
    const pts = ["底部分頁列：總覽、帳本、記一筆、狀況、建議", "總覽、面板、表格都照手機寬度重排", "從註冊到零用金，整輪在手機上都做得到"];
    for (let i = 0; i < pts.length; i++) {
      const y = 1.9 + i * 1.3;
      await iconCircle(s, "FiCheck", 7.0, y + 0.04, 0.48, C.accent2, HEX.lt1, "mob-pt-" + i);
      text(s, pts[i], { x: 7.65, y, w: 5.0, h: 1.0, fontSize: 17, color: C.text1 });
    }
    s.addNotes("同一套功能在手機上也能用：底部是分頁列，總覽和表格都照手機寬度重新排過。");
  };

  S.dThanks = async () => {
    s = slide("TITLE_DARK");
    s.addText("謝謝觀看", { placeholder: "title" });
    s.addText("Q & A", { placeholder: "body" });
    s.addText("完整操作影片：家庭記帳_完整流程.mp4（約 6 分鐘）　｜　fambudget-web.onrender.com", { placeholder: "meta" });
    qr(s, 10.35, 0.75, "qr-end");
    s.addNotes("以上是完整用一輪的過程，完整的操作影片大約六分鐘。謝謝大家，歡迎提問。");
  };

  // ============================================================ 產品介紹 v2（--demo2）
  // 比產品展示多講細節：畫面上標 ①②③（位置是 record_demo.py --snaps 拍的時候從網頁讀的，見 demo/marks.json），旁邊逐一說明
  const MARKS = fs.existsSync(asset("demo/marks.json")) ? JSON.parse(fs.readFileSync(asset("demo/marks.json"), "utf8")) : {};
  const NUM = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧"];

  /** 截圖＋編號標記（橘色圓點，放在元件左邊） */
  const markShot = (file, x, y, w, ratio, id) => {
    const h = shot(s, D(file), x, y, w, ratio, "v2-" + id);
    const placed = [];
    (MARKS[file] || []).forEach((p, i) => {
      if (!p) return;
      const d = 0.36;
      let mx = Math.max(x - 0.08, x + p[0] * w - d * 0.75);
      const my = y + p[1] * h - d / 2;
      // 兩個編號靠太近就往右錯開，不要疊在一起
      while (placed.some(([px, py]) => Math.abs(px - mx) < d + 0.04 && Math.abs(py - my) < d + 0.04)) mx += d + 0.08;
      placed.push([mx, my]);
      s.addShape(pres.shapes.OVAL, { x: mx, y: my, w: d, h: d, fill: { color: HEX.accent3 }, line: { color: "FFFFFF", width: 1.5 }, objectName: id + "-m" + i });
      s.addText(String(i + 1), { x: mx, y: my, w: d, h: d, fontSize: 12, bold: true, color: "FFFFFF", align: "center", valign: "middle", margin: 0, objectName: id + "-mt" + i });
    });
    return h;
  };
  /** 右邊的編號說明：①標題＋一句說明 */
  const legend = (items, x, y, w, gap) => {
    items.forEach(([head, body], i) => {
      const yy = y + i * gap;
      s.addShape(pres.shapes.OVAL, { x, y: yy, w: 0.36, h: 0.36, fill: { color: HEX.accent3 }, line: { color: HEX.accent3 }, objectName: "lg-c" + i });
      s.addText(String(i + 1), { x, y: yy, w: 0.36, h: 0.36, fontSize: 12, bold: true, color: "FFFFFF", align: "center", valign: "middle", margin: 0, objectName: "lg-n" + i });
      text(s, head, { x: x + 0.5, y: yy - 0.03, w: w - 0.5, h: 0.36, fontSize: 15, bold: true, color: C.text2 });
      text(s, body, { x: x + 0.5, y: yy + 0.32, w: w - 0.5, h: gap - 0.36, fontSize: 12, color: C.accent5 });
    });
  };
  /** 三張圖並排，各一段說明 */
  const tripleShots = (files, labels) => {
    files.forEach((f, i) => {
      const x = 0.6 + i * 4.1;
      shot(s, D(f), x, 1.55, 3.85, 1.6, "v2-tri-" + i);
      text(s, labels[i], { x, y: 4.15, w: 3.85, h: 1.3, fontSize: 14, color: C.text1 });
    });
  };
  /** 右邊打勾的幾點 */
  const checks = async (points, x, y, gap, size) => {
    for (let i = 0; i < points.length; i++) {
      await iconCircle(s, "FiCheck", x, y + i * gap + 0.03, 0.4, C.accent2, HEX.lt1, "v2-ck-" + i);
      text(s, points[i], { x: x + 0.55, y: y + i * gap, w: 12.75 - x - 0.55, h: gap - 0.1, fontSize: size || 14.5, color: C.text1 });
    }
  };

  S.v2Cover = async () => {
    s = slide("TITLE_DARK");
    s.addText("家庭記帳 FamBudget", { placeholder: "title" });
    s.addText("產品介紹：說一段話就記好帳，個人、活動、家庭一起看得懂", { placeholder: "body" });
    s.addText("冠文・宇傑・明樺・囷洧　｜　2026 年 10 月　｜　LLM 應用期末專題", { placeholder: "meta" });
    qr(s, 10.35, 0.75, "qr-cover");
    s.addNotes("大家好，我們是家庭記帳 FamBudget。接下來用一個空帳號，把整個產品從註冊到看建議完整走一輪，每一頁都會講到畫面上的細節。");
  };

  S.v2Why = async () => {
    s = slide("CONTENT");
    s.addText("為什麼做這個產品", { placeholder: "title" });
    const rows = [
      ["FiEdit3", C.accent1, "記帳太麻煩", "早餐、午餐、加油……一筆一筆選日期、分類、填金額，三天就放棄。", "說一段話，AI 拆成好幾筆、欄位都填好，你只要看過按確認"],
      ["FiLayers", C.accent2, "錢分散在不同地方", "自己的生活費、一趟旅行、家裡給孩子的零用錢，混在一起算不清楚。", "個人、活動、家庭三種視角，各算各的，也能合起來看"],
      ["FiHelpCircle", C.accent3, "看了數字不知道怎麼辦", "知道花了多少，卻不知道算不算多、下個月該怎麼調。", "AI 財務建議，每個數字都附算式、找得到出處"],
    ];
    for (let i = 0; i < 3; i++) {
      const [ic, col, head, pain, ours] = rows[i];
      const x = 0.6 + i * 4.1;
      card(s, x, 1.55, 3.85, 5.1, "why-" + i);
      await iconCircle(s, ic, x + 0.35, 1.9, 0.8, col, HEX.lt1, "why-ic-" + i);
      text(s, head, { x: x + 0.35, y: 2.95, w: 3.15, h: 0.5, fontSize: 22, bold: true, color: C.text2 });
      text(s, pain, { x: x + 0.35, y: 3.55, w: 3.15, h: 1.3, fontSize: 14.5, color: C.accent5 });
      text(s, "我們的做法", { x: x + 0.35, y: 4.95, w: 3.15, h: 0.35, fontSize: 13, bold: true, color: col });
      text(s, ours, { x: x + 0.35, y: 5.3, w: 3.15, h: 1.2, fontSize: 15, color: C.text1 });
    }
    s.addNotes("我們想解決三件事：記帳太麻煩、錢分散在不同地方算不清楚、看了數字不知道怎麼辦。對應的做法是：說一段話由 AI 拆帳；個人、活動、家庭三種視角；以及每個數字都有出處的 AI 財務建議。");
  };

  S.v2Views = async () => {
    s = slide("CONTENT");
    s.addText("三種視角，同一套記帳", { placeholder: "title" });
    const views = [
      ["home", "個人", "自己的總帳本：這個月還可以花多少、今天記了什麼"],
      ["activity", "活動", "個人底下的小帳本：一趟旅行、一場聚餐，有自己的總覽和目標"],
      ["family", "家庭", "全家合起來看：家庭的收支、長期目標、照看孩子與零用金"],
    ];
    views.forEach(([f, head, body], i) => {
      const x = 0.6 + i * 4.1;
      shot(s, D(f), x, 1.55, 3.85, 1.6, "v2-view-" + i);
      text(s, head, { x, y: 4.2, w: 3.85, h: 0.5, fontSize: 20, bold: true, color: C.text2 });
      text(s, body, { x, y: 4.72, w: 3.85, h: 1.0, fontSize: 14, color: C.accent5 });
    });
    text(s, "右上角一鍵切換「個人｜家庭」、選活動；底部分頁和常用功能跟著換名字：個人帳本、活動帳本、家庭帳本。",
      { x: 0.6, y: 6.0, w: 12.1, h: 0.6, fontSize: 14, color: C.text1 });
    s.addNotes("這個產品有三種視角，用的是同一套記帳。個人是自己的總帳本；活動是個人底下的小帳本，例如一趟旅行；家庭是全家合起來看。右上角一鍵切換，頁面名稱也跟著換，看名字就知道現在算的是誰的錢。");
  };

  S.v2Setup = async () => {
    s = slide("CONTENT");
    s.addText("開始使用：註冊後三步設定", { placeholder: "title" });
    tripleShots(["register", "setup", "finance"], [
      "註冊：名字、email、密碼（至少 8 個字）。寄驗證信，點了才開始用。",
      "收入與存錢：收入怎麼來（月薪、打工、接案…）、怎麼估、每月想存多少。月薪設入帳日，到了自動記。",
      "理財習慣：理財風格、最在意的事。只拿來讓 AI 建議更貼近你，每一步都能跳過。",
    ]);
    s.addNotes("註冊只要名字、email、密碼，點了驗證信才開始。接著三步設定：收入與存錢、理財習慣、主題。收入的部分可以選收入怎麼來和怎麼估；月薪設了入帳日，到了那天會自動記一筆。每一步都可以跳過。");
  };

  S.v2Theme = async () => {
    s = slide("CONTENT");
    s.addText("挑主題、走一遍導覽", { placeholder: "title" });
    await demoDouble("theme", "tour",
      "八套主題，按一下整個系統就換；存在帳號上，換裝置也一樣。",
      "第一次進來會問要不要導覽，照畫面上看得到的東西一步一步帶，隨時可以跳過。");
    s.addNotes("最後一步挑主題，按一下整個系統就換成那個樣子，設定存在帳號上。進到總覽，第一次會問要不要導覽，照畫面上的東西一步一步帶。");
  };

  S.v2Home = async () => {
    s = slide("CONTENT");
    s.addText("總覽：打開就知道這個月還可以花多少", { placeholder: "title" });
    markShot("home", 0.6, 1.45, 7.9, 1.6, "home");
    legend([
      ["本月收入", "點進去只看這個月的收入；月薪已經自動記進來"],
      ["本月支出", "點進去只看這個月的支出"],
      ["這個月還可以花", "收入 − 每月想存 ＝ 可花上限，再扣掉已經花的"],
      ["已用幾成", "進度條、可花上限、每月想存，超過會變紅"],
      ["常用功能", "記一筆、個人帳本、活動、財務狀況與建議"],
      ["下方面板", "今天的紀錄｜預算使用狀況，在面板裡捲動"],
    ], 8.95, 1.5, 3.8, 0.88);
    s.addNotes("這是總覽。上面兩條是本月收入和支出，點進去只看那一類。中間最大的數字是這個月還可以花多少：收入減掉每月想存就是可花上限，再扣掉已經花的。下面是進度、常用功能，最下面是今天的紀錄和預算的分頁面板。");
  };

  S.v2Parse = async () => {
    s = slide("CONTENT");
    s.addText("一句話，記好幾筆", { placeholder: "title" });
    markShot("parse", 0.6, 1.45, 7.9, 1.6, "parse");
    card(s, 8.95, 1.45, 3.8, 0.95, "parse-in", "F7F9FC");
    text(s, [{ text: "輸入：", options: { bold: true, color: C.text2 } }, { text: "早餐蛋餅 45，捷運 30，午餐便當 95，晚上全聯買牙膏 89", options: { color: C.text1 } }],
      { x: 9.1, y: 1.5, w: 3.55, h: 0.85, fontSize: 12.5, valign: "middle" });
    legend([
      ["原句對照", "每一筆都標出是從哪一句拆出來的"],
      ["日期", "「昨天」「上禮拜三」會自動換算"],
      ["金額", "沒講金額的留空，不會亂填"],
      ["分類", "照你家的分類挑；家庭自訂的也行"],
      ["店家", "「全聯」這類店名自動抓出來"],
      ["確認寫入", "看過、改過，一次寫入全部"],
    ], 8.95, 2.6, 3.8, 0.74);
    s.addNotes("記帳時直接打一段話，例如「早餐蛋餅 45，捷運 30，午餐便當 95，晚上全聯買牙膏 89」。AI 把它拆成四筆：每一筆標出原句、日期自動換算、金額、分類都填好，連店家全聯都抓出來。沒講的金額會留空讓你補，不會亂填。看過沒問題，按確認一次寫入。");
  };

  S.v2Ledger = async () => {
    s = slide("CONTENT");
    s.addText("個人帳本：所有紀錄都在這裡", { placeholder: "title" });
    shot(s, "entry.png", 0.6, 1.45, 7.9, 1.6, "v2-entry");
    await checks(["收支、來源（AI 解析／手動／自動入帳）、活動都能篩", "每一筆都能改；選取多筆一次刪除（要密碼）",
      "上個月以前自動收進「年月包裹」，點開才展開", "右上角搜尋，直接找某一筆"], 8.95, 1.6, 1.15);
    s.addNotes("個人帳本放所有紀錄，可以依收支、來源、活動篩選；每一筆都能修改，也可以選取多筆一次刪除，刪除要輸入密碼。上個月以前的紀錄會自動收進年月包裹，畫面不會越來越長。");
  };

  S.v2ActMenu = async () => {
    s = slide("CONTENT");
    s.addText("活動選單：只放進行中的活動", { placeholder: "title" });
    shot(s, D("dropdown"), 0.6, 1.45, 7.9, 1.6, "v2-dropdown");
    await checks(["預先規劃（還沒開始）的不會出現在選單", "到了開始日自動放上去，並通知每位成員",
      "選了活動，總覽、帳本、狀況、建議都換成這個活動的", "按「回到個人」一鍵回到自己的帳"], 8.95, 1.6, 1.15);
    s.addNotes("右上角的活動選單只放進行中的活動，預先規劃的要到開始日才會出現，同時通知每位成員。選了某個活動，總覽、帳本、財務狀況、建議都會換成這個活動的；按回到個人就回來。");
  };

  S.v2ActSettings = async () => {
    s = slide("CONTENT");
    s.addText("活動的設定與邀請朋友", { placeholder: "title" });
    await demoDouble("settings", "invite_friend",
      "名稱、說明、開始日、結束日、顏色、目標金額，建立後都能改——只有建立者能改。",
      "用完整 email 找到朋友再送出；或產生只能用一次、7 天有效的邀請碼。");
    s.addNotes("點開活動可以改所有設定，但只有建立者能改，避免大家各改各的。邀請朋友可以用完整的 email 找人，也可以產生只能用一次的邀請碼。");
  };

  S.v2ActHome = async () => {
    s = slide("CONTENT");
    s.addText("活動總覽：一張卡看懂這個活動", { placeholder: "title" });
    markShot("activity", 0.6, 1.45, 7.9, 1.6, "act");
    legend([
      ["說明", "建立者寫的一句話：這個活動在做什麼"],
      ["期間、成員、紀錄", "幾號開始、還有幾天結束；誰在裡面；記了幾筆"],
      ["目標金額", "到了幾成；到了通知全部成員"],
      ["活動的支出", "只算這個活動裡的帳，不混進個人"],
      ["回到個人", "一鍵離開活動，回到自己的總覽"],
      ["活動今天的紀錄", "下方面板也換成這個活動的"],
    ], 8.95, 1.5, 3.8, 0.88);
    s.addNotes("切到活動之後，總覽的主卡變成這個活動是什麼：說明、期間、成員、筆數和目標金額的進度。上面的收支只算活動裡的帳，不會混進個人。");
  };

  S.v2ActFriend = async () => {
    s = slide("CONTENT");
    s.addText("朋友這邊：收到邀請、加入、看得到不能改", { placeholder: "title" });
    await demoDouble("kid_activity_invite", "kid_readonly",
      "活動管理最上面就是邀請，按「加入」。",
      "看得到說明、期間、建立者訂的目標金額；設定只有建立者能改。想離開可以退出，自己記的可以合併回個人帳本。");
    s.addNotes("換到被邀請的人這邊，活動管理最上面就是邀請，按加入就進來了。成員看得到所有資訊，但設定只有建立者能改。想離開可以退出，退出時可以把自己記的那幾筆合併回個人帳本。");
  };

  S.v2Guardian = async () => {
    s = slide("CONTENT");
    s.addText("照看：家長看得到孩子的帳", { placeholder: "title" });
    shot(s, D("guardian"), 0.6, 1.45, 7.9, 1.6, "v2-guardian");
    await checks(["孩子加入後，家長按「開始照看」", "孩子看得到是誰在照看", "家長看得到孩子的帳，也能給零用金",
      "孩子看不到家長的帳，也看不到家庭帳務", "孩子可以自己退出家庭"], 8.95, 1.55, 0.98, 14);
    s.addNotes("孩子加入家庭之後，家長按開始照看，才看得到孩子的帳、才能給零用金；孩子也看得到是誰在照看。反過來，孩子看不到家長的帳，也看不到家庭的帳務。孩子可以自己退出家庭。");
  };

  S.v2Allowance = async () => {
    s = slide("CONTENT");
    s.addText("零用金：到了發放日自動記帳", { placeholder: "title" });
    tripleShots(["allowance_form", "allowance", "kid_bell"], [
      "設定每月零用金和發放日（1～28 號，沒選就是每月 1 號），改完離開欄位就存好。",
      "到了發放日自動記一對帳：家長一筆支出、孩子一筆收入。改金額只調原本那一對。",
      "孩子的鈴鐺馬上收到；零用金也算進孩子這個月可以花的錢裡。",
    ]);
    s.addNotes("家長在孩子的頁面設定每月零用金和發放日。到了發放日，系統自動記一對帳：家長那邊一筆支出、孩子那邊一筆收入；之後改金額只會調原本那一對，不會多記。孩子的鈴鐺會馬上收到通知。");
  };

  S.v2Bell = async () => {
    s = slide("CONTENT");
    s.addText("所有通知都即時進鈴鐺", { placeholder: "title" });
    const kinds = [
      ["FiHome", "家庭邀請", "有人用帳號邀你加入家庭"],
      ["FiMap", "活動邀請", "朋友邀你加入一個活動"],
      ["FiDollarSign", "零用金", "發放、調整、取消都會通知孩子"],
      ["FiTrendingUp", "固定收入入帳", "月薪到了入帳日自動記一筆"],
      ["FiTarget", "目標金額到了", "活動到了目標，全部成員都收到"],
      ["FiCalendar", "活動開始", "預先規劃的活動到了開始日"],
      ["FiEdit3", "孩子記帳", "照看的孩子記了一筆"],
      ["FiAlertCircle", "階段性提醒", "這個月花到你設的比例"],
    ];
    for (let i = 0; i < kinds.length; i++) {
      const x = 0.6 + (i % 4) * 3.08, y = 1.55 + Math.floor(i / 4) * 2.45;
      card(s, x, y, 2.88, 2.2, "bell-" + i);
      await iconCircle(s, kinds[i][0], x + 0.3, y + 0.3, 0.6, C.accent1, HEX.lt1, "bell-ic-" + i);
      text(s, kinds[i][1], { x: x + 0.3, y: y + 1.0, w: 2.4, h: 0.45, fontSize: 16, bold: true, color: C.text2 });
      text(s, kinds[i][2], { x: x + 0.3, y: y + 1.45, w: 2.4, h: 0.65, fontSize: 12.5, color: C.accent5 });
    }
    text(s, "打開系統時每 5 秒更新一次；做完會產生通知的動作，馬上再問一次。每一則都能刪，已讀的可以一次清掉。",
      { x: 0.6, y: 6.5, w: 12.1, h: 0.4, fontSize: 13, color: C.text1 });
    s.addNotes("所有通知都即時進鈴鐺：家庭和活動的邀請、零用金、固定收入入帳、目標金額到了、活動開始、孩子記帳，還有花到自己設的比例時的提醒。每一則都可以刪。");
  };

  S.v2Advice = async () => {
    s = slide("CONTENT");
    s.addText("AI 財務建議：每個數字都找得到出處", { placeholder: "title" });
    markShot("advice", 0.6, 1.45, 7.9, 1.6, "adv");
    legend([
      ["等級", "良好、參考……一眼看這一則的狀況"],
      ["標題", "一句話說重點"],
      ["說明", "AI 寫成好懂的句子"],
      ["依據", "每個數字都附算式，資料庫先算好的"],
      ["建議", "接下來可以怎麼做"],
      ["產生建議", "按一下，依這個月的帳重新寫"],
    ], 8.95, 1.5, 3.8, 0.8);
    text(s, "檢查不過的那則不顯示；不推薦投資、保險。", { x: 8.95, y: 6.35, w: 3.8, h: 0.4, fontSize: 11.5, color: C.accent5 });
    s.addNotes("財務建議按一下就產生。每一則有等級、標題、AI 寫的說明，下面的依據列出每個數字和算式——這些數字由資料庫先算好，AI 只負責寫成好懂的句子；最後是具體的建議。檢查不通過的那則不會顯示，也不會推薦投資或保險。");
  };

  S.v2Summary = async () => {
    s = slide("CONTENT");
    s.addText("一頁看完：做了哪些事", { placeholder: "title" });
    const cols = [
      ["FiUserPlus", "開始使用", ["註冊與驗證信", "收入與存錢設定", "理財習慣、主題", "新手導覽"]],
      ["FiEdit3", "記帳", ["一句話記好幾筆（AI）", "今天的紀錄", "個人帳本與年月包裹", "固定收入自動入帳"]],
      ["FiMap", "活動", ["說明、期間、目標", "預先規劃", "邀請朋友", "退出可合併"]],
      ["FiUsers", "家庭", ["邀請家人", "照看孩子", "零用金自動記帳", "鈴鐺即時通知"]],
      ["FiPieChart", "回顧", ["收支對照與趨勢", "錢花在哪", "預算與提醒", "AI 財務建議"]],
    ];
    for (let i = 0; i < cols.length; i++) {
      const [ic, head, items] = cols[i];
      const x = 0.6 + i * 2.46;
      card(s, x, 1.55, 2.3, 4.9, "sum-" + i);
      await iconCircle(s, ic, x + 0.25, 1.8, 0.6, C.accent1, HEX.lt1, "sum-ic-" + i);
      text(s, head, { x: x + 0.25, y: 2.55, w: 1.9, h: 0.45, fontSize: 18, bold: true, color: C.text2 });
      s.addText(items.map((t, j) => ({ text: t, options: { bullet: true, breakLine: j < items.length - 1 } })),
        { x: x + 0.25, y: 3.1, w: 1.95, h: 3.2, fontSize: 13, color: C.text1, paraSpaceAfter: 8, valign: "top", isTextBox: true, margin: 0 });
    }
    text(s, "手機、平板、電腦都能用；每一頁都照螢幕寬度重新排。", { x: 0.6, y: 6.6, w: 12.1, h: 0.35, fontSize: 13, color: C.accent5 });
    s.addNotes("最後用一頁整理今天看到的：開始使用、記帳、活動、家庭、回顧五大塊，手機、平板、電腦都能用。");
  };

  // 重點版：開場 3、四個領域各 3、結語 3；產品展示：照影片用一輪；v2：同一輪講得更細；完整版：原本的每一頁
  const ORDER = DEMO2
    ? ["§開場", "v2Cover", "v2Why", "v2Views", "dFlow",
       "§開始使用", "v2Setup", "v2Theme",
       "§記帳", "v2Home", "v2Parse", "dParseAI", "dToday", "v2Ledger",
       "§活動", "dActivity1", "v2ActMenu", "v2ActSettings", "v2ActHome", "v2ActFriend",
       "§家庭", "dFamily", "v2Guardian", "v2Allowance", "v2Bell",
       "§回顧", "dStats", "v2Advice",
       "§手機", "dMobile",
       "§結語", "v2Summary", "future", "dThanks"]
    : DEMO
    ? ["§開場", "dCover", "dFlow", "§開始使用", "dStart", "dHome", "§記帳", "dParse", "dParseAI", "dToday",
       "§活動", "dActivity1", "dActivity2", "§家庭", "dFamily", "dAllowance", "§回顧", "dStats", "dAdvice", "§手機", "dMobile",
       "§結語", "dThanks"]
    : FULL
    ? ["§開場", "cover", "problem", "stats", "§系統", "arch", "tech", "home", "entry", "family", "activity", "account", "admin", "db",
       "§AI 功能", "aiDivider", "paraFlow", "paraScreen", "modelVsCode", "advice",
       "§評測與測試", "evalHow", "evalResult", "errors", "finetune", "tests", "live", "round3", "round4",
       "§結語", "limits", "redo", "future", "thanks"]
    : ["§開場", "cover", "problem", "arch",
       "§認證", "account", "security", "admin",
       "§記帳", "activity", "paraFlow", "evalResult",
       "§數字", "home", "budget", "advice",
       "§家庭", "family", "allowance", "notify",
       "§結語", "tests", "future", "thanks"];
  for (const k of ORDER) {
    if (k.startsWith("§")) { SEC = k.slice(1); pres.addSection({ title: SEC }); continue; }
    await S[k]();
  }

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("寫好了：" + OUT);
}

build().catch((e) => { console.error(e); process.exit(1); });
