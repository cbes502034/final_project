/* ============================================================
   errbox.js — 錯誤匣：這一輪操作裡，後端沒給出正確結果的每一支

   ★ 這個檔案做的事
   ------------------------------------------------------------
   api.js 每次拿到「不是正確結果」的回應，就往這裡丟一筆。
   畫面左下角固定一塊紅色面板（右下角讓給浮出訊息），一支一列：

       API.summary   GET /api/summary   501   成員3        ×3
       後端還沒做這一支：GET /api/summary（成員3）

   要按才關、可以整個複製，方便貼到群組裡問「這是你的嗎」。

   ★ 什麼會進來、什麼不會
   ------------------------------------------------------------
   進來的是 api.js 的三種：backend（還沒做／出錯）、network（連不上）、
   shape（回應形狀不對）。

   **業務錯誤（400／401／403／409／422）不進來** —— 那是後端**正確**地
   回答「你不能這樣做」，畫面上照它的原話講就好，不是誰寫壞了。

   ★ 為什麼不用 window.alert
   ------------------------------------------------------------
   · 通知每 20 秒輪詢一次：那一支沒做的話，每 20 秒彈一次，頁面沒辦法用
   · 總覽一次打好幾支：一口氣疊好幾個對話框，要按好幾次才看得到畫面
   · 瀏覽器會長出「不要再顯示此對話框」，勾下去整個分頁再也不彈 ——
     最該看到的時候看不到
   · alert 的字沒辦法複製，手機上整個畫面被鎖住
   ============================================================ */
(function (global) {
  'use strict';

  var MAX = 30;                 // 只留最近 30 支，再多就把最舊的擠掉
  var state = { items: [], open: true, dismissed: false };

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

  /* api.js 呼叫這一支。同一支重複失敗（例如鈴鐺每 20 秒輪詢一次）只累加次數，不新增一列。 */
  function push(rec) {
    if (!rec || !rec.fn) return;
    var key = rec.fn + '|' + (rec.status || 0) + '|' + short(rec.message);
    var hit = state.items.filter(function (x) { return x.key === key; })[0];
    if (hit) {
      hit.n++;
      hit.at = new Date();
    } else {
      state.items.unshift({ key: key, n: 1, at: new Date(), fn: rec.fn, route: rec.route,
        owner: rec.owner, kind: rec.kind, status: rec.status, message: rec.message, detail: rec.detail });
      state.items = state.items.slice(0, MAX);
      /* 收起來之後又出現**新的**一支，再打開一次 —— 使用者收的是「已經看過的那些」。
         同一支重複失敗不會把它重新打開，不然鈴鐺的輪詢會一直彈回來。 */
      state.dismissed = false;
      state.open = true;
    }
    render();
  }

  function clear() {
    state.items = [];
    state.dismissed = false;
    render();
  }

  /* 貼到群組裡問人用的純文字 */
  function text() {
    return state.items.map(function (it) {
      return [hhmm(it.at), it.fn, it.route || '', it.status || '', it.owner || '',
        it.n > 1 ? '×' + it.n : ''].filter(Boolean).join('　') +
        '\n    ' + short(it.message) + (it.detail && it.detail !== short(it.message) ? '\n    後端原話：' + it.detail : '');
    }).join('\n');
  }

  var KIND_TW = { backend: '後端', network: '連不上', shape: '形狀' };

  function row(it) {
    var det = it.detail && it.detail !== short(it.message);
    return '<li class="eb__i">' +
      '<div class="eb__top">' +
        '<code class="eb__fn">' + esc(it.fn) + '</code>' +
        (it.route ? '<code class="eb__rt">' + esc(it.route) + '</code>' : '') +
        (it.status ? '<span class="eb__st">' + esc(it.status) + '</span>' : '') +
        '<span class="eb__kd">' + esc(KIND_TW[it.kind] || it.kind) + '</span>' +
        (it.owner ? '<span class="eb__ow">' + esc(it.owner) + '</span>' : '') +
        (it.n > 1 ? '<span class="eb__n">×' + it.n + '</span>' : '') +
        '<span class="eb__at">' + hhmm(it.at) + '</span>' +
      '</div>' +
      '<div class="eb__msg">' + esc(short(it.message)) + '</div>' +
      (det ? '<div class="eb__raw">後端原話：' + esc(it.detail) + '</div>' : '') +
      '</li>';
  }

  /* 手機上錯誤匣是整排的，會蓋住右下角的浮出訊息。
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
    var n = state.items.length;
    if (!n) { box.hidden = true; box.innerHTML = ''; measure(box); return; }
    box.hidden = false;

    if (state.dismissed || !state.open) {
      box.className = 'eb eb--min';
      box.innerHTML = '<button type="button" class="eb__pill" id="ebOpen">' +
        '後端錯誤 <b>' + n + '</b></button>';
      measure(box);
      return;
    }

    box.className = 'eb';
    box.innerHTML =
      '<div class="eb__h">' +
        '<span class="eb__t">後端錯誤 <b>' + n + '</b></span>' +
        '<button type="button" class="eb__b" id="ebCopy">複製全部</button>' +
        '<button type="button" class="eb__b" id="ebClear">清空</button>' +
        '<button type="button" class="eb__x" id="ebMin" aria-label="收起來">收起</button>' +
      '</div>' +
      '<ul class="eb__l">' + state.items.map(row).join('') + '</ul>' +
      '<div class="eb__f">業務錯誤（403、409、422…）不算，那是後端正確地回答「不能這樣做」。</div>';
    measure(box);
  }

  document.addEventListener('click', function (e) {
    var t = e.target;
    if (!t || !t.closest) return;
    if (t.closest('#ebOpen')) { state.dismissed = false; state.open = true; render(); return; }
    if (t.closest('#ebMin')) { state.dismissed = true; render(); return; }
    if (t.closest('#ebClear')) { clear(); return; }
    if (t.closest('#ebCopy')) {
      var txt = text();
      var done = function () { if (global.toast) global.toast('已複製 ' + state.items.length + ' 支', 'ok'); };
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

  global.ErrBox = { push: push, clear: clear, text: text, render: render,
    items: function () { return state.items.slice(); } };
})(window);
