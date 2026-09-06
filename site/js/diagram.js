/* ============================================================
   diagram.js — 半導體 / PCB 風格 SVG 圖表引擎
   ------------------------------------------------------------
   設計約束（依 research/00-design-spec.md 第 8 條）：
   - 模組 = IC 封裝（本體 + 接腳 + pin-1 標記）
   - 連線 = PCB 走線，只走水平 / 垂直 / 45 度，禁止任何貝茲曲線
   - 端點 = 焊墊 / via（方形，不用圓點）
   - 箭頭 = 實心直角三角形
   - 分區 = die 區塊（虛線細框 + 角落標記）
   ============================================================ */
(function (global) {
  'use strict';

  var esc = function (s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  };

  /* ---------- 幾何預設 ---------- */
  var G = {
    padX: 16, padY: 20,
    colW: 168, rowH: 66,
    gapX: 54, gapY: 48,
    pinLen: 7, pinCount: 3, padSize: 5
  };

  function geom(o) {
    var g = {};
    for (var k in G) g[k] = (o && o[k] != null) ? o[k] : G[k];
    return g;
  }

  function nodeBox(n, g) {
    var span = n.span || 1;
    var rspan = n.rspan || 1;
    return {
      x: g.padX + n.c * (g.colW + g.gapX),
      y: g.padY + n.r * (g.rowH + g.gapY),
      w: span * g.colW + (span - 1) * g.gapX,
      h: rspan * g.rowH + (rspan - 1) * g.gapY
    };
  }

  /* ---------- 基本圖元 ---------- */

  // 焊墊：小方塊
  function pad(x, y, hot, s) {
    s = s || G.padSize;
    return '<rect class="' + (hot ? 'dgm-pad-hot' : 'dgm-pad') + '" x="' +
      (x - s / 2) + '" y="' + (y - s / 2) + '" width="' + s + '" height="' + s + '"/>';
  }

  // 實心直角三角箭頭；dir: r / l / d / u
  function arrow(x, y, dir, hot) {
    var k = 5, p;
    if (dir === 'r')      p = [x, y - k, x + k + 1, y, x, y + k];
    else if (dir === 'l') p = [x, y - k, x - k - 1, y, x, y + k];
    else if (dir === 'd') p = [x - k, y, x, y + k + 1, x + k, y];
    else                  p = [x - k, y, x, y - k - 1, x + k, y];
    return '<polygon class="' + (hot ? 'dgm-arrow-hot' : 'dgm-arrow') +
      '" points="' + p[0] + ',' + p[1] + ' ' + p[2] + ',' + p[3] + ' ' + p[4] + ',' + p[5] + '"/>';
  }

  // 折線走線（只允許直角轉折）
  function trace(pts, hot) {
    var d = pts.map(function (p, i) { return (i ? 'L' : 'M') + p[0] + ' ' + p[1]; }).join(' ');
    return '<path class="' + (hot ? 'dgm-trace-hot' : 'dgm-trace') + '" d="' + d + '"/>';
  }

  // 走線上的文字標籤（帶底色遮罩，避免壓線）
  function traceLabel(x, y, text, hot) {
    if (!text) return '';
    var w = String(text).length * 5.6 + 8;
    return '<g><rect x="' + (x - w / 2) + '" y="' + (y - 8) + '" width="' + w + '" height="13" fill="#0A0D0F"/>' +
      '<text class="dgm-t-sm" x="' + x + '" y="' + (y + 1.5) + '" text-anchor="middle"' +
      (hot ? ' fill="#0ABAB5"' : '') + '>' + esc(text) + '</text></g>';
  }

  /* ---------- IC 封裝 ---------- */
  function chip(n, g) {
    var b = nodeBox(n, g);
    var hot = n.tone === 'hot';
    var cls = hot ? 'dgm-pkg-hot' : 'dgm-pkg';
    var pinCls = hot ? 'dgm-pin-hot' : 'dgm-pin';
    var s = '<g class="dgm-node">';

    // 接腳（左右各 pinCount 支）
    var pc = n.pins == null ? g.pinCount : n.pins;
    if (pc > 0) {
      for (var i = 0; i < pc; i++) {
        var py = b.y + b.h * (i + 1) / (pc + 1);
        s += '<line class="' + pinCls + '" x1="' + (b.x - g.pinLen) + '" y1="' + py + '" x2="' + b.x + '" y2="' + py + '"/>';
        s += '<line class="' + pinCls + '" x1="' + (b.x + b.w) + '" y1="' + py + '" x2="' + (b.x + b.w + g.pinLen) + '" y2="' + py + '"/>';
      }
    }

    // 本體
    s += '<rect class="' + cls + '" x="' + b.x + '" y="' + b.y + '" width="' + b.w + '" height="' + b.h + '"/>';

    // pin-1 標記（左上角小方塊）
    s += '<rect x="' + (b.x + 5) + '" y="' + (b.y + 5) + '" width="4" height="4" fill="' +
      (hot ? '#0ABAB5' : '#3D4B4F') + '"/>';

    // 右上角缺角標記（die corner）
    s += '<path class="' + pinCls + '" d="M' + (b.x + b.w - 11) + ' ' + b.y + ' L' + (b.x + b.w) + ' ' + (b.y + 11) + '"/>';

    // 文字
    var cx = b.x + b.w / 2;
    var hasCjk = !!n.cjk;
    var ty = hasCjk ? b.y + b.h / 2 - 4 : b.y + b.h / 2 + 4;
    s += '<text class="' + (hot ? 'dgm-t-hot' : 'dgm-t') + '" x="' + cx + '" y="' + ty + '" text-anchor="middle">' + esc(n.name) + '</text>';
    if (hasCjk) {
      s += '<text class="dgm-t-cjk" x="' + cx + '" y="' + (b.y + b.h / 2 + 12) + '" text-anchor="middle">' + esc(n.cjk) + '</text>';
    }
    if (n.tag) {
      s += '<text class="dgm-t-sm" x="' + (b.x + b.w - 7) + '" y="' + (b.y + b.h - 6) + '" text-anchor="end">' + esc(n.tag) + '</text>';
    }
    if (n.ref) {
      s += '<text class="dgm-t-sm" x="' + (b.x + 7) + '" y="' + (b.y + b.h - 6) + '">' + esc(n.ref) + '</text>';
    }
    s += '</g>';
    return s;
  }

  /* ---------- 分區（die zone） ---------- */
  function zone(z, g) {
    var x = g.padX + z.c * (g.colW + g.gapX) - 16;
    var y = g.padY + z.r * (g.rowH + g.gapY) - 26;
    var w = z.span * g.colW + (z.span - 1) * g.gapX + 32;
    var h = z.rspan * g.rowH + (z.rspan - 1) * g.gapY + 42;
    var s = '<g><rect class="dgm-zone" x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '"/>';
    // 四角刻度
    [[x, y, 1, 1], [x + w, y, -1, 1], [x, y + h, 1, -1], [x + w, y + h, -1, -1]].forEach(function (c) {
      s += '<path class="dgm-grid" d="M' + c[0] + ' ' + (c[1] + 9 * c[3]) + ' L' + c[0] + ' ' + c[1] +
        ' L' + (c[0] + 9 * c[2]) + ' ' + c[1] + '" stroke="#2A383D" fill="none"/>';
    });
    s += '<text class="dgm-zone-lbl" x="' + (x + 8) + '" y="' + (y + 13) + '">' + esc(z.label) + '</text></g>';
    return s;
  }

  /* ---------- 走線路由 ---------- */
  function route(a, b, g, opt) {
    opt = opt || {};
    var A = nodeBox(a, g), B = nodeBox(b, g);
    var ax, ay, bx, by, pts, adir, bdir, mid;

    // 同列 → 水平直線
    if (a.r === b.r) {
      if (B.x > A.x) {
        ax = A.x + A.w + g.pinLen; ay = A.y + A.h / 2;
        bx = B.x - g.pinLen;       by = B.y + B.h / 2;
        pts = [[ax, ay], [bx, by]]; bdir = 'r';
      } else {
        ax = A.x - g.pinLen; ay = A.y + A.h / 2;
        bx = B.x + B.w + g.pinLen; by = B.y + B.h / 2;
        pts = [[ax, ay], [bx, by]]; bdir = 'l';
      }
      mid = [(ax + bx) / 2, ay];
    }
    // 同欄 → 垂直直線
    else if (a.c === b.c && (a.span || 1) === (b.span || 1)) {
      if (B.y > A.y) {
        ax = A.x + A.w / 2; ay = A.y + A.h;
        bx = B.x + B.w / 2; by = B.y;
        pts = [[ax, ay], [bx, by]]; bdir = 'd';
      } else {
        ax = A.x + A.w / 2; ay = A.y;
        bx = B.x + B.w / 2; by = B.y + B.h;
        pts = [[ax, ay], [bx, by]]; bdir = 'u';
      }
      mid = [ax, (ay + by) / 2];
    }
    // 繞行（回授線）：出下方 → 走 lane → 回上方
    else if (opt.route === 'around') {
      var lane = Math.max(A.y + A.h, B.y + B.h) + g.gapY * 0.55;
      ax = A.x + A.w / 2; ay = A.y + A.h;
      bx = B.x + B.w / 2; by = B.y + B.h;
      pts = [[ax, ay], [ax, lane], [bx, lane], [bx, by]];
      bdir = 'u'; mid = [(ax + bx) / 2, lane];
    }
    // 跨列跨欄 → Z 形（水平先出，垂直轉折，水平進入）
    else {
      var toRight = B.x > A.x;
      ax = toRight ? A.x + A.w + g.pinLen : A.x - g.pinLen;
      ay = A.y + A.h / 2;
      bx = toRight ? B.x - g.pinLen : B.x + B.w + g.pinLen;
      by = B.y + B.h / 2;
      var mx = (ax + bx) / 2;
      pts = [[ax, ay], [mx, ay], [mx, by], [bx, by]];
      bdir = toRight ? 'r' : 'l';
      mid = [mx, (ay + by) / 2];
    }

    var hot = !!opt.hot;
    var s = trace(pts, hot);
    s += pad(pts[0][0], pts[0][1], hot);
    var last = pts[pts.length - 1];
    if (bdir === 'r')      s += arrow(last[0] - 1, last[1], 'r', hot);
    else if (bdir === 'l') s += arrow(last[0] + 1, last[1], 'l', hot);
    else if (bdir === 'd') s += arrow(last[0], last[1] - 1, 'd', hot);
    else                   s += arrow(last[0], last[1] + 1, 'u', hot);
    if (opt.label) s += traceLabel(mid[0], mid[1], opt.label, hot);
    return s;
  }

  /* ---------- 背景細網格 ---------- */
  function bgGrid(w, h) {
    var s = '<g opacity=".45">';
    for (var x = 0; x <= w; x += 24) s += '<line class="dgm-grid" x1="' + x + '" y1="0" x2="' + x + '" y2="' + h + '"/>';
    for (var y = 0; y <= h; y += 24) s += '<line class="dgm-grid" x1="0" y1="' + y + '" x2="' + w + '" y2="' + y + '"/>';
    return s + '</g>';
  }

  /* ============================================================
     架構圖
     spec = { cols, rows, zones:[{c,r,span,rspan,label}],
              nodes:[{id,c,r,span,rspan,name,cjk,tag,ref,tone,pins}],
              edges:[{a,b,label,hot,route}] }
     ============================================================ */
  function arch(spec) {
    var g = geom(spec);
    var w = g.padX * 2 + spec.cols * g.colW + (spec.cols - 1) * g.gapX;
    var h = g.padY * 2 + spec.rows * g.rowH + (spec.rows - 1) * g.gapY;
    var idx = {};
    spec.nodes.forEach(function (n) { idx[n.id] = n; });

    var s = '<svg viewBox="0 0 ' + w + ' ' + h + '" width="' + w + '" preserveAspectRatio="xMidYMid meet" role="img">';
    s += bgGrid(w, h);
    (spec.zones || []).forEach(function (z) { s += zone(z, g); });
    (spec.edges || []).forEach(function (e) {
      if (!idx[e.a] || !idx[e.b]) return;
      s += route(idx[e.a], idx[e.b], g, e);
    });
    spec.nodes.forEach(function (n) { s += chip(n, g); });
    s += '</svg>';
    return s;
  }

  /* ============================================================
     流程圖（同樣走 PCB 語彙；判斷節點用斜切八角，非菱形圓角）
     spec = { cols, rows, nodes:[{id,c,r,span,kind,name,cjk,tag}],
              edges:[{a,b,label,hot,route}] }
     kind: step | decision | io | term | llm
     ============================================================ */
  function shape(n, g) {
    var b = nodeBox(n, g);
    var hot = n.tone === 'hot' || n.kind === 'llm';
    var stroke = hot ? '#0ABAB5' : '#2A383D';
    var fill = hot ? '#0E1A1C' : '#121A1E';
    var s = '<g class="dgm-node">';
    var k = n.kind || 'step';

    if (k === 'decision') {
      // 斜切八角（四角 45 度切）
      var c = 13;
      s += '<polygon class="dgm-pkg" fill="' + fill + '" stroke="' + stroke + '" points="' +
        [[b.x + c, b.y], [b.x + b.w - c, b.y], [b.x + b.w, b.y + c], [b.x + b.w, b.y + b.h - c],
         [b.x + b.w - c, b.y + b.h], [b.x + c, b.y + b.h], [b.x, b.y + b.h - c], [b.x, b.y + c]]
          .map(function (p) { return p[0] + ',' + p[1]; }).join(' ') + '"/>';
    } else if (k === 'io') {
      // 平行四邊形（輸入 / 輸出）
      var sk = 14;
      s += '<polygon class="dgm-pkg" fill="' + fill + '" stroke="' + stroke + '" points="' +
        [[b.x + sk, b.y], [b.x + b.w, b.y], [b.x + b.w - sk, b.y + b.h], [b.x, b.y + b.h]]
          .map(function (p) { return p[0] + ',' + p[1]; }).join(' ') + '"/>';
    } else if (k === 'term') {
      // 端點：雙框
      s += '<rect class="dgm-pkg" fill="' + fill + '" stroke="' + stroke + '" x="' + b.x + '" y="' + b.y + '" width="' + b.w + '" height="' + b.h + '"/>';
      s += '<rect fill="none" stroke="' + stroke + '" stroke-width=".8" opacity=".55" x="' + (b.x + 4) + '" y="' + (b.y + 4) + '" width="' + (b.w - 8) + '" height="' + (b.h - 8) + '"/>';
    } else {
      // 一般步驟 / LLM：IC 封裝
      var pc = n.pins == null ? 2 : n.pins;
      for (var i = 0; i < pc; i++) {
        var py = b.y + b.h * (i + 1) / (pc + 1);
        s += '<line stroke="' + stroke + '" x1="' + (b.x - 6) + '" y1="' + py + '" x2="' + b.x + '" y2="' + py + '"/>';
        s += '<line stroke="' + stroke + '" x1="' + (b.x + b.w) + '" y1="' + py + '" x2="' + (b.x + b.w + 6) + '" y2="' + py + '"/>';
      }
      s += '<rect class="dgm-pkg" fill="' + fill + '" stroke="' + stroke + '" x="' + b.x + '" y="' + b.y + '" width="' + b.w + '" height="' + b.h + '"/>';
      s += '<rect x="' + (b.x + 5) + '" y="' + (b.y + 5) + '" width="4" height="4" fill="' + (hot ? '#0ABAB5' : '#3D4B4F') + '"/>';
    }

    var cx = b.x + b.w / 2;
    var ty = n.cjk ? b.y + b.h / 2 - 4 : b.y + b.h / 2 + 4;
    s += '<text class="' + (hot ? 'dgm-t-hot' : 'dgm-t') + '" x="' + cx + '" y="' + ty + '" text-anchor="middle">' + esc(n.name) + '</text>';
    if (n.cjk) s += '<text class="dgm-t-cjk" x="' + cx + '" y="' + (b.y + b.h / 2 + 12) + '" text-anchor="middle">' + esc(n.cjk) + '</text>';
    if (n.tag) s += '<text class="dgm-t-sm" x="' + (b.x + b.w - 7) + '" y="' + (b.y + b.h - 6) + '" text-anchor="end">' + esc(n.tag) + '</text>';
    s += '</g>';
    return s;
  }

  function flow(spec) {
    var g = geom({ colW: spec.colW || 158, rowH: spec.rowH || 58, gapX: spec.gapX || 44, gapY: spec.gapY || 40 });
    var w = g.padX * 2 + spec.cols * g.colW + (spec.cols - 1) * g.gapX;
    var h = g.padY * 2 + spec.rows * g.rowH + (spec.rows - 1) * g.gapY;
    var idx = {};
    spec.nodes.forEach(function (n) { idx[n.id] = n; });

    var s = '<svg viewBox="0 0 ' + w + ' ' + h + '" width="' + w + '" preserveAspectRatio="xMidYMid meet" role="img">';
    s += bgGrid(w, h);
    (spec.zones || []).forEach(function (z) { s += zone(z, g); });
    (spec.edges || []).forEach(function (e) {
      if (!idx[e.a] || !idx[e.b]) return;
      s += route(idx[e.a], idx[e.b], g, e);
    });
    spec.nodes.forEach(function (n) { s += shape(n, g); });
    s += '</svg>';
    return s;
  }

  /* ---------- 頁面背景的電路走線裝飾 ---------- */
  function circuitry() {
    var W = 1600, H = 900, s = '', i, x, y;
    var rnd = (function (seed) {
      return function () { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
    })(20260906);
    for (i = 0; i < 26; i++) {
      x = Math.round(rnd() * W / 20) * 20;
      y = Math.round(rnd() * H / 20) * 20;
      var len1 = (2 + Math.floor(rnd() * 7)) * 20;
      var len2 = (2 + Math.floor(rnd() * 6)) * 20;
      var dir = rnd() > .5 ? 1 : -1;
      s += '<path d="M' + x + ' ' + y + ' L' + (x + len1) + ' ' + y +
           ' L' + (x + len1 + len2 * dir * .5) + ' ' + (y + len2 * dir) +
           ' L' + (x + len1 + len2 * dir * .5 + 40) + ' ' + (y + len2 * dir) + '"/>';
      s += '<rect x="' + (x - 2.5) + '" y="' + (y - 2.5) + '" width="5" height="5" fill="none"/>';
    }
    return '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid slice" width="100%" height="100%">' +
      '<g stroke="rgba(10,186,181,.10)" stroke-width="1" fill="none">' + s + '</g></svg>';
  }

  global.Diagram = { arch: arch, flow: flow, circuitry: circuitry };
})(window);
