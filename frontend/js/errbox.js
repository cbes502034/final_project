/* ============================================================
   errbox.js — 左下角那張表：這一頁打過的每一支後端，現在是綠燈還是紅燈

   ★ 這個檔案做的事
   ------------------------------------------------------------
   api.js 每打完一支就往這裡丟一筆結果。一個前端函式一列，只留最新的那一次：

       ✓  API.transactions   GET /api/transactions   成員2        ← 回了，形狀也對
       ✗  API.summary        GET /api/summary   501  成員3        ← 還沒做／出錯
          後端還沒做這一支（HTTP 501）

   組員做完一支、重新整理頁面，就會看到自己那一支從紅變綠。
   全部都是綠的時候收成一顆小膠囊不擋畫面；一出現紅的就自動展開。

   ★ 綠燈的意思
   ------------------------------------------------------------
   **後端回了，而且回應的形狀通過前端的檢查**（api.js 的 SHAPE 與 ROWS）。
   也就是「照說明字串做對了，前端就一定接得住」——畫面會有反應。

   ★ 什麼不會進來
   ------------------------------------------------------------
   · 業務錯誤（400／401／403／409／422）：那是後端**正確地**拒絕這次操作
   · mock 模式：前端自己演的，沒有後端可以亮燈
   · 模型叫不動時前端頂出來的備援結果：那不是後端做出來的

   ★ 為什麼不用 window.alert
   ------------------------------------------------------------
   · 通知每 20 秒輪詢一次：那一支沒做的話，每 20 秒彈一次，頁面沒辦法用
   · 總覽一次打好幾支：一口氣疊好幾個對話框，要按好幾次才看得到畫面
   · 瀏覽器會長出「不要再顯示此對話框」，勾下去整個分頁再也不彈
   · alert 的字沒辦法複製，手機上整個畫面被鎖住
   ============================================================ */
(function (global) {
  'use strict';

  var MAX = 60;                 // 一頁最多會打到的函式數量遠小於這個
  var state = { rows: {}, order: [], open: false, dismissed: false };

  function esc(s) {
    return String(s === null || s === undefined ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function hhmm(d) {
    return ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2) +
      ':' + ('0' + d.getSeconds()).slice(-2);
  }

  /* 訊息後面那一段「｜出錯的函式：…」在每一列的標題已經寫過了，這裡不重複 */
  function short(msg) {
    return String(msg || '').split('｜出錯的函式：')[0];
  }

  function list() {
    return state.order.map(function (k) { return state.rows[k]; });
  }

  function bad() {
    return list().filter(function (r) { return r.kind !== 'ok'; });
  }

  /* api.js 呼叫這一支。同一個函式只留最新的結果——紅了又綠，就是修好了。 */
  function push(rec) {
    if (!rec || !rec.fn) return;
    var prev = state.rows[rec.fn];
    var wasBad = prev && prev.kind !== 'ok';
    var nowBad = rec.kind !== 'ok';
    var same = prev && prev.kind === rec.kind && short(prev.message) === short(rec.message);

    state.rows[rec.fn] = {
      fn: rec.fn, route: rec.route, owner: rec.owner, kind: rec.kind,
      status: rec.status, message: rec.message, detail: rec.detail, at: new Date(),
      n: same ? prev.n + 1 : 1
    };
    if (!prev) {
      state.order.unshift(rec.fn);
      if (state.order.length > MAX) delete state.rows[state.order.pop()];
    }
    /* 新冒出一支紅的（或原本綠的變紅）才自動展開。
       同一支重複失敗（例如鈴鐺每 20 秒輪詢一次）不會一直把它彈回來。 */
    if (nowBad && (!prev || !wasBad)) {
      state.dismissed = false;
      state.open = true;
    }
    render();
  }

  function clear() {
    state.rows = {};
    state.order = [];
    state.dismissed = false;
    state.open = false;
    render();
  }

  /* 貼到群組裡問人用的純文字 */
  function text() {
    return list().map(function (r) {
      var head = [r.kind === 'ok' ? 'OK' : 'NG', hhmm(r.at), r.fn, r.route || '',
        r.status || '', r.owner || '', r.n > 1 ? '×' + r.n : ''].filter(Boolean).join('　');
      if (r.kind === 'ok') return head;
      return head + '\n    ' + short(r.message) +
        (r.detail && r.detail !== short(r.message) ? '\n    後端原話：' + r.detail : '');
    }).join('\n');
  }

  var KIND_TW = { ok: '正常', backend: '後端', network: '連不上', shape: '形狀' };

  function row(r) {
    var ok = r.kind === 'ok';
    var det = !ok && r.detail && r.detail !== short(r.message);
    return '<li class="eb__i' + (ok ? ' eb__i--ok' : '') + '">' +
      '<div class="eb__top">' +
        '<span class="eb__lamp" aria-label="' + (ok ? '正常' : '有問題') + '">' + (ok ? '✓' : '✗') + '</span>' +
        '<code class="eb__fn">' + esc(r.fn) + '</code>' +
        (r.route ? '<code class="eb__rt">' + esc(r.route) + '</code>' : '') +
        (r.status ? '<span class="eb__st">' + esc(r.status) + '</span>' : '') +
        '<span class="eb__kd">' + esc(KIND_TW[r.kind] || r.kind) + '</span>' +
        (r.owner ? '<span class="eb__ow">' + esc(r.owner) + '</span>' : '') +
        (r.n > 1 ? '<span class="eb__n">×' + r.n + '</span>' : '') +
        '<span class="eb__at">' + hhmm(r.at) + '</span>' +
      '</div>' +
      (ok ? '' : '<div class="eb__msg">' + esc(short(r.message)) + '</div>') +
      (det ? '<div class="eb__raw">後端原話：' + esc(r.detail) + '</div>' : '') +
      '</li>';
  }

  /* 手機上這張表是整排的，會蓋住右下角的浮出訊息。
     把「浮出訊息至少要離底部多遠」算出來交給 CSS（見 app.css 的 --eb-clear）。 */
  function measure(box) {
    var css = document.documentElement.style;
    if (!box || box.hidden) { css.removeProperty('--eb-clear'); return; }
    var top = box.getBoundingClientRect().top;
    css.setProperty('--eb-clear', Math.max(0, Math.round(window.innerHeight - top + 8)) + 'px');
  }

  function render() {
    var box = document.getElementById('errbox');
    if (!box) return;
    var rows = list();
    if (!rows.length) { box.hidden = true; box.innerHTML = ''; measure(box); return; }
    box.hidden = false;

    var nBad = bad().length, nOk = rows.length - nBad;
    var allOk = nBad === 0;
    var tally = '<b class="eb__ok">✓ ' + nOk + '</b>' + (nBad ? '　<b class="eb__ng">✗ ' + nBad + '</b>' : '');

    // 全綠的時候預設收起來；有紅的時候看使用者有沒有按「收起」
    if (state.dismissed || !state.open) {
      box.className = 'eb eb--min' + (allOk ? ' eb--allok' : '');
      box.innerHTML = '<button type="button" class="eb__pill" id="ebOpen">' +
        (allOk ? '後端全部正常　' : '後端　') + tally + '</button>';
      measure(box);
      return;
    }

    // 紅的排前面，綠的排後面；同一種依時間新的在前
    var sorted = bad().concat(rows.filter(function (r) { return r.kind === 'ok'; }));
    box.className = 'eb' + (allOk ? ' eb--allok' : '');
    box.innerHTML =
      '<div class="eb__h">' +
        '<span class="eb__t">' + (allOk ? '後端全部正常　' : '後端　') + tally + '</span>' +
        '<button type="button" class="eb__b" id="ebCopy">複製全部</button>' +
        '<button type="button" class="eb__b" id="ebClear">清空</button>' +
        '<button type="button" class="eb__x" id="ebMin" aria-label="收起來">收起</button>' +
      '</div>' +
      '<ul class="eb__l">' + sorted.map(row).join('') + '</ul>' +
      '<div class="eb__f">綠燈＝後端回了、形狀也對，前端接得住。業務錯誤（403、409、422…）不列，那是後端正確地拒絕。</div>';
    measure(box);
  }

  document.addEventListener('click', function (e) {
    var t = e.target;
    if (!t || !t.closest) return;
    if (t.closest('#ebOpen')) { state.dismissed = false; state.open = true; render(); return; }
    if (t.closest('#ebMin')) { state.dismissed = true; state.open = false; render(); return; }
    if (t.closest('#ebClear')) { clear(); return; }
    if (t.closest('#ebCopy')) {
      var txt = text();
      var done = function () { if (global.toast) global.toast('已複製 ' + state.order.length + ' 支', 'ok'); };
      if (global.navigator && navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(txt).then(done, function () { fallbackCopy(txt, done); });
      } else fallbackCopy(txt, done);
    }
  });

  /* 沒有 clipboard API（http 的非 localhost 網址就沒有）時的退路 */
  function fallbackCopy(txt, done) {
    var ta = document.createElement('textarea');
    ta.value = txt;
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); done(); } catch (err) {}
    document.body.removeChild(ta);
  }

  global.ErrBox = {
    push: push, clear: clear, text: text, render: render,
    items: function () { return bad(); },          // 只回紅的（舊的呼叫端都是拿它判斷「有沒有錯」）
    all: function () { return list(); }             // 綠的紅的都要
  };
})(window);
