// 假後端：讓 api.js 以 http 模式跑一遍，看前端代勞、備援、錯誤訊息對不對。
// 由 tests/test_frontend_adapter.py 呼叫：node fake_backend.js <repo 根目錄> <後端 501 的訊息>
//
// 這個假後端只回「查資料庫才拿得到」的欄位（名字、百分比、淨額都不給），
// 其他交給前端的 fillIn 補；另外故意安排 501、404、500、壞形狀、斷線、業務錯誤各一支。
const path = require('path');
const root = process.argv[2];
const notReady = process.argv[3];
const store = new Map();
global.localStorage = {
  getItem: k => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: k => store.delete(k),
};
global.document = { querySelector: sel => (sel.indexOf('api-base') >= 0 ? { content: 'http://api.test' } : null) };
global.setTimeout = f => setImmediate(f);
global.window = { __FAMBUDGET_TODAY__: '2026-09-14' };

const res = (status, body) => Promise.resolve({
  ok: status < 400, status,
  json: () => Promise.resolve(body),
  text: () => Promise.resolve(JSON.stringify(body)),
});
const ROUTES = [
  ['POST', '/api/auth/login', () => res(200, { accessToken: 'a', refreshToken: 'r', user: { id: '1', name: '王大同' } })],
  ['GET', '/api/auth/me', () => res(200, { user: { id: '1', name: '王大同' } })],
  ['GET', '/api/categories', () => res(200, { categories: [{ id: 'C01', name: '餐飲', kind: 'expense', color: 'cat-food' }] })],
  ['POST', '/api/categories', () => res(501, { detail: notReady })],
  ['GET', '/api/family', () => res(200, { me: '1', family: { id: '9', name: '王家' },
    members: [{ id: '1', name: '王大同' }, { id: '2', name: '王小明' }], guardianships: [] })],
  ['GET', '/api/summary', () => res(200, { period: '2026-09', income: 50000, expense: 42000,
    byCat: [{ cat: 'C01', amount: 42000 }], monthly: [], yearly: [], savings: { goal: 10000 } })],
  ['GET', '/api/transactions', () => res(200, { transactions: [{ id: '7', user: '2', cat: 'C01', amount: 120, kind: 'expense', date: '2026-09-14' }], total: 1 })],
  ['GET', '/api/budgets', () => res(200, { budgets: [{ user: '1', cat: 'C01', limit: 40000, used: 42000, period: 'month' }] })],
  ['POST', '/api/nlp/parse-batch', () => res(501, { detail: notReady })],
  ['POST', '/api/advices/generate', () => res(501, { detail: notReady })],
  ['GET', '/api/auth/sessions', () => res(404, { detail: 'Not Found' })],
  ['GET', '/api/alerts', () => res(200, { wrong: [] })],
  ['GET', '/api/groups', () => res(500, { detail: 'relation "groups" does not exist' })],
  ['GET', '/api/notifications', () => Promise.reject(new TypeError('Failed to fetch'))],
  ['POST', '/api/family/join', () => res(409, { detail: '你已經在一個家庭裡了' })],
];
global.fetch = (url, opt) => {
  const u = url.replace('http://api.test', '').split('?')[0];
  const m = (opt && opt.method) || 'GET';
  const hit = ROUTES.find(r => r[0] === m && r[1] === u);
  return hit ? hit[2]() : res(404, { detail: 'Not Found' });
};

require(path.join(root, 'frontend/js/data.js'));
require(path.join(root, 'frontend/js/api.js'));
const A = window.API;
const settle = p => p.then(r => r, e => ({ error: e.message, kind: e.kind, fn: e.fn, route: e.route, owner: e.owner }));

(async () => {
  const out = { mode: A.mode };
  await A.login({ email: 'dad@x.tw', password: 'x' });
  const sm = await A.summary({ scope: 'me' });
  out.summary = { net: sm.net, rate: sm.rate, level: sm.savings.level, left: sm.savings.left, catName: sm.byCat[0].name };
  const tx = await A.transactions({});
  out.tx = { catName: tx.transactions[0].catName, userName: tx.transactions[0].userName };
  const bd = await A.budgets({});
  out.budget = { pct: bd.budgets[0].pct, over: bd.budgets[0].over, catName: bd.budgets[0].catName };
  const para = await A.nlpParseBatch('早餐55，加油一千二');
  out.nlpFallback = { fallback: para.fallback, amounts: para.items.map(i => i.amount) };
  const adv = await settle(A.generateAdvices({ scope: 'me' }));
  out.adviceFallback = { fallback: adv.fallback, count: (adv.advices || []).length, error: adv.error };
  const ss = await A.sessions();
  out.sessionsFallback = { fallback: ss.fallback, count: ss.sessions.length };
  out.notReady = await settle(A.createCategory({ name: '寵物', kind: 'expense' }));
  out.shape = await settle(A.alerts());
  out.server = await settle(A.groups({}));
  out.network = await settle(A.notifications({}));
  out.business = await settle(A.joinFamily({ code: 'ABCD1234' }));
  process.stdout.write(JSON.stringify(out));
})().catch(e => { console.error('CRASH', e); process.exit(1); });
