const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');

function createHarness(repo) {
  const listeners = {}, media = {matches: false, addEventListener: (_, fn) => { media.change = fn; }};
  const nodes = {};
  const document = {activeElement: null, getElementById: id => nodes[id] || null,
    addEventListener: (type, handler) => { (listeners[type] ||= []).push(handler); }};
  for (const id of ['phead','headerScope','search','searchDrawer','searchBtn','gsw','gswPanel','gswBtn','ptitle','psub','pkick','pav','pact']) {
    const classes = new Set();
    nodes[id] = {hidden: true, dataset: {}, attributes: {}, writes: 0,
      set innerHTML(value) { this.html = value; this.writes++; }, get innerHTML() { return this.html || ''; },
      setAttribute(name, value) { this.attributes[name] = value; }, focus() { document.activeElement = this; },
      classList: {remove: name => classes.delete(name), toggle: (name, on) => on ? classes.add(name) : classes.delete(name)}};
  }
  const context = {document, matchMedia: () => media, addEventListener() {}};
  context.window = context;
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(repo,'frontend/js/page-header.js'),'utf8'),context);
  const escape = text => String(text).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
  const header = context.FBPageHeader.create({escape, tint: String, avatar: u => '<span>' + escape(u.name) + '</span>'});
  const dispatch = (type, selector) => listeners[type].forEach(handler => handler({
    key: type === 'keydown' ? selector : '', preventDefault() {}, target: {closest: query => query === selector}}));
  return {context, document, media, nodes, header, dispatch};
}

function check(repo) {
  const {header, nodes, media, document, dispatch} = createHarness(repo);
  const state = {enabled: true, canFamily: true, scope: 'me', mode: '個人', title: '個人帳本', subtitle: '', user: {name: '測試'}};
  header.render(state);
  assert.equal(nodes.searchDrawer.hidden, false);
  assert.equal(nodes.search.attributes['aria-label'], '搜尋個人帳本明細');
  assert.equal(nodes.psub.hidden, false); // Subtitle space remains present on every page.
  assert.ok(nodes.pav.innerHTML.includes('測試'));
  const writes = nodes.headerScope.writes;
  header.render({...state, title: '個人資料', subtitle: '設定'});
  assert.equal(nodes.headerScope.writes, writes); // Page updates retain the switch and keyboard focus.
  dispatch('click', 'outside');
  assert.equal(nodes.searchDrawer.hidden, false); // Desktop search never collapses after an outside click.
  media.matches = true; media.change();
  assert.equal(nodes.searchDrawer.hidden, true);
  dispatch('click', '#searchBtn');
  assert.equal(nodes.searchDrawer.hidden, false);
  assert.equal(nodes.searchBtn.attributes['aria-expanded'], 'true');
  assert.equal(document.activeElement, nodes.search);
  dispatch('keydown', 'Escape');
  assert.equal(nodes.searchDrawer.hidden, true);
  assert.equal(document.activeElement, nodes.searchBtn);
  nodes.gswPanel.hidden = false;
  dispatch('keydown', 'Escape');
  assert.equal(nodes.gswPanel.hidden, true);
  assert.equal(document.activeElement, nodes.gswBtn);
  header.render({...state, scope:'family', mode:'家庭', title:'家庭帳本'});
  assert.equal(nodes.gsw.hidden, true);
  assert.equal(nodes.search.attributes['aria-label'], '搜尋家庭帳本明細');
  header.render({...state, mode:'活動', title:'活動財務建議'});
  assert.equal(nodes.gsw.hidden, false);
  assert.equal(nodes.search.attributes['aria-label'], '搜尋活動帳本明細');
  assert.ok(nodes.headerScope.innerHTML.includes('data-scope="me" aria-pressed="true"'));
  header.setActivities([], null);
  assert.ok(nodes.gsw.innerHTML.includes('目前尚未建立活動'));
  assert.ok(nodes.gsw.innerHTML.includes('建立活動 →'));
  assert.ok(nodes.gsw.innerHTML.includes('id="gswBtn"')); // Empty and populated states use the same control.
  header.setActivities([{id:'1',name:'<旅行>',count:3,color:'book-indigo',goal:1000}], '1');
  assert.ok(nodes.gsw.innerHTML.includes('&lt;旅行>'));
  assert.ok(nodes.gsw.innerHTML.includes('回到個人帳本 →'));
  assert.ok(nodes.gsw.innerHTML.includes('目標 1000'));
  header.render({...state, canFamily:false});
  assert.ok(nodes.headerScope.innerHTML.includes('個人模式'));
  assert.ok(!nodes.headerScope.innerHTML.includes('data-scope='));
  header.render({...state, enabled:false});
  assert.equal(nodes.phead.dataset.tools, 'false');
  assert.equal(nodes.searchDrawer.hidden, true);
  console.log('Shared page header behavior passed');
}

if (require.main === module) check(process.argv[2]);
module.exports = {createHarness};
