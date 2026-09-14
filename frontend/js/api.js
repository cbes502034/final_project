/* ============================================================
   api.js — 前端唯一的資料入口
   ------------------------------------------------------------
   畫面程式碼一律只呼叫 API.xxx()，永遠不要直接讀 window.DATA。
   要接真後端，只要改 index.html 的 <meta name="api-base">。

   ------------------------------------------------------------
   後端契約

   身分
   POST   /api/auth/register          註冊（名字、email、密碼。存款目標不在這裡，註冊完的個人化設定再設）
   POST   /api/auth/password-reset    忘記密碼：寄重設信（有沒有這個帳號都回同一句）
   POST   /api/auth/password-reset/confirm  用信裡的 token 設新密碼（一次性，並登出所有裝置）
   POST   /api/auth/login             登入 → { accessToken, refreshToken, user }
   POST   /api/auth/refresh           換新 token
   POST   /api/auth/logout            登出（撤銷 refresh token）
   POST   /api/auth/refresh           access token 過期時換新的
   PATCH  /api/auth/me                改個人資料（displayName / birthYear / theme / onboarded）
   PUT    /api/auth/me/avatar         上傳大頭貼（body: { image: dataUri }）
   DELETE /api/auth/me/avatar         移除大頭貼
   GET    /api/auth/me/finance        我的理財習慣（拿去當建議的背景）
   PUT    /api/auth/me/finance        改理財習慣
   PATCH  /api/auth/password          改密碼
   POST   /api/auth/verify-password   重大操作前再確認一次（不發新 token）
   GET    /api/admin/users             平台管理員：帳號清單（⚠️ 不含任何金額）
   POST   /api/admin/users/{id}/suspend    停權（body: { reason }）
   DELETE /api/admin/users/{id}/suspend    解除停權
   GET    /api/audit                   稽核紀錄
   GET    /api/auth/me                目前登入者 + 家庭角色

   家庭與權限
   GET    /api/family                 家庭資訊與成員清單（沒有家庭時 family 為 null）
   POST   /api/family                 建立家庭，建立的人成為家長（body: { name }）
   POST   /api/family/invite          產生邀請碼（家長；body: { role }，只能用一次、七天過期）
   POST   /api/family/join            用邀請碼加入（body: { code }）
   GET    /api/family/lookup          用完整 email 找人（家長；只回名字、頭像、能不能邀請）
   GET    /api/family/invites         我收到的邀請 ＋ 我們家送出去還沒回覆的
   POST   /api/family/invites         用帳號邀請（家長；body: { userId, role }）
   POST   /api/family/invites/{id}/accept   接受邀請
   DELETE /api/family/members/{id}    家長把子女移出家庭；{id} 寫 me 就是自己退出
   DELETE /api/family/invites/{id}   被邀請的人婉拒，或家長取消
   PATCH  /api/family/members/{id}    改角色（家長）
   DELETE /api/family/members/{id}    移除成員（家長）
   GET    /api/guardianships          監管關係（雙方都看得到）
   POST   /api/guardianships          建立監管（家長）
   DELETE /api/guardianships/{id}     解除監管（家長）

   記帳
   GET    /api/transactions           明細（可帶 user / from / to / cat / kind / q）
   POST   /api/transactions           新增（手動記帳走這支，不經過模型）
   PATCH  /api/transactions/{id}      修改（只送要改的欄位；結算過的帳本裡的不能改）
   DELETE /api/transactions/{id}      刪除一筆
   DELETE /api/transactions?ids=a,b   一次刪多筆（全部成功或全部不動）
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
   監管通知
   GET    /api/notifications          通知清單（帶 since 只拿新的）
   PATCH  /api/notifications/{id}     標記單則已讀
   PATCH  /api/notifications          整批已讀（帶 readUntil）

   群組（帳本）
   GET    /api/groups                 我加入的群組
   POST   /api/groups                 建立
   PATCH  /api/groups/{gid}           改名稱／圖示／顏色
   DELETE /api/groups/{gid}           封存（不刪除）；?permanent=true 移除已結算的活動帳本（紀錄保留）
   POST   /api/groups/{gid}/members   把家人加進這本帳
   DELETE /api/groups/{gid}/members/{uid}  移出

   零用金
   GET    /api/allowances            我每月給每個被監管者多少
   PUT    /api/allowance             設定 { wardId, amount }

   階段性提醒
   GET    /api/savings-goals          整體 + 各群組的每月存款目標
   GET    /api/alerts                 我設的百分比門檻
   POST   /api/alerts                 新增門檻
   PATCH  /api/alerts/{aid}           改百分比或開關
   DELETE /api/alerts/{aid}           刪掉

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
  /* v2：拿掉假資料之後換新的鑰匙。舊的 v1 裡是示範帳號的資料（U1、U2…），
     新註冊的人會拿到一樣的 id，不換的話會把舊示範紀錄認成自己的。 */
  var KEY = 'fambudget.state.v2';

  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  /* 新資料的編號：毫秒時間戳，但保證遞增。
     同一毫秒建兩筆（段落記帳一次確認好幾筆、連點兩下）用 Date.now() 會撞號，
     撞號的兩筆改一筆會兩筆一起變、刪一筆會兩筆一起不見。 */
  var lastStamp = 0;
  function stampId(prefix) {
    var n = Date.now();
    lastStamp = n > lastStamp ? n : lastStamp + 1;
    return prefix + lastStamp;
  }
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
      me: null,                                   // 目前登入者（還沒登入是 null）
      transactions: clone(global.DATA.transactions),
      budgets: clone(global.DATA.budgets),
      goals: {},
      readNotify: [],
      auth: { loggedIn: false },  // 一打開是登出狀態：沒有範例帳號，要自己註冊或登入
      patch: {},                  // 個人資料的改動（名字、大頭貼）
      newUsers: []                // 註冊進來的人
    };
    try {
      var saved = JSON.parse(localStorage.getItem(KEY) || 'null');
      if (saved) {
        if (saved.me) base.me = saved.me;
        if (saved.budgets) base.budgets = saved.budgets;
        if (saved.extra) base.transactions = saved.extra.concat(base.transactions);
        if (saved.goals) base.goals = saved.goals;
        if (saved.readNotify) base.readNotify = saved.readNotify;
        if (saved.auth) base.auth = saved.auth;
        if (saved.patch) base.patch = saved.patch;
        if (saved.newUsers) base.newUsers = saved.newUsers;
        /* ⚠️ 新增一種要存的狀態，這裡跟 save() 兩邊都要加。
           suspended／audit 漏過一次：停權在同一頁看起來有效，
           重新整理之後就消失——被停權的人重新整理一下就能登入。 */
        ['newGroups', 'groupPatch', 'joined', 'left', 'archived', 'settled', 'removed', 'txPatch', 'txGone', 'resets',
         'goalPatch', 'allowancePatch', 'newAlerts', 'alertPatch', 'alertGone',
         'suspended', 'audit', 'newFamilies', 'memberships', 'invites', 'codes', 'endedGuardians',
         'passwords', 'advices', 'customCategories', 'newGuardians', 'dissolved'].forEach(function (k) {
          if (saved[k]) base[k] = saved[k];
        });
      }
    } catch (e) {}
    applyTxEdits(base);
    /* ⚠️ 先把註冊進來的人補回 DATA.members，再套存款目標。
       順序反過來的話，新帳號在套目標的當下還不存在——個人化設定填的目標，重新整理就變回 0。 */
    applyUsers(base.newUsers);
    applyGoals(base.goals);
    applyPatch(base.patch);
    applyMemberships(base.memberships);
    applyEndedGuardians(base.endedGuardians);
    applyNewGuardians(base.newGuardians);
    state = base;
    return state;
  }
  function save() {
    try {
      var extra = state.transactions.filter(function (t) { return t.id.indexOf('N') === 0; });
      localStorage.setItem(KEY, JSON.stringify({
        me: state.me, extra: extra, goals: state.goals || {},
        readNotify: state.readNotify || [],
        auth: state.auth || { loggedIn: false },
        budgets: state.budgets || [],
        passwords: state.passwords || {},
        advices: state.advices || [],
        customCategories: state.customCategories || [],
        newGuardians: state.newGuardians || [],
        dissolved: state.dissolved || [],
        patch: state.patch || {},
        newUsers: state.newUsers || [],
        newGroups: state.newGroups || [],
        groupPatch: state.groupPatch || {},
        joined: state.joined || [],
        left: state.left || [],
        archived: state.archived || [],
        settled: state.settled || [],
        removed: state.removed || [],
        txPatch: state.txPatch || {},
        txGone: state.txGone || [],
        resets: state.resets || [],
        goalPatch: state.goalPatch || [],
        allowancePatch: state.allowancePatch || [],
        newAlerts: state.newAlerts || [],
        alertPatch: state.alertPatch || {},
        alertGone: state.alertGone || [],
        suspended: state.suspended || {},
        audit: state.audit || [],
        newFamilies: state.newFamilies || [],
        memberships: state.memberships || {},
        invites: state.invites || [],
        codes: state.codes || [],
        endedGuardians: state.endedGuardians || []
      }));
    } catch (e) {}
  }

  /* 示範紀錄（T 開頭）的修改與刪除蓋回去。
     ⚠️ save() 只存新記的（N 開頭）。以前刪掉一筆示範紀錄，重新整理它就回來了——
     看起來刪成功，其實沒有。改和刪都要各自記下來。 */
  function applyTxEdits(st) {
    var gone = st.txGone || [], patch = st.txPatch || {};
    st.transactions = st.transactions
      .filter(function (t) { return gone.indexOf(t.id) < 0; })
      .map(function (t) { return patch[t.id] ? Object.assign(t, patch[t.id]) : t; });
  }
  function dropTx(st, ids) {
    st.transactions = st.transactions.filter(function (x) { return ids.indexOf(x.id) < 0; });
    ids.forEach(function (id) {
      if (String(id).charAt(0) === 'N') return;
      st.txGone = st.txGone || [];
      if (st.txGone.indexOf(id) < 0) st.txGone.push(id);
      if (st.txPatch) delete st.txPatch[id];
    });
  }

  /* 註冊進來的人補回 DATA.members，不然重新整理就不見了 */
  function applyUsers(list) {
    (list || []).forEach(function (u) {
      if (!global.DATA.members.some(function (m) { return m.id === u.id; })) {
        global.DATA.members.push(clone(u));
      }
    });
  }
  /* 個人資料的改動蓋回去（名字、大頭貼） */
  function applyPatch(p) {
    Object.keys(p || {}).forEach(function (id) {
      var m = global.DATA.members.filter(function (x) { return x.id === id; })[0];
      if (m) Object.keys(p[id]).forEach(function (k) { m[k] = p[id][k]; });
    });
  }
  function patchOf(st, id) {
    st.patch = st.patch || {};
    st.patch[id] = st.patch[id] || {};
    return st.patch[id];
  }

  /* 同一天之內的先後：新記的 id 帶毫秒時間，種子資料是流水號 */
  function txOrder(t) {
    var n = Number(String(t.id).replace(/\D/g, '')) || 0;
    return n;
  }

  /* 今天：真實日期（本機時區）。示範資料在 data.js 載入時已經對齊到今天。
     ⚠️ 不要用 toISOString()——那是 UTC，台灣早上 8 點前會變成昨天。 */
  function todayStr() {
    return global.fbToday();
  }

  function notifyOf(gid, uid) {
    var rows = (global.DATA.groupMembers || []).concat(
      (state && state.joined) || []);
    var hit = rows.filter(function (m) {
      return m.group === gid && m.user === uid;
    });
    return hit.length ? !!hit[hit.length - 1].notify : false;
  }

  /* ⚠️ 每一支管理端路由的第一行都要呼叫它。
     真後端請用 toolkit/roles.py 的 require_platform()。 */
  function requirePlatform(s) {
    var me = memberOf(s.me);
    if (!me || !me.isPlatformAdmin) {
      var e = new Error('這個動作需要平台管理員權限');
      e.status = 403;
      throw e;
    }
  }

  /* ⚠️ 稽核時間要用當地時間。toISOString() 是 UTC，
     在台灣會比實際早 8 小時——下午三點停的權，紀錄上寫早上七點。
     稽核紀錄就是拿來對時間的，差 8 小時等於紀錄是錯的。
     真後端存 TIMESTAMPTZ，由前端依使用者時區顯示。 */
  function localStamp(d) {
    function p(n) { return (n < 10 ? '0' : '') + n; }
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) +
      ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
  }

  function pushAudit(s, action, target, note) {
    s.audit = (s.audit || []).concat([{
      id: 'A' + (2000 + (s.audit || []).length),
      actor: s.me, action: action, target: target,
      at: new Date().toISOString(), note: note
    }]);
  }

  /* 沒選過主題的人就是預設的米白。契約裡 user.theme 一定有值，前端不必自己補 */
  function withTheme(u) {
    if (u && !u.theme) u.theme = 'paper';
    /* 註冊後的個人化設定走完了沒。null = 還沒（登入後先帶去 #/setup）。
       種子帳號都是早就在用的人，當成走完了；新註冊的明確是 null。 */
    if (u && u.onboardedAt === undefined) u.onboardedAt = u.joined ? u.joined + ' 09:00' : null;
    return u;
  }

  function memberOf(id) {
    return global.DATA.members.filter(function (m) { return m.id === id; })[0];
  }

  /* ============================================================
     家庭

     一個人同時只屬於一個家庭（members[].familyId）。
     加入或建立家庭時，把「這個人現在在哪一家、是什麼身分」記在 memberships，
     重新整理之後蓋回 DATA.members。
     ============================================================ */
  function applyMemberships(map) {
    Object.keys(map || {}).forEach(function (id) {
      var m = memberOf(id);
      if (m) { m.familyId = map[id].familyId; m.role = map[id].role; }
    });
  }

  /* 結束的監管關係：從 DATA.guardianships 拿掉。
     ⚠️ 真後端是設 ended_at，不是刪列——稽核要看得到歷史。 */
  function applyEndedGuardians(list) {
    (list || []).forEach(function (e) {
      var g = global.DATA.guardianships;
      for (var i = g.length - 1; i >= 0; i--) {
        if (e.id ? gsId(g[i]) === e.id : (g[i].guardian === e.guardian && g[i].ward === e.ward)) g.splice(i, 1);
      }
    });
  }

  /* 這個瀏覽器建立的監管關係，重新整理之後補回 DATA.guardianships */
  function applyNewGuardians(list) {
    (list || []).forEach(function (g) {
      if (!global.DATA.guardianships.some(function (x) { return gsId(x) === g.id; })) {
        global.DATA.guardianships.push(clone(g));
      }
    });
  }

  /* 監管關係的 id。後端是自增主鍵；測試資料沒有 id，用「監管人-被監管人」代替 */
  function gsId(g) { return g.id || ('GS-' + g.guardian + '-' + g.ward); }

  /* 結束幾條監管關係。⚠️ 真後端是設 ended_at，不刪列——稽核要看得到歷史。
     零用金跟著監管關係，一起歸零。 */
  function endGuardians(s, rows) {
    rows.forEach(function (g) {
      var id = gsId(g);
      if ((s.newGuardians || []).some(function (x) { return x.id === id; })) {
        s.newGuardians = s.newGuardians.filter(function (x) { return x.id !== id; });
      } else {
        s.endedGuardians = (s.endedGuardians || []).concat([{ id: g.id || null, guardian: g.guardian, ward: g.ward }]);
      }
      s.allowancePatch = (s.allowancePatch || []).concat([{ payer: g.guardian, ward: g.ward, amount: 0 }]);
    });
    applyEndedGuardians(rows.map(function (g) { return { id: gsId(g) }; }));
    return rows.length;
  }

  /* 一個人離開家庭時要一起收掉的東西。
     ⚠️ **紀錄一筆都不刪**。收掉的是「還能互相看到」的那些關係：
       · 他當監管人、或他被監管的關係 → 結束（零用金跟著監管關係，一起結束）
       · 他開的帳本 → 家人移出；家人開的帳本 → 他移出
       · 他送出去還沒回覆的邀請 → 取消
     不收的話，人離開了，家人還是看得到他後來記的每一筆。 */
  function detachFromFamily(s, uid) {
    var m = memberOf(uid), famId = m.familyId;
    setMembership(s, uid, null, null);

    var ended = global.DATA.guardianships.filter(function (g) { return g.guardian === uid || g.ward === uid; });
    endGuardians(s, ended);

    var family = global.DATA.members.filter(function (x) { return x.familyId === famId; })
      .map(function (x) { return x.id; });
    allGroups(true).forEach(function (g) {
      var inside = memberIdsOf(g.id);
      var out = [];
      if (g.owner === uid) out = inside.filter(function (u) { return family.indexOf(u) >= 0; });
      else if (inside.indexOf(uid) >= 0 && family.indexOf(g.owner) >= 0) out = [uid];
      out.forEach(function (u) { s.left = (s.left || []).concat([{ group: g.id, user: u }]); });
    });

    (s.invites || []).forEach(function (i) {
      if (i.inviter === uid && i.status === 'pending') i.status = 'cancelled';
    });
    /* ⚠️ 他產生、還沒用過的邀請碼也要作廢。
       沒作廢的話：家長產生子女邀請碼 → 大家陸續離開 → 有人拿舊碼加入，
       變成一個只有子女、沒有家長的家，沒有人能邀請或管理。 */
    (s.codes || []).forEach(function (c) {
      if (c.createdBy === uid && c.status === 'pending') c.status = 'cancelled';
    });
    return { ended: ended.length };
  }

  /* 家裡還有沒有家長。沒有的話誰都不能再加入——真後端用 toolkit.family.require_has_parent() */
  function hasParent(familyId) {
    return global.DATA.members.some(function (x) { return x.familyId === familyId && x.role === 'parent'; });
  }

  function allFamilies() {
    var gone = (state && state.dissolved) || [];
    return (global.DATA.families || []).concat((state && state.newFamilies) || [])
      .filter(function (f) { return gone.indexOf(f.id) < 0; });
  }

  function familyById(id) {
    return allFamilies().filter(function (f) { return f.id === id; })[0] || null;
  }

  function familyOf(uid) {
    var m = memberOf(uid);
    return m && m.familyId ? familyById(m.familyId) : null;
  }

  function setMembership(s, uid, familyId, role) {
    var m = memberOf(uid);
    m.familyId = familyId; m.role = role;
    s.memberships = s.memberships || {};
    s.memberships[uid] = { familyId: familyId, role: role };
  }

  /* 同一個家庭的**家長**（含我自己）。我不是家長就是空的。
     ⚠️ 角色只打開「家長 ↔ 家長」這一條——家長看子女一樣要有監管關係，
        子女也不會因為角色看到任何人。後端用 toolkit/scope.py 的 co_parents()。 */
  function coParents(meId) {
    var me = memberOf(meId);
    if (!me || me.role !== 'parent' || !me.familyId) return [];
    return global.DATA.members
      .filter(function (m) { return m.familyId === me.familyId && m.role === 'parent'; })
      .map(function (m) { return m.id; });
  }

  function isParentOf(s, familyId) {
    var me = memberOf(s.me);
    return !!(me && me.role === 'parent' && me.familyId && me.familyId === familyId);
  }

  /* ⚠️ 不要叫 fail——http 轉接器裡已經有一個 fail(r)，
     同名的函式宣告後面那個會蓋掉前面的，錯誤訊息會變成「r.text is not a function」。 */
  function oops(msg, status) {
    var e = new Error(msg);
    if (status) e.status = status;
    return e;
  }

  var INVITE_DAYS = 7;

  /* mock 的密碼。⚠️ **這不是真的雜湊**，只是讓「打錯密碼會被擋」在瀏覽器裡也成立。
     真後端用 toolkit/passwords.py（bcrypt），而且密碼只存在伺服器。 */
  function pwHash(pw) {
    var h = 2166136261, str = 'fambudget:' + String(pw || '');
    for (var i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; }
    return 'mock$' + h.toString(16);
  }
  /* 沒有存過密碼的帳號（測試資料、更早註冊的）只檢查長度 */
  function checkPw(s, uid, pw) {
    var saved = (s.passwords || {})[uid];
    return saved ? saved === pwHash(pw) : String(pw || '').length >= 8;
  }

  /* 分類：系統預設 ＋ 我們家自訂的。⚠️ 別人家的自訂分類看不到 */
  function allCats(s) {
    var fam = (memberOf(s.me) || {}).familyId;
    return global.DATA.categories.map(function (c) { return Object.assign({ custom: false }, c); })
      .concat((s.customCategories || []).filter(function (c) { return fam && c.familyId === fam; }));
  }
  /* 查一個分類。紀錄可能是家人記的自訂分類，所以不限我們家 */
  function catOf(s, id) {
    return global.DATA.categories.concat(s.customCategories || []).filter(function (c) { return c.id === id; })[0] || null;
  }

  function money(n) { return Number(Math.round(n || 0)).toLocaleString('en-US'); }

  /* 往前或往後推幾個月：'2026-01' -1 → '2025-12' */
  function shiftMonth(ym, delta) {
    var t = (+ym.slice(0, 4)) * 12 + (+ym.slice(5, 7) - 1) + delta;
    return Math.floor(t / 12) + '-' + ((t % 12) < 9 ? '0' : '') + (t % 12 + 1);
  }

  /* 忘記密碼。跟 toolkit/password_reset.py 的 TOKEN_MINUTES／COOLDOWN_SECONDS／GENERIC_MESSAGE 一樣 */
  var RESET_MINUTES = 30;
  var RESET_COOLDOWN_SEC = 60;
  var RESET_MESSAGE = '如果這個 email 有註冊，重設密碼的信已經寄出，30 分鐘內有效。';
  var RESET_INVALID = '這個重設連結已經失效，請重新申請一次';

  /* 43 個字元、網址安全。⚠️ 用 crypto，不要用 Math.random——那猜得出來 */
  function randomToken() {
    var abc = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
    var buf = new Uint8Array(43), out = '';
    var c = global.crypto || (typeof crypto !== 'undefined' ? crypto : null);
    if (c && c.getRandomValues) c.getRandomValues(buf);
    else for (var i = 0; i < 43; i++) buf[i] = Math.floor(Math.random() * 256);
    for (var j = 0; j < 43; j++) out += abc.charAt(buf[j] % 64);
    return out;
  }
  var CODE_CHARS = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789';     // 拿掉 0/O、1/I/L

  /* ⚠️ mock 用 Math.random 就好；真後端要用 secrets（toolkit/family.py 的 new_code） */
  function newCode() {
    var raw = '';
    for (var i = 0; i < 8; i++) raw += CODE_CHARS.charAt(Math.floor(Math.random() * CODE_CHARS.length));
    return raw.slice(0, 4) + '-' + raw.slice(4);
  }

  function normCode(raw) { return String(raw || '').toUpperCase().replace(/[^A-Z0-9]/g, ''); }

  function daysLater(n) { return new Date(Date.now() + n * 86400000).toISOString(); }

  function expired(row) { return Date.parse(row.expiresAt) <= Date.now(); }
  /* 我看得到誰的資料：自己 ＋ 我監管的人。就這樣。
     ------------------------------------------------------------
     ⚠️ 角色不給可見範圍。家長也一樣——沒有被指派監管誰，
        就只看得到自己。可見範圍來自 guardianships 這張表，不是頭銜。

     ⚠️ 被監管的人看不到任何別人，包含監管他的人。
        監管是單向的：你看得到我，不代表我看得到你。

     （早期版本讓家裡權限最高的人直接看全家。改掉是因為「家裡的階級」和
       「可以看某個人的消費明細」是兩件事——後者要有明確的監管關係，
       這樣被監管的人才知道自己被誰看著。

       平台管理員更是完全看不到：他能停權，但讀不到任何一筆帳。） */
  /* 我看得到哪幾本帳：我有加入的群組。
     ⚠️ 這跟 visibleUsers 是**聯集**，不是交集——過一條就看得到。
     只做一道會漏：我監管的小孩在一個我沒加入的群組記帳，
     那筆不該出現在我的清單上。 */
  /* 某本帳裡有誰 */
  function memberIdsOf(gid) {
    var s = load();
    var left = (s.left || []);
    return global.DATA.groupMembers
      .filter(function (m) { return m.group === gid; })
      .map(function (m) { return m.user; })
      .concat((s.joined || []).filter(function (j) { return j.group === gid; })
        .map(function (j) { return j.user; }))
      .filter(function (u, i, a) { return a.indexOf(u) === i; })
      .filter(function (u) {
        return !left.some(function (l) { return l.group === gid && l.user === u; });
      });
  }

  function visibleGroups(meId, withArchived) {
    var s = load();
    var extra = (s.newGroups || []).map(function (g) { return g.id; });
    return global.DATA.groupMembers
      .filter(function (m) { return m.user === meId; })
      .map(function (m) { return m.group; })
      .concat((s.joined || []).filter(function (j) { return j.user === meId; })
        .map(function (j) { return j.group; }))
      .filter(function (g, i, a) { return a.indexOf(g) === i; })
      .filter(function (g) {
        return !(s.left || []).some(function (l) { return l.group === g && l.user === meId; });
      })
      .filter(function (g) { return (s.removed || []).indexOf(g) < 0; })      // 移除的帳本誰都不再「在裡面」
      .filter(function (g) { return withArchived || (s.archived || []).indexOf(g) < 0; });
  }

  /* PATCH 可以改的欄位、一次最多刪幾筆。跟 toolkit/ledger.py 的 EDITABLE／MAX_BATCH 一樣 */
  var TX_EDITABLE = ['date', 'amount', 'kind', 'cat', 'merchant', 'note', 'groupId'];
  var MAX_BATCH = 100;

  /* 這本帳裡的紀錄還能不能改、能不能刪。結算過的不行；
     移除的帳本一定是結算過的（只有結算過的能移除），groupOf 找不到它，所以另外看 removed。 */
  function ledgerLocked(gid) {
    var g = groupOf(gid);
    if (g) return !!g.settledAt;
    return ((load().removed) || []).indexOf(gid) >= 0;
  }

  function groupOf(id) {
    // 封存的也要找得到，不然「復原」會說找不到這個群組
    return allGroups(true).filter(function (g) { return g.id === id; })[0];
  }

  /* 種子群組 + 這個瀏覽器建立的群組。
     withArchived = true 時連封存的一起回（管理頁的「已封存」區塊要用）。 */
  /* 同一個家庭裡有沒有同名的帳本（沒有家庭就只看自己開的）。
     ⚠️ 只比自己家的：別的家庭有沒有「家用」不關我們的事，比了等於透露別人帳本的名字。 */
  function sameNameGroup(s, name, exceptId) {
    var fam = (memberOf(s.me) || {}).familyId;
    var peers = fam ? global.DATA.members.filter(function (m) { return m.familyId === fam; }).map(function (m) { return m.id; }) : [s.me];
    return allGroups(true).some(function (g) { return g.id !== exceptId && g.name === name && peers.indexOf(g.owner) >= 0; });
  }

  function allGroups(withArchived) {
    var s = load();
    return global.DATA.groups.concat(s.newGroups || [])
      .map(function (g) {
        var p = (s.groupPatch || {})[g.id] || {};
        // 這次工作階段裡結算掉的，要蓋回種子資料上
        var done = (s.settled || []).filter(function (x) { return x.group === g.id; });
        return Object.assign({}, g, p, {
          archived: (s.archived || []).indexOf(g.id) >= 0,
          settledAt: done.length ? done[done.length - 1].at : (g.settledAt || null)
        });
      })
      .filter(function (g) { return (s.removed || []).indexOf(g.id) < 0; })   // 移除的連「已封存」都不列
      .filter(function (g) { return withArchived || !g.archived; });
  }

  /* 某個人在某本帳上的每月存款目標。沒設過就是 0。 */
  function goalOf(userId, groupId) {
    var s = load();
    var extra = (s.goalPatch || []).filter(function (g) {
      return g.user === userId && g.group === groupId;
    });
    if (extra.length) return Number(extra[extra.length - 1].goal) || 0;
    var seed = global.DATA.groupGoals.filter(function (g) {
      return g.user === userId && g.group === groupId;
    })[0];
    return seed ? seed.goal : 0;
  }

  /* 提醒通知的排序時間。
     ⚠️ 一開始我用「期間 + 百分比」當排序鍵，結果新加一個低百分比的門檻，
     它會排在既有門檻前面 → 被 since 濾掉 → 紅點加了卻不會叮。
     真後端是「跨過門檻的當下寫一列」，所以要用建立時間。
     這個瀏覽器加的門檻 id 是 ALN<毫秒>，種子的就用期間當近似值。 */
  function alertTs(a) {
    var m = /^ALN(\d+)$/.exec(String(a.id));
    if (m) return Number(m[1]);
    // ⚠️ 用月初不是月底——月底那個日期還在未來，
    // 新加的門檻（時間是「現在」）會排在它前面，於是永遠不算「新的」。
    return Date.parse(global.DATA.meta.period + '-01T09:00:00') + a.percent;
  }

  /* 我設的門檻。種子 + 這個瀏覽器加的，扣掉刪掉的。 */
  function myAlerts(meId) {
    var s = load();
    var gone = s.alertGone || [];
    return global.DATA.alerts.concat(s.newAlerts || [])
      .filter(function (a) { return a.user === meId && gone.indexOf(a.id) < 0; })
      .map(function (a) {
        var p = (s.alertPatch || {})[a.id] || {};
        return Object.assign({}, a, p);
      })
      .sort(function (a, b) { return a.percent - b.percent; });
  }

  /* 我每月給某個被監管者多少零用金。種子 + 這個瀏覽器改過的。 */
  function allowanceOf(payer, ward) {
    var st = load();
    var mine = (st.allowancePatch || []).filter(function (a) {
      return a.payer === payer && a.ward === ward;
    });
    if (mine.length) return Number(mine[mine.length - 1].amount) || 0;
    var seed = global.DATA.allowances.filter(function (a) {
      return a.payer === payer && a.ward === ward;
    })[0];
    return seed ? seed.amount : 0;
  }

  /* 誰是我監管的人（不含我自己）。家庭總覽要靠它把收入分開算。 */
  function wardsOf(meId) {
    return global.DATA.guardianships
      .filter(function (g) { return g.guardian === meId; })
      .map(function (g) { return g.ward; });
  }

  /* 新記的一筆要進哪一本帳。
     ⚠️ 沒有 group 的紀錄會被群組篩選擋掉，使用者記了卻找不到。
     所以每一條建立路徑都要走這裡，不要各自寫。 */
  /* 新的一筆要記在哪本帳。
     ⚠️ 結算過的帳本唯讀：指定了就擋（409），沒指定也不會落到它身上。
     真後端用 toolkit.ledger.require_open()。 */
  function groupFor(meId, wanted) {
    var mine = visibleGroups(meId);
    var open = mine.filter(function (id) { var g = groupOf(id); return g && !g.settledAt; });
    if (wanted && mine.indexOf(wanted) >= 0) {
      if (open.indexOf(wanted) < 0) throw oops('這本帳已經結算，不能再記新的帳。請換一本帳本', 409);
      return wanted;
    }
    if (!open.length) throw new Error('你還沒有可以記帳的帳本，先到「帳本」開一本');
    return open[0];
  }

  /* 跟我同帳本的人。我看得到他們**在共用帳本裡**的紀錄，
     但看不到他們記在別處的——這跟監管不一樣，監管是整個人。 */
  function coMembers(meId) {
    /* ⚠️ 以前只看 DATA.groupMembers（種子資料），自己開的帳本、後來加進來的人都不算——
       有假資料的時候看不出來，拿掉之後同帳本的人就互相點不開了。 */
    var out = [meId];
    visibleGroups(meId).forEach(function (gid) {
      memberIdsOf(gid).forEach(function (u) { if (out.indexOf(u) < 0) out.push(u); });
    });
    return out;
  }

  /* 這一筆看不看得到：A 我或我監管的人記的（跨所有帳本）
                       B 記在我有加入的帳本裡
     過一條就算。 */
  function canSeeRow(t, vis, vgs) {
    return vis.indexOf(t.user) >= 0 || vgs.indexOf(t.group) >= 0;
  }

  /* 我可以點開誰：我監管的人（看得到全貌）＋ 跟我同帳本的人（只看得到那幾本）。
     ⚠️ 比 visibleUsers 寬。兩者不可以混用——
        存款目標那種個人財務資料只給 visibleUsers，不給同帳本的人。 */
  function queryableUsers(meId) {
    var out = visibleUsers(meId).slice();
    coMembers(meId).forEach(function (u) { if (out.indexOf(u) < 0) out.push(u); });
    return out;
  }

  /* 我看得到誰的**全部**紀錄：自己 ＋ 我監管的人 ＋ 同家庭的其他家長。 */
  function visibleUsers(meId) {
    if (!memberOf(meId)) return [meId];
    var out = [meId];
    global.DATA.guardianships
      .filter(function (g) { return g.guardian === meId; })
      .forEach(function (g) { if (out.indexOf(g.ward) < 0) out.push(g.ward); });
    coParents(meId).forEach(function (u) { if (out.indexOf(u) < 0) out.push(u); });
    return out;
  }

  function sum(list, kind) {
    return list.filter(function (t) { return t.kind === kind; })
      .reduce(function (n, t) { return n + t.amount; }, 0);
  }

  /* ---------- 財務建議的規則（mock 用；真後端是「算好的數字 → 模型敘述」） ----------
     sm 是 summary 的回應、bd 是 budgets 的清單。**數字一律來自這兩支**，這裡只負責寫成句子。
     http 模式下 POST /api/advices/generate 還沒做好時，前端也用這一支先頂著（見 FALLBACK）。 */
  function buildAdvices(sm, bd, scope, meId, period) {
    var who = scope === 'family' ? null : meId;
    var head = { scope: scope === 'family' ? 'family' : 'user', user: who, period: period,
                 generatedAt: localStamp(new Date()) };
    var out = [];
    // 後端的 summary 可能沒帶 count（前端代勞的欄位），有收支就當作有紀錄
    var count = 'count' in sm ? sm.count : ((sm.income || sm.expense) ? 1 : 0);
    function add(level, title, body, basis, suggest, conf) {
      out.push(Object.assign({ id: 'AV' + Date.now() + '-' + out.length, level: level, title: title,
        body: body, basis: basis, suggest: suggest, conf: conf }, head));
    }
    if (!count) {
      add('info', '這個月還沒有紀錄', '記幾筆之後，建議才有數字可以說。',
        [period + ' 紀錄 0 筆'], ['先把今天花的記下來，一段話就能記好幾筆'], 1);
    } else {
      var sv = sm.savings;
      var basis = ['收入 ' + money(sm.income) + ' − 每月想存 ' + money(sv.goal) + ' ＝ 可以花 ' + money(sv.allowance),
                   '支出 ' + money(sm.expense) + ' ÷ 可以花 ' + money(sv.allowance) + ' ＝ ' + Math.round(sv.ratio * 100) + '%'];
      if (sv.level === 'over') {
        add('warn', '這個月存不到目標了', '支出 ' + money(sm.expense) + ' 元，比可以花的多了 ' + money(sv.shortfall) + ' 元。',
          basis, ['看看花最多的分類能不能先緩一緩', '或把這個月的存款目標調低一點'], 0.95);
      } else if (sv.level === 'near') {
        add('warn', '快用完這個月可以花的', '已經用掉 ' + Math.round(sv.ratio * 100) + '%，剩 ' + money(sv.left) + ' 元。',
          basis, ['接下來大筆的支出先想一下'], 0.93);
      } else {
        add('ok', '這個月的進度正常', '到目前花了可以花的 ' + Math.round(sv.ratio * 100) + '%，照這個速度存得到目標。',
          basis, ['維持現在的節奏就好'], 0.9);
      }
      if (sm.byCat.length && sm.expense) {
        var top = sm.byCat[0];
        add('info', top.name + '是這個月花最多的', top.name + ' ' + money(top.amount) + ' 元，佔支出 ' +
          Math.round(top.amount / sm.expense * 100) + '%。',
          [top.name + ' ' + money(top.amount) + ' ÷ 支出 ' + money(sm.expense)], ['點進統計看是哪幾筆'], 0.9);
      }
      bd.filter(function (b) { return b.over && (scope === 'family' || b.user === meId); }).forEach(function (b) {
        add('warn', '「' + b.catName + '」超過預算', b.catName + ' 花了 ' + money(b.used) + ' 元，預算 ' + money(b.limit) + ' 元。',
          [b.catName + ' ' + money(b.used) + ' ÷ 預算 ' + money(b.limit) + ' ＝ ' + Math.round(b.pct * 100) + '%'],
          ['決定要少花，還是把預算調到比較實際的數字'], 0.92);
      });
      if (scope === 'family' && sm.allowance > 0) {
        add(sm.wardSpend > sm.allowance ? 'warn' : 'info', '孩子的花費與零用金',
          '照看的孩子這個月花了 ' + money(sm.wardSpend) + ' 元，零用金是 ' + money(sm.allowance) + ' 元。',
          ['支出 ' + money(sm.wardSpend) + ' ÷ 零用金 ' + money(sm.allowance)], ['跟孩子一起看看錢花到哪裡'], 0.88);
      }
    }
    return { advices: out, head: head };
  }

  /* ---------- 一句話 → 一筆（mock 用的規則；真後端是模型） ---------- */
  var ZH_NUM = { '零': 0, '一': 1, '二': 2, '兩': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9 };
  var ZH_UNIT = { '十': 10, '百': 100, '千': 1000, '萬': 10000 };
  /* 「兩千」「三百五十」「一萬二」→ 數字。阿拉伯數字優先 */
  function amountOf(text) {
    // 店名裡的數字不是金額（7-11 買咖啡 55 → 55）
    var t = String(text).replace(/7-?11|711/gi, '').replace(/,/g, '');
    var m = t.match(/(\d+(?:\.\d+)?)\s*(萬|千|k|K)?/);
    if (m) return Math.round(Number(m[1]) * (m[2] === '萬' ? 10000 : (m[2] ? 1000 : 1))) || null;
    // 中文數字至少要帶一個單位，「吃了一個便當」的「一」不是金額
    var z = t.match(/[零一二兩三四五六七八九]*[十百千萬][零一二兩三四五六七八九十百千萬]*/);
    if (!z) return null;
    var total = 0, section = 0, number = 0, lastUnit = 0;
    z[0].split('').forEach(function (ch) {
      if (ch in ZH_NUM) { number = ZH_NUM[ch]; return; }
      var u = ZH_UNIT[ch];
      if (u === 10000) { total += (section + number) * 10000; section = 0; number = 0; lastUnit = 10000; return; }
      section += (number || 1) * u; number = 0; lastUnit = u;
    });
    /* 「三百五」「一千二」「一萬二」：最後一個數字省略了單位，是上一個單位的十分之一。
       「三百零五」有「零」，就是 5 本身 */
    var tail = (number && lastUnit >= 100 && /[十百千萬][一二兩三四五六七八九]$/.test(z[0])) ? number * lastUnit / 10 : number;
    return (total + section + tail) || null;
  }
  var CAT_RULES = [
    ['I01', /薪水|薪資|月薪/], ['I02', /獎金|紅包|年終/], ['I03', /零用|媽媽給|爸爸給|給我/],
    ['I04', /賺|打工|收入|入帳|退款/],
    ['C02', /加油|捷運|公車|計程車|高鐵|火車|停車|油錢|悠遊卡|機票/],
    ['C03', /房租|房貸|水費|電費|瓦斯|管理費|網路費/],
    ['C07', /醫生|掛號|藥|牙醫|診所|醫院/],
    ['C06', /書|補習|學費|課程|文具/],
    ['C05', /電影|訂閱|遊戲|KTV|唱歌|旅遊|門票/],
    ['C04', /超市|全聯|日用|衛生紙|洗衣|清潔|好市多/],
    ['C01', /早餐|午餐|晚餐|宵夜|吃|飯|咖啡|飲料|麵包|便當|餐/]
  ];
  var MERCHANTS = ['全家', '7-11', '萊爾富', '全聯', '家樂福', '好市多', '星巴克', '麥當勞', '加油站'];
  function parseLine(text) {
    var t = String(text || '');
    var amount = amountOf(t);
    var rule = CAT_RULES.filter(function (r) { return r[1].test(t); })[0];
    var cat = rule ? rule[0] : 'C08';
    var kind = cat.charAt(0) === 'I' ? 'income' : 'expense';
    var back = /前天/.test(t) ? 2 : (/昨天|昨晚/.test(t) ? 1 : 0);
    var d = new Date(todayStr() + 'T12:00:00');
    d.setDate(d.getDate() - back);
    var date = d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2);
    var merchant = MERCHANTS.filter(function (x) { return t.indexOf(x) >= 0; })[0] || '';
    var missing = amount ? [] : ['amount'];
    return {
      date: date, amount: amount, kind: kind, cat: cat, merchant: merchant, note: '',
      conf: { date: back ? 0.9 : 0.8, amount: amount ? 0.9 : 0, kind: rule ? 0.85 : 0.6, cat: rule ? 0.75 : 0.3 },
      missing: missing,
      hint: amount ? (rule ? '' : '分類猜不出來，先放「其他」，確認時改一下。') : '這一句抓不到金額，補上才能存。'
    };
  }

  /* ============================================================
     mock 轉接器
     ============================================================ */
  var mock = {

    me: function () {
      var s = load();
      return sleep(120).then(function () {
        var m = memberOf(s.me);
        var fam = familyOf(s.me);
        return {
          user: withTheme(clone(m)),
          family: fam ? { id: fam.id, name: fam.name, period: global.DATA.meta.period } : null,
          visible: visibleUsers(s.me),
          queryable: queryableUsers(s.me),
          guardedBy: global.DATA.guardianships
            .filter(function (g) { return g.ward === s.me; })
            .map(function (g) { return clone(memberOf(g.guardian)); })
        };
      });
    },

    /* ---------------------------------------------------------
       認證。mock 沒有真的密碼雜湊，只檢查「email 存在」＋「長度夠」，
       目的是把登入 → 拿 token → 登出這個流程跑給前端看。
       真的驗證在後端，用 toolkit.passwords。
       --------------------------------------------------------- */
    authState: function () {
      var s = load();
      /* ⚠️ 已經登入的人被停權，下一次請求就要被擋——不是等他下次登入。
         真後端在載入目前使用者那層呼叫 roles.require_active()；
         只在登入時檢查的話，他手上那張 access token 還能用 30 分鐘。 */
      if ((s.suspended || {})[s.me]) {
        s.auth = { loggedIn: false };
        save();
      }
      return Promise.resolve({ loggedIn: !!(s.auth && s.auth.loggedIn) });
    },

    login: function (c) {
      var s = load(); c = c || {};
      return sleep(260).then(function () {
        var mail = String(c.email || '').trim().toLowerCase();
        var u = global.DATA.members.filter(function (m) {
          return String(m.email || '').toLowerCase() === mail;
        })[0];
        /* ⚠️ 「沒有這個帳號」跟「密碼錯」回同一句話、同一個狀態碼。
           分開講等於送給攻擊者一支帳號列舉工具。 */
        if (!u || !checkPw(s, u.id, c.password)) throw oops('email 或密碼不對', 401);

        /* ⚠️ 停權必須真的擋得住登入，否則它只是畫面上的一個標籤。
           ⚠️ 而且要**在密碼驗證通過之後**才檢查——順序反過來的話，
              任何人都能用一個 email 試出「這個帳號是不是被停權了」。 */
        var sus = (s.suspended || {})[u.id];
        if (sus) {
          throw new Error('這個帳號已被停權：' + (sus.reason || '違反使用規範'));
        }

        s.me = u.id;
        s.auth = { loggedIn: true };
        save();
        return {
          accessToken: 'mock.access.' + u.id,
          refreshToken: 'mock.refresh.' + u.id,
          expiresIn: 1800,
          user: withTheme(clone(u))
        };
      });
    },

    register: function (p) {
      var s = load(); p = p || {};
      return sleep(320).then(function () {
        var name = String(p.name || '').trim();
        var mail = String(p.email || '').trim().toLowerCase();
        if (!name) throw new Error('請填名字');
        if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(mail)) throw new Error('email 格式看起來不對');
        if (global.DATA.members.some(function (m) {
          return String(m.email || '').toLowerCase() === mail;
        })) throw new Error('這個 email 已經註冊過了');
        if (String(p.password || '').length < 8) throw new Error('密碼至少 8 個字');
        /* ⚠️ 存款目標搬到註冊後的個人化設定（PUT /api/savings-goal）。
           舊的前端還把它塞在註冊裡的話直接擋——默默吃掉，使用者會以為設好了。 */
        if (p.savingsGoal !== undefined) throw oops('存款目標不在註冊時設定，註冊完的個人化設定會問', 400);
        if (global.DATA.members.some(function (m) { return String(m.email || '').toLowerCase() === mail; })) {
          throw oops('這個 email 已經註冊過了', 409);
        }

        var n = global.DATA.members.reduce(function (mx, m) {
          return Math.max(mx, Number(String(m.id).replace(/\D/g, '')) || 0);
        }, 0) + 1;
        /* 新註冊的人**還不屬於任何家庭**：自己建立一個（成為家長），
           或是等家人邀請、輸入邀請碼加入。身分由加入的方式決定，不是註冊時選。 */
        var u = {
          id: 'U' + n, name: name, email: mail, role: null, familyId: null,
          avatar: name.slice(-1), age: null,
          joined: todayStr(),
          // 收入、支出不放在人身上：一律從明細現算（GET /api/summary 的 members[]），放了就會跟明細對不起來
          savingsGoal: 0,
          onboardedAt: null           // 還沒走個人化設定
        };
        global.DATA.members.push(u);
        s.newUsers = (s.newUsers || []).concat([clone(u)]);
        s.passwords = s.passwords || {};
        s.passwords[u.id] = pwHash(p.password);
        s.me = u.id;
        s.auth = { loggedIn: true };
        save();
        return {
          accessToken: 'mock.access.' + u.id,
          refreshToken: 'mock.refresh.' + u.id,
          expiresIn: 1800,
          user: withTheme(clone(u))
        };
      });
    },

    logout: function () {
      var s = load();
      return sleep(150).then(function () {
        s.auth = { loggedIn: false };
        save();
        return { ok: true };
      });
    },

    updateProfile: function (p) {
      var s = load(); p = p || {};
      return sleep(200).then(function () {
        var m = memberOf(s.me);
        var q = patchOf(s, s.me);
        if (p.displayName !== undefined) {
          var name = String(p.displayName).trim();
          if (!name) throw new Error('名字不能空白');
          q.name = name;
          // 沒有上傳大頭貼的人，頭像字跟著名字走
          if (!m.avatarUrl) q.avatar = name.slice(-1);
        }
        if (p.birthYear !== undefined) {
          var y = Number(p.birthYear);
          var now = new Date().getFullYear();
          if (p.birthYear !== null && (!y || y < 1900 || y > now)) {
            throw new Error('出生年份不合理');
          }
          q.birthYear = y || null;
          q.age = y ? now - y : null;
        }
        /* 主題只收清單裡有的 id。真後端用 toolkit.theme.clean_theme() 擋，回 422 */
        if (p.theme !== undefined) {
          var ids = (global.DATA.themes || []).map(function (t) { return t.id; });
          if (ids.indexOf(p.theme) < 0) throw oops('沒有這個主題', 422);
          q.theme = p.theme;
        }
        /* 個人化設定走完（或按了全部跳過）。只能設成 true——
           沒有「退回沒走過」這回事，存款目標之後到個人資料改就好。 */
        if (p.onboarded !== undefined) {
          if (p.onboarded !== true) throw oops('onboarded 只能是 true', 422);
          if (!m.onboardedAt) q.onboardedAt = new Date().toISOString();
        }
        applyPatch(s.patch);
        save();
        return withTheme(clone(memberOf(s.me)));
      });
    },

    uploadAvatar: function (dataUri) {
      var s = load();
      return sleep(420).then(function () {
        if (!/^data:image\/(png|jpeg|webp);base64,/.test(String(dataUri || ''))) {
          throw new Error('只收 PNG / JPEG / WebP');
        }
        // 粗估 base64 解出來的大小，跟後端的 200 KB 上限對齊
        var bytes = Math.floor(String(dataUri).split(',')[1].length * 3 / 4);
        if (bytes > 200 * 1024) throw new Error('圖片太大了（上限 200 KB）');
        // 看檔案開頭的識別位元組，不信宣告的型別（跟後端 toolkit/images.py 同一個檢查）
        var decode = global.atob || (typeof atob === 'function' ? atob : null), head = '';
        try { head = decode ? decode(String(dataUri).split(',')[1].slice(0, 16)) : ''; } catch (e) { head = ''; }
        var magic = head.slice(0, 4) === '\x89PNG' || head.slice(0, 3) === '\xff\xd8\xff' ||
          (head.slice(0, 4) === 'RIFF' && head.slice(8, 12) === 'WEBP');
        if (!magic) throw oops('檔案內容不是 PNG / JPEG / WebP', 422);
        patchOf(s, s.me).avatarUrl = dataUri;
        applyPatch(s.patch);
        save();
        var m = memberOf(s.me);
        return { avatarUrl: m.avatarUrl, avatar: m.avatar };
      });
    },

    deleteAvatar: function () {
      var s = load();
      return sleep(180).then(function () {
        patchOf(s, s.me).avatarUrl = null;
        applyPatch(s.patch);
        save();
        var m = memberOf(s.me);
        return { avatarUrl: null, avatar: m.avatar };
      });
    },

    /* 重大操作前的密碼確認。
       ⚠️ 它跟登入不一樣：驗證通過也**不換發 token**。
       真後端一定要做速率限制，否則這支就是免費的密碼嘗試器。 */
    /* ============================================================
       平台管理員

       ⚠️ 這幾支**刻意不回傳任何金額**。平台管理員能停權、能看稽核，
       但讀不到任何人的收支——一個能讀全系統消費明細的帳號，
       比家長越權嚴重得多，而且沒有任何人看得見那個視角。

       權限判斷在 toolkit/roles.py 的 require_platform()，
       它的白名單只有停權、解除停權、讀稽核三項。
       ============================================================ */
    adminUsers: function () {
      var s = load(), D = global.DATA;
      return sleep(240).then(function () {
        requirePlatform(s);
        return {
          users: D.members.filter(function (m) { return !m.isPlatformAdmin; })
            .map(function (m) {
              /* ⚠️ 只有身分欄位。income / expense / savingsGoal 一律不給。 */
              return {
                id: m.id, name: m.name, email: m.email, role: m.role,
                joined: m.joined,
                suspendedAt: (s.suspended || {})[m.id] ? (s.suspended || {})[m.id].at : null,
                suspendedReason: (s.suspended || {})[m.id]
                  ? (s.suspended || {})[m.id].reason : null
              };
            })
        };
      });
    },

    suspendUser: function (uid, reason) {
      var s = load();
      return sleep(320).then(function () {
        requirePlatform(s);
        var m = memberOf(uid);
        if (!m) throw new Error('找不到這個帳號');
        if (m.isPlatformAdmin) throw new Error('不能停權平台管理員');
        /* 跟 toolkit/roles.py 的 clean_suspend_reason() 同一套規則：
           空白壓成一格再數字數（擋掉用空白湊字數），最多 200 字。 */
        var why = String(reason || '').split(/\s+/).join(' ').trim().slice(0, 200);
        if (why.length < 4) throw new Error('要寫停權理由——沒有理由的停權就是任意封鎖');

        s.suspended = s.suspended || {};
        s.suspended[uid] = { at: new Date().toISOString(), reason: why };
        pushAudit(s, 'suspend_user', uid, why);
        save();
        return { id: uid, suspendedAt: s.suspended[uid].at };
      });
    },

    unsuspendUser: function (uid) {
      var s = load();
      return sleep(280).then(function () {
        requirePlatform(s);
        s.suspended = s.suspended || {};
        if (!s.suspended[uid]) throw new Error('這個帳號沒有被停權');
        delete s.suspended[uid];
        pushAudit(s, 'unsuspend_user', uid, '解除停權');
        save();
        return { id: uid, suspendedAt: null };
      });
    },

    audit: function () {
      var s = load(), D = global.DATA;
      return sleep(220).then(function () {
        requirePlatform(s);
        var extra = (s.audit || []).slice().reverse();
        return {
          logs: extra.concat(clone(D.auditLogs)).map(function (a) {
            var who = memberOf(a.actor);
            return Object.assign({}, a, { actorName: who ? who.name : a.actor });
          })
        };
      });
    },

    /* ---------------------------------------------------------
       忘記密碼

       ⚠️ 回應一律是 RESET_MESSAGE，有沒有這個帳號都一樣——不然這支就是帳號列舉工具。
       ⚠️ demoMail 只有 mock 會回：示範站沒有後端、寄不出信，只好把信的內容攤在畫面上。
          **真後端絕對不能回這個欄位**，那等於把重設連結交給任何輸入別人 email 的人。
          （mock 只在帳號存在時才附，等於說出帳號在不在；那是示範的取捨，跟登入的錯誤訊息同一個道理。）
       真後端：toolkit/password_reset.py 產 token、只存雜湊；toolkit/mailer.py 用 Brevo 寄出。
       --------------------------------------------------------- */
    requestPasswordReset: function (email) {
      var s = load();
      return sleep(420).then(function () {
        var mail = String(email || '').trim().toLowerCase();
        if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(mail)) throw oops('email 格式看起來不對', 400);
        var out = { ok: true, message: RESET_MESSAGE };
        var u = global.DATA.members.filter(function (m) { return String(m.email || '').toLowerCase() === mail; })[0];
        if (!u) return out;
        var now = Date.now();
        var last = (s.resets || []).filter(function (r) { return r.userId === u.id; })
          .reduce(function (mx, r) { return Math.max(mx, r.createdAt); }, 0);
        if (now - last < RESET_COOLDOWN_SEC * 1000) return out;          // 冷卻中：不寄，但回一樣的話
        var token = randomToken();
        s.resets = (s.resets || []).concat([{ userId: u.id, token: token, createdAt: now,
          expiresAt: now + RESET_MINUTES * 60000, usedAt: null }]);
        save();
        out.demoMail = { to: u.email, subject: '重設你的家庭記帳密碼', link: '#/reset/' + token, minutes: RESET_MINUTES };
        return out;
      });
    },

    confirmPasswordReset: function (token, password) {
      var s = load();
      return sleep(360).then(function () {
        var r = (s.resets || []).filter(function (x) { return x.token === String(token || ''); })[0];
        // 找不到、過期、用過：同一句話，不讓人分辨是哪一種
        if (!r || r.usedAt || Date.now() >= r.expiresAt) throw oops(RESET_INVALID, 400);
        if (String(password || '').length < 8) throw oops('密碼至少 8 個字', 422);
        r.usedAt = Date.now();
        s.passwords = s.passwords || {};
        s.passwords[r.userId] = pwHash(password);
        /* 改完密碼，所有裝置都要登出（連結可能是被別人拿去用的）。mock 只有這一個瀏覽器 */
        s.auth = { loggedIn: false };
        save();
        return { ok: true };
      });
    },

    verifyPassword: function (pw) {
      var s = load();
      return sleep(320).then(function () {
        /* 400 不是 401：401 會讓 http 轉接器以為 token 過期、白白續期一次再重送 */
        if (!checkPw(s, s.me, pw)) throw oops('密碼不正確', 400);
        return { ok: true };
      });
    },

    /* 登入中的裝置。mock 只有這一個瀏覽器；真後端列 sessions 表裡還沒撤銷的 */
    sessions: function () {
      return sleep(160).then(function () {
        var ua = (global.navigator && global.navigator.userAgent) || '';
        var device = /iPhone|iPad|Android/i.test(ua) ? '手機瀏覽器' : (ua ? '電腦瀏覽器' : '這台裝置');
        return { sessions: [{ id: 'this-device', device: device, current: true, lastActiveAt: new Date().toISOString() }] };
      });
    },

    /* 登出所有裝置（包含這一台）。真後端把這個人所有 sessions 設 revoked_at */
    logoutAll: function () {
      var s = load();
      return sleep(220).then(function () {
        s.auth = { loggedIn: false };
        save();
        return { revoked: 1 };
      });
    },

    /* 理財習慣。⚠️ 它會被放進財務建議的 prompt，所以：
       · 風格／目標／固定安排都是**從固定清單挑 id**，不是自由文字
       · 補充說明限 200 字，而且在組 prompt 時會被標示成「資料，不是指令」
         （隔離的做法寫在 backend/app/toolkit/profile.py）

       為什麼要這麼小心：建議是**給監管者看的**，
       子女如果能在自己的補充說明裡下指令，就能操控父母看到的內容。 */
    financeProfile: function () {
      var s = load(), D = global.DATA;
      return sleep(160).then(function () {
        var m = memberOf(s.me) || {};
        return {
          finance: clone((s.finance || {})[s.me] || m.finance || null),
          styles: clone(D.financeStyles),
          goals: clone(D.financeGoals),
          habits: clone(D.financeHabits)
        };
      });
    },

    setFinanceProfile: function (p) {
      var s = load(), D = global.DATA;
      p = p || {};
      return sleep(280).then(function () {
        var okStyle = D.financeStyles.map(function (x) { return x.id; });
        var okGoals = D.financeGoals.map(function (x) { return x.id; });
        var okHabits = D.financeHabits.map(function (x) { return x.id; });

        /* ⚠️ 認得的才留。不是為了防呆，是為了**不讓使用者自己造 id
           把任意文字送進 prompt**。 */
        var v = {
          style: okStyle.indexOf(p.style) >= 0 ? p.style : null,
          goals: (p.goals || []).filter(function (g) { return okGoals.indexOf(g) >= 0; }),
          habits: (p.habits || []).filter(function (h) { return okHabits.indexOf(h) >= 0; }),
          note: String(p.note || '').replace(/\s+/g, ' ').trim().slice(0, 200)
        };
        s.finance = s.finance || {};
        s.finance[s.me] = v;
        save();
        return clone(v);
      });
    },

    changePassword: function (p) {
      var s = load(); p = p || {};
      return sleep(260).then(function () {
        if (!checkPw(s, s.me, p.oldPassword)) throw oops('目前的密碼不對', 400);
        if (String(p.newPassword || '').length < 8) throw oops('新密碼至少 8 個字', 422);
        if (p.oldPassword === p.newPassword) throw oops('新密碼不能跟舊的一樣', 400);
        s.passwords = s.passwords || {};
        s.passwords[s.me] = pwHash(p.newPassword);
        save();
        return { ok: true };
      });
    },

    /* ---------------------------------------------------------
       群組（帳本）。一個家庭可以開好幾本帳，每一筆記帳都屬於其中一本。
       ⚠️ 只回我加入的——別人的帳本連名字都不該看到。
       --------------------------------------------------------- */
    groups: function (f) {
      var s = load(); f = f || {};
      return sleep(LATENCY).then(function () {
        var mine = visibleGroups(s.me, true);
        var vis = visibleUsers(s.me);
        return {
          me: s.me,
          groups: allGroups(!!f.includeArchived)
            .filter(function (g) { return mine.indexOf(g.id) >= 0; })
            .map(function (g) {
              var members = memberIdsOf(g.id);
              /* 活動帳本到期了沒。⚠️ 只是一個判斷，不是排程——
                 沒有人在背景跑，是畫面問「今天過了沒」。 */
              var overdue = g.kind === 'temp' && !g.settledAt && g.endsOn &&
                g.endsOn < todayStr();
              return Object.assign(clone(g), {
                kind: g.kind || 'standing',
                settled: !!g.settledAt,
                overdue: !!overdue,
                members: members,
                memberNames: members.map(function (u) {
                  return (memberOf(u) || {}).name || u;
                }),
                /* ⚠️ 筆數要跟「點進去真的看得到的」一致。
                   只用群組篩的話，面板寫 10 筆、點進去只有 7 筆——
                   因為裡面有 3 筆是我不能看的那個人記的。 */
                count: s.transactions.filter(function (t) {
                  return t.group === g.id && vis.indexOf(t.user) >= 0;
                }).length,
                goal: goalOf(s.me, g.id),
                canEdit: g.owner === s.me,
                notify: notifyOf(g.id, s.me)
              });
            })
        };
      });
    },

    /* 結算一本活動帳本。

       ⚠️ 結算**不搬動任何一筆紀錄**。紀錄本來就屬於這本帳，也本來就
       出現在每個成員自己的收支明細裡（可見範圍是聯集）。結算做的是
       兩件事：把這本帳標記成結束、之後不能再往裡面記。

       所以它也**不會改變任何人的可見範圍**——監管者早就看得到監管對象
       在任何帳本的紀錄了。這一點跟最早的設計不同，是因為可見範圍後來
       從交集改成聯集，那個隱私顧慮自己消失了。 */
    settleGroup: function (gid) {
      var s = load();
      return sleep(320).then(function () {
        var g = allGroups(true).filter(function (x) { return x.id === gid; })[0];
        if (!g) throw new Error('找不到這本帳');
        if (g.kind !== 'temp') throw new Error('只有活動帳本需要結算');
        if (g.owner !== s.me) throw new Error('只有開這本帳的人可以結算');
        if (g.settledAt) throw new Error('這本帳已經結算過了');
        s.settled = (s.settled || []).concat([
          { group: gid, at: new Date().toISOString() }]);
        save();
        return { id: gid, settledAt: s.settled[s.settled.length - 1].at };
      });
    },

    /* 這本帳有動靜要不要通知我。預設關——開著的話光家用本月就是
       31 筆 × 3 個成員 = 93 則。 */
    setGroupNotify: function (gid, on) {
      var s = load();
      return sleep(200).then(function () {
        if (visibleGroups(s.me, true).indexOf(gid) < 0) {
          var e = new Error('你不在這本帳裡'); e.status = 403; throw e;
        }
        s.joined = (s.joined || []).concat([
          { group: gid, user: s.me, notify: !!on }]);
        save();
        return { group: gid, notify: !!on };
      });
    },

    createGroup: function (p) {
      var s = load(); p = p || {};
      return sleep(300).then(function () {
        var name = String(p.name || '').trim();
        if (!name) throw new Error('帳本要有名字');
        if (sameNameGroup(s, name)) throw oops('家裡已經有一本叫「' + name + '」的帳了', 409);
        var n = allGroups().reduce(function (mx, g) {
          return Math.max(mx, Number(String(g.id).replace(/\D/g, '')) || 0);
        }, 0) + 1;
        var kind = p.kind === 'temp' ? 'temp' : 'standing';
        if (kind === 'temp' && !p.endsOn) throw new Error('活動帳本要有結束日');

        var g = {
          id: 'G' + n, name: name,
          color: p.color || (global.DATA.groupColors || [{}])[0].id || 'book-indigo',
          owner: s.me,
          kind: kind,
          endsOn: kind === 'temp' ? p.endsOn : null,
          settledAt: null,
          created: todayStr(),
          note: String(p.note || '')
        };
        s.newGroups = (s.newGroups || []).concat([g]);
        // ⚠️ 建立者要自動加入，不然他自己也看不到剛建的帳本
        s.joined = (s.joined || []).concat([{ group: g.id, user: s.me }]);
        save();
        return clone(g);
      });
    },

    updateGroup: function (gid, p) {
      var s = load(); p = p || {};
      return sleep(220).then(function () {
        var g = groupOf(gid);
        if (!g) throw new Error('找不到這個群組');
        if (g.owner !== s.me) { var e = new Error('只有建立者可以改'); e.status = 403; throw e; }
        s.groupPatch = s.groupPatch || {};
        var q = s.groupPatch[gid] = s.groupPatch[gid] || {};
        if (p.name !== undefined) {
          var nm = String(p.name).trim();
          if (!nm) throw new Error('群組要有名字');
          if (nm !== g.name && sameNameGroup(s, nm, gid)) throw oops('家裡已經有一本叫「' + nm + '」的帳了', 409);
          q.name = nm; q.icon = nm.slice(-1);
        }
        if (p.color !== undefined) q.color = p.color;
        if (p.note !== undefined) q.note = String(p.note);
        /* 復原：把 id 從封存清單拿掉。
           ⚠️ 封存從頭到尾都沒有動過任何一筆記帳，所以復原不需要還原資料，
           只是讓它重新出現在清單上。 */
        if (p.archived === false) {
          s.archived = (s.archived || []).filter(function (a) { return a !== gid; });
        }
        save();
        return clone(groupOf(gid));
      });
    },

    archiveGroup: function (gid) {
      var s = load();
      return sleep(240).then(function () {
        var g = groupOf(gid);
        if (!g) throw new Error('找不到這個群組');
        if (g.owner !== s.me) { var e = new Error('只有建立者可以封存'); e.status = 403; throw e; }
        /* ⚠️ 封存不是刪除。裡面的記帳紀錄還在——真刪了那些紀錄會變成孤兒。 */
        s.archived = (s.archived || []).concat([gid]);
        save();
        return { id: gid, archived: true };
      });
    },

    /* 移除已結算的活動帳本。
       ⚠️ 移除的是「帳本」，不是紀錄：裡面的每一筆還在記帳的人自己的收支明細和統計裡，
          過去月份的數字不會變。但這本帳從清單、切換器、「已封存」都消失，不能復原；
          原本只靠這本帳看得到別人紀錄的成員，之後就看不到了。
       只有建立者、只有結算過的才能移除——還在用的帳本請用封存。
       真後端用 toolkit.ledger.require_removable()。 */
    removeGroup: function (gid) {
      var s = load();
      return sleep(260).then(function () {
        var g = groupOf(gid);
        if (!g) throw oops('找不到這本帳', 404);
        if (g.owner !== s.me) throw oops('只有建立這本帳的人可以移除', 403);
        if (!g.settledAt) throw oops('只有結算過的活動帳本可以移除；還在用的帳本請改用封存', 409);
        s.removed = (s.removed || []).concat([gid]);
        s.archived = (s.archived || []).filter(function (a) { return a !== gid; });
        pushAudit(s, 'remove_group', gid, '移除已結算的「' + g.name + '」');
        save();
        return { id: gid, removed: true };
      });
    },

    addGroupMember: function (gid, userId) {
      var s = load();
      return sleep(240).then(function () {
        var g = groupOf(gid);
        if (!g) throw new Error('找不到這個群組');
        if (g.owner !== s.me) { var e = new Error('只有建立者可以加人'); e.status = 403; throw e; }
        var who = memberOf(userId);
        var me = memberOf(s.me);
        /* 平台管理員加進帳本，就等於讓他讀得到那本帳——停權是關門，不是配鑰匙。
           不同家庭的人也不行：帳本的成員只能從自己家裡選。 */
        if (!who || who.isPlatformAdmin || !me.familyId || who.familyId !== me.familyId) {
          throw new Error('這個家庭裡沒有這個人');
        }
        if (memberIdsOf(gid).indexOf(userId) >= 0) throw new Error('他已經在這本帳裡了');
        s.joined = (s.joined || []).concat([{ group: gid, user: userId }]);
        save();
        return { group: gid, user: userId };
      });
    },

    removeGroupMember: function (gid, userId) {
      var s = load();
      return sleep(240).then(function () {
        var g = groupOf(gid);
        if (!g) throw new Error('找不到這個群組');
        if (g.owner !== s.me) { var e = new Error('只有建立者可以移除'); e.status = 403; throw e; }
        if (userId === g.owner) throw new Error('建立者不能把自己移出去');
        s.left = (s.left || []).concat([{ group: gid, user: userId }]);
        save();
        return { group: gid, user: userId, removed: true };
      });
    },

    /* ---------------------------------------------------------
       階段性提醒
       --------------------------------------------------------- */
    allowances: function () {
      var st = load();
      return sleep(160).then(function () {
        return {
          allowances: wardsOf(st.me).map(function (w) {
            var m = memberOf(w) || {};
            return {
              wardId: w, wardName: m.name || w,
              amount: allowanceOf(st.me, w),
              // 這個月花掉多少：從明細現算（人身上沒有彙總欄位）
              spent: st.transactions.filter(function (t) {
                return t.user === w && t.kind === 'expense' && t.date.indexOf(global.DATA.meta.period) === 0;
              }).reduce(function (n, t) { return n + t.amount; }, 0)
            };
          })
        };
      });
    },

    setAllowance: function (wardId, amount) {
      var st = load();
      return sleep(220).then(function () {
        if (wardsOf(st.me).indexOf(wardId) < 0) {
          var e = new Error('你沒有監管這個人'); e.status = 403; throw e;
        }
        var v = Number(amount);
        if (isNaN(v) || v < 0) throw new Error('零用金要是 0 以上的數字');
        st.allowancePatch = (st.allowancePatch || []).concat([
          { payer: st.me, ward: wardId, amount: v }
        ]);
        save();
        var m = memberOf(wardId) || {};
        return { wardId: wardId, wardName: m.name, amount: v };
      });
    },

    savingsGoals: function () {
      var s = load();
      return sleep(160).then(function () {
        var me = memberOf(s.me) || {};
        var rows = [{ groupId: null, groupName: '整體', goal: me.savingsGoal || 0 }];
        visibleGroups(s.me).forEach(function (gid) {
          var g = groupOf(gid);
          if (g) rows.push({ groupId: gid, groupName: g.name, goal: goalOf(s.me, gid) });
        });
        return { goals: rows };
      });
    },

    alerts: function () {
      var s = load();
      return sleep(160).then(function () {
        return {
          alerts: myAlerts(s.me).map(function (a) {
            var g = a.group ? groupOf(a.group) : null;
            return Object.assign(clone(a), {
              groupId: a.group,
              groupName: g ? g.name : '整體'
            });
          })
        };
      });
    },

    createAlert: function (p) {
      var s = load(); p = p || {};
      return sleep(240).then(function () {
        var pct = Number(p.percent);
        if (!pct || pct < 1 || pct > 200) throw new Error('門檻要在 1 到 200 之間');
        var gid = p.groupId || null;
        /* ⚠️ 同一個（人、帳本、百分比）只能有一筆。
           重複的話同一次跨越會發兩則一模一樣的通知。 */
        if (myAlerts(s.me).some(function (a) {
          return a.percent === pct && (a.group || null) === gid;
        })) throw new Error('這個門檻已經設過了');
        var a = { id: stampId('ALN'), user: s.me, group: gid, percent: pct,
                  enabled: true, firedPeriod: null };
        s.newAlerts = (s.newAlerts || []).concat([a]);
        save();
        return clone(a);
      });
    },

    updateAlert: function (aid, p) {
      var s = load(); p = p || {};
      return sleep(200).then(function () {
        s.alertPatch = s.alertPatch || {};
        var q = s.alertPatch[aid] = s.alertPatch[aid] || {};
        if (p.percent !== undefined) {
          var pct = Number(p.percent);
          if (!pct || pct < 1 || pct > 200) throw new Error('門檻要在 1 到 200 之間');
          q.percent = pct;
        }
        // 關掉但不刪除——使用者常常只是這個月不想被吵
        if (p.enabled !== undefined) q.enabled = !!p.enabled;
        save();
        var row = myAlerts(s.me).filter(function (a) { return a.id === aid; })[0];
        if (!row) throw oops('找不到這個門檻', 404);
        return { id: aid, user: row.user, group: row.group || null, percent: row.percent, enabled: row.enabled, firedPeriod: row.firedPeriod || null };
      });
    },

    deleteAlert: function (aid) {
      var s = load();
      return sleep(200).then(function () {
        s.alertGone = (s.alertGone || []).concat([aid]);
        save();
        return { id: aid, deleted: true };
      });
    },

    summary: function (f) {
      f = f || {};
      var s = load(), D = global.DATA;
      return sleep(LATENCY).then(function () {
        var users = f.scope === 'family' ? visibleUsers(s.me) : [s.me];
        /* ⚠️ 統計只走 A（這些人記的），不走 B。
           B 會把共用帳本裡「別人的錢」算進這個人的總額——
           家用帳本裡配偶花的錢，不該出現在我的支出裡。 */
        var tx = s.transactions.filter(function (t) {
          if (f.groupId && f.groupId !== 'all' && t.group !== f.groupId) return false;
          return users.indexOf(t.user) >= 0 && t.date.indexOf(D.meta.period) === 0;
        });
        // 成員表上的 income / expense 是本月至今的合計（示範明細已含在內）；
        // 使用者新記的（id 以 N 開頭）才另外加上去，這樣兩個畫面的數字才會一致
        var added = tx.filter(function (t) { return String(t.id).indexOf('N') === 0; });

        /* ⚠️ 家庭總覽不把被監管者的收入算進家庭收入。
           他們的收入主要來自零用錢——那是家裡給的，
           算進來等於同一筆錢先當成家庭支出、再當成家庭收入，憑空多一筆。
           支出則要算：那筆錢確實離開了這個家。

           他們自己的收入另外回一個 wardIncome，畫面上分開顯示。 */
        var wards = f.scope === 'family' ? wardsOf(s.me) : [];
        var earners = users.filter(function (u) { return wards.indexOf(u) < 0; });

        /* ⚠️ 一律從明細算，不要用 members[] 上的彙總欄位。

           這兩份本來是各寫各的：KPI 讀彙總、圓餅圖讀明細，於是
           「本月支出 41,230」下面那張圖加起來只有 32,770——
           同一個畫面上兩個數字互相打臉，而且沒有任何錯誤訊息。

           明細是唯一的事實來源（資料表註解也是這樣寫的）。 */
        function txSum(uid, kind) {
          return sum(tx.filter(function (t) { return t.user === uid; }), kind);
        }

        var income = earners.reduce(function (n, u) { return n + txSum(u, 'income'); }, 0);
        var wardIncome = wards.reduce(function (n, u) { return n + txSum(u, 'income'); }, 0);
        var expense = users.reduce(function (n, u) { return n + txSum(u, 'expense'); }, 0);
        var byCat = {};
        tx.filter(function (t) { return t.kind === 'expense'; }).forEach(function (t) {
          byCat[t.cat] = (byCat[t.cat] || 0) + t.amount;
        });
        // 存款目標：可支配上限 = 收入 − 目標，支出超過就存不到
        /* 選了某一本帳 → 用那本帳自己的目標；沒選 → 用整體目標。
           這就是「每個月的存錢目標可以有好幾個設定」的意思。 */
        var goal = users.reduce(function (n, u) {
          if (f.groupId && f.groupId !== 'all') return n + goalOf(u, f.groupId);
          var m = memberOf(u);
          return n + (m && m.savingsGoal ? m.savingsGoal : 0);
        }, 0);
        var allow = income - goal;
        var ratio = allow > 0 ? expense / allow : (expense > 0 ? 2 : 0);
        var rule = D.savingsRule;
        var level = ratio >= rule.overAt ? 'over' : (ratio >= rule.warnAt ? 'near' : 'safe');

        /* 近 6 個月、近 3 年：**從明細算**，跟正上方的 KPI 用同一套規則
           （收入只算 earners，支出算全部的人；選了帳本就只算那本帳）。

           ⚠️ 以前是讀一份固定的數列——個人總覽和家庭總覽拿到一模一樣的數字，
           最後一個月跟 KPI 直接矛盾；選了帳本時也只能回 null。 */
        var oneGroup = f.groupId && f.groupId !== 'all';
        function rowFor(prefix) {
          var list = s.transactions.filter(function (t) {
            if (oneGroup && t.group !== f.groupId) return false;
            return users.indexOf(t.user) >= 0 && t.date.indexOf(prefix) === 0;
          });
          return {
            income: sum(list.filter(function (t) { return earners.indexOf(t.user) >= 0; }), 'income'),
            expense: sum(list, 'expense')
          };
        }
        var monthly = [5, 4, 3, 2, 1, 0].map(function (back) {
          var ym = shiftMonth(D.meta.period, -back);
          return Object.assign({ m: ym }, rowFor(ym));
        });
        var thisYear = +D.meta.period.slice(0, 4);
        var yearly = [thisYear - 2, thisYear - 1, thisYear].map(function (y) {
          // 今年還沒過完：畫面要標「未完整」，不然會被拿去跟整年比
          return Object.assign({ y: String(y), partial: y === thisYear }, rowFor(String(y)));
        });

        return {
          period: D.meta.period,
          scope: f.scope || 'me',
          income: income, expense: expense, net: income - expense,
          wardIncome: wardIncome,
          allowance: wards.reduce(function (n, u) {
            return n + allowanceOf(s.me, u);
          }, 0),
          /* 被監管者花掉多少。⚠️ 一樣從明細算——
             原本是「彙總 ＋ 新增的」，但彙總裡已經含新增的了，重複加一次。 */
          wardSpend: wards.reduce(function (n, u) { return n + txSum(u, 'expense'); }, 0),
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
            var cat = catOf(s, c) || { name: '（找不到的分類）', color: 'cat-other' };
            return { cat: c, name: cat.name, color: cat.color, amount: byCat[c] };
          }).sort(function (a, b) { return b.amount - a.amount; }),
          monthly: monthly,
          yearly: yearly,
          members: D.members.filter(function (m) { return users.indexOf(m.id) >= 0; })
            .map(function (m) {
              /* 這個人的數字也一樣從明細算 */
              var inc = txSum(m.id, 'income');
              var exp = txSum(m.id, 'expense');
              var a = inc - (m.savingsGoal || 0);
              var r = a > 0 ? exp / a : (exp > 0 ? 2 : 0);
              return Object.assign(clone(m), {
                income: inc,
                expense: exp,
                allowance: a,
                savingsRatio: r,
                savingsLevel: r >= rule.overAt ? 'over' : (r >= rule.warnAt ? 'near' : 'safe'),
                shortfall: Math.max(0, exp - a)
              });
            })
        };
      });
    },

    transactions: function (f) {
      f = f || {};
      var s = load(), D = global.DATA;
      return sleep(LATENCY).then(function () {
        /* 只認契約上有的篩選參數。
           ⚠️ 這一段是有來由的：前端曾經送 user=U3，而契約寫的是 userId。
           mock 當時默默忽略不認得的參數，所以「篩選沒生效」在 mock 下
           看起來完全正常——直到接上真後端才會發現。寧可現在就吵。 */
        var OK = ['userId', 'groupId', 'from', 'to', 'categoryId', 'kind', 'source', 'q', 'page'];
        Object.keys(f).forEach(function (k) {
          if (OK.indexOf(k) < 0) {
            throw new Error('不認得的篩選參數「' + k + '」，契約上只有：' + OK.join('、'));
          }
        });

        var vis = visibleUsers(s.me);
        var vgs = visibleGroups(s.me);
        var askable = coMembers(s.me).concat(vis);

        /* 帶了 userId 但沒權限看那個人 → 擋下來，不要回空陣列。
           回空陣列的話前端分不出「這個人沒記帳」和「你不能看」。

           ⚠️ 這裡用 askable（監管 ∪ 同帳本）而不是 vis：同帳本的人
              我看得到他在那本帳裡的紀錄，所以查他是合理的——
              只是查到的會只有那一部分，那由 canSeeRow 逐筆決定。 */
        if (f.userId && f.userId !== 'all' && askable.indexOf(f.userId) < 0) {
          var err = new Error('你沒有權限看這個人的紀錄');
          err.status = 403;
          throw err;
        }
        if (f.groupId && f.groupId !== 'all' && vgs.indexOf(f.groupId) < 0) {
          var e2 = new Error('你不在這個群組裡');
          e2.status = 403;
          throw e2;
        }

        var rows = s.transactions.filter(function (t) {
          if (!canSeeRow(t, vis, vgs)) return false;
          if (f.groupId && f.groupId !== 'all' && t.group !== f.groupId) return false;
          if (f.userId && f.userId !== 'all' && t.user !== f.userId) return false;
          /* ⚠️ from／to／categoryId 早就在契約裡、也在上面的白名單裡，
             但以前這裡沒有真的篩——傳了等於沒傳，mock 下看不出來。
             日期是 YYYY-MM-DD 字串，直接比大小就對；兩端都包含。 */
          if (f.from && t.date < f.from) return false;
          if (f.to && t.date > f.to) return false;
          if (f.categoryId && t.cat !== f.categoryId) return false;
          if (f.kind && f.kind !== 'all' && t.kind !== f.kind) return false;
          if (f.source && f.source !== 'all' && (t.source || 'manual') !== f.source) return false;
          if (f.q) {
            var hay = (t.merchant + ' ' + (t.note || '') + ' ' + (t.raw || '')).toLowerCase();
            if (hay.indexOf(f.q.toLowerCase()) < 0) return false;
          }
          return true;
        });
        /* 新的在前。同一天的用記帳先後排——真後端有 created_at，mock 用 id 推 */
        rows.sort(function (a, b) {
          if (a.date !== b.date) return a.date < b.date ? 1 : -1;
          return txOrder(b) - txOrder(a);
        });
        return {
          transactions: rows.map(function (t) {
            var c = catOf(s, t.cat);
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

    /* ★ 自然語言記帳：只解析、不寫入。使用者確認後才呼叫 confirm
       mock 沒有模型，用 parseLine() 的規則頂著——真後端由模型負責，並回每一欄的信心度。 */
    nlpParse: function (text) {
      return sleep(700).then(function () {
        var t = String(text || '').trim();
        if (!t) throw oops('先寫一句話', 422);
        var it = parseLine(t);
        return {
          raw: t, matched: false,
          out: { date: it.date, amount: it.amount || 0, kind: it.kind, cat: it.cat, merchant: it.merchant,
                 conf: it.conf.amount, catConf: it.conf.cat },
          note: 'mock 模式用規則解析。真後端由模型負責，並會回傳每個欄位的信心度。'
        };
      });
    },

    /* ★ 段落解析：一段話可能有好幾筆，模型要先切分再逐筆抽欄位 */
    nlpParseBatch: function (text) {
      return sleep(1100).then(function () {
        var t = String(text || '').trim();
        if (!t) throw oops('先寫一段話', 422);
        var parts = t.split(/[，,。；;、\n]+|(?:然後|接著|還有)/).map(function (x) { return x.trim(); })
          .filter(function (x) { return x.length > 1; });
        var items = parts.map(function (part, i) { return Object.assign({ seq: i + 1, span: part }, parseLine(part)); });
        return {
          raw: t, matched: false, items: items,
          note: 'mock 模式用規則切分與抽欄位。真後端由模型負責，並回傳每一欄的信心度。'
        };
      });
    },

    nlpConfirmBatch: function (items) {
      var s = load();
      return sleep(420).then(function () {
        var g = groupFor(s.me, items[0] && items[0].groupId);
        var made = items.map(function (p, i) {
          return {
            id: stampId('N'), user: s.me, date: p.date,
            amount: Number(p.amount), kind: p.kind, cat: p.cat,
            group: g,
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
          id: stampId('N'), user: s.me, date: p.date, amount: Number(p.amount),
          group: groupFor(s.me, p.groupId),
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
          id: stampId('N'), user: s.me, date: parsed.date, amount: Number(parsed.amount),
          group: groupFor(s.me, parsed.groupId),
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
        var t = s.transactions.filter(function (x) { return x.id === id; })[0];
        if (!t) throw new Error('找不到這筆紀錄');
        /* 監管是唯讀的。看得到不等於改得動 ——
           前端已經不畫刪除鈕了，這裡再擋一次：
           按鈕藏起來不是權限控制，任何人都能自己呼叫這支。
           真後端必須做同樣的檢查（403），不可以只靠前端。 */
        if (t.user !== s.me) throw oops('這是別人的紀錄，你只能檢視', 403);
        if (ledgerLocked(t.group)) throw oops('這本帳已經結算，裡面的紀錄不能再改或刪除', 409);
        dropTx(s, [id]);
        save();
        return { deleted: id };
      });
    },

    /* 一次刪多筆：DELETE /api/transactions?ids=T1,T2
       ⚠️ 全部成功或全部不動。先把每一筆都檢查完，全部過了才刪——
       刪到第三筆才發現第四筆是別人的，前三筆已經不見了，使用者根本不知道哪些被刪。
       ⚠️ 空的清單一定要擋。沒帶 ids 被當成「不篩選」就是整本刪光。
       真後端用 toolkit.ledger.clean_ids／require_editable。 */
    deleteTransactions: function (ids) {
      var s = load();
      return sleep(220).then(function () {
        var list = [];
        (Array.isArray(ids) ? ids : String(ids || '').split(',')).forEach(function (x) {
          var k = String(x).trim();
          if (k && list.indexOf(k) < 0) list.push(k);
        });
        if (!list.length) throw oops('沒有指定要刪哪幾筆', 400);
        if (list.length > MAX_BATCH) throw oops('一次最多刪 ' + MAX_BATCH + ' 筆', 400);
        list.forEach(function (id) {
          var t = s.transactions.filter(function (x) { return x.id === id; })[0];
          if (!t) throw oops('找不到這筆紀錄：' + id, 404);
          if (t.user !== s.me) throw oops('裡面有別人的紀錄，你只能檢視。這次一筆都沒有刪', 403);
          if (ledgerLocked(t.group)) throw oops('裡面有結算過的帳本的紀錄，不能刪。這次一筆都沒有刪', 409);
        });
        dropTx(s, list);
        save();
        return { deleted: list };
      });
    },

    /* 修改一筆：PATCH /api/transactions/{id}，只送要改的欄位。
       ⚠️ 不認得的欄位直接丟錯（source、user 都不能改）。默默忽略的話，
       前端以為改了，畫面上卻沒變，是最難抓的錯。
       真後端用 toolkit.ledger.clean_patch／require_editable；
       改的是模型解析的那筆，要把新值寫進 nlp_parses.user_corrected。 */
    updateTransaction: function (id, p) {
      var s = load(), D = global.DATA;
      return sleep(240).then(function () {
        var t = s.transactions.filter(function (x) { return x.id === id; })[0];
        if (!t) throw oops('找不到這筆紀錄', 404);
        if (t.user !== s.me) throw oops('這是別人的紀錄，你只能檢視', 403);
        if (ledgerLocked(t.group)) throw oops('這本帳已經結算，裡面的紀錄不能再改或刪除', 409);

        p = p || {};
        var keys = Object.keys(p);
        if (!keys.length) throw oops('沒有要改的欄位', 400);
        var unknown = keys.filter(function (k) { return TX_EDITABLE.indexOf(k) < 0; });
        if (unknown.length) throw oops('不認得的欄位：' + unknown.join('、'), 400);

        var next = {};
        if ('amount' in p) {
          var amt = Number(p.amount);
          if (!(amt > 0) || !isFinite(amt)) throw oops('金額要是大於 0 的數字', 400);
          next.amount = amt;
        }
        if ('date' in p) {
          var d = String(p.date || '');
          var dt = new Date(+d.slice(0, 4), +d.slice(5, 7) - 1, +d.slice(8, 10));
          var ok = /^\d{4}-\d{2}-\d{2}$/.test(d) && dt.getMonth() === +d.slice(5, 7) - 1 && dt.getDate() === +d.slice(8, 10);
          if (!ok) throw oops('日期格式要是 YYYY-MM-DD', 400);
          next.date = d;
        }
        if ('kind' in p) {
          if (p.kind !== 'expense' && p.kind !== 'income') throw oops('收支只能是支出或收入', 400);
          next.kind = p.kind;
        }
        if ('cat' in p) next.cat = p.cat;
        ['merchant', 'note'].forEach(function (k) {
          if (!(k in p)) return;
          var v = String(p[k] || '').replace(/\s+/g, ' ').trim();
          if (v.length > 100) throw oops('店家和備註最多 100 個字', 400);
          next[k] = v;
        });
        /* 分類要跟收支方向對得上：支出不能選「薪資」 */
        var kind = next.kind || t.kind, cat = next.cat || t.cat;
        var c = catOf(s, cat);
        if (!c) throw oops('沒有這個分類', 400);
        if (c.kind !== kind) {
          if ('cat' in p) throw oops('「' + c.name + '」是' + (c.kind === 'income' ? '收入' : '支出') + '的分類，跟收支方向對不上', 400);
          /* 只改了收支方向：分類換成那一邊的「其他」，不要留一個對不上的 */
          next.cat = kind === 'income' ? 'I04' : 'C08';
        }
        if ('groupId' in p && !p.groupId) throw oops('要選一本帳本', 400);
        if ('groupId' in p && p.groupId !== t.group) {
          next.group = groupFor(s.me, p.groupId);      // 看不到的帳本、結算過的帳本在這裡擋
          if (next.group !== p.groupId) throw oops('你沒有加入這本帳', 403);
        }

        Object.assign(t, next, { updatedAt: localStamp(new Date()) });
        if (String(t.id).charAt(0) !== 'N') {
          /* 種子紀錄的修改要另外存，重新整理之後才不會變回去（新記的整筆存在 extra 裡） */
          s.txPatch = s.txPatch || {};
          s.txPatch[t.id] = Object.assign(s.txPatch[t.id] || {}, next, { updatedAt: t.updatedAt });
        }
        save();
        var cc = catOf(s, t.cat) || {};
        return Object.assign(clone(t), {
          userName: (memberOf(t.user) || {}).name || '', catName: cc.name || '', catColor: cc.color || ''
        });
      });
    },

    setSavingsGoal: function (userId, goal, groupId) {
      var st = load(), D = global.DATA;
      return sleep(240).then(function () {
        // 設群組目標時不用指定人——設的一定是自己的
        if (!userId) userId = st.me;
        var m = D.members.filter(function (x) { return x.id === userId; })[0];
        if (!m) throw new Error('not found: ' + userId);

        /* 存款目標**只有本人能設**。存多少錢是那個人自己的決定——
           家長可以給零用金、可以看監管對象的紀錄，但不能替他決定要存多少。
           後端用 toolkit/roles.py 的 require_set_goal()。 */
        if (userId !== st.me) {
          var fe = new Error('存款目標只有本人可以設定'); fe.status = 403; throw fe;
        }

        var v = Number(goal);
        if (isNaN(v) || v < 0) throw new Error('存款目標要是 0 以上的數字');

        /* 帶了 groupId = 只設那一本帳的目標；不帶 = 不分群組的整體目標。
           兩者並存：整體目標管全部，群組目標管那本帳自己。 */
        if (groupId) {
          if (visibleGroups(st.me).indexOf(groupId) < 0) {
            var e = new Error('你不在這個群組裡'); e.status = 403; throw e;
          }
          st.goalPatch = (st.goalPatch || []).concat([
            { user: userId, group: groupId, goal: v }
          ]);
          save();
          var g = groupOf(groupId) || {};
          return { userId: userId, groupId: groupId, groupName: g.name, goal: v };
        }

        st.goals[userId] = v;
        applyGoals(st.goals);
        save();
        return clone(m);
      });
    },

    /* ---------------------------------------------------------
       監管通知。真後端是子女寫入時建立通知列，
       這裡用「明細裡有沒有被我監管的人新記的帳」現算，
       形狀跟真的一樣，前端不用改。
       --------------------------------------------------------- */
    notifications: function (f) {
      var s = load(), D = global.DATA;
      f = f || {};
      return sleep(120).then(function () {
        var wards = D.guardianships
          .filter(function (g) { return g.guardian === s.me; })
          .map(function (g) { return g.ward; });

        /* 真後端的 notifications 表有自增 id 跟 created_at，天生就能排序。
           mock 沒有，所以這裡自己算一個時間戳當排序鍵：
             新記的（id = 'N' + Date.now()）→ 直接取那串毫秒
             種子資料（id = 'T1041'）      → 日期 + 流水號（同一天用流水號分先後） */
        function stamp(t) {
          var id = String(t.id);
          if (id.charAt(0) === 'N') return Number(id.slice(1)) || 0;
          return Date.parse(t.date + 'T12:00:00') + (Number(id.replace(/\D/g, '')) || 0);
        }

        /* ---- 提醒型通知 ----------------------------------------
           真後端是「記帳寫入時算一次，跨過門檻就寫一列 notifications」。
           mock 沒有寫入時機，所以這裡用現況反推：
           已經跨過而且還開著的門檻，就算成一則通知。
           形狀跟真的一樣，前端不用改。 */
        var alertRows = myAlerts(s.me)
          .filter(function (a) { return a.enabled; })
          .map(function (a) {
            var scopeTx = s.transactions.filter(function (t) {
              if (t.user !== s.me) return false;
              if (t.date.indexOf(D.meta.period) !== 0) return false;
              return a.group ? t.group === a.group : true;
            });
            var spent = scopeTx.filter(function (t) { return t.kind === 'expense'; })
              .reduce(function (n, t) { return n + t.amount; }, 0);
            var income = scopeTx.filter(function (t) { return t.kind === 'income'; })
              .reduce(function (n, t) { return n + t.amount; }, 0);
            var me = memberOf(s.me) || {};
            var goal = a.group ? goalOf(s.me, a.group) : (me.savingsGoal || 0);
            var allow = income - goal;
            var pct = allow > 0 ? Math.floor(spent / allow * 100) : (spent > 0 ? 200 : 0);
            if (pct < a.percent) return null;               // 還沒跨過
            var g = a.group ? groupOf(a.group) : null;

            /* 門檻是「造成跨越的那筆記帳」當下才響的，不是月初。
               用那個範圍裡最後一筆的日期當時間，通知才會排在合理的位置，
               也不會顯示成「11 天前」。 */
            var lastAt = scopeTx.reduce(function (mx, t) {
              var ts = String(t.id).charAt(0) === 'N'
                ? Number(String(t.id).slice(1))
                : Date.parse(t.date + 'T20:00:00');
              return Math.max(mx, ts || 0);
            }, 0);
            var when = lastAt || alertTs(a);
            return {
              id: 'NA' + a.id + D.meta.period,
              type: 'budget_alert',
              actorId: null,
              actorName: null,
              percent: a.percent,
              reached: pct,
              groupId: a.group,
              groupName: g ? g.name : '整體',
              spent: spent,
              allowance: allow,
              createdAt: new Date(when).toISOString(),
              readAt: (s.readNotify || []).indexOf('NA' + a.id + D.meta.period) >= 0
                ? new Date().toISOString() : null,
              _ts: when + a.percent
            };
          })
          .filter(Boolean);

        /* ⚠️ 這裡**故意只看監管關係，不看帳本**——監管是跨帳本無條件的。
           以前明細是交集、通知是單軸，兩邊對不起來：監管對象記在一本
           我沒加入的帳，我會收到一則點進去卻看不到東西的通知。
           現在明細也是聯集，兩邊一致了。 */
        var rows = s.transactions
          .filter(function (t) { return wards.indexOf(t.user) >= 0; })
          .map(function (t) {
            var m = memberOf(t.user) || {};
            var c = catOf(s, t.cat) || {};
            var ts = stamp(t);
            return {
              id: 'NT' + t.id,
              type: 'ward_transaction',
              actorId: t.user,
              actorName: m.name || '',
              txId: t.id,
              amount: t.amount,
              cat: t.cat,
              catName: c.name || '',
              merchant: t.merchant || '',
              createdAt: new Date(ts).toISOString(),
              readAt: (s.readNotify || []).indexOf('NT' + t.id) >= 0
                ? new Date().toISOString() : null,
              _ts: ts
            };
          })
          .concat(alertRows)
          .sort(function (a, b) { return a._ts - b._ts; })   // 由舊到新
          .slice(-20);                                       // 只留最近 20 筆

        // unread 要用「全部」算，不是用這次回傳的那幾筆算。
        // 用分頁後的算，第二次輪詢帶 since 回 0 筆時紅點就被清掉了。
        var unread = rows.filter(function (r) { return !r.readAt; }).length;

        // maxId 是「最新的那筆」。rows 是由舊到新，所以取最後一個。
        // 這裡很容易寫反：如果清單是由新到舊，取 last 會拿到最舊的，
        // 下次帶 since 就永遠切不到新紀錄，新通知永遠進不了清單。
        var maxId = rows.length ? rows[rows.length - 1].id : (f.since || null);

        // since 之後（更新）的才回，跟真後端的 WHERE id > :since 一樣
        if (f.since) {
          var cut = rows.filter(function (r) { return r.id === f.since; })[0];
          if (cut) rows = rows.filter(function (r) { return r._ts > cut._ts; });
        }
        if (f.unreadOnly) rows = rows.filter(function (r) { return !r.readAt; });

        // 回給前端時改成由新到舊，畫面上最新的排最上面
        rows = rows.slice().reverse().map(function (r) {
          var o = clone(r); delete o._ts; return o;
        });
        return { notifications: rows, unread: unread, maxId: maxId };
      });
    },

    readNotification: function (id) {
      var s = load();
      return sleep(80).then(function () {
        s.readNotify = s.readNotify || [];
        if (s.readNotify.indexOf(id) < 0) s.readNotify.push(id);
        save();
        return { id: id, readAt: new Date().toISOString() };
      });
    },

    /* 整批已讀：只標到 readUntil 那一則（含）為止。
       按下「全部已讀」的瞬間剛好進來的新通知不能一起被標掉——使用者根本沒看到它。 */
    readNotifications: function (untilId) {
      if (!untilId) return Promise.reject(oops('要帶 readUntil（按下去當時最新的那一則）', 400));
      return mock.notifications({}).then(function (res) {
        var s = load();
        s.readNotify = s.readNotify || [];
        var ids = res.notifications.map(function (r) { return r.id; });   // 由新到舊
        var from = ids.indexOf(untilId);
        var updated = 0;
        res.notifications.slice(from < 0 ? 0 : from).forEach(function (r) {
          if (r.readAt || s.readNotify.indexOf(r.id) >= 0) return;
          s.readNotify.push(r.id);
          updated++;
        });
        save();
        return { updated: updated, unread: Math.max(0, res.unread - updated) };
      });
    },

    /* 預算：上限來自設定，**已花多少一律從明細現算**。
       帶 groupId 時只算那一本帳裡的花費，跟同一頁的「本月支出」一致。 */
    budgets: function (f) {
      f = f || {};
      var s = load(), D = global.DATA;
      return sleep(LATENCY).then(function () {
        var vis = visibleUsers(s.me);
        var one = f.groupId && f.groupId !== 'all';
        function used(uid, cat) {
          return sum(s.transactions.filter(function (t) {
            return t.user === uid && t.cat === cat && t.date.indexOf(D.meta.period) === 0 &&
              (!one || t.group === f.groupId);
          }), 'expense');
        }
        return {
          budgets: (s.budgets || []).filter(function (b) { return vis.indexOf(b.user) >= 0 && b.period === 'month'; })
            .map(function (b) {
              var c = catOf(s, b.cat) || { name: '（找不到的分類）', color: 'cat-other' };
              var u = used(b.user, b.cat);
              return Object.assign(clone(b), {
                used: u,
                userName: memberOf(b.user).name, catName: c.name, catColor: c.color,
                over: u > b.limit, pct: b.limit ? u / b.limit : 0
              });
            }).sort(function (a, b) { return b.pct - a.pct; })
        };
      });
    },

    /* 設定預算：PUT /api/budgets。只能設自己的；limit 0 = 拿掉這個分類的預算 */
    setBudget: function (p) {
      var s = load(); p = p || {};
      return sleep(220).then(function () {
        var c = catOf(s, p.cat);
        if (!c || c.kind !== 'expense') throw oops('預算只能設在支出分類', 400);
        var v = Number(p.limit);
        if (!isFinite(v) || v < 0) throw oops('預算要是 0 以上的數字', 422);
        var period = p.period || 'month';
        if (period !== 'month' && period !== 'year') throw oops('period 只能是 month 或 year', 400);
        s.budgets = (s.budgets || []).filter(function (b) {
          return !(b.user === s.me && b.cat === p.cat && b.period === period);
        });
        if (v > 0) s.budgets.push({ user: s.me, period: period, cat: p.cat, limit: v });
        save();
        return v > 0
          ? { user: s.me, period: period, cat: p.cat, limit: v, catName: c.name }
          : { user: s.me, period: period, cat: p.cat, limit: 0, deleted: true, catName: c.name };
      });
    },

    advices: function (f) {
      f = f || {};
      var s = load(), D = global.DATA;
      return sleep(LATENCY).then(function () {
        var vis = visibleUsers(s.me);
        /* scope: 'me'     只有寫給我本人的
                  'family' 全家的建議 ＋ 我監管的人的個人建議（家長才有）
           ⚠️ 子女不會拿到全家的建議——那幾則是寫給家長看的，裡面會點名。 */
        var fam = f.scope === 'family' && vis.length > 1;
        var rows = D.advices.concat(s.advices || []).filter(function (a) {
          if (a.scope === 'family') return fam;
          if (a.user === s.me) return !fam;
          return fam && vis.indexOf(a.user) >= 0;
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

    /* 產生這個月的財務建議：POST /api/advices/generate
       真後端：analytics 先從資料庫算好數字 → 餵給模型「只做敘述」→ Pydantic 驗證 → 存進 advices。
       mock 沒有模型，用規則把**同一批數字**寫成句子。數字一律從明細算，跟統計頁同一個來源。 */
    generateAdvices: function (p) {
      p = p || {};
      var s = load(), D = global.DATA;
      var scope = p.scope === 'family' ? 'family' : 'me';
      var me = memberOf(s.me) || {};
      if (scope === 'family' && !(isParentOf(s, me.familyId) && visibleUsers(s.me).length > 1)) {
        return Promise.reject(oops('全家的建議只有家長、而且照看著家人時才能產生', 403));
      }
      return Promise.all([mock.summary({ scope: scope }), mock.budgets({})]).then(function (r) {
        return sleep(700).then(function () {
          var sm = r[0], bd = r[1].budgets || [];
          var period = D.meta.period, who = scope === 'family' ? null : s.me;
          var built = buildAdvices(sm, bd, scope, s.me, period);
          var out = built.advices, head = built.head;
          // 同一個月、同一個範圍再產生一次：蓋掉舊的，不要疊出兩份
          s.advices = (s.advices || []).filter(function (a) {
            return !(a.period === period && a.scope === head.scope && (a.user || null) === who);
          }).concat(out);
          save();
          return {
            generatedAt: head.generatedAt,
            advices: out.map(function (a) { return Object.assign(clone(a), { userName: a.user ? memberOf(a.user).name : null }); })
          };
        });
      });
    },

    members: function () {
      var s = load(), D = global.DATA;
      return sleep(LATENCY).then(function () {
        /* 名字、角色、監管關係是公開的——被監管的人必須知道自己被誰看著，
           所以這張表不能藏。但「存款目標」是個人財務資料，
           看不到那個人的就不要送過去。⚠️ 後端也要這樣做：
           前端把欄位藏起來不算保護，資料根本不該離開伺服器。 */
        var vis = visibleUsers(s.me);
        var me = memberOf(s.me) || {};
        var fam = familyOf(s.me);
        return {
          me: s.me,
          myRole: me.role || null,
          family: fam ? { id: fam.id, name: fam.name, createdBy: fam.createdBy } : null,
          visible: vis,
          queryable: queryableUsers(s.me),
          /* 只列**同一個家庭**的人；還沒有家庭就只有自己。
             ⚠️ 平台管理員不屬於任何家庭，不可以出現在這裡——漏過一次，
             帳本的加人清單能把他加進來，等於讓平台管理員讀到那本帳。 */
          members: D.members.filter(function (m) {
            if (m.isPlatformAdmin) return false;
            return fam ? m.familyId === fam.id : m.id === s.me;
          }).map(function (m) {
            var o = clone(m);
            if (vis.indexOf(m.id) < 0) {
              delete o.savingsGoal;
              delete o.income;
              delete o.expense;
              delete o.budget;
            }
            return o;
          }),
          roles: clone(D.roles),
          guardianships: D.guardianships.filter(function (g) {
            return fam && (memberOf(g.guardian) || {}).familyId === fam.id;
          }).map(function (g) {
            return Object.assign(clone(g), {
              id: gsId(g),
              guardianName: memberOf(g.guardian).name,
              wardName: memberOf(g.ward).name
            });
          }),
          permissions: clone(D.permissions)
        };
      });
    },

    /* ---------------------------------------------------------
       家庭綁定
       --------------------------------------------------------- */

    /* 建立家庭。建立的人成為家長。已經在家庭裡就不行。 */
    createFamily: function (p) {
      var s = load(); p = p || {};
      return sleep(280).then(function () {
        var me = memberOf(s.me);
        if (me.isPlatformAdmin) throw oops('平台管理員不屬於任何家庭', 403);
        if (me.familyId) throw oops('你已經在一個家庭裡了', 409);
        var name = String(p.name || '').replace(/\s+/g, ' ').trim().slice(0, 20);
        if (!name) throw oops('幫你的家庭取個名字，例如「林家」');
        var f = { id: 'F' + (allFamilies().length + 1) + '-' + Date.now().toString(36),
                  name: name, createdBy: s.me, createdAt: todayStr() };
        s.newFamilies = (s.newFamilies || []).concat([f]);
        setMembership(s, s.me, f.id, 'parent');
        pushAudit(s, 'create_family', null, '建立「' + name + '」');
        save();
        return { family: clone(f), role: 'parent' };
      });
    },

    /* 產生邀請碼。⚠️ 身分由家長決定，拿到碼的人不能自己選。
       同一個身分再產生一次，舊的那組就作廢——「重新產生」就是這個意思。 */
    createInviteCode: function (p) {
      var s = load(); p = p || {};
      return sleep(240).then(function () {
        var me = memberOf(s.me);
        if (!isParentOf(s, me.familyId)) throw oops('只有家長可以邀請家人', 403);
        if (p.role !== 'parent' && p.role !== 'child') throw oops('身分只能是家長或子女');
        (s.codes || []).forEach(function (c) {
          if (c.familyId === me.familyId && c.role === p.role && c.status === 'pending') c.status = 'cancelled';
        });
        var row = { id: stampId('K'), familyId: me.familyId, role: p.role, code: newCode(),
                    createdBy: s.me, status: 'pending', expiresAt: daysLater(INVITE_DAYS) };
        s.codes = (s.codes || []).concat([row]);
        save();
        return { code: row.code, role: row.role, expiresAt: row.expiresAt };
      });
    },

    /* 用邀請碼加入。碼只能用一次。 */
    joinFamily: function (p) {
      var s = load(); p = p || {};
      return sleep(300).then(function () {
        var me = memberOf(s.me);
        if (me.isPlatformAdmin) throw oops('平台管理員不屬於任何家庭', 403);
        if (me.familyId) throw oops('你已經在一個家庭裡了', 409);
        var want = normCode(p.code);
        if (want.length !== 8) throw oops('邀請碼是 8 個字，例如 K7QM-3XWP');
        var row = (s.codes || []).filter(function (c) { return normCode(c.code) === want; })[0];
        if (!row) throw oops('找不到這組邀請碼，確認一下有沒有打錯', 404);
        if (row.status === 'used') throw oops('這組邀請碼已經用過了');
        if (row.status !== 'pending') throw oops('這組邀請碼已經失效，請家人重新產生一組');
        if (expired(row)) throw oops('這組邀請碼已經過期了，請家人重新產生一組');
        if (!hasParent(row.familyId)) throw oops('這個家目前沒有家長，暫時不能加入。請家人重新建立家庭再邀請你', 409);
        row.status = 'used'; row.usedBy = s.me;
        setMembership(s, s.me, row.familyId, row.role);
        var fam = familyById(row.familyId);
        pushAudit(s, 'join_family', s.me, '用邀請碼加入「' + fam.name + '」');
        save();
        return { family: { id: fam.id, name: fam.name }, role: row.role };
      });
    },

    /* 用帳號找人。⚠️ 只接受完整的 email，不做模糊搜尋；
       找到了也只回名字與頭像，不回任何財務資料。
       在別的家庭、或是平台管理員，一律只說「目前不能邀請」，不說原因。 */
    lookupUser: function (email) {
      var s = load();
      return sleep(260).then(function () {
        var me = memberOf(s.me);
        if (!isParentOf(s, me.familyId)) throw oops('只有家長可以邀請家人', 403);
        var mail = String(email || '').trim().toLowerCase();
        if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(mail)) throw oops('請輸入完整的 email');
        var u = global.DATA.members.filter(function (m) {
          return String(m.email || '').toLowerCase() === mail;
        })[0];
        if (!u) throw oops('找不到這個帳號', 404);
        var pending = (s.invites || []).some(function (i) {
          return i.invitee === u.id && i.familyId === me.familyId && i.status === 'pending' && !expired(i);
        });
        var status = u.isPlatformAdmin ? 'unavailable'
          : (u.familyId && u.familyId === me.familyId) ? 'member'
          : u.familyId ? 'unavailable'
          : pending ? 'invited' : 'available';
        return {
          user: { id: u.id, name: u.name, avatar: u.avatar, avatarUrl: u.avatarUrl || null },
          status: status
        };
      });
    },

    /* 用帳號邀請。對方會在自己的畫面上看到邀請，按「加入」才算數。 */
    sendInvite: function (p) {
      var s = load(); p = p || {};
      return sleep(280).then(function () {
        var me = memberOf(s.me);
        if (!isParentOf(s, me.familyId)) throw oops('只有家長可以邀請家人', 403);
        if (p.role !== 'parent' && p.role !== 'child') throw oops('身分只能是家長或子女');
        var u = memberOf(p.userId);
        if (!u || u.isPlatformAdmin || u.familyId) throw oops('這個帳號目前不能邀請');
        var dup = (s.invites || []).some(function (i) {
          return i.invitee === u.id && i.familyId === me.familyId && i.status === 'pending' && !expired(i);
        });
        if (dup) throw oops('已經邀請過了，等對方回覆就好', 409);
        var row = { id: stampId('I'), familyId: me.familyId, inviter: s.me, invitee: u.id,
                    role: p.role, status: 'pending', createdAt: new Date().toISOString(),
                    expiresAt: daysLater(INVITE_DAYS) };
        s.invites = (s.invites || []).concat([row]);
        pushAudit(s, 'invite_member', u.id, '邀請' + u.name + '成為' + (p.role === 'parent' ? '家長' : '子女'));
        save();
        return { id: row.id, status: 'pending' };
      });
    },

    /* 我收到的邀請、我們家送出去還沒回覆的、我們家還有效的邀請碼 */
    invites: function () {
      var s = load();
      return sleep(200).then(function () {
        var me = memberOf(s.me);
        var parent = isParentOf(s, me.familyId);
        var live = function (r) { return r.status === 'pending' && !expired(r); };
        return {
          received: (s.invites || []).filter(function (i) { return i.invitee === s.me && live(i); })
            .map(function (i) {
              var f = familyById(i.familyId) || {}, who = memberOf(i.inviter) || {};
              return { id: i.id, familyName: f.name, inviterName: who.name, role: i.role, expiresAt: i.expiresAt };
            }),
          sent: parent ? (s.invites || []).filter(function (i) { return i.familyId === me.familyId && live(i); })
            .map(function (i) {
              var u = memberOf(i.invitee) || {};
              return { id: i.id, name: u.name, email: u.email, avatar: u.avatar, role: i.role, expiresAt: i.expiresAt };
            }) : [],
          codes: parent ? (s.codes || []).filter(function (c) { return c.familyId === me.familyId && live(c); })
            .map(function (c) { return { code: c.code, role: c.role, expiresAt: c.expiresAt }; }) : []
        };
      });
    },

    acceptInvite: function (id) {
      var s = load();
      return sleep(300).then(function () {
        var me = memberOf(s.me);
        var row = (s.invites || []).filter(function (i) { return i.id === id; })[0];
        if (!row || row.invitee !== s.me) throw oops('找不到這個邀請', 404);
        if (row.status !== 'pending') throw oops('這個邀請已經處理過了');
        if (expired(row)) throw oops('這個邀請已經過期了，請家人重新邀請一次');
        if (me.familyId) throw oops('你已經在一個家庭裡了', 409);
        if (!hasParent(row.familyId)) throw oops('這個家目前沒有家長，暫時不能加入', 409);
        row.status = 'accepted'; row.respondedAt = new Date().toISOString();
        setMembership(s, s.me, row.familyId, row.role);
        var fam = familyById(row.familyId);
        pushAudit(s, 'join_family', s.me, '接受邀請加入「' + fam.name + '」');
        save();
        return { family: { id: fam.id, name: fam.name }, role: row.role };
      });
    },

    /* 家長把**子女**移出家庭。
       ⚠️ 家長不能移除另一位家長——另一位家長只能自己退出，
          不然兩個人吵架時，一方就能把另一方踢出家門。 */
    removeMember: function (uid) {
      var s = load();
      return sleep(300).then(function () {
        var me = memberOf(s.me), who = memberOf(uid);
        if (!isParentOf(s, me.familyId)) throw oops('只有家長可以移除成員', 403);
        if (!who || who.familyId !== me.familyId) throw oops('這個家庭裡沒有這個人', 404);
        if (uid === s.me) throw oops('要離開請用「退出家庭」');
        if (who.role !== 'child') throw oops('另一位家長只能自己退出，不能被移除', 403);
        var fam = familyById(me.familyId);
        var r = detachFromFamily(s, uid);
        pushAudit(s, 'remove_member', uid, '把' + who.name + '移出「' + fam.name + '」');
        save();
        return { id: uid, removed: true, endedGuardianships: r.ended };
      });
    },

    /* 自己退出家庭。任何人都可以——這是自由意願。
       ⚠️ 唯一的家長不能在家裡還有其他人的時候退出，孩子會留在一個沒有人能管理的家。 */
    leaveFamily: function () {
      var s = load();
      return sleep(300).then(function () {
        var me = memberOf(s.me);
        if (!me.familyId) throw oops('你目前沒有加入任何家庭');
        var fam = familyById(me.familyId);
        var others = global.DATA.members.filter(function (x) { return x.familyId === me.familyId && x.id !== s.me; });
        var otherParents = others.filter(function (x) { return x.role === 'parent'; });
        if (me.role === 'parent' && !otherParents.length && others.length) {
          throw oops('你是這個家唯一的家長。先邀請另一位家長，或把其他成員移出，才能退出', 409);
        }
        detachFromFamily(s, s.me);
        pushAudit(s, 'leave_family', s.me, '退出「' + fam.name + '」');
        save();
        return { left: true, family: { id: fam.id, name: fam.name } };
      });
    },

    /* 監管關係：GET /api/guardianships。同一個家庭的都列出來——
       ⚠️ 監管必須雙向可見，被照看的人一定看得到是誰在看。 */
    guardianships: function () {
      var s = load(), D = global.DATA;
      return sleep(160).then(function () {
        var fam = familyOf(s.me);
        return {
          guardianships: D.guardianships.filter(function (g) {
            return fam && (memberOf(g.guardian) || {}).familyId === fam.id;
          }).map(function (g) {
            return Object.assign(clone(g), { id: gsId(g), guardianName: memberOf(g.guardian).name,
              wardName: memberOf(g.ward).name, mine: g.guardian === s.me });
          })
        };
      });
    },

    /* 開始照看一個孩子：POST /api/guardianships { wardId }。監管人一定是自己——
       ⚠️ 不能替別的家長建立監管，那等於替他決定要看誰。 */
    createGuardianship: function (p) {
      var s = load(); p = p || {};
      return sleep(240).then(function () {
        var me = memberOf(s.me), ward = memberOf(p.wardId);
        if (!isParentOf(s, me.familyId)) throw oops('只有家長可以照看家人', 403);
        if (p.guardianId && p.guardianId !== s.me) throw oops('只能設定「我」照看誰，不能替別的家長設定', 403);
        if (!ward || ward.familyId !== me.familyId) throw oops('這個家庭裡沒有這個人', 404);
        if (ward.role !== 'child') throw oops('只能照看子女；家長之間本來就看得到彼此', 422);
        if (global.DATA.guardianships.some(function (g) { return g.guardian === s.me && g.ward === ward.id; })) {
          throw oops('你已經在照看' + ward.name + '了', 409);
        }
        var row = { id: stampId('GS'), guardian: s.me, ward: ward.id, since: todayStr(), scope: '全部明細' };
        s.newGuardians = (s.newGuardians || []).concat([row]);
        global.DATA.guardianships.push(clone(row));
        pushAudit(s, 'grant_guardianship', ward.id, '開始照看' + ward.name);
        save();
        return Object.assign(clone(row), { guardianName: me.name, wardName: ward.name, mine: true });
      });
    },

    /* 解除監管：DELETE /api/guardianships/{id}。監管人自己，或同一個家庭的其他家長 */
    endGuardianship: function (id) {
      var s = load();
      return sleep(240).then(function () {
        var g = global.DATA.guardianships.filter(function (x) { return gsId(x) === id; })[0];
        if (!g) throw oops('找不到這個監管關係', 404);
        var me = memberOf(s.me), ward = memberOf(g.ward) || {};
        if (g.guardian !== s.me && !isParentOf(s, ward.familyId)) throw oops('只有家長可以解除監管', 403);
        endGuardians(s, [g]);
        pushAudit(s, 'end_guardianship', g.ward, (g.guardian === s.me ? '停止照看' : '解除' + memberOf(g.guardian).name + '對') + (ward.name || '') + (g.guardian === s.me ? '' : '的監管'));
        save();
        return { id: id, ended: true };
      });
    },

    /* 改角色：PATCH /api/family/members/{id} { role }
       · 家長可以把子女設為家長
       · 家長可以把**自己**改成子女，但家裡要還有別的家長
       · ⚠️ 不能把另一位家長降成子女——那跟「移除另一位家長」是同一件事 */
    changeMemberRole: function (uid, role) {
      var s = load();
      return sleep(260).then(function () {
        var me = memberOf(s.me), who = memberOf(uid);
        if (!isParentOf(s, me.familyId)) throw oops('只有家長可以改角色', 403);
        if (!who || who.familyId !== me.familyId) throw oops('這個家庭裡沒有這個人', 404);
        if (role !== 'parent' && role !== 'child') throw oops('角色只能是家長或子女', 422);
        if (who.role === role) return { id: uid, role: role, changed: false };
        var parents = global.DATA.members.filter(function (x) { return x.familyId === me.familyId && x.role === 'parent'; });
        if (role === 'child') {
          if (uid !== s.me) throw oops('不能把另一位家長改成子女，他只能自己調整', 403);
          if (parents.length < 2) throw oops('你是唯一的家長，先把另一位家人設為家長', 409);
          endGuardians(s, global.DATA.guardianships.filter(function (g) { return g.guardian === uid; }));
        } else {
          // 設為家長：他被照看的關係一起結束（家長之間本來就看得到）
          endGuardians(s, global.DATA.guardianships.filter(function (g) { return g.ward === uid; }));
        }
        setMembership(s, uid, me.familyId, role);
        pushAudit(s, 'change_role', uid, '把' + who.name + '設為' + (role === 'parent' ? '家長' : '子女'));
        save();
        return { id: uid, role: role, changed: true };
      });
    },

    /* 解散家庭：DELETE /api/family
       · 只有家長，而且**是唯一的家長**——還有別的家長時，一個人不能替另一位家長決定解散，
         你可以自己退出（家裡還有別的家長，退出不會卡住）
       · 每個人都離開家庭：監管關係、零用金結束，家人之間的帳本互相移出，邀請與邀請碼作廢
       · ⚠️ **紀錄一筆都不刪**，每一筆仍在記帳的人自己的收支明細裡 */
    dissolveFamily: function () {
      var s = load();
      return sleep(320).then(function () {
        var me = memberOf(s.me);
        if (!me.familyId) throw oops('你目前沒有加入任何家庭', 404);
        if (!isParentOf(s, me.familyId)) throw oops('只有家長可以解散家庭', 403);
        var famId = me.familyId, fam = familyById(famId);
        var people = global.DATA.members.filter(function (x) { return x.familyId === famId; });
        var others = people.filter(function (x) { return x.role === 'parent' && x.id !== s.me; });
        if (others.length) {
          throw oops('家裡還有其他家長（' + others.map(function (x) { return x.name; }).join('、') + '），不能一個人解散。你可以自己退出家庭', 409);
        }
        people.filter(function (x) { return x.id !== s.me; }).forEach(function (x) { detachFromFamily(s, x.id); });
        detachFromFamily(s, s.me);
        (s.invites || []).forEach(function (i) { if (i.familyId === famId && i.status === 'pending') i.status = 'cancelled'; });
        (s.codes || []).forEach(function (c) { if (c.familyId === famId && c.status === 'pending') c.status = 'cancelled'; });
        s.dissolved = (s.dissolved || []).concat([famId]);
        pushAudit(s, 'dissolve_family', null, '解散「' + fam.name + '」（' + people.length + ' 人離開）');
        save();
        return { dissolved: true, family: { id: famId, name: fam.name }, released: people.length };
      });
    },

    /* 被邀請的人婉拒，或是發邀請那一家的家長取消 */
    declineInvite: function (id) {
      var s = load();
      return sleep(240).then(function () {
        var row = (s.invites || []).filter(function (i) { return i.id === id; })[0];
        if (!row || row.status !== 'pending') throw oops('找不到這個邀請', 404);
        if (row.invitee === s.me) row.status = 'declined';
        else if (isParentOf(s, row.familyId)) row.status = 'cancelled';
        else throw oops('這個邀請不是給你的', 403);
        row.respondedAt = new Date().toISOString();
        save();
        return { id: row.id, status: row.status };
      });
    },


    categories: function () {
      var s = load();
      return sleep(120).then(function () { return { categories: clone(allCats(s)) }; });
    },

    /* 新增家庭自訂分類：POST /api/categories。家長才能加，全家共用 */
    createCategory: function (p) {
      var s = load(); p = p || {};
      return sleep(220).then(function () {
        var me = memberOf(s.me);
        if (!isParentOf(s, me.familyId)) throw oops('只有家長可以新增家庭的分類', 403);
        var name = String(p.name || '').replace(/\s+/g, ' ').trim();
        if (!name || name.length > 10) throw oops('分類名稱要 1～10 個字', 422);
        if (p.kind !== 'expense' && p.kind !== 'income') throw oops('要選支出或收入', 422);
        if (allCats(s).some(function (c) { return c.kind === p.kind && c.name === name; })) {
          throw oops('已經有「' + name + '」這個分類了', 409);
        }
        var c = { id: stampId('CX'), name: name, kind: p.kind, color: 'cat-other',
                  icon: name.charAt(0), familyId: me.familyId, custom: true };
        s.customCategories = (s.customCategories || []).concat([c]);
        save();
        return clone(c);
      });
    },


    reset: function () {
      try { localStorage.removeItem(KEY); } catch (e) {}
      applyGoals(null);
      state = null;
      return sleep(120).then(function () { return { reset: true }; });
    }
  };

  /* 登入閘：mock 也跟真後端一樣，沒登入就 401。
     ⚠️ 沒有這一層的話，登出之後某個畫面還在打 API，mock 會拿著 me = null 往下跑，
     錯在「讀不到 null 的 name」這種看不出原因的地方。 */
  var MOCK_PUBLIC = ['authState', 'login', 'register', 'logout', 'requestPasswordReset', 'confirmPasswordReset', 'reset'];
  Object.keys(mock).forEach(function (name) {
    if (MOCK_PUBLIC.indexOf(name) >= 0) return;
    var fn = mock[name];
    mock[name] = function () {
      var st = load();
      if (!st.auth || !st.auth.loggedIn || !memberOf(st.me)) return Promise.reject(oops('請先登入', 401));
      return fn.apply(mock, arguments);
    };
  });

  /* ============================================================
     http 轉接器
     ============================================================ */
  /* ------------------------------------------------------------
     token 保管
     ------------------------------------------------------------
     放 localStorage：重新整理不會掉，而且我們的 API 吃 Bearer 標頭，
     不吃 cookie —— 所以不需要處理 CSRF，也不用送 credentials。

     ⚠️ localStorage 擋不住 XSS。真正的防線是「不要有 XSS」：
        所有使用者輸入都要 esc() 過再塞進 innerHTML。
     ------------------------------------------------------------ */
  var TOK = 'fambudget.auth';

  function tokens() {
    try { return JSON.parse(localStorage.getItem(TOK) || 'null'); } catch (e) { return null; }
  }
  function setTokens(t) {
    try {
      if (t) localStorage.setItem(TOK, JSON.stringify(t));
      else localStorage.removeItem(TOK);
    } catch (e) {}
  }

  var refreshing = null;          // 同時只跑一次續期，見 doRefresh()

  function send(path, opt) {
    opt = opt || {};
    var h = { 'Content-Type': 'application/json' };
    var t = tokens();
    if (t && t.accessToken) h.Authorization = 'Bearer ' + t.accessToken;
    return fetch(BASE + path, {
      method: opt.method || 'GET',
      headers: h,
      body: opt.body ? JSON.stringify(opt.body) : undefined
    });
  }

  /* 後端寫的錯誤訊息比「HTTP 422」有用得多，盡量把它挖出來給使用者看 */
  function fail(r, path) {
    return r.text().then(function (txt) {
      var msg = '';
      try {
        var j = JSON.parse(txt);
        msg = j.detail || j.message || '';
        // FastAPI 的 422 會回一個陣列，直接顯示不好看，取第一條就好
        if (msg && typeof msg !== 'string') {
          msg = (msg[0] && (msg[0].msg || msg[0].detail)) || JSON.stringify(msg);
        }
      } catch (e) {}
      var err = new Error(msg || ('HTTP ' + r.status + ' ' + path));
      err.status = r.status;
      throw err;
    });
  }

  var NO_RETRY = ['/api/auth/login', '/api/auth/register', '/api/auth/refresh'];

  function req(path, opt, retried) {
    return send(path, opt).then(function (r) {
      /* 401 → 自動換新的 access token，再把剛才那個請求重送一次。
         沒有這段的話，access token 30 分鐘一到，使用者就被踢出去一次。 */
      if (r.status === 401 && !retried && NO_RETRY.indexOf(path.split('?')[0]) < 0) {
        return doRefresh().then(function () { return req(path, opt, true); });
      }
      if (!r.ok) return fail(r, path);
      return r.status === 204 ? null : r.json();
    });
  }

  function doRefresh() {
    /* 一次載入會同時發好幾個請求，token 過期時它們會一起收到 401。
       沒有這個閘的話會同時打好幾次 /refresh —— 而 refresh token 是
       一次性的（後端換發新的、撤銷舊的），慢的那幾個就會拿著被撤銷的
       token 去換，全部失敗，使用者被登出。 */
    if (refreshing) return refreshing;

    var t = tokens();
    if (!t || !t.refreshToken) return Promise.reject(new Error('尚未登入'));

    refreshing = send('/api/auth/refresh', {
      method: 'POST', body: { refreshToken: t.refreshToken }
    }).then(function (r) {
      if (!r.ok) { setTokens(null); return fail(r, '/api/auth/refresh'); }
      return r.json();
    }).then(function (d) {
      setTokens({
        accessToken: d.accessToken,
        refreshToken: d.refreshToken || t.refreshToken
      });
      refreshing = null;
      return d;
    }, function (e) {
      refreshing = null;
      setTokens(null);
      throw e;
    });
    return refreshing;
  }
  function qs(f) {
    var p = Object.keys(f || {})
      .filter(function (k) { var v = f[k]; return v !== undefined && v !== null && v !== '' && v !== 'all'; })
      .map(function (k) { return encodeURIComponent(k) + '=' + encodeURIComponent(f[k]); });
    return p.length ? '?' + p.join('&') : '';
  }

  function keep(d) {
    if (d && d.accessToken) {
      setTokens({ accessToken: d.accessToken, refreshToken: d.refreshToken });
    }
    return d;
  }

  var http = {
    me:                function ()      { return req('/api/auth/me'); },

    /* ---- 認證 ---------------------------------------------------
       login／register 成功之後要把 token 存起來，
       之後每個請求由 send() 自動帶上 Authorization 標頭。
       ------------------------------------------------------------ */
    authState:         function ()      {
      var t = tokens();
      return Promise.resolve({ loggedIn: !!(t && t.accessToken) });
    },
    login:             function (c)     {
      return req('/api/auth/login', { method: 'POST', body: c }).then(keep);
    },
    register:          function (p)     {
      return req('/api/auth/register', { method: 'POST', body: p }).then(keep);
    },
    logout:            function ()      {
      var t = tokens();
      // 先叫後端撤銷 refresh token，不管成不成功，本機的一定要清掉
      return req('/api/auth/logout', {
        method: 'POST', body: { refreshToken: t && t.refreshToken }
      }).catch(function () {}).then(function () {
        setTokens(null);
        return { ok: true };
      });
    },
    updateProfile:     function (p)     { return req('/api/auth/me', { method: 'PATCH', body: p }); },
    uploadAvatar:      function (d)     { return req('/api/auth/me/avatar', { method: 'PUT', body: { image: d } }); },
    deleteAvatar:      function ()      { return req('/api/auth/me/avatar', { method: 'DELETE' }); },
    financeProfile:    function ()      { return req('/api/auth/me/finance'); },
    setFinanceProfile: function (p)     { return req('/api/auth/me/finance', { method: 'PUT', body: p }); },
    changePassword:    function (p)     { return req('/api/auth/password', { method: 'PATCH', body: p }); },
    adminUsers:        function ()      { return req('/api/admin/users'); },
    suspendUser:       function (u, r)  { return req('/api/admin/users/' + u + '/suspend', { method: 'POST', body: { reason: r } }); },
    unsuspendUser:     function (u)     { return req('/api/admin/users/' + u + '/suspend', { method: 'DELETE' }); },
    audit:             function ()      { return req('/api/audit'); },
    verifyPassword:    function (pw)    { return req('/api/auth/verify-password', { method: 'POST', body: { password: pw } }); },
    requestPasswordReset: function (e)  { return req('/api/auth/password-reset', { method: 'POST', body: { email: e } }); },
    confirmPasswordReset: function (t, pw) { return req('/api/auth/password-reset/confirm', { method: 'POST', body: { token: t, password: pw } }); },

    summary:           function (f)     { return req('/api/summary' + qs(f)); },
    transactions:      function (f)     { return req('/api/transactions' + qs(f)); },
    nlpParse:          function (t)     { return req('/api/nlp/parse', { method: 'POST', body: { text: t } }); },
    nlpParseBatch:     function (t)     { return req('/api/nlp/parse-batch', { method: 'POST', body: { text: t } }); },
    nlpConfirm:        function (p)     { return req('/api/nlp/confirm', { method: 'POST', body: p }); },
    nlpConfirmBatch:   function (i)     { return req('/api/nlp/confirm-batch', { method: 'POST', body: { items: i } }); },
    createTransaction: function (p)     { return req('/api/transactions', { method: 'POST', body: p }); },
    deleteTransaction: function (id)    { return req('/api/transactions/' + encodeURIComponent(id), { method: 'DELETE' }); },
    deleteTransactions: function (ids)  { return req('/api/transactions' + qs({ ids: ids.join(',') }), { method: 'DELETE' }); },
    updateTransaction: function (id, p) { return req('/api/transactions/' + encodeURIComponent(id), { method: 'PATCH', body: p }); },
    notifications:     function (f)     { return req('/api/notifications' + qs(f)); },
    readNotification:  function (i)     { return req('/api/notifications/' + encodeURIComponent(i), { method: 'PATCH', body: { read: true } }); },
    readNotifications: function (u)     { return req('/api/notifications', { method: 'PATCH', body: { readUntil: u } }); },
    groups:            function (f)     { return req('/api/groups' + qs(f)); },
    createGroup:       function (p)     { return req('/api/groups', { method: 'POST', body: p }); },
    settleGroup:       function (g)     { return req('/api/groups/' + g + '/settle', { method: 'POST' }); },
    setGroupNotify:    function (g, on) { return req('/api/groups/' + g + '/notify', { method: 'PATCH', body: { notify: !!on } }); },
    updateGroup:       function (g, p)  { return req('/api/groups/' + encodeURIComponent(g), { method: 'PATCH', body: p }); },
    archiveGroup:      function (g)     { return req('/api/groups/' + encodeURIComponent(g), { method: 'DELETE' }); },
    removeGroup:       function (g)     { return req('/api/groups/' + encodeURIComponent(g) + '?permanent=true', { method: 'DELETE' }); },
    addGroupMember:    function (g, u)  { return req('/api/groups/' + encodeURIComponent(g) + '/members', { method: 'POST', body: { userId: u } }); },
    removeGroupMember: function (g, u)  { return req('/api/groups/' + encodeURIComponent(g) + '/members/' + encodeURIComponent(u), { method: 'DELETE' }); },
    allowances:        function ()      { return req('/api/allowances'); },
    setAllowance:      function (w, a)  { return req('/api/allowance', { method: 'PUT', body: { wardId: w, amount: a } }); },
    savingsGoals:      function ()      { return req('/api/savings-goals'); },
    alerts:            function ()      { return req('/api/alerts'); },
    createAlert:       function (p)     { return req('/api/alerts', { method: 'POST', body: p }); },
    updateAlert:       function (a, p)  { return req('/api/alerts/' + encodeURIComponent(a), { method: 'PATCH', body: p }); },
    deleteAlert:       function (a)     { return req('/api/alerts/' + encodeURIComponent(a), { method: 'DELETE' }); },
    budgets:           function (f)     { return req('/api/budgets' + qs(f || {})); },
    setSavingsGoal:    function (u, g, gid) { return req('/api/savings-goal', { method: 'PUT', body: { userId: u, goal: g, groupId: gid || null } }); },
    advices:           function (f)     { return req('/api/advices' + qs(f)); },
    members:           function ()      { return req('/api/family'); },
    createFamily:      function (p)     { return req('/api/family', { method: 'POST', body: p }); },
    createInviteCode:  function (p)     { return req('/api/family/invite', { method: 'POST', body: p }); },
    joinFamily:        function (p)     { return req('/api/family/join', { method: 'POST', body: p }); },
    lookupUser:        function (e)     { return req('/api/family/lookup' + qs({ email: e })); },
    invites:           function ()      { return req('/api/family/invites'); },
    sendInvite:        function (p)     { return req('/api/family/invites', { method: 'POST', body: p }); },
    acceptInvite:      function (i)     { return req('/api/family/invites/' + i + '/accept', { method: 'POST' }); },
    declineInvite:     function (i)     { return req('/api/family/invites/' + i, { method: 'DELETE' }); },
    removeMember:      function (u)     { return req('/api/family/members/' + u, { method: 'DELETE' }); },
    leaveFamily:       function ()      { return req('/api/family/members/' + 'me', { method: 'DELETE' }); },
    categories:        function ()      { return req('/api/categories'); },
    createCategory:    function (p)     { return req('/api/categories', { method: 'POST', body: p }); },
    setBudget:         function (p)     { return req('/api/budgets', { method: 'PUT', body: p }); },
    generateAdvices:   function (p)     { return req('/api/advices/generate', { method: 'POST', body: p || {} }); },
    guardianships:     function ()      { return req('/api/guardianships'); },
    createGuardianship: function (p)    { return req('/api/guardianships', { method: 'POST', body: p }); },
    endGuardianship:   function (i)     { return req('/api/guardianships/' + encodeURIComponent(i), { method: 'DELETE' }); },
    changeMemberRole:  function (u, r)  { return req('/api/family/members/' + encodeURIComponent(u), { method: 'PATCH', body: { role: r } }); },
    dissolveFamily:    function ()      { return req('/api/family', { method: 'DELETE' }); },
    sessions:          function ()      { return req('/api/auth/sessions'); },
    logoutAll:         function ()      {
      return req('/api/auth/logout-all', { method: 'POST' }).then(function (d) { setTokens(null); return d; });
    },
    reset:             function ()      { return Promise.resolve({ reset: false, note: '真後端不提供重置' }); }
  };

  var impl = MODE === 'http' ? http : mock;

  /* ============================================================
     對外的 API
     ------------------------------------------------------------
     每一支都登記「打哪條路由、歸哪位成員」。出錯的時候，錯誤上會帶著：
       e.fn     'API.summary'
       e.route  'GET /api/summary'
       e.owner  '成員3'
       e.kind   'business'  後端照規則擋下來（400／403／409…），訊息就是給使用者看的
                'backend'   後端壞了或還沒做（5xx、404／405 路由不存在、501）
                'network'   連不上後端
                'shape'     回應的形狀不對（少了畫面要用的欄位）
     backend／network／shape 會把「是哪一支出錯」接在訊息後面——
     前提是前端沒問題：這三種都是「照契約打過去，拿回來的不對」。

     ⚠️ 新增一支 API：mock、http 各寫一個，再在 FN 這裡登記一行。
        路由與負責人跟 backend/app/ownership.py 對齊，有測試擋。
     ============================================================ */
  var FN = {
    me:                 ['GET /api/auth/me', '成員1'],
    authState:          [null, '前端'],
    login:              ['POST /api/auth/login', '成員1'],
    register:           ['POST /api/auth/register', '成員1'],
    logout:             ['POST /api/auth/logout', '成員1'],
    updateProfile:      ['PATCH /api/auth/me', '成員1'],
    uploadAvatar:       ['PUT /api/auth/me/avatar', '成員1'],
    deleteAvatar:       ['DELETE /api/auth/me/avatar', '成員1'],
    financeProfile:     ['GET /api/auth/me/finance', '成員1'],
    setFinanceProfile:  ['PUT /api/auth/me/finance', '成員1'],
    changePassword:     ['PATCH /api/auth/password', '成員1'],
    verifyPassword:     ['POST /api/auth/verify-password', '成員1'],
    requestPasswordReset: ['POST /api/auth/password-reset', '成員1'],
    confirmPasswordReset: ['POST /api/auth/password-reset/confirm', '成員1'],
    sessions:           ['GET /api/auth/sessions', '成員1'],
    logoutAll:          ['POST /api/auth/logout-all', '成員1'],
    adminUsers:         ['GET /api/admin/users', '成員1'],
    suspendUser:        ['POST /api/admin/users/{user_id}/suspend', '成員1'],
    unsuspendUser:      ['DELETE /api/admin/users/{user_id}/suspend', '成員1'],

    transactions:       ['GET /api/transactions', '成員2'],
    createTransaction:  ['POST /api/transactions', '成員2'],
    updateTransaction:  ['PATCH /api/transactions/{tx_id}', '成員2'],
    deleteTransaction:  ['DELETE /api/transactions/{tx_id}', '成員2'],
    deleteTransactions: ['DELETE /api/transactions', '成員2'],
    nlpParse:           ['POST /api/nlp/parse', '成員2'],
    nlpParseBatch:      ['POST /api/nlp/parse-batch', '成員2'],
    nlpConfirm:         ['POST /api/nlp/confirm', '成員2'],
    nlpConfirmBatch:    ['POST /api/nlp/confirm-batch', '成員2'],
    categories:         ['GET /api/categories', '成員2'],
    createCategory:     ['POST /api/categories', '成員2'],
    groups:             ['GET /api/groups', '成員2'],
    createGroup:        ['POST /api/groups', '成員2'],
    updateGroup:        ['PATCH /api/groups/{gid}', '成員2'],
    archiveGroup:       ['DELETE /api/groups/{gid}', '成員2'],
    removeGroup:        ['DELETE /api/groups/{gid}', '成員2'],
    addGroupMember:     ['POST /api/groups/{gid}/members', '成員2'],
    removeGroupMember:  ['DELETE /api/groups/{gid}/members/{user_id}', '成員2'],
    settleGroup:        ['POST /api/groups/{gid}/settle', '成員2'],
    setGroupNotify:     ['PATCH /api/groups/{gid}/notify', '成員2'],

    summary:            ['GET /api/summary', '成員3'],
    budgets:            ['GET /api/budgets', '成員3'],
    setBudget:          ['PUT /api/budgets', '成員3'],
    savingsGoals:       ['GET /api/savings-goals', '成員3'],
    setSavingsGoal:     ['PUT /api/savings-goal', '成員3'],
    alerts:             ['GET /api/alerts', '成員3'],
    createAlert:        ['POST /api/alerts', '成員3'],
    updateAlert:        ['PATCH /api/alerts/{aid}', '成員3'],
    deleteAlert:        ['DELETE /api/alerts/{aid}', '成員3'],
    advices:            ['GET /api/advices', '成員3'],
    generateAdvices:    ['POST /api/advices/generate', '成員3'],

    members:            ['GET /api/family', '成員4'],
    createFamily:       ['POST /api/family', '成員4'],
    dissolveFamily:     ['DELETE /api/family', '成員4'],
    createInviteCode:   ['POST /api/family/invite', '成員4'],
    joinFamily:         ['POST /api/family/join', '成員4'],
    lookupUser:         ['GET /api/family/lookup', '成員4'],
    invites:            ['GET /api/family/invites', '成員4'],
    sendInvite:         ['POST /api/family/invites', '成員4'],
    acceptInvite:       ['POST /api/family/invites/{invite_id}/accept', '成員4'],
    declineInvite:      ['DELETE /api/family/invites/{invite_id}', '成員4'],
    changeMemberRole:   ['PATCH /api/family/members/{user_id}', '成員4'],
    removeMember:       ['DELETE /api/family/members/{user_id}', '成員4'],
    leaveFamily:        ['DELETE /api/family/members/{user_id}', '成員4'],
    guardianships:      ['GET /api/guardianships', '成員4'],
    createGuardianship: ['POST /api/guardianships', '成員4'],
    endGuardianship:    ['DELETE /api/guardianships/{gid}', '成員4'],
    notifications:      ['GET /api/notifications', '成員4'],
    readNotification:   ['PATCH /api/notifications/{nid}', '成員4'],
    readNotifications:  ['PATCH /api/notifications', '成員4'],
    allowances:         ['GET /api/allowances', '成員4'],
    setAllowance:       ['PUT /api/allowance', '成員4'],
    audit:              ['GET /api/audit', '成員4'],

    reset:              [null, '前端']
  };

  /* 畫面一定會讀的欄位。少了任何一個，畫面會在很後面的地方壞掉（讀不到 undefined 的 map），
     看不出是哪一支回錯——所以在這裡先檢查，直接指出是哪一支。 */
  var SHAPE = {
    me: ['user'], login: ['user'], register: ['user'],
    financeProfile: ['finance', 'styles', 'goals', 'habits'],
    requestPasswordReset: ['ok', 'message'], sessions: ['sessions'],
    adminUsers: ['users'], audit: ['logs'],
    transactions: ['transactions', 'total'], createTransaction: ['id'], updateTransaction: ['id'],
    deleteTransactions: ['deleted'], nlpParse: ['out'], nlpParseBatch: ['items'],
    categories: ['categories'], groups: ['groups'], createGroup: ['id'],
    summary: ['income', 'expense', 'byCat', 'monthly', 'yearly'],
    budgets: ['budgets'], savingsGoals: ['goals'], alerts: ['alerts'],
    advices: ['advices'], generateAdvices: ['advices'],
    members: ['family', 'members', 'guardianships'], invites: ['received', 'sent', 'codes'],
    guardianships: ['guardianships'], createGuardianship: ['id'],
    notifications: ['notifications', 'unread'], allowances: ['allowances'], lookupUser: ['user', 'status']
  };

  /* ============================================================
     前端代勞
     ------------------------------------------------------------
     後端只要回「查資料庫才拿得到」的東西；下面這些前端補得出來，後端可以不帶：

       衍生欄位  summary 的 net／rate／savings.*（用 income、expense、goal 算）
                budgets[].pct／over（用 used、limit 算）
       名稱對照  transactions／budgets／notifications 的 catName、catColor、userName
                guardianships 的 guardianName／wardName、advices 的 userName
                （用 GET /api/categories 與 GET /api/family 的清單對）
       備援      後端這幾支還沒做（501／404／405）或連不上時，前端先頂著：
                nlpParse／nlpParseBatch → 前端規則解析（寫入還是走後端）
                generateAdvices          → 用 summary＋budgets 在前端寫成句子（不會存）
                sessions                 → 只列這一台

     ⚠️ 權限、可見範圍、密碼、金額加總、寫入**一律是後端的**，前端不代勞——
        那些放前端等於任何人改一下瀏覽器就能繞過。
     ============================================================ */
  var LOOKUP = { cats: null, people: null, me: null };
  /* 家庭、分類、名字改了，對照表要重拿 */
  var LOOKUP_STALE = ['createCategory', 'createFamily', 'joinFamily', 'acceptInvite', 'removeMember',
    'leaveFamily', 'dissolveFamily', 'changeMemberRole', 'updateProfile', 'login', 'logout', 'register'];

  function lookups() {
    var jobs = [];
    if (!LOOKUP.cats) jobs.push(impl.categories().then(function (d) { LOOKUP.cats = d.categories || []; }, function () { LOOKUP.cats = global.DATA.categories || []; }));
    if (!LOOKUP.people) jobs.push(impl.members().then(function (d) { LOOKUP.people = d.members || []; LOOKUP.me = d.me; }, function () { LOOKUP.people = []; }));
    return Promise.all(jobs);
  }
  function catName(id) { return ((LOOKUP.cats || []).filter(function (c) { return c.id === id; })[0] || {}); }
  function personName(id) { return ((LOOKUP.people || []).filter(function (m) { return m.id === id; })[0] || {}).name || ''; }

  function needsNames(list, keys) {
    return (list || []).some(function (x) { return keys.some(function (k) { return !(k in x); }); });
  }

  function fillIn(name, res) {
    if (!res || typeof res !== 'object') return Promise.resolve(res);
    if (name === 'summary') {
      var rule = (res.savings && res.savings.rule) || global.DATA.savingsRule;
      var sv = res.savings = res.savings || {};
      if (!('net' in res)) res.net = res.income - res.expense;
      if (!('rate' in res)) res.rate = res.income ? (res.income - res.expense) / res.income : 0;
      if (!('goal' in sv)) sv.goal = 0;
      if (!('allowance' in sv)) sv.allowance = res.income - sv.goal;
      if (!('used' in sv)) sv.used = res.expense;
      if (!('left' in sv)) sv.left = sv.allowance - res.expense;
      if (!('ratio' in sv)) sv.ratio = sv.allowance > 0 ? res.expense / sv.allowance : (res.expense > 0 ? 2 : 0);
      if (!('level' in sv)) sv.level = sv.ratio >= rule.overAt ? 'over' : (sv.ratio >= rule.warnAt ? 'near' : 'safe');
      if (!('shortfall' in sv)) sv.shortfall = Math.max(0, res.expense - sv.allowance);
      if (!('actual' in sv)) sv.actual = res.income - res.expense;
      if (!sv.rule) sv.rule = rule;
      if (!needsNames(res.byCat, ['name', 'color'])) return Promise.resolve(res);
      return lookups().then(function () {
        res.byCat.forEach(function (c) { var k = catName(c.cat); if (!('name' in c)) c.name = k.name || c.cat; if (!('color' in c)) c.color = k.color || 'cat-other'; });
        return res;
      });
    }
    if (name === 'budgets') {
      (res.budgets || []).forEach(function (b) {
        if (!('pct' in b)) b.pct = b.limit ? b.used / b.limit : 0;
        if (!('over' in b)) b.over = b.used > b.limit;
      });
      if (!needsNames(res.budgets, ['catName', 'catColor', 'userName'])) return Promise.resolve(res);
      return lookups().then(function () {
        res.budgets.forEach(function (b) { var k = catName(b.cat); b.catName = b.catName || k.name || b.cat; b.catColor = b.catColor || k.color || 'cat-other'; b.userName = b.userName || personName(b.user); });
        return res;
      });
    }
    var rows = name === 'transactions' ? res.transactions : name === 'notifications' ? res.notifications
      : name === 'guardianships' ? res.guardianships : name === 'advices' ? res.advices : null;
    if (!rows) return Promise.resolve(res);
    var keys = { transactions: ['catName', 'catColor', 'userName'], notifications: ['actorName'],
                 guardianships: ['guardianName', 'wardName'], advices: ['userName'] }[name];
    if (!needsNames(rows, keys)) return Promise.resolve(res);
    return lookups().then(function () {
      rows.forEach(function (x) {
        if (name === 'transactions') { var k = catName(x.cat); if (!('catName' in x)) x.catName = k.name || ''; if (!('catColor' in x)) x.catColor = k.color || 'cat-other'; if (!('userName' in x)) x.userName = personName(x.user); }
        if (name === 'notifications') { if (!('actorName' in x)) x.actorName = x.actorId ? personName(x.actorId) : null; if (x.cat && !('catName' in x)) x.catName = catName(x.cat).name || ''; }
        if (name === 'guardianships') { if (!('guardianName' in x)) x.guardianName = personName(x.guardian); if (!('wardName' in x)) x.wardName = personName(x.ward); if (!('mine' in x)) x.mine = x.guardian === LOOKUP.me; }
        if (name === 'advices') { if (!('userName' in x)) x.userName = x.user ? personName(x.user) : null; }
      });
      return res;
    });
  }

  /* 後端還沒做這一支（或連不上）時，前端先頂著。回傳 null = 這一支沒有備援，照常報錯 */
  var FALLBACK = {
    nlpParse: function (args) {
      var t = String(args[0] || '').trim(), it = parseLine(t);
      return { raw: t, matched: false, fallback: true,
        out: { date: it.date, amount: it.amount || 0, kind: it.kind, cat: it.cat, merchant: it.merchant, conf: it.conf.amount, catConf: it.conf.cat },
        note: '後端的解析還沒接上，先用前端的規則解析。確認寫入還是存到後端。' };
    },
    nlpParseBatch: function (args) {
      var t = String(args[0] || '').trim();
      var items = t.split(/[，,。；;、\n]+/).map(function (x) { return x.trim(); }).filter(function (x) { return x.length > 1; })
        .map(function (part, i) { return Object.assign({ seq: i + 1, span: part }, parseLine(part)); });
      return { raw: t, matched: false, fallback: true, items: items,
        note: '後端的解析還沒接上，先用前端的規則切分。確認寫入還是存到後端。' };
    },
    generateAdvices: function (args) {
      var scope = (args[0] || {}).scope === 'family' ? 'family' : 'me';
      return Promise.all([global.API.summary({ scope: scope }), global.API.budgets({}), global.API.me()]).then(function (r) {
        var built = buildAdvices(r[0], r[1].budgets || [], scope, r[2].user.id, r[0].period || global.DATA.meta.period);
        return { fallback: true, generatedAt: built.head.generatedAt,
          advices: built.advices.map(function (a) { return Object.assign(a, { userName: a.user ? r[2].user.name : null }); }),
          note: '後端的建議還沒接上，這幾則是前端用同一批數字寫的，不會存起來。' };
      });
    },
    sessions: function () {
      var ua = (global.navigator && global.navigator.userAgent) || '';
      return { fallback: true, sessions: [{ id: 'this-device', current: true, lastActiveAt: new Date().toISOString(),
        device: /iPhone|iPad|Android/i.test(ua) ? '手機瀏覽器' : '電腦瀏覽器' }] };
    }
  };

  function where(name) {
    var info = FN[name] || [];
    return 'API.' + name + (info[0] ? '（' + info[0] + '，' + info[1] + '）' : '');
  }

  function tag(e, name) {
    if (!(e instanceof Error)) e = new Error(String(e));
    if (e.fn) return e;                                 // 已經標過（例如 A 裡面呼叫了 B）
    var info = FN[name] || [];
    e.fn = 'API.' + name; e.route = info[0] || null; e.owner = info[1] || null;
    var st = e.status || 0;
    if (e.kind === 'shape') {
      // 已經在下面組好訊息
    } else if (!st && (e.name === 'TypeError' || /Failed to fetch|NetworkError|Load failed/i.test(e.message))) {
      e.kind = 'network';
      e.message = '連不上後端｜出錯的函式：' + where(name);
    } else if (st >= 500 || st === 404 && /^Not Found$/i.test(e.message) || st === 405) {
      e.kind = 'backend';
      /* 後端 501 的訊息本身就是「後端還沒做這一支：路由（成員）」，路由與負責人 where() 會再講一次，不重複 */
      var detail = e.message && !/^HTTP \d+/.test(e.message) && !/^Not Found$/i.test(e.message) &&
        !(st === 501 && /^後端還沒做這一支/.test(e.message)) ? '：' + e.message : '';
      e.message = (st === 501 ? '後端還沒做這一支' : '後端出錯（HTTP ' + st + '）') + detail +
        '｜出錯的函式：' + where(name);
    } else {
      e.kind = 'business';
    }
    return e;
  }

  function call(name, args) {
    var fn = impl[name];
    if (typeof fn !== 'function') {
      var miss = new Error('前端的 ' + (MODE === 'http' ? 'http' : 'mock') + ' 轉接器少了這一支｜出錯的函式：' + where(name));
      miss.kind = 'backend';
      return Promise.reject(tag(miss, name));
    }
    var out;
    try { out = fn.apply(impl, args); } catch (e) { return Promise.reject(tag(e, name)); }
    return Promise.resolve(out).catch(function (e) {
      /* 後端還沒做（501／404／405）或連不上：有備援的就先頂著 */
      var st = e && e.status;
      var notReady = st === 501 || st === 405 || (st === 404 && /^Not Found$/i.test(e.message)) ||
        (!st && e && (e.name === 'TypeError' || /Failed to fetch|NetworkError|Load failed/i.test(e.message)));
      if (notReady && FALLBACK[name]) return FALLBACK[name](args);
      throw e;
    }).then(function (res) {
      if (LOOKUP_STALE.indexOf(name) >= 0) { LOOKUP.cats = null; LOOKUP.people = null; }
      var need = SHAPE[name];
      if (need) {
        var lack = need.filter(function (k) { return !res || !(k in res); });
        if (lack.length) {
          var bad = new Error('回應少了 ' + lack.join('、') + '｜出錯的函式：' + where(name));
          bad.kind = 'shape';
          throw bad;
        }
      }
      return fillIn(name, res);
    }).catch(function (e) { throw tag(e, name); });
  }

  global.API = { mode: MODE, base: BASE, routes: FN, where: where };
  Object.keys(FN).forEach(function (name) {
    global.API[name] = function () { return call(name, Array.prototype.slice.call(arguments)); };
  });
})(window);
