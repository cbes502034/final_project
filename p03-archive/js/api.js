/* ============================================================
   api.js — 前端唯一的資料入口
   ------------------------------------------------------------
   畫面程式碼一律只呼叫 API.xxx()，永遠不要直接讀 window.DATA。

   要接真後端，只要改 index.html 的

       <meta name="api-base" content="">

   填上後端網址（例如 http://localhost:8000），整個前端就會改打真 API，
   畫面程式碼一行都不用改。

   兩個轉接器：
     mockAdapter — 讀 js/data.js，寫入存在 localStorage，附帶假的網路延遲
     httpAdapter — fetch 真後端

   ------------------------------------------------------------
   後端契約（後端照這張表做即可）

   GET    /api/shift                  本班次統計 + 近 8 班次趨勢
   GET    /api/campaigns              收斂後群組（可帶 verdict / status / q）
   GET    /api/campaigns/{id}         單一群組（含成員、指標、判定理由）
   PATCH  /api/campaigns/{id}         處置 { status?, action? }
   POST   /api/campaigns/bulk         批次處置 { ids: [], patch: {} }
   GET    /api/dedup                  三層收斂各收掉多少
   GET    /api/tactics                話術體系（六類）
   GET    /api/annotation             標註進度與一致率
   GET    /api/eval                   模型評測（base vs fine-tuned）
   GET    /api/schema                 資料表結構與關聯（ER 圖用）
   POST   /api/ingest                 上傳 .eml 進行分析（Demo 用）
   ============================================================ */
(function (global) {
  'use strict';

  var BASE = (function () {
    var el = document.querySelector('meta[name="api-base"]');
    return el && el.content ? el.content.trim().replace(/\/$/, '') : '';
  })();

  var MODE = BASE ? 'http' : 'mock';
  var LATENCY = 240;                 // 模擬網路延遲，讓載入狀態是真的看得到的
  var KEY = 'phishtriage.state.v1';

  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function clone(x) { return JSON.parse(JSON.stringify(x)); }

  /* ---------- mock 模式下的「資料庫」 ---------- */
  var state = null;

  function load() {
    if (state) return state;
    var base = { campaigns: clone(global.DATA.campaigns) };
    try {
      var saved = JSON.parse(localStorage.getItem(KEY) || 'null');
      if (saved && saved.campaigns) {
        base.campaigns.forEach(function (c) {
          var s = saved.campaigns[c.id];
          if (s) { c.status = s.status; c.verdict = s.verdict; }
        });
      }
    } catch (e) { /* localStorage 不可用就當作沒存過 */ }
    state = base;
    return state;
  }

  function save() {
    try {
      var m = {};
      state.campaigns.forEach(function (c) { m[c.id] = { status: c.status, verdict: c.verdict }; });
      localStorage.setItem(KEY, JSON.stringify({ campaigns: m }));
    } catch (e) { /* 無痕視窗等情況，靜默略過 */ }
  }

  /* ============================================================
     mock 轉接器
     ============================================================ */
  var mock = {

    shift: function () {
      var s = load(), D = global.DATA;
      return sleep(LATENCY).then(function () {
        var open = s.campaigns.filter(function (c) { return c.status === 'open'; });
        return {
          meta: clone(D.meta),
          shift: clone(D.shift),
          trend: clone(D.trend),
          open: open.length,
          openPhishing: open.filter(function (c) { return c.verdict === 'phishing'; }).length,
          mix: ['phishing', 'spam', 'benign'].map(function (v) {
            var cs = s.campaigns.filter(function (c) { return c.verdict === v; });
            return {
              verdict: v,
              cards: cs.length,
              reports: cs.reduce(function (n, c) { return n + c.reports; }, 0)
            };
          }),
          topRisk: clone(s.campaigns.filter(function (c) {
            return c.verdict === 'phishing' && c.status === 'open';
          }).sort(function (a, b) { return a.priority - b.priority; })[0] || null)
        };
      });
    },

    campaigns: function (f) {
      f = f || {};
      var s = load();
      return sleep(LATENCY).then(function () {
        var rows = s.campaigns.filter(function (c) {
          if (f.verdict && f.verdict !== 'all' && c.verdict !== f.verdict) return false;
          if (f.status && f.status !== 'all' && c.status !== f.status) return false;
          if (f.q) {
            var hay = (c.id + ' ' + c.name + ' ' + c.subject + ' ' + c.from).toLowerCase();
            if (hay.indexOf(f.q.toLowerCase()) < 0) return false;
          }
          return true;
        });
        var order = { phishing: 0, spam: 1, benign: 2 };
        rows.sort(function (a, b) {
          if (f.sort === 'reports') return b.reports - a.reports;
          if (order[a.verdict] !== order[b.verdict]) return order[a.verdict] - order[b.verdict];
          return a.priority - b.priority;
        });
        return { campaigns: clone(rows), total: s.campaigns.length };
      });
    },

    campaign: function (id) {
      var s = load();
      return sleep(180).then(function () {
        var c = s.campaigns.filter(function (x) { return x.id === id; })[0];
        if (!c) throw new Error('not found: ' + id);
        return {
          campaign: clone(c),
          tactics: clone(global.DATA.tactics.filter(function (t) {
            return c.tactics.indexOf(t.id) >= 0;
          }))
        };
      });
    },

    patchCampaign: function (id, patch) {
      var s = load();
      return sleep(160).then(function () {
        var c = s.campaigns.filter(function (x) { return x.id === id; })[0];
        if (!c) throw new Error('not found: ' + id);
        Object.keys(patch).forEach(function (k) { c[k] = patch[k]; });
        save();
        return clone(c);
      });
    },

    bulkCampaign: function (ids, patch) {
      var s = load();
      return sleep(220).then(function () {
        var n = 0;
        s.campaigns.forEach(function (c) {
          if (ids.indexOf(c.id) >= 0) {
            Object.keys(patch).forEach(function (k) { c[k] = patch[k]; });
            n++;
          }
        });
        save();
        return { updated: n };
      });
    },

    dedup: function () {
      return sleep(LATENCY).then(function () {
        return { dedup: clone(global.DATA.dedup), shift: clone(global.DATA.shift) };
      });
    },

    tactics: function () {
      return sleep(LATENCY).then(function () {
        var s = load();
        return {
          tactics: global.DATA.tactics.map(function (t) {
            var cs = s.campaigns.filter(function (c) { return c.tactics.indexOf(t.id) >= 0; });
            return Object.assign(clone(t), {
              cards: cs.length,
              reports: cs.reduce(function (n, c) { return n + c.reports; }, 0)
            });
          }),
          annotation: clone(global.DATA.annotation)
        };
      });
    },

    evaluation: function () {
      return sleep(LATENCY).then(function () { return { eval: clone(global.DATA.eval) }; });
    },

    schema: function () {
      return sleep(LATENCY).then(function () {
        return { schema: clone(global.DATA.schema), relations: clone(global.DATA.relations) };
      });
    },

    ingest: function () {
      // 真後端要解析 .eml、去識別化、抽指標、跑收斂；這裡只是示意
      return sleep(1600).then(function () {
        return { ok: true, note: 'mock 模式沒有真的解析郵件' };
      });
    },

    reset: function () {
      try { localStorage.removeItem(KEY); } catch (e) {}
      state = null;
      return sleep(120).then(function () { return { reset: true }; });
    }
  };

  /* ============================================================
     http 轉接器 — 後端做好之後走這條
     ============================================================ */
  function req(path, opt) {
    opt = opt || {};
    return fetch(BASE + path, {
      method: opt.method || 'GET',
      headers: { 'Content-Type': 'application/json' },
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
    shift:          function ()        { return req('/api/shift'); },
    campaigns:      function (f)       { return req('/api/campaigns' + qs(f)); },
    campaign:       function (id)      { return req('/api/campaigns/' + encodeURIComponent(id)); },
    patchCampaign:  function (id, p)   { return req('/api/campaigns/' + encodeURIComponent(id), { method: 'PATCH', body: p }); },
    bulkCampaign:   function (ids, p)  { return req('/api/campaigns/bulk', { method: 'POST', body: { ids: ids, patch: p } }); },
    dedup:          function ()        { return req('/api/dedup'); },
    tactics:        function ()        { return req('/api/tactics'); },
    evaluation:     function ()        { return req('/api/eval'); },
    schema:         function ()        { return req('/api/schema'); },
    ingest:         function ()        { return req('/api/ingest', { method: 'POST' }); },
    reset:          function ()        { return Promise.resolve({ reset: false, note: '真後端不提供重置' }); }
  };

  var impl = MODE === 'http' ? http : mock;

  global.API = {
    mode: MODE,
    base: BASE,
    shift:          function ()       { return impl.shift(); },
    campaigns:      function (f)      { return impl.campaigns(f); },
    campaign:       function (i)      { return impl.campaign(i); },
    patchCampaign:  function (i, p)   { return impl.patchCampaign(i, p); },
    bulkCampaign:   function (i, p)   { return impl.bulkCampaign(i, p); },
    dedup:          function ()       { return impl.dedup(); },
    tactics:        function ()       { return impl.tactics(); },
    evaluation:     function ()       { return impl.evaluation(); },
    schema:         function ()       { return impl.schema(); },
    ingest:         function ()       { return impl.ingest(); },
    reset:          function ()       { return impl.reset(); }
  };
})(window);
