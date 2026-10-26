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

   輪詢 5 秒就接近即時，而且斷線重連是免費的（下一次輪詢自然就接上了）；
   使用者自己做完會產生通知的動作（記帳、邀請、改零用金），api.js 會立刻再問一次。
   ============================================================ */
(function (global) {
  'use strict';

  var POLL_MS = 5000;           // 5 秒問一次
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
    busy: false,                // 同時只跑一次輪詢，見 poll()
    down: null                  // 這支路由還沒做的話，鈴鐺裡要講出來，見 poll()
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
            try { ding(); toastNew(fresh[0], fresh.length, fresh); } catch (e) {}
          }
        }
        state.down = null;
        render();
      })
      .catch(function (e) {
        /* 連不上、逾時 —— 安靜地等下一次，不要每 20 秒吵一次。
           但「通知那一支壞了」不一樣：不講的話，鈴鐺會顯示
           「目前沒有通知」，看的人會以為真的沒有通知。e.message 是白話（見 api.js 的 USER_TEXT）。 */
        var was = state.down;
        state.down = (e && e.kind === 'backend') ? e.message : null;
        if (state.open || was !== state.down) render();
      })
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
    state.down = null;
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

  var ALLOWANCE_TW = { paid: '給了你這個月的零用金', adjusted: '把這個月的零用金改成', cancelled: '取消了這個月的零用金' };

  var KIND_TW = { budget_alert: '階段性提醒', allowance: '零用金', family_invite: '家庭邀請',
                  activity_invite: '活動邀請', activity_target: '目標金額' };

  function line(n) {
    /* 記帳類：監管對象記帳（ward_transaction）、有開通知的帳本有人記帳（group_transaction），畫面上長一樣。
       其他：支出跨過門檻（budget_alert）、零用金（allowance）、家庭邀請（family_invite）、
       活動邀請（activity_invite）、活動到達目標金額（activity_target）。
       ⚠️ 型別要用 type 判斷，不要靠「有沒有 actorName」猜——
       之後多一種通知，猜的那套就會壞。 */
    if (n.type === 'budget_alert') {
      /* percent 是「你設的門檻」，reached 是「實際用掉幾成」。
         ⚠️ 兩個一起顯示時要講清楚誰是誰——
         只寫門檻再附上金額，讀起來會像「12,800 是 5,000 的 90%」。 */
      var hit = n.reached != null ? n.reached : n.percent;
      /* ⚠️ 可支配上限 = 收入 − 每月想存，**可能是 0 或負數**（這本帳還沒有收入、或目標訂得比收入高）。
         直接寫「可支配 NT$ -5,000」讀起來像系統算錯，所以那種情況改講原因。 */
      var money2 = n.allowance > 0
        ? money(n.spent) + ' / 可支配 ' + money(n.allowance)
        : money(n.spent) + '・這個月還沒有收入進來，可支配是 0';
      return esc(n.groupName || '整體') + ' 已用掉可支配額度的 <b>' + esc(hit) + '%</b>' +
        '（超過你設的 ' + esc(n.percent) + '%）' +
        (n.spent != null ? '<br><span class="bell__n2">' + money2 + '</span>' : '');
    }
    if (n.type === 'allowance') {
      return esc(n.payerName || '家長') + ' ' + ALLOWANCE_TW[n.action] +
        (n.action === 'cancelled' ? '' : ' <b>' + money(n.amount) + '</b>') +
        (n.action === 'adjusted' && n.prev != null ? '<br><span class="bell__n2">原本 ' + money(n.prev) + '</span>' : '');
    }
    if (n.type === 'family_invite') {
      return esc(n.inviterName || '家人') + ' 邀請你以' + (n.role === 'parent' ? '家長' : '子女') +
        '身分加入「' + esc(n.familyName) + '」<br><span class="bell__n2">到總覽最上面按加入</span>';
    }
    if (n.type === 'activity_invite') {
      return esc(n.inviterName || '朋友') + ' 邀請你加入活動「' + esc(n.groupName) + '」' +
        '<br><span class="bell__n2">到活動管理按接受</span>';
    }
    if (n.type === 'activity_target') {
      return '「' + esc(n.groupName) + '」' + (n.metric === 'saved' ? '已存到 ' : '已花到 ') +
        '<b>' + money(n.value) + '</b>，到了你設的目標金額 ' + money(n.goal);
    }
    var who = esc(n.actorName || '家人');
    var what = esc(n.catName || '一筆');
    var where = n.merchant ? '（' + esc(n.merchant) + '）' : '';
    return who + ' 記了一筆 ' + what + ' ' + money(n.amount) + where;
  }

  /* 同一個人一次記好幾筆（段落記帳一次確認、或連著手動記）會產生好幾則通知。
     畫面上合成一則：「冠文_user 記了 4 筆，共 NT$ 285」，點一下全部標成已讀。
     規則：記帳類（不是預算提醒）、同一個人、同一種、彼此相隔 60 秒內、在清單裡相鄰。
     ⚠️ 只合併顯示，後端照樣一筆一則——之後要改合併規則，不用動資料。 */
  var GROUP_MS = 60000;
  var TX_TYPES = ['ward_transaction', 'group_transaction'];
  function grouped(items) {
    var out = [];
    items.forEach(function (n) {
      var last = out[out.length - 1];
      var prev = last && last.items[last.items.length - 1];
      if (prev && TX_TYPES.indexOf(n.type) >= 0 && prev.type === n.type &&
          String(prev.actorId) === String(n.actorId) &&
          Math.abs(new Date(prev.createdAt) - new Date(n.createdAt)) <= GROUP_MS) {
        last.items.push(n);
      } else {
        out.push({ items: [n] });
      }
    });
    return out;
  }

  function groupLine(g) {
    if (g.items.length === 1) return line(g.items[0]);
    var n = g.items[0];
    var total = g.items.reduce(function (sum, x) { return sum + (Number(x.amount) || 0); }, 0);
    var cats = [];
    g.items.forEach(function (x) { if (x.catName && cats.indexOf(x.catName) < 0) cats.push(x.catName); });
    return esc(n.actorName || '家人') + ' 記了 <b>' + g.items.length + '</b> 筆，共 ' + money(total) +
      (cats.length ? '<br><span class="bell__n2">' + esc(cats.join('、')) + '</span>' : '');
  }

  function toastNew(n, count, fresh) {
    if (!global.toast) return;
    // toast 會把訊息 esc 過，所以這裡要把 line() 的標籤去掉，
    // 不然畫面上會出現 <b> 這種字樣
    var gs = fresh ? grouped(fresh) : [{ items: [n] }];
    var txt = groupLine(gs[0]).replace(/<br>/g, '　').replace(/<[^>]+>/g, '');
    global.toast(gs.length > 1 ? txt + '　等 ' + gs.length + ' 則新通知' : txt, 'ok');
  }

  function render() {
    var btn = document.getElementById('bell');
    var dot = document.getElementById('bellDot');
    var panel = document.getElementById('bellPanel');
    if (!btn || !dot || !panel) return;

    /* 沒有監管對象的人（例如子女）不該看到一個永遠空的鈴鐺。
       這裡用「一則都沒有」當作判斷：監管者一旦有人記帳就會出現。
       ⚠️ state.down（那一支還沒做）要例外：鈴鐺收起來的話，
          「收不到通知」這件事就沒有地方講了。 */
    var wrap = btn.parentNode;
    if (wrap) wrap.hidden = !state.items.length && !state.unread && !state.down;

    /* 紅點算「則」：合併成一則的那幾筆只算一次（清單外、還沒載入的未讀照樣算進去） */
    var groups = grouped(state.items);
    var unreadItems = state.items.filter(function (n) { return !n.readAt; }).length;
    var unreadGroups = groups.filter(function (g) { return g.items.some(function (n) { return !n.readAt; }); }).length;
    var shown = Math.max(0, state.unread - unreadItems + unreadGroups);
    dot.textContent = shown > 99 ? '99+' : shown;
    dot.hidden = shown === 0;
    btn.classList.toggle('has', shown > 0);

    var wasHidden = panel.hidden;
    btn.classList.toggle('open', state.open);
    if (!state.open) {
      // 關起來就把內容清掉。留著的話，換人之後 DOM 裡還躺著
      // 上一個使用者的記帳明細 —— 看不到不等於不在。
      // 先往上收完再清，不然內容一清面板就瞬間變空白。
      var clear = function () { if (!state.open) panel.innerHTML = ''; };
      if (global.__slide && !wasHidden) global.__slide.close(panel, clear);
      else { panel.hidden = true; clear(); }
      return;
    }
    panel.hidden = false;

    var h = '<div class="bell__h">' +
      '<span class="bell__t">通知</span>' +
      '<button class="bell__mute" id="bellMute" title="開關提示音">' +
        (muted() ? '🔇 靜音中' : '🔔 有聲音') + '</button>' +
      (state.unread ? '<button class="bell__all" id="bellAll">全部已讀</button>' : '') +
      (state.items.some(function (x) { return x.readAt; }) ? '<button class="bell__all" id="bellClear">清除已讀</button>' : '') +
      '</div>';

    if (!state.items.length && state.down) {
      h += '<div class="bell__empty">' + esc(state.down) + '<br>' +
        '<span>通知暫時收不到，稍後會自動再試。</span></div>';
    } else if (!state.items.length) {
      h += '<div class="bell__empty">目前沒有通知。<br>' +
        '<span>被你監管的成員新增記帳時，這裡會即時跳出來。</span></div>';
    } else {
      h += '<div class="bell__list">' + groups.map(function (g) {
        var n = g.items[0];
        var unread = g.items.some(function (x) { return !x.readAt; });
        var ids = g.items.map(function (x) { return x.id; }).join(',');
        return '<div class="bell__row"><button class="bell__i' + (unread ? ' unread' : '') +
          '" data-nid="' + esc(ids) + '"' +
          ' data-tx="' + esc(g.items.length === 1 ? (n.txId || '') : '') + '">' +
          '<span class="bell__dot"></span>' +
          '<span class="bell__m">' +
            '<span class="bell__l">' + groupLine(g) + '</span>' +
            '<span class="bell__s">' + ago(n.createdAt) + '　·　' +
              (KIND_TW[n.type] || '唯讀檢視') + '</span>' +
          '</span></button>' +
          '<button class="bell__del" data-ndel="' + esc(ids) + '" aria-label="刪除這則通知" title="刪除">&#10005;</button></div>';
      }).join('') + '</div>';
    }

    panel.innerHTML = h;
    if (wasHidden && global.__slide) global.__slide.open(panel);
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

    /* 刪通知：這一列（合併的那一列一次好幾則），或「清除已讀」 */
    var del = e.target.closest && (e.target.closest('[data-ndel]') || e.target.closest('#bellClear'));
    if (del) {
      if (!global.API.deleteNotifications) return;
      var gone = del.id === 'bellClear'
        ? state.items.filter(function (x) { return x.readAt; }).map(function (x) { return String(x.id); })
        : String(del.dataset.ndel || '').split(',');
      if (!gone.length) return;
      global.API.deleteNotifications(gone).then(function () {
        var lost = state.items.filter(function (x) { return gone.indexOf(String(x.id)) >= 0 && !x.readAt; }).length;
        state.items = state.items.filter(function (x) { return gone.indexOf(String(x.id)) < 0; });
        state.unread = Math.max(0, state.unread - lost);
        render();
      });
      return;
    }

    var item = e.target.closest && e.target.closest('.bell__i');
    if (item) {
      /* 合併的那一則帶著好幾個 id：一次全部標成已讀 */
      var ids = String(item.dataset.nid || '').split(',');
      var picked = state.items.filter(function (x) { return ids.indexOf(String(x.id)) >= 0; });
      var n = picked[0];
      picked.filter(function (x) { return !x.readAt; }).forEach(function (x) {
        if (!global.API.readNotification) return;
        global.API.readNotification(x.id).then(function () {
          x.readAt = new Date().toISOString();
          state.unread = Math.max(0, state.unread - 1);
          render();
        });
      });
      state.open = false;
      render();
      /* 跳到那個人的記帳表單，並把這一筆標起來（合併的那一則只跳到他的紀錄）。
         只跳到家庭總覽的話，使用者還要自己在一堆紀錄裡找是哪一筆。 */
      if (n && (n.type === 'budget_alert' || n.type === 'family_invite' || n.type === 'activity_target')) {
        // 提醒點下去看自己的總覽，不是別人的紀錄；家庭邀請的「加入」也在總覽最上面
        location.hash = '#/';
      } else if (n && n.type === 'allowance') {
        location.hash = '#/entry';
      } else if (n && n.type === 'activity_invite') {
        location.hash = '#/groups';
      } else if (n && n.actorId) {
        location.hash = '#/member/' + n.actorId + (item.dataset.tx ? '/' + item.dataset.tx : '');
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
