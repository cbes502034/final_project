/* ============================================================
   app.js — 路由、主頁（Top 10）、詳細頁、版本切換、連續瀏覽
   ============================================================ */
(function (global) {
  'use strict';

  var root = document.getElementById('root');
  var R = window.Render, D = window.Diagram;
  var PJ = window.PROJECTS || [];
  var META = window.META || {};

  PJ.sort(function (a, b) { return a.rank - b.rank; });
  var byId = {};
  PJ.forEach(function (p) { byId[p.id] = p; });

  /* ---------- 背景電路裝飾 ---------- */
  var cir = document.getElementById('circuitry');
  if (cir) cir.innerHTML = D.circuitry();

  /* ---------- 工具 ---------- */
  function esc(s) { return R.esc(s); }

  function piTag(p) {
    var m = { '核心': 'pi-core', '選配': 'pi-opt', '不需要': 'pi-no' };
    return '<span class="tag tag--' + (m[p.pi.k] || 'pi-no') + '">RPi:' + esc(p.pi.k) + '</span>';
  }
  function fcTag(p) {
    var m = { '必要': 'fc-must', '加分': 'fc-good', '有限': 'fc-low' };
    return '<span class="tag tag--' + (m[p.fc.k] || 'fc-low') + '">FC:' + esc(p.fc.k) + '</span>';
  }

  /* ============================================================
     主頁
     ============================================================ */
  function homeHTML() {
    var h = '';

    /* -- Hero -- */
    h += '<section class="wrap hero" id="sec-intro">';
    h += '<div class="hero__kicker">' + esc(META.kicker) + '</div>';
    h += '<h1 class="hero__title">' + META.title + '</h1>';
    h += '<p class="hero__lede">' + R.inline(META.lede) + '</p>';
    h += '<div class="spec">' + META.spec.map(function (s) {
      return '<div class="spec__cell"><div class="spec__k">' + esc(s[0]) + '</div><div class="spec__v">' + R.inline(s[1]) +
        (s[2] ? '<br><small>' + esc(s[2]) + '</small>' : '') + '</div></div>';
    }).join('') + '</div>';
    h += '</section>';

    /* -- Function Calling 說明（卡片上到處是 FC 標記，先講清楚） -- */
    var F = META.fcHome || {};
    h += '<section class="wrap fcn">';
    h += '<div class="fcn__k">FUNCTION CALLING</div>';
    h += '<p class="fcn__lede">' + R.inline(F.lede || '') + '</p>';
    h += '<div class="fcn__cols">' + (F.cols || []).map(function (c) {
      return '<div class="fcn__c"><div class="fcn__ct"><b>' + esc(c[0]) + '</b>' +
             '<span>' + esc(c[1]) + '</span></div>' +
             '<p>' + R.inline(c[2]) + '</p></div>';
    }).join('') + '</div>';
    h += '<p class="fcn__tail">' + R.inline(F.tail || '') + '</p>';
    h += '</section>';

    /* -- Top 10 -- */
    h += '<section class="wrap section" id="top20">';
    h += '<button class="docs-cta" data-go="about">' +
         '<span class="docs-cta__k">專案說明文件</span>' +
         '<span class="docs-cta__t">題目怎麼來的、依據什麼限制篩選、每一項分數怎麼給、所有數字的出處</span>' +
         '<span class="docs-cta__go">開啟</span></button>';
    h += secHead('', 'Top 10 專題排名', 'SCORED / EVIDENCE-BASED');
    h += '<div class="filters" id="filters">';
    h += '<button data-f="all" class="is-on">ALL · ' + PJ.length + '</button>';
    META.domains.forEach(function (d) {
      var n = PJ.filter(function (p) { return p.domain === d; }).length;
      h += '<button data-f="' + esc(d) + '">' + esc(d) + ' · ' + n + '</button>';
    });
    h += '</div>';
    h += '<div class="picks" id="picks"></div>';
    h += '<div class="grid" id="list">' + PJ.map(cardHTML).join('') + '</div>';
    h += '</section>';

    /* -- 頁尾：只留一句話與專案說明入口 -- */
    h += '<footer class="wrap foot">';
    h += '<div class="foot__note">' + R.inline(META.footNote) + '</div>';
    h += '</footer>';

    return h;
  }

  /* ============================================================
     專案說明文件（獨立頁，抽屜式，預設全部收合）
     ============================================================ */
  function aboutHTML() {
    var h = '<div class="wrap ab">';
    h += '<div class="ab-head">';
    h += '<div class="dt-head__crumb"><a href="#/">TOP 10</a><span>/</span>專案說明</div>';
    h += '<h1 class="ab-head__t">專案說明文件</h1>';
    h += '<p class="ab-head__lede">' + R.inline(META.aboutLede) + '</p>';
    h += '<div class="ab-head__act">';
    h += '<button class="ab-tog" data-acc="open">全部展開</button>';
    h += '<button class="ab-tog" data-acc="close">全部收合</button>';
    h += '</div></div>';

    (META.about || []).forEach(function (d, i) {
      h += '<details class="acc" id="' + esc(d.id) + '" data-sec="' + esc(d.t.split('：')[0].split('（')[0]) + '">';
      h += '<summary class="acc__h">';
      h += '<span class="acc__n">' + String(i + 1).padStart(2, '0') + '</span>';
      h += '<span class="acc__t">' + esc(d.t) + '</span>';
      h += '<span class="acc__en">' + esc(d.en) + '</span>';
      h += '<span class="acc__ic" aria-hidden="true"><i></i><i></i></span>';
      h += '</summary>';
      h += '<div class="acc__b">' + aboutBody(d.use) + '</div>';
      h += '</details>';
    });

    h += '<div class="pager"><button class="pager__b pager__b--home" data-go="home">' +
         '<span class="pager__k">INDEX</span><span class="pager__t">返回 Top 10</span></button></div>';
    h += '</div>';
    return h;
  }

  function aboutBody(use) {
    if (use === 'pipeline') {
      return '<p class="ab-lede">' + R.inline(META.methodLede) + '</p>' +
        '<div class="pipe">' + META.pipeline.map(function (x, i) {
          return '<div class="pipe__step"><div class="pipe__n">' + String(i + 1).padStart(2, '0') +
                 '</div><div class="pipe__t">' + esc(x) + '</div></div>';
        }).join('') + '</div>';
    }
    if (use === 'scoring') {
      var rows = (META.scoreItems || []).map(function (it) {
        return [it[0], String(it[1]), it[2]];
      });
      return '<div class="body">' + R.blocks([
        { t: 'table', head: ['評分項目', '配分', '判斷依據'], rows: rows },
        { t: 'note', k: '未來延展性', kind: 'info',
          x: '刻意不計分，只在分數接近時作為參考。理由是延展性人人都能講，' +
             '一旦計分就會變成比誰想像力好，而不是比誰的證據紮實。' }
      ]) + '</div>';
    }
    if (use === 'sources') {
      return '<div class="foot__grid">' + (META.foot || []).map(function (c) {
        return '<div><div class="foot__t">' + esc(c.t) + '</div><ul>' +
          c.items.map(function (i) { return '<li>' + R.inline(i) + '</li>'; }).join('') +
          '</ul></div>';
      }).join('') + '</div>';
    }
    return '<div class="body">' + R.blocks(META[use] || []) + '</div>';
  }

  function secHead(no, t, sub) {
    return '<div class="sec-head">' +
      (no ? '<span class="sec-head__no">' + no + '</span>' : '') +
      '<h2 class="sec-head__t">' + esc(t) + '</h2>' +
      '<span class="sec-head__sub">' + esc(sub) + '</span></div>';
  }

  var HW_CLS = { '核心': 'chip-c--hwcore', '選配': 'chip-c--hwopt', '不需要': 'chip-c--sw' };
  var HW_TXT = { '核心': '樹莓派為核心', '選配': '含樹莓派（選配）', '不需要': '純軟體' };

  function cardHTML(p) {
    var hw = HW_CLS[p.pi.k] || 'chip-c--sw';
    return '<article class="chip-c ' + hw + '" data-go="' + p.id + '" data-dom="' + esc(p.domain) + '" data-hw="' + esc(p.pi.k) + '" role="link" tabindex="0" aria-label="' + esc(p.title) + '">' +
      '<div class="chip-c__top"><i class="chip-c__pin1"></i>' +
        '<span class="chip-c__hw">' + esc(HW_TXT[p.pi.k] || '純軟體') + '</span>' +
        '<span class="chip-c__code">' + esc(p.code) + '</span></div>' +
      '<div class="chip-c__rank">' + String(p.rank).padStart(2, '0') + '</div>' +
      '<div class="chip-c__hr"></div>' +
      '<h3 class="chip-c__t">' + esc(p.title) + '</h3>' +
      '<p class="chip-c__s">' + R.inline(p.summary) + '</p>' +
      '<div class="chip-c__meta">' +
        '<span class="tag tag--dom">' + esc(p.domain) + '</span>' + piTag(p) + fcTag(p) +
      '</div>' +
      '<div class="chip-c__score">' +
        '<div class="chip-c__bar"><i style="width:' + p.score + '%"></i></div>' +
        '<div class="chip-c__num">' + p.score + '<span>/100</span></div>' +
      '</div>' +
      '<div class="chip-c__votes" data-votes="' + p.id + '"></div></article>';
  }

  /* ============================================================
     詳細頁
     ============================================================ */
  function detailHTML(p, ver) {
    var h = '';
    var prev = PJ[p.rank - 2], next = PJ[p.rank];

    /* -- 標頭 -- */
    h += '<section class="wrap dt-head">';
    h += '<div class="dt-head__crumb"><a href="#/">MAIN</a><span>/</span>TOP 10<span>/</span>' +
         esc(p.code) + ' &nbsp;RANK ' + String(p.rank).padStart(2, '0') + '</div>';
    h += '<div class="progress">' + PJ.map(function (q) {
      return '<i class="' + (q.rank <= p.rank ? 'on' : '') + '"></i>';
    }).join('') + '</div>';
    h += '<div class="dt-head__top">';
    h += '<div class="dt-head__rank">' + String(p.rank).padStart(2, '0') + '<sup>SCORE ' + p.score + '</sup></div>';
    h += '<div class="dt-head__tt"><h1 class="dt-head__t">' + esc(p.title) + '</h1>' +
         '<p class="dt-head__sub">' + R.inline(p.subtitle) + '</p>' +
         '<div class="tagline" style="margin-top:10px">' +
           '<span class="tag tag--dom">' + esc(p.domain) + '</span>' + piTag(p) + fcTag(p) +
           p.tags.map(function (t) { return '<span class="tag">' + esc(t) + '</span>'; }).join('') +
         '</div>' +
         '<div class="dt-head__votes" data-detail-votes="' + p.id + '"></div></div>';
    h += '</div>';
    h += '<div class="kpi">' + p.kpi.map(function (k) {
      return '<div class="kpi__c"><div class="kpi__k">' + esc(k[0]) + '</div><div class="kpi__v">' + R.inline(k[1]) + '</div></div>';
    }).join('') + '</div>';
    h += '</section>';

    h += '<div class="wrap">';

    /* -- 評估面板 -- */
    h += evalPanel(p);

    /* -- 1 源起 / 2 前提摘要（兩版共用） -- */
    h += block('01', '源起', 'ORIGIN', p.origin);
    h += block('02', '前提摘要', 'PREMISE', p.premise);

    /* -- 版本切換 -- */
    h += '<div class="vswitch" id="vswitch">';
    h += '<div class="vswitch__lbl">VERSION</div>';
    h += '<button class="vswitch__b' + (ver === 'nofc' ? ' is-on' : '') + '" data-v="nofc">' +
         '<b>不使用 Function Calling</b><small>BASELINE / STATIC CONTEXT</small></button>';
    h += '<button class="vswitch__b' + (ver === 'fc' ? ' is-on' : '') + '" data-v="fc">' +
         '<b>使用 Function Calling</b><small>TOOL-AUGMENTED / LIVE LOOKUP</small></button>';
    h += '</div>';

    /* -- 版本切換就地說明（預設收合，第一次看的人才需要） -- */
    h += '<details class="fcx">';
    h += '<summary class="fcx__h"><span class="fcx__ic" aria-hidden="true"><i></i><i></i></span>' +
         '這兩個版本差在哪？什麼是 Function Calling</summary>';
    h += '<div class="fcx__b"><div class="body">' + R.blocks(META.fcPrimer || []) + '</div></div>';
    h += '</details>';

    /* -- 3/4/5（依版本切換） -- */
    h += '<div id="vbody">' + versionHTML(p, ver) + '</div>';

    /* -- 6 結語（共用 + 版本判定） -- */
    h += block('06', '結語', 'CONCLUSION', p.conclusion);

    /* -- 底部導覽 -- */
    h += '<div class="pager">';
    h += prev
      ? '<button class="pager__b" data-go="' + prev.id + '"><span class="pager__k">&#9666; PREV · ' + String(prev.rank).padStart(2, '0') + '</span><span class="pager__t">' + esc(prev.title) + '</span></button>'
      : '<button class="pager__b" disabled><span class="pager__k">&#9666; PREV</span><span class="pager__t">已是第一個專題</span></button>';
    h += '<button class="pager__b pager__b--home" data-go="home"><span class="pager__k">INDEX</span><span class="pager__t">返回主頁</span></button>';
    h += next
      ? '<button class="pager__b pager__b--next" data-go="' + next.id + '"><span class="pager__k">NEXT · ' + String(next.rank).padStart(2, '0') + ' &#9656;</span><span class="pager__t">' + esc(next.title) + '</span></button>'
      : '<button class="pager__b pager__b--next" disabled><span class="pager__k">NEXT &#9656;</span><span class="pager__t">已是最後一個專題</span></button>';
    h += '</div>';

    h += '</div>';
    return h;
  }

  function landClass(lv) {
    if (lv === '極低' || lv === '低') return 'ok';
    if (lv === '中') return 'mid';
    return 'hi';
  }

  function evalPanel(p) {
    var items = META.scoreItems || [];
    var rows = items.map(function (it, i) {
      var v = (p.scores && p.scores[i]) || 0, mx = it[1];
      var pct = Math.round(v / mx * 100);
      var lvl = pct >= 90 ? ' is-hi' : (pct >= 70 ? '' : ' is-lo');
      return '<div class="ev__row' + lvl + '" title="' + esc(it[2]) + '">' +
        '<div class="ev__lbl">' + R.inline(it[0]) + '</div>' +
        '<div class="ev__bar"><i style="width:' + pct + '%"></i></div>' +
        '<div class="ev__val">' + v + '<span>/' + mx + '</span></div>' +
      '</div>';
    }).join('');

    return '<section class="blk" id="blk-00" data-sec="評估明細"><div class="blk__h">' +
      '<span class="blk__n">00</span><h2 class="blk__t">評估明細</h2>' +
      '<span class="sec-head__sub">SCORING</span></div>' +
      '<div class="ev">' +
        '<div class="ev__grid">' + rows + '</div>' +
        '<div class="ev__side">' +
          '<div class="ev__card ev__card--total"><div class="ev__k">總分</div>' +
            '<div class="ev__v ev__v--big">' + p.score + '<span>/100</span></div>' +
            '<p class="ev__n">十題中排名第 ' + p.rank + '</p></div>' +
          '<div class="ev__card"><div class="ev__k">樹莓派角色</div>' +
            '<div class="ev__v">' + esc(p.pi.k) + '</div>' +
            '<p class="ev__n">' + R.inline(p.pi.note) + '</p></div>' +
          '<div class="ev__card"><div class="ev__k">Function Calling 價值</div>' +
            '<div class="ev__v">' + esc(p.fc.k) + '</div>' +
            '<p class="ev__n">' + R.inline(p.fc.note) + '</p></div>' +
        '</div>' +
      '</div>' +
      (p.landing ? '<div class="ev__extra">' +
        '<div class="ev__x ev__x--' + landClass(p.landing.lv) + '">' +
          '<div class="ev__k">實務落地障礙<b>' + esc(p.landing.lv) + '</b></div>' +
          '<p class="ev__n">' + R.inline(p.landing.x) + '</p></div>' +
        (p.future ? '<div class="ev__x ev__x--future">' +
          '<div class="ev__k">未來延展性<b>不計分</b></div>' +
          '<p class="ev__n">' + R.inline(p.future) + '</p></div>' : '') +
      '</div>' : '') +
      '</section>';
  }

  function versionHTML(p, ver) {
    var v = p.versions[ver];
    var badge = ver === 'fc'
      ? '<span class="tag tag--fc-must">WITH FUNCTION CALLING</span>'
      : '<span class="tag">WITHOUT FUNCTION CALLING</span>';
    return block('03', '專案說明及分析', 'ANALYSIS', v.analysis, badge) +
           block('04', '分工', 'WORK BREAKDOWN', v.division, badge) +
           block('05', '時間規劃安排', 'SCHEDULE', v.schedule, badge);
  }

  function block(no, title, en, body, badge) {
    return '<section class="blk" id="blk-' + no + '" data-sec="' + esc(title) + '"><div class="blk__h">' +
      '<span class="blk__n">' + no + '</span>' +
      '<h2 class="blk__t">' + esc(title) + '</h2>' +
      '<span class="sec-head__sub">' + esc(en) + '</span>' +
      (badge ? '<span class="blk__tag">' + badge + '</span>' : '') +
      '</div><div class="body">' + R.blocks(body) + '</div></section>';
  }

  /* ============================================================
     路由
     ============================================================ */
  function parse() {
    var raw = (location.hash || '#/').replace(/^#\/?/, '');
    var seg = raw.split('/').filter(Boolean);
    return { id: seg[0] || null, ver: (seg[1] === 'fc' ? 'fc' : 'nofc') };
  }

  var current = { id: null, ver: 'nofc' };

  function paint(keepScroll) {
    var r = parse();
    var p = r.id ? byId[r.id] : null;

    // 只有版本變動 → 局部更新，不重畫整頁、不重新載入
    if (p && current.id === r.id && current.ver !== r.ver) {
      current.ver = r.ver;
      document.getElementById('vbody').innerHTML = versionHTML(p, r.ver);
      Array.prototype.forEach.call(document.querySelectorAll('.vswitch__b'), function (b) {
        b.classList.toggle('is-on', b.dataset.v === r.ver);
      });
      mountFloating(p);
      return;
    }

    current = { id: r.id, ver: r.ver };
    root.innerHTML = p ? detailHTML(p, r.ver)
                   : (r.id === 'about' ? aboutHTML() : homeHTML());
    if (!keepScroll) window.scrollTo(0, 0);
    mountFloating(p);
  }

  /* 浮動章節導覽 + 選題投票（主頁與詳細頁都有） */
  function mountFloating(p) {
    if (!global.UI) return;
    global.UI.mountSectionNav();
    global.UI.mountVote(p ? { id: p.id, title: p.title } : { id: null, title: '' });
    paintVotes(global.UI.getPicks());
  }

  /* 把「誰選了這一題」標到卡片與詳細頁標頭 */
  function paintVotes(picks) {
    var byProj = {};
    (picks || []).forEach(function (v) { (byProj[v.project] = byProj[v.project] || []).push(v.member); });

    Array.prototype.forEach.call(document.querySelectorAll('[data-votes]'), function (n) {
      var who = byProj[n.dataset.votes];
      n.innerHTML = who ? who.map(function (m) {
        return '<span class="vtag">' + esc(m) + ' 選了這題</span>';
      }).join('') : '';
      var card = n.closest('.chip-c');
      if (card) card.classList.toggle('is-picked', !!who);
    });

    var board = document.getElementById('picks');
    if (board) {
      var members = (global.UI && global.UI.MEMBERS) || [];
      var done = (picks || []).length;
      board.innerHTML =
        '<div class="picks__hd"><span class="picks__t">大家選了什麼</span>' +
          '<span class="picks__n">' + done + ' / ' + members.length + ' 人已選</span></div>' +
        '<div class="picks__row">' + members.map(function (m) {
          var v = (picks || []).filter(function (x) { return x.member === m; })[0];
          var pj = v && byId[v.project];
          return '<div class="picks__c' + (v ? ' is-done' : '') + '">' +
            '<div class="picks__m">' + esc(m) + '</div>' +
            (pj
              ? '<button class="picks__p" data-go="' + pj.id + '">' +
                  '<b>' + String(pj.rank).padStart(2, '0') + '</b>' + esc(pj.title) + '</button>'
              : '<span class="picks__none">尚未選擇</span>') +
          '</div>';
        }).join('') + '</div>';
    }

    var hd = document.querySelector('[data-detail-votes]');
    if (hd) {
      var who2 = byProj[hd.dataset.detailVotes];
      hd.innerHTML = who2 ? who2.map(function (m) {
        return '<span class="vtag vtag--lg">' + esc(m) + ' 選了這題</span>';
      }).join('') : '';
    }
  }

  global.App = { onPicks: paintVotes };


  /* ---------- 事件委派 ---------- */
  document.addEventListener('click', function (e) {
    var v = e.target.closest ? e.target.closest('[data-v]') : null;
    if (v) {
      var r = parse();
      if (!r.id) return;
      // 用 replace 避免版本切換塞爆瀏覽器歷史
      location.replace('#/' + r.id + (v.dataset.v === 'fc' ? '/fc' : ''));
      return;
    }
    var g = e.target.closest ? e.target.closest('[data-go]') : null;
    if (g) {
      var to = g.dataset.go;
      location.hash = (to === 'home') ? '#/' : '#/' + to;
    }
  });

  document.addEventListener('keydown', function (e) {
    // 清單以鍵盤開啟
    if ((e.key === 'Enter' || e.key === ' ') && e.target.classList && e.target.classList.contains('chip-c')) {
      e.preventDefault();
      location.hash = '#/' + e.target.dataset.go;
      return;
    }
    // 詳細頁：左右鍵連續瀏覽
    var r = parse();
    if (!r.id || e.metaKey || e.ctrlKey || e.altKey) return;
    var p = byId[r.id]; if (!p) return;
    if (e.key === 'ArrowLeft' && PJ[p.rank - 2])  location.hash = '#/' + PJ[p.rank - 2].id;
    if (e.key === 'ArrowRight' && PJ[p.rank])     location.hash = '#/' + PJ[p.rank].id;
  });

  // 主頁領域篩選
  document.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('#filters button') : null;
    if (!b) return;
    Array.prototype.forEach.call(document.querySelectorAll('#filters button'), function (x) {
      x.classList.toggle('is-on', x === b);
    });
    var f = b.dataset.f;
    Array.prototype.forEach.call(document.querySelectorAll('#list .chip-c'), function (row) {
      row.style.display = (f === 'all' || row.dataset.dom === f) ? '' : 'none';
    });
  });

  document.addEventListener('click', function (e) {
    var t = e.target.closest ? e.target.closest('[data-acc]') : null;
    if (!t) return;
    var open = t.dataset.acc === 'open';
    Array.prototype.forEach.call(document.querySelectorAll('.acc'), function (d) { d.open = open; });
  });

  window.addEventListener('hashchange', function () { paint(false); });

  /* ---------- 啟動 ---------- */
  if (!PJ.length) {
    root.innerHTML = '<div class="wrap section"><div class="note note--risk"><div class="note__k">LOAD ERROR</div>' +
      '<p>專題內容尚未載入完成，請重新整理頁面。</p></div></div>';
  } else {
    paint(false);
  }
})(window);