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

  /* 抽屜不要浮在內容上面。
     ------------------------------------------------------------
     一開始是用 padding-top 把內容往下推，但那只有在頁面捲到最上面
     才有用：捲動之後文件整體往下移，視窗還停在原本的文件位置，
     看到的仍然是被蓋住的那一段（實測有 5 個元素被蓋到）。

     所以改成把面板**搬進版面裡**——放到頂欄和內容之間當一個真的區塊。
     它佔的是真實的空間，不管捲到哪裡都不會壓到任何東西。

     圖示模式維持一般下拉（小面板貼著按鈕），那是慣例，不搬。 */
  function placePanel(panel) {
    if (!panel) return;
    var main = document.querySelector('.main');
    var view = document.getElementById('view');
    if (!main || !view) return;

    if (!document.body.classList.contains('bar-text')) {
      panel.classList.remove('inflow');
      return;
    }
    /* ⚠️ 重繪會在原位生一個同 id 的新面板，搬走的舊的還在 main 裡，
       於是 querySelector 查到的是文件順序在前的那一個（原位、關著的），
       看起來就像「按了沒反應」。所以搬之前先把舊的清掉。 */
    var stale = main.querySelector(':scope > #' + panel.id);
    if (stale && stale !== panel) stale.remove();
    if (panel.parentElement !== main) main.insertBefore(panel, view);
    panel.classList.add('inflow');
  }

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
    DRAWERS.forEach(function (sel) {
      var e = document.querySelector(sel);
      if (e) placePanel(e);
    });
    var open = DRAWERS.map(function (sel) { return document.querySelector(sel); })
      .filter(function (e) { return e && !e.hidden; })[0];
    document.body.classList.toggle('dw-on', !!open);
  }
  global.__pushForDrawer = pushForDrawer;

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
    { name: '林建國 · 家長',   email: 'jianguo@lin.tw' },
    { name: '陳淑芬 · 家長',   email: 'shufen@lin.tw' },
    { name: '林宇涵 · 子女',   email: 'yuhan@lin.tw' },
    { name: '林宇軒 · 子女',   email: 'yuxuan@lin.tw' },
    /* ⚠️ 用他登入會看到完全不同的側欄——那正是這個角色的重點 */
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
              '<span class="dot" style="background:' + tint(x.catColor) + '"></span>' + esc(x.catName) + '</div>' +
              '<div class="bgt__t"><i style="width:' + Math.min(100, x.pct * 100) +
              '%;background:' + (x.over ? 'var(--down)' : tint(x.catColor)) + '"></i></div>' +
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
             '</div>' +
             '<div id="recent">' + skeleton(4) + '</div></div>';
        $view.innerHTML = h;
        animate();
        return API.transactions({});
      }).then(function (d) {
        var box = document.getElementById('recent');
        if (!box || !d) return;
        box.innerHTML = txTable(d.transactions.slice(0, 6), null, '') ||
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
    return '<div class="txw"><table class="txt">' +
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

  function foldHead(id, title, label, kicker, help) {
    var on = !!FOLD[id];
    /* ⚠️ title 一定要 esc()，所以問號不能混在 title 裡傳進來——
       那樣傳會變成畫面上出現一串 &lt;button&gt;。要掛說明就用 help 參數。 */
    return '<div class="sec"><h2 class="sec__t">' + esc(title) +
      (help ? helpBtn(help) : '') + '</h2>' +
      (kicker ? '<span class="sec__n">' + esc(kicker) + '</span>' : '') +
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
    wrap.hidden = !on;
    if (btn) {
      btn.classList.toggle('on', on);
      btn.setAttribute('aria-expanded', on ? 'true' : 'false');
      var t = btn.querySelector('.fold__t');
      if (t) t.textContent = on ? '收起' : (btn.dataset.label || '展開');
    }
    if (on && !wrap.innerHTML) foldFill(id, wrap);
  }

  var MODE = 'para';          // 'para' 段落批次 ｜ 'single' 單筆手動。兩者互斥
  var batch = null;           // 段落解析結果，尚未寫入

  /* 記帳頁：明細先出來。

     「記一筆」是有事才做的動作，不該一進來就佔掉半個版面——
     大部分時候使用者是來看自己花了什麼，不是來記帳的。
     要記的時候點 ＋，表單才長出來。 */
  function vEntry() {
    head('記帳', '');
    var h = '<div class="page">';

    h += foldHead('entry', '收支明細', '記一筆', 'TRANSACTIONS');
    h += filterBar() + '<div id="txList">' + skeleton(6) + '</div></div>';
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
    return '<div class="bar">' +
      sel('kind', '收支', [['all', '全部'], ['expense', '支出'], ['income', '收入']]) +
      sel('source', '來源', [['all', '全部'], ['nlp', '段落記帳'], ['manual', '手動輸入']]) +
      '</div>';
  }

  function loadTx() {
    var box = document.getElementById('txList');
    if (!box) return;
    API.transactions(Object.assign({}, F, { groupId: GROUP })).then(function (d) {
      box.innerHTML = txTable(d.transactions, null,
        emptyState('沒有符合的紀錄', '換個篩選條件，或記一筆新的。'));
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
        /* 第一道：這個功能只有家長有。 */
        if (m.user.role !== 'parent') {
          h += '<div class="note note--warn"><div class="note__k">沒有這個功能</div>' +
            '<p>家庭總覽是給家長看的。</p></div></div>';
          $view.innerHTML = h;
          return;
        }

        /* 第二道：有這個功能，但沒有人被指派給你看。 */
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
        h += kpi('每月零用金', d.allowance || 0, '',
          '子女已花 ' + money(d.wardSpend || 0), 'a', 3);
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
              '<span class="tag tag--' + (u.role === 'parent' ? 'MEDIUM' : 'soft') + '">' +
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

        /* 這一頁只回答「誰」。

           ⚠️ 不要在這裡放圓餅或月趨勢——「統計」那一頁已經有了，
           而且同樣是家庭範圍、同一份資料。放兩份就是同一個東西兩個地方。

           三頁的分工是照**問題**切的，不是照範圍切的：
             家庭總覽   誰有問題      成員狀況、超支、誰花的
             統計       數字長什麼樣   月／年對照、分類圓餅、趨勢
             財務建議   那該怎麼辦     建議清單 */
        h += '<div class="sec"><h2 class="sec__t">誰花的</h2>' +
             '<span class="sec__n">WHO</span></div>';
        h += '<div class="card rise">' + memberBar(d.members, d.expense) + '</div>';

        h += '<div class="sec"><h2 class="sec__t">超出預算的項目</h2></div>';
        var over = b.budgets.filter(function (x) { return x.over; });
        h += over.length ? '<div class="card">' + over.map(function (x) {
          return '<div class="bgt"><div class="bgt__k"><span class="dot" style="background:' +
            tint(x.catColor) + '"></span>' + esc(x.userName) + '　' + esc(x.catName) + '</div>' +
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
        ? (d.monthly || []).map(function (r) { return { k: r.m, income: r.income, expense: r.expense }; })
        : (d.yearly || []).map(function (r) { return { k: r.y, income: r.income, expense: r.expense, partial: r.partial }; });

      /* 選了單一帳本、又在看「按月」的時候，月數列是 null——
         與其給一張空表，不如講清楚為什麼。 */
      if (STAT.period === 'month' && !d.monthly) {
        h += '<div class="note"><div class="note__k">月趨勢只有在「全部帳本」時看得到</div>' +
          '<p>每個人的月數列沒有分帳本，硬拆出來的數字會是錯的。' +
          '下面的支出分類仍然是這一本帳的。</p></div>';
      }

      h += (STAT.period === 'month' && !d.monthly) ? '' :
        '<div class="card rise"><div class="card__h"><span class="card__t">' +
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
    API.advices().then(function (d) {
      ADV = d.advices || [];
      $view.innerHTML =
        '<div class="page">' +
          '<div class="bar">' +
            '<label class="fsel"><span>搜尋</span>' +
              '<input type="search" id="advq" placeholder="標題、內容或依據" ' +
                'value="' + esc(ADVQ) + '" autocomplete="off"></label>' +
          '</div>' +
          '<div id="advList"></div>' +
        '</div>';
      paintAdvices();
      /* 沒填理財習慣的話，在這裡提一次——這是它真正會派上用場的地方，
         比在註冊流程裡多問四題有用。 */
      API.financeProfile().then(function (p) {
        var f = p.finance || {};
        var empty = !f.style && !(f.goals || []).length &&
          !(f.habits || []).length && !f.note;
        if (!empty) return;
        var box = document.getElementById('advList');
        if (!box) return;
        box.insertAdjacentHTML('beforebegin',
          '<div class="note"><div class="note__k">建議可以更貼近你</div>' +
          '<p>到<a href="#/profile">個人資料</a>填一下理財習慣——' +
          '在意的目標不一樣，同一筆支出的意義就不一樣。</p></div>');
      }).catch(function () {});
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
      box.innerHTML = emptyState('沒有符合的建議', '換個關鍵字試試。');
      return;
    }

    box.innerHTML = rows.map(function (a) {
      var open = ADVOPEN === a.id;
      return '<div class="ad' + (open ? ' on' : '') + '">' +
        '<button class="ad__h" data-adv="' + esc(a.id) + '">' +
          '<span class="ad__lv ad__lv--' + esc(a.level) + '">' + advLevel(a) + '</span>' +
          '<span class="ad__t">' + esc(a.title) + '</span>' +
          '<span class="ad__m">' + esc(a.scope === 'family' ? '家庭' : a.userName) + '</span>' +
          '<span class="ad__p">' + esc(a.period) + '</span>' +
          '<svg class="ad__cv" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
            'stroke-width="2"><path d="m6 9 6 6 6-6"/></svg>' +
        '</button>' +
        (open
          ? '<div class="ad__b">' +
              '<p>' + esc(a.body) + '</p>' +
              '<div class="ad__k">依據</div><ul>' +
                (a.basis || []).map(function (b) { return '<li>' + esc(b) + '</li>'; }).join('') +
              '</ul>' +
              '<div class="ad__k">建議</div><ul>' +
                (a.suggest || []).map(function (b) { return '<li>' + esc(b) + '</li>'; }).join('') +
              '</ul>' +
            '</div>'
          : '') +
      '</div>';
    }).join('');
  }


  /* ============================================================
     06 成員與權限
     ============================================================ */
  /* 誰的存款目標我能改：我自己，或我監管的人。
     ⚠️ 不看年齡、也不看角色——有沒有監管關係是那一家自己決定的。 */
  function canSetGoal(u, d) {
    if (u.id === d.me) return true;
    return (d.guardianships || []).some(function (g) {
      return g.guardian === d.me && g.ward === u.id;
    });
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
            '<span class="tag tag--' + (u.role === 'parent' ? 'MEDIUM' : 'soft') + '">' +
              ROLE_TW[u.role] + '</span>' +
            (u.id === d.me ? '<span class="tag tag--na">目前登入</span>' : '') +
            (canSetGoal(u, d) && u.id !== d.me
              ? '<span class="tag tag--info">目標由你代設</span>' : '') +
          '</div><div class="row__sub">' +
            (wards.length ? '監管：' + wards.map(function (g) { return esc(g.wardName); }).join('、') : '') +
            (wards.length && by.length ? '　｜　' : '') +
            (by.length ? '<b style="color:var(--warn)">被 ' +
              by.map(function (g) { return esc(g.guardianName); }).join('、') + ' 監管</b>' : '') +
            (!wards.length && !by.length ? '無監管關係' : '') +
          '</div></div>' +
          /* 這一列只講身分：誰、什麼角色、跟誰有監管關係。
             存款目標是財務設定，不屬於這裡——自己的在「個人資料」，
             代監管對象設的在那個人的紀錄頁。擠在這裡又醜又難按。

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
    Promise.all([API.me(), API.members(), API.allowances().catch(function () {
      return { allowances: [] };
    })])
      .then(function (r) {
        var me = r[0], d = r[1], al = r[2];
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
        /* 兩種看得到的方式，能看到的範圍不一樣，要講清楚是哪一種：
             監管    → 這個人的全部紀錄，跨所有帳本
             同帳本  → 只有你們共用的那幾本裡的紀錄 */
        var supervised = (me.visible || []).indexOf(id) >= 0;
        var shared = (me.queryable || []).indexOf(id) >= 0;

        if (!supervised && !shared) {
          $view.innerHTML = '<div class="page"><div class="note note--warn">' +
            '<div class="note__k">看不到這個人的紀錄</div>' +
            '<p>你沒有監管 <b>' + esc(u.name) + '</b>，也沒有跟他共用的帳本。<br>' +
            '監管關係由家長建立，而且雙方都看得到——系統不提供隱藏監管。</p>' +
            '</div>' + backLink() + '</div>';
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
      var by = d.guardianships.filter(function (g) { return g.ward === id; });

      var h = '<div class="page">' + backLink();

      /* 只因為共用帳本才看得到的話，一定要說清楚這不是全部——
         不然使用者會把「他這個月只花了 800」當成事實，
         而那其實只是他記在這幾本帳裡的部分。 */
      if (partial) {
        h += '<div class="note"><div class="note__k">這不是他的全部紀錄</div>' +
          '<p>你沒有監管 ' + esc(u.name) + '，看得到的只有你們<b>共用帳本</b>裡的紀錄。' +
          '他記在其他帳本的不會出現在這裡。</p></div>';
      }

      h += '<div class="card mhead">' +
        ava(u, 'ava--xl') +
        '<div class="mhead__m">' +
          '<div class="mhead__top">' +
            '<span class="mhead__n">' + esc(u.name) + '</span>' +
            '<span class="tag tag--' + (u.role === 'parent' ? 'MEDIUM' : 'soft') + '">' +
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

      /* 監管對象的存款目標可由監管者代設——設定的地方就放在
         看得到他紀錄的這一頁，不要塞回成員名冊那張表。 */
      /* ⚠️ 只有監管他的人才看得到零用金——那是監管者對監管對象的設定。
         只是跟他共用一本帳的人不該看到，更不該改。 */
      if (!mine && !partial) {
        /* 我給他多少零用金。這是設定，不是一筆支出紀錄——
           不要另外記一筆「給小孩 3000」，否則他花掉之後同一筆錢會被算兩次。 */
        h += '<div class="sec"><h2 class="sec__t">每月零用金' + helpBtn('allowance') + '</h2></div>' +
          '<div class="card prof__goal">' +
            '<input class="goal__i" type="number" min="0" ' +
              'data-allow="' + esc(u.id) + '" value="' + (u.allowance || 0) + '">' +
          '</div>';
      }

      if (canSetGoal(u, d) && !mine) {
        h += '<div class="sec"><h2 class="sec__t">每月存款目標' + helpBtn('goal') + '</h2></div>' +
          '<div class="card prof__goal">' +
            '<input class="goal__i" type="number" min="0" ' +
              'data-goal="' + esc(u.id) + '" value="' + (u.savingsGoal || 0) + '">' +
          '</div>';
      }

      h += '<div class="sec"><h2 class="sec__t">收支明細</h2>' +
        '<span class="sec__n">' + tx.total + ' 筆</span></div>';

      h += '<div id="mtx">' + txTable(tx.transactions, hit,
        emptyState('還沒有紀錄', esc(u.name) + '這個月還沒有記過帳。')) + '</div></div>';

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
     帳本

     記帳除了有「分類」，還有「這筆算在哪一本帳上」。
     分類回答錢花在什麼，帳本回答這筆屬於哪一份預算。
     每一本帳可以各自設一個每月存款目標。
     ============================================================ */
  function vGroups() {
    head('帳本', '一個家庭可以開好幾本，各自有自己的存款目標');
    $view.innerHTML = '<div class="page">' + skeleton(4) + '</div>';

    Promise.all([API.groups({ includeArchived: true }), API.members()])
      .then(function (r) {
      var d = r[0], fam = r[1];

      var live = d.groups.filter(function (g) { return !g.archived; });
      var gone = d.groups.filter(function (g) { return g.archived; });

      /* 常設／活動分成兩區，不是兩個分頁。
         分頁會把一半藏起來——只有一本活動帳的時候，為它開一個分頁太重，
         手機上多一層隱藏狀態也跟「看得到現在在哪一本」相反。
         區塊則是全部看得到、只是分群；沒有活動帳本時整個區塊不出現。 */
      var standing = live.filter(function (g) { return g.kind !== 'temp'; });
      var temps = live.filter(function (g) { return g.kind === 'temp' && !g.settled; });
      var done = live.filter(function (g) { return g.kind === 'temp' && g.settled; });

      var h = '<div class="page">';

      /* 「開一本新的」跟記帳頁的「記一筆」是同一個做法：
         進來先看到的是**帳本本身**，開新的那張表單縮成標題右邊的一個＋。

         ⚠️ 這不只是版面偏好。開帳本是一次性動作——開完就不會再開了，
         但那張表單原本每次進來都攤在畫面中間，永遠佔著位置。
         真正每天要看的是「我有哪幾本、各自花到哪」。 */
      var gnewForm =
        '<form class="card gnew" id="gnewF">' +
          '<label class="fld"><span>名字</span>' +
            '<input type="text" id="gnName" placeholder="例如 旅遊基金、沖繩旅遊" required></label>' +
          '<label class="fld"><span>種類</span>' +
            '<select id="gnKind">' +
              '<option value="standing">常設 —— 一直用的</option>' +
              '<option value="temp">活動 —— 有結束日，結束後結算</option>' +
            '</select></label>' +
          /* 只有活動帳本要填結束日，所以它預設藏起來 */
          '<label class="fld" id="gnEndWrap" hidden><span>結束日</span>' +
            '<input type="date" id="gnEnd"></label>' +
          '<label class="fld"><span>顏色</span>' +
            /* ⚠️ 顏色從 DATA.groupColors 來，不要再寫死一份。
               寫死的那一版跟種子資料用的顏色完全是兩套：表單給亮彩、
               資料用濁色，結果新開的帳本跟全站格格不入，而且看不見。 */
            '<select id="gnColor">' +
              ((global.DATA && global.DATA.groupColors) || []).map(function (c) {
                return '<option value="' + esc(c.id) + '">' + esc(c.name) + '</option>';
              }).join('') +
            '</select></label>' +
          '<div><button class="btn btn--go" type="submit">建立</button></div>' +
        '</form>';

      h += foldBlock('gnew', '常設帳本', '開一本', gnewForm,
                     standing.length + ' 本', 'books');
      h += '<div class="rows">' + standing.map(gcard).join('') + '</div>';

      if (temps.length) {
        h += '<div class="sec"><h2 class="sec__t">活動帳本</h2>' +
          '<span class="sec__n">' + temps.length + ' 本</span></div>';
        h += '<div class="rows">' + temps.map(gcard).join('') + '</div>';
      }
      if (done.length) {
        h += foldBlock('gdone', '已結算', '看看',
          '<div class="rows">' + done.map(gcard).join('') + '</div>',
          String(done.length) + ' 本');
      }

      function gcard(g, i) {
        /* ⚠️ 帳本沒有圖示方塊。

           名字已經說清楚是哪一本了，再擺一個寫著同一個字的方塊只是佔位；
           活動帳本另外有「活動 · 到 mm/dd」的標籤，更沒有理由。
           顏色靠切換器上的小圓點就夠。 */
        return '<article class="row" style="animation-delay:' + ((i || 0) * 50) +
          'ms;grid-template-columns:1fr 150px auto">' +
          '<div class="row__m"><div class="row__top">' +
            '<span class="row__act" style="font-size:15px">' + esc(g.name) + '</span>' +
            (g.kind === 'temp'
              ? '<span class="tag tag--MEDIUM">活動' +
                (g.endsOn ? ' · 到 ' + esc(g.endsOn.slice(5).replace('-', '/')) : '') +
                '</span>' : '') +
            (g.settled ? '<span class="tag tag--soft">已結算</span>' : '') +
            (g.overdue ? '<span class="tag tag--down">已到期</span>' : '') +
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
            (g.kind === 'temp' && !g.settled && g.canEdit
              ? '<button class="gx gx--go" data-gsettle="' + esc(g.id) + '">結算</button>' : '') +
            (g.canEdit && !g.settled
              ? '<button class="gx" data-garch="' + esc(g.id) +
                '" title="收起這本帳。紀錄不會被刪掉，之後可以復原">封存</button>' : '') +
          '</div>' +
          '<label class="gnot"><input type="checkbox" data-gnotify="' + esc(g.id) + '"' +
            (g.notify ? ' checked' : '') + '><span>有動靜通知我</span></label>' +
        '</article>';
      }

      /* ---- 成員 ----
         同樣收起來。編成員是偶爾才做一次的事，
         但這張卡片會隨著帳本數量一直長高，攤開的話下面的「已封存」
         幾乎永遠滾不到。 */
      var editable = d.groups.filter(function (g) { return g.canEdit; });
      if (editable.length) {
        h += foldBlock('gmem', '誰在哪一本帳裡', '編成員',
          '<div class="card gmem">' + editable.map(function (g) {
          var inside = g.members;
          var outside = fam.members.filter(function (u) { return inside.indexOf(u.id) < 0; });
          return '<div class="gmem__g">' +
            '<div class="gmem__t"><span class="gsw__d" style="background:' + tint(g.color) +
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
        }).join('') + '</div>', String(editable.length) + ' 本');
      }

      /* ---- 已封存 ---- */
      if (gone.length) {
        h += foldBlock('garch', '已封存', '看看',
          '<div class="card arch">' +
          '<div class="arch__l">' + gone.map(function (g) {
            return '<div class="arch__i">' +
              '<span class="gsw__d" style="background:' + tint(g.color) + '"></span>' +
              '<span class="arch__n">' + esc(g.name) + '</span>' +
              '<span class="arch__c">' + g.count + ' 筆紀錄還在</span>' +
              (g.canEdit
                ? '<button class="btn btn--sm" data-grestore="' + esc(g.id) + '">復原</button>'
                : '') +
            '</div>';
          }).join('') + '</div></div>', String(gone.length) + ' 本', 'archive');
      }

      $view.innerHTML = h + '</div>';
      /* ⚠️ 重畫之後一定要叫它——不然使用者展開表單、按了建立，
         畫面重畫完就無聲收合，看起來像沒有反應。 */
      foldRestore();
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
         '<p>如果有人監管你，他也可以幫你設定這個數字。</p>'
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
         '<p>家裡的家長可以建立「監管關係」，被指派之後，' +
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
          '<th>家長</th><th>子女</th></tr></thead><tbody>' +
          PERMS.permissions.map(function (p) {
            return '<tr><td>' + esc(p.action) + '</td>' +
              cell(p.parent) + cell(p.child) + '</tr>';
          }).join('') + '</tbody></table></div>';
      }
    },
    allowance: {
      t: '每月零用金',
      b: '<p>你每個月給他多少錢。<b>這是設定，不是一筆支出紀錄。</b></p>' +
         '<p>不要另外記一筆「給小孩 3000」——他把那 3000 花掉時會記成支出，' +
         '同一筆錢就被算了兩次，家庭支出會憑空多一倍。</p>' +
         '<p>所以家庭總覽是這樣算的：' +
         '<b>子女的支出算進家庭支出</b>（那筆錢確實離開了這個家），' +
         '<b>子女的收入不算進家庭收入</b>（零用錢是家裡給的）。</p>' +
         '<p>這個數字只拿來跟「他實際花了多少」做對照。</p>'
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
    { sel: '.nav__i[data-nav="entry"]', hash: '#/',
      t: '從這裡記帳',
      b: '打一段話就好，例如「早餐55 中午吃飯320」，系統會幫你拆成一筆一筆。' },
    { sel: '.kpis .kpi:last-child', hash: '#/',
      t: '這個月還能花多少',
      b: '收入扣掉你設定的存款目標，剩下的就是能放心花的錢。' },
    { sel: '#gswBtn', hash: '#/',
      t: '切換帳本',
      b: '家用、旅遊基金可以分開記。切過去之後，統計和目標都只看那一本。' },
    { sel: '#bell', hash: '#/',
      t: '通知',
      b: '家人記帳、或是你花到設定的比例時，這裡會亮。' },
    { sel: '.nav__i[data-nav="profile"]', hash: '#/',
      t: '設定在這裡',
      b: '每月想存多少、花到幾成提醒你，都在個人資料裡設定。' },
    { sel: '.docs__i--main', hash: '#/',
      t: '看不懂就來這裡',
      b: '完整的使用說明放在這。另外，畫面上標題旁邊的「?」可以隨時點開。' }
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
       平台管理員的側欄裡一個都沒有——框會圈在看不見的元素上。 */
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

    var el0 = document.querySelector(step.sel);
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
    head('平台管理', '停權與稽核');
    $view.innerHTML = '<div class="page">' + skeleton(4) + '</div>';

    Promise.all([API.adminUsers(), API.audit()]).then(function (r) {
      var users = r[0].users, logs = r[1].logs;
      var h = '<div class="page">';

      h += '<div class="note"><div class="note__k">這裡看不到任何人的錢</div>' +
        '<p>平台管理員能停權、能查稽核，但<b>讀不到任何一筆帳</b>。' +
        '停權是關門，不是配鑰匙。</p></div>';

      h += '<div class="sec"><h2 class="sec__t">帳號</h2>' +
        '<span class="sec__n">' + users.length + ' 個</span></div>';

      h += '<div class="rows">' + users.map(function (u, i) {
        var off = !!u.suspendedAt;
        return '<article class="row" style="animation-delay:' + (i * 50) +
          'ms;grid-template-columns:1fr 150px">' +
          '<div class="row__m"><div class="row__top">' +
            '<span class="row__act" style="font-size:15px">' + esc(u.name) + '</span>' +
            (off ? '<span class="tag tag--down">已停權</span>'
                 : '<span class="tag tag--soft">正常</span>') +
          '</div><div class="row__sub">' + esc(u.email) +
            (off ? '　｜　' + esc(u.suspendedReason) : '') + '</div></div>' +
          '<div class="row__go2">' +
            (off
              ? '<button class="gx gx--go" data-unsus="' + esc(u.id) + '">解除停權</button>'
              : '<button class="gx gx--warn" data-sus="' + esc(u.id) + '">停權</button>') +
          '</div>' +
        '</article>';
      }).join('') + '</div>';

      /* ⚠️ 稽核收合起來，但**不是次要功能**——沒有稽核的停權就是任意封鎖。
         收起來只是因為它是清單，不是一進來就要處理的東西。 */
      h += foldBlock('audit', '稽核紀錄', '看紀錄',
        '<div class="card">' + logs.map(function (a) {
          return '<div class="aud">' +
            '<span class="aud__t">' + esc(a.at) + '</span>' +
            '<span class="aud__a">' + esc(a.actorName) + '</span>' +
            '<span class="aud__k">' + esc(AUDIT_TW[a.action] || a.action) + '</span>' +
            '<span class="aud__n">' + esc(a.note || '') + '</span>' +
          '</div>';
        }).join('') + '</div>', String(logs.length) + ' 筆');

      h += '</div>';
      $view.innerHTML = h;
      foldRestore();
    }).catch(function (e) {
      $view.innerHTML = '<div class="page">' + errState(e) + '</div>';
    });
  }

  var AUDIT_TW = {
    suspend_user: '停權帳號', unsuspend_user: '解除停權',
    grant_guardianship: '建立監管關係', end_guardianship: '解除監管',
    change_role: '變更角色', create_family: '建立家庭', view_ward: '查看被監管者'
  };

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
        '<div class="gate__b"><span class="brand__n">家庭記帳</span></div>' +
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
      /* 左右兩欄。大頭貼、存款目標、密碼都只需要半欄的寬度，
         各自獨佔一整條的話，整頁會被拉得很長而且空空的。
         階段性提醒有清單又有新增列，需要整欄，所以放在下面。 */
      /* 基本資料在左，其他設定在右。
         階段性提醒有清單又有新增列，需要整欄，放下面。 */
      var h = '<div class="page">' +
        '<div class="cols"><div class="col">' +

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

        '</div><div class="col">' +

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

        foldHead('fin', '理財習慣', '填寫', 'FOR ADVICE') +

        '<div class="sec"><h2 class="sec__t">階段性提醒' + helpBtn('alerts') + '</h2></div>' +
        '<div class="card" id="alertBox">' + skeleton(2) + '</div>' +

      '</div>';
      $view.innerHTML = h;
      foldRestore();
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
        '<label class="fld anew__pct"><span>百分比</span>' +
          '<input type="number" id="anPct" min="1" max="200" value="80" required></label>' +
        '<label class="fld anew__grp"><span>哪一本帳</span>' +
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
      // 重繪之後面板是新的，馬上搬到版面裡，避免留下同 id 的舊節點
      pushForDrawer();
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
      /* 家庭總覽是給家長的功能。
         ⚠️ 這跟「可見範圍」是兩件事：
           角色  決定「有沒有這個功能」
           監管  決定「看得到誰的資料」
         兩道都要過——家長也只看得到被指派給他的那幾個人。 */
      document.body.classList.toggle('role-child', m.user.role !== 'parent');
      /* ⚠️ 平台管理員沒有財務頁可以看——那不是藏起來，是他真的沒有資料。
         側欄只留「平台管理」。 */
      document.body.classList.toggle('is-admin', !!m.user.isPlatformAdmin);

      var f = document.getElementById('famName');
      if (f) f.textContent = m.family.family + '　' + m.family.period;
    });
  }

  /* ---------- 路由 ---------- */
  var ROUTES = { '': vHome, entry: vEntry, family: vFamily, stats: vStats,
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
        // 看某個成員的紀錄時，左邊仍然亮「成員與權限」
        var lit = page === 'member' ? 'members' : page;
        Array.prototype.forEach.call(document.querySelectorAll('.nav__i'), function (b) {
          b.classList.toggle('on', b.dataset.nav === lit);
        });
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
      ADVOPEN = (ADVOPEN === adv.dataset.adv) ? null : adv.dataset.adv;
      paintAdvices();
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
        sd.hidden = !sd.hidden;
        sb.classList.toggle('open', !sd.hidden);
        document.body.classList.toggle('dw-on', !sd.hidden);
        setTimeout(pushForDrawer, 0);
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
        pushForDrawer();
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
        gp.hidden = !gp.hidden;
        document.getElementById('gswBtn').classList.toggle('open', !gp.hidden);
        document.body.classList.toggle('dw-on', !gp.hidden);
        setTimeout(pushForDrawer, 0);
        /* 抽屜在版面最上面。捲到下面才點開的話它會開在畫面外，
           看起來像沒反應——所以直接回到頂端。 */
        if (!gp.hidden) setTimeout(function () { window.scrollTo(0, 0); }, 40);
      }
      return;
    }
    var gpick = t.closest('[data-group]');
    if (gpick) {
      setGroup(gpick.dataset.group);
      document.body.classList.remove('dw-on');
      pushForDrawer();
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
        pushForDrawer();
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

    /* ---- 帳本管理 ---- */
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
