/* ============================================================
   ui.js — 兩個導覽元件
   1. 章節導覽（頁首）：隨滾動高亮目前章節，點擊跳轉
   2. 選題投票（右下）：四人各選一題，共用區域即時可見
   ============================================================ */
(function (global) {
  'use strict';

  var MEMBERS = ['冠文', '明樺', '囷洧', '宇傑'];

  /* API 位址：同源優先；若靜態站與投票服務分開部署，用 data-vote-api 覆寫 */
  var API = (function () {
    var el = document.querySelector('meta[name="vote-api"]');
    var v = el && el.content ? el.content.trim().replace(/\/$/, '') : '';
    var local = /^(localhost|127\.0\.0\.1)$/.test(location.hostname);
    return local ? 'http://localhost:8001' : v;
  })();

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  /* ============================================================
     1. 頁首章節導覽
     ============================================================ */
  var secNavEl = null, secItems = [], spyRaf = 0;

  function mountSectionNav() {
    if (!secNavEl) {
      secNavEl = document.getElementById('secnav');
      if (!secNavEl) return;
      secNavEl.addEventListener('click', function (e) {
        var b = e.target.closest('[data-jump]');
        if (b) {
          var t = document.getElementById(b.dataset.jump);
          if (t) {
            if (t.tagName === 'DETAILS') t.open = true;   // 跳到抽屜就順手打開
            window.scrollTo({ top: t.getBoundingClientRect().top + window.scrollY - 68, behavior: 'smooth' });
          }
          secNavEl.classList.remove('is-open');
          return;
        }
        if (e.target.closest('.secnav__toggle')) secNavEl.classList.toggle('is-open');
      });
    }

    var nodes = Array.prototype.slice.call(document.querySelectorAll('[data-sec]'));
    secItems = nodes.map(function (n, i) {
      if (!n.id) n.id = 'sec-' + i;
      return { id: n.id, label: n.dataset.sec, el: n };
    });

    if (!secItems.length) { secNavEl.hidden = true; return; }
    secNavEl.hidden = false;

    secNavEl.innerHTML =
      '<button class="secnav__toggle" type="button" aria-label="開啟章節選單">' +
        '<span class="secnav__tt">章節</span><span class="secnav__car"></span>' +
      '</button>' +
      '<div class="secnav__list">' +
        '<div class="secnav__hd">章節跳轉</div>' +
        secItems.map(function (s, i) {
          return '<button class="secnav__i" type="button" data-jump="' + s.id + '">' +
            '<span class="secnav__n">' + String(i + 1).padStart(2, '0') + '</span>' +
            '<span class="secnav__l">' + esc(s.label) + '</span></button>';
        }).join('') +
      '</div>';

    spy();
  }

  function spy() {
    if (spyRaf) return;
    spyRaf = requestAnimationFrame(function () {
      spyRaf = 0;
      if (!secItems.length || !secNavEl) return;
      var y = window.scrollY + 120, active = 0;
      for (var i = 0; i < secItems.length; i++) {
        if (secItems[i].el.getBoundingClientRect().top + window.scrollY <= y) active = i;
      }
      var btns = secNavEl.querySelectorAll('.secnav__i');
      for (var j = 0; j < btns.length; j++) btns[j].classList.toggle('is-on', j === active);
    });
  }
  window.addEventListener('scroll', spy, { passive: true });
  window.addEventListener('resize', spy, { passive: true });

  /* ============================================================
     2. 選題投票
     ============================================================ */
  var voteEl = null, picks = [], me = null, ctx = { id: null, title: '' };

  try { me = localStorage.getItem('capstone-me') || null; } catch (e) { me = null; }

  function api(path, opt) {
    return fetch(API + '/api/picks' + (path || ''), Object.assign({
      headers: { 'Content-Type': 'application/json' }
    }, opt || {})).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.status === 204 ? null : r.json();
    });
  }

  function loadPicks() {
    return api('').then(function (d) {
      applyPicks(d, live);
      return picks;
    }).catch(function () {
      picks = null;             // null = 服務未就緒
      render();
      return null;
    });
  }

  function myPick() {
    if (!me || !picks) return null;
    var f = picks.filter(function (p) { return p.member === me; })[0];
    return f ? f.project : null;
  }

  function setPick(projectId) {
    if (!me) return;
    api('', { method: 'PUT', body: JSON.stringify({ member: me, project: projectId }) })
      .then(loadPicks)
      .catch(function () { flash('儲存失敗，請稍後再試'); });
  }

  function clearPick() {
    if (!me) return;
    api('/' + encodeURIComponent(me), { method: 'DELETE' })
      .then(loadPicks)
      .catch(function () { flash('取消失敗，請稍後再試'); });
  }

  function flash(msg) {
    var n = voteEl && voteEl.querySelector('.vote__msg');
    if (!n) return;
    n.textContent = msg;
    n.classList.add('is-on');
    setTimeout(function () { n.classList.remove('is-on'); }, 2600);
  }

  function projectOptions(sel) {
    var list = (global.PROJECTS || []).slice().sort(function (a, b) { return a.rank - b.rank; });
    return '<option value="">— 選擇專題 —</option>' + list.map(function (p) {
      return '<option value="' + p.id + '"' + (p.id === sel ? ' selected' : '') + '>' +
        String(p.rank).padStart(2, '0') + '　' + esc(p.title) + '</option>';
    }).join('');
  }

  function titleOf(id) {
    var p = (global.PROJECTS || []).filter(function (x) { return x.id === id; })[0];
    return p ? (String(p.rank).padStart(2, '0') + '　' + p.title) : id;
  }

  function mountVote(context) {
    ctx = context || { id: null, title: '' };
    if (!voteEl) {
      voteEl = document.createElement('div');
      voteEl.className = 'vote';
      document.body.appendChild(voteEl);

      voteEl.addEventListener('click', function (e) {
        if (e.target.closest('.vote__fab') || e.target.closest('.vote__close')) {
          voteEl.classList.toggle('is-open'); return;
        }
        if (e.target.closest('[data-pick-this]')) { setPick(ctx.id); return; }
        if (e.target.closest('[data-clear]')) { clearPick(); return; }
        var go = e.target.closest('[data-goto]');
        if (go) { location.hash = '#/' + go.dataset.goto; voteEl.classList.remove('is-open'); }
      });

      voteEl.addEventListener('change', function (e) {
        if (e.target.matches('[data-me]')) {
          me = e.target.value || null;
          try { me ? localStorage.setItem('capstone-me', me) : localStorage.removeItem('capstone-me'); } catch (err) {}
          render();
        }
        if (e.target.matches('[data-proj]')) {
          if (e.target.value) setPick(e.target.value);
        }
      });

      // 免費方案的服務會休眠，第一次載入可能要等喚醒
      var warm = 0;
      (function retry() {
        loadPicks().then(function (ok) {
          if (!ok && warm < 12) { warm++; setTimeout(retry, 5000); }
        });
      })();
      connectStream();
    }
    render();
  }

  /* ---- 即時更新：SSE 為主，連不上才退回輪詢 ---- */
  var es = null, pollTimer = 0, live = false, lastSig = '', esFails = 0, esRetry = 0;

  function sigOf(list) {
    return (list || []).map(function (p) { return p.member + ':' + p.project; }).join(',');
  }

  function applyPicks(d, isLive) {
    var next = (d && d.picks) || [];
    var sig = sigOf(next);
    var changed = sig !== lastSig;
    var before = {};
    (picks || []).forEach(function (p) { before[p.member] = p.project; });

    picks = next; lastSig = sig; live = !!isLive;
    render();
    if (global.App && global.App.onPicks) global.App.onPicks(picks);

    // 別人剛剛改動的那一列閃一下，不然畫面靜靜換掉不會被注意到
    if (changed) {
      next.forEach(function (p) {
        if (before[p.member] !== p.project && p.member !== me) flashRow(p.member);
      });
    }
  }

  function flashRow(member) {
    if (!voteEl) return;
    var i = MEMBERS.indexOf(member);
    var row = voteEl.querySelectorAll('.vote__row')[i];
    var cell = document.querySelectorAll('.picks__c')[i];
    [row, cell].forEach(function (el) {
      if (!el) return;
      el.classList.remove('is-fresh');
      void el.offsetWidth;              // 重新觸發動畫
      el.classList.add('is-fresh');
      setTimeout(function () { el.classList.remove('is-fresh'); }, 2400);
    });
  }

  function stopPoll() { if (pollTimer) { clearInterval(pollTimer); pollTimer = 0; } }
  function startPoll() { if (!pollTimer) pollTimer = setInterval(loadPicks, 15000); }

  function connectStream() {
    if (!API || typeof EventSource === 'undefined') { startPoll(); return; }
    if (es) return;
    try { es = new EventSource(API + '/api/stream'); }
    catch (e) { startPoll(); return; }

    es.onopen = function () { esFails = 0; stopPoll(); live = true; render(); };
    es.onmessage = function (ev) {
      try { applyPicks(JSON.parse(ev.data), true); } catch (e) {}
    };
    es.onerror = function () {
      live = false; render(); startPoll();
      esFails++;
      // 服務真的掛了就別再敲——瀏覽器預設每三秒重連一次，會把 console 洗爆
      if (esFails >= 3) {
        closeStream();
        clearTimeout(esRetry);
        esRetry = setTimeout(function () { esFails = 0; connectStream(); }, 60000);
      }
    };
  }

  function closeStream() {
    if (es) { es.close(); es = null; }
    live = false;
  }

  // 分頁切到背景就收掉連線，回來再接。免得閒置連線一直把免費方案的服務吊著
  var idleTimer = 0;
  document.addEventListener('visibilitychange', function () {
    if (document.hidden) {
      idleTimer = setTimeout(function () { closeStream(); stopPoll(); }, 60000);
    } else {
      clearTimeout(idleTimer);
      if (!es) { connectStream(); loadPicks(); }
    }
  });

  function render() {
    if (!voteEl) return;
    var mine = myPick();
    var done = picks ? picks.length : 0;

    var board;
    if (picks === null) {
      board = '<div class="vote__off">投票服務喚醒中（免費方案休眠後首次連線約需一分鐘），稍候會自動載入。</div>';
    } else {
      board = '<div class="vote__board">' + MEMBERS.map(function (m) {
        var f = picks.filter(function (p) { return p.member === m; })[0];
        return '<div class="vote__row' + (f ? ' is-done' : '') + (m === me ? ' is-me' : '') + '">' +
          '<div class="vote__who"><b>' + esc(m) + '</b></div>' +
          (f
            ? '<button class="vote__pk" type="button" data-goto="' + f.project + '">' + esc(titleOf(f.project)) + '</button>'
            : '<span class="vote__none">尚未選擇</span>') +
        '</div>';
      }).join('') + '</div>';
    }

    voteEl.innerHTML =
      '<button class="vote__fab" type="button" aria-label="選題投票">' +
        '<span class="vote__fabk">選題</span>' +
        '<span class="vote__cnt">' + done + '<i>/4</i></span>' +
      '</button>' +
      '<div class="vote__panel">' +
        '<div class="vote__hd">選題投票' +
          '<span class="vote__live' + (live ? ' is-on' : '') + '">' + (live ? '即時同步' : '連線中') + '</span>' +
          '<button class="vote__close" type="button" aria-label="關閉">×</button></div>' +
        '<div class="vote__body">' +
          '<label class="vote__lb">我是</label>' +
          '<select class="vote__sel" data-me>' +
            '<option value="">— 選擇你的名字 —</option>' +
            MEMBERS.map(function (m) {
              return '<option value="' + m + '"' + (m === me ? ' selected' : '') + '>' + esc(m) + '</option>';
            }).join('') +
          '</select>' +

          (me
            ? (ctx.id
                ? '<button class="vote__act' + (mine === ctx.id ? ' is-on' : '') + '" type="button" data-pick-this>' +
                    (mine === ctx.id ? '✓ 這是你目前選的專題' : '把這一題設為我的選擇') +
                  '</button>'
                : '') +
              '<label class="vote__lb">' + (ctx.id ? '或直接指定' : '我選的專題') + '</label>' +
              '<select class="vote__sel" data-proj>' + projectOptions(mine) + '</select>' +
              (mine ? '<button class="vote__clear" type="button" data-clear>取消我的選擇</button>' : '')
            : '<div class="vote__hint">先選名字，才能投票。每人只有一次選擇，可以隨時更改。</div>') +

          '<div class="vote__msg"></div>' +
          '<div class="vote__lb vote__lb--sep">目前選擇狀況</div>' +
          board +
        '</div>' +
      '</div>';
  }

  /* 點面板以外的地方自動收起，避免浮動面板一直擋住內容 */
  document.addEventListener('click', function (e) {
    if (voteEl && voteEl.classList.contains('is-open') && !voteEl.contains(e.target)) {
      voteEl.classList.remove('is-open');
    }
    if (secNavEl && secNavEl.classList.contains('is-open') && !secNavEl.contains(e.target)) {
      secNavEl.classList.remove('is-open');
    }
  }, true);
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    if (voteEl) voteEl.classList.remove('is-open');
    if (secNavEl) secNavEl.classList.remove('is-open');
  });

  global.UI = {
    mountSectionNav: mountSectionNav,
    mountVote: mountVote,
    getPicks: function () { return picks || []; },
    reloadPicks: loadPicks,
    MEMBERS: MEMBERS
  };
})(window);
