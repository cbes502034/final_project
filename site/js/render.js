/* ============================================================
   render.js — 內容區塊 → HTML
   支援區塊：p / h / ul / ol / table / note / fig / pre / gantt / kv
   行內語法：**粗體**  `程式碼`  [S12] 引註  {{連結文字|url}}
   ============================================================ */
(function (global) {
  'use strict';

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  // 行內語法解析（先跳脫，再還原受支援的標記）
  function inline(s) {
    return esc(s)
      .replace(/\{\{([^|}]+)\|([^}]+)\}\}/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\[(S\d{1,2}(?:\]\[S\d{1,2})*)\]/g, function (m, inner) {
        return inner.split('][').map(function (id) {
          return '<span class="cite">' + id + '</span>';
        }).join('');
      });
  }

  var B = {};

  B.p = function (b) { return '<p>' + inline(b.x) + '</p>'; };

  B.h = function (b) { return '<h4>' + inline(b.x) + '</h4>'; };

  B.ul = function (b) {
    return '<ul>' + b.x.map(function (i) { return '<li>' + inline(i) + '</li>'; }).join('') + '</ul>';
  };

  B.ol = function (b) {
    return '<ol>' + b.x.map(function (i) { return '<li>' + inline(i) + '</li>'; }).join('') + '</ol>';
  };

  B.table = function (b) {
    var h = '<div class="tw"><table><thead><tr>' +
      b.head.map(function (c) { return '<th>' + inline(c) + '</th>'; }).join('') +
      '</tr></thead><tbody>';
    h += b.rows.map(function (r) {
      return '<tr>' + r.map(function (c) { return '<td>' + inline(c) + '</td>'; }).join('') + '</tr>';
    }).join('');
    return h + '</tbody></table></div>';
  };

  B.note = function (b) {
    var kind = b.kind ? ' note--' + b.kind : '';
    var body = Array.isArray(b.x)
      ? b.x.map(function (p) { return '<p>' + inline(p) + '</p>'; }).join('')
      : '<p>' + inline(b.x) + '</p>';
    return '<div class="note' + kind + '"><div class="note__k">' + esc(b.k || 'NOTE') + '</div>' + body + '</div>';
  };

  B.pre = function (b) {
    return '<div class="pre"><code>' + esc(b.x) + '</code></div>';
  };

  B.kv = function (b) {
    return '<div class="kpi">' + b.x.map(function (r) {
      return '<div class="kpi__c"><div class="kpi__k">' + esc(r[0]) + '</div><div class="kpi__v">' + inline(r[1]) + '</div></div>';
    }).join('') + '</div>';
  };

  B.fig = function (b) {
    var svg = '';
    try {
      svg = (b.type === 'FLOW') ? global.Diagram.flow(b.spec) : global.Diagram.arch(b.spec);
    } catch (e) {
      svg = '<div class="lbl">DIAGRAM RENDER ERROR</div>';
    }
    return '<figure class="fig">' +
      '<div class="fig__bar"><span class="fig__id">' + esc(b.id) + '</span>' +
      '<span class="fig__t">' + esc(b.title) + '</span>' +
      '<span class="fig__type">' + esc(b.type === 'FLOW' ? 'FLOWCHART' : 'BLOCK DIAGRAM') + '</span></div>' +
      '<div class="fig__body">' + svg + '</div>' +
      (b.cap ? '<figcaption class="fig__cap">' + inline(b.cap) + '</figcaption>' : '') +
      '</figure>';
  };

  B.gantt = function (b) {
    var h = '<div class="gantt"><table><thead><tr><th>' + esc(b.axis || '工作項目 / 負責人') + '</th>';
    b.weeks.forEach(function (w) {
      var parts = String(w).split('/');
      h += '<th><span class="g-wk">' + esc(parts[0]) + '</span>' +
           (parts[1] ? '<span class="g-half">' + esc(parts[1]) + '</span>' : '') + '</th>';
    });
    h += '</tr></thead><tbody>';
    b.rows.forEach(function (r) {
      h += '<tr><td>' + inline(r.name) + '<span class="g-owner">' + esc(r.owner) + '</span></td>';
      r.cells.forEach(function (c) {
        var cls = 'g-cell' + (c ? ' on' : '') + (c === 2 ? ' milestone' : '');
        h += '<td><div class="' + cls + '" style="height:100%"></div></td>';
      });
      h += '</tr>';
    });
    h += '</tbody></table></div>';
    h += '<div class="g-legend">' +
         '<span><i class="g-k g-k--on"></i>進行中</span>' +
         '<span><i class="g-k g-k--ms"></i>里程碑（此時要驗收）</span>' +
         '<span class="g-legend__note">每格代表半週，約 3–4 天</span>' +
         '</div>';
    return h;
  };

  function blocks(list) {
    if (!list || !list.length) return '';
    return list.map(function (b) {
      var fn = B[b.t];
      return fn ? fn(b) : '';
    }).join('');
  }

  global.Render = { blocks: blocks, inline: inline, esc: esc };
})(window);
