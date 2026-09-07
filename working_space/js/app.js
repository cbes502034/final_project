/* ============================================================
   app.js — 路由與五個畫面
   純前端原型：所有資料來自 js/data.js，沒有後端。
   欄位結構即為之後後端 API 的契約草案。
   ============================================================ */
(function (global) {
  'use strict';

  var D = global.DATA;
  var root = document.getElementById('view');
  var assetById = {};
  D.assets.forEach(function (a) { assetById[a.id] = a; });
  var advById = {};
  D.advisories.forEach(function (a) { advById[a.id] = a; });
  var ALL = D.advisories.concat(D.unmatched).sort(function (a, b) { return b.score - a.score; });

  var NAV = [
    { id: '', n: '01', t: '總覽', c: null },
    { id: 'queue', n: '02', t: '修補優先序', c: D.queue.length },
    { id: 'advisories', n: '03', t: '漏洞情資', c: ALL.length },
    { id: 'assets', n: '04', t: '資產清單', c: D.assets.length },
    { id: 'trace', n: '05', t: '查詢軌跡', c: D.trace.length }
  ];

  /* ---------- 工具 ---------- */
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
  function sevCls(sev) {
    return { CRITICAL: 'crit', HIGH: 'high', MEDIUM: 'med', LOW: 'low' }[sev] || 'low';
  }
  function sevTw(sev) {
    return { CRITICAL: '重大', HIGH: '高', MEDIUM: '中', LOW: '低' }[sev] || sev;
  }
  function pill(cls, txt) { return '<span class="pill pill--' + cls + '">' + esc(txt) + '</span>'; }
  function expoPill(e) { return pill(e === '對外' ? 'out' : 'in', e); }

  /* ============================================================
     01 總覽
     ============================================================ */
  function vHome() {
    var hits = D.queue.length;
    var affected = D.queue.reduce(function (s, q) { return s + assetById[q.asset].count; }, 0);
    var vague = D.assets.filter(function (a) { return a.clarity === 'vague'; }).length;
    var top = D.queue[0];
    var ta = assetById[top.asset];

    var topAll = ALL[0];

    var h = head('總覽',
      '這一批情資有 ' + ALL.length + ' 條，系統逐條與你的資產清單比對，只留下跟你有關的。' +
      '下面的數字是判定結果，不是情資總量。');

    h += '<div class="tiles">';
    h += tile('本批情資', ALL.length, '條', '同步時間 ' + D.meta.synced, '');
    h += tile('與你有關', hits, '條', '其餘 ' + D.unmatched.length + ' 條判定為無關，不進待辦', 'hot');
    h += tile('受影響資產', affected, '台', '跨 ' + hits + ' 項資產類別', 'hot');
    h += tile('名稱不明確', vague, '項', vague ? '無法組出 CPE，需要補資料' : '全部可查', vague ? '' : 'good');
    h += '</div>';

    h += '<div class="sh"><h2 class="sh__t">現在最該先做的一件事</h2>' +
         '<span class="sh__n">TOP PRIORITY</span></div>';
    h += actCard(top, true);

    if (!topAll.matched) {
      h += '<div class="note note--warn"><div class="note__k">本批分數最高的那一條，不在你的待辦裡</div><p>' +
        '<strong>' + esc(topAll.id) + '</strong> 的 CVSS 是 <strong>' + topAll.score +
        '</strong>，全批最高，但它影響的是 <strong>' + esc(topAll.product) + '</strong>——' +
        '你的資產清單裡沒有這項產品，所以判定為無關。' +
        '<strong>照 CVSS 排序會讓你先去處理一條跟自己無關的公告。</strong>' +
        '這就是「影響面判定」要做在「優先序」前面的原因。</p></div>';
    }

    h += '<div class="note"><div class="note__k">為什麼是這一條</div><p>' +
      '排序不是照 CVSS 高低。' + esc(top.cve) + ' 的 CVSS 是 ' + top.f.cvss +
      '，但它同時是<strong>對外暴露</strong>而且<strong>影響 ' + ta.count + ' 台</strong>，' +
      '所以綜合優先度高於分數更高但只影響一兩台內網機器的項目。' +
      '完整的因子拆解在每一張待辦卡上都看得到。</p></div>';

    if (vague) {
      h += '<div class="note note--warn"><div class="note__k">有 ' + vague + ' 項資產查不動</div><p>' +
        '資產清單上有 ' + vague + ' 項只寫了籠統名稱（例如「防火牆」），組不出 CPE 就無法比對。' +
        '系統不會亂猜，而是列出來請你補「廠牌 + 型號 + 版本」。' +
        '亂猜會產生假警報，而且會白白消耗查詢額度。</p></div>';
    }
    return h;
  }

  function tile(k, v, unit, sub, mod) {
    return '<div class="tile' + (mod ? ' tile--' + mod : '') + '">' +
      '<div class="tile__k">' + esc(k) + '</div>' +
      '<div class="tile__v">' + v + '<small>' + esc(unit) + '</small></div>' +
      '<div class="tile__s">' + esc(sub) + '</div></div>';
  }

  /* ============================================================
     02 修補優先序
     ============================================================ */
  function vQueue() {
    var h = head('修補優先序',
      '每一筆待辦都附上優先度是怎麼算出來的。分數本身不重要，重要的是你能看懂為什麼這件事排在前面，' +
      '並且在不同意的時候知道該調哪一個因子。');
    h += D.queue.map(function (q) { return actCard(q, false); }).join('');
    h += '<div class="note"><div class="note__k">優先度公式</div><p>' +
      '<code>優先度 = CVSS ÷ 10 × 暴露係數 × 資產數係數 × 修補可得係數 × 100</code><br>' +
      '暴露係數：對外 1.0、內網 0.6。資產數係數：1 台 1.0、2–5 台 1.15、6–20 台 1.3、20 台以上 1.45。' +
      '修補可得係數：官方已釋出修補 1.0、只有緩解措施 0.8。' +
      '<strong>這條公式刻意做成看得見、可以吵的。</strong>每個組織的暴露定義不一樣，係數本來就該讓使用者自己調。</p></div>';
    return h;
  }

  function actCard(q, isTop) {
    var a = assetById[q.asset], ad = advById[q.cve];
    return '<article class="act' + (q.rank === 1 ? ' act--1' : '') + '">' +
      '<div class="act__top">' +
        '<span class="act__rk">' + q.rank + '</span>' +
        '<span class="act__id" data-go="advisories/' + esc(q.cve) + '">' + esc(q.cve) + '</span>' +
        pill(sevCls(ad.sev), sevTw(ad.sev) + ' ' + ad.score) +
        expoPill(a.exposure) +
        '<span class="act__pri"><div class="act__pv">' + q.priority + '</div>' +
        '<div class="act__pk">PRIORITY</div></span>' +
      '</div>' +
      '<div class="act__body">' +
        '<div class="act__what">' + esc(q.action) + '</div>' +
        '<div class="act__where">' + esc(a.name) + ' · <b>' + a.count + ' 台</b> · ' +
          esc(a.owner) + '　目前版本 <b>' + esc(a.version) + '</b></div>' +
        (isTop ? '' : fx(q)) +
      '</div></article>';
  }

  function fx(q) {
    return '<div class="fx">' +
      fxc('CVSS', q.f.cvss) + fxc('暴露係數', '×' + q.f.expo) +
      fxc('資產數係數', '×' + q.f.cnt) + fxc('修補可得', '×' + q.f.patch) +
      '<div class="fx__c fx__c--eq"><div class="fx__k">優先度</div><div class="fx__v">' + q.priority + '</div></div>' +
      '</div>';
  }
  function fxc(k, v) {
    return '<div class="fx__c"><div class="fx__k">' + esc(k) + '</div><div class="fx__v">' + esc(v) + '</div></div>';
  }

  /* ============================================================
     03 漏洞情資
     ============================================================ */
  function vAdvisories() {
    var h = head('漏洞情資',
      '整批 ' + ALL.length + ' 條依 CVSS 由高到低排列——刻意不先過濾，這樣才看得出「分數高低」和' +
      '「跟你有沒有關」是兩件不同的事。命中的那幾條可以點進去看原文與抽取欄位的對照。');
    h += '<div class="tw"><table><thead><tr>' +
      '<th>CVE</th><th>CVSS</th><th>產品</th><th>判定</th><th>受影響資產</th><th>發布</th>' +
      '</tr></thead><tbody>';
    h += ALL.map(function (a) {
      if (!a.matched) {
        return '<tr style="opacity:.62"><td class="mono">' + esc(a.id) + '</td>' +
          '<td>' + pill(sevCls(a.sev), sevTw(a.sev) + ' ' + a.score) + '</td>' +
          '<td>' + esc(a.product) + '</td>' +
          '<td>' + pill('low', '無關') + '</td>' +
          '<td style="color:var(--c-faint)">清單中沒有這項產品</td>' +
          '<td class="mono">' + esc(a.published) + '</td></tr>';
      }
      var asset = assetById[a.matched];
      return '<tr class="rowlink" data-go="advisories/' + esc(a.id) + '">' +
        '<td><b class="mono">' + esc(a.id) + '</b></td>' +
        '<td>' + pill(sevCls(a.sev), sevTw(a.sev) + ' ' + a.score) + '</td>' +
        '<td>' + esc(a.extracted.vendor) + ' ' + esc(a.extracted.product) + '</td>' +
        '<td>' + pill('ok', '命中') + '</td>' +
        '<td><b>' + esc(asset.name) + '</b> ×' + asset.count + '　' + expoPill(asset.exposure) + '</td>' +
        '<td class="mono">' + esc(a.published) + '</td></tr>';
    }).join('');
    h += '</tbody></table></div>';
    h += '<div class="note"><div class="note__k">' + D.unmatched.length + ' 條無關的也留著</div><p>' +
      '判定為無關的公告不會刪掉，因為<strong>資產清單會變</strong>——今天沒裝的東西明天可能就裝了。' +
      '清單一更新，這些公告會重新比對一次。</p></div>';
    return h;
  }

  function vAdvisory(id) {
    var a = advById[id];
    if (!a) return vAdvisories();
    var asset = assetById[a.matched];
    var e = a.extracted;

    var h = '<button class="back" data-go="advisories">◄ 回到情資清單</button>';
    h += '<div class="phead"><h1 class="phead__t">' + esc(a.id) + '</h1>' +
      '<div class="phead__s">' +
        pill(sevCls(a.sev), sevTw(a.sev) + ' ' + a.score) + ' ' +
        '<span class="mono" style="font-size:11.5px">' + esc(a.vector) + '</span><br>' +
        '發布 ' + esc(a.published) + '　最後修改 ' + esc(a.modified) + '　狀態 ' + esc(a.status) +
      '</div></div>';

    h += '<div class="split">';
    h += '<div class="split__c"><div class="split__k">公告原文（NVD）</div>' +
         '<div class="split__raw">' + esc(a.desc) + '</div></div>';
    h += '<div class="split__c"><div class="split__k">抽取結果</div><div class="fields">' +
      field('產品', e.vendor + ' ' + e.product, e.conf.product) +
      field('受影響版本', e.affected, e.conf.affected) +
      field('修補版本', e.fixed, e.conf.patch) +
      field('攻擊途徑', e.av, null) +
      field('所需權限', e.priv, null) +
      field('使用者互動', e.ui, null) +
      field('緩解措施', e.work, e.conf.work) +
      '</div></div>';
    h += '</div>';

    h += '<div class="sh"><h2 class="sh__t">影響面判定</h2><span class="sh__n">CPE MATCH</span></div>';
    h += '<div class="cpe">';
    h += '<div class="cpe__row"><span class="cpe__k">你的資產</span><span class="cpe__v">' +
         esc(asset.cpe) + '</span></div>';
    a.cpe.forEach(function (c, i) {
      var rng = [];
      if (c.ge) rng.push('≥ ' + c.ge);
      if (c.lt) rng.push('< ' + c.lt);
      if (c.le) rng.push('≤ ' + c.le);
      h += '<div class="cpe__row"><span class="cpe__k">' + (i ? '' : '公告範圍') + '</span>' +
        '<span class="cpe__v">' + esc(c.c) + (rng.length ? '　<span style="color:var(--c-dim)">' + esc(rng.join(' , ')) + '</span>' : '') +
        '</span></div>';
    });
    h += '<div class="cpe__row"><span class="cpe__k">判定</span>' +
      '<span class="cpe__v cpe__hit">命中 — ' + esc(asset.name) + '，' + asset.count + ' 台，' +
      esc(asset.exposure) + '，負責單位 ' + esc(asset.owner) + '</span></div>';
    h += '</div>';

    if (a.refs.length) {
      h += '<div class="note"><div class="note__k">來源</div><p>' +
        a.refs.map(function (u) {
          return '<a href="' + esc(u) + '" target="_blank" rel="noopener">' + esc(u) + '</a>';
        }).join('<br>') + '</p></div>';
    }
    return h;
  }

  function field(k, v, conf) {
    var lo = conf !== null && conf < .8;
    return '<div class="field' + (lo ? ' field--lo' : '') + '">' +
      '<div class="field__k">' + esc(k) + '</div>' +
      '<div class="field__v">' + esc(v) +
      (conf === null ? '' :
        '<div class="field__c"><div class="field__bar"><i style="width:' + Math.round(conf * 100) + '%"></i></div>' +
        '<span class="field__n">信心 ' + Math.round(conf * 100) + '%</span></div>') +
      '</div></div>';
  }

  /* ============================================================
     04 資產清單
     ============================================================ */
  function vAssets() {
    var h = head('資產清單',
      '這份清單由你自己維護，系統不掃描你的網路，也不需要任何存取權限。' +
      '清單的品質直接決定判定的品質——寫得夠具體才查得動。');
    h += '<div class="tw"><table><thead><tr>' +
      '<th>資產</th><th>版本</th><th>台數</th><th>暴露</th><th>負責</th><th>CPE</th>' +
      '</tr></thead><tbody>';
    h += D.assets.map(function (a) {
      if (a.clarity === 'vague') {
        return '<tr class="is-vague"><td><b>' + esc(a.name) + '</b><br>' +
          '<span style="font-size:11.5px">' + esc(a.hint) + '</span></td>' +
          '<td>—</td><td>' + a.count + '</td><td>' + expoPill(a.exposure) + '</td>' +
          '<td>' + esc(a.owner) + '</td><td>' + pill('warn', '無法組出') + '</td></tr>';
      }
      return '<tr><td><b>' + esc(a.name) + '</b><br><span style="font-size:11.5px;color:var(--c-dim)">' +
        esc(a.tag) + '</span></td>' +
        '<td class="mono">' + esc(a.version) + '</td>' +
        '<td><b>' + a.count + '</b></td>' +
        '<td>' + expoPill(a.exposure) + '</td>' +
        '<td>' + esc(a.owner) + '</td>' +
        '<td class="mono">' + esc(a.cpe) + '</td></tr>';
    }).join('');
    h += '</tbody></table></div>';
    h += '<div class="note note--warn"><div class="note__k">為什麼不自動掃描</div><p>' +
      '自動掃描要拿到對方網路的存取權限，那是導入時最難跨過的一道門。' +
      '改成使用者自建清單，中小企業或校園網管自己就能開始用，不必先說服任何人開權限。' +
      '代價是清單要人維護——所以系統必須明講哪幾項寫得不夠清楚。</p></div>';
    return h;
  }

  /* ============================================================
     05 查詢軌跡
     ============================================================ */
  function vTrace() {
    var h = head('查詢軌跡',
      '模型每一次呼叫了什麼工具、帶了什麼參數、拿到什麼、花了多久、有沒有吃到快取、額度剩多少——全部攤開。' +
      '工具呼叫最怕變成黑盒子，出錯時沒有這份紀錄就無從追起。');
    h += '<div class="tr">';
    h += D.trace.map(function (t) {
      return '<div class="tr__row">' +
        '<div class="tr__s">' + t.s + '</div>' +
        '<div><span class="tr__t">' + esc(t.tool) + '</span>' +
          '<span class="tr__a">' + esc(t.args) + '</span></div>' +
        '<div class="tr__r">' + esc(t.res) + '</div>' +
        '<div class="tr__m">' + esc(t.cache) + '<br><span style="color:var(--c-faint)">' + t.ms + ' ms</span></div>' +
        '<div class="tr__q">' + esc(t.quota) + '</div>' +
      '</div>';
    }).join('');
    h += '</div>';
    h += '<div class="note"><div class="note__k">額度守門</div><p>' +
      'NVD 的介接限制是<strong>無金鑰每 30 秒 5 次、有金鑰 50 次</strong>。' +
      '所以三道防線：本地快取優先、同一項產品 24 小時內只查一次、' +
      '名稱不夠明確的資產<strong>先追問而不是先查</strong>——上面第 2 步就是這樣省下兩次呼叫的。</p></div>';
    return h;
  }

  /* ---------- 版面零件 ---------- */
  function head(t, s) {
    return '<div class="phead"><h1 class="phead__t">' + esc(t) + '</h1>' +
      '<p class="phead__s">' + esc(s) + '</p></div>';
  }

  /* ============================================================
     路由
     ============================================================ */
  function parse() {
    var raw = (location.hash || '#/').replace(/^#\/?/, '');
    return raw.split('/').filter(Boolean);
  }

  function paint() {
    var seg = parse();
    var page = seg[0] || '';
    var html;
    if (page === 'queue') html = vQueue();
    else if (page === 'advisories') html = seg[1] ? vAdvisory(seg[1]) : vAdvisories();
    else if (page === 'assets') html = vAssets();
    else if (page === 'trace') html = vTrace();
    else html = vHome();

    root.innerHTML = '<div class="wrap">' + html + footHTML() + '</div>';
    Array.prototype.forEach.call(document.querySelectorAll('.rail__i'), function (b) {
      b.classList.toggle('is-on', b.dataset.go === page);
    });
    window.scrollTo(0, 0);
  }

  function footHTML() {
    return '<div class="foot">' +
      '這是前端原型，沒有後端：資產清單與判定結果為模擬資料，CVE 內容取自 NVD 真實資料。<br>' +
      'This product uses data from the NVD API but is not endorsed or certified by the NVD.' +
      '</div>';
  }

  /* ---------- 導覽與事件 ---------- */
  function mountRail() {
    var q = D.meta.quota;
    document.getElementById('nav').innerHTML = NAV.map(function (n) {
      return '<button class="rail__i" type="button" data-go="' + n.id + '">' +
        '<span class="rail__n">' + n.n + '</span>' +
        '<span class="rail__t">' + esc(n.t) + '</span>' +
        (n.c ? '<span class="rail__c">' + n.c + '</span>' : '') +
      '</button>';
    }).join('');
    document.getElementById('quota').innerHTML =
      '<div class="rail__q">介接額度 ' + q.used + ' / ' + q.limit + '（' + esc(q.window) + '）</div>' +
      '<div class="rail__bar"><i style="width:' + Math.round(q.used / q.limit * 100) + '%"></i></div>' +
      '<div class="rail__sync">上次同步 ' + esc(D.meta.synced) + '<br>' + esc(D.meta.org) + '</div>';
  }

  document.addEventListener('click', function (e) {
    var t = e.target.closest ? e.target.closest('[data-go]') : null;
    if (!t) return;
    location.hash = '#/' + t.dataset.go;
  });

  window.addEventListener('hashchange', paint);

  mountRail();
  paint();
})(window);
