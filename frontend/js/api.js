/* ============================================================
   api.js — 前端唯一的資料入口
   ------------------------------------------------------------
   畫面程式碼一律只呼叫 API.xxx()，永遠不要直接讀 window.DATA。
   要接真後端，只要改 index.html 的 <meta name="api-base">。

   ------------------------------------------------------------
   後端契約

   身分
   POST   /api/auth/register          註冊
   POST   /api/auth/login             登入 → { accessToken, refreshToken, user }
   POST   /api/auth/refresh           換新 token
   POST   /api/auth/logout            登出（撤銷 refresh token）
   GET    /api/auth/me                目前登入者 + 家庭角色

   家庭與權限
   GET    /api/family                 家庭資訊與成員清單
   POST   /api/family/invite          產生邀請碼（master）
   PATCH  /api/family/members/{id}    改角色（master）
   DELETE /api/family/members/{id}    移除成員（master）
   GET    /api/guardianships          監管關係（雙方都看得到）
   POST   /api/guardianships          建立監管（master）
   DELETE /api/guardianships/{id}     解除監管（master）

   記帳
   GET    /api/transactions           明細（可帶 user / from / to / cat / kind / q）
   POST   /api/transactions           新增（手動記帳走這支，不經過模型）
   PATCH  /api/transactions/{id}      修改
   DELETE /api/transactions/{id}      刪除
   POST   /api/nlp/parse              ★ 單句記帳：一句話 → 一筆（不寫入）
   POST   /api/nlp/parse-batch        ★ 段落記帳：一段話 → 切分成 N 筆（不寫入）
   POST   /api/nlp/confirm            單筆確認後寫入，並記錄修正供評測
   POST   /api/nlp/confirm-batch      批次確認後一次寫入 N 筆

   統計與預算
   GET    /api/summary                個人／家庭摘要（帶 scope=me|family, period）
   GET    /api/stats                  月或年統計（帶 periodType=month|year）
   GET    /api/budgets                預算與使用率
   PUT    /api/budgets                設定預算
   GET    /api/savings-goal           ★ 每月存款目標與達成狀態
   PUT    /api/savings-goal           ★ 設定每月存款目標（註冊時也走這支）

   建議
   GET    /api/advices                LLM 財務建議（帶 scope / period）
   POST   /api/advices/generate       重新產生（後端先算好數字再餵給模型）

   其他
   GET    /api/categories             分類體系
   GET    /api/schema                 資料表結構與關聯（ER 圖用）
   ============================================================ */
(function (global) {
  'use strict';

  var BASE = (function () {
    var el = document.querySelector('meta[name="api-base"]');
    return el && el.content ? el.content.trim().replace(/\/$/, '') : '';
  })();

  var MODE = BASE ? 'http' : 'mock';
  var LATENCY = 240;
  var KEY = 'fambudget.state.v1';

  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function clone(x) { return JSON.parse(JSON.stringify(x)); }

  /* ---------- mock 模式的「資料庫」 ---------- */
  var state = null;

  /* 註冊時填的存款目標。使用者改過之後要存得住，reset 再還原回這裡 */
  var GOALS0 = null;
  function applyGoals(map) {
    if (!GOALS0) {
      GOALS0 = {};
      global.DATA.members.forEach(function (m) { GOALS0[m.id] = m.savingsGoal; });
    }
    global.DATA.members.forEach(function (m) {
      m.savingsGoal = (map && map[m.id] !== undefined) ? map[m.id] : GOALS0[m.id];
    });
  }

  function load() {
    if (state) return state;
    var base = {
      me: 'U1',                                   // 模擬目前登入者
      transactions: clone(global.DATA.transactions),
      budgets: clone(global.DATA.budgets),
      goals: {}
    };
    try {
      var saved = JSON.parse(localStorage.getItem(KEY) || 'null');
      if (saved) {
        if (saved.me) base.me = saved.me;
        if (saved.extra) base.transactions = saved.extra.concat(base.transactions);
        if (saved.goals) base.goals = saved.goals;
      }
    } catch (e) {}
    applyGoals(base.goals);
    state = base;
    return state;
  }
  function save() {
    try {
      var extra = state.transactions.filter(function (t) { return t.id.indexOf('N') === 0; });
      localStorage.setItem(KEY, JSON.stringify({
        me: state.me, extra: extra, goals: state.goals || {}
      }));
    } catch (e) {}
  }

  function memberOf(id) {
    return global.DATA.members.filter(function (m) { return m.id === id; })[0];
  }
  /* 我看得到誰的資料：自己 + 被我監管的人（master 看全家） */
  function visibleUsers(meId) {
    var me = memberOf(meId);
    if (!me) return [meId];
    if (me.role === 'master') return global.DATA.members.map(function (m) { return m.id; });
    var wards = global.DATA.guardianships
      .filter(function (g) { return g.guardian === meId; })
      .map(function (g) { return g.ward; });
    return [meId].concat(wards);
  }

  function sum(list, kind) {
    return list.filter(function (t) { return t.kind === kind; })
      .reduce(function (n, t) { return n + t.amount; }, 0);
  }

  /* ============================================================
     mock 轉接器
     ============================================================ */
  var mock = {

    me: function () {
      var s = load();
      return sleep(120).then(function () {
        var m = memberOf(s.me);
        return {
          user: clone(m),
          family: clone(global.DATA.meta),
          visible: visibleUsers(s.me),
          guardedBy: global.DATA.guardianships
            .filter(function (g) { return g.ward === s.me; })
            .map(function (g) { return clone(memberOf(g.guardian)); })
        };
      });
    },

    switchUser: function (id) {
      var s = load();
      return sleep(160).then(function () {
        s.me = id; save();
        return { me: id };
      });
    },

    summary: function (f) {
      f = f || {};
      var s = load(), D = global.DATA;
      return sleep(LATENCY).then(function () {
        var users = f.scope === 'family' ? visibleUsers(s.me) : [s.me];
        var tx = s.transactions.filter(function (t) {
          return users.indexOf(t.user) >= 0 && t.date.indexOf(D.meta.period) === 0;
        });
        // 成員表上的 income / expense 是本月至今的合計（示範明細已含在內）；
        // 使用者新記的（id 以 N 開頭）才另外加上去，這樣兩個畫面的數字才會一致
        var added = tx.filter(function (t) { return String(t.id).indexOf('N') === 0; });
        var income = users.reduce(function (n, u) {
          var m = memberOf(u); return n + (m ? m.income : 0);
        }, 0) + sum(added, 'income');
        var expense = users.reduce(function (n, u) {
          var m = memberOf(u); return n + (m ? m.expense : 0);
        }, 0) + sum(added, 'expense');
        var byCat = {};
        tx.filter(function (t) { return t.kind === 'expense'; }).forEach(function (t) {
          byCat[t.cat] = (byCat[t.cat] || 0) + t.amount;
        });
        // 存款目標：可支配上限 = 收入 − 目標，支出超過就存不到
        var goal = users.reduce(function (n, u) {
          var m = memberOf(u);
          return n + (m && m.savingsGoal ? m.savingsGoal : 0);
        }, 0);
        var allow = income - goal;
        var ratio = allow > 0 ? expense / allow : (expense > 0 ? 2 : 0);
        var rule = D.savingsRule;
        var level = ratio >= rule.overAt ? 'over' : (ratio >= rule.warnAt ? 'near' : 'safe');

        return {
          period: D.meta.period,
          scope: f.scope || 'me',
          income: income, expense: expense, net: income - expense,
          rate: income ? (income - expense) / income : 0,
          count: tx.length,
          savings: {
            goal: goal,
            allowance: allow,
            used: expense,
            left: allow - expense,
            ratio: ratio,
            level: level,
            shortfall: Math.max(0, expense - allow),
            actual: income - expense,
            rule: clone(rule)
          },
          byCat: Object.keys(byCat).map(function (c) {
            var cat = D.categories.filter(function (x) { return x.id === c; })[0];
            return { cat: c, name: cat.name, color: cat.color, amount: byCat[c] };
          }).sort(function (a, b) { return b.amount - a.amount; }),
          monthly: clone(D.monthly),
          yearly: clone(D.yearly),
          members: D.members.filter(function (m) { return users.indexOf(m.id) >= 0; })
            .map(function (m) {
              var a = m.income - (m.savingsGoal || 0);
              var r = a > 0 ? m.expense / a : (m.expense > 0 ? 2 : 0);
              return Object.assign(clone(m), {
                allowance: a,
                savingsRatio: r,
                savingsLevel: r >= rule.overAt ? 'over' : (r >= rule.warnAt ? 'near' : 'safe'),
                shortfall: Math.max(0, m.expense - a)
              });
            })
        };
      });
    },

    transactions: function (f) {
      f = f || {};
      var s = load(), D = global.DATA;
      return sleep(LATENCY).then(function () {
        var vis = visibleUsers(s.me);
        var rows = s.transactions.filter(function (t) {
          if (vis.indexOf(t.user) < 0) return false;
          if (f.user && f.user !== 'all' && t.user !== f.user) return false;
          if (f.kind && f.kind !== 'all' && t.kind !== f.kind) return false;
          if (f.source && f.source !== 'all' && (t.source || 'manual') !== f.source) return false;
          if (f.q) {
            var hay = (t.merchant + ' ' + (t.note || '') + ' ' + (t.raw || '')).toLowerCase();
            if (hay.indexOf(f.q.toLowerCase()) < 0) return false;
          }
          return true;
        });
        rows.sort(function (a, b) { return a.date < b.date ? 1 : -1; });
        return {
          transactions: rows.map(function (t) {
            var c = D.categories.filter(function (x) { return x.id === t.cat; })[0];
            return Object.assign(clone(t), {
              userName: memberOf(t.user).name,
              catName: c ? c.name : '',
              catColor: c ? c.color : '#5B7085'
            });
          }),
          total: rows.length
        };
      });
    },

    /* ★ 自然語言記帳：只解析、不寫入。使用者確認後才呼叫 confirm */
    nlpParse: function (text) {
      var D = global.DATA;
      return sleep(900).then(function () {
        var demo = D.nlpDemo.filter(function (x) { return x.raw === text; })[0];
        if (demo) return { raw: text, out: clone(demo.out), note: demo.note, matched: true };
        // 沒對到示範句時做一個很陽春的示意解析（真後端由模型負責）
        var m = String(text).match(/(\d+)/);
        var amt = m ? Number(m[1]) : 0;
        return {
          raw: text, matched: false,
          out: { date: D.meta.period + '-10', amount: amt, kind: 'expense',
                 cat: 'C08', merchant: '', conf: amt ? 0.55 : 0.2, catConf: 0.3 },
          note: 'mock 模式只做示意解析。真後端由模型負責，並會回傳每個欄位的信心度。'
        };
      });
    },

    /* ★ 段落解析：一段話可能有好幾筆，模型要先切分再逐筆抽欄位 */
    nlpParseBatch: function (text) {
      var D = global.DATA;
      return sleep(1500).then(function () {
        var demo = D.paragraphDemo;
        if (String(text).trim() === demo.raw) {
          return { raw: text, matched: true, items: clone(demo.items), note: demo.note };
        }
        // 沒對到示範段落時做陽春切分（真後端由模型負責）
        var parts = String(text).split(/[，,。；;\n]+/).map(function (x) { return x.trim(); })
                     .filter(function (x) { return x.length > 1; });
        var items = parts.map(function (p, i) {
          var m = p.match(/(\d+)/);
          var amt = m ? Number(m[1]) : null;
          var income = /賺|收入|薪|給我|入帳/.test(p);
          return {
            seq: i + 1, span: p,
            date: D.meta.period + '-10',
            amount: amt,
            kind: income ? 'income' : 'expense',
            cat: income ? 'I04' : 'C08',
            merchant: '', note: '',
            conf: { date: .5, amount: amt ? .6 : 0, kind: .55, cat: .3 },
            missing: amt === null ? ['amount'] : [],
            hint: amt === null ? '這一句抓不到金額。' : ''
          };
        });
        return {
          raw: text, matched: false, items: items,
          note: 'mock 模式只做陽春切分。真後端由模型負責切分與抽欄位，並回傳每一欄的信心度。'
        };
      });
    },

    nlpConfirmBatch: function (items) {
      var s = load();
      return sleep(420).then(function () {
        var made = items.map(function (p, i) {
          return {
            id: 'N' + (Date.now() + i), user: s.me, date: p.date,
            amount: Number(p.amount), kind: p.kind, cat: p.cat,
            merchant: p.merchant || '', note: p.note || '',
            source: 'nlp', raw: p.span || '',
            parsed: { conf: (p.conf && p.conf.amount) || 0, catConf: (p.conf && p.conf.cat) || 0 }
          };
        });
        made.slice().reverse().forEach(function (t) { s.transactions.unshift(t); });
        save();
        return { created: made.length };
      });
    },

    /* 手動記帳不經過模型，走 POST /api/transactions，來源記成 manual。
       之前這裡借用 nlp/confirm，害手動填的資料被標成 AI 記帳，來源篩選也篩不到 */
    createTransaction: function (p) {
      var s = load();
      return sleep(260).then(function () {
        var t = {
          id: 'N' + Date.now(), user: s.me, date: p.date, amount: Number(p.amount),
          kind: p.kind, cat: p.cat, merchant: p.merchant || '',
          note: p.note || '', source: 'manual', raw: ''
        };
        s.transactions.unshift(t); save();
        return clone(t);
      });
    },

    nlpConfirm: function (parsed) {
      var s = load();
      return sleep(260).then(function () {
        var t = {
          id: 'N' + Date.now(), user: s.me, date: parsed.date, amount: Number(parsed.amount),
          kind: parsed.kind, cat: parsed.cat, merchant: parsed.merchant || '',
          note: parsed.note || '', source: 'nlp', raw: parsed.raw || '',
          parsed: { conf: parsed.conf || 0, catConf: parsed.catConf || 0 }
        };
        s.transactions.unshift(t); save();
        return clone(t);
      });
    },

    deleteTransaction: function (id) {
      var s = load();
      return sleep(180).then(function () {
        s.transactions = s.transactions.filter(function (t) { return t.id !== id; });
        save();
        return { deleted: id };
      });
    },

    setSavingsGoal: function (userId, goal) {
      var st = load(), D = global.DATA;
      return sleep(240).then(function () {
        var m = D.members.filter(function (x) { return x.id === userId; })[0];
        if (!m) throw new Error('not found: ' + userId);
        var v = Number(goal);
        if (isNaN(v) || v < 0) throw new Error('存款目標要是 0 以上的數字');
        st.goals[userId] = v;
        applyGoals(st.goals);
        save();
        return clone(m);
      });
    },

    budgets: function () {
      var s = load(), D = global.DATA;
      return sleep(LATENCY).then(function () {
        var vis = visibleUsers(s.me);
        return {
          budgets: D.budgets.filter(function (b) { return vis.indexOf(b.user) >= 0; })
            .map(function (b) {
              var c = D.categories.filter(function (x) { return x.id === b.cat; })[0];
              return Object.assign(clone(b), {
                userName: memberOf(b.user).name, catName: c.name, catColor: c.color,
                over: b.used > b.limit, pct: b.limit ? b.used / b.limit : 0
              });
            }).sort(function (a, b) { return b.pct - a.pct; })
        };
      });
    },

    advices: function (f) {
      f = f || {};
      var s = load(), D = global.DATA;
      return sleep(LATENCY).then(function () {
        var vis = visibleUsers(s.me);
        var rows = D.advices.filter(function (a) {
          if (a.scope === 'family') return true;
          return vis.indexOf(a.user) >= 0;
        });
        return {
          advices: rows.map(function (a) {
            return Object.assign(clone(a), {
              userName: a.user ? memberOf(a.user).name : null
            });
          }),
          rules: clone(D.adviceRules)
        };
      });
    },

    members: function () {
      var s = load(), D = global.DATA;
      return sleep(LATENCY).then(function () {
        return {
          me: s.me,
          members: clone(D.members),
          roles: clone(D.roles),
          guardianships: D.guardianships.map(function (g) {
            return Object.assign(clone(g), {
              guardianName: memberOf(g.guardian).name,
              wardName: memberOf(g.ward).name
            });
          }),
          permissions: clone(D.permissions)
        };
      });
    },


    categories: function () {
      return sleep(120).then(function () { return { categories: clone(global.DATA.categories) }; });
    },


    reset: function () {
      try { localStorage.removeItem(KEY); } catch (e) {}
      applyGoals(null);
      state = null;
      return sleep(120).then(function () { return { reset: true }; });
    }
  };

  /* ============================================================
     http 轉接器
     ============================================================ */
  function req(path, opt) {
    opt = opt || {};
    return fetch(BASE + path, {
      method: opt.method || 'GET',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: opt.body ? JSON.stringify(opt.body) : undefined
    }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status + ' ' + path);
      return r.status === 204 ? null : r.json();
    });
  }
  function qs(f) {
    var p = Object.keys(f || {})
      .filter(function (k) { var v = f[k]; return v !== undefined && v !== null && v !== '' && v !== 'all'; })
      .map(function (k) { return encodeURIComponent(k) + '=' + encodeURIComponent(f[k]); });
    return p.length ? '?' + p.join('&') : '';
  }

  var http = {
    me:                function ()      { return req('/api/auth/me'); },
    /* ⚠️ 後端沒有這支，也絕對不可以實作。
       讓任何人任意切換身分等於把整套權限系統作廢。
       接上真後端之後，「切換身分」這個鈕要換成正常的登入登出。 */
    switchUser:        function (id)    { return Promise.reject(new Error('真後端不提供切換身分，請改用登入')); },
    summary:           function (f)     { return req('/api/summary' + qs(f)); },
    transactions:      function (f)     { return req('/api/transactions' + qs(f)); },
    nlpParse:          function (t)     { return req('/api/nlp/parse', { method: 'POST', body: { text: t } }); },
    nlpParseBatch:     function (t)     { return req('/api/nlp/parse-batch', { method: 'POST', body: { text: t } }); },
    nlpConfirm:        function (p)     { return req('/api/nlp/confirm', { method: 'POST', body: p }); },
    nlpConfirmBatch:   function (i)     { return req('/api/nlp/confirm-batch', { method: 'POST', body: { items: i } }); },
    createTransaction: function (p)     { return req('/api/transactions', { method: 'POST', body: p }); },
    deleteTransaction: function (id)    { return req('/api/transactions/' + encodeURIComponent(id), { method: 'DELETE' }); },
    budgets:           function ()      { return req('/api/budgets'); },
    setSavingsGoal:    function (u, g)  { return req('/api/savings-goal', { method: 'PUT', body: { userId: u, goal: g } }); },
    advices:           function (f)     { return req('/api/advices' + qs(f)); },
    members:           function ()      { return req('/api/family'); },
    categories:        function ()      { return req('/api/categories'); },
    reset:             function ()      { return Promise.resolve({ reset: false, note: '真後端不提供重置' }); }
  };

  var impl = MODE === 'http' ? http : mock;

  global.API = {
    mode: MODE, base: BASE,
    me:                function ()     { return impl.me(); },
    switchUser:        function (i)    { return impl.switchUser(i); },
    summary:           function (f)    { return impl.summary(f); },
    transactions:      function (f)    { return impl.transactions(f); },
    nlpParse:          function (t)    { return impl.nlpParse(t); },
    nlpParseBatch:     function (t)    { return impl.nlpParseBatch(t); },
    nlpConfirm:        function (p)    { return impl.nlpConfirm(p); },
    nlpConfirmBatch:   function (i)    { return impl.nlpConfirmBatch(i); },
    createTransaction: function (p)    { return impl.createTransaction(p); },
    deleteTransaction: function (i)    { return impl.deleteTransaction(i); },
    budgets:           function ()     { return impl.budgets(); },
    setSavingsGoal:    function (u, g) { return impl.setSavingsGoal(u, g); },
    advices:           function (f)    { return impl.advices(f); },
    members:           function ()     { return impl.members(); },
    categories:        function ()     { return impl.categories(); },
    reset:             function ()     { return impl.reset(); }
  };
})(window);
