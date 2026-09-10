/* ============================================================
   app.js — PHISHTRIAGE 前端
   ------------------------------------------------------------
   資料一律走 API.*（見 js/api.js），不直接讀 window.DATA。
   要接真後端只要改 index.html 的 <meta name="api-base">。
   ============================================================ */
(function (global) {
  'use strict';

  var API = global.API;
  var $view = document.getElementById('view');
  var $title = document.getElementById('ptitle');
  var $sub = document.getElementById('psub');
  var $search = document.getElementById('search');
  var $toasts = document.getElementById('toasts');

  var F = { verdict: 'all', status: 'all', sort: 'priority', q: '' };
  var picked = [];

  /* ---------- 小工具 ---------- */
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  // 資料裡的網域刻意用 <span>.</span> 斷開，避免被當成可點連結；顯示時還原
  function dom(s) { return esc(String(s || '').replace(/<span>\.<\/span>/g, '.')); }
  function el(h) { var d = document.createElement('div'); d.innerHTML = h.trim(); return d.firstChild; }

  var V_TW = { phishing: '釣魚', spam: '垃圾信', benign: '正常信' };
  var V_CLS = { phishing: 'CRITICAL', spam: 'MEDIUM', benign: 'LOW' };

  function vTag(v) { return '<span class="tag tag--' + V_CLS[v] + '">' + V_TW[v] + '</span>'; }
  function stTag(s) {
    return s === 'closed'
      ? '<span class="tag tag--done">已處置</span>'
      : '<span class="tag tag--soft">待處理</span>';
  }
  function pct(x) { return Math.round(x * 100) + '%'; }

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
      esc(e && e.message ? e.message : String(e)) + '<br>目前模式：<b>' + API.mode + '</b>' +
      (API.base ? '（' + esc(API.base) + '）' : '') + '</div></div>';
  }

  /* ============================================================
     01 總覽
     ============================================================ */
  function vHome() {
    head('總覽', '這個班次收到多少回報、收斂成幾張卡片、真正需要看的有幾件');
    $view.innerHTML = '<div class="page">' + skeleton(4, 'skel__k') + '</div>';

    API.shift().then(function (d) {
      var s = d.shift;
      var h = '<div class="page"><div class="kpis">';
      h += kpi('本班次回報', s.reports, '封', d.meta.shift, 'a', 0);
      h += kpi('收斂成卡片', s.cards, '張', '收斂率 ' + s.ratio + ' 倍', 'ok', 1);
      h += kpi('真釣魚', d.openPhishing, '件', '分析師實際需要看的', 'crit', 2);
      h += kpi('非威脅', s.spam + s.benign, '封', '佔全部的 ' +
           Math.round((s.spam + s.benign) / s.reports * 100) + '%', 'warn', 3);
      h += '</div>';

      /* 收斂視覺化 —— 這是本系統最直接的價值 */
      h += '<div class="sec"><h2 class="sec__t">這個班次省下了什麼</h2>' +
           '<span class="sec__n">CONVERGENCE</span></div>';
      h += '<div class="card rise"><div class="funnel">' +
        fbar('分析師原本要看', s.reports, s.reports, 'var(--r-crit)', s.reports + ' 封信') +
        fbar('系統收斂後', s.cards, s.reports, 'var(--a)', s.cards + ' 張卡片') +
        fbar('其中真的是威脅', d.openPhishing, s.reports, 'var(--r-high)', d.openPhishing + ' 件') +
        '</div>' +
        '<div class="lgd" style="margin-top:16px">' +
        '<span>人工處理時間 <b style="color:var(--r-crit)">' + s.analystMinutesBefore + ' 分</b>' +
        ' → <b style="color:var(--r-done)">' + s.analystMinutesAfter + ' 分</b></span>' +
        '<span style="margin-left:auto">生成模型呼叫 <b style="color:var(--r-done)">' +
        s.llmCalls + ' 次</b>（不收斂要 ' + s.llmCallsIfNoDedup + ' 次）</span></div></div>';

      h += '<div class="charts" style="margin-top:12px">';
      h += '<div class="card rise"><div class="card__h"><span class="card__t">近 8 個班次</span>' +
           '<span class="card__s">回報量與收斂後卡片數</span></div>' +
           trendChart(d.trend) +
           '<div class="lgd"><span><i style="background:var(--r-high)"></i>回報封數</span>' +
           '<span><i style="background:var(--a)"></i>收斂後卡片</span></div></div>';

      h += '<div class="card rise" style="animation-delay:80ms">' +
           '<div class="card__h"><span class="card__t">判定分佈</span></div>' +
           d.mix.map(function (m) {
             return '<div class="mix__r" style="margin-bottom:11px">' +
               '<span class="mix__k">' + V_TW[m.verdict] + '</span>' +
               '<span class="mix__t"><i style="width:' + (m.reports / s.reports * 100) +
               '%;background:var(--r-' + (m.verdict === 'phishing' ? 'crit' :
                 (m.verdict === 'spam' ? 'med' : 'low')) + ')"></i></span>' +
               '<span class="mix__n">' + m.reports + '</span></div>' +
               '<div style="font-size:11px;color:var(--t4);margin:-6px 0 12px 57px">' +
               m.cards + ' 張卡片</div>';
           }).join('') + '</div>';
      h += '</div>';

      if (d.topRisk) {
        var t = d.topRisk;
        h += '<div class="note note--crit"><div class="note__k">最需要先看的一件</div><p>' +
          '<b>' + esc(t.name) + '</b>（' + esc(t.id) + '）只有 <b>' + t.reports +
          ' 封回報</b>，在 ' + s.reports + ' 封裡幾乎看不見 —— ' +
          '但它是<b>' + esc(global.DATA.tactics.filter(function (x) {
            return x.id === t.tactics[0]; })[0].name) + '</b>，損失金額最大的一類。<br>' +
          '照回報量排序，它會排在第 12 名。<b>這就是為什麼不能用「多少人回報」當優先序。</b>' +
          '</p></div>';
      }

      h += '<div class="sec"><h2 class="sec__t">待處理的卡片</h2>' +
           '<button class="btn btn--sm" data-nav="queue" style="margin-left:auto">看全部 ▸</button></div>';
      h += '<div class="rows" id="top3">' + skeleton(3) + '</div></div>';
      $view.innerHTML = h;
      animate();
      return API.campaigns({ status: 'open' });
    }).then(function (d) {
      if (!d) return;
      var box = document.getElementById('top3');
      if (!box) return;
      box.innerHTML = d.campaigns.slice(0, 3).map(function (c, i) { return rowHTML(c, i, false); }).join('') ||
        emptyState('沒有待處理的卡片', '這個班次的回報都處置完了。');
    }).catch(function (e) { $view.innerHTML = '<div class="page">' + errState(e) + '</div>'; });
  }

  function kpi(k, v, unit, sub, mod, i) {
    return '<div class="kpi kpi--' + mod + '" style="animation-delay:' + (i * 60) + 'ms">' +
      '<div class="kpi__k">' + esc(k) + '</div>' +
      '<div class="kpi__v"><span data-count="' + v + '">0</span><small>' + esc(unit) + '</small></div>' +
      '<div class="kpi__s">' + esc(sub) + '</div></div>';
  }

  function fbar(label, n, max, color, right) {
    return '<div class="fnl"><div class="fnl__k">' + esc(label) + '</div>' +
      '<div class="fnl__t"><i style="width:' + Math.max(2, n / max * 100) + '%;background:' + color + '"></i></div>' +
      '<div class="fnl__v">' + esc(right) + '</div></div>';
  }

  function trendChart(t) {
    var W = 520, H = 130, P = 8;
    var max = Math.max.apply(null, t.map(function (d) { return d.reports; })) || 1;
    function pts(key, scale) {
      return t.map(function (d, i) {
        var x = P + i * ((W - P * 2) / (t.length - 1));
        var y = H - P - (d[key] * (scale || 1) / max) * (H - P * 2);
        return x.toFixed(1) + ',' + y.toFixed(1);
      }).join(' ');
    }
    var grid = [0, .25, .5, .75, 1].map(function (f) {
      var y = (P + f * (H - P * 2)).toFixed(1);
      return '<line x1="' + P + '" y1="' + y + '" x2="' + (W - P) + '" y2="' + y +
             '" stroke="var(--line)" stroke-width="1"/>';
    }).join('');
    return '<svg viewBox="0 0 ' + W + ' ' + H + '" style="width:100%;height:auto;display:block">' + grid +
      '<polyline points="' + pts('reports') + '" fill="none" stroke="var(--r-high)" stroke-width="2"/>' +
      '<polyline points="' + pts('cards', 10) + '" fill="none" stroke="var(--a)" stroke-width="2"/>' +
      '</svg><div style="display:flex;justify-content:space-between;font-family:var(--mono);' +
      'font-size:9.5px;color:var(--t4);margin-top:6px"><span>' + esc(t[0].d) +
      '</span><span>卡片數已放大 10 倍以便對照</span><span>' + esc(t[t.length - 1].d) + '</span></div>';
  }

  /* ============================================================
     02 Campaign 佇列
     ============================================================ */
  function vQueue() {
    head('分流佇列', '一個 campaign 一張卡片，不是一封信一張');
    $view.innerHTML = '<div class="page">' + toolbar() +
      '<div class="rows" id="rows">' + skeleton(5) + '</div></div>';
    loadQueue();
  }

  function toolbar() {
    var vs = [['all', '全部'], ['phishing', '釣魚'], ['spam', '垃圾信'], ['benign', '正常信']];
    var st = [['all', '全部'], ['open', '待處理'], ['closed', '已處置']];
    return '<div class="bar"><div class="chips">' + vs.map(function (v) {
        return '<button class="chip' + (F.verdict === v[0] ? ' on' : '') +
          '" data-f="verdict" data-v="' + v[0] + '">' + v[1] + '</button>';
      }).join('') + '</div>' +
      '<select class="sel" data-f="status">' + st.map(function (s) {
        return '<option value="' + s[0] + '"' + (F.status === s[0] ? ' selected' : '') +
          '>狀態：' + s[1] + '</option>';
      }).join('') + '</select>' +
      '<select class="sel" data-f="sort">' +
        '<option value="priority"' + (F.sort === 'priority' ? ' selected' : '') + '>依風險排序</option>' +
        '<option value="reports"' + (F.sort === 'reports' ? ' selected' : '') + '>依回報量排序</option>' +
      '</select><span style="flex:1"></span>' +
      '<button class="btn btn--sm" id="reset">重置示範資料</button></div><div id="bulk"></div>';
  }

  function loadQueue() {
    var box = document.getElementById('rows');
    if (!box) return;
    API.campaigns(Object.assign({}, F)).then(function (d) {
      box.innerHTML = d.campaigns.length
        ? d.campaigns.map(function (c, i) { return rowHTML(c, i, true); }).join('')
        : emptyState('這個條件下沒有卡片', '換一個判定或狀態看看。');
      renderBulk();
      animate();
      if (F.sort === 'reports') {
        box.insertAdjacentHTML('beforeend',
          '<div class="note note--warn"><div class="note__k">注意排序方式</div><p>' +
          '依回報量排序時，<b>BEC（流程劫持）會沉到很後面</b> —— 它通常只鎖定少數幾個人，' +
          '回報量極低，但損失金額最大。這正是「回報量 ≠ 風險」的實例。</p></div>');
      }
    }).catch(function (e) { box.innerHTML = errState(e); });
  }

  function rowHTML(c, i, selectable) {
    var tacs = (c.tactics || []).map(function (id) {
      var t = global.DATA.tactics.filter(function (x) { return x.id === id; })[0];
      return t ? '<span class="tag tag--soft">' + esc(t.name) + '</span>' : '';
    }).join('');
    return '<article class="row row--' + V_CLS[c.verdict] + (c.status === 'closed' ? ' is-done' : '') +
      (picked.indexOf(c.id) >= 0 ? ' sel-on' : '') +
      '" style="animation-delay:' + Math.min(i * 45, 400) + 'ms">' +
      (selectable
        ? '<button class="cbx' + (picked.indexOf(c.id) >= 0 ? ' on' : '') +
          '" data-pick="' + esc(c.id) + '" aria-label="選取"></button>'
        : '<span></span>') +
      '<div class="row__p"><div class="row__pv">' + c.reports + '</div>' +
        '<div class="row__pk">封回報</div></div>' +
      '<div class="row__m"><div class="row__top">' +
          '<button class="row__cve" data-open="' + esc(c.id) + '">' + esc(c.id) + '</button>' +
          vTag(c.verdict) + stTag(c.status) + tacs +
          '<span class="tag tag--na">' + esc(c.level) + ' 收斂</span>' +
        '</div>' +
        '<div class="row__act">' + esc(c.name) + '</div>' +
        '<div class="row__sub">主旨「' + esc(c.subject) + '」　' +
          '<span style="color:var(--t4)">寄件 ' + dom(c.from) + '　信心 ' + pct(c.confidence) +
          '　' + esc(c.first) + ' 起</span></div>' +
      '</div>' +
      '<div class="sla"><div class="sla__v">' + pct(c.confidence) + '</div>' +
        '<div class="sla__b"><i style="width:' + (c.confidence * 100) + '%;background:' +
        (c.verdict === 'phishing' ? 'var(--r-crit)' : 'var(--r-done)') + '"></i></div></div>' +
      '<div class="row__do">' +
        (c.status === 'open'
          ? '<button class="btn btn--sm" data-act="closed" data-id="' + esc(c.id) + '">處置</button>'
          : '<button class="btn btn--sm" data-act="open" data-id="' + esc(c.id) + '">重開</button>') +
      '</div></article>';
  }

  function renderBulk() {
    var b = document.getElementById('bulk');
    if (!b) return;
    b.innerHTML = picked.length
      ? '<div class="bulk"><span class="bulk__n">已選 <b>' + picked.length + '</b> 張</span>' +
        '<button class="btn btn--sm" data-bulk="closed">標記已處置</button>' +
        '<button class="btn btn--sm" data-bulk="open">重開</button>' +
        '<span style="flex:1"></span>' +
        '<button class="btn btn--sm" data-bulk="clear">取消選取</button></div>'
      : '';
  }

  /* ============================================================
     03 收斂視圖
     ============================================================ */
  function vDedup() {
    head('收斂過程', '312 封信怎麼變成 14 張卡片，以及每一層各收掉多少');
    $view.innerHTML = '<div class="page">' + skeleton(5) + '</div>';
    API.dedup().then(function (d) {
      var s = d.shift, left = s.reports;
      var h = '<div class="page"><div class="card">' +
        '<div class="card__h"><span class="card__t">三層收斂，由便宜到貴</span>' +
        '<span class="card__s">' + s.reports + ' 封 → ' + s.cards + ' 張</span></div>';

      h += '<div class="tbl" style="border:0"><table><thead><tr>' +
        '<th>層級</th><th>方法</th><th>成本</th><th>收掉</th><th>剩餘</th><th>耗時</th>' +
        '</tr></thead><tbody>';
      d.dedup.forEach(function (x) {
        var before = left;
        left -= x.collapsed;
        h += '<tr><td><b>' + esc(x.level) + '</b><br><span style="font-size:11px;color:var(--t4)">' +
          esc(x.name) + '</span></td>' +
          '<td>' + esc(x.how) + '</td>' +
          '<td>' + esc(x.cost) + '</td>' +
          '<td>' + (x.collapsed ? '<b>−' + x.collapsed + '</b>' : '—') + '</td>' +
          '<td class="mono">' + before + ' → ' + left + '</td>' +
          '<td class="mono">' + x.ms + ' ms</td></tr>';
      });
      h += '</tbody></table></div></div>';

      h += '<div class="note"><div class="note__k">為什麼順序是這樣</div><p>' +
        '三層刻意<b>由便宜排到貴</b>：先用幾乎零成本的雜湊比對收掉最多的一批，' +
        '再用字串運算收一批，最後才動用需要向量化的語意分群。<br>' +
        '<b>生成模型放在最後，而且只對「群組」跑一次，不是對每封信跑。</b>' +
        '本班次只呼叫 <b>' + s.llmCalls + ' 次</b>；如果一開始就把 ' + s.llmCallsIfNoDedup +
        ' 封信全丟給模型，成本是 <b>' + Math.round(s.llmCallsIfNoDedup / s.llmCalls) +
        ' 倍</b>，而且效果不會比較好。</p></div>';

      h += '<div class="sec"><h2 class="sec__t">收斂後的實際結果</h2></div>';
      h += '<div class="card"><div class="funnel">' +
        fbar('進來的回報', s.reports, s.reports, 'var(--r-crit)', s.reports + ' 封') +
        fbar('L1 精確比對後', s.reports - 118, s.reports, 'var(--r-high)', (s.reports - 118) + ' 封') +
        fbar('L2 特徵比對後', s.reports - 222, s.reports, 'var(--r-med)', (s.reports - 222) + ' 封') +
        fbar('L3 語意分群後', s.cards, s.reports, 'var(--a)', s.cards + ' 張卡片') +
        '</div></div>';
      $view.innerHTML = h;
    }).catch(function (e) { $view.innerHTML = '<div class="page">' + errState(e) + '</div>'; });
  }

  /* ============================================================
     04 話術體系
     ============================================================ */
  function vTactics() {
    head('話術體系', '技術指標抓不到的部分，只能靠語言模型');
    $view.innerHTML = '<div class="page">' + skeleton(6) + '</div>';
    API.tactics().then(function (d) {
      var no = d.tactics.filter(function (t) { return t.techDetectable === false; }).length;
      var h = '<div class="page"><div class="tbl"><table><thead><tr>' +
        '<th>話術類型</th><th>典型句式</th><th>技術指標抓得到嗎</th><th>損失規模</th><th>本班次</th>' +
        '</tr></thead><tbody>';
      h += d.tactics.map(function (t) {
        var det = t.techDetectable === false
          ? '<span class="tag tag--CRITICAL">抓不到</span>'
          : (t.techDetectable === 'partial'
            ? '<span class="tag tag--MEDIUM">部分</span>'
            : '<span class="tag tag--done">抓得到</span>');
        return '<tr><td><b>' + esc(t.name) + '</b><br>' +
          '<span style="font-size:11px;color:var(--t4)">' + esc(t.desc) + '</span></td>' +
          '<td>' + esc(t.example) + '</td>' +
          '<td>' + det + '</td>' +
          '<td>' + (t.loss === '最高'
            ? '<b style="color:var(--r-crit)">最高</b>' : esc(t.loss)) + '</td>' +
          '<td>' + (t.cards ? '<b>' + t.cards + '</b> 群／' + t.reports + ' 封' : '—') + '</td></tr>';
      }).join('') + '</tbody></table></div>';

      h += '<div class="note note--crit"><div class="note__k">這張表就是本題需要 LLM 的理由</div><p>' +
        '六類話術裡有 <b>' + no + ' 類是純技術指標完全抓不到的</b>。' +
        'SPF、DKIM、網域年齡這些指標能告訴你「這封信來源可疑」，' +
        '但沒辦法告訴你「這封信正在要求變更匯款帳戶」。<br>' +
        '而其中<b>流程劫持（BEC）正是損失金額最大的一類</b> —— ' +
        '它的信件往往通過所有技術檢查（有時甚至來自被入侵的真實帳號），' +
        '唯一的破綻在文字內容本身。' +
        '<b>語言模型在這裡不是加分配件，是唯一能覆蓋這幾個空白格的方法。</b></p></div>';

      var a = d.annotation;
      h += '<div class="sec"><h2 class="sec__t">標註進度</h2>' +
           '<span class="sec__n">ANNOTATION</span></div>';
      h += '<div class="charts"><div class="card">' +
        '<div class="card__h"><span class="card__t">語料標註</span>' +
        '<span class="card__s">' + a.done + ' / ' + a.target + '</span></div>' +
        '<div class="quota__bar" style="height:8px"><i style="width:' +
        (a.done / a.target * 100) + '%"></i></div>' +
        '<div style="margin-top:14px;font-size:12.5px;color:var(--t2)">' +
        '兩人獨立標註一致率 <b style="color:' +
        (a.agreement >= a.agreementTarget ? 'var(--r-done)' : 'var(--r-crit)') + '">' +
        pct(a.agreement) + '</b>（門檻 ' + pct(a.agreementTarget) + '）' +
        (a.agreement >= a.agreementTarget ? ' — 已達標，可以開始大量標註' : ' — 未達標，要先修準則') +
        '</div></div>';

      h += '<div class="card"><div class="card__h"><span class="card__t">各話術已標註數</span></div>' +
        '<div class="mix">' + a.byTactic.map(function (b, i) {
          var t = d.tactics.filter(function (x) { return x.id === b.id; })[0];
          var max = Math.max.apply(null, a.byTactic.map(function (x) { return x.n; }));
          return '<div class="mix__r"><span class="mix__k">' + esc(t.name.slice(0, 5)) + '</span>' +
            '<span class="mix__t"><i style="width:' + (b.n / max * 100) +
            '%;background:' + (b.id === 'T5' ? 'var(--r-crit)' : 'var(--a)') +
            ';animation-delay:' + (i * 80) + 'ms"></i></span>' +
            '<span class="mix__n">' + b.n + '</span></div>';
        }).join('') + '</div>' +
        '<div class="note note--warn" style="margin:16px 0 0"><div class="note__k">樣本不均</div><p>' +
        '<b>流程劫持只有 12 筆</b>，因為 BEC 本來就罕見 —— 但它是損失最大的一類。' +
        '訓練時要特別處理類別不平衡，不能讓模型因為看得少就學不會。</p></div></div></div>';
      $view.innerHTML = h;
      animate();
    }).catch(function (e) { $view.innerHTML = '<div class="page">' + errState(e) + '</div>'; });
  }

  /* ============================================================
     05 模型評測
     ============================================================ */
  function vEval() {
    head('模型評測', '微調前後的對照，以及為什麼 Recall 比 Precision 重要');
    $view.innerHTML = '<div class="page">' + skeleton(5) + '</div>';
    API.evaluation().then(function (d) {
      var h = '<div class="page"><div class="tbl"><table><thead><tr>' +
        '<th>任務</th><th>指標</th><th>未微調</th><th>微調後</th><th>目標</th><th>達標</th>' +
        '</tr></thead><tbody>';
      h += d.eval.map(function (e) {
        var ok = e.ft >= e.target;
        return '<tr><td><b>' + esc(e.task) + '</b></td>' +
          '<td>' + esc(e.metric) + '</td>' +
          '<td class="mono">' + (e.base === null ? '—' : e.base) + '</td>' +
          '<td class="mono"><b style="color:var(--t0)">' + e.ft + '</b></td>' +
          '<td class="mono">' + e.target + '</td>' +
          '<td>' + (ok ? '<span class="tag tag--done">達標</span>'
                       : '<span class="tag tag--CRITICAL">未達</span>') + '</td></tr>';
      }).join('') + '</tbody></table></div>';

      h += '<div class="note note--crit"><div class="note__k">誤判成本是不對稱的</div><p>' +
        '本題<b>不能只看 F1</b>。把釣魚判成正常（漏判）可能造成實際金錢損失；' +
        '把正常判成釣魚（誤報）只是浪費分析師 30 秒。<br>' +
        '因此閾值必須<b>偏向高 Recall</b>，報告中要畫出 Precision-Recall 曲線並標出選定的操作點，' +
        '說明為什麼選在那裡。<b>選在哪裡是一個決策，不是一個預設值。</b></p></div>';

      h += '<div class="note"><div class="note__k">收斂率是最直接的效益指標</div><p>' +
        '其他指標都是模型好不好，只有<b>收斂率</b>直接回答「這套系統幫使用者省了多少事」。' +
        '目標 8 倍，目前模擬資料是 22.3 倍 —— 但要注意收斂率會隨攻擊型態變動：' +
        '<b>大量群發的 campaign 收斂率高，針對性攻擊（如 BEC）本來就收不動。</b>' +
        '報告裡要分開報，不要只報平均值。</p></div>';
      $view.innerHTML = h;
    }).catch(function (e) { $view.innerHTML = '<div class="page">' + errState(e) + '</div>'; });
  }

  /* ============================================================
     06 資料庫架構
     ============================================================ */
  function vSchema() {
    head('資料庫架構', '11 張表與它們的關聯，後端照這個建表');
    $view.innerHTML = '<div class="page">' + skeleton(4, 'skel__k') + '</div>';
    API.schema().then(function (d) {
      var h = '<div class="page">';
      h += '<div class="card rise"><div class="card__h"><span class="card__t">關聯圖</span>' +
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
              '<td class="mono" style="color:var(--a)">' + esc(c[1]) + '</td>' +
              '<td>' + esc(c[2]) + '</td></tr>';
          }).join('') + '</tbody></table></div></div></details>';
      }).join('');

      h += '<div class="note"><div class="note__k">三個設計重點</div><p>' +
        '<b>1. 收斂結果與郵件本體分開。</b> `campaign_members` 是多對多，' +
        '因為收斂規則可能會改 —— 重跑收斂只需要重寫這張表，不動 `messages`。<br>' +
        '<b>2. 話術是多標籤不是單選。</b> `message_tactics` 一封信可以有多個標籤，' +
        '而且記錄來源是模型還是人工，評測時要分開算。<br>' +
        '<b>3. 向量表要記模型版本。</b> `embeddings.model_ver` —— 換 embedding 模型' +
        '就必須全部重算，沒記版本會出現新舊向量混在一起卻查不出原因。</p></div>';

      h += '<div class="note note--warn"><div class="note__k">個資處理</div><p>' +
        '`messages.body_redacted` 存的是<b>已去識別化</b>的內文，' +
        '`reports.reporter_hash` 存的是雜湊而非姓名。原始郵件不進資料庫。<br>' +
        '這不只是隱私考量 —— 研究階段已標明「驗證需要真實郵件（涉個資）」是本題' +
        '<b>落地障礙中高</b>的主因，資料表設計必須先把這件事處理掉。</p></div>';
      h += '</div>';
      $view.innerHTML = h;
    }).catch(function (e) { $view.innerHTML = '<div class="page">' + errState(e) + '</div>'; });
  }

  /* ER 圖：純 SVG，直角、無外部相依 */
  function erDiagram(schema, rels) {
    var W = 940, H = 560;
    var pos = {
      messages:         [390, 240, 160, 74],
      reports:          [120, 100, 150, 50],
      indicators:       [120, 240, 150, 50],
      urls:             [120, 380, 150, 50],
      embeddings:       [390, 400, 160, 50],
      annotations:      [390, 90,  160, 50],
      campaign_members: [660, 170, 170, 50],
      campaigns:        [660, 60,  170, 50],
      message_tactics:  [660, 320, 170, 50],
      tactics:          [660, 430, 170, 50],
      actions:          [660, 500, 170, 46]
    };
    var meta = {};
    schema.forEach(function (t) { meta[t.t] = t; });

    var core = ['messages', 'campaigns'];
    var s = '<svg viewBox="0 0 ' + W + ' ' + H + '" style="width:100%;height:auto;display:block" ' +
      'font-family="var(--mono)">';

    // 關聯線先畫（在方塊底下）
    rels.forEach(function (r) {
      var a = pos[r[0]], b = pos[r[1]];
      if (!a || !b) return;
      var ax = a[0] + a[2] / 2, ay = a[1] + a[3] / 2;
      var bx = b[0] + b[2] / 2, by = b[1] + b[3] / 2;
      s += '<path d="M' + ax + ' ' + ay + ' L' + bx + ' ' + ay + ' L' + bx + ' ' + by +
        '" fill="none" stroke="var(--line-2)" stroke-width="1.2"/>';
      s += '<rect x="' + (bx - 13) + '" y="' + (ay - 7) + '" width="26" height="14" ' +
        'fill="var(--s0)" stroke="var(--line-2)" stroke-width="1"/>' +
        '<text x="' + bx + '" y="' + (ay + 4) + '" text-anchor="middle" font-size="8" ' +
        'fill="var(--t3)">' + esc(r[2]) + '</text>';
    });

    // 方塊
    Object.keys(pos).forEach(function (k) {
      var p = pos[k], m = meta[k];
      if (!m) return;
      var isCore = core.indexOf(k) >= 0;
      s += '<rect x="' + p[0] + '" y="' + p[1] + '" width="' + p[2] + '" height="' + p[3] + '" ' +
        'fill="' + (isCore ? 'var(--s3)' : 'var(--s2)') + '" ' +
        'stroke="' + (isCore ? 'var(--a)' : 'var(--line-3)') + '" stroke-width="' +
        (isCore ? 2 : 1) + '"/>';
      s += '<text x="' + (p[0] + 10) + '" y="' + (p[1] + 19) + '" font-size="11.5" ' +
        'font-weight="700" fill="' + (isCore ? 'var(--a-lit)' : 'var(--t0)') + '">' + esc(k) + '</text>';
      s += '<text x="' + (p[0] + 10) + '" y="' + (p[1] + 34) + '" font-size="9.5" ' +
        'fill="var(--t3)">' + esc(m.label) + '　' + m.cols.length + ' 欄</text>';
      if (p[3] > 60) {
        s += '<text x="' + (p[0] + 10) + '" y="' + (p[1] + 52) + '" font-size="9" ' +
          'fill="var(--t4)">核心表</text>';
      }
    });
    s += '</svg>';
    return '<div style="overflow-x:auto">' + s + '</div>';
  }

  /* ---------- 側滑：campaign 詳細 ---------- */
  function openCampaign(id) {
    var scrim = el('<div class="scrim"></div>');
    var draw = el('<aside class="draw"><div class="draw__h">' +
      '<span class="draw__t">' + esc(id) + '</span>' +
      '<button class="draw__x" aria-label="關閉">✕</button></div>' +
      '<div class="draw__b">' + skeleton(4) + '</div></aside>');
    document.body.appendChild(scrim); document.body.appendChild(draw);
    document.body.style.overflow = 'hidden';
    function close() {
      scrim.remove(); draw.remove(); document.body.style.overflow = '';
      document.removeEventListener('keydown', onKey);
    }
    function onKey(e) { if (e.key === 'Escape') close(); }
    scrim.addEventListener('click', close);
    draw.querySelector('.draw__x').addEventListener('click', close);
    document.addEventListener('keydown', onKey);

    API.campaign(id).then(function (r) {
      var c = r.campaign, i = c.indicators;
      var h = '<div class="bar" style="margin-bottom:16px">' + vTag(c.verdict) + stTag(c.status) +
        '<span class="tag tag--na">' + esc(c.level) + ' 收斂</span>' +
        '<span style="flex:1"></span><span style="font-size:11.5px;color:var(--t3)">' +
        c.reports + ' 封回報　' + esc(c.first) + ' – ' + esc(c.last) + '</span></div>';

      h += '<h3 style="font-size:17px;margin-bottom:12px">' + esc(c.name) + '</h3>';

      h += '<div class="cmp"><div class="cmp__c"><div class="cmp__k">郵件樣本</div>' +
        '<div class="fld"><div class="fld__k">寄件人</div><div class="fld__v mono">' +
          dom(c.from) + '</div></div>' +
        '<div class="fld"><div class="fld__k">主旨</div><div class="fld__v">' + esc(c.subject) + '</div></div>' +
        '<div class="fld"><div class="fld__k">內文摘要</div><div class="fld__v">' + esc(c.snippet) + '</div></div>' +
        (c.spoof ? '<div class="fld"><div class="fld__k">偽裝手法</div><div class="fld__v">' +
          esc(c.spoof) + '</div></div>' : '') +
        '</div>' +
        '<div class="cmp__c"><div class="cmp__k">技術指標</div>' +
        ind('SPF', i.spf) + ind('DKIM', i.dkim) + ind('DMARC', i.dmarc) +
        '<div class="fld"><div class="fld__k">網域年齡</div><div class="fld__v mono">' +
          (i.domainAge === null ? '多來源' : i.domainAge + ' 天' +
            (i.domainAge < 30 ? ' <span class="tag tag--CRITICAL">極新</span>' : '')) + '</div></div>' +
        '<div class="fld"><div class="fld__k">連結</div><div class="fld__v mono">' + i.urls + ' 個' +
          (i.mismatch ? ' <span class="tag tag--CRITICAL">顯示與實際不符</span>' : '') + '</div></div>' +
        (i.attach ? '<div class="fld"><div class="fld__k">附件</div><div class="fld__v mono">' +
          esc(i.attach) + '</div></div>' : '') +
        '</div></div>';

      if (r.tactics.length) {
        h += '<div class="sec"><h2 class="sec__t">辨識到的話術</h2></div>';
        h += '<div class="tbl"><table><tbody>' + r.tactics.map(function (t) {
          return '<tr><td style="width:120px"><b>' + esc(t.name) + '</b></td>' +
            '<td>' + esc(t.example) + '</td>' +
            '<td style="width:100px">' + (t.techDetectable === false
              ? '<span class="tag tag--CRITICAL">技術指標抓不到</span>' : '') + '</td></tr>';
        }).join('') + '</tbody></table></div>';
      }

      h += '<div class="note"><div class="note__k">判定理由（模型生成）</div><p>' +
        esc(c.why).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>') + '</p></div>';

      h += '<div class="note ' + (c.verdict === 'phishing' ? 'note--crit' : '') + '">' +
        '<div class="note__k">建議處置</div><p>' + esc(c.action) + '</p></div>';
      draw.querySelector('.draw__b').innerHTML = h;
    }).catch(function (e) { draw.querySelector('.draw__b').innerHTML = errState(e); });
  }

  function ind(k, v) {
    var cls = v === 'pass' ? 'done' : (v === 'fail' ? 'CRITICAL' : 'na');
    return '<div class="fld"><div class="fld__k">' + k + '</div>' +
      '<div class="fld__v"><span class="tag tag--' + cls + '">' + esc(v) + '</span></div></div>';
  }

  /* ---------- 共用 ---------- */
  function head(t, s) { $title.textContent = t; $sub.textContent = s; }

  function animate(scope) {
    var root = scope || document;
    Array.prototype.forEach.call(root.querySelectorAll('[data-count]'), function (n) {
      var to = Number(n.dataset.count), t0 = performance.now(), dur = 700;
      (function step(now) {
        var p = Math.min(1, (now - t0) / dur);
        n.textContent = Math.round(to * (1 - Math.pow(1 - p, 3)));
        if (p < 1) requestAnimationFrame(step);
      })(t0);
    });
  }

  function refreshBadges() {
    API.campaigns({ status: 'open' }).then(function (d) {
      var b = document.querySelector('[data-badge="queue"]');
      if (b) {
        b.textContent = d.campaigns.length;
        b.classList.toggle('nav__b--hot',
          d.campaigns.some(function (c) { return c.verdict === 'phishing'; }));
      }
    }).catch(function () {});
  }

  /* ---------- 路由 ---------- */
  var ROUTES = { '': vHome, queue: vQueue, dedup: vDedup, tactics: vTactics,
                 eval: vEval, schema: vSchema };

  function paint() {
    var seg = (location.hash || '#/').replace(/^#\/?/, '').split('/').filter(Boolean);
    var page = seg[0] || '';
    (ROUTES[page] || vHome)();
    Array.prototype.forEach.call(document.querySelectorAll('.nav__i'), function (b) {
      b.classList.toggle('on', b.dataset.nav === page);
    });
    if (page === 'queue' && seg[1]) openCampaign(seg[1]);
  }

  /* ---------- 事件 ---------- */
  document.addEventListener('click', function (e) {
    var t = e.target;
    if (!t.closest) return;

    var nav = t.closest('[data-nav]');
    if (nav) { location.hash = '#/' + nav.dataset.nav; return; }

    var open = t.closest('[data-open]');
    if (open) { openCampaign(open.dataset.open); return; }

    var act = t.closest('[data-act]');
    if (act) {
      var id = act.dataset.id, to = act.dataset.act;
      var prev = to === 'closed' ? 'open' : 'closed';
      API.patchCampaign(id, { status: to }).then(function () {
        loadQueue(); refreshBadges();
        toast(id + ' → ' + (to === 'closed' ? '已處置' : '重新開啟'), 'ok', function () {
          API.patchCampaign(id, { status: prev }).then(function () { loadQueue(); refreshBadges(); });
        });
      }).catch(function (err) { toast('更新失敗：' + err.message, 'err'); });
      return;
    }

    var pick = t.closest('[data-pick]');
    if (pick) {
      var pid = pick.dataset.pick, k = picked.indexOf(pid);
      if (k >= 0) picked.splice(k, 1); else picked.push(pid);
      pick.classList.toggle('on');
      pick.closest('.row').classList.toggle('sel-on');
      renderBulk();
      return;
    }

    var bulk = t.closest('[data-bulk]');
    if (bulk) {
      var op = bulk.dataset.bulk;
      if (op === 'clear') { picked = []; loadQueue(); return; }
      var list = picked.slice(), n = list.length;
      API.bulkCampaign(list, { status: op }).then(function () {
        picked = []; loadQueue(); refreshBadges();
        toast('已把 ' + n + ' 張標記為「' + (op === 'closed' ? '已處置' : '待處理') + '」', 'ok',
          function () {
            API.bulkCampaign(list, { status: op === 'closed' ? 'open' : 'closed' })
              .then(function () { loadQueue(); refreshBadges(); });
          });
      }).catch(function (err) { toast('批次更新失敗：' + err.message, 'err'); });
      return;
    }

    var f = t.closest('[data-f]');
    if (f && f.tagName === 'BUTTON') {
      F[f.dataset.f] = f.dataset.v;
      picked = [];
      Array.prototype.forEach.call(document.querySelectorAll('[data-f="' + f.dataset.f + '"]'),
        function (x) { if (x.tagName === 'BUTTON') x.classList.toggle('on', x === f); });
      loadQueue();
      return;
    }

    if (t.closest('#reset')) {
      API.reset().then(function (r) {
        if (r.reset === false) { toast(r.note || '此模式不支援重置', 'err'); return; }
        picked = []; loadQueue(); refreshBadges(); toast('已還原成示範資料', 'ok');
      });
      return;
    }

    var ing = t.closest('#ingest');
    if (ing) {
      ing.disabled = true;
      ing.innerHTML = '<span class="btn__sp"></span>分析中';
      API.ingest().then(function (r) {
        ing.disabled = false; ing.textContent = '上傳 .eml';
        toast(r.note || '分析完成', r.ok ? 'ok' : 'err');
      }).catch(function (err) {
        ing.disabled = false; ing.textContent = '上傳 .eml';
        toast('失敗：' + err.message, 'err');
      });
    }
  });

  document.addEventListener('change', function (e) {
    var s = e.target.closest ? e.target.closest('select[data-f]') : null;
    if (s) { F[s.dataset.f] = s.value; loadQueue(); }
  });

  var timer = 0;
  $search.addEventListener('input', function () {
    clearTimeout(timer);
    var v = $search.value.trim();
    timer = setTimeout(function () {
      F.q = v;
      var page = (location.hash || '').replace(/^#\/?/, '').split('/')[0];
      if (page === 'queue') loadQueue(); else location.hash = '#/queue';
    }, 260);
  });

  window.addEventListener('hashchange', paint);

  document.getElementById('mode').textContent =
    API.mode === 'http' ? 'API ' + API.base : 'API mock';
  refreshBadges();
  paint();
})(window);
