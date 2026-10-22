/* 所有一般頁面共用的模式橫幅。頁面只提供標題與目前對象，不自行排列工具。 */
(function (global) {
  'use strict';

  function create(options) {
    var esc = options.escape, tint = options.tint, avatar = options.avatar, money = options.money || String;
    var root = document.getElementById('phead');
    var scope = document.getElementById('headerScope');
    var search = document.getElementById('search');
    var drawer = document.getElementById('searchDrawer');
    var searchButton = document.getElementById('searchBtn');
    var media = global.matchMedia('(max-width: 760px)');
    var enabled = false, scopeKey = '', currentMode = '', mobile = media.matches;

    function closeActivity() {
      var panel = document.getElementById('gswPanel'), button = document.getElementById('gswBtn');
      if (panel) panel.hidden = true;
      if (button) { button.classList.remove('open'); button.setAttribute('aria-expanded', 'false'); }
    }

    function setSearchOpen(open, restoreFocus) {
      var expanded = enabled && mobile && !!open;
      drawer.hidden = !enabled || (mobile && !expanded);
      searchButton.setAttribute('aria-expanded', String(expanded));
      searchButton.classList.toggle('open', expanded);
      if (expanded) { closeActivity(); search.focus(); }
      else if (restoreFocus && mobile && enabled) searchButton.focus();
    }

    function resize() {
      if (mobile === media.matches) return;
      mobile = media.matches;
      setSearchOpen(false);
    }
    media.addEventListener('change', resize);
    global.addEventListener('resize', resize);
    document.addEventListener('click', function (event) {
      var target = event.target;
      if (!target.closest) return;
      if (target.closest('#searchBtn')) {
        if (mobile) setSearchOpen(drawer.hidden, false);
      } else if (target.closest('#searchClose')) {
        setSearchOpen(false, true);
      } else if (mobile && !target.closest('#searchDrawer')) {
        setSearchOpen(false);
      }
    });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && mobile && !drawer.hidden) {
        event.preventDefault(); setSearchOpen(false, true);
      } else if (event.key === 'Escape') {
        var panel = document.getElementById('gswPanel');
        if (panel && !panel.hidden) {
          event.preventDefault(); closeActivity(); document.getElementById('gswBtn').focus();
        }
      }
    });

    function render(state) {
      enabled = !!state.enabled;
      root.dataset.mode = state.mode;
      root.dataset.tools = String(enabled);
      document.getElementById('ptitle').textContent = state.title || '';
      document.getElementById('ptitle').title = state.title || '';
      var subtitle = document.getElementById('psub');
      subtitle.textContent = state.subtitle || '';
      subtitle.title = state.subtitle || '';
      subtitle.hidden = false; // 固定副標題的位置；沒有文字也不改變橫幅高度。
      document.getElementById('pkick').textContent = enabled ? state.mode : '';
      var av = document.getElementById('pav');
      av.innerHTML = state.user ? avatar(state.user) : '';
      av.hidden = !state.user;

      var nextKey = [enabled, state.canFamily, state.scope].join(':');
      if (scopeKey !== nextKey) {
        scopeKey = nextKey;
        scope.innerHTML = !enabled ? '' : state.canFamily
          ? '<div class="seg" role="group" aria-label="切換財務對象">' + [['me', '個人'], ['family', '家庭']].map(function (item) {
              var selected = item[0] === state.scope;
              return '<button class="seg__b' + (selected ? ' on' : '') + '" data-scope="' + item[0] + '" aria-pressed="' + selected + '">' + item[1] + '</button>';
            }).join('') + '</div>'
          : '<span class="phead__mode-label">個人模式</span>';
      }
      document.getElementById('gsw').hidden = !enabled || state.mode === '家庭';
      var label = '搜尋' + state.mode + '帳本明細';
      search.placeholder = label;
      search.setAttribute('aria-label', label);
      searchButton.setAttribute('aria-label', label);
      searchButton.title = label;
      drawer.setAttribute('aria-label', label);
      if (currentMode !== state.mode || !enabled) setSearchOpen(false);
      else if (!mobile) drawer.hidden = !enabled;
      currentMode = state.mode;

      var actions = document.getElementById('pact');
      actions.innerHTML = state.actions || '';
      actions.hidden = !state.actions;
    }

    function setActivities(activities, selectedId) {
      var box = document.getElementById('gsw');
      var current = activities.filter(function (activity) { return activity.id === selectedId; })[0];
      var label = current ? current.name : activities.length ? '選擇活動' : '目前尚未建立活動';
      var accessibleLabel = activities.length ? '切換活動，目前是' + label : '目前尚未建立活動，開啟活動選單';
      box.innerHTML = '<button class="gsw__b" id="gswBtn" title="' + esc(label) + '" aria-label="' + esc(accessibleLabel) + '" aria-expanded="false" aria-controls="gswPanel">' +
        (activities.length ? '<span class="gsw__d" style="background:' + tint(current ? current.color : 'book-indigo') + '"></span>' : '') +
        '<span class="gsw__n">' + esc(label) + '</span>' +
        '<svg class="gsw__cv" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></button>' +
        '<div class="gsw__p" id="gswPanel" hidden>' +
        (activities.length ? activities.map(function (activity) {
          return '<button class="gsw__i' + (activity.id === selectedId ? ' on' : '') + '" data-group="' + esc(activity.id) + '">' +
            '<span class="gsw__d" style="background:' + tint(activity.color) + '"></span>' +
            '<span class="gsw__m"><b>' + esc(activity.name) + '</b><i>' + activity.count + ' 筆' + (activity.goal ? '　目標 ' + money(activity.goal) : '') + '</i></span></button>';
        }).join('') : '<p class="gsw__empty">目前尚未建立活動</p><a class="gsw__i gsw__create" href="#/groups">建立活動 →</a>') +
        '<a class="gsw__more" href="#/" data-personal-return>回到個人帳本 →</a></div>';
    }

    setSearchOpen(false);
    return { render: render, setActivities: setActivities, closeSearch: function () { setSearchOpen(false); } };
  }

  global.FBPageHeader = { create: create };
})(window);
