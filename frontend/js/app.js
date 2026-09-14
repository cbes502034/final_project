/* ============================================================
   app.js — 家庭記帳與財務控管系統 前端
   ------------------------------------------------------------
   資料一律走 API.*（見 js/api.js），不直接讀 window.DATA。
   ============================================================ */
(function (global) {
  'use strict';

  var API = global.API;
  var $view = document.getElementById('view');
  var DATA_CATS = {};   // 分類 id → 名稱，確認訊息要用

  /* 帳本清單與通知是**從按鈕往下浮出來的下拉面板**。

     ⚠️ 以前把它們搬進版面（頂列和內容之間），佔真實空間把內容往下推。
     改版之後頁首多了標題那一段，搬進去的面板就插在標題底下，整頁往下跳——
     使用者看到的就是「一點就跑版」。現在面板留在按鈕旁邊，用定位浮起來，
     內容一格都不動；項目多的話面板自己捲動，不會把頁面撐長。 */
  /* 寬螢幕的搜尋是頂欄上一直都在的輸入框，窄螢幕才是「按圖示展開」的抽屜。
     ⚠️ 以前兩邊都靠 CSS 硬蓋：寬螢幕用 display:flex !important 蓋掉 [hidden]，
     結果那個輸入框看得見、打得了字，hidden 屬性卻是 true——
     螢幕閱讀器會直接跳過它，等於對讀螢幕的人來說搜尋不存在。
     改成讓 hidden 一直說實話：寬螢幕拿掉它，窄螢幕才交給按鈕控制。 */
  var narrowBar = window.matchMedia('(max-width: 760px)');

  function syncSearchMode() {
    var sd = document.getElementById('searchDrawer');
    var sb = document.getElementById('searchBtn');
    if (!sd) return;
    if (narrowBar.matches) {
      sd.hidden = true;                       // 收起來，等使用者按圖示
      if (sb) sb.classList.remove('open');
      document.body.classList.remove('dw-on');
    } else {
      sd.hidden = false;                      // 一直都在
    }
  }
  syncSearchMode();
  /* ⚠️ 只靠 matchMedia 的 change 不夠可靠（換裝置模擬、某些瀏覽器不一定送），
     所以 resize 也補一道。但只在**模式真的變了**的時候才動——
     否則使用者一邊打字一邊轉螢幕，搜尋框會被關掉。 */
  var wasNarrow = narrowBar.matches;
  narrowBar.addEventListener('change', function () {
    wasNarrow = narrowBar.matches;
    syncSearchMode();
  });
  window.addEventListener('resize', function () {
    if (narrowBar.matches === wasNarrow) return;
    wasNarrow = narrowBar.matches;
    syncSearchMode();
  });

  /* ⚠️ 只有這兩個是抽屜。#searchDrawer 在文字模式是頂欄上的行內搜尋框，
     把它搬進版面的話，頂欄的搜尋就不見了。 */
  var DRAWERS = ['#gswPanel', '#bellPanel'];

  function pushForDrawer() {
    var open = DRAWERS.map(function (sel) { return document.querySelector(sel); })
      .filter(function (e) { return e && !e.hidden; })[0];
    document.body.classList.toggle('dw-on', !!open);
  }
  global.__pushForDrawer = pushForDrawer;

  /* ⚠️ 以前這裡用 body.bar-text／bar-icon 切換兩種頂列方案。
     頂列已經併進頁首，只剩一種做法；那個 class 留著的話，
     舊方案的規則（優先度比較高）會蓋掉新的工具列樣式。所以整段拿掉。 */

  /* ============================================================
     主題
     ------------------------------------------------------------
     換膚 = 在 <html> 上換 data-theme。顏色、圓角、字體都是變數，
     元件本身什麼都不用改（見 css/themes.css）。

     存兩個地方：
       · 帳號上（PATCH /api/auth/me 的 theme）——換裝置登入也一樣
       · 這台裝置（localStorage）——index.html 在 CSS 載入前先掛上，重新整理不會閃
     ============================================================ */
  var THEME_KEY = 'fambudget.theme';

  function themeOf(id) {
    return (global.DATA.themes || []).filter(function (t) { return t.id === id; })[0];
  }
  function currentTheme() {
    return document.documentElement.getAttribute('data-theme') || 'paper';
  }
  function applyTheme(id) {
    var t = themeOf(id) || themeOf('paper');
    if (!t) return;
    document.documentElement.setAttribute('data-theme', t.id);
    if (t.font) loadFont(t.font);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta && t.band) meta.setAttribute('content', t.band);
    try { localStorage.setItem(THEME_KEY, t.id); } catch (e) {}
  }
  /* 手寫體、粉圓體只有選到那一套才載，其他人不用多下載幾百 KB */
  function loadFont(spec) {
    var id = 'font-' + spec.replace(/[^A-Za-z]+/g, '-');
    if (document.getElementById(id)) return;
    var l = document.createElement('link');
    l.id = id; l.rel = 'stylesheet';
    l.href = 'https://fonts.googleapis.com/css2?family=' + spec + '&display=swap';
    document.head.appendChild(l);
  }
  applyTheme(currentTheme());

  /* 展示用帳號。mock 模式的登入頁會列出來，免得評審還要猜 email。
     接上真後端（API.mode === 'http'）之後就不顯示了。 */
  var DEMO = [
    { name: '林建國 · 家長',   email: 'jianguo@lin.tw' },
    { name: '陳淑芬 · 家長',   email: 'shufen@lin.tw' },
    { name: '林宇涵 · 子女',   email: 'yuhan@lin.tw' },
    { name: '林宇軒 · 子女',   email: 'yuxuan@lin.tw' },
    /* 還沒加入家庭——用家長登入邀請她，或用她登入輸入邀請碼 */
    { name: '林玉珍 · 還沒加入家庭', email: 'yuzhen@mail.tw' },
    /* ⚠️ 用他登入會看到完全不同的首頁——那正是這個角色的重點 */
    { name: '系統管理員 · 平台', email: 'admin@fambudget.tw' }
  ];
  var $title = document.getElementById('ptitle');
  var $sub = document.getElementById('psub');
  var $search = document.getElementById('search');
  var $toasts = document.getElementById('toasts');

  var ME = null;
  var F = { userId: 'all', kind: 'all', source: 'all', q: '' };

  /* 目前在看哪一本帳。'all' = 全部（我看得到的所有帳本合起來）。
     存在 localStorage，重新整理不會跳回去。 */
  var GKEY = 'fambudget.group';
  var GROUP = (function () {
    try { return localStorage.getItem(GKEY) || 'all'; } catch (e) { return 'all'; }
  })();
  function setGroup(id) {
    GROUP = id || 'all';
    try { localStorage.setItem(GKEY, GROUP); } catch (e) {}
  }
  var STAT = { period: 'month' };

  /* ============================================================
     展開與收起的動畫

     點了才長出來的東西，一律「往下拉開、往上收回」，兩個方向都有。
       版面裡的區塊   高度從 0 長到內容高度；收起時縮回 0，下面的內容跟著移動
       浮動的下拉     從按鈕往下滑出、往上收回，不推動任何內容

     ⚠️ 只用 CSS 做不到「收起」：hidden 一設下去元素就消失了，沒有時間播動畫。
        所以收起是先播完，再設 hidden。
     ⚠️ 使用者在系統設定裡關掉動態效果（prefers-reduced-motion）就直接開關。
     ============================================================ */
  var MOTION = !(global.matchMedia && global.matchMedia('(prefers-reduced-motion: reduce)').matches);

  function floating(el) {
    var p = getComputedStyle(el).position;
    return p === 'absolute' || p === 'fixed';
  }

  function slideOpen(el) {
    if (!el) return;
    el.hidden = false;
    if (el.__slide) { el.__slide.cancel(); el.__slide = null; }
    if (!MOTION || !el.animate) return;
    var a;
    if (floating(el)) {
      a = el.animate([
        { opacity: 0, transform: 'translateY(-10px)', clipPath: 'inset(0 0 100% 0)' },
        { opacity: 1, transform: 'none', clipPath: 'inset(0 0 0 0)' }
      ], { duration: 240, easing: 'cubic-bezier(.16,1,.3,1)' });
    } else {
      var cs = getComputedStyle(el);
      var h = el.getBoundingClientRect().height;
      el.style.overflow = 'hidden';
      a = el.animate([
        { height: '0px', opacity: 0, marginTop: '0px', marginBottom: '0px', paddingTop: '0px', paddingBottom: '0px' },
        { height: h + 'px', opacity: 1, marginTop: cs.marginTop, marginBottom: cs.marginBottom,
          paddingTop: cs.paddingTop, paddingBottom: cs.paddingBottom }
      ], { duration: 300, easing: 'cubic-bezier(.16,1,.3,1)' });
    }
    el.__slide = a;
    a.onfinish = a.oncancel = function () { el.style.overflow = ''; if (el.__slide === a) el.__slide = null; };
  }

  function slideClose(el, done) {
    if (!el || el.hidden) { if (done) done(); return; }
    if (el.__slide) { el.__slide.cancel(); el.__slide = null; }
    if (!MOTION || !el.animate) { el.hidden = true; if (done) done(); return; }
    var a;
    if (floating(el)) {
      a = el.animate([
        { opacity: 1, transform: 'none', clipPath: 'inset(0 0 0 0)' },
        { opacity: 0, transform: 'translateY(-10px)', clipPath: 'inset(0 0 100% 0)' }
      ], { duration: 180, easing: 'cubic-bezier(.4,0,1,1)', fill: 'forwards' });
    } else {
      var cs = getComputedStyle(el);
      el.style.overflow = 'hidden';
      a = el.animate([
        { height: el.getBoundingClientRect().height + 'px', opacity: 1, marginTop: cs.marginTop,
          marginBottom: cs.marginBottom, paddingTop: cs.paddingTop, paddingBottom: cs.paddingBottom },
        { height: '0px', opacity: 0, marginTop: '0px', marginBottom: '0px', paddingTop: '0px', paddingBottom: '0px' }
      ], { duration: 220, easing: 'cubic-bezier(.4,0,.2,1)', fill: 'forwards' });
    }
    el.__slide = a;
    var ended = false;
    function finish() {
      /* 收到一半又被打開（slideOpen 換掉了 __slide）就不要藏起來 */
      if (ended || el.__slide !== a) return;
      ended = true;
      el.hidden = true;
      el.style.overflow = '';
      a.cancel();
      el.__slide = null;
      if (done) done();
    }
    a.onfinish = finish;
    /* 保險：動畫被瀏覽器暫停或中斷時，狀態也不能卡在「半開」 */
    setTimeout(finish, a.effect.getTiming().duration + 250);
  }

  /* 從 DOM 拿掉的區塊（帳本、財務建議的展開內容）：收完再移除 */
  function slideAway(el, done) {
    if (!el) { if (done) done(); return; }
    slideClose(el, function () { el.remove(); if (done) done(); });
  }

  global.__slide = { open: slideOpen, close: slideClose };

  /* 右上角的帳號選單：往下拉開、往上收回 */
  function acctMenu(on) {
    var p = document.getElementById('acctPanel'), b = document.getElementById('acctBtn');
    if (!p) return;
    if (on === undefined) on = p.hidden;
    if (b) { b.setAttribute('aria-expanded', on ? 'true' : 'false'); b.classList.toggle('open', !!on); }
    if (on) { paintAcct(); slideOpen(p); } else slideClose(p);
  }
  var draft = null;                       // 自然語言解析後、尚未確認的暫存

  /* ---------- 小工具 ---------- */
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function el(h) { var d = document.createElement('div'); d.innerHTML = h.trim(); return d.firstChild; }
  function money(n) { return 'NT$ ' + Number(n || 0).toLocaleString('en-US'); }
  function pct(x) { return Math.round((x || 0) * 100) + '%'; }

  var ROLE_TW = { master: '平台管理員', parent: '家長', child: '子女' };

  function toast(msg, kind, undo) {
    var t = el('<div class="toast' + (kind ? ' toast--' + kind : '') + '">' +
      '<span class="toast__t">' + esc(msg) + '</span>' +
      (undo ? '<button class="toast__u">復原</button>' : '') + '</div>');
    if (undo) t.querySelector('.toast__u').addEventListener('click', function () { t.remove(); undo(); });
    $toasts.appendChild(t);
    setTimeout(function () {
      t.style.transition = 'opacity .25s, transform .25s';
      t.style.opacity = '0'; t.style.transform = 'translateX(16px)';
      setTimeout(function () { t.remove(); }, 260);
    }, undo ? 6000 : 3200);
  }

  function skeleton(n, cls) {
    var s = '<div class="skel">';
    for (var i = 0; i < (n || 5); i++) s += '<div class="skel__r' + (cls ? ' ' + cls : '') + '"></div>';
    return s + '</div>';
  }
  function emptyState(t, s) {
    return '<div class="empty"><svg class="empty__ic" viewBox="0 0 24 24" fill="none" ' +
      'stroke="currentColor" stroke-width="1.4"><path d="M3 3h18v18H3z"/><path d="M8 12h8"/></svg>' +
      '<div class="empty__t">' + esc(t) + '</div><div class="empty__s">' + esc(s) + '</div></div>';
  }
  function errState(e) {
    return '<div class="err"><div class="err__t">讀取失敗</div><div class="err__s">' +
      esc(e && e.message ? e.message : String(e)) + '<br>目前模式：<b>' + API.mode + '</b></div></div>';
  }

  /* ============================================================
     共用小零件
     ============================================================ */

  /* 線條圖示，跟頂列、儀表板同一套粗細 */
  var IC = (function () {
    function g(d) {
      return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" ' +
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + d + '</svg>';
    }
    return {
      in:   g('<path d="M12 4v11"/><path d="m7 10 5 5 5-5"/><path d="M5 20h14"/>'),
      out:  g('<path d="M12 20V9"/><path d="m7 14 5-5 5 5"/><path d="M5 4h14"/>'),
      net:  g('<path d="M3 7h18v12H3z"/><path d="M3 11h18"/><path d="M16 15h2"/>'),
      left: g('<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>'),
      goal: g('<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1"/>')
    };
  })();

  /* 金額：幣別小一號、淡一點，眼睛先落在數字上 */
  function amt(v) {
    var n = Math.round(Number(v) || 0);
    return '<span class="amt"><i>NT$</i>' + (n < 0 ? '−' : '') +
      Math.abs(n).toLocaleString('en-US') + '</span>';
  }

  function num(v) { return Number(Math.round(v || 0)).toLocaleString('en-US'); }

  /* 「林建國」叫「建國」，兩個字的名字就整個叫 */
  function callName(name) {
    name = String(name || '');
    return name.length === 3 ? name.slice(1) : name;
  }

  function greeting() {
    var h = new Date().getHours();
    return h < 11 ? '早安' : (h < 17 ? '午安' : '晚上好');
  }

  /* 「今天」是哪一天。
     ⚠️ mock 的示範資料停在某一天（DATA.meta.updated），如果拿電腦的日期，
     總覽的「今天的紀錄」永遠是空的、問候語的日期也跟資料對不上。
     接上真後端之後，今天就是真的今天。 */
  function todayKey() {
    if (API.mode !== 'http') {
      var k = String((global.DATA.meta && global.DATA.meta.updated) || '').slice(0, 10);
      if (/^\d{4}-\d{2}-\d{2}$/.test(k)) return k;
    }
    var d = new Date();
    return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2);
  }

  function todayText() {
    var d = new Date(todayKey() + 'T12:00:00');
    return (d.getMonth() + 1) + ' 月 ' + d.getDate() + ' 日　星期' + '日一二三四五六'.charAt(d.getDay());
  }

  /* ============================================================
     我／全家

     家庭跟個人是**同一套畫面**，差別只在範圍：
       我    自己的數字，可以記帳、可以調整
       全家  整理全家的資訊，**唯讀**——沒有「記一筆」，也沒有任何輸入框

     只有家長、而且真的有監管對象時才出現切換。子女只有「我」。
     ============================================================ */
  var SCOPE = (function () {
    try { return sessionStorage.getItem('fambudget.scope') === 'family' ? 'family' : 'me'; }
    catch (e) { return 'me'; }
  })();

  function canFamily(m) {
    return !!(m && m.user && m.user.role === 'parent' && (m.visible || []).length > 1);
  }

  function scopeOf(m) { return canFamily(m) ? SCOPE : 'me'; }

  function seg(key, opts, cur, off) {
    return '<div class="seg" role="group">' + opts.map(function (o) {
      var dis = off && off.indexOf(o[0]) >= 0;
      return '<button class="seg__b' + (cur === o[0] ? ' on' : '') + '" data-' + key + '="' + o[0] + '"' +
        ' aria-pressed="' + (cur === o[0]) + '"' + (dis ? ' disabled' : '') + '>' + o[1] + '</button>';
    }).join('') + '</div>';
  }

  function scopeSeg(m) {
    return canFamily(m) ? seg('scope', [['me', '我'], ['family', '全家']], SCOPE) : '';
  }

  /* ============================================================
     01 總覽：這個月現在怎樣

     只放四個數字、存款目標、預算。圖表在「統計」，紀錄在「收支明細」——
     主頁什麼都塞，使用者反而找不到最重要的那一個數字。
     ============================================================ */
  /* ============================================================
     01 總覽：儀表板

     照富邦新版的首頁：沒有側欄，所有功能都嵌在這一頁上。
       1. 疊卡       後面露出收入、支出，最前面是這個月還可以花
       2. 常用功能   收支明細、帳本、統計、財務建議、家庭成員、個人資料、使用說明（電腦版多一顆記一筆）
       3. 預算       一個分類一張小卡，右上角「看統計 ›」
       4. 今天       今天記的每一筆——一打開就知道今天的動向
       全家模式在預算後面多「每個人的這個月」，今天的紀錄也換成全家的

     ⚠️ 趨勢圖在「統計」、完整明細與篩選在「收支明細」，這裡不重複放。
     ============================================================ */
  var TILE_IC = {
    add: '<path d="M12 5v14M5 12h14"/>',
    entry: '<path d="M5 4h10l4 4v12H5z"/><path d="M15 4v4h4"/><path d="M9 13h6M9 16.5h4"/>',
    groups: '<path d="M4 5h11a3 3 0 0 1 3 3v12H7a3 3 0 0 1-3-3z"/><path d="M18 8h2v12"/><path d="M8 9h6M8 13h4"/>',
    stats: '<path d="M4 20V10M10 20V4M16 20v-7M21 20H3"/>',
    advice: '<path d="M12 3a6 6 0 0 0-3.5 10.9V17h7v-3.1A6 6 0 0 0 12 3z"/><path d="M9.5 20.5h5"/>',
    members: '<circle cx="9" cy="8" r="3"/><circle cx="17" cy="9.5" r="2.3"/><path d="M3.5 20v-1.5A4.5 4.5 0 0 1 8 14h2a4.5 4.5 0 0 1 4.5 4.5V20"/><path d="M15.5 14.5h1.5a3.5 3.5 0 0 1 3.5 3.5v2"/>',
    profile: '<circle cx="12" cy="8" r="3.5"/><path d="M5 20v-1.5A5.5 5.5 0 0 1 10.5 13h3a5.5 5.5 0 0 1 5.5 5.5V20"/>',
    guide: '<path d="M12 6.5S10 5 7 5H4v13h3c3 0 5 1.5 5 1.5S14 18 17 18h3V5h-3c-3 0-5 1.5-5 1.5z"/><path d="M12 6.5v13"/>'
  };

  function tile(t) {
    var attr = t.quick ? ' data-quick="entry"' : t.nav !== undefined ? ' data-nav="' + t.nav + '"' : '';
    var tag = t.href ? 'a' : 'button';
    return '<' + tag + ' class="dtile' + (t.tone ? ' dtile--' + t.tone : '') + '"' + attr + (t.href ? ' href="' + t.href + '"' : '') + '>' +
      '<span class="dtile__ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" ' +
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + TILE_IC[t.icon] + '</svg></span>' +
      '<span class="dtile__t">' + esc(t.label) + '</span>' +
      (t.badge ? '<span class="dtile__b">' + esc(t.badge) + '</span>' : '') +
    '</' + tag + '>';
  }

  function vHome() {
    head('總覽', '');
    $view.innerHTML = '<div class="page">' + skeleton(4, 'skel__k') + '</div>';

    API.me().then(function (m) {
      var sc = scopeOf(m), fam = sc === 'family';
      return Promise.all([
        API.summary({ scope: sc, groupId: GROUP }),
        API.budgets({ groupId: GROUP }),
        API.groups({}).catch(function () { return { groups: [] }; }),
        API.advices({ scope: sc }).catch(function () { return { advices: [] }; }),
        API.members().catch(function () { return { members: [], family: null }; }),
        /* 今天的紀錄：我的模式只看自己，全家模式看全家（下面再濾成統計算進去的那幾個人） */
        API.transactions(Object.assign({ from: todayKey(), to: todayKey(), groupId: GROUP },
          fam ? {} : { userId: m.user.id })).catch(function () { return { transactions: [] }; })
      ]).then(function (r) {
        var d = r[0], b = r[1], gs = r[2].groups || [], ads = r[3].advices || [], fm = r[4];
        var ids = d.members ? d.members.map(function (u) { return u.id; }) : [m.user.id];
        var today = (r[5].transactions || []).filter(function (t) { return !fam || ids.indexOf(t.user) >= 0; });
        head(fam ? '全家這個月' : greeting() + '，' + callName(m.user.name),
             fam ? d.members.length + ' 位家人的收支' : todayText(),
             scopeSeg(m));

        var sv = d.savings, lv = sv.level;
        var used = Math.min(100, Math.round(sv.ratio * 100));
        var budgets = fam ? b.budgets : b.budgets.filter(function (x) { return x.user === m.user.id; });
        var warn = ads.filter(function (a) { return a.level === 'warn'; }).length;
        var go = fam ? '#/stats' : '#/entry';
        var chev = '<svg class="wal__cv" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
          'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg>';

        var h = '<div class="page"><div id="homeInv"></div><div class="dash">';

        /* 1. 疊在一起的數字卡——像皮夾裡的卡片。
              後面兩張露出一截：收入、支出；最前面那張是這個月還可以花。 */
        h += '<section class="wal wal--' + lv + '" aria-label="這個月的錢">' +
          '<a class="wal__strip wal__strip--1" href="' + go + '">' +
            '<span>' + (fam ? '全家收入' : '本月收入') + '</span><b>' + amt(d.income) + '</b>' + chev + '</a>' +
          '<a class="wal__strip wal__strip--2" href="' + go + '">' +
            '<span>' + (fam ? '全家支出' : '本月支出') + '<small>' + d.count + ' 筆</small></span>' +
            '<b>' + amt(d.expense) + '</b>' + chev + '</a>' +
          '<div class="wal__card">' +
            '<div class="wal__k">' + (lv === 'over' ? '這個月超出計畫' : '這個月還可以花') +
              (lv === 'over' ? '' : '<span class="pill pill--' + lv + '">' + LEVEL_TW[lv] + '</span>') + '</div>' +
            '<div class="wal__v">' + amt(lv === 'over' ? sv.shortfall : Math.max(0, sv.left)) + '</div>' +
            '<div class="wal__bar" role="progressbar" aria-valuenow="' + used + '" aria-valuemin="0" aria-valuemax="100">' +
              '<i style="width:' + used + '%"></i></div>' +
            '<div class="wal__meta"><span>已用 <b>' + used + '%</b></span>' +
              '<span>可花上限 <b>' + num(sv.allowance) + '</b></span>' +
              '<span>每月想存 <b>' + num(sv.goal) + '</b></span></div>' +
            '<div class="wal__foot">' +
              '<div class="wal__f"><span>結餘</span><b>' + amt(d.net) + '</b></div>' +
              '<div class="wal__f"><span>存下</span><b>' + pct(d.rate) + '</b></div>' +
              '<a class="wal__go" href="#/stats" aria-label="看統計" title="看統計">' +
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
                'stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg></a>' +
            '</div>' +
          '</div>' +
        '</section>';

        /* 2. 常用功能：原本側欄的東西都在這裡
              ⚠️ 全家模式只整理資訊，沒有「記一筆」——記帳永遠是記自己的 */
        var tiles = [
          fam ? null : { quick: true, label: '記一筆', icon: 'add', tone: 'add' },
          { nav: 'entry', label: '收支明細', icon: 'entry', badge: d.count ? d.count + ' 筆' : '' },
          { nav: 'groups', label: '帳本', icon: 'groups', badge: gs.length ? gs.length + ' 本' : '' },
          { nav: 'stats', label: '統計', icon: 'stats' },
          { nav: 'advice', label: '財務建議', icon: 'advice', tone: warn ? 'warn' : '', badge: warn ? warn + ' 則要注意' : '' },
          { nav: 'members', label: fm.family ? '家庭成員' : '加入家庭', icon: 'members',
            badge: fm.family ? fm.members.length + ' 人' : '' },
          { nav: 'profile', label: '個人資料', icon: 'profile' },
          { href: 'docs/guide.html', label: '使用說明', icon: 'guide' }
        ];
        h += '<section class="qk"><div class="qk__h"><h2 class="qk__t">常用功能</h2></div>' +
          '<nav class="dgrid" aria-label="功能">' + tiles.filter(Boolean).map(tile).join('') + '</nav></section>';
        h += '</div>';

        /* 3. 預算：一個分類一張小卡 */
        h += '<div class="sec"><h2 class="sec__t">預算使用狀況</h2>' +
          (budgets.length ? '<span class="sec__n">' + budgets.length + ' 項</span>' : '') +
          '<a class="sec__link" href="#/stats">看統計 ›</a></div>';
        h += budgets.length
          ? '<div class="bgrid">' + budgets.map(function (x) {
              var p = Math.round(x.pct * 100);
              return '<div class="bcard' + (x.over ? ' is-over' : '') + '">' +
                '<div class="bcard__top"><span class="dot" style="background:' + tint(x.catColor) + '"></span>' +
                  '<b>' + esc(x.catName) + '</b>' + (fam ? '<small>' + esc(x.userName) + '</small>' : '') +
                  '<span class="bcard__p">' + p + '%</span></div>' +
                '<div class="bcard__bar"><i style="width:' + Math.min(100, p) + '%;background:' +
                  (x.over ? 'var(--down)' : tint(x.catColor)) + '"></i></div>' +
                '<div class="bcard__v">' + num(x.used) + '<small> / ' + num(x.limit) + '</small></div>' +
              '</div>';
            }).join('') + '</div>'
          : '<div class="card">' + emptyState('還沒有設定預算', '替常花的分類設個上限，花到一定程度就會提醒你。') + '</div>';

        if (fam) {
          h += '<div class="sec"><h2 class="sec__t">每個人的這個月</h2></div>' +
            memberTable(d.members, d.expense) +
            '<div class="card mshare-card">' + memberBar(d.members, d.expense) + '</div>';
        }

        /* 4. 今天的紀錄：一打開就看得到今天的動向 */
        h += todayCard(today, fam);

        $view.innerHTML = h + '</div>';
        animate();

        /* 有人邀請你、或是你還沒有家庭，放在最上面——這是現在唯一要你決定的事 */
        API.invites().then(function (inv) {
          var box = document.getElementById('homeInv');
          if (!box) return;
          if (inv.received.length) box.innerHTML = inviteCards(inv.received);
          else if (!m.family && !m.user.isPlatformAdmin) {
            box.innerHTML = '<a class="nudge" href="#/members"><b>還沒有加入家庭</b>' +
              '<span>建立一個，或輸入家人給你的邀請碼 →</span></a>';
          }
        }).catch(function () {});
      });
    }).catch(function (e) { $view.innerHTML = '<div class="page">' + errState(e) + '</div>'; });
  }

  /* 今天的紀錄。上面一條是今天花了多少、收了多少，下面是一筆一筆。
     ⚠️ 只放今天：完整的明細在「收支明細」，這裡不做篩選、不做刪除。 */
  function todayCard(rows, fam) {
    var MAX = 6, spent = 0, got = 0;
    rows.forEach(function (t) {
      if (t.kind === 'income') got += t.amount;
      else if (t.kind === 'expense') spent += t.amount;
    });
    var d = new Date(todayKey() + 'T12:00:00');
    var h = '<div class="sec"><h2 class="sec__t">' + (fam ? '全家今天的紀錄' : '今天的紀錄') + '</h2>' +
      (rows.length ? '<span class="sec__n">' + rows.length + ' 筆</span>' : '') +
      '<a class="sec__link" href="#/entry">看全部 ›</a></div>';

    if (!rows.length) {
      /* ⚠️ 選了某一本帳的時候，「今天還沒有記帳」會讓人以為真的沒記——其實是被帳本篩掉了 */
      var one = GROUP !== 'all';
      return h + '<div class="card tdy tdy--empty">' +
        (one
          ? emptyState('這本帳今天還沒有紀錄', '右上角切回「全部帳本」，就看得到今天所有的紀錄。')
          : emptyState('今天還沒有記帳', fam ? '家人今天記的帳會出現在這裡。' : '花了什麼，說一句話就記好了。')) +
        (fam ? '' : '<div class="tdy__go"><button class="btn btn--go btn--sm" data-quick="entry">記一筆</button></div>') +
      '</div>';
    }

    return h + '<div class="card card--flush tdy">' +
      '<div class="tdy__sum">' +
        '<span class="tdy__day">' + (d.getMonth() + 1) + ' 月 ' + d.getDate() + ' 日</span>' +
        '<span>支出 <b class="is-out">' + num(spent) + '</b></span>' +
        '<span>收入 <b class="is-in">' + num(got) + '</b></span>' +
      '</div>' +
      '<ul class="tdy__l">' + rows.slice(0, MAX).map(function (t) {
        var sign = t.kind === 'income' ? '+' : t.kind === 'expense' ? '−' : '';
        return '<li><a class="tdy__i" href="#/entry">' +
          '<span class="tdy__ic" style="--c:' + tint(t.catColor) + '">' + esc((t.catName || '記').charAt(0)) + '</span>' +
          '<span class="tdy__m"><b>' + esc(t.merchant || t.catName) + '</b>' +
            '<small>' + esc(t.catName) + (fam ? ' · ' + esc(t.userName) : '') +
              (t.note ? ' · ' + esc(t.note) : '') + '</small></span>' +
          '<span class="tdy__a is-' + esc(t.kind) + '">' + sign + num(t.amount) + '</span>' +
        '</a></li>';
      }).join('') + '</ul>' +
      (rows.length > MAX ? '<a class="tdy__more" href="#/entry">還有 ' + (rows.length - MAX) + ' 筆，看全部 ›</a>' : '') +
    '</div>';
  }

  var LEVEL_TW = { safe: '進度穩穩的', near: '快到上限了', over: '超出計畫' };

  /* 全家模式：每個人一列。點一列就進那個人的紀錄（唯讀） */
  function memberTable(members, total) {
    return '<div class="card card--flush"><table class="dt">' +
      '<thead><tr><th>成員</th><th class="rt">收入</th><th class="rt">支出</th>' +
      '<th class="rt">結餘</th><th>佔全家支出</th></tr></thead><tbody>' +
      members.map(function (u) {
        var net = u.income - u.expense;
        var share = total ? Math.round(u.expense / total * 100) : 0;
        return '<tr class="dt__go" data-open="' + esc(u.id) + '" title="看 ' + esc(u.name) + ' 的紀錄">' +
          '<td><span class="dt__name">' + ava(u, 'ava--sm') +
            '<span><b>' + esc(u.name) + '</b><small>' + esc(ROLE_TW[u.role] || '') + '</small></span></span></td>' +
          '<td class="rt num">' + num(u.income) + '</td>' +
          '<td class="rt num">' + num(u.expense) + '</td>' +
          '<td class="rt num ' + (net >= 0 ? 'is-up' : 'is-down') + '">' + (net >= 0 ? '+' : '−') + num(Math.abs(net)) + '</td>' +
          '<td class="dt__bar"><span class="mbar"><i style="width:' + share + '%"></i></span><em>' + share + '%</em></td>' +
        '</tr>';
      }).join('') + '</tbody></table></div>';
  }

  /* 圓環圖：純 SVG */
  function donut(byCat, total) {
    var R = 62, C = 2 * Math.PI * R, off = 0;
    var arcs = byCat.map(function (c) {
      var frac = total ? c.amount / total : 0;
      /* ⚠️ stroke 是 SVG 的「呈現屬性」，不吃 var()——要寫進 style 才有效 */
      var seg = '<circle cx="80" cy="80" r="' + R + '" fill="none" style="stroke:' + tint(c.color) +
        '" stroke-width="24" stroke-dasharray="' + (frac * C).toFixed(1) + ' ' + C.toFixed(1) +
        '" stroke-dashoffset="' + (-off * C).toFixed(1) + '" transform="rotate(-90 80 80)"/>';
      off += frac;
      return seg;
    }).join('');
    return '<div class="dnt"><svg width="160" height="160" viewBox="0 0 160 160">' + arcs +
      '<text x="80" y="76" text-anchor="middle" font-size="10" fill="var(--ink-faint)" ' +
      'font-family="var(--mono)">本月支出</text>' +
      '<text x="80" y="95" text-anchor="middle" font-size="15" fill="var(--ink)" ' +
      'font-weight="700" font-family="var(--mono)">' + Number(total).toLocaleString('en-US') + '</text>' +
      '</svg><div class="dnt__l">' + byCat.map(function (c) {
        return '<div class="dnt__i"><span class="dot" style="background:' + tint(c.color) + '"></span>' +
          '<span class="dnt__n">' + esc(c.name) + '</span>' +
          '<span class="dnt__v">' + money(c.amount) + '</span>' +
          '<span class="dnt__p">' + pct(total ? c.amount / total : 0) + '</span></div>';
      }).join('') + '</div></div>';
  }

  /* 誰花的：一條橫的堆疊條 ＋ 一份名單。

     家庭總覽真正多出來的問題是「這筆是誰花的」——
     「錢花在什麼」個人總覽已經用圓餅回答了，再畫一次只是重複。 */
  function memberBar(members, total) {
    if (!members.length || !total) return emptyState('還沒有支出', '這個月還沒有人記到支出。');
    var cols = ['var(--accent)', 'var(--accent-2)', 'var(--warn)', 'var(--info)',
                'var(--down)', 'var(--up)'];
    var rows = members.slice().sort(function (a, b) { return b.expense - a.expense; });
    var bar = rows.map(function (u, i) {
      var w = u.expense / total * 100;
      return '<i style="width:' + w.toFixed(2) + '%;background:' + cols[i % cols.length] +
        '" title="' + esc(u.name) + ' ' + money(u.expense) + '"></i>';
    }).join('');
    var list = rows.map(function (u, i) {
      return '<div class="mshare__i">' +
        '<span class="dot" style="background:' + cols[i % cols.length] + '"></span>' +
        '<span class="mshare__n">' + esc(u.name) + '</span>' +
        '<span class="mshare__p">' + pct(u.expense / total) + '</span>' +
        '<b class="mshare__v num">' + money(u.expense) + '</b>' +
      '</div>';
    }).join('');
    return '<div class="mshare"><div class="mshare__b">' + bar + '</div>' + list + '</div>';
  }

  function barChart(rows) {
    /* ⚠️ 選了單一帳本時 summary 會回 null——每個人的月數列沒有分帳本，
       硬畫出來就是一張假的圖。這裡回一句話，不要讓整頁掛掉。

       這個防護漏掉過一次：家庭總覽加了 if (d.monthly)，統計頁沒加，
       於是「選了某一本帳 → 打開統計」整頁變成「讀取失敗」。 */
    if (!rows || !rows.length) {
      return emptyState('近 6 個月看不到', '月趨勢只有在「全部帳本」時算得出來。');
    }
    var max = Math.max.apply(null, rows.map(function (r) { return Math.max(r.income, r.expense); })) || 1;
    return '<div class="bars">' + rows.map(function (r, i) {
      return '<div class="bars__g">' +
        '<div class="bars__p">' +
          '<i style="height:' + (r.income / max * 100) + '%;background:var(--up);animation-delay:' + (i * 60) + 'ms"></i>' +
          '<i style="height:' + (r.expense / max * 100) + '%;background:var(--warn);animation-delay:' + (i * 60 + 30) + 'ms"></i>' +
        '</div><div class="bars__k">' + esc(r.label || String(r.m || '').slice(5)) + '</div></div>';
    }).join('') + '</div>' +
      '<div class="lgd"><span><i style="background:var(--up)"></i>收入</span>' +
      '<span><i style="background:var(--warn)"></i>支出</span></div>';
  }

  /* 這筆是不是我自己的。ME 還沒載入時一律當成別人的 ——
     寧可少一顆按鈕，也不要讓人對別人的紀錄按下刪除。 */
  function isMine(t) {
    return !!(ME && ME.user && t.user === ME.user.id);
  }

  /* hit = 要標起來的那一筆 id（從通知點進來時用）。
     ⚠️ 不要寫成 .map(txRow)——map 會把索引值當成第二個參數傳進來。
     所以呼叫端一律包一層 function。 */
  /* 明細是表格。
     帳目本來就是一欄一欄對齊的東西——日期對日期、金額對金額。
     卡片式的排版每一筆的資訊位置都不一樣，掃過去很累。 */
  function txRow(t, hit) {
    return '<tr class="txr' + (hit && hit === t.id ? ' is-hit' : '') + '">' +
      '<td class="txr__d">' + esc(t.date) + '</td>' +
      '<td class="txr__c"><span style="color:' + tint(t.catColor) + '">' +
        esc(t.catName) + '</span></td>' +
      '<td class="txr__t">' + esc(t.merchant || t.catName) +
        (t.note ? ' <em>' + esc(t.note) + '</em>' : '') +
        (t.raw ? '<br><span class="txr__raw">「' + esc(t.raw) + '」</span>' : '') +
      '</td>' +
      '<td class="txr__u">' + esc(t.userName) + '</td>' +
      '<td class="txr__s">' + (t.source === 'nlp' ? '段落' : '手動') + '</td>' +
      '<td class="txr__a' + (t.kind === 'income' ? ' is-in' : '') + '">' +
        (t.kind === 'income' ? '+' : '−') + money(t.amount).replace('NT$ ', '') + '</td>' +
      '<td class="txr__x">' +
        (isMine(t) ? '<button class="del" data-del="' + esc(t.id) + '">刪除</button>' : '') +
      '</td></tr>';
  }

  /* 表頭 ＋ 表身。空的時候不要畫一個只有表頭的空表格。 */
  function txTable(rows, hit, empty) {
    if (!rows.length) return empty;
    return '<div class="txw card card--flush"><table class="txt">' +
      '<thead><tr>' +
        '<th>日期</th><th>分類</th><th>項目</th><th>記錄者</th><th>來源</th>' +
        '<th class="rt">金額</th><th></th>' +
      '</tr></thead><tbody>' +
      rows.map(function (t) { return txRow(t, hit); }).join('') +
      '</tbody></table></div>';
  }

  /* ============================================================
     02 記帳（自然語言輸入）
     ============================================================ */
  /* ============================================================
     收合區塊

     一個畫面只留「現在要看的東西」，其他的收起來，點了才長出來。

     理由是版面：一進來就攤開三四個區塊，使用者得先跳過前面兩個
     才找得到自己要的。次要功能收起來之後，主功能自己會浮上來。

     ⚠️ 內容是**點了才渲染**，不是先畫好再 display:none。
        先畫好的話，一個沒人展開的區塊照樣花掉它的渲染時間，
        而且藏起來的東西最容易腐爛——沒人看得到它壞了。
     ============================================================ */
  var FOLD = {};                       // id → 展開中嗎

  function foldHead(id, title, label, kicker, help, tools) {
    var on = !!FOLD[id];
    /* ⚠️ title 一定要 esc()，所以問號不能混在 title 裡傳進來——
       那樣傳會變成畫面上出現一串 &lt;button&gt;。要掛說明就用 help 參數。 */
    return '<div class="sec"><h2 class="sec__t">' + esc(title) +
      (help ? helpBtn(help) : '') + '</h2>' +
      (kicker ? '<span class="sec__n">' + esc(kicker) + '</span>' : '') +
      (tools ? '<div class="sec__tools">' + tools + '</div>' : '') +
      '<button class="fold__b' + (on ? ' on' : '') + '" data-fold="' + esc(id) + '" ' +
        'data-label="' + esc(label) + '" ' +
        'aria-expanded="' + (on ? 'true' : 'false') + '">' +
        '<span class="fold__x" aria-hidden="true"></span>' +
        '<span class="fold__t">' + esc(on ? '收起' : label) + '</span>' +
      '</button></div>' +
      '<div class="fold__p" id="fold-' + esc(id) + '"' + (on ? '' : ' hidden') + '></div>';
  }

  /* 每個收合區塊怎麼長出自己的內容。展開的當下才會被呼叫。 */
  var FOLD_BUILD = {};

  /* 內容已經是一段 HTML 字串的，放這裡就好，不用另外寫 builder。
     ⚠️ 字串是先組好沒錯，但**節點要展開才會進 DOM**——
        沒有版面、沒有排版計算，收起來的區塊是真的不存在。 */
  var FOLD_HTML = {};

  function foldBlock(id, title, label, html, kicker, help) {
    FOLD_HTML[id] = html;
    return foldHead(id, title, label, kicker, help);
  }

  function foldFill(id, wrap) {
    if (FOLD_BUILD[id]) { FOLD_BUILD[id](wrap); return; }
    if (FOLD_HTML[id] != null) wrap.innerHTML = FOLD_HTML[id];
  }

  /* 畫面重畫之後，本來展開的區塊要自己長回來——
     否則使用者展開一個表單、按了送出，重畫完就無聲收合了。 */
  function foldRestore() {
    Array.prototype.forEach.call(
      document.querySelectorAll('[data-fold]'), function (b) {
        var id = b.dataset.fold;
        if (!FOLD[id]) return;
        var wrap = document.getElementById('fold-' + id);
        if (wrap && !wrap.innerHTML) foldFill(id, wrap);
      });
  }

  function foldToggle(id) {
    var wrap = document.getElementById('fold-' + id);
    var btn = document.querySelector('[data-fold="' + id + '"]');
    if (!wrap) return;
    var on = !FOLD[id];
    FOLD[id] = on;
    if (btn) {
      btn.classList.toggle('on', on);
      btn.setAttribute('aria-expanded', on ? 'true' : 'false');
      var t = btn.querySelector('.fold__t');
      if (t) t.textContent = on ? '收起' : (btn.dataset.label || '展開');
    }
    if (!on) { slideClose(wrap); return; }
    wrap.hidden = false;
    if (!wrap.innerHTML) foldFill(id, wrap);
    slideOpen(wrap);
  }

  var MODE = 'para';          // 'para' 段落批次 ｜ 'single' 單筆手動。兩者互斥
  var batch = null;           // 段落解析結果，尚未寫入

  /* 記帳頁：明細先出來。

     「記一筆」是有事才做的動作，不該一進來就佔掉半個版面——
     大部分時候使用者是來看自己花了什麼，不是來記帳的。
     要記的時候點 ＋，表單才長出來。 */
  function vEntry() {
    head('收支明細', '');
    var h = '<div class="page">';

    /* 篩選放在標題那一列，跟「記一筆」並排——不要自己佔一整條 */
    h += foldHead('entry', '所有紀錄', '記一筆', '', null, filterBar());
    h += '<div id="txList">' + skeleton(6) + '</div></div>';
    $view.innerHTML = h;

    foldRestore();
    loadTx();
  }

  /* 理財習慣：拿來當財務建議的背景。

     ⚠️ 全部是**從固定清單挑選**，只有補充說明是自由文字，而且限 200 字。
     不是為了防呆——建議是會給監管者看的，如果子女能在自己的說明裡
     下指令，就能操控父母看到的內容。隔離的做法在 toolkit/profile.py。 */
  FOLD_BUILD.fin = function (wrap) {
    wrap.innerHTML = skeleton(2);
    API.financeProfile().then(function (d) {
      var f = d.finance || {};
      var picked = function (list, key) {
        return (f[key] || []).indexOf(list) >= 0 ? ' checked' : '';
      };
      wrap.innerHTML = '<form class="card finf" id="finF">' +
        '<div class="finf__g"><span class="finf__k">理財風格</span>' +
          '<div class="finf__o">' + d.styles.map(function (x) {
            return '<label class="pick"><input type="radio" name="finStyle" value="' +
              esc(x.id) + '"' + (f.style === x.id ? ' checked' : '') + '>' +
              '<b>' + esc(x.name) + '</b><i>' + esc(x.desc) + '</i></label>';
          }).join('') + '</div></div>' +

        '<div class="finf__g"><span class="finf__k">目前最在意的</span>' +
          '<div class="finf__o finf__o--row">' + d.goals.map(function (x) {
            return '<label class="pick pick--sm"><input type="checkbox" name="finGoal" value="' +
              esc(x.id) + '"' + picked(x.id, 'goals') + '><b>' + esc(x.name) + '</b></label>';
          }).join('') + '</div></div>' +

        '<div class="finf__g"><span class="finf__k">固定的財務安排</span>' +
          '<div class="finf__o finf__o--row">' + d.habits.map(function (x) {
            return '<label class="pick pick--sm"><input type="checkbox" name="finHabit" value="' +
              esc(x.id) + '"' + picked(x.id, 'habits') + '><b>' + esc(x.name) + '</b></label>';
          }).join('') + '</div></div>' +

        '<label class="fld"><span>還有什麼是我們該知道的（選填，200 字）</span>' +
          '<textarea id="finNote" rows="3" maxlength="200" ' +
            'placeholder="例如：房貸還有十二年，小孩教育費最優先">' +
            esc(f.note || '') + '</textarea></label>' +
        '<div><button class="btn btn--go" type="submit">儲存</button></div>' +
      '</form>';
    }).catch(function (e) { wrap.innerHTML = errState(e); });
  };

  FOLD_BUILD.entry = function (wrap) {
    /* ---- 模式切換：抽屜 ----
       兩張帶說明的大卡片收成一條。要用哪一種是常態性的選擇，
       選好之後幾乎不會再動，不值得一直佔著版面。 */
    var h = '<div class="mbar">' +
      /* ⚠️ helpBtn() 回傳的是一個 <button>，不可以放進另一個 <button> 裡。
         HTML 不允許按鈕巢狀——瀏覽器解析到內層按鈕時會把外層直接關掉，
         後面的東西就被踢出去變成兄弟節點，樣式全部對不上。
         問號放在按鈕外面。 */
      '<button class="mbar__b" id="modeBtn">' +
        '<span class="mbar__n">' + (MODE === 'para' ? '段落記帳' : '單筆手動') + '</span>' +
        '<svg class="mbar__cv" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
          'stroke-width="2"><path d="m6 9 6 6 6-6"/></svg>' +
      '</button>' +
      (MODE === 'para' ? helpBtn('entry') : '') +
      '<div class="mbar__p" id="modePanel" hidden>' +
        modeRow('para', '段落記帳', '一次寫一整段，自動切成好幾筆') +
        modeRow('single', '單筆手動', '一次填一筆，欄位自己選') +
      '</div>' +
    '</div>';

    h += '<div id="entryBox"></div>';
    wrap.innerHTML = h;
    renderMode();
  };

  function modeRow(id, title, desc) {
    return '<button class="mbar__i' + (MODE === id ? ' on' : '') +
      '" data-mode="' + id + '">' +
      '<span class="mbar__t">' + esc(title) + '</span>' +
      '<span class="mbar__d">' + esc(desc) + '</span></button>';
  }

  function renderMode() {
    // 確認訊息要顯示分類名稱，先把對照表備好
    if (!Object.keys(DATA_CATS).length && global.DATA) {
      (global.DATA.categories || []).forEach(function (c) { DATA_CATS[c.id] = c.name; });
    }
    var box = document.getElementById('entryBox');
    if (!box) return;
    box.innerHTML = MODE === 'para' ? paraHTML() : singleHTML();

    // 抽屜上的標籤與選中狀態也要跟著換，不然按了看起來沒反應
    var n = document.querySelector('.mbar__n');
    if (n) n.textContent = MODE === 'para' ? '段落記帳' : '單筆手動';
    Array.prototype.forEach.call(document.querySelectorAll('.mbar__i'), function (b) {
      b.classList.toggle('on', b.dataset.mode === MODE);
    });
    var mp = document.getElementById('modePanel');
    if (mp) mp.hidden = true;
    var mb = document.getElementById('modeBtn');
    if (mb) mb.classList.remove('open');
  }

  /* ============================================================
     段落記帳
     ============================================================ */
  function paraHTML() {
    return '<div class="card nlp">' +
      '<div class="card__h"><span class="card__t">寫一段話，系統幫你拆成好幾筆</span>' +
      '<span class="card__s">解析後由你確認才寫入</span></div>' +
      '<textarea id="paraText" class="nlp__ta" rows="3" ' +
      'placeholder="例如：早上買早餐55，中午跟同事吃飯320，下午在全家買咖啡，晚上加油1200，今天打工賺了1500"></textarea>' +
      '<div class="nlp__row">' +
        '<button class="btn btn--go" id="paraGo">解析這段話</button>' +
        '<button class="chip" id="paraEx">用示範段落試試</button>' +
      '</div>' +
      '<div id="paraOut"></div></div>';
  }

  function renderBatch(r) {
    var out = document.getElementById('paraOut');
    if (!out) return;
    batch = r.items.map(function (x) { return Object.assign({}, x); });

    var miss = batch.filter(function (x) { return x.missing && x.missing.length; }).length;
    var h = '<div class="prs">';
    h += '<div class="prs__h">這段話被切成 <b>' + batch.length + ' 筆</b>' +
      (miss ? '，其中 <b style="color:var(--warn)">' + miss + ' 筆有欄位缺漏</b>，補齊才能送出' : '') +
      '</div>';

    h += '<div class="btbl"><div class="btbl__hd">' +
      '<span></span><span>原句</span><span>日期</span><span>金額</span>' +
      '<span>收支</span><span>分類</span><span>店家</span><span></span></div>';
    h += batch.map(function (it, i) { return batchRow(it, i); }).join('');
    h += '</div>';

    h += '<div class="prs__a">' +
      '<button class="btn btn--go" id="paraSave"><span id="paraLbl">確認並寫入</span>' +
      ' <b id="paraN">' + batch.length + '</b> 筆</button>' +
      '<button class="btn" id="paraCancel">全部捨棄</button></div></div>';
    out.innerHTML = h;
    syncSaveState();
  }

  function batchRow(it, i) {
    var cats = global.DATA.categories.filter(function (c) { return c.kind === it.kind; });
    function miss(f) { return it.missing && it.missing.indexOf(f) >= 0; }
    function cell(field, inner, conf) {
      var low = conf !== undefined && conf > 0 && conf < 0.85;
      return '<span class="bcell' + (miss(field) ? ' is-miss' : (low ? ' is-low' : '')) + '">' +
        inner +
        (miss(field) ? '<em class="bcell__x">必填</em>'
                     : (low ? '<em class="bcell__c">' + pct(conf) + '</em>' : '')) +
        '</span>';
    }
    return '<div class="btbl__r' + (it.missing && it.missing.length ? ' has-miss' : '') +
      '" data-bi="' + i + '" style="animation-delay:' + (i * 50) + 'ms">' +
      '<span class="btbl__n">' + it.seq + '</span>' +
      '<span class="btbl__span">' + esc('「' + it.span + '」') +
        (it.hint ? '<em class="btbl__hint">' + esc(it.hint) + '</em>' : '') + '</span>' +
      cell('date', '<input data-b="date" type="date" value="' + esc(it.date || '') + '">', it.conf.date) +
      cell('amount', '<input data-b="amount" type="number" placeholder="缺" value="' +
           (it.amount === null || it.amount === undefined ? '' : it.amount) + '">', it.conf.amount) +
      cell('kind', '<select data-b="kind">' +
           '<option value="expense"' + (it.kind === 'expense' ? ' selected' : '') + '>支出</option>' +
           '<option value="income"' + (it.kind === 'income' ? ' selected' : '') + '>收入</option>' +
           '</select>', it.conf.kind) +
      cell('cat', '<select data-b="cat">' + cats.map(function (c) {
             return '<option value="' + c.id + '"' + (c.id === it.cat ? ' selected' : '') +
               '>' + esc(c.name) + '</option>';
           }).join('') + '</select>', it.conf.cat) +
      cell('merchant', '<input data-b="merchant" type="text" placeholder="選填" value="' +
           esc(it.merchant || '') + '">') +
      '<button class="btbl__del" data-bdel="' + i + '" title="移除這一筆">&#10005;</button>' +
      '</div>';
  }

  /* 把畫面上的值收回 batch，並重算缺漏狀態 */
  function syncBatch() {
    if (!batch) return;
    Array.prototype.forEach.call(document.querySelectorAll('.btbl__r'), function (row) {
      var i = Number(row.dataset.bi);
      if (!batch[i]) return;
      Array.prototype.forEach.call(row.querySelectorAll('[data-b]'), function (inp) {
        var f = inp.dataset.b;
        batch[i][f] = f === 'amount'
          ? (inp.value === '' ? null : Number(inp.value))
          : inp.value;
      });
      var m = [];
      if (batch[i].amount === null || batch[i].amount === '' || isNaN(batch[i].amount)) m.push('amount');
      if (!batch[i].date) m.push('date');
      batch[i].missing = m;
      row.classList.toggle('has-miss', m.length > 0);

      ['amount', 'date'].forEach(function (f) {
        var inp = row.querySelector('[data-b="' + f + '"]');
        if (!inp) return;
        var wrap = inp.parentElement;
        var need = m.indexOf(f) >= 0;
        wrap.classList.toggle('is-miss', need);
        var mark = wrap.querySelector('.bcell__x');
        if (need && !mark) wrap.insertAdjacentHTML('beforeend', '<em class="bcell__x">必填</em>');
        if (!need && mark) mark.remove();
      });
    });
    syncSaveState();
  }

  function syncSaveState() {
    var btn = document.getElementById('paraSave');
    if (!btn || !batch) return;
    var bad = batch.filter(function (x) { return x.missing && x.missing.length; }).length;
    var n = document.getElementById('paraN');
    var lbl = document.getElementById('paraLbl');
    if (n) n.textContent = batch.length;
    if (lbl) lbl.textContent = bad > 0 ? ('還有 ' + bad + ' 筆缺欄位，共') : '確認並寫入';
    btn.disabled = bad > 0 || batch.length === 0;
  }

  /* ============================================================
     單筆手動
     ============================================================ */
  function singleHTML() {
    var cats = global.DATA.categories.filter(function (c) { return c.kind === 'expense'; });
    var today = todayKey();
    return '<div class="card">' +
      '<div class="card__h"><span class="card__t">單筆手動輸入</span>' +
      '<span class="card__s">不經過模型，欄位自己填</span></div>' +
      '<div class="prs__g">' +
        '<div class="prs__f"><label>日期</label><input data-s="date" type="date" value="' + today + '"></div>' +
        '<div class="prs__f"><label>金額</label><input data-s="amount" type="number" placeholder="必填"></div>' +
        '<div class="prs__f"><label>收支</label><select data-s="kind">' +
          '<option value="expense">支出</option><option value="income">收入</option></select></div>' +
        '<div class="prs__f"><label>分類</label><select data-s="cat">' +
          cats.map(function (c) { return '<option value="' + c.id + '">' + esc(c.name) + '</option>'; }).join('') +
          '</select></div>' +
        '<div class="prs__f"><label>店家</label><input data-s="merchant" type="text" placeholder="選填"></div>' +
        '<div class="prs__f"><label>備註</label><input data-s="note" type="text" placeholder="選填"></div>' +
      '</div>' +
      '<div class="prs__a"><button class="btn btn--go" id="singleSave">寫入這一筆</button>' +
      '<button class="btn" id="singleClear">清空</button></div></div>';
  }

  /* 篩選一律用「標題 ＋ 下拉」。
     本來收支方向是三顆並排的按鈕，跟旁邊的下拉長得不一樣，
     而且沒有標題——看得到選項卻不知道那一排在篩什麼。 */
  function filterBar() {
    function sel(key, label, opts) {
      return '<label class="fsel"><span>' + label + '</span>' +
        '<select data-f="' + key + '">' + opts.map(function (o) {
          return '<option value="' + o[0] + '"' +
            (F[key] === o[0] ? ' selected' : '') + '>' + o[1] + '</option>';
        }).join('') + '</select></label>';
    }
    return '<div class="bar bar--inline">' +
      sel('kind', '收支', [['all', '全部'], ['expense', '支出'], ['income', '收入']]) +
      sel('source', '來源', [['all', '全部'], ['nlp', '段落記帳'], ['manual', '手動輸入']]) +
      '</div>';
  }

  function loadTx() {
    var box = document.getElementById('txList');
    if (!box) return;
    API.transactions(Object.assign({}, F, { groupId: GROUP })).then(function (d) {
      box.innerHTML = txTable(d.transactions, null,
        '<div class="card">' + emptyState('沒有符合的紀錄', '換個篩選條件，或記一筆新的。') + '</div>');
    }).catch(function (e) { box.innerHTML = errState(e); });
  }

  /* ============================================================
     03 統計：過去的趨勢

     家長可以切「我／全家」。年度數列只有涵蓋全家每一個人時才算得出來，
     算不出來的時候「按年」直接關掉，不給一份對不上的數字。
     ============================================================ */
  function vStats() {
    head('統計', '');
    $view.innerHTML = '<div class="page">' + skeleton(4) + '</div>';

    API.me().then(function (m) {
      var sc = scopeOf(m);
      return API.summary({ scope: sc, groupId: GROUP }).then(function (d) { render(m, sc, d); });
    }).catch(function (e) { $view.innerHTML = '<div class="page">' + errState(e) + '</div>'; });

    function render(m, sc, d) {
      if (STAT.period === 'year' && !d.yearly) STAT.period = 'month';
      var month = STAT.period === 'month';
      head('統計', sc === 'family' ? '全家的收支' : '', scopeSeg(m));

      var rows = month
        ? (d.monthly || []).map(function (r) { return { k: r.m, label: r.m.slice(5) + ' 月', income: r.income, expense: r.expense }; })
        : (d.yearly || []).map(function (r) { return { k: r.y, label: String(r.y), income: r.income, expense: r.expense, partial: r.partial }; });

      var h = '<div class="page"><div class="sec"><h2 class="sec__t">收支對照</h2>' +
        '<div class="sec__tools">' +
          seg('sp', [['month', '按月'], ['year', '按年']], STAT.period, d.yearly ? null : ['year']) +
        '</div></div>';

      if (month && !d.monthly) {
        h += '<div class="card">' + emptyState('選了單一帳本時看不到趨勢', '切回「全部帳本」就看得到。') + '</div>';
      } else {
        h += '<div class="duo">' +
          '<section class="duo__c"><div class="card card--flush">' +
            '<table class="dt"><thead><tr><th>' + (month ? '月份' : '年度') + '</th>' +
              '<th class="rt">收入</th><th class="rt">支出</th><th class="rt">結餘</th><th>存下</th></tr></thead><tbody>' +
            rows.slice().reverse().map(function (r) {
              var net = r.income - r.expense, rate = r.income ? net / r.income : 0;
              var w = Math.max(0, Math.min(100, rate * 200));
              return '<tr><td><b>' + esc(r.label) + '</b>' +
                  (r.partial ? '<small>還沒過完</small>' : '') + '</td>' +
                '<td class="rt num">' + num(r.income) + '</td>' +
                '<td class="rt num">' + num(r.expense) + '</td>' +
                '<td class="rt num ' + (net >= 0 ? 'is-up' : 'is-down') + '">' + (net >= 0 ? '+' : '−') + num(Math.abs(net)) + '</td>' +
                '<td class="dt__bar"><span class="mbar"><i style="width:' + w + '%;background:' +
                  (rate >= 0.2 ? 'var(--up)' : (rate >= 0 ? 'var(--warn)' : 'var(--down)')) + '"></i></span>' +
                  '<em>' + pct(rate) + '</em></td></tr>';
            }).join('') + '</tbody></table>' +
          '</div></section>' +
          '<section class="duo__c"><div class="card">' +
            '<div class="card__h"><span class="card__t">' + (month ? '近 6 個月' : '近 3 年') + '</span>' +
              '<span class="card__s">收入與支出</span></div>' +
            barChart(rows) +
          '</div></section>' +
        '</div>';
      }

      h += '<div class="sec"><h2 class="sec__t">錢花在哪</h2><span class="sec__n">' + esc(d.period) + '</span></div>' +
        '<div class="card">' + (d.byCat.length ? donut(d.byCat, d.expense) : emptyState('這個月還沒有支出', '')) + '</div>';

      $view.innerHTML = h + '</div>';
    }
  }

  /* ============================================================
     05 AI 財務建議
     ============================================================ */
  /* ============================================================
     財務建議

     原本每一則都整個攤開：標題、內文、依據、建議四段全部展開。
     五六則排下來就是一大片文字，還沒讀就先累了。

     改成一則一行——等級、標題、日期。想看細節才點開。
     ============================================================ */
  var ADV = [];          // 目前這一頁的建議，搜尋時用
  var ADVQ = '';         // 搜尋字串
  var ADVOPEN = null;    // 展開中的那一則

  function vAdvice() {
    head('財務建議', '');
    $view.innerHTML = '<div class="page">' + skeleton(4) + '</div>';
    API.me().then(function (m) {
      var sc = scopeOf(m);
      head('財務建議', sc === 'family' ? '全家的建議，以及你照顧的家人的個人建議' : '', scopeSeg(m));
      return API.advices({ scope: sc }).then(function (d) {
        ADV = d.advices || [];
        $view.innerHTML =
          '<div class="page">' +
            '<div id="advHint"></div>' +
            '<div class="sec"><h2 class="sec__t">' + (sc === 'family' ? '全家的建議' : '給你的建議') + '</h2>' +
              '<span class="sec__n">' + ADV.length + ' 則</span>' +
              '<div class="sec__tools"><label class="fsel fsel--q">' +
                '<input type="search" id="advq" placeholder="搜尋建議" aria-label="搜尋建議" ' +
                  'value="' + esc(ADVQ) + '" autocomplete="off"></label></div></div>' +
            '<div class="card card--flush adl" id="advList"></div>' +
          '</div>';
        paintAdvices();
        if (sc === 'family') return;
        /* 沒填理財習慣的話提一次——這是它真正派得上用場的地方 */
        return API.financeProfile().then(function (p) {
          var f = p.finance || {};
          if (f.style || (f.goals || []).length || (f.habits || []).length || f.note) return;
          var box = document.getElementById('advHint');
          if (box) box.innerHTML = '<a class="nudge" href="#/profile">' +
            '<b>想要更貼近你的建議？</b><span>填一下理財習慣，一分鐘就好 →</span></a>';
        }).catch(function () {});
      });
    }).catch(function (e) { $view.innerHTML = '<div class="page">' + errState(e) + '</div>'; });
  }

  function advLevel(a) {
    return a.level === 'warn' ? '需注意' : (a.level === 'ok' ? '良好' : '參考');
  }

  function paintAdvices() {
    var box = document.getElementById('advList');
    if (!box) return;

    var q = ADVQ.trim().toLowerCase();
    var rows = !q ? ADV : ADV.filter(function (a) {
      var hay = [a.title, a.body, (a.basis || []).join(' '), (a.suggest || []).join(' ')]
        .join(' ').toLowerCase();
      return hay.indexOf(q) >= 0;
    });

    if (!rows.length) {
      box.innerHTML = ADVQ.trim()
        ? emptyState('沒有符合的建議', '換個關鍵字試試。')
        : emptyState('這個月還沒有建議', '記帳的資料多一點，建議就會出現。');
      return;
    }

    box.innerHTML = rows.map(function (a) {
      var open = ADVOPEN === a.id;
      return '<div class="ad' + (open ? ' on' : '') + '">' +
        '<button class="ad__h" data-adv="' + esc(a.id) + '">' +
          '<span class="ad__lv ad__lv--' + esc(a.level) + '">' + advLevel(a) + '</span>' +
          '<span class="ad__t">' + esc(a.title) + '</span>' +
          '<span class="ad__m">' + esc(a.scope === 'family' ? '全家' : a.userName) + '</span>' +
          '<span class="ad__p">' + esc(a.period) + '</span>' +
          '<svg class="ad__cv" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
            'stroke-width="2"><path d="m6 9 6 6 6-6"/></svg>' +
        '</button>' +
        (open ? advBody(a) : '') +
      '</div>';
    }).join('');
  }

  function advBody(a) {
    return '<div class="ad__b">' +
      '<p>' + esc(a.body) + '</p>' +
      '<div class="ad__k">依據</div><ul>' +
        (a.basis || []).map(function (b) { return '<li>' + esc(b) + '</li>'; }).join('') +
      '</ul>' +
      '<div class="ad__k">建議</div><ul>' +
        (a.suggest || []).map(function (b) { return '<li>' + esc(b) + '</li>'; }).join('') +
      '</ul>' +
    '</div>';
  }


  /* ============================================================
     06 成員與權限
     ============================================================ */
  /* ============================================================
     家庭

     還沒有家庭：建立一個（成為家長），或用邀請碼加入；有人邀請就先看到邀請。
     已經有家庭：成員卡片。家長多一個「邀請家人」——
       用帳號邀請   輸入完整 email → 找到人 → 選家長或子女 → 送出
       邀請碼       選身分 → 產生 → 複製給家人

     ⚠️ 身分由家長決定，被邀請的人不能自己選。
     ============================================================ */
  var INV = { role: 'child', codeRole: 'child', found: null };

  function roleTW(r) { return r === 'parent' ? '家長' : '子女'; }

  function shortDate(iso) {
    var d = new Date(iso);
    return (d.getMonth() + 1) + ' 月 ' + d.getDate() + ' 日';
  }

  /* 收到的邀請：一張卡一個，直接按加入或婉拒 */
  function inviteCards(list) {
    return list.map(function (i) {
      return '<div class="card invc">' +
        '<div class="invc__mark" aria-hidden="true">' + esc(String(i.familyName || '家').charAt(0)) + '</div>' +
        '<div class="invc__m">' +
          '<div class="invc__t"><b>' + esc(i.inviterName) + '</b> 邀請你加入「' + esc(i.familyName) + '」</div>' +
          '<div class="invc__s">身分：' + roleTW(i.role) + '　·　' + shortDate(i.expiresAt) + '前有效</div>' +
        '</div>' +
        '<div class="invc__a">' +
          '<button class="btn btn--sm btn--ghost" data-inv-decline="' + esc(i.id) + '">婉拒</button>' +
          '<button class="btn btn--sm btn--go" data-inv-accept="' + esc(i.id) + '">加入</button>' +
        '</div>' +
      '</div>';
    }).join('');
  }

  function vMembers() {
    head('家庭', '');
    $view.innerHTML = '<div class="page">' + skeleton(4) + '</div>';
    Promise.all([API.members(), API.invites()]).then(function (r) {
      var d = r[0], inv = r[1];
      PERMS = d;   // 「誰可以做什麼」要用，見 HELP.perms
      if (!d.family) return renderNoFamily(inv);
      renderFamily(d, inv);
    }).catch(function (e) { $view.innerHTML = '<div class="page">' + errState(e) + '</div>'; });
  }

  function renderNoFamily(inv) {
    head('家庭', '和家人一起記帳');
    var h = '<div class="page">';
    if (inv.received.length) {
      h += '<div class="sec"><h2 class="sec__t">收到的邀請</h2><span class="sec__n">' + inv.received.length + '</span></div>' +
        inviteCards(inv.received);
    }
    h += '<div class="duo' + (inv.received.length ? '' : ' duo--first') + '">' +
      '<section class="duo__c"><div class="card fam0">' +
        '<div class="fam0__ic" aria-hidden="true">＋</div>' +
        '<h3 class="fam0__t">建立我的家庭</h3>' +
        '<p class="fam0__s">建立的人會是家長，之後可以邀請家人加入。</p>' +
        '<form class="fam0__f" id="famNewF">' +
          '<input type="text" id="famName" maxlength="20" placeholder="例如 林家" aria-label="家庭名稱" required>' +
          '<button class="btn btn--go" type="submit">建立</button>' +
        '</form>' +
      '</div></section>' +
      '<section class="duo__c"><div class="card fam0">' +
        '<div class="fam0__ic fam0__ic--key" aria-hidden="true">#</div>' +
        '<h3 class="fam0__t">用邀請碼加入</h3>' +
        '<p class="fam0__s">輸入家人傳給你的 8 碼邀請碼。</p>' +
        '<form class="fam0__f" id="famJoinF">' +
          '<input type="text" id="famCode" class="codein" maxlength="9" placeholder="K7QM-3XWP" ' +
            'autocomplete="off" autocapitalize="characters" spellcheck="false" aria-label="邀請碼" required>' +
          '<button class="btn btn--go" type="submit">加入</button>' +
        '</form>' +
      '</div></section>' +
    '</div></div>';
    $view.innerHTML = h;
  }

  function renderFamily(d, inv) {
    var parent = d.myRole === 'parent';
    head('家庭成員', d.family.name + '　·　' + d.members.length + ' 位');

    function names(list, key) {
      return list.map(function (g) { return esc(g[key]); }).join('、');
    }

    var tools = '<button class="btn btn--sm btn--ghost" data-help="perms">誰可以做什麼</button>';
    /* 子女沒有邀請的功能，標題列就不放「邀請家人」 */
    var h = '<div class="page">' + (parent
      ? foldHead('finv', d.family.name, '邀請家人', d.members.length + ' 人', null, tools)
      : '<div class="sec"><h2 class="sec__t">' + esc(d.family.name) + '</h2>' +
        '<span class="sec__n">' + d.members.length + ' 人</span><div class="sec__tools">' + tools + '</div></div>');

    if (parent && inv.sent.length) {
      h += '<div class="card card--flush pend">' +
        '<div class="card__h"><span class="card__t">等待回覆</span><span class="card__s">' + inv.sent.length + ' 個邀請</span></div>' +
        inv.sent.map(function (i) {
          return '<div class="pend__i">' + ava({ name: i.name, avatar: i.avatar }, 'ava--sm') +
            '<div class="pend__m"><b>' + esc(i.name) + '</b><small>' + esc(i.email) + '</small></div>' +
            '<span class="pill pill--near">' + roleTW(i.role) + '</span>' +
            '<button class="btn btn--sm btn--ghost" data-inv-cancel="' + esc(i.id) + '">取消</button>' +
          '</div>';
        }).join('') + '</div>';
    }

    h += '<div class="mtiles">' + d.members.map(function (u, i) {
      var full = (d.visible || []).indexOf(u.id) >= 0;
      /* ⚠️ 只有共用帳本的人也點得進去（只看得到共用帳本那部分）。
         以前這裡只看 visible，於是陳淑芬那張卡沒有「看紀錄」，
         看起來像完全不能看，其實共用帳本裡的紀錄都看得到。 */
      var shared = !full && (d.queryable || []).indexOf(u.id) >= 0;
      var go = full || shared;
      var wards = d.guardianships.filter(function (g) { return g.guardian === u.id; });
      var by = d.guardianships.filter(function (g) { return g.ward === u.id; });
      return '<article class="mt' + (go ? ' mt--go' : '') + '"' +
        (go ? ' data-open="' + esc(u.id) + '" title="看 ' + esc(u.name) + ' 的紀錄"' : '') +
        ' style="animation-delay:' + (i * 60) + 'ms">' +
        (u.id === d.me ? '<span class="mt__me">你</span>' : '') +
        ava(u, 'ava--lg') +
        '<div class="mt__n">' + esc(u.name) + '</div>' +
        '<div class="mt__r">' + esc(ROLE_TW[u.role] || '') + '</div>' +
        '<div class="mt__rel">' +
          (wards.length ? '<span>照看 ' + names(wards, 'wardName') + '</span>' : '') +
          (by.length ? '<span>由 ' + names(by, 'guardianName') + ' 照看</span>' : '') +
        '</div>' +
        (u.id === d.me ? '' : full ? '<span class="mt__go">看紀錄</span>'
          : shared ? '<span class="mt__go mt__go--part">看共用帳本</span>' : '') +
        /* 家長可以把子女移出；另一位家長只能自己退出，所以家長的卡片沒有這顆 */
        (parent && u.role === 'child' && u.id !== d.me
          ? '<button class="mt__x" data-member-remove="' + esc(u.id) + '" data-name="' + esc(u.name) + '">移出家庭</button>'
          : '') +
      '</article>';
    }).join('') + '</div>' +

    /* 退出家庭：放在最下面、安靜一點。任何人都可以退出 */
    '<div class="card leave">' +
      '<div class="leave__m"><b>退出「' + esc(d.family.name) + '」</b>' +
        '<small>你的紀錄會留著；退出後你跟家人之間就互相看不到了。</small></div>' +
      '<button class="btn btn--sm btn--danger" data-family-leave data-name="' + esc(d.family.name) + '">退出家庭</button>' +
    '</div></div>';

    $view.innerHTML = h;
    foldRestore();
  }

  /* 邀請家人的面板：展開的時候才畫 */
  FOLD_BUILD.finv = function (wrap) {
    wrap.innerHTML = '<div class="duo duo--tight">' +
      '<section class="duo__c"><div class="card invp">' +
        '<div class="invp__h"><span class="invp__n">1</span><b>用帳號邀請</b></div>' +
        '<form class="invp__f" id="invFindF">' +
          '<input type="email" id="invEmail" placeholder="輸入家人的完整 email" autocomplete="off" aria-label="家人的 email" required>' +
          '<button class="btn btn--sm" type="submit">找人</button>' +
        '</form>' +
        '<div id="invFound" class="invp__r"><p class="invp__hint">只接受完整的 email，找到之後再選身分。</p></div>' +
      '</div></section>' +
      '<section class="duo__c"><div class="card invp">' +
        '<div class="invp__h"><span class="invp__n">2</span><b>或是給他邀請碼</b></div>' +
        '<div class="invp__row"><span class="invp__k">身分</span>' +
          seg('codrole', [['child', '子女'], ['parent', '家長']], INV.codeRole) +
          '<button class="btn btn--sm btn--go" data-code-new>產生邀請碼</button></div>' +
        '<div id="invCodes"></div>' +
      '</div></section>' +
    '</div>';
    paintCodes();
  };

  function paintCodes() {
    var box = document.getElementById('invCodes');
    if (!box) return;
    API.invites().then(function (inv) {
      box.innerHTML = inv.codes.length
        ? inv.codes.map(function (c) {
            return '<div class="code">' +
              '<div class="code__v" aria-label="邀請碼">' + esc(c.code) + '</div>' +
              '<div class="code__m">' + roleTW(c.role) + '　·　' + shortDate(c.expiresAt) + '前有效　·　只能用一次</div>' +
              '<button class="btn btn--sm" data-copy="' + esc(c.code) + '">複製</button>' +
            '</div>';
          }).join('')
        : '<p class="invp__hint">產生之後傳給家人，他在「家庭」頁輸入就能加入。</p>';
    });
  }

  function paintFound(r) {
    var box = document.getElementById('invFound');
    if (!box) return;
    INV.found = r && r.user ? r.user : null;
    if (!r || !r.user) { box.innerHTML = '<p class="invp__hint">' + esc(r && r.msg || '找不到這個帳號') + '</p>'; return; }
    var st = {
      member: '已經是你的家人了',
      invited: '已經邀請過了，等對方回覆就好',
      unavailable: '這個帳號目前不能邀請'
    }[r.status];
    box.innerHTML = '<div class="found">' + ava(r.user, 'ava--md') +
      '<div class="found__m"><b>' + esc(r.user.name) + '</b>' + (st ? '<small>' + st + '</small>' : '') + '</div>' +
      (r.status === 'available'
        ? '<div class="found__a">' + seg('invrole', [['child', '子女'], ['parent', '家長']], INV.role) +
            '<button class="btn btn--sm btn--go" data-inv-send="' + esc(r.user.id) + '">送出邀請</button></div>'
        : '') +
    '</div>';
  }

  /* 加入或建立家庭之後，身分變了：帳號選單、帳本清單、目前這一頁都要重畫 */
  function afterFamilyChange(msg) {
    ME = null;
    FOLD.finv = false;
    paintWho(); paintGroups(); paint();
    toast(msg, 'ok');
  }

  /* ============================================================
     單一成員的記帳紀錄（唯讀）

     從兩個地方進來：
       成員與權限點某一列       → #/member/U3
       通知點某一則             → #/member/U3/T1051（那一筆會標起來）
     ============================================================ */
  function vMember(id, hit) {
    head('成員紀錄', '');
    $view.innerHTML = '<div class="page">' + skeleton(4) + '</div>';

    /* 先問「我看不看得到」，確認之後才去拿明細。
       沒權限就不要發那個請求——後端會回 403，前端也不該去撞。 */
    Promise.all([API.me(), API.members(), API.allowances().catch(function () {
      return { allowances: [] };
    })])
      .then(function (r) {
        var me = r[0], d = r[1], al = r[2];
        var u = d.members.filter(function (x) { return x.id === id; })[0];

        if (!u) {
          $view.innerHTML = '<div class="page">' + backLink() + '<div class="card">' +
            emptyState('找不到這個人', '他可能已經不在這個家庭裡了。') + '</div></div>';
          return;
        }

        /* 看得到誰是後端說了算（me.visible）。
           前端這裡擋一次是為了給一句人話，並且不要去發一個註定被拒絕的請求。
           真正的把關在 API：帶了沒權限的 userId 會回 403（不是空陣列——
           回空的話，前端分不出「這個人沒記帳」和「你不能看」）。 */
        /* 兩種看得到的方式，能看到的範圍不一樣，要講清楚是哪一種：
             監管    → 這個人的全部紀錄，跨所有帳本
             同帳本  → 只有你們共用的那幾本裡的紀錄 */
        var supervised = (me.visible || []).indexOf(id) >= 0;
        var shared = (me.queryable || []).indexOf(id) >= 0;

        if (!supervised && !shared) {
          $view.innerHTML = '<div class="page">' + backLink() + '<div class="card">' +
            emptyState('看不到' + u.name + '的紀錄', '你們沒有監管關係，也沒有共用的帳本。') + '</div></div>';
          return;
        }
        var partial = !supervised;

        var a = (al.allowances || []).filter(function (x) { return x.wardId === id; })[0];
        u.allowance = a ? a.amount : 0;
        return API.transactions({ userId: id }).then(function (tx) {
          render(me, d, u, tx, partial);
        });
      })
      .catch(function (e) {
        $view.innerHTML = '<div class="page">' + errState(e) + '</div>';
      });

    function render(me, d, u, tx, partial) {
      var mine = id === d.me;
      head(mine ? '我的紀錄' : callName(u.name) + '的紀錄', '');

      var h = '<div class="page">' + backLink();
      h += '<div class="duo">' +
        '<section class="duo__c"><div class="card pcard">' +
          ava(u, 'ava--xl') +
          '<div class="pcard__m"><div class="pcard__n">' + esc(u.name) + '</div>' +
            '<div class="pcard__r">' + esc(ROLE_TW[u.role] || '') + (mine ? '　·　你自己' : '') + '</div>' +
            (partial ? '<div class="pcard__h">只看得到你們共用帳本裡的紀錄</div>' : '') +
          '</div>' +
          '<div class="pcard__stat"><b>' + tx.total + '</b><span>筆紀錄</span></div>' +
        '</div></section>' +
        /* 零用金只有**監管他的人**看得到——那是監管者對他的設定，不是一筆支出。
           ⚠️ 不能用「看得到全部紀錄」判斷：家長之間也看得到全部，但不會給對方零用金。 */
        (!mine && d.guardianships.some(function (g) { return g.guardian === d.me && g.ward === id; })
          ? '<section class="duo__c"><div class="card allow">' +
              '<div class="allow__k">每個月給' + esc(callName(u.name)) + '的零用金' + helpBtn('allowance') + '</div>' +
              '<label class="money"><i>NT$</i><input type="number" min="0" inputmode="numeric" ' +
                'data-allow="' + esc(u.id) + '" value="' + (u.allowance || 0) + '" aria-label="每月零用金"></label>' +
              '<div class="allow__h">改完離開欄位就會存好</div>' +
            '</div></section>'
          : '') +
      '</div>';

      h += '<div class="sec"><h2 class="sec__t">收支明細</h2><span class="sec__n">' + tx.total + ' 筆</span></div>';
      h += '<div id="mtx">' + txTable(tx.transactions, hit,
        '<div class="card">' + emptyState('還沒有紀錄', '這個月還沒記過帳。') + '</div>') + '</div></div>';

      $view.innerHTML = h;

      // 從通知點進來的那一筆捲進畫面，不然在長清單裡要自己找
      var el = document.querySelector('.txr.is-hit');
      if (el) setTimeout(function () {
        el.scrollIntoView({ block: 'center', behavior: 'smooth' });
      }, 120);
    }
  }

  function backLink() {
    return '<a class="back" href="#/members">← 家庭成員</a>';
  }


  /* ============================================================
     帳本

     記帳除了有「分類」，還有「這筆算在哪一本帳上」。
     分類回答錢花在什麼，帳本回答這筆屬於哪一份預算。
     每一本帳可以各自設一個每月存款目標。
     ============================================================ */
  function vGroups() {
    head('帳本', '家用、旅遊、自己的零用，分開記');
    $view.innerHTML = '<div class="page">' + skeleton(4) + '</div>';

    Promise.all([API.groups({ includeArchived: true }), API.members()])
      .then(function (r) {
      var d = r[0], fam = r[1];

      /* 展開的時候要用到，先記下來——點開一本帳不用再打一次 API */
      LG.fam = fam;
      LG.byId = {};
      d.groups.forEach(function (g) { LG.byId[g.id] = g; });

      var live = d.groups.filter(function (g) { return !g.archived; });
      var gone = d.groups.filter(function (g) { return g.archived; });

      /* 常設／活動分成兩區，不是兩個分頁。
         分頁會把一半藏起來——只有一本活動帳的時候，為它開一個分頁太重，
         手機上多一層隱藏狀態也跟「看得到現在在哪一本」相反。
         區塊則是全部看得到、只是分群；沒有活動帳本時整個區塊不出現。 */
      var standing = live.filter(function (g) { return g.kind !== 'temp'; });
      var temps = live.filter(function (g) { return g.kind === 'temp' && !g.settled; });
      var done = live.filter(function (g) { return g.kind === 'temp' && g.settled; });

      /* 開一本新的：跟「記一筆」同一個做法，縮成標題右邊的按鈕 */
      var gnewForm =
        '<form class="card gnew" id="gnewF">' +
          '<label class="fld fld--wide"><span>名字</span>' +
            '<input type="text" id="gnName" placeholder="例如 旅遊基金、沖繩旅遊" required></label>' +
          '<label class="fld"><span>種類</span>' +
            '<select id="gnKind">' +
              '<option value="standing">常設</option>' +
              '<option value="temp">活動（有結束日）</option>' +
            '</select></label>' +
          '<label class="fld"><span>顏色</span>' +
            /* ⚠️ 顏色從 DATA.groupColors 來，不要再寫死一份 */
            '<select id="gnColor">' +
              ((global.DATA && global.DATA.groupColors) || []).map(function (c) {
                return '<option value="' + esc(c.id) + '">' + esc(c.name) + '</option>';
              }).join('') +
            '</select></label>' +
          /* 只有活動帳本要填結束日 */
          '<label class="fld" id="gnEndWrap" hidden><span>結束日</span>' +
            '<input type="date" id="gnEnd"></label>' +
          '<div class="form__act"><button class="btn btn--go btn--sm" type="submit">建立</button></div>' +
        '</form>';

      var archHTML = '<div class="card card--flush"><ul class="arch">' + gone.map(function (g) {
        return '<li class="arch__i">' +
          '<span class="gsw__d" style="background:' + tint(g.color) + '"></span>' +
          '<span class="arch__n">' + esc(g.name) + '</span>' +
          '<span class="arch__c">' + g.count + ' 筆</span>' +
          (g.canEdit ? '<button class="btn btn--sm" data-grestore="' + esc(g.id) + '">復原</button>' : '') +
        '</li>';
      }).join('') + '</ul></div>';

      var h = '<div class="page"><div class="duo">' +
        '<section class="duo__c">' +
          foldBlock('gnew', '常設帳本', '開一本', gnewForm, standing.length + ' 本', 'books') +
          ledgerList(standing) +
          (gone.length ? foldBlock('garch', '已封存', '看看', archHTML, String(gone.length) + ' 本', 'archive') : '') +
        '</section>' +
        '<section class="duo__c">' +
          '<div class="sec"><h2 class="sec__t">活動帳本</h2><span class="sec__n">' + temps.length + ' 本</span></div>' +
          (temps.length
            ? ledgerList(temps)
            : '<div class="card">' + emptyState('沒有進行中的活動', '出國、搬家這種有結束日的花費，開一本活動帳本來記。') + '</div>') +
          (done.length ? foldBlock('gdone', '已結算', '看看', ledgerList(done), String(done.length) + ' 本') : '') +
        '</section>' +
      '</div>';

      $view.innerHTML = h + '</div>';
      /* ⚠️ 重畫之後一定要叫它——不然使用者展開表單、按了建立，
         畫面重畫完就無聲收合，看起來像沒有反應。 */
      foldRestore();
    }).catch(function (e) { $view.innerHTML = '<div class="page">' + errState(e) + '</div>'; });
  }


  /* ============================================================
     帳本清單：收合列

     跟財務建議同一個做法——一本帳平常只佔一行：
       顏色 · 名稱 · 狀態 · 成員 · 筆數
     點開才出現成員、月目標、通知、結算／封存。

     ⚠️ 原本一本帳就是一張 150px 高的卡：月目標輸入框、三顆按鈕、
     通知勾選全部攤開，三本帳就佔掉一整個螢幕，而且那些東西
     每天根本不會動。真正每天要看的只有「有哪幾本、各記了多少」。

     ⚠️ 成員管理也在這裡。以前另外有一個「誰在哪一本帳裡」區塊，
     同一本帳的資訊被拆成上下兩處，要對著名字找。
     ============================================================ */
  var LG = { open: null, fam: null, byId: {} };

  function ledgerList(list) {
    return '<div class="lgl">' + list.map(ledgerRow).join('') + '</div>';
  }

  function ledgerRow(g) {
    var open = LG.open === g.id;
    return '<div class="lg' + (open ? ' on' : '') + '" data-lgid="' + esc(g.id) + '">' +
      '<button class="lg__h" data-lg="' + esc(g.id) + '" aria-expanded="' + open + '">' +
        /* ⚠️ 帳本沒有圖示方塊。名字已經說清楚是哪一本了；
           顏色只用一個小方點，跟切換器上的一樣。 */
        '<span class="gsw__d lg__dot" style="background:' + tint(g.color) + '"></span>' +
        '<span class="lg__t">' + esc(g.name) + '</span>' +
        '<span class="lg__tags">' +
          (g.kind === 'temp' && g.endsOn && !g.settled
            ? '<span class="tag tag--MEDIUM">到 ' + esc(g.endsOn.slice(5).replace('-', '/')) + '</span>' : '') +
          (g.overdue ? '<span class="tag tag--down">已到期</span>' : '') +
          (g.settled ? '<span class="tag tag--soft">已結算</span>' : '') +
          (g.id === GROUP ? '<span class="tag tag--done">目前在看</span>' : '') +
        '</span>' +
        '<span class="lg__m">' + esc(g.memberNames.join('、')) + '</span>' +
        '<span class="lg__c">' + g.count + ' 筆</span>' +
        '<svg class="lg__cv" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
          'stroke-width="2" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>' +
      '</button>' +
      (open ? ledgerBody(g) : '') +
    '</div>';
  }

  function ledgerBody(g) {
    var fam = LG.fam || { members: [] };
    var byId = {};
    fam.members.forEach(function (m) { byId[m.id] = m; });

    /* 結算之後唯讀：不能再加減人。改成員等於改「誰看得到這本帳」，
       結算過的帳不該在事後被改掉這件事。 */
    var editable = g.canEdit && !g.settled;
    var outside = editable
      ? fam.members.filter(function (m) { return g.members.indexOf(m.id) < 0; })
      : [];

    var who = g.members.map(function (u) {
      var m = byId[u] || {};
      var owner = u === g.owner;
      return '<span class="chip' + (owner ? ' chip--own' : '') + '">' + esc(m.name || u) +
        (owner ? '<i>開帳本的人</i>' : '') +
        (editable && !owner
          ? '<button data-gdel="' + esc(g.id) + '|' + esc(u) + '" title="移出這本帳" ' +
            'aria-label="把' + esc(m.name || u) + '移出這本帳">×</button>'
          : '') +
        '</span>';
    }).join('');

    var add = outside.length
      ? '<select class="lg__add" data-gaddsel="' + esc(g.id) + '" aria-label="把家人加進這本帳">' +
          '<option value="">＋ 加人</option>' +
          outside.map(function (m) {
            return '<option value="' + esc(m.id) + '">' + esc(m.name) + '</option>';
          }).join('') +
        '</select>'
      : '';

    return '<div class="lg__b">' +
      (g.note ? '<p class="lg__note">' + esc(g.note) + '</p>' : '') +
      '<dl class="lg__f">' +
        '<dt>成員</dt><dd><div class="lg__who">' + who + add + '</div>' +
          (g.canEdit ? '' : '<div class="lg__hint">只有開這本帳的人可以加減成員</div>') + '</dd>' +
        '<dt>月目標</dt><dd>' +
          '<input class="goal__i" type="number" min="0" data-ggoal="' + esc(g.id) + '" ' +
            'value="' + (g.goal || 0) + '" aria-label="這本帳的每月存款目標"></dd>' +
        '<dt>通知</dt><dd>' +
          '<label class="lg__chk"><input type="checkbox" data-gnotify="' + esc(g.id) + '"' +
            (g.notify ? ' checked' : '') + '><span>這本帳有動靜就通知我</span></label></dd>' +
      '</dl>' +
      '<div class="lg__acts">' +
        '<button class="btn btn--sm" data-gopen="' + esc(g.id) + '">看這本的 ' + g.count + ' 筆紀錄 →</button>' +
        '<span class="lg__sp"></span>' +
        (g.kind === 'temp' && !g.settled && g.canEdit
          ? '<button class="gx gx--go" data-gsettle="' + esc(g.id) + '">結算</button>' : '') +
        (g.canEdit && !g.settled
          ? '<button class="gx" data-garch="' + esc(g.id) +
            '" title="收起這本帳。紀錄不會被刪掉，之後可以復原">封存</button>' : '') +
      '</div>' +
    '</div>';
  }

  /* 點一本打開、再點收起；一次只開一本，跟財務建議一樣。
     只換那兩列，不重打 API，也不重畫整頁。 */
  function ledgerToggle(id) {
    var prev = LG.open;
    LG.open = (prev === id) ? null : id;

    function rowOf(gid) { return document.querySelector('.lg[data-lgid="' + gid + '"]'); }
    function mark(node, on) {
      node.classList.toggle('on', on);
      var h = node.querySelector('.lg__h');
      if (h) h.setAttribute('aria-expanded', on ? 'true' : 'false');
    }

    // 收起原本開著的那一本：先播完往上收，再從 DOM 拿掉
    if (prev) {
      var pn = rowOf(prev);
      if (pn) { mark(pn, false); slideAway(pn.querySelector('.lg__b')); }
    }
    // 打開新的那一本
    if (LG.open && LG.byId[LG.open]) {
      var nn = rowOf(LG.open);
      if (nn) {
        mark(nn, true);
        nn.insertAdjacentHTML('beforeend', ledgerBody(LG.byId[LG.open]));
        slideOpen(nn.lastElementChild);
      }
    }
  }


  /* ============================================================
     說明彈窗

     介面上不放長篇解釋——需要解釋的地方，標題旁邊放一個問號，
     想知道的人自己點。點開時背景模糊並且鎖住，
     讓注意力只剩下這段說明。

     每一則都用「使用者聽得懂的話」寫，不寫系統怎麼實作。
     ============================================================ */
  var HELP = {
    limit: {
      t: '還可以花是怎麼算的',
      b: '<p class="hp__f">本月收入 − 每月想存的 ＝ 這個月可以花的</p>' +
         '<p>例如收入 68,000、想存 20,000，這個月就可以花 48,000。</p>'
    },
    goal: {
      t: '每月存款目標',
      b: '<p>每個月想存多少，<b>只有你自己能設定</b>。</p>' +
         '<p>隨時可以改，改了只影響這個月和以後的月份。</p>'
    },
    entry: {
      t: '一句話就能記好幾筆',
      b: '<p>直接把今天花了什麼打成一段話，例如：</p>' +
         '<p class="hp__f">早上買早餐 55，中午跟同事吃飯 320，' +
         '下午在全家買咖啡，晚上加油 1200</p>' +
         '<p>系統會把它拆成一筆一筆，填好金額和分類讓你確認。' +
         '<b>確認之前不會存進去</b>，看到不對的地方直接改。</p>' +
         '<p>有時候會拆錯或猜錯分類——那很正常，改掉就好。' +
         '你改過的地方會讓它下次更準。</p>'
    },
    watch: {
      t: '誰看得到我的紀錄',
      b: '<p>預設只有你自己。</p>' +
         '<p>家長建立監管關係後可以看你的紀錄，但不能修改、刪除，也不能登入你的帳號。' +
         '這些關係在「成員與權限」都看得到。</p>'
    },
    books: {
      t: '帳本是什麼',
      b: '<p>把不同用途的錢分開記，例如「家用」「旅遊基金」。</p>' +
         '<p>右上角切換帳本之後，數字都只看那一本。</p>'
    },
    archive: {
      t: '封存',
      b: '<p>把用不到的帳本收起來。<b>紀錄一筆都不會刪</b>，隨時可以復原。</p>'
    },
    alerts: {
      t: '花到幾成提醒我',
      b: '<p>例如設 80%，花到可以花的額度八成時就通知你。</p>' +
         '<p>同一個提醒一個月只響一次，下個月重新開始。</p>'
    },
    budget: {
      t: '預算',
      b: '<p>替某一個分類設每月上限，例如餐飲不超過 8,000。</p>'
    },
    advice: {
      t: '建議是怎麼來的',
      b: '<p>系統先把數字算好，再請模型用白話說出來。每一則底下都附著依據的算式。</p>'
    },
    perms: {
      t: '誰可以做什麼',
      build: function () {
        if (!PERMS) return '<p>資料還在載入。</p>';
        function cell(v) {
          if (v === 'Y') return '<td>可以</td>';
          if (v === 'N') return '<td style="color:var(--ink-dim)">不可以</td>';
          return '<td>' + esc(v) + '</td>';
        }
        return '<div class="hp__t"><table><thead><tr><th>　</th>' +
          '<th>家長</th><th>子女</th></tr></thead><tbody>' +
          PERMS.permissions.map(function (p) {
            return '<tr><td>' + esc(p.action) + '</td>' +
              cell(p.parent) + cell(p.child) + '</tr>';
          }).join('') + '</tbody></table></div>';
      }
    },
    allowance: {
      t: '每月零用金',
      b: '<p>每個月給家人多少零用金。<b>這是設定，不是一筆支出。</b></p>' +
         '<p>不用另外記一筆「給小孩 3000」，不然他花掉時同一筆錢會被算兩次。</p>'
    },
    avatar: {
      t: '大頭貼',
      b: '<p>選一張圖就好，系統會自動裁成正方形並縮小，' +
         '不用先處理。</p>' +
         '<p>沒有上傳的話，會用你名字的最後一個字當頭像。</p>'
    }
  };

  function helpBtn(key) {
    var h = HELP[key];
    if (!h) return '';
    return '<button class="q" data-help="' + key + '" ' +
      'aria-label="關於「' + esc(h.t) + '」的說明" title="這是什麼？">?</button>';
  }

  var helpOpen = false;
  var PERMS = null;   // 成員頁載入後放這裡，給權限矩陣的問號用

  function openHelp(key) {
    var h = HELP[key];
    if (!h || helpOpen) return;
    // 有些說明的內容要現算（例如權限矩陣要讀目前的成員資料）
    if (h.build) h = { t: h.t, b: h.build() };
    helpOpen = true;

    var wrap = el('<div class="hp" id="hp">' +
      '<div class="hp__c" role="dialog" aria-modal="true" aria-label="' + esc(h.t) + '">' +
        '<div class="hp__h"><h3>' + esc(h.t) + '</h3>' +
          '<button class="hp__x" id="hpX" aria-label="關閉">✕</button></div>' +
        '<div class="hp__b">' + h.b + '</div>' +
        '<div class="hp__d"><button class="btn btn--go" id="hpOk">知道了</button></div>' +
      '</div></div>');

    document.body.appendChild(wrap);
    // 背景鎖住：關掉捲動，內容不可點（.hp 蓋住整頁並吃掉事件）
    document.body.classList.add('hp-on');
    requestAnimationFrame(function () { wrap.classList.add('on'); });
    var x = document.getElementById('hpX');
    if (x) x.focus();
  }

  function closeHelp() {
    var w = document.getElementById('hp');
    if (!w) return;
    helpOpen = false;
    w.classList.remove('on');
    document.body.classList.remove('hp-on');
    setTimeout(function () { w.remove(); }, 200);
  }


  /* ============================================================
     重大操作的確認

     兩種強度：
       'password'  只要密碼。用在「刪一筆紀錄」這種救不回來但範圍小的。
       'full'      密碼 ＋ 一段 64 碼。用在影響很大的，例如把人移出帳本
                   （他會失去那本帳所有紀錄的存取，包含自己記的）。

     那段 64 碼**故意不給複製按鈕**。要使用者自己用滑鼠圈起來複製，
     這個動作本身就是一道減速帶——手滑點下去的人不會剛好完成它。
     ============================================================ */
  var dangerOn = false;
  var dangerFn = null;
  var dangerCode = '';

  function randomCode() {
    var hex = '0123456789abcdef', out = '';
    var buf = new Uint8Array(64);
    if (global.crypto && global.crypto.getRandomValues) global.crypto.getRandomValues(buf);
    else for (var i = 0; i < 64; i++) buf[i] = Math.floor(Math.random() * 256);
    for (var j = 0; j < 64; j++) out += hex[buf[j] % 16];
    return out;
  }

  function danger(opt) {
    if (dangerOn) return;
    dangerOn = true;
    dangerFn = opt.onOk;
    dangerCode = opt.level === 'full' ? randomCode() : '';

    var w = el('<div class="hp dg" id="dg">' +
      '<div class="hp__c" role="dialog" aria-modal="true">' +
        '<div class="hp__h"><h3>' + esc(opt.title) + '</h3>' +
          '<button class="hp__x" id="dgX" aria-label="取消">✕</button></div>' +
        '<div class="hp__b">' +
          '<p class="dg__w">' + opt.detail + '</p>' +
          '<label class="fld"><span>輸入密碼</span>' +
            '<input type="password" id="dgPw" autocomplete="current-password"></label>' +
          /* 有些動作要留下理由。⚠️ 不是為了流程好看——
             沒有理由的停權就是任意封鎖，被停的人也沒有東西可以申訴。
             理由會跟著寫進稽核紀錄。 */
          (opt.reason
            ? '<label class="fld"><span>' + esc(opt.reason) + '</span>' +
                '<input type="text" id="dgReason" autocomplete="off" maxlength="80"></label>'
            : '') +
          (dangerCode
            ? '<div class="dg__code"><span>把下面這段複製貼到欄位裡</span>' +
                '<b id="dgSrc">' + dangerCode + '</b></div>' +
              '<label class="fld"><span>貼在這裡</span>' +
                '<input type="text" id="dgCode" autocomplete="off" spellcheck="false"></label>'
            : '') +
          '<p class="dg__err" id="dgErr" hidden></p>' +
        '</div>' +
        '<div class="hp__d">' +
          '<button class="btn" id="dgNo">取消</button>' +
          '<button class="btn btn--danger" id="dgYes">' + esc(opt.ok || '確定刪除') + '</button>' +
        '</div>' +
      '</div></div>');

    document.body.appendChild(w);
    document.body.classList.add('hp-on');
    requestAnimationFrame(function () { w.classList.add('on'); });
    var p = document.getElementById('dgPw');
    if (p) p.focus();
  }

  function dangerClose() {
    var w = document.getElementById('dg');
    if (!w) return;
    dangerOn = false;
    dangerFn = null;
    w.classList.remove('on');
    document.body.classList.remove('hp-on');
    setTimeout(function () { w.remove(); }, 200);
  }

  function dangerErr(msg) {
    var e = document.getElementById('dgErr');
    if (!e) return;
    e.textContent = msg;
    e.hidden = false;
    var c = document.querySelector('#dg .hp__c');
    if (c) { c.style.animation = 'nudge .3s'; setTimeout(function () { c.style.animation = ''; }, 320); }
  }

  function dangerGo() {
    var pw = (document.getElementById('dgPw') || {}).value || '';
    if (!pw) { dangerErr('請先輸入密碼'); return; }

    var reasonEl = document.getElementById('dgReason');
    var reason = reasonEl ? reasonEl.value.trim() : null;
    if (reasonEl && reason.length < 4) {
      dangerErr('請寫一下理由，這會留在稽核紀錄裡');
      return;
    }

    if (dangerCode) {
      var typed = ((document.getElementById('dgCode') || {}).value || '').trim();
      if (typed !== dangerCode) { dangerErr('那段代碼跟上面不一樣'); return; }
    }

    var btn = document.getElementById('dgYes');
    if (btn) { btn.disabled = true; btn.textContent = '確認中…'; }

    API.verifyPassword(pw).then(function () {
      var fn = dangerFn;
      dangerClose();
      if (fn) fn(reason);
    }).catch(function (err) {
      if (btn) { btn.disabled = false; btn.textContent = '確定刪除'; }
      dangerErr(err.message || '密碼不正確');
    });
  }


  /* ============================================================
     新手導覽

     第一次打開時先問一句「要不要帶你走一遍」，願意的人才走。
     不強迫、隨時可以跳過，跳過之後不會再問。

     每一步用一個方框把目標圈起來（其餘變暗），旁邊放一句話。
     說明只講「這裡能做什麼」，不解釋系統怎麼實作。
     ============================================================ */
  var TOUR_KEY = 'fambudget.tour';
  var TOUR = [
    { sel: '.dtile--add', hash: '#/',
      t: '從這裡記帳',
      b: '打一段話就好，例如「早餐55 中午吃飯320」，系統會幫你拆成一筆一筆。' },
    { sel: '.wal__card', hash: '#/',
      t: '這個月還能花多少',
      b: '收入扣掉你想存的，剩下的就是能放心花的錢。' },
    { sel: '#gswBtn', hash: '#/',
      t: '切換帳本',
      b: '家用、旅遊基金可以分開記。切過去之後，數字都只看那一本。' },
    { sel: '#bell', hash: '#/',
      t: '通知',
      b: '家人記帳、或是你花到設定的比例時，這裡會亮。' },
    { sel: '#acctBtn', hash: '#/',
      t: '你的帳戶卡',
      b: '點頭貼看這個月記了幾天、快速換主題；點名字進個人資料。' }
  ];
    var tourAt = -1;

  function clamp(v, lo, hi) {
    if (hi < lo) return lo;                   // 空間比框還小：貼著上緣就好
    return Math.max(lo, Math.min(v, hi));
  }

  function tourDone() {
    try { return localStorage.getItem(TOUR_KEY) === 'done'; } catch (e) { return true; }
  }
  function tourRemember() {
    try { localStorage.setItem(TOUR_KEY, 'done'); } catch (e) {}
  }

  function tourAsk() {
    if (tourDone()) return;
    /* ⚠️ 導覽的每一步都指向財務功能（記帳、帳本、通知），
       平台管理員的首頁上一個都沒有——框會圈在看不見的元素上。 */
    API.me().then(function (m) {
      if (m.user.isPlatformAdmin || tourDone() || document.getElementById('tourAsk')) return;
      tourAskShow();
    });
  }

  function tourAskShow() {
    var w = el('<div class="hp tw2 on" id="tourAsk">' +
      '<div class="hp__c" role="dialog" aria-modal="true">' +
        '<div class="hp__b" style="padding-top:26px">' +
          '<h3 style="font-size:19px;margin-bottom:10px">第一次用？</h3>' +
          '<p>花一分鐘帶你走一遍，看完就知道東西都在哪裡。</p>' +
        '</div>' +
        '<div class="hp__d" style="justify-content:center;gap:10px">' +
          '<button class="btn" id="tourNo">自己看看就好</button>' +
          '<button class="btn btn--go" id="tourYes">好，帶我走一遍</button>' +
        '</div>' +
      '</div></div>');
    document.body.appendChild(w);
    document.body.classList.add('hp-on');
  }

  function tourAskClose() {
    var w = document.getElementById('tourAsk');
    if (w) w.remove();
    document.body.classList.remove('hp-on');
  }

  function tourStart() {
    tourAskClose();
    tourAt = -1;
    if (!document.getElementById('tour')) {
      document.body.appendChild(el(
        '<div class="tour" id="tour">' +
          '<div class="tour__hole" id="tourHole"></div>' +
          '<div class="tour__box" id="tourBox"></div>' +
        '</div>'));
    }
    tourGo(1);
  }

  function tourEnd() {
    var w = document.getElementById('tour');
    if (w) w.remove();
    document.body.classList.remove('tour-on');
    tourRemember();
    tourAt = -1;
  }

  function tourGo(delta) {
    var next = tourAt + delta;
    if (next < 0) next = 0;
    if (next >= TOUR.length) { tourEnd(); toast('隨時可以從「使用說明」再看一次', 'ok'); return; }
    tourAt = next;
    var step = TOUR[tourAt];

    if (step.hash && location.hash !== step.hash) { location.hash = step.hash; }
    document.body.classList.add('tour-on');
    setTimeout(tourPaint, 260);
  }

  function tourPaint() {
    var step = TOUR[tourAt];
    var hole = document.getElementById('tourHole');
    var box = document.getElementById('tourBox');
    if (!hole || !box) return;

    /* 同一步可能有桌機和手機兩個位置，挑畫面上真的看得到的那一個 */
    var el0 = Array.prototype.filter.call(document.querySelectorAll(step.sel), function (n) {
      var rr = n.getBoundingClientRect();
      return rr.width > 0 && rr.height > 0;
    })[0];
    if (!el0) { tourGo(1); return; }          // 那個東西這次不在畫面上就跳過

    /* 導覽期間 body 是 overflow:hidden（不讓使用者自己捲，否則圈圈會跟目標分家）。
       但那也擋掉了我們自己的 scrollIntoView——目標在畫面外的那幾步就會圈到空氣。
       所以捲的當下先解開，捲完立刻鎖回去；同一個 tick 內做完，不會閃。 */
    var locked = document.body.classList.contains('tour-on');
    if (locked) document.body.classList.remove('tour-on');
    /* ⚠️ 一定要 'instant'。tokens.css 給了 html { scroll-behavior: smooth }，
       用 'auto' 會繼承成動畫捲動，下一行 getBoundingClientRect() 讀到的
       還是捲之前的位置——圈圈就畫在目標的舊位址，看起來像圈到空氣。 */
    el0.scrollIntoView({ block: 'center', behavior: 'instant' });
    if (locked) document.body.classList.add('tour-on');

    var r = el0.getBoundingClientRect();
    /* ⚠️ 圈圈有過場動畫，所以它從這裡搬到那裡的途中，
       getBoundingClientRect() 讀到的是「動畫現在畫到哪」，不是最後停的位置。
       後面排說明框要避開它，一定得用下面這四個數字，不能回頭去讀 DOM。 */
    var pad = 6;
    var hx = Math.max(2, r.left - pad);
    var hy = Math.max(2, r.top - pad);
    var hw = r.width + pad * 2;
    var hgt = r.height + pad * 2;
    hole.style.left = hx + 'px';
    hole.style.top = hy + 'px';
    hole.style.width = hw + 'px';
    hole.style.height = hgt + 'px';

    box.innerHTML =
      '<div class="tour__n">' + (tourAt + 1) + ' / ' + TOUR.length + '</div>' +
      '<h4>' + esc(step.t) + '</h4>' +
      '<p>' + esc(step.b) + '</p>' +
      '<div class="tour__a">' +
        '<button class="tour__skip" id="tourSkip">跳過</button>' +
        (tourAt > 0 ? '<button class="btn btn--sm" id="tourPrev">上一步</button>' : '') +
        '<button class="btn btn--sm btn--go" id="tourNext">' +
          (tourAt === TOUR.length - 1 ? '完成' : '下一步') + '</button>' +
      '</div>';

    /* 說明框的位置。

       規矩只有一條：**不可以蓋住它正在指的東西**。
       先試右邊，再試左邊；手機上卡片幾乎滿版，兩邊都塞不下，
       這時候要改放上面或下面（挑空間大的那一側），不能硬擠回原位——
       擠回去就會正好疊在目標上，使用者只看到一個框跟一片灰。 */
    var gap = 14, edge = 12;
    var bw = Math.min(300, innerWidth - edge * 2);
    box.style.width = bw + 'px';
    box.style.top = '0px';
    box.style.left = '0px';
    var bh = box.getBoundingClientRect().height;

    /* 要避開的是「圈圈」，不是目標本身——圈圈比目標大一圈，
       而且貼邊時會被夾住，位置跟目標對不起來。 */
    var hRight = hx + hw, hBottom = hy + hgt;
    var left, top;

    if (hRight + gap + bw <= innerWidth - edge) {
      left = hRight + gap;                                    // 放右邊
      top = clamp(hy + hgt / 2 - bh / 2, edge, innerHeight - bh - edge);
    } else if (hx - gap - bw >= edge) {
      left = hx - gap - bw;                                   // 放左邊
      top = clamp(hy + hgt / 2 - bh / 2, edge, innerHeight - bh - edge);
    } else {
      /* 兩邊都塞不下（手機上卡片幾乎滿版）：改放上面或下面，挑空間大的那側。
         不能硬擠回原位——擠回去就正好疊在目標上，
         使用者只看到一個框跟一片灰，根本不知道你在指什麼。 */
      left = clamp(hx + hw / 2 - bw / 2, edge, innerWidth - bw - edge);
      var below = innerHeight - hBottom - gap;
      var above = hy - gap;
      top = (below >= bh || below >= above)
        ? clamp(hBottom + gap, edge, innerHeight - bh - edge)
        : clamp(hy - gap - bh, edge, innerHeight - bh - edge);
    }

    box.style.left = Math.round(left) + 'px';
    box.style.top = Math.round(top) + 'px';
  }



  /* 語意代號 → 主題變數。

     資料裡存的是「這是餐飲」（cat-food），不是「這是 #C4693C」。
     實際顏色由 tokens.css 決定，所以換一套外觀時圖表會跟著換。

     ⚠️ 它同時是**過濾器**。這個字串會被塞進 style="background:…"，
     那是 CSS 的情境——esc() 擋不住，因為 esc() 只處理 HTML。
     所以這裡只放行 [a-z0-9-]，其他一律丟掉。
     沒有代號就回中性色，不要讓畫面出現空白的洞。 */
  function tint(token) {
    var t = String(token || '').replace(/[^a-z0-9-]/gi, '');
    return t ? 'var(--' + t + ')' : 'var(--ink-faint)';
  }


  /* ============================================================
     平台管理（只有平台管理員看得到）

     ⚠️ 這一頁**沒有任何金額**，而且是刻意的。

     平台管理員能停權、能看稽核，但讀不到任何人的收支——一個能讀全系統
     消費明細的帳號，比家長越權嚴重得多，因為沒有任何人看得見那個視角。
     後端不回金額，前端也就畫不出來；不是藏起來，是真的沒有。

     停權是關門，不是配鑰匙。
     ============================================================ */
  function vAdmin() {
    head('平台管理', '停權與稽核。這裡看不到任何人的帳。');
    $view.innerHTML = '<div class="page">' + skeleton(4) + '</div>';

    Promise.all([API.adminUsers(), API.audit()]).then(function (r) {
      var users = r[0].users, logs = r[1].logs;
      var h = '<div class="page"><div class="duo">' +
        '<section class="duo__c">' +
          '<div class="sec"><h2 class="sec__t">帳號</h2><span class="sec__n">' + users.length + ' 個</span></div>' +
          '<div class="card card--flush"><table class="dt">' +
            '<thead><tr><th>帳號</th><th>狀態</th><th></th></tr></thead><tbody>' +
            users.map(function (u) {
              var off = !!u.suspendedAt;
              return '<tr><td><span class="dt__name"><span><b>' + esc(u.name) + '</b>' +
                  '<small>' + esc(u.email) + '</small></span></span></td>' +
                '<td>' + (off
                  ? '<span class="pill pill--over">已停權</span><small class="dt__why">' + esc(u.suspendedReason) + '</small>'
                  : '<span class="pill pill--safe">正常</span>') + '</td>' +
                '<td class="rt">' + (off
                  ? '<button class="gx gx--go" data-unsus="' + esc(u.id) + '">解除停權</button>'
                  : '<button class="gx gx--warn" data-sus="' + esc(u.id) + '">停權</button>') + '</td></tr>';
            }).join('') + '</tbody></table></div>' +
        '</section>' +
        /* ⚠️ 稽核跟帳號並排，不收起來——沒有稽核的停權就是任意封鎖 */
        '<section class="duo__c">' +
          '<div class="sec"><h2 class="sec__t">稽核紀錄</h2><span class="sec__n">' + logs.length + ' 筆</span></div>' +
          '<div class="card card--flush"><ol class="audl">' + logs.map(function (a) {
            return '<li class="audl__i">' +
              '<div class="audl__top"><b>' + esc(AUDIT_TW[a.action] || a.action) + '</b>' +
                '<time>' + esc(a.at) + '</time></div>' +
              '<div class="audl__s">' + esc(a.actorName) + (a.note ? '　' + esc(a.note) : '') + '</div>' +
            '</li>';
          }).join('') + '</ol></div>' +
        '</section>' +
      '</div></div>';
      $view.innerHTML = h;
    }).catch(function (e) {
      $view.innerHTML = '<div class="page">' + errState(e) + '</div>';
    });
  }

  var AUDIT_TW = {
    suspend_user: '停權帳號', unsuspend_user: '解除停權',
    grant_guardianship: '建立監管關係', end_guardianship: '解除監管',
    change_role: '變更角色', create_family: '建立家庭', view_ward: '查看被監管者',
    invite_member: '邀請家人', join_family: '加入家庭',
    remove_member: '移出家庭', leave_family: '退出家庭'
  };

  /* ---------- 共用 ---------- */
  /* 第一層標題。有「我｜全家」切換的頁面，標題上方的小字跟著顯示「我的／全家」；
     act 是這一頁右上角的動作，可以不給。 */
  function head(t, sub, act) {
    $title.textContent = t;
    $sub.textContent = sub || '';
    $sub.hidden = !sub;
    var a = document.getElementById('pact');
    if (a) { a.innerHTML = act || ''; a.hidden = !act; }
    /* 有「我／全家」切換的頁面，小字直接說現在看的是誰 */
    var k = document.getElementById('pkick');
    var fam = /data-scope=/.test(act || '') && SCOPE === 'family';
    if (k) k.textContent = /data-scope=/.test(act || '') ? (fam ? '全家' : '我的') : '';
    /* 全家模式只整理資訊、不記帳：右上角和手機的「記一筆」一起收起來 */
    document.body.classList.toggle('in-family', fam);
  }

  function animate() {
    Array.prototype.forEach.call(document.querySelectorAll('[data-count]'), function (n) {
      var to = Number(n.dataset.count), t0 = performance.now(), dur = 700;
      (function step(now) {
        var p = Math.min(1, (now - t0) / dur);
        n.textContent = Math.round(to * (1 - Math.pow(1 - p, 3)));
        if (p < 1) requestAnimationFrame(step);
      })(t0);
    });
  }


  /* ============================================================
     登入 / 註冊 / 個人資料
     ============================================================ */


  /* ============================================================
     登入前的主頁

     它不是另一個路由，是**登入頁的第一個狀態**。按下「開始使用」
     之後在原地換成表單——不換網址、不重新載入，所以沒有白屏，
     那一下的連續感就是互動感的來源。

     ⚠️ 這只是畫面順序，不是權限。真正的把關仍然在 paint() 的登入閘
     以及後端；主頁本身什麼資料都沒有。
     ============================================================ */
  var gateStep = 'landing';           // landing ｜ login ｜ register

  /* 一頁帳簿。用 SVG 畫，不外連圖檔：
     它要跟著米白主題走，而且放大不會糊。 */
  function ledgerArt() {
    var rows = [
      ['09-02', '早餐店', '55'],
      ['09-02', '捷運', '32'],
      ['09-03', '午餐', '120'],
      ['09-05', '家樂福 週採買', '2,450'],
      ['09-06', '加油站', '1,150']
    ];
    var y0 = 74, gap = 27;
    var lines = rows.map(function (r, i) {
      var y = y0 + i * gap;
      return '<g class="lg__row" style="animation-delay:' + (260 + i * 90) + 'ms">' +
        '<text class="lg__d" x="30" y="' + y + '">' + r[0] + '</text>' +
        '<text class="lg__m" x="86" y="' + y + '">' + r[1] + '</text>' +
        '<text class="lg__v" x="388" y="' + y + '">−' + r[2] + '</text>' +
        '<line class="lg__rule" x1="24" y1="' + (y + 9) + '" x2="388" y2="' + (y + 9) + '"/>' +
      '</g>';
    }).join('');

    return '<svg class="lg" viewBox="0 0 412 312" role="img" ' +
        'aria-label="一頁帳簿：五筆支出、本月已花與還能花">' +
      '<rect class="lg__paper" x="1" y="1" width="410" height="310"/>' +
      /* 左邊那條裝訂線，帳簿紙才有的樣子 */
      '<line class="lg__bind" x1="66" y1="1" x2="66" y2="311"/>' +
      '<text class="lg__h" x="30" y="38">日期</text>' +
      '<text class="lg__h" x="86" y="38">項目</text>' +
      '<text class="lg__h lg__h--r" x="388" y="38">金額</text>' +
      '<line class="lg__rule lg__rule--head" x1="24" y1="48" x2="388" y2="48"/>' +
      lines +
      /* 合計上面的雙線——這是帳簿的收尾寫法 */
      '<line class="lg__dbl" x1="248" y1="222" x2="388" y2="222"/>' +
      '<line class="lg__dbl" x1="248" y1="226" x2="388" y2="226"/>' +
      '<text class="lg__t" x="248" y="248">本月已花</text>' +
      '<text class="lg__sum" x="388" y="248" id="lgSum">0</text>' +
      /* ⚠️ 這一欄才是重點。這類 App 的主頁幾乎都用「一個大數字」當主體，
         而我們最清楚的一句話就是可再支出＝收入−存款目標−已花。 */
      '<rect class="lg__hi" x="24" y="262" width="364" height="1"/>' +
      '<text class="lg__lt" x="24" y="290">還能花</text>' +
      '<text class="lg__lv" x="388" y="294" id="lgLeft">0</text>' +
    '</svg>';
  }

  function vLanding() {
    head('', '');
    document.body.classList.add('is-out');
    $view.innerHTML =
      '<div class="lp">' +
        '<div class="lp__l">' +
          /* 扉頁式的排法：**專題名稱最大**，一條細線，標語在下面。

             主頁同時是這個專題的門面，名稱本來就該是視覺重心；
             而標語仍然要講**結果**不講機制——
             「打一句話就記好一筆帳」是說明文件的句型，它在講功能怎麼運作，
             主頁要講的是使用者得到什麼。機制降到副標，細節再降到三點。 */
          '<span class="lp__k">專題</span>' +
          '<h1 class="lp__t">家庭記帳與財務控管系統</h1>' +
          '<div class="lp__rule"></div>' +
          '<p class="lp__tag">花錢，心裡有數</p>' +
          '<p class="lp__s">' +
            '收入扣掉你想存的，剩下的才是能放心花的錢。<br>' +
            '打開就看見這個月還剩多少，不用等月底對帳。' +
          '</p>' +
          /* 三點式細列：一行標題 ＋ 一行說明，用上框線分隔，不做成卡片。
             這是這類 App 的共同做法，而且比一整段文字好掃。 */
          '<ul class="lp__f">' +
            '<li><b>一句話記好幾筆</b><i>「早餐55 中午吃飯320」送出就拆開，' +
              '分類和金額都填好</i></li>' +
            '<li><b>家人的支出看得見</b><i>誰花的、花在哪，不用互相問</i></li>' +
            '<li><b>花超前先提醒</b><i>到你設的比例就通知，不用等月底才發現</i></li>' +
          '</ul>' +
          '<button class="lp__go" id="lpGo">' +
            '<span>開始使用</span>' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
              'stroke-width="1.8"><path d="M4 12h15"/><path d="m13 6 6 6-6 6"/></svg>' +
          '</button>' +
          '<p class="lp__n">不用註冊也能試——裡面是示範資料</p>' +
        '</div>' +
        '<div class="lp__r">' + ledgerArt() + '</div>' +
      '</div>';
    countUp(document.getElementById('lgSum'), 3807, 900);
    countUp(document.getElementById('lgLeft'), 26770, 1200);
  }

  /* 合計從 0 跑上去。⚠️ 用 requestAnimationFrame 不用 setInterval——
     分頁切到背景時 rAF 會暫停，回來不會突然跳一大段。 */
  function countUp(el, target, ms) {
    if (!el) return;
    var t0 = 0;
    function step(t) {
      if (!t0) t0 = t;
      var p = Math.min(1, (t - t0) / ms);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(target * eased).toLocaleString('en-US');
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  function authShell(title, sub, inner) {
    document.body.classList.add('is-out');
    $view.innerHTML =
      '<div class="gate"><div class="gate__c">' +
        '<div class="gate__b"><span class="brand__m" aria-hidden="true">FamBudget</span><span class="brand__n">家庭記帳</span></div>' +
        '<h1 class="gate__t">' + title + '</h1>' +
        '<p class="gate__s">' + sub + '</p>' +
        inner +
      '</div></div>';
  }

  function vLogin() {
    /* 主頁是這一頁的第一個狀態。直接打 #/login 進來的人（例如按了
       「登入」的書籤）就跳過主頁，不要再擋他一次。 */
    if (gateStep === 'landing') { vLanding(); return; }
    head('登入', '');
    authShell('登入', '記一句話就記一筆帳，家人的支出一起看得見。',
      '<form class="gate__f" id="loginF">' +
        '<label class="fld"><span>Email</span>' +
          '<input type="email" id="lgEmail" autocomplete="username" required></label>' +
        '<label class="fld"><span>密碼</span>' +
          '<input type="password" id="lgPw" autocomplete="current-password" required></label>' +
        '<button class="btn btn--go gate__go" type="submit">登入</button>' +
        '<p class="gate__alt">還沒有帳號？<a href="#/register" data-gate="register">建立一個</a></p>' +
      '</form>' +
      (API.mode === 'http' ? '' :
        '<div class="gate__demo"><b>展示資料</b>　密碼隨便打，滿 8 個字就好' +
        '<div class="gate__accs">' +
          DEMO.map(function (d) {
            return '<button class="gate__acc" data-demo="' + esc(d.email) + '">' +
              esc(d.name) + '<span>' + esc(d.email) + '</span></button>';
          }).join('') +
        '</div></div>'));
  }

  function vRegister() {
    gateStep = 'register';
    head('註冊', '');
    authShell('建立帳號', '註冊之後可以自己記帳，也可以加入家庭一起看。',
      '<form class="gate__f" id="regF">' +
        '<label class="fld"><span>名字</span>' +
          '<input type="text" id="rgName" autocomplete="name" required></label>' +
        '<label class="fld"><span>Email</span>' +
          '<input type="email" id="rgEmail" autocomplete="username" required></label>' +
        '<label class="fld"><span>密碼</span>' +
          '<input type="password" id="rgPw" autocomplete="new-password" required>' +
          '<em class="fld__h">至少 8 個字</em></label>' +
        '<label class="fld"><span>每月存款目標</span>' +
          '<input type="number" id="rgGoal" min="0" value="0">' +
          '</label>' +
        '<button class="btn btn--go gate__go" type="submit">建立帳號</button>' +
        '<p class="gate__alt">已經有帳號了？<a href="#/login" data-gate="login">回去登入</a></p>' +
      '</form>');
  }

  function vProfile() {
    head('個人資料', '');
    $view.innerHTML = '<div class="page">' + skeleton(3) + '</div>';
    API.me().then(function (m) {
      var u = m.user;
      /* 左邊是「我是誰」，右邊是「我的錢怎麼管」。
         存款目標和提醒放在一起：提醒算的就是目標之後剩下的額度。 */
      var h = '<div class="page"><div class="duo">' +
        '<section class="duo__c">' +
          '<div class="sec"><h2 class="sec__t">我的資料</h2></div>' +
          '<div class="card me">' +
            '<div class="me__top">' +
              '<div class="me__a" id="profAva">' + ava(u, 'ava--xl') + '</div>' +
              '<div class="me__who">' +
                '<div class="me__n">' + esc(u.name) + '</div>' +
                '<div class="me__r">' + esc(ROLE_TW[u.role] || '') + '</div>' +
                '<div class="me__do">' +
                  '<label class="btn btn--sm">換照片' +
                    '<input type="file" id="avaF" accept="image/png,image/jpeg,image/webp" hidden></label>' +
                  (u.avatarUrl ? '<button class="btn btn--sm btn--ghost" id="avaDel">移除照片</button>' : '') +
                '</div>' +
              '</div>' +
            '</div>' +
            '<form class="grid-form" id="profF">' +
              '<label class="fld"><span>名字</span>' +
                '<input type="text" id="pfName" value="' + esc(u.name) + '" required></label>' +
              '<label class="fld"><span>出生年份</span>' +
                '<input type="number" id="pfYear" min="1900" max="' + new Date().getFullYear() + '" ' +
                  'value="' + (u.birthYear || '') + '" placeholder="例如 1974"></label>' +
              '<label class="fld fld--wide"><span>Email</span>' +
                '<input type="email" value="' + esc(u.email || '') + '" disabled></label>' +
              '<div class="form__act"><button class="btn btn--go btn--sm" type="submit">儲存</button></div>' +
            '</form>' +
          '</div>' +

          '<div class="sec"><h2 class="sec__t">密碼</h2></div>' +
          '<form class="card grid-form" id="pwF">' +
            '<label class="fld"><span>目前的密碼</span>' +
              '<input type="password" id="pwOld" autocomplete="current-password" required></label>' +
            '<label class="fld"><span>新密碼</span>' +
              '<input type="password" id="pwNew" autocomplete="new-password" placeholder="至少 8 個字" required></label>' +
            '<div class="form__act"><button class="btn btn--sm" type="submit">更改密碼</button></div>' +
          '</form>' +
        '</section>' +

        '<section class="duo__c">' +
          '<div class="sec"><h2 class="sec__t">存錢計畫</h2></div>' +
          '<div class="card plan">' +
            '<div class="plan__k">每個月想存' + helpBtn('goal') + '</div>' +
            '<label class="money money--lg"><i>NT$</i>' +
              '<input type="number" min="0" inputmode="numeric" data-goal="' + esc(u.id) + '" ' +
                'value="' + (u.savingsGoal || 0) + '" aria-label="每月存款目標"></label>' +
            '<div class="plan__h">只有你自己能設定。改完離開欄位就會存好</div>' +
          '</div>' +
          '<div class="card card--flush" id="alertBox">' + skeleton(2) + '</div>' +
          foldHead('fin', '理財習慣', '填寫') +
        '</section>' +
      '</div>' +

      /* 主題設定：左右滑著挑，按一下就套用 */
      '<section class="thm">' +
        '<div class="sec"><h2 class="sec__t">主題設定</h2>' +
          '<span class="sec__n">' + (global.DATA.themes || []).length + ' 套</span>' +
          '<div class="thm__nav">' +
            '<button type="button" data-thm-go="-1" aria-label="往左看">' +
              '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 6 9 12l6 6"/></svg></button>' +
            '<button type="button" data-thm-go="1" aria-label="往右看">' +
              '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg></button>' +
          '</div>' +
        '</div>' +
        '<div class="thm__row" id="thmRow">' + themeCards(u.theme || currentTheme()) + '</div>' +
      '</section>' +
      '</div>';
      $view.innerHTML = h;
      var onCard = document.querySelector('.thm__i.on');
      if (onCard && onCard.scrollIntoView) onCard.parentNode.scrollLeft = onCard.offsetLeft - 8;
      foldRestore();
      paintAlerts();
    });
  }

  /* 每一張預覽自己掛著 data-theme，裡面的顏色、圓角、字就是那一套的——
     不用另外準備截圖，主題改了預覽自動跟著變。 */
  function themeCards(cur) {
    return (global.DATA.themes || []).map(function (t) {
      var on = t.id === cur;
      return '<button type="button" class="thm__i' + (on ? ' on' : '') + '" data-theme-pick="' + esc(t.id) + '" ' +
          'aria-pressed="' + on + '">' +
        '<span class="thm__pv" data-theme="' + esc(t.id) + '" aria-hidden="true">' +
          '<span class="thm__hi">午安</span>' +
          '<span class="thm__s thm__s--1"></span><span class="thm__s thm__s--2"></span>' +
          '<span class="thm__c">6,770<i></i></span>' +
          '<span class="thm__q"><b></b><b></b><b></b><b></b></span>' +
        '</span>' +
        '<span class="thm__m"><span class="thm__n">' + esc(t.name) + '</span>' +
          '<span class="thm__st">' + (on ? '使用中' : '套用') + '</span></span>' +
        '<span class="thm__d">' + esc(t.note) + '</span>' +
      '</button>';
    }).join('');
  }

  /* ---------------------------------------------------------
     我的帳戶卡（右上角頭貼點開）

     ⚠️ 以前這裡是一串連結：個人資料、家庭成員、使用說明……
     跟儀表板上的常用功能幾乎一樣，等於同一件事放兩個地方。
     現在只放儀表板上「沒有」的：
       · 這個月記帳的天數（一格一天，看得出習慣）
       · 家人（頭像疊在一起，點了進家庭成員）
       · 快速換主題（八個小圓點，按一下就換）
     --------------------------------------------------------- */
  function paintAcct() {
    var sw = document.getElementById('acctThemes');
    var cur = currentTheme();
    if (sw) sw.innerHTML = (global.DATA.themes || []).map(function (t) {
      var on = t.id === cur;
      return '<button type="button" class="acctm__sw' + (on ? ' on' : '') + '" data-theme-pick="' + esc(t.id) + '" ' +
        'data-theme="' + esc(t.id) + '" title="' + esc(t.name) + '" aria-label="換成' + esc(t.name) + '" ' +
        'aria-pressed="' + on + '"></button>';
    }).join('');

    var habit = document.getElementById('acctHabit'), fam = document.getElementById('acctFam');
    if (!habit || !fam) return;
    API.me().then(function (m) {
      if (m.user.isPlatformAdmin) return;          // 平台管理員沒有帳，也不屬於任何家庭
      var day = todayKey(), first = day.slice(0, 8) + '01';
      return Promise.all([
        API.transactions({ userId: m.user.id, from: first, to: day }),
        API.members().catch(function () { return { members: [], family: null }; })
      ]).then(function (r) {
        var seen = {};
        r[0].transactions.forEach(function (t) { seen[t.date] = true; });
        var n = Number(day.slice(8)), got = 0, cells = '';
        for (var i = 1; i <= n; i++) {
          var k = day.slice(0, 8) + ('0' + i).slice(-2);
          if (seen[k]) got++;
          cells += '<i' + (seen[k] ? ' class="on"' : '') + ' title="' + Number(day.slice(5, 7)) + '/' + i +
            (seen[k] ? ' 有記帳' : '') + '"></i>';
        }
        habit.innerHTML = '<div class="acctm__k">這個月記帳 <b>' + got + '</b><span> / ' + n + ' 天</span></div>' +
          '<div class="acctm__cal" aria-hidden="true">' + cells + '</div>';

        var fm = r[1];
        fam.innerHTML = fm.family
          ? '<span class="acctm__fm"><span class="acctm__k">' + esc(fm.family.name) + '</span>' +
              '<small>' + fm.members.length + ' 位家人</small></span>' +
            '<span class="acctm__avs">' + fm.members.slice(0, 5).map(function (u) { return ava(u); }).join('') + '</span>'
          : '<span class="acctm__fm"><span class="acctm__k">還沒有加入家庭</span><small>建立一個，或輸入邀請碼</small></span>';
      });
    }).catch(function () {});
  }

  function markTheme(id) {
    Array.prototype.forEach.call(document.querySelectorAll('.thm__i, .acctm__sw'), function (b) {
      var on = b.dataset.themePick === id;
      b.classList.toggle('on', on);
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
      var st = b.querySelector('.thm__st');
      if (st) st.textContent = on ? '使用中' : '套用';
    });
  }

  /* 按下去馬上換，同時存到帳號上；存失敗就換回去，畫面不會跟帳號對不上 */
  function chooseTheme(id) {
    var prev = currentTheme();
    if (id === prev || !themeOf(id)) return;
    applyTheme(id);
    markTheme(id);
    API.updateProfile({ theme: id }).then(function () {
      if (ME && ME.user) ME.user.theme = id;
      toast('換成「' + themeOf(id).name + '」了', 'ok');
    }).catch(function (e) {
      applyTheme(prev);
      markTheme(prev);
      toast((e && e.message) || '沒有存成功，等一下再試', 'err');
    });
  }

  /* ---------------------------------------------------------
     花到幾成提醒我：一條清單 ＋ 同一行加一個
     --------------------------------------------------------- */
  function paintAlerts() {
    var box = document.getElementById('alertBox');
    if (!box) return;
    Promise.all([API.alerts(), API.savingsGoals()]).then(function (r) {
      var list = r[0].alerts || [], goals = r[1].goals || [];

      var h = '<div class="card__h"><span class="card__t">花到幾成提醒我</span>' + helpBtn('alerts') + '</div>';
      h += list.length
        ? '<ul class="alist">' + list.map(function (a) {
            return '<li class="ai' + (a.enabled ? '' : ' off') + '">' +
              '<span class="ai__p">' + esc(a.percent) + '<i>%</i></span>' +
              '<span class="ai__s">' + esc(a.groupName) + '</span>' +
              '<button class="sw' + (a.enabled ? ' on' : '') + '" role="switch" aria-checked="' + !!a.enabled + '" ' +
                'data-atoggle="' + esc(a.id) + '|' + (a.enabled ? '0' : '1') + '" ' +
                'aria-label="' + (a.enabled ? '關掉' : '打開') + '這個提醒"><i></i></button>' +
              '<button class="ai__x" data-adel="' + esc(a.id) + '" title="刪掉" aria-label="刪掉這個提醒">×</button>' +
            '</li>';
          }).join('') + '</ul>'
        : '<p class="alist__empty">還沒有提醒</p>';

      h += '<form class="anew" id="anewF">' +
        '<span class="anew__t">花到</span>' +
        '<input type="number" id="anPct" min="1" max="200" value="80" required aria-label="百分比">' +
        '<span class="anew__t">%，</span>' +
        '<select id="anGroup" aria-label="哪一本帳">' + goals.map(function (g) {
          return '<option value="' + (g.groupId || '') + '">' + esc(g.groupName) + '</option>';
        }).join('') + '</select>' +
        '<button class="btn btn--sm btn--go" type="submit">加入</button>' +
      '</form>';

      box.innerHTML = h;
    }).catch(function (e) { box.innerHTML = errState(e); });
  }

  /* 縮圖：置中裁成正方形再縮到 256，超過 200 KB 就降畫質重來。
     後端的上限是 200 KB，在這裡先擋掉比讓使用者送出去再被打回來好。 */
  function shrink(file) {
    return new Promise(function (ok, no) {
      var fr = new FileReader();
      fr.onerror = function () { no(new Error('讀不到這個檔案')); };
      fr.onload = function () {
        var img = new Image();
        img.onerror = function () { no(new Error('這不是一張能顯示的圖片')); };
        img.onload = function () {
          var side = Math.min(img.width, img.height);
          var cv = document.createElement('canvas');
          cv.width = cv.height = 256;
          cv.getContext('2d').drawImage(
            img, (img.width - side) / 2, (img.height - side) / 2, side, side, 0, 0, 256, 256);
          var q = 0.85, out = cv.toDataURL('image/jpeg', q);
          while (out.length * 3 / 4 > 200 * 1024 && q > 0.4) {
            q -= 0.15;
            out = cv.toDataURL('image/jpeg', q);
          }
          ok(out);
        };
        img.src = fr.result;
      };
      fr.readAsDataURL(file);
    });
  }

  /* ---------------------------------------------------------
     頭像。沒上傳大頭貼的人顯示名字的最後一個字，
     上傳過的人顯示圖片 —— 契約裡 avatarUrl 為 null 就退回文字。
     --------------------------------------------------------- */
  function ava(u, cls) {
    cls = cls ? ' ' + cls : '';
    var url = u && u.avatarUrl;
    // 只認 data:image，其他一律退回文字。頭像網址是後端給的，
    // 但「後端給的」不等於「可以直接塞進 src」——擋一手成本很低。
    if (url && /^data:image\//.test(url)) {
      return '<span class="ava ava--img' + cls + '"><img src="' + esc(url) + '" alt=""></span>';
    }
    return '<span class="ava' + cls + '">' + esc((u && u.avatar) || '') + '</span>';
  }

  /* 帳本切換器。只有一本帳的時候不顯示——一個只有一個選項的下拉是雜訊。 */
  function paintGroups() {
    var box = document.getElementById('gsw');
    if (!box) return;
    API.groups().then(function (d) {
      var gs = d.groups || [];
      box.hidden = gs.length < 2;
      if (box.hidden) { setGroup('all'); return; }

      // 選到的帳本如果已經看不到了（被移出或封存），退回全部
      if (GROUP !== 'all' && !gs.some(function (g) { return g.id === GROUP; })) setGroup('all');

      var cur = GROUP === 'all'
        ? { name: '全部帳本', color: 'var(--ink-faint)' }
        : gs.filter(function (g) { return g.id === GROUP; })[0];

      /* 兩種長相都畫出來，由 body 上的 class 決定顯示哪一種：
           方案一（bar-text）文字 ＋ 抽屜
           方案二（bar-icon）圖示 ＋ 一般下拉
         挑定之後把另一邊刪掉就好。 */
      box.innerHTML =
        '<button class="ic gsw__b" id="gswBtn" title="帳本：' + esc(cur.name) + '" ' +
          'aria-label="切換帳本，目前是' + esc(cur.name) + '">' +
          '<svg class="gsw__ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">' +
            '<path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H10v16H5.5A1.5 1.5 0 0 1 4 18.5z"/>' +
            '<path d="M10 4h8.5A1.5 1.5 0 0 1 20 5.5v13a1.5 1.5 0 0 1-1.5 1.5H10"/></svg>' +
          '<span class="ic__d" style="background:' + tint(cur.color) + '"></span>' +
          '<span class="gsw__d" style="background:' + tint(cur.color) + '"></span>' +
          '<span class="gsw__n">' + esc(cur.name) + '</span>' +
          '<svg class="gsw__cv" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
            'stroke-width="2"><path d="m6 9 6 6 6-6"/></svg>' +
        '</button>' +
        '<div class="gsw__p" id="gswPanel" hidden>' +
          '<button class="gsw__i' + (GROUP === 'all' ? ' on' : '') + '" data-group="all">' +
            '<span class="gsw__d" style="background:var(--ink-faint)"></span>' +
            '<span class="gsw__m"><b>全部帳本</b><i>我看得到的全部合起來</i></span></button>' +
          gs.map(function (g) {
            return '<button class="gsw__i' + (g.id === GROUP ? ' on' : '') +
              '" data-group="' + esc(g.id) + '">' +
              '<span class="gsw__d" style="background:' + tint(g.color) + '"></span>' +
              '<span class="gsw__m"><b>' + esc(g.name) + '</b><i>' +
                g.count + ' 筆' + (g.goal ? '　目標 ' + money(g.goal) : '') +
              '</i></span></button>';
          }).join('') +
          '<a class="gsw__more" href="#/groups">管理帳本 →</a>' +
        '</div>';
      pushForDrawer();
    }).catch(function () { box.hidden = true; });
  }

  function paintWho() {
    API.me().then(function (m) {
      ME = m;
      /* 帳戶卡最上面：頭貼、全名、身分 · 家庭。整塊點下去是個人資料 */
      var role = ROLE_TW[m.user.role] || (m.user.isPlatformAdmin ? '平台管理員' : '還沒有家庭');
      var card = ava(m.user, 'ava--md') +
        '<span class="acct__m"><b class="acct__n">' + esc(m.user.name) + '</b>' +
          '<span class="acct__r">' + esc(role) + (m.family ? ' · ' + esc(m.family.name) : '') + '</span></span>' +
        '<span class="acctm__to">個人資料' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
          'stroke-linejoin="round" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg></span>';
      var w = document.getElementById('who');
      if (w) w.innerHTML = ava(m.user, 'ava--sm') + '<span class="acctm__n">' + esc(callName(m.user.name)) + '</span>';
      var wc = document.getElementById('whoCard');
      if (wc) wc.innerHTML = card;
      /* 角色決定「有沒有這個功能」，監管決定「看得到誰」——兩件事 */
      document.body.classList.toggle('role-child', m.user.role !== 'parent');
      /* ⚠️ 平台管理員沒有財務頁可以看——那不是藏起來，是他真的沒有資料 */
      document.body.classList.toggle('is-admin', !!m.user.isPlatformAdmin);
      if (m.user.theme && m.user.theme !== currentTheme()) applyTheme(m.user.theme);
    });
  }

  /* ---------- 路由 ---------- */
  var ROUTES = { '': vHome, entry: vEntry, stats: vStats,
                 advice: vAdvice, members: vMembers,
                 login: vLogin, register: vRegister, profile: vProfile,
                 member: vMember, groups: vGroups, admin: vAdmin };

  var OPEN = ['login', 'register'];      // 沒登入也能看的頁

  function paint() {
    // #/member/U3/T1051 → ['member', 'U3', 'T1051']
    var parts = (location.hash || '#/').replace(/^#\/?/, '').split('/');
    var page = parts[0];
    API.authState().then(function (a) {
      /* 登入閘。沒登入只能待在 login／register，
         登入了就別再讓他看登入頁。 */
      if (!a.loggedIn && OPEN.indexOf(page) < 0) { location.hash = '#/login'; return; }
      if (a.loggedIn && OPEN.indexOf(page) >= 0) { location.hash = '#/'; return; }

      if (!a.loggedIn) { render(); return; }
      document.body.classList.remove('is-out');

      /* 平台管理員與一般使用者走的是兩組完全不重疊的頁面。

         ⚠️ 這一段擋的是「平台管理員登入之後落在我的總覽」：
         他沒有任何財務資料，總覽會是一頁全部是 0 的空殼，
         看起來像壞掉，而且那一頁的存在本身就在暗示他「應該要有」。
         反過來，一般使用者打 #/admin 會拿到 403，直接送回首頁。

         ME 在登出時會清掉，所以這裡不會拿上一個人的身分來判斷。 */
      (ME && ME.user ? Promise.resolve(ME) : API.me()).then(function (m) {
        ME = m;
        var admin = !!m.user.isPlatformAdmin;
        if (admin && page !== 'admin') { location.hash = '#/admin'; return; }
        if (!admin && page === 'admin') { location.hash = '#/'; return; }
        render();
      });

      function render() {
        (ROUTES[page] || vHome)(parts[1], parts[2]);
        /* 總覽就是儀表板；其他頁面左上角出現「總覽」可以回去 */
        var hb = document.getElementById('homeBtn');
        if (hb) hb.hidden = page === '' || page === 'admin' || OPEN.indexOf(page) >= 0;
        document.body.classList.toggle('is-home', page === '');
        var tab = page === 'member' ? 'members' : page;
        Array.prototype.forEach.call(document.querySelectorAll('.tabbar__i[data-tab]'), function (b) {
          b.classList.toggle('on', b.dataset.tab === tab);
        });
        acctMenu(false);
      }
    });
  }

  /* ---------- 事件 ---------- */
  document.addEventListener('click', function (e) {
    var t = e.target;
    if (!t.closest) return;

    /* 導覽進行中：只有導覽自己的按鈕能按 */
    if (document.getElementById('tourAsk')) {
      if (t.closest('#tourYes')) tourStart();
      else if (t.closest('#tourNo')) { tourAskClose(); tourRemember(); }
      e.preventDefault(); e.stopPropagation();
      return;
    }
    if (tourAt >= 0) {
      if (t.closest('#tourNext')) tourGo(1);
      else if (t.closest('#tourPrev')) tourGo(-1);
      else if (t.closest('#tourSkip')) tourEnd();
      e.preventDefault(); e.stopPropagation();
      return;
    }

    /* 確認視窗開著的時候，底下什麼都不能點 */
    if (dangerOn) {
      if (t.closest('#dgYes')) dangerGo();
      else if (t.closest('#dgX') || t.closest('#dgNo') || !t.closest('.hp__c')) dangerClose();
      e.preventDefault();
      e.stopPropagation();
      return;
    }

    /* 說明彈窗：開著的時候，除了關閉之外什麼都不能點 */
    if (helpOpen) {
      if (t.closest('#hpX') || t.closest('#hpOk') || !t.closest('.hp__c')) closeHelp();
      e.preventDefault();
      e.stopPropagation();
      return;
    }
    var q = t.closest('[data-help]');
    if (q) { openHelp(q.dataset.help); return; }

    /* 右上角的帳號選單；點選單以外的地方就收起來 */
    if (t.closest('#acctBtn')) { acctMenu(); return; }

    var tp = t.closest('[data-theme-pick]');
    if (tp) { chooseTheme(tp.dataset.themePick); return; }
    var tg = t.closest('[data-thm-go]');
    if (tg) {
      var row = document.getElementById('thmRow');
      if (row) row.scrollBy({ left: Number(tg.dataset.thmGo) * 186, behavior: 'smooth' });
      return;
    }
    if (!t.closest('#acctm')) {
      var ap = document.getElementById('acctPanel');
      if (ap && !ap.hidden) acctMenu(false);
    }

    /* 記一筆：從哪裡按都直接打開記帳的輸入區 */
    if (t.closest('[data-quick="entry"]')) {
      acctMenu(false);
      if (/^#\/entry/.test(location.hash)) {
        if (!FOLD.entry) foldToggle('entry');
        var fw = document.getElementById('fold-entry');
        if (fw) fw.scrollIntoView({ block: 'start', behavior: 'smooth' });
      } else {
        FOLD.entry = true;
        location.hash = '#/entry';
      }
      return;
    }

    /* 我／全家：換範圍之後重畫這一頁 */
    var scp = t.closest('[data-scope]');
    if (scp) {
      SCOPE = scp.dataset.scope === 'family' ? 'family' : 'me';
      try { sessionStorage.setItem('fambudget.scope', SCOPE); } catch (err) {}
      paint();
      return;
    }

    var nav = t.closest('[data-nav]');
    if (nav) { acctMenu(false); location.hash = '#/' + nav.dataset.nav; return; }

    /* 成員那一列點下去看他的紀錄。
       存款目標的輸入框也在這一列裡，點它不能跳走。 */
    /* 移出家庭（家長 → 子女）。⚠️ 要放在 data-open 前面：
       按鈕在成員卡片裡，卡片本身點了會進那個人的紀錄 */
    var mrm = t.closest('[data-member-remove]');
    if (mrm) {
      var rmId = mrm.dataset.memberRemove, rmName = mrm.dataset.name;
      danger({
        title: '把' + rmName + '移出家庭',
        detail: '他的紀錄<b>一筆都不會刪</b>。<br>' +
                '你們之間的監管關係、零用金會結束，他也會離開家人開的帳本——之後彼此就看不到了。',
        level: 'password',
        ok: '確定移出',
        onOk: function () {
          API.removeMember(rmId).then(function () {
            paintGroups(); vMembers();
            toast(rmName + ' 已經移出家庭', 'ok');
          }).catch(function (err) { toast(err.message || '移除失敗', 'err'); });
        }
      });
      return;
    }
    if (t.closest('[data-family-leave]')) {
      var famName = t.closest('[data-family-leave]').dataset.name;
      danger({
        title: '退出「' + famName + '」',
        detail: '你的紀錄<b>一筆都不會刪</b>，之後也可以再被邀請回來。<br>' +
                '退出後你跟家人之間就互相看不到了，你也會離開家人開的帳本。',
        level: 'password',
        ok: '確定退出',
        onOk: function () {
          API.leaveFamily().then(function () {
            afterFamilyChange('已經退出「' + famName + '」');
          }).catch(function (err) { toast(err.message || '退出失敗', 'err'); });
        }
      });
      return;
    }

    var open = t.closest('[data-open]');
    if (open && !t.closest('input') && !t.closest('label')) {
      location.hash = '#/member/' + open.dataset.open;
      return;
    }

    if (t.closest('#logout')) {
      acctMenu(false);
      API.logout().then(function () {
        // 先把通知收件匣清掉，不然登出後 DOM 裡還躺著上一個人的明細
        if (global.Notify) { global.Notify.stop(); global.Notify.reset(); }
        /* ⚠️ 身分也要清。不清的話，管理員登出、家長登入的那一瞬間，
           路由閘還拿著管理員的身分，會把家長送去 #/admin。 */
        ME = null;
        document.body.classList.remove('is-admin', 'role-child');
        document.body.classList.add('is-out');
        location.hash = '#/login';
        paint();
        toast('已登出', 'ok');
      });
      return;
    }

    /* ---- 財務建議：點一則展開，再點收起 ---- */
    var adv = t.closest('[data-adv]');
    if (adv) {
      var prevAd = ADVOPEN;
      ADVOPEN = (ADVOPEN === adv.dataset.adv) ? null : adv.dataset.adv;
      var list = document.getElementById('advList');
      var rowAd = function (id) {
        var b = list && list.querySelector('[data-adv="' + id + '"]');
        return b ? b.parentNode : null;
      };
      if (prevAd && rowAd(prevAd)) {
        rowAd(prevAd).classList.remove('on');
        slideAway(rowAd(prevAd).querySelector('.ad__b'));
      }
      if (ADVOPEN && rowAd(ADVOPEN)) {
        var one = ADV.filter(function (x) { return x.id === ADVOPEN; })[0];
        var box = rowAd(ADVOPEN);
        box.classList.add('on');
        box.insertAdjacentHTML('beforeend', advBody(one));
        slideOpen(box.lastElementChild);
      }
      return;
    }

    /* ---- 記帳方式的抽屜 ---- */
    if (t.closest('#modeBtn') && !t.closest('[data-help]')) {
      var mp = document.getElementById('modePanel');
      if (mp) {
        var opening = mp.hidden;
        document.getElementById('modeBtn').classList.toggle('open', opening);
        if (opening) slideOpen(mp); else slideClose(mp);
      }
      return;
    }
    if (!t.closest('.mbar')) {
      var mp2 = document.getElementById('modePanel');
      if (mp2 && !mp2.hidden) {
        document.getElementById('modeBtn').classList.remove('open');
        slideClose(mp2);
      }
    }

    var fold = t.closest('[data-fold]');
    if (fold) { foldToggle(fold.dataset.fold); return; }

    /* 開始使用：原地換成登入表單，不跳轉。
       已經登入的人不會走到這裡（登入閘會先把他送回首頁）。 */
    if (t.closest('#lpGo')) {
      gateStep = 'login';
      vLogin();
      var first = document.getElementById('lgEmail');
      if (first) setTimeout(function () { first.focus(); }, 260);
      return;
    }

    /* 登入 ↔ 註冊 也在原地換，不要為了切換表單重畫整頁 */
    var swap = t.closest('[data-gate]');
    if (swap) {
      e.preventDefault();
      gateStep = swap.dataset.gate;
      (gateStep === 'register' ? vRegister : vLogin)();
      return;
    }

    /* ---- 搜尋抽屜 ---- */
    if (t.closest('#searchBtn') && !narrowBar.matches) return;   // 寬螢幕沒有這顆
    if (t.closest('#searchBtn')) {
      var sd = document.getElementById('searchDrawer');
      var sb = document.getElementById('searchBtn');
      if (sd) {
        if (sd.hidden) {
          sb.classList.add('open');
          slideOpen(sd);
          document.getElementById('search').focus();
        } else {
          sb.classList.remove('open');
          slideClose(sd);
        }
      }
      return;
    }
    /* ⚠️ 點外面收起搜尋框**只在手機**。電腦版的搜尋框一直都在，
       之前這裡沒分，點頁面任何地方就把電腦版的搜尋框藏掉，旁邊的按鈕跟著位移。 */
    if (narrowBar.matches && !t.closest('#searchDrawer') && !t.closest('#searchBtn')) {
      var sd2 = document.getElementById('searchDrawer');
      if (sd2 && !sd2.hidden) {
        document.getElementById('searchBtn').classList.remove('open');
        slideClose(sd2);
      }
    }

    /* 停權。⚠️ 一定要有理由——沒有理由的停權就是任意封鎖，
       而且被停的人沒有東西可以申訴。 */
    var sus = t.closest('[data-sus]');
    if (sus) {
      var sid = sus.dataset.sus;
      danger({
        title: '停權這個帳號',
        detail: '停權之後他<b>無法登入</b>，但<b>資料一筆都不會刪</b>。' +
                '<br>這個動作會寫進稽核紀錄，而且需要理由。',
        level: 'password',
        ok: '確定停權',
        reason: '停權理由',
        onOk: function (why) {
          API.suspendUser(sid, why).then(function () {
            vAdmin(); toast('已停權', 'ok');
          }).catch(function (err) { toast(err.message || '停權失敗', 'err'); });
        }
      });
      return;
    }

    var unsus = t.closest('[data-unsus]');
    if (unsus) {
      var uid = unsus.dataset.unsus;
      API.unsuspendUser(uid).then(function () {
        vAdmin(); toast('已解除停權', 'ok');
      }).catch(function (err) { toast(err.message || '解除失敗', 'err'); });
      return;
    }

    /* ---- 帳本切換器 ---- */
    if (t.closest('#gswBtn')) {
      var gp = document.getElementById('gswPanel');
      if (gp) {
        var gOpen = gp.hidden;
        document.getElementById('gswBtn').classList.toggle('open', gOpen);
        if (gOpen) slideOpen(gp); else slideClose(gp);
      }
      return;
    }
    var gpick = t.closest('[data-group]');
    if (gpick) {
      setGroup(gpick.dataset.group);
      // 先把面板往上收完，再重畫——不然一換帳本面板就瞬間消失
      slideClose(document.getElementById('gswPanel'), function () { paintGroups(); paint(); });
      return;
    }
    if (!t.closest('#gsw')) {
      var gp2 = document.getElementById('gswPanel');
      if (gp2 && !gp2.hidden) {
        var gb = document.getElementById('gswBtn');
        if (gb) gb.classList.remove('open');
        slideClose(gp2);
      }
    }

    /* 選了「活動」才要填結束日 */
    var kindSel = t.closest('#gnKind');
    if (kindSel) {
      var wrap = document.getElementById('gnEndWrap');
      if (wrap) wrap.hidden = kindSel.value !== 'temp';
      return;
    }

    /* 有動靜通知我。⚠️ 預設關——開著的話光家用本月就是 93 則。 */
    var gnot = t.closest('[data-gnotify]');
    if (gnot) {
      API.setGroupNotify(gnot.dataset.gnotify, gnot.checked).then(function (r) {
        toast(r.notify ? '這本帳有動靜會通知你' : '已關閉這本帳的通知', 'ok');
      }).catch(function (err) {
        gnot.checked = !gnot.checked;
        toast(err.message || '設定失敗', 'err');
      });
      return;
    }

    /* 結算。⚠️ 它不搬動任何一筆紀錄，也不改變誰看得到——
       只是把這本帳標記結束、之後不能再往裡面記。 */
    var gset = t.closest('[data-gsettle]');
    if (gset) {
      var gid = gset.dataset.gsettle;
      danger({
        title: '結算這本活動帳本',
        detail: '結算之後<b>不能再往裡面記帳</b>，紀錄會留著、也還看得到。' +
                '<br>已經花掉的錢本來就算在你的收支裡，<b>數字不會變</b>。',
        level: 'password',
        ok: '確定結算',
        onOk: function () {
          API.settleGroup(gid).then(function () {
            paintGroups(); vGroups();
            toast('已結算', 'ok');
          }).catch(function (err) { toast(err.message || '結算失敗', 'err'); });
        }
      });
      return;
    }

    /* ---- 家庭 ---- */
    var ia = t.closest('[data-inv-accept]');
    if (ia) {
      ia.disabled = true;
      API.acceptInvite(ia.dataset.invAccept).then(function (r) {
        afterFamilyChange('歡迎加入「' + r.family.name + '」');
      }).catch(function (err) { ia.disabled = false; toast(err.message || '加入失敗', 'err'); });
      return;
    }
    var idc = t.closest('[data-inv-decline]');
    if (idc) {
      API.declineInvite(idc.dataset.invDecline).then(function () {
        toast('已婉拒', 'ok'); paint();
      }).catch(function (err) { toast(err.message || '操作失敗', 'err'); });
      return;
    }
    var icn = t.closest('[data-inv-cancel]');
    if (icn) {
      API.declineInvite(icn.dataset.invCancel).then(function () {
        toast('已取消邀請', 'ok'); vMembers();
      }).catch(function (err) { toast(err.message || '操作失敗', 'err'); });
      return;
    }
    var ir = t.closest('[data-invrole]');
    if (ir) {
      INV.role = ir.dataset.invrole;
      Array.prototype.forEach.call(ir.parentNode.children, function (b) { b.classList.toggle('on', b === ir); b.setAttribute('aria-pressed', b === ir); });
      return;
    }
    var cr = t.closest('[data-codrole]');
    if (cr) {
      INV.codeRole = cr.dataset.codrole;
      Array.prototype.forEach.call(cr.parentNode.children, function (b) { b.classList.toggle('on', b === cr); b.setAttribute('aria-pressed', b === cr); });
      return;
    }
    var isd = t.closest('[data-inv-send]');
    if (isd) {
      isd.disabled = true;
      API.sendInvite({ userId: isd.dataset.invSend, role: INV.role }).then(function () {
        toast('邀請送出了，等' + (INV.found ? INV.found.name : '對方') + '按「加入」', 'ok');
        vMembers();
      }).catch(function (err) { isd.disabled = false; toast(err.message || '送不出去', 'err'); });
      return;
    }
    if (t.closest('[data-code-new]')) {
      API.createInviteCode({ role: INV.codeRole }).then(function (c) {
        paintCodes(); toast('邀請碼 ' + c.code + ' 產生好了', 'ok');
      }).catch(function (err) { toast(err.message || '產生失敗', 'err'); });
      return;
    }
    var cp = t.closest('[data-copy]');
    if (cp) {
      var txt = cp.dataset.copy;
      (navigator.clipboard && navigator.clipboard.writeText
        ? navigator.clipboard.writeText(txt) : Promise.reject())
        .then(function () { toast('已複製 ' + txt, 'ok'); })
        .catch(function () { toast('複製不了，請手動記下：' + txt, 'info'); });
      return;
    }

    /* ---- 帳本管理 ---- */
    var lgh = t.closest('[data-lg]');
    if (lgh) { ledgerToggle(lgh.dataset.lg); return; }

    var gopen = t.closest('[data-gopen]');
    if (gopen) {
      setGroup(gopen.dataset.gopen);
      paintGroups();
      location.hash = '#/entry';
      return;
    }
    var garch = t.closest('[data-garch]');
    if (garch) {
      /* 兩段式：第一下先問，第二下才真的做。
         ⚠️ 封存會讓那本帳從切換器和統計裡消失，看起來跟刪除一樣——
         使用者按下去之前必須知道會發生什麼。 */
      if (garch.dataset.sure !== '1') {
        garch.dataset.sure = '1';
        garch.textContent = '確定封存？';
        garch.classList.add('gx--sure');
        setTimeout(function () {
          if (!garch.isConnected) return;
          garch.dataset.sure = '0';
          garch.textContent = '封存';
          garch.classList.remove('gx--sure');
        }, 4000);
        return;
      }
      API.archiveGroup(garch.dataset.garch).then(function () {
        if (GROUP === garch.dataset.garch) setGroup('all');
        paintGroups(); vGroups();
        toast('已封存。紀錄一筆都沒刪，在下面「已封存」可以復原', 'ok');
      }).catch(function (err) { toast(err.message || '封存失敗', 'err'); });
      return;
    }

    var grest = t.closest('[data-grestore]');
    if (grest) {
      API.updateGroup(grest.dataset.grestore, { archived: false }).then(function (g) {
        paintGroups(); vGroups();
        toast('「' + g.name + '」回來了', 'ok');
      }).catch(function (err) { toast(err.message || '復原失敗', 'err'); });
      return;
    }
    var gdel = t.closest('[data-gdel]');
    if (gdel) {
      var b = gdel.dataset.gdel.split('|');
      danger({
        title: '把這個人移出帳本',
        detail: '他會失去這本帳<b>所有紀錄</b>的存取，' +
                '<b>包含他自己記的那些</b>——紀錄是屬於帳本的。',
        level: 'full',
        ok: '確定移出',
        onOk: function () {
          API.removeGroupMember(b[0], b[1]).then(function () {
            paintGroups(); vGroups();
            toast('已移出', 'ok');
          }).catch(function (err) { toast(err.message || '移不出去', 'err'); });
        }
      });
      return;
    }

    /* ---- 階段性提醒 ---- */
    var atg = t.closest('[data-atoggle]');
    if (atg) {
      var c = atg.dataset.atoggle.split('|');
      API.updateAlert(c[0], { enabled: c[1] === '1' }).then(function () {
        paintAlerts();
      }).catch(function (err) { toast(err.message || '改不了', 'err'); });
      return;
    }
    var adel = t.closest('[data-adel]');
    if (adel) {
      API.deleteAlert(adel.dataset.adel).then(function () {
        paintAlerts(); toast('門檻刪掉了', 'ok');
      }).catch(function (err) { toast(err.message || '刪不掉', 'err'); });
      return;
    }

    var demo = t.closest('[data-demo]');
    if (demo) {
      document.getElementById('lgEmail').value = demo.dataset.demo;
      document.getElementById('lgPw').value = 'demo1234';
      document.getElementById('lgPw').focus();
      return;
    }

    if (t.closest('#avaDel')) {
      API.deleteAvatar().then(function () {
        paintWho(); vProfile(); toast('已改回文字頭像', 'ok');
      }).catch(function (err) { toast(err.message || '移除失敗', 'err'); });
      return;
    }

    /* ---- 模式切換：兩者互斥 ---- */
    var md = t.closest('[data-mode]');
    if (md) {
      if (MODE === md.dataset.mode) return;
      MODE = md.dataset.mode;
      batch = null;
      Array.prototype.forEach.call(document.querySelectorAll('.mode'), function (x) {
        var on = x.dataset.mode === MODE;
        x.classList.toggle('on', on);
        var tag = x.querySelector('.tag');
        tag.className = 'tag tag--' + (on ? 'info' : 'na');
        tag.textContent = on ? '使用中' : '已停用';
      });
      renderMode();
      toast(MODE === 'para' ? '已切換到段落記帳' : '已切換到單筆手動', 'ok');
      return;
    }

    /* ---- 段落記帳 ---- */
    if (t.closest('#paraEx')) {
      document.getElementById('paraText').value =
        '早上買早餐55，中午跟同事吃飯320，下午在全家買咖啡，晚上加油1200，今天打工賺了1500';
      document.getElementById('paraGo').click();
      return;
    }

    var pgo = t.closest('#paraGo');
    if (pgo) {
      var txt = document.getElementById('paraText').value.trim();
      if (!txt) { toast('請先寫一段話', 'err'); return; }
      pgo.disabled = true;
      pgo.innerHTML = '<span class="btn__sp"></span>解析中';
      API.nlpParseBatch(txt).then(function (r) {
        pgo.disabled = false; pgo.textContent = '解析這段話';
        renderBatch(r);
      }).catch(function (err) {
        pgo.disabled = false; pgo.textContent = '解析這段話';
        toast('解析失敗：' + err.message, 'err');
      });
      return;
    }

    var bdel = t.closest('[data-bdel]');
    if (bdel) {
      var bi = Number(bdel.dataset.bdel);
      batch.splice(bi, 1);
      if (!batch.length) {
        document.getElementById('paraOut').innerHTML = '';
        toast('已全部移除', 'ok');
        return;
      }
      renderBatch({ items: batch, note: '' });
      return;
    }

    if (t.closest('#paraSave')) {
      syncBatch();
      var bad = batch.filter(function (x) { return x.missing && x.missing.length; }).length;
      if (bad) { toast('還有 ' + bad + ' 筆缺欄位', 'err'); return; }
      var n = batch.length;
      // 記進目前正在看的那一本帳
      if (GROUP !== 'all' && batch.length) batch[0].groupId = GROUP;
      API.nlpConfirmBatch(batch).then(function () {
        document.getElementById('paraOut').innerHTML = '';
        document.getElementById('paraText').value = '';
        batch = null;
        loadTx();
        toast('已一次寫入 ' + n + ' 筆', 'ok');
      }).catch(function (err) { toast('寫入失敗：' + err.message, 'err'); });
      return;
    }

    if (t.closest('#paraCancel')) {
      document.getElementById('paraOut').innerHTML = '';
      batch = null;
      return;
    }

    /* ---- 單筆手動 ---- */
    if (t.closest('#singleSave')) {
      var btn = t.closest('#singleSave');
      var box = document.getElementById('entryBox');
      var v = {};
      Array.prototype.forEach.call(box.querySelectorAll('[data-s]'), function (i) {
        v[i.dataset.s] = i.value;
      });
      if (!v.amount) { toast('金額是必填的', 'err'); return; }

      /* 存進去之後要刪掉得驗密碼，所以寫入前先讓人看一眼。
         把要寫的內容放在按鈕上，再按一次才真的寫——
         段落記帳本來就有確認步驟，單筆手動不該比它更容易出錯。 */
      if (btn.dataset.sure !== '1') {
        var cn = (DATA_CATS[v.cat] || v.cat);
        btn.dataset.sure = '1';
        btn.textContent = '再按一次寫入　' +
          (v.kind === 'income' ? '+' : '−') + money(Number(v.amount)) + '・' + cn;
        btn.classList.add('btn--sure');
        setTimeout(function () {
          if (!btn.isConnected) return;
          btn.dataset.sure = '0';
          btn.textContent = '寫入這一筆';
          btn.classList.remove('btn--sure');
        }, 4000);
        return;
      }

      API.createTransaction({
        date: v.date, amount: Number(v.amount), kind: v.kind, cat: v.cat,
        merchant: v.merchant, note: v.note,
        // 記進目前正在看的那一本帳；看「全部」就交給後端決定
        groupId: GROUP === 'all' ? null : GROUP
      }).then(function () {
        renderMode(); loadTx(); toast('已寫入一筆', 'ok');
      }).catch(function (err) { toast('寫入失敗：' + err.message, 'err'); });
      return;
    }

    if (t.closest('#singleClear')) { renderMode(); return; }

    var del = t.closest('[data-del]');
    if (del) {
      var did = del.dataset.del;
      danger({
        title: '刪除這筆紀錄',
        detail: '刪掉就<b>救不回來</b>了。輸入密碼確認這是你本人。',
        level: 'password',
        onOk: function () {
          API.deleteTransaction(did).then(function () {
            loadTx(); toast('已刪除', 'ok');
          }).catch(function (err) { toast('刪除失敗：' + err.message, 'err'); });
        }
      });
      return;
    }

    var f = t.closest('[data-f]');
    if (f && f.tagName === 'BUTTON') {
      F[f.dataset.f] = f.dataset.v;
      Array.prototype.forEach.call(document.querySelectorAll('[data-f="' + f.dataset.f + '"]'),
        function (x) { if (x.tagName === 'BUTTON') x.classList.toggle('on', x === f); });
      loadTx();
      return;
    }

    var sp = t.closest('[data-sp]');
    if (sp) { STAT.period = sp.dataset.sp; vStats(); return; }

  });

  /* ============================================================
     登入 / 註冊 / 個人資料 的事件
     ============================================================ */
  function busy(form, on, label) {
    var b = form.querySelector('button[type=submit]');
    if (!b) return;
    if (on) { b.dataset.t = b.textContent; b.textContent = label; b.disabled = true; }
    else { b.textContent = b.dataset.t || b.textContent; b.disabled = false; }
  }

  /* 登入成功之後要做的事都一樣：重畫身分、開通知、回總覽 */
  function afterLogin(d) {
    ME = null;                      // 同上：路由閘要重新問一次這個人是誰
    document.body.classList.remove('is-out');
    paintWho();
    if (global.Notify) { global.Notify.reset(); global.Notify.start(); }
    location.hash = '#/';
    paint();
    toast('歡迎回來，' + (d && d.user ? d.user.name : ''), 'ok');
  }

  /* 建議的搜尋：邊打邊篩。 */
  var advTimer = null;
  document.addEventListener('input', function (e) {
    if (e.target.id !== 'advq') return;
    var v = e.target.value;
    clearTimeout(advTimer);
    advTimer = setTimeout(function () { ADVQ = v; paintAdvices(); }, 220);
  });

  document.addEventListener('submit', function (e) {
    var f = e.target;

    if (f.id === 'loginF') {
      e.preventDefault();
      busy(f, true, '登入中…');
      API.login({
        email: document.getElementById('lgEmail').value,
        password: document.getElementById('lgPw').value
      }).then(afterLogin).catch(function (err) {
        busy(f, false);
        toast(err.message || '登入失敗', 'err');
      });
      return;
    }

    if (f.id === 'regF') {
      e.preventDefault();
      busy(f, true, '建立中…');
      API.register({
        name: document.getElementById('rgName').value,
        email: document.getElementById('rgEmail').value,
        password: document.getElementById('rgPw').value,
        savingsGoal: Number(document.getElementById('rgGoal').value) || 0
      }).then(function (d) {
        afterLogin(d);
        toast('帳號建好了', 'ok');
      }).catch(function (err) {
        busy(f, false);
        toast(err.message || '註冊失敗', 'err');
      });
      return;
    }

    if (f.id === 'famNewF') {
      e.preventDefault();
      busy(f, true, '建立中…');
      API.createFamily({ name: document.getElementById('famName').value }).then(function (r) {
        busy(f, false);
        afterFamilyChange('「' + r.family.name + '」建好了，現在可以邀請家人');
      }).catch(function (err) { busy(f, false); toast(err.message || '建立失敗', 'err'); });
      return;
    }
    if (f.id === 'famJoinF') {
      e.preventDefault();
      busy(f, true, '加入中…');
      API.joinFamily({ code: document.getElementById('famCode').value }).then(function (r) {
        busy(f, false);
        afterFamilyChange('歡迎加入「' + r.family.name + '」');
      }).catch(function (err) { busy(f, false); toast(err.message || '加入失敗', 'err'); });
      return;
    }
    if (f.id === 'invFindF') {
      e.preventDefault();
      busy(f, true, '找…');
      API.lookupUser(document.getElementById('invEmail').value).then(function (r) {
        busy(f, false); paintFound(r);
      }).catch(function (err) { busy(f, false); paintFound({ msg: err.message }); });
      return;
    }

    if (f.id === 'gnewF') {
      e.preventDefault();
      busy(f, true, '建立中…');
      var kind = (document.getElementById('gnKind') || {}).value || 'standing';
      API.createGroup({
        name: document.getElementById('gnName').value,
        color: document.getElementById('gnColor').value,
        kind: kind,
        endsOn: kind === 'temp'
          ? (document.getElementById('gnEnd') || {}).value : null
      }).then(function (g) {
        busy(f, false);
        /* 開完就收起來。開帳本是一次性動作，不像記帳會連記好幾筆——
           建好之後該看到的是「我現在有哪幾本」，不是一張空白表單。 */
        FOLD.gnew = false;
        paintGroups(); vGroups();
        toast('「' + g.name + '」開好了', 'ok');
      }).catch(function (err) {
        busy(f, false);
        toast(err.message || '建立失敗', 'err');
      });
      return;
    }

    if (f.id === 'finF') {
      e.preventDefault();
      busy(f, true, '儲存中…');
      var pick = function (name) {
        return [].slice.call(f.querySelectorAll('[name="' + name + '"]:checked'))
          .map(function (i) { return i.value; });
      };
      API.setFinanceProfile({
        style: (pick('finStyle')[0] || null),
        goals: pick('finGoal'),
        habits: pick('finHabit'),
        note: document.getElementById('finNote').value
      }).then(function () {
        busy(f, false);
        toast('記下了。之後的財務建議會參考這些', 'ok');
      }).catch(function (err) {
        busy(f, false);
        toast(err.message || '儲存失敗', 'err');
      });
      return;
    }

    if (f.id === 'anewF') {
      e.preventDefault();
      busy(f, true, '加入中…');
      API.createAlert({
        percent: Number(document.getElementById('anPct').value),
        groupId: document.getElementById('anGroup').value || null
      }).then(function () {
        busy(f, false);
        paintAlerts();
        toast('門檻加好了', 'ok');
      }).catch(function (err) {
        busy(f, false);
        toast(err.message || '加不了', 'err');
      });
      return;
    }

    if (f.id === 'profF') {
      e.preventDefault();
      var y = document.getElementById('pfYear').value;
      busy(f, true, '儲存中…');
      API.updateProfile({
        displayName: document.getElementById('pfName').value,
        birthYear: y === '' ? null : Number(y)
      }).then(function () {
        busy(f, false);
        paintWho();
        vProfile();
        toast('已儲存', 'ok');
      }).catch(function (err) {
        busy(f, false);
        toast(err.message || '存不起來', 'err');
      });
      return;
    }

    if (f.id === 'pwF') {
      e.preventDefault();
      busy(f, true, '更改中…');
      API.changePassword({
        oldPassword: document.getElementById('pwOld').value,
        newPassword: document.getElementById('pwNew').value
      }).then(function () {
        busy(f, false);
        f.reset();
        toast('密碼已更改', 'ok');
      }).catch(function (err) {
        busy(f, false);
        toast(err.message || '改不了', 'err');
      });
      return;
    }
  });

  /* 大頭貼：選檔 → 瀏覽器縮圖 → 送 data URI */
  document.addEventListener('change', function (e) {
    if (e.target.id !== 'avaF') return;
    var file = e.target.files && e.target.files[0];
    if (!file) return;
    toast('處理圖片中…', 'info');
    shrink(file).then(function (uri) {
      return API.uploadAvatar(uri);
    }).then(function () {
      paintWho();
      vProfile();
      toast('大頭貼換好了', 'ok');
    }).catch(function (err) {
      toast(err.message || '上傳失敗', 'err');
    });
  });

  document.addEventListener('change', function (e) {
    var al = e.target.closest ? e.target.closest('[data-allow]') : null;
    if (al) {
      var av = Number(al.value);
      if (isNaN(av) || av < 0) { toast('零用金要是 0 以上的數字', 'err'); return; }
      API.setAllowance(al.dataset.allow, av).then(function (r) {
        toast('每月給 ' + (r.wardName || '他') + ' ' + money(av), 'ok');
      }).catch(function (err) { toast('設定失敗：' + err.message, 'err'); });
      return;
    }

    /* 加人：收合列裡的下拉選單，選了就加 */
    var ga = e.target.closest ? e.target.closest('[data-gaddsel]') : null;
    if (ga) {
      var uid = ga.value;
      if (!uid) return;
      ga.disabled = true;
      API.addGroupMember(ga.dataset.gaddsel, uid).then(function () {
        paintGroups(); vGroups();
        toast('加進去了', 'ok');
      }).catch(function (err) {
        ga.disabled = false; ga.value = '';
        toast(err.message || '加不進去', 'err');
      });
      return;
    }

    var gg = e.target.closest ? e.target.closest('[data-ggoal]') : null;
    if (gg) {
      var gv = Number(gg.value);
      if (isNaN(gv) || gv < 0) { toast('目標要是 0 以上的數字', 'err'); return; }
      API.setSavingsGoal(null, gv, gg.dataset.ggoal).then(function (r) {
        toast('「' + (r.groupName || '這本帳') + '」的月目標改為 ' + money(gv), 'ok');
        paintGroups();
      }).catch(function (err) { toast('設定失敗：' + err.message, 'err'); });
      return;
    }

    var g = e.target.closest ? e.target.closest('[data-goal]') : null;
    if (g) {
      var v = Number(g.value);
      if (isNaN(v) || v < 0) { toast('存款目標要是 0 以上的數字', 'err'); return; }
      API.setSavingsGoal(g.dataset.goal, v).then(function (m) {
        toast(m.name + ' 的每月存款目標改為 ' + money(v), 'ok');
        paint();
      }).catch(function (err) { toast('設定失敗：' + err.message, 'err'); });
      return;
    }
    var s = e.target.closest ? e.target.closest('select[data-f]') : null;
    if (s) { F[s.dataset.f] = s.value; loadTx(); }
    if (e.target.closest && e.target.closest('[data-b]')) {
      // 收支方向改了，分類選項要跟著換
      if (e.target.dataset.b === 'kind') { syncBatch(); renderBatch({ items: batch, note: '' }); }
      else syncBatch();
    }
  });

  document.addEventListener('input', function (e) {
    if (e.target.closest && e.target.closest('[data-b]')) syncBatch();
  });

  document.addEventListener('keydown', function (e) {
    // 段落是多行輸入，用 Ctrl/Cmd + Enter 送出，直接按 Enter 是換行
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && e.target.id === 'paraText') {
      e.preventDefault();
      document.getElementById('paraGo').click();
    }
  });

  var timer = 0;
  $search.addEventListener('input', function () {
    clearTimeout(timer);
    var v = $search.value.trim();
    timer = setTimeout(function () {
      F.q = v;
      var page = (location.hash || '').replace(/^#\/?/, '').split('/')[0];
      if (page === 'entry') loadTx(); else location.hash = '#/entry';
    }, 260);
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && helpOpen) closeHelp();
    if (e.key === 'Escape' && dangerOn) dangerClose();
    if (e.key === 'Escape' && tourAt >= 0) tourEnd();
    if (e.key === 'ArrowRight' && tourAt >= 0) tourGo(1);
    if (e.key === 'ArrowLeft' && tourAt >= 0) tourGo(-1);
  });

  /* 捲動一點點就讓頂欄浮出陰影，知道自己不在最上面 */
  window.addEventListener('resize', function () { if (tourAt >= 0) tourPaint(); });

  window.addEventListener('scroll', function () {
    document.body.classList.toggle('scrolled', window.scrollY > 4);
  }, { passive: true });

  window.addEventListener('hashchange', paint);

  (function () {
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') acctMenu(false);
    });
  })();

  /* 更早的版本有一個顯示 API 模式的小徽章。那是給開發者看的，
     介面上已經拿掉——這裡留一個保險，元素不在就不要炸。 */
  var $mode = document.getElementById('mode');
  if ($mode) $mode.textContent = API.mode === 'http' ? API.base : '示範資料';
  API.authState().then(function (a) {
    if (a.loggedIn) { paintWho(); paintGroups(); }
    paint();
  });

  /* 監管通知：輪詢 + 音效 + 鈴鐺。實作在 js/notify.js
     沒登入的時候不要輪詢——會一路 401，還會在登入頁叮一聲。 */
  /* notify.js 需要它來跳提示。
     ⚠️ 沒掛出去的話 notify.js 的 `if (!global.toast) return;` 會靜靜地跳過——
     不會報錯，只是提示永遠不出現，很難發現。 */
  global.toast = toast;

  API.authState().then(function (a) {
    if (a.loggedIn && global.Notify) global.Notify.start();

    /* 第一次打開才問。網址帶 ?tour=1 可以重看一次。 */
    if (!a.loggedIn) return;
    if (/[?&]tour=1/.test(location.search)) {
      try { localStorage.removeItem(TOUR_KEY); } catch (e) {}
      API.me().then(function (m) {
        if (!m.user.isPlatformAdmin) setTimeout(tourStart, 600);
      });
    } else {
      setTimeout(tourAsk, 900);
    }
  });
})(window);
