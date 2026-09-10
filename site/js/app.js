/* ============================================================
   app.js — 家庭記帳與財務控管系統 前端
   ------------------------------------------------------------
   資料一律走 API.*（見 js/api.js），不直接讀 window.DATA。
   ============================================================ */
(function (global) {
  'use strict';

  var API = global.API;
  var $view = document.getElementById('view');
  var $title = document.getElementById('ptitle');
  var $sub = document.getElementById('psub');
  var $search = document.getElementById('search');
  var $toasts = document.getElementById('toasts');

  var ME = null;
  var F = { user: 'all', kind: 'all', source: 'all', q: '' };
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

    Promise.all([API.summary({ scope: 'me' }), API.budgets(), API.me()])
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
            ' 可以看到你的完整收支明細。<br>' +
            '<b>這是家庭監管設定，系統一律讓被監管者自己也看得到這件事</b>，' +
            '不會有「被偷偷監看」的情況。</p></div>';
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
        box.innerHTML = d.transactions.slice(0, 6).map(txRow).join('') ||
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

  function txRow(t) {
    return '<div class="tx">' +
      '<div class="tx__c" style="background:' + t.catColor + '22;color:' + t.catColor +
        ';border-color:' + t.catColor + '55">' + esc(t.catName.slice(0, 2)) + '</div>' +
      '<div class="tx__m"><div class="tx__t">' + esc(t.merchant || t.catName) +
        (t.source === 'nlp' ? ' <span class="tag tag--soft">語音記帳</span>' : '') + '</div>' +
        '<div class="tx__s">' + esc(t.date) + '　' + esc(t.userName) +
        (t.note ? '　' + esc(t.note) : '') +
        (t.raw ? '<br><span class="tx__raw">原話「' + esc(t.raw) + '」</span>' : '') + '</div></div>' +
      '<div class="tx__a' + (t.kind === 'income' ? ' is-in' : '') + '">' +
        (t.kind === 'income' ? '+' : '−') + money(t.amount).replace('NT$ ', '') + '</div>' +
      '<button class="btn btn--sm" data-del="' + esc(t.id) + '">刪除</button>' +
      '</div>';
  }

  /* ============================================================
     02 記帳（自然語言輸入）
     ============================================================ */
  var MODE = 'para';          // 'para' 段落批次 ｜ 'single' 單筆手動。兩者互斥
  var batch = null;           // 段落解析結果，尚未寫入

  function vEntry() {
    head('記帳', '兩種寫入方式，一次只能用一種');
    var h = '<div class="page">';

    /* ---- 模式切換：選一種，另一種停用 ---- */
    h += '<div class="modes">' +
      modeCard('para', '段落記帳',
        '一次寫一整段，系統自動切成好幾筆',
        '「早上買早餐55，中午吃飯320，今天打工賺了1500」') +
      modeCard('single', '單筆手動',
        '一次填一筆，欄位自己選',
        '傳統表單，不經過模型') +
      '</div>';

    h += '<div class="note note--warn"><div class="note__k">為什麼一次只能用一種</div><p>' +
      '兩種方式同時開著，使用者會不知道自己送出的是哪一份資料，也容易把同一筆重複記兩次。' +
      '<b>選定一種之後，另一種會停用</b>，想換隨時可以切回來，未送出的內容會清掉。</p></div>';

    h += '<div id="entryBox"></div>';

    h += '<div class="sec"><h2 class="sec__t">收支明細</h2>' +
      '<span class="sec__n">TRANSACTIONS</span></div>';
    h += filterBar() + '<div id="txList">' + skeleton(6) + '</div></div>';
    $view.innerHTML = h;
    renderMode();
    loadTx();
  }

  function modeCard(id, title, desc, eg) {
    var on = MODE === id;
    return '<button class="mode' + (on ? ' on' : '') + '" data-mode="' + id + '">' +
      '<span class="mode__r"><i></i></span>' +
      '<span class="mode__m"><span class="mode__t">' + esc(title) + '</span>' +
      '<span class="mode__d">' + esc(desc) + '</span>' +
      '<span class="mode__e">' + esc(eg) + '</span></span>' +
      (on ? '<span class="tag tag--info">使用中</span>'
          : '<span class="tag tag--na">已停用</span>') + '</button>';
  }

  function renderMode() {
    var box = document.getElementById('entryBox');
    if (!box) return;
    box.innerHTML = MODE === 'para' ? paraHTML() : singleHTML();
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

    if (r.note) h += '<div class="prs__n">' + esc(r.note) + '</div>';

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
    var ss = [['all', '不分來源'], ['nlp', '語音記帳'], ['manual', '手動輸入']];
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
    API.transactions(Object.assign({}, F)).then(function (d) {
      box.innerHTML = d.transactions.length
        ? d.transactions.map(txRow).join('')
        : emptyState('沒有符合的紀錄', '換個篩選條件，或記一筆新的。');
    }).catch(function (e) { box.innerHTML = errState(e); });
  }

  /* ============================================================
     03 家庭總覽
     ============================================================ */
  function vFamily() {
    head('家庭總覽', '管理者看得到全家；家長看得到被指派監管的成員');
    $view.innerHTML = '<div class="page">' + skeleton(4, 'skel__k') + '</div>';
    Promise.all([API.summary({ scope: 'family' }), API.me(), API.budgets()])
      .then(function (r) {
        var d = r[0], m = r[1], b = r[2];
        var h = '<div class="page">';
        if (m.user.role === 'member') {
          h += '<div class="note note--warn"><div class="note__k">權限不足</div><p>' +
            '你目前的角色是<b>成員</b>，只看得到自己的紀錄。' +
            '若要檢視家庭總覽，需要管理者調整角色。<br>' +
            '（可以用右上角切換身分，體驗不同角色看到的畫面。）</p></div></div>';
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
            }).join('、') + '。<br>' +
            '<b>看家庭總數會漏掉個人的問題</b>，所以每個人的狀態要分開看。</p></div>';
        }

        h += '<div class="sec"><h2 class="sec__t">各成員本月狀況</h2></div>';
        h += '<div class="rows">' + d.members.map(function (u, i) {
          var over = u.expense > u.budget;
          var bs = b.budgets.filter(function (x) { return x.user === u.id && x.over; });
          return '<article class="row" style="animation-delay:' + (i * 50) + 'ms;' +
            'grid-template-columns:44px 1fr 150px 110px">' +
            '<div class="ava">' + esc(u.avatar) + '</div>' +
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
    API.summary({ scope: 'family' }).then(function (d) {
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
          '年度統計在當年度會標示「未完整」。<b>不要拿未完整年度直接跟完整年度比較</b> —— ' +
          '系統在畫面上明確標出來，避免使用者誤判「今年支出變少了」。</p></div>';
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

      h += '<div class="note note--crit"><div class="note__k">最重要的一條：數字不由模型生成</div><p>' +
        '所有金額、百分比、成長率<b>一律由後端從資料庫算好，再連同結果一起餵給模型</b>，' +
        '模型只負責把數字組織成人看得懂的敘述。<br>' +
        '理由很直接：<b>財務數字算錯會讓使用者做出錯誤決定</b>，' +
        '而語言模型本來就不擅長算術。這條規則跟畫面上「依據」欄位是同一件事的兩面 —— ' +
        '使用者要能自己驗算。</p></div></div>';
      $view.innerHTML = h;
    }).catch(function (e) { $view.innerHTML = '<div class="page">' + errState(e) + '</div>'; });
  }

  /* ============================================================
     06 成員與權限
     ============================================================ */
  function vMembers() {
    head('成員與權限', '角色、監管關係、以及每個角色看得到什麼');
    $view.innerHTML = '<div class="page">' + skeleton(5) + '</div>';
    API.members().then(function (d) {
      var h = '<div class="page"><div class="sec"><h2 class="sec__t">家庭成員</h2>' +
        '<span class="sec__n">' + d.members.length + ' 人</span></div>';
      h += '<div class="rows">' + d.members.map(function (u, i) {
        var wards = d.guardianships.filter(function (g) { return g.guardian === u.id; });
        var by = d.guardianships.filter(function (g) { return g.ward === u.id; });
        return '<article class="row" style="animation-delay:' + (i * 50) +
          'ms;grid-template-columns:44px 1fr 200px">' +
          '<div class="ava">' + esc(u.avatar) + '</div>' +
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
          '<div class="row__do">' +
            '<span class="goal"><label>每月存款目標</label>' +
            '<input class="goal__i" type="number" data-goal="' + esc(u.id) + '" value="' +
            (u.savingsGoal || 0) + '"></span>' +
            (u.id === d.me ? '' :
            '<button class="btn btn--sm" data-switch="' + esc(u.id) + '">切換身分</button>') +
          '</div></article>';
      }).join('') + '</div>';

      h += '<div class="note"><div class="note__k">每月存款目標是註冊時就要填的</div><p>' +
        '註冊流程會請使用者設定「每月想存多少」。系統據此算出<b>可支配上限＝收入 − 存款目標</b>，' +
        '支出超過上限就代表這個月存不到原本設定的金額，總覽頁會直接跳警告。<br>' +
        '目標改動<b>保留歷史不覆蓋</b>（資料表 <code>savings_goals</code> 帶 period_key），' +
        '否則之後回頭看會不知道當時的目標是多少。</p></div>';

      h += '<div class="note"><div class="note__k">監管是雙向可見的</div><p>' +
        '被監管者在自己的總覽頁會看到「誰看得到你的紀錄」。' +
        '<b>系統不提供「隱藏監管」的選項</b> —— 偷偷監看家人的消費會破壞信任，' +
        '而信任正是家庭記帳能持續下去的前提。</p></div>';

      h += '<div class="sec"><h2 class="sec__t">角色</h2></div>';
      h += '<div class="tbl"><table><thead><tr><th>角色</th><th>說明</th></tr></thead><tbody>' +
        d.roles.map(function (r) {
          return '<tr><td><b>' + esc(r.name) + '</b><br><span class="mono" style="color:var(--ink-dim)">' +
            esc(r.id) + '</span></td><td>' + esc(r.desc) + '</td></tr>';
        }).join('') + '</tbody></table></div>';

      h += '<div class="sec"><h2 class="sec__t">權限矩陣</h2>' +
        '<span class="sec__n">PERMISSIONS</span></div>';
      h += '<div class="tbl"><table><thead><tr><th>動作</th><th>管理者</th><th>家長</th><th>成員</th>' +
        '</tr></thead><tbody>' + d.permissions.map(function (p) {
          function cell(v) {
            if (v === 'Y') return '<span class="tag tag--done">可</span>';
            if (v === 'N') return '<span class="tag tag--na">不可</span>';
            return '<span class="tag tag--MEDIUM">' + esc(v) + '</span>';
          }
          return '<tr><td><b>' + esc(p.action) + '</b></td><td>' + cell(p.master) +
            '</td><td>' + cell(p.parent) + '</td><td>' + cell(p.member) + '</td></tr>';
        }).join('') + '</tbody></table></div></div>';
      $view.innerHTML = h;
    }).catch(function (e) { $view.innerHTML = '<div class="page">' + errState(e) + '</div>'; });
  }

  /* ============================================================
     07 模型評測
     ============================================================ */
  function vEval() {
    head('模型評測', '自然語言記帳的抽取準確率 —— 這是本專題的量化成果');
    $view.innerHTML = '<div class="page">' + skeleton(5) + '</div>';
    API.nlpEval().then(function (d) {
      var h = '<div class="page"><div class="tbl"><table><thead><tr>' +
        '<th>任務</th><th>指標</th><th>未微調</th><th>微調後</th><th>目標</th><th>達標</th>' +
        '</tr></thead><tbody>' + d.eval.map(function (e) {
          return '<tr><td><b>' + esc(e.task) + '</b></td><td>' + esc(e.metric) + '</td>' +
            '<td class="mono">' + e.base + '</td>' +
            '<td class="mono"><b style="color:var(--ink)">' + e.ft + '</b></td>' +
            '<td class="mono">' + e.target + '</td>' +
            '<td>' + (e.ft >= e.target ? '<span class="tag tag--done">達標</span>' :
              '<span class="tag tag--CRITICAL">未達</span>') + '</td></tr>';
        }).join('') + '</tbody></table></div>';

      h += '<div class="note"><div class="note__k">最重要的是最後一列</div><p>' +
        '<b>一次輸入完全正確率</b>（日期、金額、方向、分類全部都對）從 0.42 提升到 0.79。' +
        '單看個別欄位的分數會高估實際體驗 —— 使用者在意的是「我講一句話，它有沒有一次記對」，' +
        '只要有一欄錯就要動手改，摩擦就回來了。</p></div>';

      h += '<div class="sec"><h2 class="sec__t">解析範例與難點</h2></div>';
      h += '<div class="tbl"><table><thead><tr><th>使用者說</th><th>解析成</th><th>難在哪</th>' +
        '</tr></thead><tbody>' + d.demo.map(function (x) {
          var c = global.DATA.categories.filter(function (y) { return y.id === x.out.cat; })[0];
          return '<tr><td><b>「' + esc(x.raw) + '」</b></td>' +
            '<td class="mono">' + esc(x.out.date) + '　' +
            (x.out.kind === 'income' ? '+' : '−') + x.out.amount + '　' + esc(c.name) +
            (x.out.merchant ? '　' + esc(x.out.merchant) : '') + '</td>' +
            '<td>' + esc(x.note) + '</td></tr>';
        }).join('') + '</tbody></table></div>';

      h += '<div class="note note--warn"><div class="note__k">評測資料哪裡來</div><p>' +
        '資料表 <code>nlp_parses</code> 會記下每一次的<b>原始輸入、模型輸出、以及使用者修正後的值</b>。' +
        '使用者每改一次，就等於免費標了一筆資料。<br>' +
        '<b>這是本系統的資料飛輪</b>：用得越久，訓練資料越多，模型越準，摩擦越低。</p></div></div>';
      $view.innerHTML = h;
    }).catch(function (e) { $view.innerHTML = '<div class="page">' + errState(e) + '</div>'; });
  }

  /* ============================================================
     08 資料庫架構
     ============================================================ */
  function vSchema() {
    head('資料庫架構', '12 張表與關聯，後端照這個建表');
    $view.innerHTML = '<div class="page">' + skeleton(4, 'skel__k') + '</div>';
    API.schema().then(function (d) {
      var h = '<div class="page"><div class="card rise">' +
        '<div class="card__h"><span class="card__t">關聯圖</span>' +
        '<span class="card__s">' + d.schema.length + ' 張表</span></div>' +
        erDiagram(d.schema, d.relations) + '</div>';

      h += '<div class="sec"><h2 class="sec__t">各表欄位</h2>' +
        '<span class="sec__n">DDL DRAFT</span></div>';
      h += d.schema.map(function (t, i) {
        return '<details class="acc" style="margin-bottom:8px"' + (i === 0 ? ' open' : '') + '>' +
          '<summary class="acc__h"><span class="acc__ic" aria-hidden="true"><i></i><i></i></span>' +
          '<code class="acc__code">' + esc(t.t) + '</code>' +
          '<span class="acc__t">' + esc(t.label) + '</span>' +
          '<span class="acc__en">' + esc(t.note) + '</span></summary>' +
          '<div class="acc__b"><div class="tbl" style="border:0"><table><thead><tr>' +
          '<th>欄位</th><th>型別</th><th>說明</th></tr></thead><tbody>' +
          t.cols.map(function (c) {
            return '<tr><td class="mono"><b>' + esc(c[0]) + '</b></td>' +
              '<td class="mono" style="color:var(--accent)">' + esc(c[1]) + '</td>' +
              '<td>' + esc(c[2]) + '</td></tr>';
          }).join('') + '</tbody></table></div></div></details>';
      }).join('');

      h += '<div class="note"><div class="note__k">四個設計重點</div><p>' +
        '<b>1. 帳號與家庭角色分開。</b> `users` 是登入身分，`family_members` 才是角色 —— ' +
        '一個人可以同時是甲家的管理者、乙家的成員。<br>' +
        '<b>2. 監管關係獨立成表。</b> `guardianships` 有起訖時間，' +
        '解除監管是設 `ended_at` 而不是刪除，因為稽核需要看得到歷史。<br>' +
        '<b>3. `nlp_parses` 是資料飛輪的核心。</b> 記下原始輸入、模型輸出、使用者修正值，' +
        '既是評測來源也是下一輪訓練資料。<br>' +
        '<b>4. `advices.basis_json` 存的是後端算好的數字</b>，不是模型生成的 —— ' +
        '這樣使用者才驗算得了。</p></div>';

      h += '<div class="note note--warn"><div class="note__k">安全與隱私</div><p>' +
        '`password_hash` 用 bcrypt 或 argon2，<b>絕不存明碼</b>。' +
        '`sessions` 只存 refresh token 的雜湊，登出就是設 `revoked_at`。<br>' +
        '`audit_logs` 記錄「誰看了誰的資料」—— 監管功能一旦存在，' +
        '就必須有紀錄可查，否則權限會變成沒人管的黑箱。</p></div></div>';
      $view.innerHTML = h;
    }).catch(function (e) { $view.innerHTML = '<div class="page">' + errState(e) + '</div>'; });
  }

  function erDiagram(schema, rels) {
    var W = 940, H = 580;
    var pos = {
      users:            [380, 40,  170, 62],
      sessions:         [120, 40,  150, 46],
      families:         [680, 40,  170, 50],
      family_members:   [680, 130, 170, 50],
      guardianships:    [680, 220, 170, 50],
      accounts:         [120, 140, 150, 46],
      categories:       [120, 320, 150, 46],
      transactions:     [380, 250, 170, 66],
      nlp_parses:       [380, 380, 170, 50],
      budgets:          [680, 330, 170, 46],
      advices:          [680, 420, 170, 46],
      audit_logs:       [120, 420, 150, 46]
    };
    var meta = {};
    schema.forEach(function (t) { meta[t.t] = t; });
    var core = ['transactions', 'users'];
    var star = ['nlp_parses'];
    var s = '<svg viewBox="0 0 ' + W + ' ' + H + '" style="width:100%;height:auto;display:block">';

    rels.forEach(function (r) {
      var a = pos[r[0]], b = pos[r[1]];
      if (!a || !b) return;
      var ax = a[0] + a[2] / 2, ay = a[1] + a[3] / 2;
      var bx = b[0] + b[2] / 2, by = b[1] + b[3] / 2;
      s += '<path d="M' + ax + ' ' + ay + ' L' + bx + ' ' + ay + ' L' + bx + ' ' + by +
        '" fill="none" stroke="var(--line-2)" stroke-width="1.1"/>';
    });

    Object.keys(pos).forEach(function (k) {
      var p = pos[k], m = meta[k];
      if (!m) return;
      var isCore = core.indexOf(k) >= 0, isStar = star.indexOf(k) >= 0;
      var stroke = isStar ? 'var(--warn)' : (isCore ? 'var(--accent)' : 'var(--line-3)');
      s += '<rect x="' + p[0] + '" y="' + p[1] + '" width="' + p[2] + '" height="' + p[3] +
        '" fill="' + (isCore || isStar ? 'var(--card-3)' : 'var(--card-2)') + '" stroke="' + stroke +
        '" stroke-width="' + (isCore || isStar ? 2 : 1) + '"/>';
      s += '<text x="' + (p[0] + 10) + '" y="' + (p[1] + 19) + '" font-size="11.5" ' +
        'font-weight="700" font-family="var(--mono)" fill="' +
        (isStar ? 'var(--warn)' : (isCore ? 'var(--accent-hi)' : 'var(--ink)')) + '">' + esc(k) + '</text>';
      s += '<text x="' + (p[0] + 10) + '" y="' + (p[1] + 34) + '" font-size="9.5" ' +
        'fill="var(--ink-faint)">' + esc(m.label) + '　' + m.cols.length + ' 欄</text>';
      if (p[3] > 58) {
        s += '<text x="' + (p[0] + 10) + '" y="' + (p[1] + 51) + '" font-size="9" ' +
          'fill="var(--ink-dim)">' + (isStar ? '★ 評測與訓練資料來源' : '核心表') + '</text>';
      }
    });
    s += '</svg>';
    return '<div style="overflow-x:auto">' + s + '</div>';
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

  function paintWho() {
    API.me().then(function (m) {
      ME = m;
      var w = document.getElementById('who');
      if (w) {
        w.innerHTML = '<span class="ava ava--sm">' + esc(m.user.avatar) + '</span>' +
          '<span class="who__n">' + esc(m.user.name) + '</span>' +
          '<span class="who__r">' + ROLE_TW[m.user.role] + '</span>';
      }
      var f = document.getElementById('famName');
      if (f) f.textContent = m.family.family + '　' + m.family.period;
    });
  }

  /* ---------- 路由 ---------- */
  var ROUTES = { '': vHome, entry: vEntry, family: vFamily, stats: vStats,
                 advice: vAdvice, members: vMembers, eval: vEval, schema: vSchema };

  function paint() {
    var page = (location.hash || '#/').replace(/^#\/?/, '').split('/')[0];
    (ROUTES[page] || vHome)();
    Array.prototype.forEach.call(document.querySelectorAll('.nav__i'), function (b) {
      b.classList.toggle('on', b.dataset.nav === page);
    });
  }

  /* ---------- 事件 ---------- */
  document.addEventListener('click', function (e) {
    var t = e.target;
    if (!t.closest) return;

    var nav = t.closest('[data-nav]');
    if (nav) { location.hash = '#/' + nav.dataset.nav; return; }

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
      API.nlpConfirm({
        date: v.date, amount: Number(v.amount), kind: v.kind, cat: v.cat,
        merchant: v.merchant, note: v.note, raw: '', conf: 1, catConf: 1
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

    var sw = t.closest('[data-switch]');
    if (sw) {
      API.switchUser(sw.dataset.switch).then(function () {
        paintWho(); paint(); toast('已切換身分', 'ok');
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

    if (t.closest('#reset')) {
      API.reset().then(function (r) {
        if (r.reset === false) { toast(r.note || '此模式不支援重置', 'err'); return; }
        paintWho(); paint(); toast('已還原成示範資料', 'ok');
      });
    }
  });

  document.addEventListener('change', function (e) {
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

  window.addEventListener('hashchange', paint);

  document.getElementById('mode').textContent =
    API.mode === 'http' ? 'API ' + API.base : 'API mock';
  paintWho();
  paint();
})(window);
