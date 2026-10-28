// 專案報告產生器：node report/build_deck.js → report/家庭記帳_專案報告.pptx
//
// 產品介紹：照完整流程影片用一輪，畫面標 ①②③ 逐一說明，最後是接下來上線的兩件事（26 頁）。
// 截圖是 qa/record_demo.py --trial --snaps 同一輪拍的（report/assets/demo/），個人帳本那張是 screenshot.py 拍的（assets/entry.png）。
// AI 記帳那一頁與未來展望的數字從 report/data/facts.json 讀（python report/collect.py 產生），不手打。
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
const outArg = process.argv.slice(2).find((a) => !a.startsWith("--"));
const OUT = outArg ? path.resolve(outArg) : path.join(HERE, "家庭記帳_專案報告.pptx");

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
pres.title = "家庭記帳 FamBudget 專案報告";
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
/** 封面與結尾的網站 QR code：白底卡片，深色底上也掃得到。 */
function qr(slide, x, y, id) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 2.3, h: 2.75, rectRadius: 0.12, fill: { color: "FFFFFF" }, line: { color: "FFFFFF" }, objectName: id + "-card" });
  slide.addImage({ path: asset("qr_site.png"), x: x + 0.2, y: y + 0.15, w: 1.9, h: 1.9, objectName: id });
  slide.addText([{ text: "掃描開啟網站", options: { bold: true, breakLine: true } }, { text: "fambudget-web.onrender.com", options: { fontSize: 9 } }],
    { x: x + 0.1, y: y + 2.08, w: 2.1, h: 0.6, fontSize: 12, color: "16233F", align: "center", valign: "middle", margin: 0, objectName: id + "-cap" });
}
/** 右上角的小標籤：「步驟 n／6・記帳」，看得出現在講到哪裡 */
function pillTag(slide, label) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 10.85, y: 0.52, w: 1.85, h: 0.46, rectRadius: 0.23,
    fill: { color: "EEF3FA" }, line: { color: "D6E0EE", width: 0.75 }, objectName: "pill-tag" });
  slide.addText(label, { x: 10.85, y: 0.52, w: 1.85, h: 0.46, fontSize: 12, bold: true,
    color: "1F5FBF", align: "center", valign: "middle", margin: 0, objectName: "pill-tag-text" });
}
const pct = (v) => (v === null || v === undefined ? "—" : (v * 100).toFixed(1) + "%");
const fmt = (n) => Number(n).toLocaleString("en-US");

async function build() {
  let s;
  let SEC = "開場";
  const STEP_NO = { "開始使用": 1, "記帳": 2, "活動": 3, "家庭": 4, "回顧": 5, "手機": 6 };
  const slide = (master) => {
    const sl = pres.addSlide({ masterName: master, sectionTitle: SEC });
    if (master === "CONTENT" && STEP_NO[SEC]) pillTag(sl, "步驟 " + STEP_NO[SEC] + "／6・" + SEC);
    return sl;
  };
  const S = {};

  // ============================================================ 頁面
  // 照完整流程影片走一輪。截圖是 record_demo.py --trial --snaps 同一輪拍的（report/assets/demo/）
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

  S.dFamily = async () => {
    s = slide("CONTENT");
    s.addText("家庭：邀請家人一起記", { placeholder: "title" });
    await demoDouble("family", "kid_invite",
      "用完整 email 找到人，選身分（子女／家長）再送出。",
      "對方的總覽最上面就是邀請，按「加入」就進這個家庭。");
    s.addNotes("接著建立家庭、邀請家人。用完整的 email 找到人，選好身分再送出。換成孩子的帳號，總覽最上面就是邀請，按加入就進來了。");
  };

  S.dStats = async () => {
    s = slide("CONTENT");
    s.addText("回顧：錢花在哪", { placeholder: "title" });
    await demoSingle("stats", ["收支對照：按月、按年", "近六個月的趨勢", "錢花在哪：各分類比例", "數字跟總覽、明細同一個來源"]);
    s.addNotes("回顧的第一步是統計：收支對照、近六個月的趨勢，還有錢花在哪。這些數字跟總覽、明細是同一個來源。");
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

  // 畫面上標 ①②③（位置是 record_demo.py --snaps 拍的時候從網頁讀的，見 demo/marks.json），旁邊逐一說明
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

  // 未來展望：使用者定的兩件事（10/28）——AI 換成 Hugging Face 上的開源模型（不用蒸餾模型）、記帳加上語音與圖片
  S.v3Future = async () => {
    s = slide("CONTENT");
    s.addText("未來展望：接下來上線的兩件事", { placeholder: "title" });
    const plans = [
      ["FiCpu", C.accent1, "AI：換成 Hugging Face 的開源模型", ["Anthropic API", "Hugging Face 開源模型"], [
        "從 Hugging Face 挑合適的開源模型，用我們的記帳資料再訓練：" + fmt(facts.train.cases) + " 題訓練資料，加上使用者改過的解析",
        "上線前用同一份 " + facts.heldout.cases + " 題評測，準確率跟現在一樣才換",
        "部署在 Hugging Face Space（或自己的伺服器），不用再付商業 API 的費用",
        "延伸：財務建議也換成同一個模型",
      ]],
      ["FiMic", C.accent2, "記帳更省事：語音與圖片", ["打一段字", "說一段話／拍一張照"], [
        "語音：按住說話，轉成文字後走同一套 AI 拆帳",
        "圖片：拍收據或發票，讀出店家、品項、金額，拆成好幾筆",
        "跟現在一樣：拆好之後由你看過、按確認才寫入",
        "延伸：電子發票載具自動匯入",
      ]],
    ];
    for (let i = 0; i < plans.length; i++) {
      const [ic, col, head, [from, to], items] = plans[i];
      const x = 0.6 + i * 6.15;
      card(s, x, 1.5, 5.95, 5.15, "plan-" + i);
      await iconCircle(s, ic, x + 0.35, 1.75, 0.7, col, HEX.lt1, "plan-ic-" + i);
      text(s, head, { x: x + 1.25, y: 1.75, w: 4.5, h: 0.7, fontSize: 20, bold: true, color: C.text2, valign: "middle" });
      // 現在 → 之後
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.35, y: 2.75, w: 2.15, h: 0.55, rectRadius: 0.27,
        fill: { color: "FFFFFF" }, line: { color: "D6E0EE", width: 1 }, objectName: "plan-from-" + i });
      text(s, from, { x: x + 0.35, y: 2.75, w: 2.15, h: 0.55, fontSize: 13, color: C.accent5, align: "center", valign: "middle" });
      arrow(s, x + 2.6, 3.02, 0.55, "plan-arrow-" + i, col);
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 3.25, y: 2.75, w: 2.35, h: 0.55, rectRadius: 0.27,
        fill: { color: col }, line: { color: col }, objectName: "plan-to-" + i });
      text(s, to, { x: x + 3.25, y: 2.75, w: 2.35, h: 0.55, fontSize: 13, bold: true, color: "FFFFFF", align: "center", valign: "middle" });
      s.addText(items.map((t, j) => ({ text: t, options: { bullet: true, breakLine: j < items.length - 1 } })),
        { x: x + 0.35, y: 3.55, w: 5.3, h: 2.95, fontSize: 14.5, color: C.text1, paraSpaceAfter: 10, valign: "top", isTextBox: true, margin: 0 });
    }
    s.addNotes("接下來要上線的有兩件事。第一，AI 從現在的 Anthropic API，換成 Hugging Face 上的開源模型：用我們的記帳資料再訓練，上線前用同一份題目評測，準確率跟現在一樣才換；部署在 Hugging Face Space 或自己的伺服器，就不用再付商業 API 的費用。第二，記帳更省事：除了打字，還能直接說一段話，或拍一張收據、發票，一樣由 AI 拆成好幾筆，最後由你確認才寫入。");
  };

  const ORDER = ["§開場", "v2Cover", "v2Why", "v2Views", "dFlow",
    "§開始使用", "v2Setup", "v2Theme",
    "§記帳", "v2Home", "v2Parse", "dParseAI", "dToday", "v2Ledger",
    "§活動", "dActivity1", "v2ActMenu", "v2ActSettings", "v2ActHome", "v2ActFriend",
    "§家庭", "dFamily", "v2Guardian", "v2Allowance", "v2Bell",
    "§回顧", "dStats", "v2Advice",
    "§手機", "dMobile",
    "§結語", "v2Summary", "v3Future", "dThanks"];
  for (const k of ORDER) {
    if (k.startsWith("§")) { SEC = k.slice(1); pres.addSection({ title: SEC }); continue; }
    await S[k]();
  }

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("寫好了：" + OUT);
}

build().catch((e) => { console.error(e); process.exit(1); });
