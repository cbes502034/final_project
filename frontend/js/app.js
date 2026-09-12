/* ============================================================
   app.js — 家庭記帳與財務控管系統 前端
   ------------------------------------------------------------
   資料一律走 API.*（見 js/api.js），不直接讀 window.DATA。
   ============================================================ */
(function (global) {
  'use strict';

  var API = global.API;
  var $view = document.getElementById('view');

  /* 側欄收合。記在 localStorage，下次打開維持上次的樣子。 */
  (function () {
    var K = 'fambudget.rail';
    var min = false;
    try { min = localStorage.getItem(K) === '1'; } catch (e) {}
    document.body.classList.toggle('rail-min', min);

    /* 收起來之後只剩圖示，滑過去要看得到名字。
       直接拿標籤的文字當 title，不用在 HTML 裡重寫一遍。 */
    Array.prototype.forEach.call(
      document.querySelectorAll('.nav__i, .docs__i'), function (b) {
        var t = b.querySelector('.nav__t, span');
        if (t && !b.title) b.title = t.textContent.trim();
      });
    document.addEventListener('click', function (e) {
      if (!e.target.closest || !e.target.closest('#railx')) return;
      var now = !document.body.classList.contains('rail-min');
      document.body.classList.toggle('rail-min', now);
      try { localStorage.setItem(K, now ? '1' : '0'); } catch (err) {}
      var b = document.getElementById('railx');
      if (b) b.title = now ? '展開側欄' : '收合側欄';
    });
  })();

  /* 頂欄的兩個方案。用網址挑：?bar=text 或 ?bar=icon，預設 text。
     挑定之後把這段拿掉、只留選中的那一套樣式。 */
  (function () {
    var m = /[?&]bar=(text|icon)/.exec(location.search);
    var pick = m ? m[1] : (function () {
      try { return localStorage.getItem('fambudget.bar') || 'text'; } catch (e) { return 'text'; }
    })();
    if (m) { try { localStorage.setItem('fambudget.bar', pick); } catch (e) {} }
    document.body.classList.add('bar-' + pick);
  })();

  /* 展示用帳號。mock 模式的登入頁會列出來，免得評審還要猜 email。
     接上真後端（API.mode === 'http'）之後就不顯示了。 */
  var DEMO = [
    { name: '林建國 · 管理者', email: 'jianguo@lin.tw' },
    { name: '陳淑芬 · 家長',   email: 'shufen@lin.tw' },
    { name: '林宇涵 · 成員',   email: 'yuhan@lin.tw' },
    { name: '林宇軒 · 成員',   email: 'yuxuan@lin.tw' }
  ];
  var $title = document.getElementById('ptitle');
  var $sub = document.getElementById('psub');
  var $search = document.getElementById('search');
  var $toasts = document.getElementById('toasts');

  var ME = null;
  var F = { userId: 'all', kind: 'all', source: 'all', q: '' };

  /* 目前在看哪一本帳。'all' = 全部（我看得到的所有群組合起來）。
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
  var draft = null;                       // 自然語言解析後、尚未確認的暫存

  /* ---------- 小工具 ---------- */
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function el(h) { var d = document.createElement('div'); d.innerHTML = h.trim(); return d.firstChild; }
  function money(n) { return 'NT$ ' + Number(n || 0).toLocaleString('en-US'); }
  function pct(x) { return Math.round((x || 0) * 100) + '%'; }

  var ROLE_TW = { master: '管理者', parent: '家長', member: '成員' };

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

  var SV_TW = { safe: '達標中', near: '接近上限', over: '存不到目標' };

  /* 存款目標狀態卡。level: safe / near / over */
  function savingsCard(sv, who) {
    var lv = sv.level;
    var pct100 = Math.min(100, Math.round(sv.ratio * 100));
    var over = lv === 'over';
    return '<div class="svg-card svg-card--' + lv + ' rise">' +
      '<div class="svg-card__h">' +
        '<span class="svg-card__ic">' + (over ? '!' : (lv === 'near' ? '~' : '✓')) + '</span>' +
        '<span class="svg-card__t">' +
          (over ? (who ? esc(who) + '這個月存不到目標' : '這個月存不到目標')
                : (lv === 'near' ? '快接近可支配上限了' : '存款目標達標中')) + '</span>' +
        '<span class="tag tag--' + (over ? 'down' : (lv === 'near' ? 'warn' : 'up')) + '">' +
          SV_TW[lv] + '</span>' +
      '</div>' +
      '<div class="svg-card__bar"><i style="width:' + pct100 + '%"></i>' +
        '<em style="left:100%"></em></div>' +
      '<div class="svg-card__nums">' +
        svN('每月存款目標', money(sv.goal)) +
        svN('可支配上限', money(sv.allowance), '收入 − 目標') +
        svN('本月已支出', money(sv.used)) +
        svN(over ? '超出上限' : '還可以花',
            money(over ? sv.shortfall : Math.max(0, sv.left)),
            over ? '這個月會少存這麼多' : '') +
      '</div>' +
      (over
        ? '<div class="svg-card__msg">照目前的支出，這個月實際只能存下 <b>' +
          money(Math.max(0, sv.actual)) + '</b>，比目標少 <b>' + money(sv.shortfall) + '</b>。</div>'
        : (lv === 'near'
          ? '<div class="svg-card__msg">已用掉可支配額度的 <b>' + pct100 +
            '%</b>。再花 ' + money(Math.max(0, sv.left)) + ' 就會影響到存款目標。</div>'
          : '')) +
      '</div>';
  }

  function svN(k, v, hint) {
    return '<div class="svg-n"><span class="svg-n__k">' + esc(k) + '</span>' +
      '<span class="svg-n__v">' + v + '</span>' +
      (hint ? '<span class="svg-n__h">' + esc(hint) + '</span>' : '') + '</div>';
  }

  /* ============================================================
     01 我的總覽
     ============================================================ */
  function vHome() {
    head('我的總覽', '本月收支、預算使用狀況、最近幾筆');
    $view.innerHTML = '<div class="page">' + skeleton(4, 'skel__k') + '</div>';

    Promise.all([API.summary({ scope: 'me', groupId: GROUP }), API.budgets(), API.me()])
      .then(function (r) {
        var d = r[0], b = r[1], m = r[2];
        var h = '<div class="page"><div class="kpis">';
        h += kpi('本月收入', d.income, '', d.period, 'ok', 0);
        h += kpi('本月支出', d.expense, '', d.count + ' 筆紀錄', 'warn', 1);
        h += kpi('結餘', d.net, '', '儲蓄率 ' + pct(d.rate), d.net >= 0 ? 'a' : 'crit', 2);
        h += kpi(d.savings.level === 'over' ? '短少' : '可再支出',
                 d.savings.level === 'over' ? d.savings.shortfall : Math.max(0, d.savings.left),
                 '', '存款目標 ' + money(d.savings.goal),
                 d.savings.level === 'over' ? 'crit' : (d.savings.level === 'near' ? 'warn' : 'ok'), 3);
        h += '</div>';

        // 存款目標狀態，超支時放最上面
        if (d.savings) h += savingsCard(d.savings, null);

        if (m.guardedBy && m.guardedBy.length) {
          h += '<div class="note note--warn"><div class="note__k">誰看得到你的紀錄</div><p>' +
            m.guardedBy.map(function (g) { return '<b>' + esc(g.name) + '</b>'; }).join('、') +
            ' 可以看到你的完整收支明細。</p></div>';
        }

        var mine = b.budgets.filter(function (x) { return x.user === m.user.id; });
        if (mine.length) {
          h += '<div class="sec"><h2 class="sec__t">預算使用狀況</h2>' +
               '<span class="sec__n">MONTHLY BUDGET</span></div><div class="card rise">';
          h += mine.map(function (x) {
            return '<div class="bgt"><div class="bgt__k">' +
              '<span class="dot" style="background:' + x.catColor + '"></span>' + esc(x.catName) + '</div>' +
              '<div class="bgt__t"><i style="width:' + Math.min(100, x.pct * 100) +
              '%;background:' + (x.over ? 'var(--down)' : x.catColor) + '"></i></div>' +
              '<div class="bgt__v' + (x.over ? ' is-over' : '') + '">' +
              money(x.used) + ' / ' + money(x.limit) + '</div></div>';
          }).join('') + '</div>';
        }

        h += '<div class="sec"><h2 class="sec__t">支出分類</h2></div>';
        h += '<div class="charts"><div class="card rise">' + donut(d.byCat, d.expense) + '</div>' +
          '<div class="card rise" style="animation-delay:80ms">' +
          '<div class="card__h"><span class="card__t">近 6 個月</span></div>' +
          barChart(d.monthly) + '</div></div>';

        h += '<div class="sec"><h2 class="sec__t">最近的紀錄</h2>' +
             '<button class="btn btn--sm" data-nav="entry" style="margin-left:auto">去記帳 ▸</button></div>' +
             '<div id="recent">' + skeleton(4) + '</div></div>';
        $view.innerHTML = h;
        animate();
        return API.transactions({});
      }).then(function (d) {
        var box = document.getElementById('recent');
        if (!box || !d) return;
        box.innerHTML = d.transactions.slice(0, 6).map(function (t) { return txRow(t); }).join('') ||
          emptyState('還沒有紀錄', '到「記帳」頁用一句話記下第一筆。');
      }).catch(function (e) { $view.innerHTML = '<div class="page">' + errState(e) + '</div>'; });
  }

  function kpi(k, v, unit, sub, mod, i, plain) {
    return '<div class="kpi kpi--' + mod + '" style="animation-delay:' + (i * 60) + 'ms">' +
      '<div class="kpi__k">' + esc(k) + '</div>' +
      '<div class="kpi__v" style="font-size:' + (plain ? '36' : '25') + 'px">' +
      (plain ? '<span data-count="' + v + '">0</span>' : money(v)) +
      '<small>' + esc(unit) + '</small></div>' +
      '<div class="kpi__s">' + esc(sub) + '</div></div>';
  }

  /* 圓環圖：純 SVG */
  function donut(byCat, total) {
    var R = 62, C = 2 * Math.PI * R, off = 0;
    var arcs = byCat.map(function (c) {
      var frac = total ? c.amount / total : 0;
      var seg = '<circle cx="80" cy="80" r="' + R + '" fill="none" stroke="' + c.color +
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
        return '<div class="dnt__i"><span class="dot" style="background:' + c.color + '"></span>' +
          '<span class="dnt__n">' + esc(c.name) + '</span>' +
          '<span class="dnt__v">' + money(c.amount) + '</span>' +
          '<span class="dnt__p">' + pct(total ? c.amount / total : 0) + '</span></div>';
      }).join('') + '</div></div>';
  }

  function barChart(rows) {
    var max = Math.max.apply(null, rows.map(function (r) { return Math.max(r.income, r.expense); })) || 1;
    return '<div class="bars">' + rows.map(function (r, i) {
      return '<div class="bars__g">' +
        '<div class="bars__p">' +
          '<i style="height:' + (r.income / max * 100) + '%;background:var(--up);animation-delay:' + (i * 60) + 'ms"></i>' +
          '<i style="height:' + (r.expense / max * 100) + '%;background:var(--warn);animation-delay:' + (i * 60 + 30) + 'ms"></i>' +
        '</div><div class="bars__k">' + esc(r.m.slice(5)) + '</div></div>';
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
  function txRow(t, hit) {
    return '<div class="tx' + (hit && hit === t.id ? ' is-hit' : '') + '">' +
      '<div class="tx__c" style="background:' + t.catColor + '22;color:' + t.catColor +
        ';border-color:' + t.catColor + '55">' + esc(t.catName.slice(0, 2)) + '</div>' +
      '<div class="tx__m"><div class="tx__t">' + esc(t.merchant || t.catName) +
        (t.source === 'nlp' ? ' <span class="tag tag--soft">段落記帳</span>' : '') + '</div>' +
        '<div class="tx__s">' + esc(t.date) + '　' + esc(t.userName) +
        (t.note ? '　' + esc(t.note) : '') +
        (t.raw ? '<br><span class="tx__raw">原句「' + esc(t.raw) + '」</span>' : '') + '</div></div>' +
      '<div class="tx__a' + (t.kind === 'income' ? ' is-in' : '') + '">' +
        (t.kind === 'income' ? '+' : '−') + money(t.amount).replace('NT$ ', '') + '</div>' +
      /* 別人的紀錄就是不給刪除鈕，不用再掛一個「唯讀」標籤。
         同一句話在一頁上重複十次不會更清楚，只會變成雜訊——
         該講的在抬頭講一次就好。 */
      (isMine(t)
        ? '<button class="btn btn--sm" data-del="' + esc(t.id) + '">刪除</button>'
        : '') +
      '</div>';
  }

  /* ============================================================
     02 記帳（自然語言輸入）
     ============================================================ */
  var MODE = 'para';          // 'para' 段落批次 ｜ 'single' 單筆手動。兩者互斥
  var batch = null;           // 段落解析結果，尚未寫入

  function vEntry() {
    head('記帳', '');
    var h = '<div class="page">';

    /* ---- 模式切換：抽屜 ----
       兩張帶說明的大卡片收成一條。要用哪一種是常態性的選擇，
       選好之後幾乎不會再動，不值得一直佔著版面。 */
    h += '<div class="mbar">' +
      '<button class="mbar__b" id="modeBtn">' +
        '<span class="mbar__n">' + (MODE === 'para' ? '段落記帳' : '單筆手動') + '</span>' +
        helpBtn(MODE === 'para' ? 'entry' : '') +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
          '<path d="m6 9 6 6 6-6"/></svg>' +
      '</button>' +
      '<div class="mbar__p" id="modePanel" hidden>' +
        modeRow('para', '段落記帳', '一次寫一整段，自動切成好幾筆') +
        modeRow('single', '單筆手動', '一次填一筆，欄位自己選') +
      '</div>' +
    '</div>';


    h += '<div id="entryBox"></div>';

    h += '<div class="sec"><h2 class="sec__t">收支明細</h2>' +
      '<span class="sec__n">TRANSACTIONS</span></div>';
    h += filterBar() + '<div id="txList">' + skeleton(6) + '</div></div>';
    $view.innerHTML = h;
    renderMode();
    loadTx();
  }

  function modeRow(id, title, desc) {
    return '<button class="mbar__i' + (MODE === id ? ' on' : '') +
      '" data-mode="' + id + '">' +
      '<span class="mbar__t">' + esc(title) + '</span>' +
      '<span class="mbar__d">' + esc(desc) + '</span></button>';
  }

  function renderMode() {
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
    var today = global.DATA.meta.period + '-10';
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

  function filterBar() {
    var ks = [['all', '全部'], ['expense', '支出'], ['income', '收入']];
    var ss = [['all', '不分來源'], ['nlp', '段落記帳'], ['manual', '手動輸入']];
    return '<div class="bar"><div class="chips">' + ks.map(function (k) {
        return '<button class="chip' + (F.kind === k[0] ? ' on' : '') +
          '" data-f="kind" data-v="' + k[0] + '">' + k[1] + '</button>';
      }).join('') + '</div>' +
      '<select class="sel" data-f="source">' + ss.map(function (s) {
        return '<option value="' + s[0] + '"' + (F.source === s[0] ? ' selected' : '') + '>' + s[1] + '</option>';
      }).join('') + '</select>' +
      '<span style="flex:1"></span>' +
      '<button class="btn btn--sm" id="reset">重置示範資料</button></div>';
  }

  function loadTx() {
    var box = document.getElementById('txList');
    if (!box) return;
    API.transactions(Object.assign({}, F, { groupId: GROUP })).then(function (d) {
      box.innerHTML = d.transactions.length
        ? d.transactions.map(function (t) { return txRow(t); }).join('')
        : emptyState('沒有符合的紀錄', '換個篩選條件，或記一筆新的。');
    }).catch(function (e) { box.innerHTML = errState(e); });
  }

  /* ============================================================
     03 家庭總覽
     ============================================================ */
  function vFamily() {
    head('家庭總覽', '你自己 ＋ 被指派給你監管的成員');
    $view.innerHTML = '<div class="page">' + skeleton(4, 'skel__k') + '</div>';
    Promise.all([API.summary({ scope: 'family', groupId: GROUP }), API.me(), API.budgets()])
      .then(function (r) {
        var d = r[0], m = r[1], b = r[2];
        var h = '<div class="page">';
        /* 門檻不是角色，是「有沒有人被指派給你看」。
           一個沒有監管對象的管理者，家庭總覽上也只有自己，沒有意義。 */
        if ((m.visible || []).length <= 1) {
          h += '<div class="note note--warn"><div class="note__k">你只看得到自己</div>' +
            '<p>目前沒有成員指派給你。</p></div></div>';
          $view.innerHTML = h;
          return;
        }
        h += '<div class="kpis">';
        h += kpi('家庭收入', d.income, '', d.period, 'ok', 0);
        h += kpi('家庭支出', d.expense, '', d.members.length + ' 位成員', 'warn', 1);
        h += kpi('結餘', d.net, '', '儲蓄率 ' + pct(d.rate), 'a', 2);
        h += kpi('可檢視成員', d.members.length, '人', ROLE_TW[m.user.role] + '權限', 'a', 3, true);
        h += '</div>';

        if (d.savings) h += savingsCard(d.savings, '全家');

        var overs = d.members.filter(function (u) { return u.savingsLevel === 'over'; });
        if (overs.length && d.savings.level !== 'over') {
          h += '<div class="note note--crit"><div class="note__k">總體達標，但不是每個人都達標</div><p>' +
            '家庭整體看起來安全，是因為結餘較多的成員把其他人的超支蓋過去了。' +
            '實際上有 <b>' + overs.length + ' 位成員存不到自己的目標</b>：' +
            overs.map(function (u) {
              return '<b>' + esc(u.name) + '</b>（短少 ' + money(u.shortfall) + '）';
            }).join('、') + '。</p></div>';
        }

        h += '<div class="sec"><h2 class="sec__t">各成員本月狀況</h2></div>';
        h += '<div class="rows">' + d.members.map(function (u, i) {
          var over = u.expense > u.budget;
          var bs = b.budgets.filter(function (x) { return x.user === u.id && x.over; });
          return '<article class="row" style="animation-delay:' + (i * 50) + 'ms;' +
            'grid-template-columns:44px 1fr 150px 110px">' +
            ava(u) +
            '<div class="row__m"><div class="row__top">' +
              '<span class="row__act" style="font-size:15px">' + esc(u.name) + '</span>' +
              '<span class="tag tag--' + (u.role === 'master' ? 'done' : 'soft') + '">' +
              ROLE_TW[u.role] + '</span>' +
              (u.savingsLevel === 'over'
                ? '<span class="tag tag--down">存不到目標 · 短少 ' + money(u.shortfall) + '</span>'
                : (u.savingsLevel === 'near' ? '<span class="tag tag--warn">接近上限</span>'
                                             : '<span class="tag tag--up">存款達標</span>')) +
              (bs.length ? '<span class="tag tag--MEDIUM">' + bs.length + ' 項分類超支</span>' : '') +
            '</div><div class="row__sub">收入 ' + money(u.income) + '　支出 ' + money(u.expense) +
            '　存款目標 ' + money(u.savingsGoal) + '　可支配 ' + money(u.allowance) + '</div></div>' +
            '<div class="sla"><div class="sla__v"' + (over ? ' style="color:var(--down)"' : '') + '>' +
              pct(u.expense / u.budget) + '</div>' +
              '<div class="sla__b"><i style="width:' + Math.min(100, u.expense / u.budget * 100) +
              '%;background:' + (over ? 'var(--down)' : 'var(--up)') + '"></i></div></div>' +
            '<div class="row__do"><b class="num" style="color:' +
              (u.income - u.expense >= 0 ? 'var(--up)' : 'var(--down)') + '">' +
              (u.income - u.expense >= 0 ? '+' : '') +
              Number(u.income - u.expense).toLocaleString('en-US') + '</b></div>' +
            '</article>';
        }).join('') + '</div>';

        h += '<div class="sec"><h2 class="sec__t">超出預算的項目</h2></div>';
        var over = b.budgets.filter(function (x) { return x.over; });
        h += over.length ? '<div class="card">' + over.map(function (x) {
          return '<div class="bgt"><div class="bgt__k"><span class="dot" style="background:' +
            x.catColor + '"></span>' + esc(x.userName) + '　' + esc(x.catName) + '</div>' +
            '<div class="bgt__t"><i style="width:100%;background:var(--down)"></i></div>' +
            '<div class="bgt__v is-over">' + money(x.used) + ' / ' + money(x.limit) +
            '（' + pct(x.pct) + '）</div></div>';
        }).join('') + '</div>' : emptyState('沒有超支項目', '本月所有分類都在預算內。');
        h += '</div>';
        $view.innerHTML = h;
        animate();
      }).catch(function (e) { $view.innerHTML = '<div class="page">' + errState(e) + '</div>'; });
  }

  /* ============================================================
     04 統計（月／年）
     ============================================================ */
  function vStats() {
    head('統計', '月與年兩個時間基準');
    $view.innerHTML = '<div class="page">' + skeleton(4) + '</div>';
    API.summary({ scope: 'family', groupId: GROUP }).then(function (d) {
      var h = '<div class="page"><div class="bar"><div class="chips">' +
        [['month', '按月'], ['year', '按年']].map(function (p) {
          return '<button class="chip' + (STAT.period === p[0] ? ' on' : '') +
            '" data-sp="' + p[0] + '">' + p[1] + '</button>';
        }).join('') + '</div></div>';

      var rows = STAT.period === 'month'
        ? d.monthly.map(function (r) { return { k: r.m, income: r.income, expense: r.expense }; })
        : d.yearly.map(function (r) { return { k: r.y, income: r.income, expense: r.expense, partial: r.partial }; });

      h += '<div class="card rise"><div class="card__h"><span class="card__t">' +
        (STAT.period === 'month' ? '近 6 個月' : '近 3 年') + '收支對照</span></div>' +
        '<div class="tbl" style="border:0"><table><thead><tr>' +
        '<th>' + (STAT.period === 'month' ? '月份' : '年度') + '</th><th>收入</th><th>支出</th>' +
        '<th>結餘</th><th>儲蓄率</th><th></th></tr></thead><tbody>' +
        rows.map(function (r) {
          var net = r.income - r.expense, rate = r.income ? net / r.income : 0;
          return '<tr><td><b>' + esc(r.k) + '</b>' +
            (r.partial ? ' <span class="tag tag--soft">未完整</span>' : '') + '</td>' +
            '<td class="mono">' + money(r.income) + '</td>' +
            '<td class="mono">' + money(r.expense) + '</td>' +
            '<td class="mono"><b style="color:' + (net >= 0 ? 'var(--up)' : 'var(--down)') +
            '">' + money(net) + '</b></td>' +
            '<td class="mono">' + pct(rate) + '</td>' +
            '<td style="width:140px"><div class="sla__b"><i style="width:' +
            Math.max(0, Math.min(100, rate * 200)) + '%;background:' +
            (rate >= 0.2 ? 'var(--up)' : (rate >= 0 ? 'var(--warn)' : 'var(--down)')) +
            '"></i></div></td></tr>';
        }).join('') + '</tbody></table></div></div>';

      if (STAT.period === 'year') {
        h += '<div class="note note--warn"><div class="note__k">2026 年尚未結束</div><p>' +
          '年度統計在當年度會標示「未完整」，<b>不要直接跟完整年度比較</b>。</p></div>';
      }

      h += '<div class="charts" style="margin-top:12px"><div class="card rise">' +
        '<div class="card__h"><span class="card__t">支出分類佔比</span></div>' +
        donut(d.byCat, d.expense) + '</div>' +
        '<div class="card rise" style="animation-delay:80ms">' +
        '<div class="card__h"><span class="card__t">近 6 個月趨勢</span></div>' +
        barChart(d.monthly) + '</div></div></div>';
      $view.innerHTML = h;
    }).catch(function (e) { $view.innerHTML = '<div class="page">' + errState(e) + '</div>'; });
  }

  /* ============================================================
     05 AI 財務建議
     ============================================================ */
  function vAdvice() {
    head('財務建議', '每月結算後由模型產生，每一條都附可驗算的依據');
    $view.innerHTML = '<div class="page">' + skeleton(4) + '</div>';
    API.advices().then(function (d) {
      var h = '<div class="page">';
      h += d.advices.map(function (a, i) {
        var cls = a.level === 'warn' ? 'crit' : (a.level === 'ok' ? '' : 'warn');
        return '<div class="adv adv--' + a.level + '" style="animation-delay:' + (i * 70) + 'ms">' +
          '<div class="adv__h">' +
            '<span class="tag tag--' + (a.level === 'warn' ? 'CRITICAL' :
              (a.level === 'ok' ? 'done' : 'MEDIUM')) + '">' +
            (a.level === 'warn' ? '需注意' : (a.level === 'ok' ? '良好' : '參考')) + '</span>' +
            '<span class="adv__t">' + esc(a.title) + '</span>' +
            '<span class="adv__m">' + esc(a.scope === 'family' ? '家庭' : a.userName) +
            '　' + esc(a.period) + '</span></div>' +
          '<p class="adv__b">' + esc(a.body) + '</p>' +
          '<div class="adv__basis"><div class="adv__bk">依據（可自行驗算）</div><ul>' +
            a.basis.map(function (b) { return '<li>' + esc(b) + '</li>'; }).join('') + '</ul></div>' +
          '<div class="adv__sug"><div class="adv__bk">建議</div><ul>' +
            a.suggest.map(function (b) { return '<li>' + esc(b) + '</li>'; }).join('') + '</ul></div>' +
          '</div>';
      }).join('');

      h += '<div class="sec"><h2 class="sec__t">建議的邊界規則</h2>' +
        '<span class="sec__n">GUARDRAILS</span></div>';
      h += '<div class="tbl"><table><thead><tr><th>規則</th><th>為什麼</th></tr></thead><tbody>' +
        d.rules.map(function (r) {
          return '<tr><td><b>' + esc(r.rule) + '</b></td><td>' + esc(r.why) + '</td></tr>';
        }).join('') + '</tbody></table></div>';

      h += '</div>';
      $view.innerHTML = h;
    }).catch(function (e) { $view.innerHTML = '<div class="page">' + errState(e) + '</div>'; });
  }

  /* ============================================================
     06 成員與權限
     ============================================================ */
  /* 誰的存款目標我能改：我自己；未成年的由 master 代設。
     監管者看得到子女的數字，但不能替成年的子女決定要存多少。 */
  function canSetGoal(u, d) {
    if (u.id === d.me) return true;
    var me = d.members.filter(function (x) { return x.id === d.me; })[0];
    return !!(me && me.role === 'master' && u.age !== null && u.age < 18);
  }

  function vMembers() {
    head('成員與權限', '角色、監管關係、以及每個角色看得到什麼');
    $view.innerHTML = '<div class="page">' + skeleton(5) + '</div>';
    API.members().then(function (d) {
      PERMS = d;   // 問號要用，見 HELP.perms
      var h = '<div class="page"><div class="sec"><h2 class="sec__t">家庭成員' +
        helpBtn('perms') + '</h2>' +
        '<span class="sec__n">' + d.members.length + ' 人</span></div>';
      h += '<div class="rows">' + d.members.map(function (u, i) {
        var seeable = (d.visible || []).indexOf(u.id) >= 0;
        var wards = d.guardianships.filter(function (g) { return g.guardian === u.id; });
        var by = d.guardianships.filter(function (g) { return g.ward === u.id; });
        return '<article class="row' + (seeable
            ? ' row--open" data-open="' + esc(u.id) + '" title="看 ' + esc(u.name) + ' 的記帳紀錄'
            : '" title="你沒有監管這個人，看不到他的紀錄') +
          '" style="animation-delay:' + (i * 50) +
          'ms;grid-template-columns:44px 1fr 104px">' +
          ava(u) +
          '<div class="row__m"><div class="row__top">' +
            '<span class="row__act" style="font-size:15px">' + esc(u.name) + '</span>' +
            '<span class="tag tag--' + (u.role === 'master' ? 'done' :
              (u.role === 'parent' ? 'MEDIUM' : 'soft')) + '">' + ROLE_TW[u.role] + '</span>' +
            (u.id === d.me ? '<span class="tag tag--na">目前登入</span>' : '') +
            (u.age < 18 ? '<span class="tag tag--info">未成年 · 目標由管理者代設</span>' : '') +
          '</div><div class="row__sub">' +
            (wards.length ? '監管：' + wards.map(function (g) { return esc(g.wardName); }).join('、') : '') +
            (wards.length && by.length ? '　｜　' : '') +
            (by.length ? '<b style="color:var(--warn)">被 ' +
              by.map(function (g) { return esc(g.guardianName); }).join('、') + ' 監管</b>' : '') +
            (!wards.length && !by.length ? '無監管關係' : '') +
          '</div></div>' +
          /* 這一列只講身分：誰、什麼角色、跟誰有監管關係。
             存款目標是財務設定，不屬於這裡——自己的在「個人資料」，
             代未成年設的在那個人的紀錄頁。擠在這裡又醜又難按。

             看得到才給按鈕，而且一直看得到。
             ⚠️ 之前這顆是 hover 才浮出來的，於是「哪幾列點得下去」
             要滑過去才知道——使用者當然會去點一個點不進去的。 */
          '<div class="row__go2">' +
            (seeable ? '<span class="rowbtn">看紀錄 →</span>' : '') +
          '</div>' +
          '</article>';
      }).join('') + '</div>';



      h += '';

      h += '</div>';
      $view.innerHTML = h;
    }).catch(function (e) { $view.innerHTML = '<div class="page">' + errState(e) + '</div>'; });
  }


  /* ============================================================
     單一成員的記帳紀錄（唯讀）

     從兩個地方進來：
       成員與權限點某一列       → #/member/U3
       通知點某一則             → #/member/U3/T1051（那一筆會標起來）
     ============================================================ */
  function vMember(id, hit) {
    head('成員紀錄', '看得到，不能改');
    $view.innerHTML = '<div class="page">' + skeleton(4) + '</div>';

    /* 先問「我看不看得到」，確認之後才去拿明細。
       沒權限就不要發那個請求——後端會回 403，前端也不該去撞。 */
    Promise.all([API.me(), API.members()])
      .then(function (r) {
        var me = r[0], d = r[1];
        var u = d.members.filter(function (x) { return x.id === id; })[0];

        if (!u) {
          $view.innerHTML = '<div class="page"><div class="note note--warn">' +
            '<div class="note__k">找不到這個人</div>' +
            '<p>這個家庭裡沒有 <code>' + esc(id) + '</code> 這位成員。</p>' +
            '</div></div>';
          return;
        }

        /* 看得到誰是後端說了算（me.visible）。
           前端這裡擋一次是為了給一句人話，並且不要去發一個註定被拒絕的請求。
           真正的把關在 API：帶了沒權限的 userId 會回 403（不是空陣列——
           回空的話，前端分不出「這個人沒記帳」和「你不能看」）。 */
        if ((me.visible || []).indexOf(id) < 0) {
          $view.innerHTML = '<div class="page"><div class="note note--warn">' +
            '<div class="note__k">看不到這個人的紀錄</div>' +
            '<p>你沒有被指派監管 <b>' + esc(u.name) + '</b>。<br>' +
            '監管關係由管理者建立，而且雙方都看得到——系統不提供隱藏監管。</p>' +
            '</div>' + backLink() + '</div>';
          return;
        }

        return API.transactions({ userId: id }).then(function (tx) {
          render(me, d, u, tx);
        });
      })
      .catch(function (e) {
        $view.innerHTML = '<div class="page">' + errState(e) + '</div>';
      });

    function render(me, d, u, tx) {
      var mine = id === d.me;
      var by = d.guardianships.filter(function (g) { return g.ward === id; });

      var h = '<div class="page">' + backLink();

      h += '<div class="card mhead">' +
        ava(u, 'ava--xl') +
        '<div class="mhead__m">' +
          '<div class="mhead__top">' +
            '<span class="mhead__n">' + esc(u.name) + '</span>' +
            '<span class="tag tag--' + (u.role === 'master' ? 'done' :
              (u.role === 'parent' ? 'MEDIUM' : 'soft')) + '">' +
              ROLE_TW[u.role] + '</span>' +
            (mine ? '<span class="tag tag--na">這是你自己</span>' : '') +
          '</div>' +
          (by.length && !mine
            ? '<p class="mhead__s"><span class="mhead__h">被 ' +
              by.map(function (g) { return esc(g.guardianName); }).join('、') +
              ' 監管</span></p>'
            : '') +
        '</div>' +
        '<div class="mhead__n2"><b>' + tx.total + '</b><span>筆紀錄</span></div>' +
      '</div>';

      /* 未成年的存款目標由管理者代設——設定的地方就放在
         看得到他紀錄的這一頁，不要塞回成員名冊那張表。 */
      if (canSetGoal(u, d) && !mine) {
        h += '<div class="sec"><h2 class="sec__t">每月存款目標' + helpBtn('goal') + '</h2></div>' +
          '<div class="card prof__goal">' +
            '<input class="goal__i" type="number" min="0" ' +
              'data-goal="' + esc(u.id) + '" value="' + (u.savingsGoal || 0) + '">' +
          '</div>';
      }

      h += '<div class="sec"><h2 class="sec__t">收支明細</h2>' +
        '<span class="sec__n">' + tx.total + ' 筆</span></div>';

      h += '<div class="txs" id="mtx">' + (tx.transactions.length
        ? tx.transactions.map(function (t) { return txRow(t, hit); }).join('')
        : emptyState('還沒有紀錄', esc(u.name) + '這個月還沒有記過帳。')) + '</div></div>';

      $view.innerHTML = h;

      // 標起來的那一筆捲進畫面，不然在長清單裡要自己找
      var el = document.querySelector('.tx.is-hit');
      if (el) setTimeout(function () {
        el.scrollIntoView({ block: 'center', behavior: 'smooth' });
      }, 120);
    }
  }

  function backLink() {
    return '<a class="back" href="#/members">← 回成員與權限</a>';
  }


  /* ============================================================
     群組（帳本）

     記帳除了有「分類」，還有「這筆算在哪一本帳上」。
     分類回答錢花在什麼，群組回答這筆屬於哪一份預算。
     每一本帳可以各自設一個每月存款目標。
     ============================================================ */
  function vGroups() {
    head('群組', '一個家庭可以開好幾本帳，各自有自己的存款目標');
    $view.innerHTML = '<div class="page">' + skeleton(4) + '</div>';

    Promise.all([API.groups({ includeArchived: true }), API.members()])
      .then(function (r) {
      var d = r[0], fam = r[1];

      var live = d.groups.filter(function (g) { return !g.archived; });
      var gone = d.groups.filter(function (g) { return g.archived; });

      var h = '<div class="page">' +
        '';

      h += '<div class="sec"><h2 class="sec__t">我的帳本' + helpBtn('books') + '</h2>' +
        '<span class="sec__n">' + live.length + ' 本</span></div>';

      h += '<div class="rows">' + live.map(function (g, i) {
        return '<article class="row" style="animation-delay:' + (i * 50) +
          'ms;grid-template-columns:44px 1fr 150px 108px">' +
          '<div class="ava" style="background:' + esc(g.color) + '22;color:' + esc(g.color) +
            ';border-color:' + esc(g.color) + '55">' + esc(g.icon) + '</div>' +
          '<div class="row__m"><div class="row__top">' +
            '<span class="row__act" style="font-size:15px">' + esc(g.name) + '</span>' +
            (g.canEdit ? '<span class="tag tag--done">你建立的</span>'
                       : '<span class="tag tag--soft">你是成員</span>') +
            (g.id === GROUP ? '<span class="tag tag--na">目前在看</span>' : '') +
          '</div><div class="row__sub">' +
            esc(g.memberNames.join('、')) +
            (g.note ? '　｜　' + esc(g.note) : '') +
          '</div></div>' +
          '<div class="row__do">' +
            '<span class="goal"><label>這本帳的月目標</label>' +
            '<input class="goal__i" type="number" min="0" ' +
              'data-ggoal="' + esc(g.id) + '" value="' + (g.goal || 0) + '"></span>' +
          '</div>' +
          '<div class="row__go2">' +
            '<span class="rowbtn" data-gopen="' + esc(g.id) + '">' + g.count + ' 筆 →</span>' +
            (g.canEdit ? '<button class="gx" data-garch="' + esc(g.id) +
                         '" title="收起這本帳。紀錄不會被刪掉，之後可以復原">封存</button>' : '') +
          '</div>' +
        '</article>';
      }).join('') + '</div>';

      // ---- 建立 ----
      h += '<div class="sec"><h2 class="sec__t">開一本新的</h2></div>' +
        '<form class="card gnew" id="gnewF">' +
          '<label class="fld"><span>名字</span>' +
            '<input type="text" id="gnName" placeholder="例如 旅遊基金、寵物開銷" required></label>' +
          '<label class="fld"><span>顏色</span>' +
            '<select id="gnColor">' +
              ['#6C9FFB:藍', '#8B7CF0:紫', '#5FB8D9:青', '#6EE7B7:綠',
               '#FBBF6E:橙', '#FB8A8F:紅'].map(function (c) {
                var p = c.split(':');
                return '<option value="' + p[0] + '">' + p[1] + '</option>';
              }).join('') +
            '</select></label>' +
          '<div><button class="btn btn--go" type="submit">建立</button></div>' +
        '</form>';

      // ---- 成員 ----
      var editable = d.groups.filter(function (g) { return g.canEdit; });
      if (editable.length) {
        h += '<div class="sec"><h2 class="sec__t">誰在哪一本帳裡</h2></div>';
        h += '<div class="card gmem">' + editable.map(function (g) {
          var inside = g.members;
          var outside = fam.members.filter(function (u) { return inside.indexOf(u.id) < 0; });
          return '<div class="gmem__g">' +
            '<div class="gmem__t"><span class="gsw__d" style="background:' + esc(g.color) +
              '"></span>' + esc(g.name) + '</div>' +
            '<div class="gmem__l">' + inside.map(function (u) {
              var m = fam.members.filter(function (x) { return x.id === u; })[0] || {};
              return '<span class="chip">' + esc(m.name || u) +
                (u === g.owner ? '' :
                  '<button data-gdel="' + esc(g.id) + '|' + esc(u) + '" title="移出">×</button>') +
                '</span>';
            }).join('') + '</div>' +
            (outside.length
              ? '<div class="gmem__add">加人：' + outside.map(function (u) {
                  return '<button class="chip chip--add" data-gadd="' + esc(g.id) + '|' +
                    esc(u.id) + '">＋ ' + esc(u.name) + '</button>';
                }).join('') + '</div>'
              : '') +
          '</div>';
        }).join('') + '</div>';
      }

      // ---- 已封存 ----
      if (gone.length) {
        h += '<div class="sec"><h2 class="sec__t">已封存' + helpBtn('archive') + '</h2>' +
          '<span class="sec__n">' + gone.length + ' 本</span></div>';
        h += '<div class="card arch">' +
          '<div class="arch__l">' + gone.map(function (g) {
            return '<div class="arch__i">' +
              '<span class="gsw__d" style="background:' + esc(g.color) + '"></span>' +
              '<span class="arch__n">' + esc(g.name) + '</span>' +
              '<span class="arch__c">' + g.count + ' 筆紀錄還在</span>' +
              (g.canEdit
                ? '<button class="btn btn--sm" data-grestore="' + esc(g.id) + '">復原</button>'
                : '') +
            '</div>';
          }).join('') + '</div></div>';
      }


      $view.innerHTML = h + '</div>';
    }).catch(function (e) { $view.innerHTML = '<div class="page">' + errState(e) + '</div>'; });
  }


  /* ============================================================
     說明彈窗

     介面上不放長篇解釋——需要解釋的地方，標題旁邊放一個問號，
     想知道的人自己點。點開時背景模糊並且鎖住，
     讓注意力只剩下這段說明。

     每一則都用「使用者聽得懂的話」寫，不寫系統怎麼實作。
     ============================================================ */
  var HELP = {
    allowance: {
      t: '可支配上限是怎麼算的',
      b: '<p>先看這個月進來多少錢，扣掉你設定的<b>每月存款目標</b>，' +
         '剩下的就是這個月可以放心花的錢。</p>' +
         '<p class="hp__f">本月收入　−　每月存款目標　＝　可支配上限</p>' +
         '<p>舉個例子：這個月收入 68,000，你希望存下 20,000，' +
         '那可以花的就是 48,000。花超過的話，這個月就存不到原本想存的金額。</p>' +
         '<p>所以進度條看的不是「你花了多少」，而是' +
         '<b>「離存不到錢還有多遠」</b>。</p>'
    },
    goal: {
      t: '每月存款目標',
      b: '<p>你希望每個月存下多少錢。填了之後，系統才知道你還剩多少可以花。</p>' +
         '<p>這個數字<b>隨時可以改</b>，改了只影響現在和以後。' +
         '過去的月份會沿用當時設定的數字——否則十月回頭看九月，' +
         '會用現在的標準去評斷當時的自己，那不公平也不準。</p>' +
         '<p>未滿 18 歲的成員，這個數字由家裡的管理者代為設定。</p>'
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
         '<p>家裡的管理者可以建立「監管關係」，被指派之後，' +
         '那個人就看得到你的記帳明細。<b>但他只能看</b>——' +
         '不能修改、不能刪除，也不能登入你的帳號。</p>' +
         '<p>這件事<b>不會偷偷發生</b>：只要有人看得到你，' +
         '你的畫面上就一定看得到是誰。系統不提供隱藏的監管。</p>'
    },
    books: {
      t: '帳本是什麼',
      b: '<p>同一個家庭可以開好幾本帳，例如「家用」「旅遊基金」「我自己的」。' +
         '每一筆記帳都會歸到其中一本。</p>' +
         '<p>分類回答的是「錢花在什麼」，帳本回答的是' +
         '<b>「這筆算在哪一份預算上」</b>。' +
         '所以同樣是吃飯，家庭聚餐算家用，出國吃的算旅遊基金。</p>' +
         '<p>每一本帳可以設<b>自己的每月存款目標</b>，' +
         '右上角切換帳本之後，統計和進度都會跟著那一本走。</p>' +
         '<p>任何人都可以開自己的帳本，不分身分。開的人就是那本帳的管理者。</p>'
    },
    archive: {
      t: '封存會發生什麼事',
      b: '<p>把一本帳收起來不再使用。它會從切換器和統計裡消失，' +
         '<b>但裡面的記帳一筆都不會被刪掉</b>。</p>' +
         '<p>在「已封存」那一區隨時可以把它叫回來，' +
         '回來之後所有紀錄都還在原位。</p>'
    },
    alerts: {
      t: '階段性提醒',
      b: '<p>自己決定在花到幾成的時候提醒你。' +
         '例如設 60%、85%、100% 三個門檻，' +
         '每跨過一個就通知一次。</p>' +
         '<p>算的是<b>可支配額度的幾成</b>，不是收入的幾成。</p>' +
         '<p>同一個門檻<b>一個月只會響一次</b>，' +
         '不會因為你來回記帳就一直被吵。下個月自動重新開始。</p>' +
         '<p>暫時不想被打擾的話，把它關掉就好，設定會留著。</p>'
    },
    budget: {
      t: '預算怎麼用',
      b: '<p>針對某一個分類設一個月的上限，例如餐飲不超過 8,000。</p>' +
         '<p>它跟存款目標是兩件事：<b>存款目標管的是整體</b>' +
         '（這個月要留下多少），<b>預算管的是單一類別</b>' +
         '（這一類最多花多少）。兩個一起看，才知道是哪裡超出去的。</p>'
    },
    advice: {
      t: '財務建議是怎麼來的',
      b: '<p>系統先把你這個月的收支算清楚，' +
         '再把<b>算好的數字</b>交給模型，請它用人話講出來，' +
         '並且給幾個具體可做的調整。</p>' +
         '<p>每一則建議底下都會附上它依據的數字。' +
         '<b>數字是系統算的，不是模型猜的</b>——' +
         '你可以自己核對。</p>'
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
          '<th>管理者</th><th>家長</th><th>成員</th></tr></thead><tbody>' +
          PERMS.permissions.map(function (p) {
            return '<tr><td>' + esc(p.action) + '</td>' +
              cell(p.master) + cell(p.parent) + cell(p.member) + '</tr>';
          }).join('') + '</tbody></table></div>';
      }
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

  /* ---------- 共用 ---------- */
  function head(t, s) { $title.textContent = t; $sub.textContent = s; }

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

  function authShell(title, sub, inner) {
    document.body.classList.add('is-out');
    $view.innerHTML =
      '<div class="gate"><div class="gate__c">' +
        '<div class="gate__b"><span class="brand__n">家庭記帳</span></div>' +
        '<h1 class="gate__t">' + title + '</h1>' +
        '<p class="gate__s">' + sub + '</p>' +
        inner +
      '</div></div>';
  }

  function vLogin() {
    head('登入', '');
    authShell('登入', '記一句話就記一筆帳，家人的支出一起看得見。',
      '<form class="gate__f" id="loginF">' +
        '<label class="fld"><span>Email</span>' +
          '<input type="email" id="lgEmail" autocomplete="username" required></label>' +
        '<label class="fld"><span>密碼</span>' +
          '<input type="password" id="lgPw" autocomplete="current-password" required></label>' +
        '<button class="btn btn--go gate__go" type="submit">登入</button>' +
        '<p class="gate__alt">還沒有帳號？<a href="#/register">建立一個</a></p>' +
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
        '<p class="gate__alt">已經有帳號了？<a href="#/login">回去登入</a></p>' +
      '</form>');
  }

  function vProfile() {
    head('個人資料', '');
    $view.innerHTML = '<div class="page">' + skeleton(3) + '</div>';
    API.me().then(function (m) {
      var u = m.user;
      /* 左右兩欄。大頭貼、存款目標、密碼都只需要半欄的寬度，
         各自獨佔一整條的話，整頁會被拉得很長而且空空的。
         階段性提醒有清單又有新增列，需要整欄，所以放在下面。 */
      var h = '<div class="page">' +
        '<div class="cols"><div class="col">' +

        '<div class="sec"><h2 class="sec__t">大頭貼' + helpBtn('avatar') + '</h2></div>' +
        '<div class="card prof">' +
          '<div class="prof__a" id="profAva">' + ava(u, 'ava--xl') + '</div>' +
          '<div class="prof__m">' +
            '<div class="prof__do">' +
              '<label class="btn btn--sm btn--go">選一張圖' +
                '<input type="file" id="avaF" accept="image/png,image/jpeg,image/webp" hidden></label>' +
              (u.avatarUrl ? '<button class="btn btn--sm" id="avaDel">移除，改用文字</button>' : '') +
            '</div>' +
          '</div>' +
        '</div>' +

        '<div class="sec"><h2 class="sec__t">每月存款目標' + helpBtn('goal') + '</h2></div>' +
        '<div class="card prof__goal">' +
          '<input class="goal__i" type="number" min="0" ' +
            'data-goal="' + esc(u.id) + '" value="' + (u.savingsGoal || 0) + '">' +
        '</div>' +

        '</div><div class="col">' +

        '<div class="sec"><h2 class="sec__t">基本資料</h2></div>' +
        '<form class="card prof__form" id="profF">' +
          '<label class="fld"><span>名字</span>' +
            '<input type="text" id="pfName" value="' + esc(u.name) + '" required></label>' +
          '<label class="fld"><span>出生年份</span>' +
            '<input type="number" id="pfYear" min="1900" max="' + new Date().getFullYear() + '" ' +
              'value="' + (u.birthYear || '') + '" placeholder="例如 1974">' +
            '</label>' +
          '<label class="fld"><span>Email</span>' +
            '<input type="email" value="' + esc(u.email || '') + '" disabled>' +
            '</label>' +
          '<div><button class="btn btn--go" type="submit">儲存</button></div>' +
        '</form>' +

        '<div class="sec"><h2 class="sec__t">密碼</h2></div>' +
        '<form class="card prof__form" id="pwF">' +
          '<label class="fld"><span>目前的密碼</span>' +
            '<input type="password" id="pwOld" autocomplete="current-password" required></label>' +
          '<label class="fld"><span>新密碼</span>' +
            '<input type="password" id="pwNew" autocomplete="new-password" required>' +
            '<em class="fld__h">至少 8 個字</em></label>' +
          '<div><button class="btn" type="submit">更改密碼</button></div>' +
        '</form>' +

        '</div></div>' +

        '<div class="sec"><h2 class="sec__t">階段性提醒' + helpBtn('alerts') + '</h2></div>' +
        '<div class="card" id="alertBox">' + skeleton(2) + '</div>' +

      '</div>';
      $view.innerHTML = h;
      paintAlerts();
    });
  }

  /* ---------------------------------------------------------
     階段性提醒：使用者自己設幾個百分比門檻
     --------------------------------------------------------- */
  function paintAlerts() {
    var box = document.getElementById('alertBox');
    if (!box) return;
    Promise.all([API.alerts(), API.savingsGoals()]).then(function (r) {
      var list = r[0].alerts || [], goals = r[1].goals || [];

      var h = list.length
        ? '<div class="alist">' + list.map(function (a) {
            return '<div class="ai' + (a.enabled ? '' : ' off') + '">' +
              '<span class="ai__p">' + esc(a.percent) + '%</span>' +
              '<span class="ai__s">' + esc(a.groupName) + '</span>' +
              '<button class="ai__t" data-atoggle="' + esc(a.id) + '|' +
                (a.enabled ? '0' : '1') + '">' +
                (a.enabled ? '開著' : '關掉了') + '</button>' +
              '<button class="ai__x" data-adel="' + esc(a.id) + '" title="刪掉">×</button>' +
            '</div>';
          }).join('') + '</div>'
        : '<p class="prof__h">還沒設定</p>';

      h += '<form class="anew" id="anewF">' +
        '<label class="fld"><span>百分比</span>' +
          '<input type="number" id="anPct" min="1" max="200" value="80" required></label>' +
        '<label class="fld"><span>哪一本帳</span>' +
          '<select id="anGroup">' + goals.map(function (g) {
            return '<option value="' + (g.groupId || '') + '">' + esc(g.groupName) +
              (g.goal ? '（目標 ' + money(g.goal) + '）' : '（還沒設目標）') + '</option>';
          }).join('') + '</select></label>' +
        '<div><button class="btn btn--sm btn--go" type="submit">加一個門檻</button></div>' +
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

  /* 群組切換器。只有一本帳的時候不顯示——一個只有一個選項的下拉是雜訊。 */
  function paintGroups() {
    var box = document.getElementById('gsw');
    if (!box) return;
    API.groups().then(function (d) {
      var gs = d.groups || [];
      box.hidden = gs.length < 2;
      if (box.hidden) { setGroup('all'); return; }

      // 選到的群組如果已經看不到了（被移出或封存），退回全部
      if (GROUP !== 'all' && !gs.some(function (g) { return g.id === GROUP; })) setGroup('all');

      var cur = GROUP === 'all'
        ? { icon: '全', name: '全部帳本', color: 'var(--ink-faint)' }
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
          '<span class="ic__d" style="background:' + esc(cur.color) + '"></span>' +
          '<span class="gsw__d" style="background:' + esc(cur.color) + '"></span>' +
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
              '<span class="gsw__d" style="background:' + esc(g.color) + '"></span>' +
              '<span class="gsw__m"><b>' + esc(g.name) + '</b><i>' +
                g.count + ' 筆' + (g.goal ? '　目標 ' + money(g.goal) : '') +
              '</i></span></button>';
          }).join('') +
          '<a class="gsw__more" href="#/groups">管理群組 →</a>' +
        '</div>';
    }).catch(function () { box.hidden = true; });
  }

  function paintWho() {
    API.me().then(function (m) {
      ME = m;
      var w = document.getElementById('who');
      if (w) {
        w.innerHTML = ava(m.user, 'ava--sm') +
          '<span class="who__n">' + esc(m.user.name) + '</span>' +
          '<span class="who__r">' + ROLE_TW[m.user.role] + '</span>' +
          '<button class="who__out" id="logout">登出</button>';
      }
      var f = document.getElementById('famName');
      if (f) f.textContent = m.family.family + '　' + m.family.period;
    });
  }

  /* ---------- 路由 ---------- */
  var ROUTES = { '': vHome, entry: vEntry, family: vFamily, stats: vStats,
                 advice: vAdvice, members: vMembers,
                 login: vLogin, register: vRegister, profile: vProfile,
                 member: vMember, groups: vGroups };

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

      if (a.loggedIn) document.body.classList.remove('is-out');
      (ROUTES[page] || vHome)(parts[1], parts[2]);
      // 看某個成員的紀錄時，左邊仍然亮「成員與權限」
      var lit = page === 'member' ? 'members' : page;
      Array.prototype.forEach.call(document.querySelectorAll('.nav__i'), function (b) {
        b.classList.toggle('on', b.dataset.nav === lit);
      });
    });
  }

  /* ---------- 事件 ---------- */
  document.addEventListener('click', function (e) {
    var t = e.target;
    if (!t.closest) return;

    /* 說明彈窗：開著的時候，除了關閉之外什麼都不能點 */
    if (helpOpen) {
      if (t.closest('#hpX') || t.closest('#hpOk') || !t.closest('.hp__c')) closeHelp();
      e.preventDefault();
      e.stopPropagation();
      return;
    }
    var q = t.closest('[data-help]');
    if (q) { openHelp(q.dataset.help); return; }

    var nav = t.closest('[data-nav]');
    if (nav) { location.hash = '#/' + nav.dataset.nav; return; }

    /* 成員那一列點下去看他的紀錄。
       存款目標的輸入框也在這一列裡，點它不能跳走。 */
    var open = t.closest('[data-open]');
    if (open && !t.closest('input') && !t.closest('label')) {
      location.hash = '#/member/' + open.dataset.open;
      return;
    }

    if (t.closest('#logout') || t.closest('#logout2')) {
      API.logout().then(function () {
        // 先把通知收件匣清掉，不然登出後 DOM 裡還躺著上一個人的明細
        if (global.Notify) { global.Notify.stop(); global.Notify.reset(); }
        document.body.classList.add('is-out');
        location.hash = '#/login';
        paint();
        toast('已登出', 'ok');
      });
      return;
    }

    /* ---- 記帳方式的抽屜 ---- */
    if (t.closest('#modeBtn') && !t.closest('[data-help]')) {
      var mp = document.getElementById('modePanel');
      if (mp) {
        mp.hidden = !mp.hidden;
        document.getElementById('modeBtn').classList.toggle('open', !mp.hidden);
      }
      return;
    }
    if (!t.closest('.mbar')) {
      var mp2 = document.getElementById('modePanel');
      if (mp2 && !mp2.hidden) {
        mp2.hidden = true;
        document.getElementById('modeBtn').classList.remove('open');
      }
    }

    /* ---- 搜尋抽屜 ---- */
    if (t.closest('#searchBtn')) {
      var sd = document.getElementById('searchDrawer');
      var sb = document.getElementById('searchBtn');
      if (sd) {
        sd.hidden = !sd.hidden;
        sb.classList.toggle('open', !sd.hidden);
        document.body.classList.toggle('dw-on', !sd.hidden);
        if (!sd.hidden) document.getElementById('search').focus();
      }
      return;
    }
    if (!t.closest('#searchDrawer') && !t.closest('#searchBtn')) {
      var sd2 = document.getElementById('searchDrawer');
      if (sd2 && !sd2.hidden) {
        sd2.hidden = true;
        document.getElementById('searchBtn').classList.remove('open');
        document.body.classList.remove('dw-on');
      }
    }

    /* ---- 群組切換器 ---- */
    if (t.closest('#gswBtn')) {
      var gp = document.getElementById('gswPanel');
      if (gp) {
        gp.hidden = !gp.hidden;
        // 抽屜拉開時，按鈕本身跟底下的內容都要有反應
        document.getElementById('gswBtn').classList.toggle('open', !gp.hidden);
        document.body.classList.toggle('dw-on', !gp.hidden);
      }
      return;
    }
    var gpick = t.closest('[data-group]');
    if (gpick) {
      setGroup(gpick.dataset.group);
      document.body.classList.remove('dw-on');
      paintGroups();
      paint();
      return;
    }
    if (!t.closest('#gsw')) {
      var gp2 = document.getElementById('gswPanel');
      if (gp2 && !gp2.hidden) {
        gp2.hidden = true;
        var gb = document.getElementById('gswBtn');
        if (gb) gb.classList.remove('open');
        document.body.classList.remove('dw-on');
      }
    }

    /* ---- 群組管理 ---- */
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
    var gadd = t.closest('[data-gadd]');
    if (gadd) {
      var a = gadd.dataset.gadd.split('|');
      API.addGroupMember(a[0], a[1]).then(function () {
        vGroups(); toast('加進去了', 'ok');
      }).catch(function (err) { toast(err.message || '加不進去', 'err'); });
      return;
    }
    var gdel = t.closest('[data-gdel]');
    if (gdel) {
      var b = gdel.dataset.gdel.split('|');
      API.removeGroupMember(b[0], b[1]).then(function () {
        paintGroups(); vGroups();
        toast('已移出。他看不到這本帳的紀錄了', 'ok');
      }).catch(function (err) { toast(err.message || '移不出去', 'err'); });
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
      var box = document.getElementById('entryBox');
      var v = {};
      Array.prototype.forEach.call(box.querySelectorAll('[data-s]'), function (i) {
        v[i.dataset.s] = i.value;
      });
      if (!v.amount) { toast('金額是必填的', 'err'); return; }
      API.createTransaction({
        date: v.date, amount: Number(v.amount), kind: v.kind, cat: v.cat,
        merchant: v.merchant, note: v.note
      }).then(function () {
        renderMode(); loadTx(); toast('已寫入一筆', 'ok');
      }).catch(function (err) { toast('寫入失敗：' + err.message, 'err'); });
      return;
    }

    if (t.closest('#singleClear')) { renderMode(); return; }

    var del = t.closest('[data-del]');
    if (del) {
      API.deleteTransaction(del.dataset.del).then(function () {
        loadTx(); toast('已刪除', 'ok');
      }).catch(function (err) { toast('刪除失敗：' + err.message, 'err'); });
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

    if (t.closest('#reset')) {
      API.reset().then(function (r) {
        if (r.reset === false) { toast(r.note || '此模式不支援重置', 'err'); return; }
        paintWho(); paint(); toast('已還原成示範資料', 'ok');
      });
    }
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
    document.body.classList.remove('is-out');
    paintWho();
    if (global.Notify) { global.Notify.reset(); global.Notify.start(); }
    location.hash = '#/';
    paint();
    toast('歡迎回來，' + (d && d.user ? d.user.name : ''), 'ok');
  }

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

    if (f.id === 'gnewF') {
      e.preventDefault();
      busy(f, true, '建立中…');
      API.createGroup({
        name: document.getElementById('gnName').value,
        color: document.getElementById('gnColor').value
      }).then(function (g) {
        busy(f, false);
        paintGroups(); vGroups();
        toast('「' + g.name + '」開好了', 'ok');
      }).catch(function (err) {
        busy(f, false);
        toast(err.message || '建立失敗', 'err');
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
  });

  /* 捲動一點點就讓頂欄浮出陰影，知道自己不在最上面 */
  window.addEventListener('scroll', function () {
    document.body.classList.toggle('scrolled', window.scrollY > 4);
  }, { passive: true });

  window.addEventListener('hashchange', paint);

  /* 舊版側欄有一個顯示 API 模式的小徽章。那是給開發者看的，
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
  });
})(window);
