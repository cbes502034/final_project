/* ============================================================
   app.js — VULNSCOPE 前端
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

  /* 篩選條件放這裡，換頁不會掉 */
  var F = {
    queue: { status: 'open', sev: 'all', sort: 'priority', q: '' },
    adv:   { matched: 'all', sev: 'all', q: '' },
    asset: { clarity: 'all', q: '' }
  };
  var picked = [];

  /* ---------- 小工具 ---------- */
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function el(html) { var d = document.createElement('div'); d.innerHTML = html.trim(); return d.firstChild; }

  var SEV_TW = { CRITICAL: '重大', HIGH: '高', MEDIUM: '中', LOW: '低' };
  var ST_TW  = { open: '待處理', done: '已修補', snoozed: '已延後', na: '不適用' };
  var SEV_VAR = { CRITICAL: 'crit', HIGH: 'high', MEDIUM: 'med', LOW: 'low' };

  function sevTag(s, n) {
    return '<span class="tag tag--' + s + '">' + SEV_TW[s] + (n != null ? ' ' + n : '') + '</span>';
  }
  function expoTag(e) {
    return '<span class="tag tag--' + (e === '對外' ? 'out' : 'in') + '">' + esc(e) + '</span>';
  }
  function stTag(s) {
    if (s === 'done')    return '<span class="tag tag--done">已修補</span>';
    if (s === 'snoozed') return '<span class="tag tag--soft">已延後</span>';
    if (s === 'na')      return '<span class="tag tag--na">不適用</span>';
    return '';
  }

  /* ---------- 浮動提示（含復原） ---------- */
  function toast(msg, kind, undo) {
    var t = el('<div class="toast' + (kind ? ' toast--' + kind : '') + '">' +
      '<span class="toast__t">' + esc(msg) + '</span>' +
      (undo ? '<button class="toast__u">復原</button>' : '') + '</div>');
    if (undo) {
      t.querySelector('.toast__u').addEventListener('click', function () { t.remove(); undo(); });
    }
    $toasts.appendChild(t);
    setTimeout(function () {
      t.style.transition = 'opacity .25s, transform .25s';
      t.style.opacity = '0';
      t.style.transform = 'translateX(16px)';
      setTimeout(function () { t.remove(); }, 260);
    }, undo ? 6000 : 3200);
  }

  /* ---------- 狀態畫面 ---------- */
  function skeleton(n, cls) {
    var s = '<div class="skel">';
    for (var i = 0; i < (n || 5); i++) s += '<div class="skel__r' + (cls ? ' ' + cls : '') + '"></div>';
    return s + '</div>';
  }
  function emptyState(t, s) {
    return '<div class="empty">' +
      '<svg class="empty__ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4">' +
      '<path d="M3 3h18v18H3z"/><path d="M8 12h8"/></svg>' +
      '<div class="empty__t">' + esc(t) + '</div><div class="empty__s">' + esc(s) + '</div></div>';
  }
  function errState(e) {
    return '<div class="err"><div class="err__t">讀取失敗</div>' +
      '<div class="err__s">' + esc(e && e.message ? e.message : String(e)) +
      '<br>目前模式：<b>' + API.mode + '</b>' + (API.base ? '（' + esc(API.base) + '）' : '') + '</div></div>';
  }

  /* ============================================================
     01 總覽
     ============================================================ */
  function vHome() {
    head('總覽', '這批情資跟你有沒有關、現在最該做什麼');
    $view.innerHTML = '<div class="page">' + skeleton(4, 'skel__k') + '</div>';

    API.summary().then(function (d) {
      var h = '<div class="page"><div class="kpis">';
      h += kpi('本批情資', d.batch, '條', d.relevant + ' 條與你有關 · ' + d.irrelevant + ' 條無關', 'a', 0);
      h += kpi('待處理', d.open, '件', d.overdue ? d.overdue + ' 件已逾期' : '目前沒有逾期', d.overdue ? 'crit' : 'ok', 1);
      h += kpi('受影響資產', d.affected, '台', '跨 ' + d.relevant + ' 項資產類別', 'warn', 2);
      h += kpi('名稱待補', d.vague, '項', d.vague ? '組不出 CPE，查不動' : '全部可查', d.vague ? 'warn' : 'ok', 3);
      h += '</div>';

      h += '<div class="sec"><h2 class="sec__t">趨勢與分佈</h2><span class="sec__n">LAST 14 DAYS</span></div>';
      h += '<div class="charts">';
      h += '<div class="card rise"><div class="card__h"><span class="card__t">每日新增與結案</span>' +
           '<span class="card__s">本週 +' + d.weekly.opened + ' / −' + d.weekly.closed + '</span></div>' +
           trendChart(d.trend) +
           '<div class="lgd"><span><i style="background:var(--r-high)"></i>新增</span>' +
           '<span><i style="background:var(--r-done)"></i>結案</span>' +
           '<span style="margin-left:auto">平均修補 ' + d.weekly.mttr + ' 天</span></div></div>';

      h += '<div class="card rise" style="animation-delay:80ms"><div class="card__h">' +
           '<span class="card__t">待辦的嚴重度分佈</span></div>' + sevMix(d.sevMix) +
           '<div class="card__h" style="margin:22px 0 14px"><span class="card__t">處理狀況</span></div>' +
           '<div class="rings">' +
             ring(d.weekly.closed, d.weekly.opened, 'var(--r-done)', '本週結案率') +
             ring(d.open - d.overdue, d.open, 'var(--a)', '仍在 SLA 內') +
           '</div></div>';
      h += '</div>';

      if (d.topUnmatched) {
        h += '<div class="note note--crit"><div class="note__k">本批分數最高的那一條，不在你的待辦裡</div><p>' +
          '<b>' + esc(d.topUnmatched.id) + '</b> 的 CVSS 是 <b>' + d.topUnmatched.score + '</b>，全批最高，' +
          '但它影響的是 <b>' + esc(d.topUnmatched.product) + '</b> —— 你的資產清單沒有這項產品，判定為無關。<br>' +
          '照 CVSS 排序，你的第一件事會是去處理一條跟自己無關的公告。' +
          '這就是影響面判定要做在優先序<b>前面</b>的原因。</p></div>';
      }

      h += '<div class="sec"><h2 class="sec__t">最該先做的三件事</h2>' +
           '<button class="btn btn--sm" data-nav="queue" style="margin-left:auto">看全部待辦 ▸</button></div>';
      h += '<div class="rows" id="top3">' + skeleton(3) + '</div></div>';
      $view.innerHTML = h;
      animate();
      return API.queue({ status: 'open', sort: 'priority' });
    }).then(function (d) {
      if (!d) return;
      var box = document.getElementById('top3');
      if (!box) return;
      box.innerHTML = d.queue.slice(0, 3).map(function (q, i) { return rowHTML(q, i, false); }).join('') ||
        emptyState('沒有待處理項目', '這批情資裡沒有與你的資產相關的漏洞。');
    }).catch(function (e) {
      $view.innerHTML = '<div class="page">' + errState(e) + '</div>';
    });
  }

  function kpi(k, v, unit, sub, mod, i) {
    return '<div class="kpi kpi--' + mod + '" style="animation-delay:' + (i * 60) + 'ms">' +
      '<div class="kpi__k">' + esc(k) + '</div>' +
      '<div class="kpi__v"><span data-count="' + v + '">0</span><small>' + esc(unit) + '</small></div>' +
      '<div class="kpi__s">' + esc(sub) + '</div></div>';
  }

  /* 折線圖：純 SVG，無外部相依 */
  function trendChart(t) {
    var W = 520, H = 132, P = 8;
    var max = Math.max.apply(null, t.map(function (d) { return Math.max(d.new, d.closed); })) || 1;
    function pts(key) {
      return t.map(function (d, i) {
        var x = P + i * ((W - P * 2) / (t.length - 1));
        var y = H - P - (d[key] / max) * (H - P * 2);
        return x.toFixed(1) + ',' + y.toFixed(1);
      }).join(' ');
    }
    var grid = [0, .25, .5, .75, 1].map(function (f) {
      var y = (P + f * (H - P * 2)).toFixed(1);
      return '<line x1="' + P + '" y1="' + y + '" x2="' + (W - P) + '" y2="' + y +
             '" stroke="var(--line)" stroke-width="1"/>';
    }).join('');
    return '<svg viewBox="0 0 ' + W + ' ' + H + '" style="width:100%;height:auto;display:block">' + grid +
      '<polyline points="' + pts('new') + '" fill="none" stroke="var(--r-high)" stroke-width="2"/>' +
      '<polyline points="' + pts('closed') + '" fill="none" stroke="var(--r-done)" stroke-width="2"/>' +
      '</svg><div style="display:flex;justify-content:space-between;font-family:var(--mono);' +
      'font-size:9.5px;color:var(--t4);margin-top:6px">' +
      '<span>' + esc(t[0].d) + '</span><span>' + esc(t[t.length - 1].d) + '</span></div>';
  }

  function sevMix(mix) {
    var max = Math.max.apply(null, mix.map(function (m) { return m.n; })) || 1;
    return '<div class="mix">' + mix.map(function (m, i) {
      return '<div class="mix__r"><span class="mix__k">' + SEV_TW[m.sev] + '</span>' +
        '<span class="mix__t"><i style="width:' + (m.n / max * 100) + '%;background:var(--r-' +
        SEV_VAR[m.sev] + ');animation-delay:' + (i * 90) + 'ms"></i></span>' +
        '<span class="mix__n">' + m.n + '</span></div>';
    }).join('') + '</div>';
  }

  function ring(v, total, color, label) {
    var R = 30, C = 2 * Math.PI * R;
    var pct = total ? Math.max(0, Math.min(1, v / total)) : 0;
    return '<div class="ring"><svg width="76" height="76" viewBox="0 0 76 76">' +
      '<circle class="bg" cx="38" cy="38" r="' + R + '"/>' +
      '<circle class="fg" cx="38" cy="38" r="' + R + '" stroke="' + color +
      '" stroke-dasharray="' + C.toFixed(1) + '" stroke-dashoffset="' + C.toFixed(1) +
      '" data-ring="' + (C * (1 - pct)).toFixed(1) + '"/></svg>' +
      '<div class="ring__v">' + Math.round(pct * 100) + '%</div>' +
      '<div class="ring__k">' + esc(label) + '</div></div>';
  }

  /* ============================================================
     02 修補優先序
     ============================================================ */
  function vQueue() {
    head('修補優先序', '排序依據四個因子，每一列都看得到怎麼算的');
    $view.innerHTML = '<div class="page">' + toolbar() +
      '<div class="rows" id="rows">' + skeleton(5) + '</div></div>';
    loadQueue();
  }

  function toolbar() {
    var sts = [['open', '待處理'], ['done', '已修補'], ['snoozed', '已延後'], ['na', '不適用'], ['all', '全部']];
    var sevs = [['all', '全部'], ['CRITICAL', '重大'], ['HIGH', '高'], ['MEDIUM', '中'], ['LOW', '低']];
    return '<div class="bar"><div class="chips">' + sts.map(function (s) {
        return '<button class="chip' + (F.queue.status === s[0] ? ' on' : '') +
          '" data-f="status" data-v="' + s[0] + '">' + s[1] + '</button>';
      }).join('') + '</div>' +
      '<select class="sel" data-f="sev">' + sevs.map(function (s) {
        return '<option value="' + s[0] + '"' + (F.queue.sev === s[0] ? ' selected' : '') +
          '>嚴重度：' + s[1] + '</option>';
      }).join('') + '</select>' +
      '<select class="sel" data-f="sort">' +
        '<option value="priority"' + (F.queue.sort === 'priority' ? ' selected' : '') + '>依優先度</option>' +
        '<option value="sla"' + (F.queue.sort === 'sla' ? ' selected' : '') + '>依 SLA 剩餘</option>' +
        '<option value="cvss"' + (F.queue.sort === 'cvss' ? ' selected' : '') + '>依 CVSS</option>' +
      '</select><span style="flex:1"></span>' +
      '<button class="btn btn--sm" id="reset">重置示範資料</button></div><div id="bulk"></div>';
  }

  function loadQueue() {
    var box = document.getElementById('rows');
    if (!box) return;
    API.queue(Object.assign({}, F.queue)).then(function (d) {
      box.innerHTML = d.queue.length
        ? d.queue.map(function (q, i) { return rowHTML(q, i, true); }).join('')
        : emptyState('這個條件下沒有項目',
            F.queue.status === 'open' ? '待辦都處理完了，或把篩選放寬一點。' : '換一個狀態或嚴重度看看。');
      renderBulk();
      animate();
    }).catch(function (e) { box.innerHTML = errState(e); });
  }

  function rowHTML(q, i, selectable) {
    var cls = q.left <= 0 ? 'over' : (q.left <= 2 ? 'soon' : 'ok');
    var pct = Math.max(0, Math.min(100, q.left / q.sla * 100));
    return '<article class="row row--' + q.sev + (q.status !== 'open' ? ' is-done' : '') +
      (picked.indexOf(q.cve) >= 0 ? ' sel-on' : '') +
      '" style="animation-delay:' + Math.min(i * 45, 400) + 'ms">' +
      (selectable
        ? '<button class="cbx' + (picked.indexOf(q.cve) >= 0 ? ' on' : '') +
          '" data-pick="' + esc(q.cve) + '" aria-label="選取"></button>'
        : '<span></span>') +
      '<div class="row__p"><div class="row__pv">' + q.priority + '</div>' +
        '<div class="row__pk">PRIORITY</div></div>' +
      '<div class="row__m"><div class="row__top">' +
          '<button class="row__cve" data-open="' + esc(q.cve) + '">' + esc(q.cve) + '</button>' +
          sevTag(q.sev, q.score) + expoTag(q.exposure) + stTag(q.status) +
        '</div>' +
        '<div class="row__act">' + esc(q.action) + '</div>' +
        '<div class="row__sub">' + esc(q.title) + ' · <b>' + q.count + ' 台</b> · ' + esc(q.owner) +
          '<span style="color:var(--t4)">　優先度 = CVSS ' + q.f.cvss + ' × 暴露 ' + q.f.expo +
          ' × 台數 ' + q.f.cnt + ' × 修補 ' + q.f.patch + '</span></div>' +
      '</div>' +
      '<div class="sla sla--' + cls + '"><div class="sla__v">' +
        (q.left <= 0 ? '逾期 ' + Math.abs(q.left) + ' 天' : '剩 ' + q.left + ' 天') + '</div>' +
        '<div class="sla__b"><i style="width:' + pct + '%"></i></div></div>' +
      '<div class="row__do">' +
        (q.status === 'open'
          ? '<button class="btn btn--sm" data-act="done" data-cve="' + esc(q.cve) + '">修補</button>' +
            '<button class="btn btn--sm" data-act="snoozed" data-cve="' + esc(q.cve) + '">延後</button>'
          : '<button class="btn btn--sm" data-act="open" data-cve="' + esc(q.cve) + '">還原</button>') +
      '</div></article>';
  }

  function renderBulk() {
    var b = document.getElementById('bulk');
    if (!b) return;
    b.innerHTML = picked.length
      ? '<div class="bulk"><span class="bulk__n">已選 <b>' + picked.length + '</b> 筆</span>' +
        '<button class="btn btn--sm" data-bulk="done">標記已修補</button>' +
        '<button class="btn btn--sm" data-bulk="snoozed">延後</button>' +
        '<button class="btn btn--sm" data-bulk="na">不適用</button>' +
        '<span style="flex:1"></span>' +
        '<button class="btn btn--sm" data-bulk="clear">取消選取</button></div>'
      : '';
  }

  function setStatus(cve, status) {
    API.queue({ status: 'all' }).then(function (d) {
      var row = d.queue.filter(function (x) { return x.cve === cve; })[0];
      var prev = row ? row.status : 'open';
      return API.patchQueue(cve, { status: status }).then(function () {
        loadQueue(); refreshBadges();
        toast(cve + ' → ' + ST_TW[status], 'ok', function () {
          API.patchQueue(cve, { status: prev }).then(function () { loadQueue(); refreshBadges(); });
        });
      });
    }).catch(function (e) { toast('更新失敗：' + e.message, 'err'); });
  }

  /* ============================================================
     03 漏洞情資
     ============================================================ */
  function vAdvisories() {
    head('漏洞情資', '整批依 CVSS 排列，刻意不先過濾 —— 分數高低跟跟你有沒有關是兩件事');
    var ms = [['all', '全部'], ['hit', '命中'], ['miss', '無關']];
    $view.innerHTML = '<div class="page"><div class="bar"><div class="chips">' +
      ms.map(function (m) {
        return '<button class="chip' + (F.adv.matched === m[0] ? ' on' : '') +
          '" data-af="matched" data-v="' + m[0] + '">' + m[1] + '</button>';
      }).join('') + '</div></div><div id="advbox">' + skeleton(6) + '</div></div>';
    loadAdv();
  }

  function loadAdv() {
    var box = document.getElementById('advbox');
    if (!box) return;
    API.advisories(Object.assign({}, F.adv)).then(function (d) {
      if (!d.advisories.length) { box.innerHTML = emptyState('沒有符合的情資', '換個篩選條件試試。'); return; }
      var h = '<div class="tbl"><table><thead><tr>' +
        '<th>CVE</th><th>CVSS</th><th>產品</th><th>判定</th><th>受影響資產</th><th>發布</th>' +
        '</tr></thead><tbody>' +
        d.advisories.map(function (a) {
          if (!a.matched) {
            return '<tr class="dim"><td class="mono">' + esc(a.id) + '</td>' +
              '<td>' + sevTag(a.sev, a.score) + '</td><td>' + esc(a.product) + '</td>' +
              '<td><span class="tag tag--na">無關</span></td>' +
              '<td style="color:var(--t4)">清單中沒有這項產品</td>' +
              '<td class="mono">' + esc(a.published) + '</td></tr>';
          }
          return '<tr class="clickable" data-open="' + esc(a.id) + '">' +
            '<td><span class="lnk">' + esc(a.id) + '</span></td>' +
            '<td>' + sevTag(a.sev, a.score) + '</td>' +
            '<td>' + esc(a.extracted.vendor) + ' ' + esc(a.extracted.product) + '</td>' +
            '<td><span class="tag tag--done">命中</span>' +
              (a.extracted.patch === '已釋出' ? '' : ' <span class="tag tag--MEDIUM">無修補版本</span>') + '</td>' +
            '<td>點開看比對</td>' +
            '<td class="mono">' + esc(a.published) + '</td></tr>';
        }).join('') + '</tbody></table></div>' +
        '<div class="note"><div class="note__k">無關的也留著</div><p>' +
        '判定為無關的公告不會刪掉，因為<b>資產清單會變</b> —— 今天沒裝的東西明天可能就裝了。' +
        '清單一更新就會重新比對一次。</p></div>';
      box.innerHTML = h;
    }).catch(function (e) { box.innerHTML = errState(e); });
  }

  /* ============================================================
     04 資產清單
     ============================================================ */
  function vAssets() {
    head('資產清單', '你自己維護，系統不掃描你的網路，也不需要任何存取權限');
    $view.innerHTML = '<div class="page"><div class="bar">' +
      '<button class="btn btn--go" id="addasset">＋ 新增資產</button></div>' +
      '<div id="assetbox">' + skeleton(6) + '</div></div>';
    loadAssets();
  }

  function loadAssets() {
    var box = document.getElementById('assetbox');
    if (!box) return;
    API.assets(Object.assign({}, F.asset)).then(function (d) {
      if (!d.assets.length) {
        box.innerHTML = emptyState('還沒有資產', '先新增幾項，系統才知道哪些漏洞跟你有關。');
        return;
      }
      box.innerHTML = '<div class="tbl"><table><thead><tr>' +
        '<th>資產</th><th>版本</th><th>台數</th><th>暴露</th><th>負責</th><th>CPE</th><th></th>' +
        '</tr></thead><tbody>' +
        d.assets.map(function (a) {
          return '<tr class="' + (a.clarity === 'vague' ? 'vague' : '') + '">' +
            '<td><b>' + esc(a.name) + '</b><br><span style="font-size:11px;color:' +
              (a.clarity === 'vague' ? 'var(--r-med)' : 'var(--t4)') + '">' +
              esc(a.clarity === 'vague' ? (a.hint || '資料不足') : a.tag) + '</span></td>' +
            '<td class="mono">' + esc(a.version || '—') + '</td>' +
            '<td><b>' + a.count + '</b></td>' +
            '<td>' + expoTag(a.exposure) + '</td>' +
            '<td>' + esc(a.owner) + '</td>' +
            '<td class="mono" style="max-width:250px;word-break:break-all">' +
              (a.cpe ? esc(a.cpe) : '<span class="miss">組不出 CPE</span>') + '</td>' +
            '<td><button class="btn btn--sm" data-edit="' + esc(a.id) + '">編輯</button></td></tr>';
        }).join('') + '</tbody></table></div>' +
        '<div class="note note--warn"><div class="note__k">為什麼不自動掃描</div><p>' +
        '自動掃描要拿到對方網路的存取權限，那是導入時最難跨過的一道門。改成使用者自建清單，' +
        '中小企業或校園網管自己就能開始用。代價是清單要人維護 —— 所以系統必須明講哪幾項寫得不夠清楚，' +
        '而不是默默亂猜。<b>亂猜會產生假警報，而且白白消耗查詢額度。</b></p></div>';
    }).catch(function (e) { box.innerHTML = errState(e); });
  }

  /* ============================================================
     05 查詢軌跡
     ============================================================ */
  function vTrace() {
    head('查詢軌跡', '模型呼叫了哪些工具、帶什麼參數、拿到什麼、花掉多少額度');
    $view.innerHTML = '<div class="page">' + skeleton(6) + '</div>';
    API.trace().then(function (d) {
      $view.innerHTML = '<div class="page"><div class="trc">' +
        d.trace.map(function (t, i) {
          return '<div class="trc__r" style="animation-delay:' + (i * 45) + 'ms">' +
            '<div class="trc__s">' + t.s + '</div>' +
            '<div><div class="trc__t">' + esc(t.tool) + '</div>' +
              '<div class="trc__a">' + esc(t.args) + '</div></div>' +
            '<div class="trc__v">' + esc(t.res) + '</div>' +
            '<div class="trc__m">' + esc(t.cache) +
              '<br><span style="color:var(--t4)">' + t.ms + ' ms</span></div>' +
            '<div class="trc__q">' + esc(t.quota) + '</div></div>';
        }).join('') + '</div>' +
        '<div class="note"><div class="note__k">額度守門</div><p>' +
        'NVD 的介接限制是<b>無金鑰每 30 秒 5 次、有金鑰 50 次</b>。三道防線：本地快取優先、' +
        '同一項產品 24 小時內只查一次、名稱不夠明確的資產<b>先追問而不是先查</b> —— ' +
        '上面第 2 步就是這樣省下兩次呼叫的。</p></div></div>';
    }).catch(function (e) { $view.innerHTML = '<div class="page">' + errState(e) + '</div>'; });
  }

  /* ============================================================
     側滑面板
     ============================================================ */
  function drawer(titleHTML, bodyHTML, footHTML, width) {
    var scrim = el('<div class="scrim"></div>');
    var draw = el('<aside class="draw"' + (width ? ' style="width:' + width + '"' : '') + '>' +
      '<div class="draw__h">' + titleHTML +
      '<button class="draw__x" aria-label="關閉">✕</button></div>' +
      '<div class="draw__b">' + bodyHTML + '</div>' +
      (footHTML ? '<div class="draw__f">' + footHTML + '</div>' : '') + '</aside>');
    document.body.appendChild(scrim);
    document.body.appendChild(draw);
    document.body.style.overflow = 'hidden';

    function close() {
      scrim.remove(); draw.remove();
      document.body.style.overflow = '';
      document.removeEventListener('keydown', onKey);
    }
    function onKey(e) { if (e.key === 'Escape') close(); }
    scrim.addEventListener('click', close);
    draw.querySelector('.draw__x').addEventListener('click', close);
    document.addEventListener('keydown', onKey);
    return { el: draw, close: close };
  }

  var NA = '原文未提供';

  function openAdvisory(cve) {
    var d = drawer('<span class="draw__t">' + esc(cve) + '</span>', skeleton(4), '');
    API.advisory(cve).then(function (r) {
      var a = r.advisory, asset = r.asset, e = a.extracted;
      var h = '<div class="bar" style="margin-bottom:16px">' + sevTag(a.sev, a.score) +
        '<span class="mono" style="font-size:11px;color:var(--t3)">' + esc(a.vector) + '</span>' +
        '<span style="flex:1"></span><span style="font-size:11.5px;color:var(--t3)">發布 ' +
        esc(a.published) + '　修改 ' + esc(a.modified) + '</span></div>';

      h += '<div class="cmp"><div class="cmp__c"><div class="cmp__k">公告原文（NVD）</div>' +
        '<div class="cmp__raw">' + esc(a.desc) + '</div></div>' +
        '<div class="cmp__c"><div class="cmp__k">抽取結果</div>' +
        fld('產品', e.vendor + ' ' + e.product, e.conf.product) +
        fld('弱點類型', e.kind, null) +
        fld('受影響版本', e.affected, e.conf.affected) +
        fld('修補版本', e.fixed, e.conf.patch) +
        fld('攻擊途徑', e.av, null) +
        fld('所需權限', e.priv, null) +
        fld('使用者互動', e.ui, null) +
        fld('緩解措施', e.work, e.conf.work) + '</div></div>';

      var na = ['affected', 'fixed', 'work', 'priv', 'ui'].filter(function (k) { return e[k] === NA; }).length;
      if (na) {
        h += '<div class="note note--warn"><div class="note__k">有 ' + na + ' 個欄位原文沒寫</div><p>' +
          '這些欄位標成「原文未提供」，<b>不由模型補上</b>。版本號尤其危險 —— 猜一個看起來合理的版本號，' +
          '會讓人升級到不存在的版本，或誤以為自己不受影響。抽不到就要說抽不到，這是硬規則。</p></div>';
      }

      h += '<div class="sec"><h2 class="sec__t">影響面判定</h2><span class="sec__n">CPE MATCH</span></div>' +
        '<div class="cpe"><div class="cpe__r"><span class="cpe__k">你的資產</span>' +
        '<span class="cpe__v">' + esc(asset.cpe) + '</span></div>';
      a.cpe.forEach(function (c, i) {
        var rg = [];
        if (c.ge) rg.push('≥ ' + c.ge);
        if (c.lt) rg.push('< ' + c.lt);
        if (c.le) rg.push('≤ ' + c.le);
        h += '<div class="cpe__r"><span class="cpe__k">' + (i ? '' : '公告範圍') + '</span>' +
          '<span class="cpe__v">' + esc(c.c) +
          (rg.length ? ' <em>' + esc(rg.join(' , ')) + '</em>' : '') + '</span></div>';
      });
      h += '<div class="cpe__r"><span class="cpe__k">判定</span>' +
        '<span class="cpe__v cpe__hit">命中 — ' + esc(asset.name) + '，' + asset.count + ' 台，' +
        esc(asset.exposure) + '，' + esc(asset.owner) + '</span></div></div>';

      if (a.refs && a.refs.length) {
        h += '<div class="note"><div class="note__k">來源</div><p>' + a.refs.map(function (u) {
          return '<a href="' + esc(u) + '" target="_blank" rel="noopener">' + esc(u) + '</a>';
        }).join('<br>') + '</p></div>';
      }
      d.el.querySelector('.draw__b').innerHTML = h;
      animate(d.el);
    }).catch(function (err) {
      d.el.querySelector('.draw__b').innerHTML = errState(err);
    });
  }

  function fld(k, v, conf) {
    if (v === NA) {
      return '<div class="fld"><div class="fld__k">' + esc(k) + '</div>' +
        '<div class="fld__v"><span class="miss">原文未提供</span></div></div>';
    }
    var lo = conf !== null && conf > 0 && conf < .8;
    return '<div class="fld' + (lo ? ' fld--lo' : '') + '">' +
      '<div class="fld__k">' + esc(k) + '</div><div class="fld__v">' + esc(v) +
      (conf === null || !conf ? '' :
        '<div class="fld__c"><span class="fld__t"><i style="width:' + Math.round(conf * 100) +
        '%"></i></span><span class="fld__n">信心 ' + Math.round(conf * 100) + '%</span></div>') +
      '</div></div>';
  }

  function openAsset(id) {
    API.assets({}).then(function (r) {
      var a = id ? r.assets.filter(function (x) { return x.id === id; })[0] : null;
      var body = '<div class="form">' +
        fi('name', '資產名稱', a ? a.name : '', '例如 WatchGuard Firebox T145', true) +
        fi('vendor', '廠牌 vendor', a ? a.vendor : '', '例如 watchguard') +
        fi('product', '產品 product', a ? a.product : '', '例如 fireware') +
        fi('version', '版本 version', a ? a.version : '', '例如 12.10.2') +
        fi('count', '台數', a ? a.count : 1, '', false, 'number') +
        fs('exposure', '暴露面', a ? a.exposure : '內網', ['對外', '內網']) +
        fs('owner', '負責單位', a ? a.owner : '資訊室', ['網管組', '系統組', '資訊室']) +
        '</div><div class="note note--warn" style="margin-top:18px">' +
        '<div class="note__k">廠牌 · 產品 · 版本 三者缺一就查不動</div><p>' +
        '系統要用這三項組出 CPE 才能跟公告比對。缺任何一項，這筆資產會被標成「名稱待補」，' +
        '<b>不會被亂猜，也不會消耗查詢額度</b>。</p></div>';
      var foot = '<button class="btn btn--go" data-save>' + (a ? '儲存' : '新增') + '</button>' +
        '<button class="btn" data-cancel>取消</button><span style="flex:1"></span>' +
        (a ? '<button class="btn btn--danger" data-del="' + esc(a.id) + '">刪除</button>' : '');
      var d = drawer('<span class="draw__t">' + (a ? '編輯資產' : '新增資產') + '</span>',
                     body, foot, 'min(560px,96vw)');

      d.el.querySelector('[data-cancel]').addEventListener('click', d.close);
      d.el.querySelector('[data-save]').addEventListener('click', function () {
        var b = {};
        Array.prototype.forEach.call(d.el.querySelectorAll('[data-k]'), function (i) {
          b[i.dataset.k] = i.type === 'number' ? Number(i.value) : i.value.trim();
        });
        if (!b.name) { toast('資產名稱不能空白', 'err'); return; }
        (a ? API.patchAsset(a.id, b) : API.createAsset(b)).then(function (res) {
          d.close(); loadAssets(); refreshBadges();
          toast((a ? '已更新 ' : '已新增 ') + res.name +
                (res.clarity === 'vague' ? '（標記為名稱待補）' : ''), 'ok');
        }).catch(function (e) { toast('儲存失敗：' + e.message, 'err'); });
      });
      var del = d.el.querySelector('[data-del]');
      if (del) del.addEventListener('click', function () {
        API.deleteAsset(del.dataset.del).then(function () {
          d.close(); loadAssets(); refreshBadges(); toast('已刪除 ' + a.name, 'ok');
        }).catch(function (e) { toast('刪除失敗：' + e.message, 'err'); });
      });
    });
  }

  function fi(k, label, v, ph, wide, type) {
    return '<div class="f' + (wide ? ' f--wide' : '') + '"><label>' + esc(label) + '</label>' +
      '<input data-k="' + k + '" type="' + (type || 'text') + '" value="' + esc(v) +
      '" placeholder="' + esc(ph || '') + '"></div>';
  }
  function fs(k, label, v, opts) {
    return '<div class="f"><label>' + esc(label) + '</label><select data-k="' + k + '">' +
      opts.map(function (o) { return '<option' + (o === v ? ' selected' : '') + '>' + esc(o) + '</option>'; }).join('') +
      '</select></div>';
  }

  /* ============================================================
     共用
     ============================================================ */
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
    Array.prototype.forEach.call(root.querySelectorAll('[data-ring]'), function (c) {
      requestAnimationFrame(function () { c.style.strokeDashoffset = c.dataset.ring; });
    });
  }

  function refreshBadges() {
    API.summary().then(function (d) {
      var q = document.querySelector('[data-badge="queue"]');
      if (q) { q.textContent = d.open; q.classList.toggle('nav__b--hot', d.overdue > 0); }
      var a = document.querySelector('[data-badge="assets"]');
      if (a) a.textContent = d.vague ? d.vague + '!' : '';
      var s = document.getElementById('synced');
      if (s) s.textContent = '上次同步 ' + d.synced;
    }).catch(function () {});
    API.quota().then(function (q) {
      var bar = document.getElementById('qbar'), txt = document.getElementById('qtxt');
      if (bar) bar.style.width = (q.used / q.limit * 100) + '%';
      if (txt) txt.textContent = q.used + ' / ' + q.limit;
    }).catch(function () {});
  }

  /* ============================================================
     路由
     ============================================================ */
  var ROUTES = { '': vHome, queue: vQueue, advisories: vAdvisories, assets: vAssets, trace: vTrace };

  function paint() {
    var seg = (location.hash || '#/').replace(/^#\/?/, '').split('/').filter(Boolean);
    var page = seg[0] || '';
    (ROUTES[page] || vHome)();
    Array.prototype.forEach.call(document.querySelectorAll('.nav__i'), function (b) {
      b.classList.toggle('on', b.dataset.nav === page);
    });
    if (page === 'advisories' && seg[1]) openAdvisory(seg[1]);
  }

  /* ============================================================
     事件
     ============================================================ */
  document.addEventListener('click', function (e) {
    var t = e.target;
    if (!t.closest) return;

    var nav = t.closest('[data-nav]');
    if (nav) { location.hash = '#/' + nav.dataset.nav; return; }

    var open = t.closest('[data-open]');
    if (open) { openAdvisory(open.dataset.open); return; }

    var edit = t.closest('[data-edit]');
    if (edit) { openAsset(edit.dataset.edit); return; }

    if (t.closest('#addasset')) { openAsset(null); return; }

    var act = t.closest('[data-act]');
    if (act) { setStatus(act.dataset.cve, act.dataset.act); return; }

    var pick = t.closest('[data-pick]');
    if (pick) {
      var cve = pick.dataset.pick, i = picked.indexOf(cve);
      if (i >= 0) picked.splice(i, 1); else picked.push(cve);
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
      API.bulkQueue(list, { status: op }).then(function () {
        picked = []; loadQueue(); refreshBadges();
        toast('已把 ' + n + ' 筆標記為「' + ST_TW[op] + '」', 'ok', function () {
          API.bulkQueue(list, { status: 'open' }).then(function () { loadQueue(); refreshBadges(); });
        });
      }).catch(function (err) { toast('批次更新失敗：' + err.message, 'err'); });
      return;
    }

    var f = t.closest('[data-f]');
    if (f && f.tagName === 'BUTTON') {
      F.queue[f.dataset.f] = f.dataset.v;
      picked = [];
      Array.prototype.forEach.call(document.querySelectorAll('[data-f="' + f.dataset.f + '"]'), function (x) {
        if (x.tagName === 'BUTTON') x.classList.toggle('on', x === f);
      });
      loadQueue();
      return;
    }

    var af = t.closest('[data-af]');
    if (af) {
      F.adv[af.dataset.af] = af.dataset.v;
      Array.prototype.forEach.call(document.querySelectorAll('[data-af="' + af.dataset.af + '"]'), function (x) {
        x.classList.toggle('on', x === af);
      });
      loadAdv();
      return;
    }

    if (t.closest('#reset')) {
      API.reset().then(function (r) {
        if (r.reset === false) { toast(r.note || '此模式不支援重置', 'err'); return; }
        picked = []; loadQueue(); refreshBadges(); toast('已還原成示範資料', 'ok');
      });
      return;
    }

    var sync = t.closest('#sync');
    if (sync) {
      sync.disabled = true;
      sync.innerHTML = '<span class="btn__sp"></span>同步中';
      API.sync().then(function (r) {
        sync.disabled = false; sync.textContent = '同步 NVD';
        toast(r.note || '同步完成', r.started ? 'ok' : 'err');
        refreshBadges();
      }).catch(function (err) {
        sync.disabled = false; sync.textContent = '同步 NVD';
        toast('同步失敗：' + err.message, 'err');
      });
    }
  });

  document.addEventListener('change', function (e) {
    var s = e.target.closest ? e.target.closest('select[data-f]') : null;
    if (s) { F.queue[s.dataset.f] = s.value; loadQueue(); }
  });

  var searchTimer = 0;
  $search.addEventListener('input', function () {
    clearTimeout(searchTimer);
    var v = $search.value.trim();
    searchTimer = setTimeout(function () {
      var page = (location.hash || '').replace(/^#\/?/, '').split('/')[0];
      if (page === 'advisories') { F.adv.q = v; loadAdv(); }
      else if (page === 'assets') { F.asset.q = v; loadAssets(); }
      else if (page === 'queue') { F.queue.q = v; loadQueue(); }
      else { F.queue.q = v; location.hash = '#/queue'; }
    }, 260);
  });

  window.addEventListener('hashchange', paint);

  /* ---------- 啟動 ---------- */
  document.getElementById('mode').textContent =
    API.mode === 'http' ? 'API ' + API.base : 'API mock';
  refreshBadges();
  paint();
})(window);
