const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const repo = process.argv[2];
const app = fs.readFileSync(path.join(repo, 'frontend/js/app.js'), 'utf8');
function extract(name) {
  const start = app.indexOf('  function ' + name + '(');
  assert.ok(start >= 0, name);
  return app.slice(start, app.indexOf('\n  }', start) + '\n  }'.length);
}
async function checkUI() {
  const box = {};
  const books = [{ id: 'other', name: '旅遊', count: 2 },
    { id: 'personal', name: '自己的帳本', count: 1, personal: true },
    { id: 'closed', name: '已結算', settled: true }];
  const ui = { document: { getElementById: () => box }, API: { groups: async () => ({ groups: books }) },
    GROUP: 'all', esc: String, tint: String, money: String, pushForDrawer() {},
    setGroup(id) { ui.GROUP = id; }, LG: { fam: { members: [] } } };
  vm.createContext(ui);
  ui.TXGROUPS = [];
  vm.runInContext(extract('paintGroups') + '\n' + extract('ledgerBody') + '\n' + extract('txLocked'), ui);
  assert.equal(ui.txLocked({ snapshot: true, group: 'shared' }), true);
  await ui.paintGroups(true);
  assert.equal(ui.GROUP, 'personal');
  assert.ok(box.innerHTML.includes('data-group="personal"'));
  assert.ok(!box.innerHTML.includes('data-group="all"'));
  assert.ok(!box.innerHTML.includes('data-group="closed"'));
  ui.GROUP = 'closed';
  await ui.paintGroups(true);
  assert.equal(ui.GROUP, 'personal');
  books.splice(0, 1); books.splice(1, 1);
  await ui.paintGroups(true);
  assert.equal(box.hidden, false); // Even a lone personal book stays selected and labelled.
  const html = ui.ledgerBody({ id: 'shared', members: [], count: 2, canEdit: false });
  assert.ok(html.includes('data-gsettle="shared"')); // Non-owners can merge.
  assert.ok(html.includes('data-gview="shared"'));
  assert.ok(!ui.ledgerBody({ id: 'personal', personal: true, members: [], count: 0 }).includes('data-gsettle='));
}
async function checkMock() {
  const storage = { 'fambudget.state.v2': JSON.stringify({ me: 'U1', auth: { loggedIn: true } }) };
  function open() {
    const c = { location: { search: '', hostname: 'localhost' },
      document: { querySelector: () => null }, URLSearchParams,
      localStorage: { getItem: k => storage[k] || null, setItem: (k, v) => { storage[k] = v; } },
      setTimeout: fn => { fn(); }, clearTimeout() {}, console, Date, Math };
    c.window = c;
    vm.createContext(c);
    vm.runInContext(fs.readFileSync(path.join(repo, 'frontend/js/data.js'), 'utf8'), c);
    c.DATA.members = [{ id: 'U1', name: '甲' }, { id: 'U2', name: '乙' }];
    c.DATA.groups = [{ id: 'G1', name: '旅行', kind: 'standing', owner: 'U1' }];
    c.DATA.groupMembers = [{ group: 'G1', user: 'U1' }, { group: 'G1', user: 'U2' }];
    c.DATA.transactions = [{ id: 'T1', user: 'U1', group: 'G1', amount: 10 },
      { id: 'T2', user: 'U2', group: 'G1', amount: 20 }].map(t => Object.assign(t, {
        date: c.DATA.meta.period + '-01', kind: 'expense', cat: 'C01', source: 'manual' }));
    vm.runInContext(fs.readFileSync(path.join(repo, 'frontend/js/api.js'), 'utf8'), c);
    return c;
  }
  let c = open();
  const merged = await c.API.settleGroup('G1');
  assert.equal(merged.copied, 1);
  assert.equal(merged.closed, false);
  let saved = JSON.parse(storage['fambudget.state.v2']);
  assert.equal(saved.txPatch.T1.snapshot, true);
  assert.equal(saved.txPatch.T1.group, undefined);
  assert.equal(saved.extra.find(t => t.copiedFrom === 'T1').group, merged.personalGroupId);
  assert.equal(saved.txPatch.T2, undefined);
  assert.equal(saved.groupPatch.G1.owner, 'U2');
  assert.ok(!(await c.API.groups()).groups.some(g => g.id === 'G1'));
  assert.equal((await c.API.summary({ scope: 'me' })).expense, 10);
  assert.equal((await c.API.transactions({})).total, 1);
  // Reload as the remaining member: original history, personal copy, and ownership persist.
  saved = JSON.parse(storage['fambudget.state.v2']); saved.me = 'U2';
  storage['fambudget.state.v2'] = JSON.stringify(saved);
  c = open();
  const rows = (await c.API.groups()).groups;
  assert.equal(rows.find(g => g.id === 'G1').count, 2);
  assert.equal(rows.find(g => g.id === 'G1').canEdit, true);
  const history = (await c.API.transactions({ groupId: 'G1' })).transactions;
  assert.equal(history.length, 2);
  assert.equal(history.find(t => t.id === 'T1').amount, 10);
  assert.equal(history.find(t => t.id === 'T1').snapshot, true);
  const last = await c.API.settleGroup('G1');
  assert.equal(last.closed, true);
  assert.equal(last.copied, 1);
  assert.ok(!(await c.API.groups()).groups.some(g => g.id === 'G1'));
}
(async () => { await checkUI(); await checkMock(); console.log('personal merge UI and mock checks passed'); })()
  .catch(err => { console.error(err); process.exitCode = 1; });
