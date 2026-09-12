/* ============================================================
   notify.js — 監管通知：輪詢、音效、鈴鐺

   ★ 這個檔案做的事
   ------------------------------------------------------------
   子女新增一筆記帳 → 監管者的畫面上要跳出通知、要有聲音。

   為什麼用輪詢不用 SSE
   ------------------------------------------------------------
   EventSource 沒辦法送自訂標頭，不能帶 Authorization: Bearer，
   只能把 token 放網址上 —— 而網址會進瀏覽器歷史、伺服器日誌、
   Referer 標頭。為了 SSE 破壞「token 絕不放查詢參數」的規則不划算。

   輪詢 20 秒對「子女記了一筆帳」這種通知完全夠用，而且斷線重連
   是免費的（下一次輪詢自然就接上了）。
   ============================================================ */
(function (global) {
  'use strict';

  var POLL_MS = 20000;          // 20 秒問一次
  var MUTE_KEY = 'fambudget.notify.mute';
  var SEEN_KEY = 'fambudget.notify.seen';

  var state = {
    items: [],
    unread: 0,
    maxId: null,
    open: false,
    timer: null,
    audio: null,
    unlocked: false,
    busy: false                 // 同時只跑一次輪詢，見 poll()
  };

  /* ---------------------------------------------------------
     音效：用 Web Audio 合成，不放 mp3
     ---------------------------------------------------------
     好處是不用託管音檔、不用等下載、離線也能響。
     ⚠️ 瀏覽器會擋自動播放：使用者第一次跟頁面互動之前，
     AudioContext 是 suspended 狀態，所以要在第一次點擊時 resume。
     --------------------------------------------------------- */
  function muted() {
    try { return localStorage.getItem(MUTE_KEY) === '1'; } catch (e) { return false; }
  }
  function setMuted(v) {
    try { localStorage.setItem(MUTE_KEY, v ? '1' : '0'); } catch (e) {}
  }

  function unlockAudio() {
    if (state.unlocked) return;
    var AC = global.AudioContext || global.webkitAudioContext;
    if (!AC) return;
    try {
      state.audio = state.audio || new AC();
      if (state.audio.state === 'suspended') state.audio.resume();
      state.unlocked = true;
    } catch (e) { /* 不支援就算了，通知還是看得到 */ }
  }

  function ding() {
    if (muted() || !state.audio) return;
    try {
      var t = state.audio.currentTime;
      // 兩個音，像是「叮－咚」，比單音好認又不刺耳
      [880, 1174.7].forEach(function (hz, i) {
        var osc = state.audio.createOscillator();
        var gain = state.audio.createGain();
        osc.type = 'sine';
        osc.frequency.value = hz;
        gain.gain.setValueAtTime(0.0001, t + i * 0.12);
        gain.gain.exponentialRampToValueAtTime(0.12, t + i * 0.12 + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, t + i * 0.12 + 0.28);
        osc.connect(gain);
        gain.connect(state.audio.destination);
        osc.start(t + i * 0.12);
        osc.stop(t + i * 0.12 + 0.3);
      });
    } catch (e) {}
  }

  /* ---------------------------------------------------------
     輪詢
     --------------------------------------------------------- */
  function poll(first) {
    if (!global.API || !global.API.notifications) return Promise.resolve();

    /* 同時只允許一次請求在飛。
       會撞在一起的情境：20 秒的定時輪詢還沒回來，使用者剛好切回分頁
       （visibilitychange）又打一次 —— 兩邊都還沒更新 maxId，
       就會拿到同一批新通知，結果叮兩聲、清單出現重複。 */
    if (state.busy) return Promise.resolve();
    state.busy = true;

    return global.API.notifications({ since: state.maxId })
      .then(function (r) {
        var fresh = r.notifications || [];
        state.unread = r.unread || 0;
        if (fresh.length) {
          state.items = fresh.concat(state.items).slice(0, 50);
          state.maxId = r.maxId || state.maxId;
          // 第一次載入不要叮，不然一進站就一堆聲音
          // 包 try：叮一聲或跳提示壞掉，不該連帶讓整個清單不重畫。
          // （外層那個 .catch 會把例外吃掉，下面的 render() 就不會跑）
          if (!first) {
            try { ding(); toastNew(fresh[0], fresh.length); } catch (e) {}
          }
        }
        render();
      })
      .catch(function () { /* 輪詢失敗就安靜地等下一次 */ })
      .then(function () { state.busy = false; });
  }

  /* 換人了就要把上一個人的通知清乾淨。
     ⚠️ 不清的後果是把 A 的記帳內容顯示給 B 看 ——
     登入／登出如果沒有整頁重載（我們是單頁），state.items 會留著。 */
  function reset() {
    state.items = [];
    state.unread = 0;
    state.maxId = null;
    state.open = false;
    render();
  }

  function start() {
    stop();
    reset();
    poll(true);
    state.timer = setInterval(poll, POLL_MS);
    // 切回這個分頁時立刻問一次，不用等 20 秒
    document.addEventListener('visibilitychange', onVisible);
  }
  function stop() {
    if (state.timer) clearInterval(state.timer);
    state.timer = null;
    document.removeEventListener('visibilitychange', onVisible);
  }
  function onVisible() {
    if (document.visibilityState === 'visible') poll();
  }

  /* ---------------------------------------------------------
     畫面
     --------------------------------------------------------- */
  function esc(t) {
    return String(t == null ? '' : t)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function money(n) {
    return 'NT$ ' + Number(n || 0).toLocaleString('en-US');
  }

  function ago(iso) {
    var d = new Date(iso);
    if (isNaN(d.getTime())) return '';
    var s = Math.max(0, (Date.now() - d.getTime()) / 1000);
    if (s < 60) return '剛剛';
    if (s < 3600) return Math.floor(s / 60) + ' 分鐘前';
    if (s < 86400) return Math.floor(s / 3600) + ' 小時前';
    return Math.floor(s / 86400) + ' 天前';
  }

  function line(n) {
    /* 兩種通知：子女記帳、支出跨過門檻。
       ⚠️ 型別要用 type 判斷，不要靠「有沒有 actorName」猜——
       之後多一種通知，猜的那套就會壞。 */
    if (n.type === 'budget_alert') {
      /* percent 是「你設的門檻」，reached 是「實際用掉幾成」。
         ⚠️ 兩個一起顯示時要講清楚誰是誰——
         只寫門檻再附上金額，讀起來會像「12,800 是 5,000 的 90%」。 */
      var hit = n.reached != null ? n.reached : n.percent;
      return esc(n.groupName || '整體') + ' 已用掉可支配額度的 <b>' + esc(hit) + '%</b>' +
        '（超過你設的 ' + esc(n.percent) + '%）' +
        (n.spent != null
          ? '<br><span class="bell__n2">' + money(n.spent) + ' / 可支配 ' +
            money(n.allowance) + '</span>'
          : '');
    }
    var who = esc(n.actorName || '家人');
    var what = esc(n.catName || '一筆');
    var where = n.merchant ? '（' + esc(n.merchant) + '）' : '';
    return who + ' 記了一筆 ' + what + ' ' + money(n.amount) + where;
  }

  function toastNew(n, count) {
    if (!global.toast) return;
    // toast 會把訊息 esc 過，所以這裡要把 line() 的標籤去掉，
    // 不然畫面上會出現 <b> 這種字樣
    var txt = line(n).replace(/<br>/g, '　').replace(/<[^>]+>/g, '');
    global.toast(count > 1 ? txt + '　等 ' + count + ' 筆新紀錄' : txt, 'ok');
  }

  function render() {
    var btn = document.getElementById('bell');
    var dot = document.getElementById('bellDot');
    var panel = document.getElementById('bellPanel');
    if (!btn || !dot || !panel) return;

    /* 沒有監管對象的人（例如子女）不該看到一個永遠空的鈴鐺。
       這裡用「一則都沒有」當作判斷：監管者一旦有人記帳就會出現。 */
    var wrap = btn.parentNode;
    if (wrap) wrap.hidden = !state.items.length && !state.unread;

    dot.textContent = state.unread > 99 ? '99+' : state.unread;
    dot.hidden = state.unread === 0;
    btn.classList.toggle('has', state.unread > 0);

    panel.hidden = !state.open;
    if (!state.open) {
      // 關起來就把內容清掉。留著的話，換人之後 DOM 裡還躺著
      // 上一個使用者的記帳明細 —— 看不到不等於不在。
      panel.innerHTML = '';
      return;
    }

    var h = '<div class="bell__h">' +
      '<span class="bell__t">監管通知</span>' +
      '<button class="bell__mute" id="bellMute" title="開關提示音">' +
        (muted() ? '🔇 靜音中' : '🔔 有聲音') + '</button>' +
      (state.unread ? '<button class="bell__all" id="bellAll">全部已讀</button>' : '') +
      '</div>';

    if (!state.items.length) {
      h += '<div class="bell__empty">目前沒有通知。<br>' +
        '<span>被你監管的成員新增記帳時，這裡會即時跳出來。</span></div>';
    } else {
      h += '<div class="bell__list">' + state.items.map(function (n) {
        return '<button class="bell__i' + (n.readAt ? '' : ' unread') +
          '" data-nid="' + esc(n.id) + '" data-tx="' + esc(n.txId || '') + '">' +
          '<span class="bell__dot"></span>' +
          '<span class="bell__m">' +
            '<span class="bell__l">' + line(n) + '</span>' +
            '<span class="bell__s">' + ago(n.createdAt) + '　·　' +
              (n.type === 'budget_alert' ? '階段性提醒' : '唯讀檢視') + '</span>' +
          '</span></button>';
      }).join('') + '</div>';
    }

    h += '<div class="bell__f">監管是<b>唯讀</b>的 —— 你看得到，但不能修改或刪除。</div>';
    panel.innerHTML = h;
  }

  /* ---------------------------------------------------------
     事件
     --------------------------------------------------------- */
  document.addEventListener('click', function (e) {
    unlockAudio();

    var bell = e.target.closest && e.target.closest('#bell');
    if (bell) {
      state.open = !state.open;
      render();
      return;
    }

    if (e.target.closest && e.target.closest('#bellMute')) {
      setMuted(!muted());
      if (!muted()) ding();
      render();
      return;
    }

    if (e.target.closest && e.target.closest('#bellAll')) {
      if (!global.API.readNotifications) return;
      global.API.readNotifications(state.maxId).then(function () {
        state.items.forEach(function (n) { n.readAt = n.readAt || new Date().toISOString(); });
        state.unread = 0;
        render();
      });
      return;
    }

    var item = e.target.closest && e.target.closest('.bell__i');
    if (item) {
      var nid = item.dataset.nid;
      var n = state.items.filter(function (x) { return String(x.id) === nid; })[0];
      if (n && !n.readAt && global.API.readNotification) {
        global.API.readNotification(nid).then(function () {
          n.readAt = new Date().toISOString();
          state.unread = Math.max(0, state.unread - 1);
          render();
        });
      }
      state.open = false;
      render();
      /* 跳到那個人的記帳表單，並把這一筆標起來。
         只跳到家庭總覽的話，使用者還要自己在一堆紀錄裡找是哪一筆。 */
      if (n && n.type === 'budget_alert') {
        // 提醒點下去看自己的總覽，不是別人的紀錄
        location.hash = '#/';
      } else if (n && n.actorId) {
        location.hash = '#/member/' + n.actorId + (n.txId ? '/' + n.txId : '');
      }
      return;
    }

    // 點面板外面就收起來
    if (state.open && !(e.target.closest && e.target.closest('#bellPanel'))) {
      state.open = false;
      render();
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && state.open) { state.open = false; render(); }
  });

  global.Notify = {
    start: start,
    stop: stop,
    reset: reset,
    refresh: function () { return poll(); },
    render: render
  };
})(window);
