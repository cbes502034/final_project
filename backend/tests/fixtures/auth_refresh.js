// Exercise the real browser adapter with controlled, out-of-order HTTP replies.
const assert = require('node:assert/strict');
const path = require('node:path');
const root = process.argv[2];
const store = new Map();
global.window = {};
global.localStorage = {
  getItem: k => store.get(k) || null,
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: k => store.delete(k),
};
global.document = { querySelector: () => ({ content: 'http://api.test' }) };
const response = (status, body) => ({ status, ok: status < 400,
  json: async () => body, text: async () => JSON.stringify(body) });
let handler;
global.fetch = (url, opts) => handler(new URL(url).pathname, opts);
require(path.join(root, 'frontend/js/data.js'));
require(path.join(root, 'frontend/js/api.js'));
const api = window.API;
const success = () => response(200, { user: { id: '1', name: 'Test' } });
async function login() {
  handler = async () => response(200, { accessToken: 'old', refreshToken: 'refresh-old',
    expiresIn: 1800, user: { id: '1', name: 'Test' } });
  await api.login({ email: 'test@example.test', password: 'password123' });
}
async function main() {
  await login();
  let releaseLate, refreshes = 0, oldRequests = 0;
  handler = async (url, opts) => {
    if (url === '/api/auth/refresh') {
      refreshes++;
      return response(200, { accessToken: 'new', refreshToken: 'refresh-new' });
    }
    if (opts.headers.Authorization === 'Bearer old') {
      if (++oldRequests === 1) return response(401, { detail: 'expired' });
      return new Promise(resolve => { releaseLate = () => resolve(response(401, { detail: 'expired' })); });
    }
    return success();
  };
  const first = api.me(), late = api.me();
  await first;
  releaseLate();
  await late;
  assert.equal(refreshes, 1, 'late 401 must reuse the refreshed access token');

  await login();
  handler = async () => response(503, { detail: 'temporarily unavailable' });
  await assert.rejects(api.renew());
  assert.equal((await api.authState()).loggedIn, true, 'temporary failures retain the session');
  handler = async () => response(401, { detail: 'revoked' });
  await assert.rejects(api.renew());
  assert.equal((await api.authState()).loggedIn, false, 'revoked sessions are cleared');

  await login();
  let finishRefresh;
  handler = async url => url === '/api/auth/refresh'
    ? new Promise(resolve => { finishRefresh = resolve; }) : response(200, { ok: true });
  const pending = api.renew();
  const rejected = assert.rejects(pending);
  await api.logout();
  finishRefresh(response(200, { accessToken: 'new', refreshToken: 'refresh-new' }));
  await rejected;
  assert.equal((await api.authState()).loggedIn, false, 'late refresh cannot undo logout');
  console.log('auth refresh: 4 scenarios passed');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
