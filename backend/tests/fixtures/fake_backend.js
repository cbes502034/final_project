// 假後端：讓 api.js 以 http 模式跑一遍，看前端代勞、備援、錯誤訊息對不對。
// 由 tests/test_frontend_adapter.py 呼叫：node fake_backend.js <repo 根目錄> <後端 501 的訊息>
//
// 這個假後端只回「查資料庫才拿得到」的欄位（名字、百分比、淨額都不給），
// 其他交給前端的 fillIn 補；另外故意安排 501、404、500、壞形狀、斷線、業務錯誤各一支。
const path = require('path');
const root = process.argv[2];
const notReady = process.argv[3];
let notifyMode = 'network';         // network → notReady → empty，見 /api/notifications
const store = new Map();
global.localStorage = {
  getItem: k => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: k => store.delete(k),
};
global.setTimeout = f => setImmediate(f);
global.window = { __FAMBUDGET_TODAY__: '2026-09-14' };

// 假 DOM：只做到 notify.js 的鈴鐺跑得起來（api.js 只要 querySelector 找得到 api-base）。
const listeners = {};
const mkEl = id => ({ id, hidden: false, innerHTML: '', textContent: '', classList: { toggle() {} } });
const bellEls = { bell: mkEl('bell'), bellDot: mkEl('bellDot'), bellPanel: mkEl('bellPanel') };
const bellWrap = { hidden: false };
bellEls.bell.parentNode = bellWrap;
const clickBell = () => (listeners.click || []).forEach(
  f => f({ target: { closest: sel => (sel === '#bell' ? bellEls.bell : null) } }));
global.document = {
  querySelector: sel => (sel.indexOf('api-base') >= 0 ? { content: 'http://api.test' } : null),
  getElementById: id => bellEls[id] || null,
  addEventListener: (type, fn) => { (listeners[type] = listeners[type] || []).push(fn); },
  removeEventListener: () => {},
  visibilityState: 'visible',
};

const res = (status, body) => Promise.resolve({
  ok: status < 400, status,
  json: () => Promise.resolve(body),
  text: () => Promise.resolve(JSON.stringify(body)),
});
const ROUTES = [
  ['POST', '/api/auth/login', () => res(200, { accessToken: 'a', refreshToken: 'r', user: { id: '1', name: '王大同' } })],
  ['GET', '/api/auth/me', () => res(200, { user: { id: '1', name: '王大同' } })],
  // ⚠️ id 故意用真後端的樣子（1、2），不是 data.js 的 C01——
  //    前端規則解析（備援）回來的 cat 要對得回這裡的 id，不然記帳頁那一格會選錯分類
  ['GET', '/api/categories', () => res(200, { categories: [
    { id: '1', name: '餐飲', kind: 'expense', color: 'cat-food' },
    { id: '2', name: '交通', kind: 'expense', color: 'cat-transit' }] })],
  ['POST', '/api/categories', () => res(501, { detail: notReady })],
  ['GET', '/api/family', () => res(200, { me: '1', family: { id: '9', name: '王家' },
    members: [{ id: '1', name: '王大同' }, { id: '2', name: '王小明' }], guardianships: [] })],
  ['GET', '/api/summary', () => res(200, { period: '2026-09', income: 50000, expense: 42000,
    byCat: [{ cat: '1', amount: 42000 }], monthly: [], yearly: [], savings: { goal: 10000 } })],
  ['GET', '/api/transactions', () => res(200, { transactions: [{ id: '7', user: '2', cat: '1', amount: 120, kind: 'expense', date: '2026-09-14' }], total: 1 })],
  ['GET', '/api/budgets', () => res(200, { budgets: [{ user: '1', cat: '1', limit: 40000, used: 42000, period: 'month' }] })],
  ['POST', '/api/nlp/parse-batch', () => res(501, { detail: notReady })],
  ['POST', '/api/nlp/parse', () => res(503, { detail: '模型服務還沒接上，先用前端的規則解析' })],
  ['POST', '/api/advices/generate', () => res(501, { detail: notReady })],
  ['GET', '/api/auth/sessions', () => res(404, { detail: 'Not Found' })],
  ['GET', '/api/alerts', () => res(200, { wrong: [] })],
  ['GET', '/api/groups', () => res(500, { detail: 'relation "groups" does not exist' })],
  // 這一支要演三種狀況：斷線、那一支還沒做、真的沒有通知。見下面的 notifyMode
  ['GET', '/api/notifications', () => (
    notifyMode === 'notReady' ? res(501, { detail: notReady })
      : notifyMode === 'empty' ? res(200, { notifications: [], unread: 0, maxId: null })
        : Promise.reject(new TypeError('Failed to fetch')))],
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
require(path.join(root, 'frontend/js/notify.js'));
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
  out.nlpFallback = { fallback: para.fallback, amounts: para.items.map(i => i.amount),
    cats: para.items.map(i => i.cat) };
  const one = await settle(A.nlpParse('午餐120'));
  out.modelDown = { fallback: one.fallback, amount: one.out && one.out.amount,
    cat: one.out && one.out.cat, error: one.error };
  const adv = await settle(A.generateAdvices({ scope: 'me' }));
  out.adviceFallback = { fallback: adv.fallback, count: (adv.advices || []).length, error: adv.error };
  const ss = await A.sessions();
  out.sessionsFallback = { fallback: ss.fallback, count: ss.sessions.length };
  out.notReady = await settle(A.createCategory({ name: '寵物', kind: 'expense' }));
  out.shape = await settle(A.alerts());
  out.server = await settle(A.groups({}));
  out.network = await settle(A.notifications({}));
  out.business = await settle(A.joinFamily({ code: 'ABCD1234' }));

  // 鈴鐺：「那一支還沒做」跟「真的沒有通知」在畫面上要分得出來。
  // 分不出來的話，通知那一支還沒接的時候，鈴鐺會說「目前沒有通知」——看的人會信。
  notifyMode = 'notReady';
  window.Notify.reset();
  await window.Notify.refresh();
  clickBell();
  out.bellNotReady = { wrapHidden: bellWrap.hidden, text: bellEls.bellPanel.innerHTML };
  clickBell();

  notifyMode = 'empty';
  window.Notify.reset();
  await window.Notify.refresh();
  clickBell();
  out.bellEmpty = { wrapHidden: bellWrap.hidden, text: bellEls.bellPanel.innerHTML };
  window.Notify.stop();

  process.stdout.write(JSON.stringify(out));
})().catch(e => { console.error('CRASH', e); process.exit(1); });
