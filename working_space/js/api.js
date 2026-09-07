/* ============================================================
   api.js — 前端唯一的資料入口
   ------------------------------------------------------------
   畫面程式碼一律只呼叫 API.xxx()，永遠不要直接讀 window.DATA。
   這樣後端做好之後，只要把 index.html 的

       <meta name="api-base" content="">

   填上後端網址（例如 http://localhost:8000），整個前端就會改打真 API，
   畫面程式碼一行都不用改。

   兩個轉接器：
     mockAdapter — 讀 js/data.js，寫入存在 localStorage，附帶假的網路延遲
     httpAdapter — fetch 真後端

   每個方法上面都標了對應的後端路由，後端照著做即可。
   所有方法都回傳 Promise。
   ============================================================ */
(function (global) {
  'use strict';

  var BASE = (function () {
    var el = document.querySelector('meta[name="api-base"]');
    return el && el.content ? el.content.trim().replace(/\/$/, '') : '';
  })();

  var MODE = BASE ? 'http' : 'mock';
  var LATENCY = 260;                 // 模擬網路延遲，讓載入狀態是真的看得到的
  var STORE_KEY = 'vulnscope.state.v1';

  /* ============================================================
     後端契約
     ------------------------------------------------------------
     GET    /api/summary                     總覽數字 + 本週統計 + 近 14 天趨勢
     GET    /api/queue                       修補待辦（可帶 status / owner / sev / q）
     PATCH  /api/queue/{cve}                 更新單筆待辦 { status?, owner? }
     POST   /api/queue/bulk                  批次更新 { cves: [], patch: {} }
     GET    /api/advisories                  情資清單（可帶 matched / sev / q）
     GET    /api/advisories/{cve}            單筆情資（含抽取欄位與 CPE 比對）
     GET    /api/assets                      資產清單
     POST   /api/assets                      新增資產
     PATCH  /api/assets/{id}                 修改資產
     DELETE /api/assets/{id}                 刪除資產
     GET    /api/trace                       最近一次工具呼叫軌跡
     GET    /api/quota                       介接額度
     POST   /api/sync                        觸發一次 NVD 同步
     ============================================================ */

  function sleep(ms) {
    return new Promise(function (r) { setTimeout(r, ms); });
  }
  function clone(x) { return JSON.parse(JSON.stringify(x)); }

  /* ---------- 本機狀態：mock 模式下的「資料庫」 ---------- */
  var state = null;

  function loadState() {
    if (state) return state;
    var base = {
      queue: clone(global.DATA.queue),
      assets: clone(global.DATA.assets)
    };
    try {
      var saved = JSON.parse(localStorage.getItem(STORE_KEY) || 'null');
      if (saved && saved.queue) {
        // 只還原使用者改過的欄位，其餘仍以 data.js 為準
        base.queue.forEach(function (q) {
          var s = saved.queue[q.cve];
          if (s) { q.status = s.status; q.owner = s.owner; }
        });
        if (saved.assets) base.assets = saved.assets;
      }
    } catch (e) { /* localStorage 不可用就當作沒存過 */ }
    state = base;
    return state;
  }

  function saveState() {
    try {
      var q = {};
      state.queue.forEach(function (x) { q[x.cve] = { status: x.status, owner: x.owner }; });
      localStorage.setItem(STORE_KEY, JSON.stringify({ queue: q, assets: state.assets }));
    } catch (e) { /* 無痕視窗等情況，靜默略過 */ }
  }

  /* ============================================================
     mock 轉接器
     ============================================================ */
  var mockAdapter = {

    summary: function () {
      var s = loadState();
      var D = global.DATA;
      var all = D.advisories.length + D.unmatched.length;
      var open = s.queue.filter(function (q) { return q.status === 'open'; });
      return sleep(LATENCY).then(function () {
        return {
          batch: all,
          relevant: D.advisories.length,
          irrelevant: D.unmatched.length,
          affected: open.reduce(function (n, q) { return n + q.count; }, 0),
          vague: s.assets.filter(function (a) { return a.clarity === 'vague'; }).length,
          open: open.length,
          overdue: open.filter(function (q) { return q.left <= 0; }).length,
          urgent: open.filter(function (q) { return q.left > 0 && q.left <= 2; }).length,
          topUnmatched: D.unmatched[0] || null,
          sevMix: ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(function (k) {
            return { sev: k, n: s.queue.filter(function (q) { return q.sev === k; }).length };
          }),
          weekly: clone(D.weekly),
          trend: clone(D.trend),
          synced: D.meta.synced,
          org: D.meta.org
        };
      });
    },

    queue: function (f) {
      f = f || {};
      var s = loadState();
      return sleep(LATENCY).then(function () {
        var rows = s.queue.filter(function (q) {
          if (f.status && f.status !== 'all' && q.status !== f.status) return false;
          if (f.sev && f.sev !== 'all' && q.sev !== f.sev) return false;
          if (f.owner && f.owner !== 'all' && q.owner !== f.owner) return false;
          if (f.q) {
            var hay = (q.cve + ' ' + q.title + ' ' + q.action).toLowerCase();
            if (hay.indexOf(f.q.toLowerCase()) < 0) return false;
          }
          return true;
        });
        var dir = f.desc === false ? 1 : -1;
        var key = f.sort || 'priority';
        rows.sort(function (a, b) {
          if (key === 'sla') return (a.left - b.left) * -dir;
          if (key === 'cvss') return (a.score - b.score) * dir;
          return (a.priority - b.priority) * dir;
        });
        return { queue: clone(rows), total: s.queue.length };
      });
    },

    patchQueue: function (cve, patch) {
      var s = loadState();
      return sleep(180).then(function () {
        var row = s.queue.filter(function (q) { return q.cve === cve; })[0];
        if (!row) throw new Error('not found: ' + cve);
        Object.keys(patch).forEach(function (k) { row[k] = patch[k]; });
        saveState();
        return clone(row);
      });
    },

    bulkQueue: function (cves, patch) {
      var s = loadState();
      return sleep(240).then(function () {
        var n = 0;
        s.queue.forEach(function (q) {
          if (cves.indexOf(q.cve) >= 0) {
            Object.keys(patch).forEach(function (k) { q[k] = patch[k]; });
            n++;
          }
        });
        saveState();
        return { updated: n };
      });
    },

    advisories: function (f) {
      f = f || {};
      var D = global.DATA;
      return sleep(LATENCY).then(function () {
        var rows = D.advisories.concat(D.unmatched);
        rows = rows.filter(function (a) {
          if (f.matched === 'hit' && !a.matched) return false;
          if (f.matched === 'miss' && a.matched) return false;
          if (f.sev && f.sev !== 'all' && a.sev !== f.sev) return false;
          if (f.q) {
            var hay = (a.id + ' ' + (a.product || '') + ' ' +
                       (a.extracted ? a.extracted.vendor + ' ' + a.extracted.product : '')).toLowerCase();
            if (hay.indexOf(f.q.toLowerCase()) < 0) return false;
          }
          return true;
        });
        rows.sort(function (a, b) { return b.score - a.score; });
        return { advisories: clone(rows) };
      });
    },

    advisory: function (cve) {
      var D = global.DATA;
      return sleep(200).then(function () {
        var a = D.advisories.filter(function (x) { return x.id === cve; })[0];
        if (!a) throw new Error('not found: ' + cve);
        var asset = loadState().assets.filter(function (x) { return x.id === a.matched; })[0];
        return { advisory: clone(a), asset: clone(asset) };
      });
    },

    assets: function (f) {
      f = f || {};
      var s = loadState();
      return sleep(LATENCY).then(function () {
        var rows = s.assets.filter(function (a) {
          if (f.clarity && f.clarity !== 'all' && a.clarity !== f.clarity) return false;
          if (f.q) {
            var hay = (a.name + ' ' + a.vendor + ' ' + a.product + ' ' + a.tag).toLowerCase();
            if (hay.indexOf(f.q.toLowerCase()) < 0) return false;
          }
          return true;
        });
        return { assets: clone(rows), total: s.assets.length };
      });
    },

    createAsset: function (body) {
      var s = loadState();
      return sleep(240).then(function () {
        var id = 'A' + String(s.assets.length + 1).padStart(2, '0');
        var a = Object.assign({
          id: id, name: '', vendor: '', product: '', version: '', cpe: '',
          count: 1, exposure: '內網', owner: '資訊室', tag: '未分類', clarity: 'ok'
        }, body, { id: id });
        // 廠牌／產品／版本任一缺漏就組不出 CPE，標成待補
        if (!a.vendor || !a.product || !a.version) {
          a.clarity = 'vague';
          a.cpe = '';
          a.hint = a.hint || '缺少廠牌、產品或版本，組不出 CPE，因此無法比對。';
        } else {
          a.clarity = 'ok';
          a.cpe = 'cpe:2.3:a:' + a.vendor + ':' + a.product + ':' + a.version + ':*:*:*:*:*:*:*';
          delete a.hint;
        }
        s.assets.push(a);
        saveState();
        return clone(a);
      });
    },

    patchAsset: function (id, patch) {
      var s = loadState();
      return sleep(200).then(function () {
        var a = s.assets.filter(function (x) { return x.id === id; })[0];
        if (!a) throw new Error('not found: ' + id);
        Object.keys(patch).forEach(function (k) { a[k] = patch[k]; });
        if (a.vendor && a.product && a.version) {
          a.clarity = 'ok';
          a.cpe = 'cpe:2.3:a:' + a.vendor + ':' + a.product + ':' + a.version + ':*:*:*:*:*:*:*';
          delete a.hint;
        }
        saveState();
        return clone(a);
      });
    },

    deleteAsset: function (id) {
      var s = loadState();
      return sleep(200).then(function () {
        s.assets = s.assets.filter(function (x) { return x.id !== id; });
        saveState();
        return { deleted: id };
      });
    },

    trace: function () {
      return sleep(LATENCY).then(function () { return { trace: clone(global.DATA.trace) }; });
    },

    quota: function () {
      return sleep(120).then(function () { return clone(global.DATA.meta.quota); });
    },

    sync: function () {
      // 真後端要打 NVD、寫快取、重跑比對；這裡只是把時間戳往前推
      return sleep(1400).then(function () {
        return { started: true, synced: global.DATA.meta.synced, note: 'mock 模式沒有真的同步' };
      });
    },

    reset: function () {
      try { localStorage.removeItem(STORE_KEY); } catch (e) {}
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
      .filter(function (k) { return f[k] !== undefined && f[k] !== null && f[k] !== '' && f[k] !== 'all'; })
      .map(function (k) { return encodeURIComponent(k) + '=' + encodeURIComponent(f[k]); });
    return p.length ? '?' + p.join('&') : '';
  }

  var httpAdapter = {
    summary:     function ()          { return req('/api/summary'); },
    queue:       function (f)         { return req('/api/queue' + qs(f)); },
    patchQueue:  function (cve, p)    { return req('/api/queue/' + encodeURIComponent(cve), { method: 'PATCH', body: p }); },
    bulkQueue:   function (cves, p)   { return req('/api/queue/bulk', { method: 'POST', body: { cves: cves, patch: p } }); },
    advisories:  function (f)         { return req('/api/advisories' + qs(f)); },
    advisory:    function (cve)       { return req('/api/advisories/' + encodeURIComponent(cve)); },
    assets:      function (f)         { return req('/api/assets' + qs(f)); },
    createAsset: function (b)         { return req('/api/assets', { method: 'POST', body: b }); },
    patchAsset:  function (id, p)     { return req('/api/assets/' + encodeURIComponent(id), { method: 'PATCH', body: p }); },
    deleteAsset: function (id)        { return req('/api/assets/' + encodeURIComponent(id), { method: 'DELETE' }); },
    trace:       function ()          { return req('/api/trace'); },
    quota:       function ()          { return req('/api/quota'); },
    sync:        function ()          { return req('/api/sync', { method: 'POST' }); },
    reset:       function ()          { return Promise.resolve({ reset: false, note: '真後端不提供重置' }); }
  };

  var impl = MODE === 'http' ? httpAdapter : mockAdapter;

  global.API = {
    mode: MODE,
    base: BASE,
    summary:     function (f)      { return impl.summary(f); },
    queue:       function (f)      { return impl.queue(f); },
    patchQueue:  function (c, p)   { return impl.patchQueue(c, p); },
    bulkQueue:   function (c, p)   { return impl.bulkQueue(c, p); },
    advisories:  function (f)      { return impl.advisories(f); },
    advisory:    function (c)      { return impl.advisory(c); },
    assets:      function (f)      { return impl.assets(f); },
    createAsset: function (b)      { return impl.createAsset(b); },
    patchAsset:  function (i, p)   { return impl.patchAsset(i, p); },
    deleteAsset: function (i)      { return impl.deleteAsset(i); },
    trace:       function ()       { return impl.trace(); },
    quota:       function ()       { return impl.quota(); },
    sync:        function ()       { return impl.sync(); },
    reset:       function ()       { return impl.reset(); }
  };
})(window);
