// 基準線：前端的規則解析（模型叫不動時，使用者實際看到的就是它）跑一遍留出集。
// 由 tools/eval_nlp.py --rules 呼叫：node rules_baseline.js <repo 根目錄> <留出集 .jsonl>
// 每一題印一行 JSON：{"id", "items": [{"span", "date", "amount", "kind", "cat"（分類名稱）}]}
//
// ⚠️ 用的是 api.js 的 mock 轉接器（不設 api-base）：跟後端回 503 時的備援用同一支 parseLine，
//    差別只在 mock 版切分時多認「然後／接著／還有」。
const fs = require('fs');
const path = require('path');

const root = path.resolve(process.argv[2]);
const cases = fs.readFileSync(process.argv[3], 'utf8').split(/\r?\n/).filter(Boolean).map(JSON.parse);

const store = new Map();
global.localStorage = {
  getItem: k => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: k => store.delete(k),
};
global.setTimeout = f => setImmediate(f);          // mock 會故意 sleep，這裡不用等
global.window = global;
global.document = { querySelector: () => null, addEventListener() {}, getElementById: () => null };

window.__FAMBUDGET_TODAY__ = (cases[0] && cases[0].today) || '';
require(path.join(root, 'frontend/js/data.js'));
require(path.join(root, 'frontend/js/api.js'));
const names = {};
window.DATA.categories.forEach(c => { names[c.id] = c.name; });

(async () => {
  // mock 跟真後端一樣要先登入；這是 node 裡的假 localStorage，跑完就丟
  await window.API.register({ name: '基準線', email: 'baseline@eval.test', password: 'baseline-only-not-real' });
  for (const c of cases) {
    window.__FAMBUDGET_TODAY__ = c.today;
    const out = await window.API.nlpParseBatch(c.text);
    const items = out.items.map(it => ({
      span: it.span, date: it.date, amount: it.amount || null, kind: it.kind, cat: names[it.cat] || null,
    }));
    process.stdout.write(JSON.stringify({ id: c.id, items }) + '\n');
  }
})().catch(e => { console.error(e); process.exit(1); });
