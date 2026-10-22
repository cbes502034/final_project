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
  const harness = require('./page_header.js').createHarness(repo);
  const box = harness.nodes.gsw;
  const books = [{ id: 'other', name: '旅遊', count: 2 },
    { id: 'personal', name: '自己的帳本', count: 1, personal: true },
    { id: 'closed', name: '已結算', settled: true }];
  const ui = Object.assign(harness.context, { HEADER: harness.header, API: { groups: async () => ({ groups: books }) },
    GROUP: 'all', isFamily: () => false, esc: String, tint: String, money: String, pushForDrawer() {},
    setGroup(id) { ui.GROUP = id; }, LG: { fam: { members: [] } }, activityInvitePanel: () => '' });
  ui.TXGROUPS = [];
  vm.runInContext(extract('paintGroups') + '\n' + extract('ledgerBody') + '\n' + extract('txLocked'), ui);
  assert.equal(ui.txLocked({ snapshot: true, group: 'shared' }), true);
  await ui.paintGroups(true);
  assert.equal(ui.GROUP, 'personal');
  assert.ok(!box.innerHTML.includes('data-group="personal"'));
  assert.ok(!box.innerHTML.includes('data-group="all"'));
  assert.ok(!box.innerHTML.includes('data-group="closed"'));
  ui.GROUP = 'closed';
  await ui.paintGroups(true);
  assert.equal(ui.GROUP, 'personal');
  books.splice(0, 1); books.splice(1, 1);
  await ui.paintGroups(true);
  assert.equal(box.hidden, false);
  assert.ok(box.innerHTML.includes('目前尚未建立活動'));
  const html = ui.ledgerBody({ id: 'shared', members: [], count: 2, canEdit: false });
  assert.ok(html.includes('data-gsettle="shared"')); // Non-owners can merge.
  assert.ok(html.includes('data-gview="shared"'));
  assert.ok(html.includes('>退出</button>'));
  const ownerHTML = ui.ledgerBody({ id: 'shared', members: [], count: 2, canEdit: true });
  assert.ok(!ownerHTML.includes('data-garch='));
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
  // Leaving alone must not create copies, including after a reload.
  const initial = storage['fambudget.state.v2'];
  const left = await c.API.settleGroup('G1', false);
  assert.equal(left.copied, 0);
  assert.equal(left.personalGroupId, null);
  let leaveSaved = JSON.parse(storage['fambudget.state.v2']);
  assert.equal((leaveSaved.extra || []).length, 0);
  assert.equal(leaveSaved.txPatch.T1.snapshot, true);
  assert.equal(leaveSaved.groupPatch.G1.owner, 'U2');
  leaveSaved.me = 'U2'; storage['fambudget.state.v2'] = JSON.stringify(leaveSaved);
  c = open();
  assert.equal((await c.API.transactions({ groupId: 'G1' })).transactions.length, 2);
  const leaveLast = await c.API.settleGroup('G1', false);
  assert.equal(leaveLast.closed, true);
  assert.equal(leaveLast.copied, 0);
  assert.ok(!(await c.API.groups()).groups.some(g => g.id === 'G1'));
  storage['fambudget.state.v2'] = initial;
  c = open();
  assert.equal((await c.API.summary({ scope: 'me' })).expense, 0);
  assert.equal((await c.API.summary({ scope: 'me', groupId: 'G1' })).expense, 30);
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
  const origin = await c.API.transactions({ groupId: merged.personalGroupId, q: '旅行', activityId: 'G1' });
  assert.equal(origin.total, 1);
  assert.equal(origin.transactions[0].activityName, '旅行');
  c.__FAMBUDGET_TODAY__ = '2027-01-31';
  assert.equal((await c.API.transactionArchive({ groupId: merged.personalGroupId })).nextPackAt, '2027-02-01T00:00:00+08:00');
  await c.API.logoutAll();
  assert.equal((await c.API.me()).user.id, 'U1');
  // Reload as the remaining member: original history, personal copy, and ownership persist.
  saved = JSON.parse(storage['fambudget.state.v2']); saved.me = 'U2';
  storage['fambudget.state.v2'] = JSON.stringify(saved);
  c = open();
  const rows = (await c.API.groups()).groups;
  assert.equal(rows.find(g => g.id === 'G1').count, 2);
  assert.equal(rows.find(g => g.id === 'G1').canEdit, true);
  const history = (await c.API.transactions({ groupId: 'G1' })).transactions;
  assert.equal((await c.API.summary({ scope: 'me', groupId: 'G1' })).expense, 30);
  assert.equal(history.length, 2);
  assert.equal(history.find(t => t.id === 'T1').amount, 10);
  assert.equal(history.find(t => t.id === 'T1').snapshot, true);
  const last = await c.API.settleGroup('G1');
  assert.equal(last.closed, true);
  assert.equal(last.copied, 1);
  assert.ok(!(await c.API.groups()).groups.some(g => g.id === 'G1'));
  const past = await c.API.transactions({ groupId: last.personalGroupId, activityId: 'G1', q: '旅行' });
  assert.equal(past.total, 1);
  assert.equal(past.transactions[0].activityName, '旅行');
}
function checkArchive() {
  class Clock extends Date { static now() { return Date.parse('2026-12-31T16:00:00Z'); } }
  let loaded = 0;
  const ui = { Date: Clock, ARCHIVE: { current: '2026-12', month: '2026-12' },
    location: { hash: '#/entry' }, F: { activityId: 'all' }, esc: String,
    skeleton: () => 'loading', emptyState: () => 'empty', loadTx: () => { loaded++; } };
  vm.createContext(ui);
  vm.runInContext(['taipeiMonth', 'monthRange', 'archiveMarkup', 'archiveRollover'].map(extract).join('\n'), ui);
  assert.equal(ui.taipeiMonth(Date.parse('2026-12-31T15:59:59Z')), '2026-12');
  assert.equal(ui.taipeiMonth(Date.parse('2026-12-31T16:00:00Z')), '2027-01');
  assert.equal(ui.monthRange('2024-02').join(','), '2024-02-01,2024-02-29');
  assert.equal(ui.monthRange('2025-02').join(','), '2025-02-01,2025-02-28');
  ui.archiveRollover();
  assert.equal(ui.ARCHIVE.month, '2027-01');
  assert.equal(loaded, 1);
  ui.archiveRollover();
  assert.equal(loaded, 1);
  const data = { currentMonth: '2027-01', activities: [], years: [
    { year: '2026', months: [{ month: '2026-12', count: 250, packed: true }] }] };
  const html = ui.archiveMarkup(data);
  assert.ok(html.includes('2026 年') && !html.includes('2027 年'));
  assert.ok(html.includes('250 筆 · 已打包'));
  assert.ok(!html.includes('id="txList"')); // Closed months do not mount detailed rows.
  ui.ARCHIVE.month = '2026-12';
  assert.ok(ui.archiveMarkup(data).includes('id="txList"'));
  assert.ok(ui.archiveMarkup({currentMonth:'2027-01', activities:[], years:[]}).includes('empty'));
}
async function checkInvitationUI() {
  const nodes = {'activityCodes-G1':{}, 'activitySent-G1':{}, activityIncoming:{}};
  const code = {id:'code1', groupId:'G1', kind:'code', label:'給小明', expiresAt:'2030-12-31', code:'SECRET-CODE'};
  const account = {id:'account1', groupId:'G1', kind:'account', label:'小美', inviteeEmail:'friend@x.tw'};
  const ui = { LG:{invites:[code,account], byId:{G1:{}}}, ACTIVITY_INV:{busy:false,sequence:0},
    location:{hash:'#/groups'}, document:{hidden:false,getElementById:id=>nodes[id]},
    API:{activityInvites:async()=>({invites:[account]})}, esc:String, shortDate:()=>'', ttlText:()=>'', ava:()=>'', toast:()=>{} };
  vm.createContext(ui);
  vm.runInContext(['activityCodeCards','activitySentCards','activityIncomingCards','activityInvitePanel','refreshActivityInvites'].map(extract).join('\n'),ui);
  const panel = ui.activityInvitePanel({id:'G1'});
  assert.ok(panel.includes('data-activity-find="G1"') && panel.includes('找人'));
  assert.ok(panel.includes('data-activity-code="G1"') && panel.includes('產生邀請碼'));
  assert.ok(panel.includes('給小明') && panel.includes('等待回覆'));
  assert.ok(!panel.includes('SECRET-CODE')); // Only the dialog may reveal a new code.
  assert.ok(!panel.includes('activityCode-G1'));
  await ui.refreshActivityInvites(true);
  assert.ok(!nodes['activityCodes-G1'].innerHTML.includes('code1'));
  assert.ok(nodes['activitySent-G1'].innerHTML.includes('account1'));
  ui.API.activityInvites=async()=>({invites:[]});
  await ui.refreshActivityInvites(true);
  assert.equal(nodes['activitySent-G1'].innerHTML,'');
  ui.document.hidden=true;
  ui.API.activityInvites=()=>{throw Error('Hidden pages must not poll');};
  await ui.refreshActivityInvites(true);
}
(async () => { checkArchive(); await checkInvitationUI(); await checkUI(); await checkMock(); console.log('personal merge, archive and invitation UI checks passed'); })()
  .catch(err => { console.error(err); process.exitCode = 1; });
