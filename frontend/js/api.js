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
   POST   /api/auth/refresh           access token 過期時換新的
   PATCH  /api/auth/me                改個人資料（displayName / birthYear）
   PUT    /api/auth/me/avatar         上傳大頭貼（body: { image: dataUri }）
   DELETE /api/auth/me/avatar         移除大頭貼
   PATCH  /api/auth/password          改密碼
   POST   /api/auth/verify-password   重大操作前再確認一次（不發新 token）
   GET    /api/auth/me                目前登入者 + 家庭角色

   家庭與權限
   GET    /api/family                 家庭資訊與成員清單
   POST   /api/family/invite          產生邀請碼（家長）
   PATCH  /api/family/members/{id}    改角色（家長）
   DELETE /api/family/members/{id}    移除成員（家長）
   GET    /api/guardianships          監管關係（雙方都看得到）
   POST   /api/guardianships          建立監管（家長）
   DELETE /api/guardianships/{id}     解除監管（家長）

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
   監管通知
   GET    /api/notifications          通知清單（帶 since 只拿新的）
   PATCH  /api/notifications/{id}     標記單則已讀
   PATCH  /api/notifications          整批已讀（帶 readUntil）

   群組（帳本）
   GET    /api/groups                 我加入的群組
   POST   /api/groups                 建立
   PATCH  /api/groups/{gid}           改名稱／圖示／顏色
   DELETE /api/groups/{gid}           封存（不刪除）
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
      goals: {},
      readNotify: [],
      auth: { loggedIn: true },   // mock 預設已登入，不然一打開就被擋在登入頁
      patch: {},                  // 個人資料的改動（名字、大頭貼）
      newUsers: []                // 註冊進來的人
    };
    try {
      var saved = JSON.parse(localStorage.getItem(KEY) || 'null');
      if (saved) {
        if (saved.me) base.me = saved.me;
        if (saved.extra) base.transactions = saved.extra.concat(base.transactions);
        if (saved.goals) base.goals = saved.goals;
        if (saved.readNotify) base.readNotify = saved.readNotify;
        if (saved.auth) base.auth = saved.auth;
        if (saved.patch) base.patch = saved.patch;
        if (saved.newUsers) base.newUsers = saved.newUsers;
        ['newGroups', 'groupPatch', 'joined', 'left', 'archived',
         'goalPatch', 'allowancePatch', 'newAlerts', 'alertPatch', 'alertGone'].forEach(function (k) {
          if (saved[k]) base[k] = saved[k];
        });
      }
    } catch (e) {}
    applyGoals(base.goals);
    applyUsers(base.newUsers);
    applyPatch(base.patch);
    state = base;
    return state;
  }
  function save() {
    try {
      var extra = state.transactions.filter(function (t) { return t.id.indexOf('N') === 0; });
      localStorage.setItem(KEY, JSON.stringify({
        me: state.me, extra: extra, goals: state.goals || {},
        readNotify: state.readNotify || [],
        auth: state.auth || { loggedIn: true },
        patch: state.patch || {},
        newUsers: state.newUsers || [],
        newGroups: state.newGroups || [],
        groupPatch: state.groupPatch || {},
        joined: state.joined || [],
        left: state.left || [],
        archived: state.archived || [],
        goalPatch: state.goalPatch || [],
        allowancePatch: state.allowancePatch || [],
        newAlerts: state.newAlerts || [],
        alertPatch: state.alertPatch || {},
        alertGone: state.alertGone || []
      }));
    } catch (e) {}
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

  function memberOf(id) {
    return global.DATA.members.filter(function (m) { return m.id === id; })[0];
  }
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
      .filter(function (g) { return withArchived || (s.archived || []).indexOf(g) < 0; });
  }

  function groupOf(id) {
    // 封存的也要找得到，不然「復原」會說找不到這個群組
    return allGroups(true).filter(function (g) { return g.id === id; })[0];
  }

  /* 種子群組 + 這個瀏覽器建立的群組。
     withArchived = true 時連封存的一起回（管理頁的「已封存」區塊要用）。 */
  function allGroups(withArchived) {
    var s = load();
    return global.DATA.groups.concat(s.newGroups || [])
      .map(function (g) {
        var p = (s.groupPatch || {})[g.id] || {};
        return Object.assign({}, g, p, {
          archived: (s.archived || []).indexOf(g.id) >= 0
        });
      })
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
  function groupFor(meId, wanted) {
    var mine = visibleGroups(meId);
    if (wanted && mine.indexOf(wanted) >= 0) return wanted;
    if (!mine.length) throw new Error('你還沒有任何帳本，先去「群組」開一本');
    return mine[0];
  }

  /* 跟我同帳本的人。我看得到他們**在共用帳本裡**的紀錄，
     但看不到他們記在別處的——這跟監管不一樣，監管是整個人。 */
  function coMembers(meId) {
    var mine = visibleGroups(meId);
    var out = [meId];
    global.DATA.groupMembers.forEach(function (m) {
      if (mine.indexOf(m.group) >= 0 && out.indexOf(m.user) < 0) out.push(m.user);
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

  function visibleUsers(meId) {
    if (!memberOf(meId)) return [meId];
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
      return Promise.resolve({ loggedIn: !!(s.auth && s.auth.loggedIn) });
    },

    login: function (c) {
      var s = load(); c = c || {};
      return sleep(260).then(function () {
        var mail = String(c.email || '').trim().toLowerCase();
        var u = global.DATA.members.filter(function (m) {
          return String(m.email || '').toLowerCase() === mail;
        })[0];
        /* 真後端這兩種情況要回同一句話。
           分開講等於送給攻擊者一支帳號列舉工具：
           「這個 email 沒有註冊過」就是在確認哪些 email 有註冊。
           這裡分開只是為了 demo 時看得懂自己打錯什麼。 */
        if (!u) throw new Error('這個 email 沒有註冊過');
        if (String(c.password || '').length < 8) throw new Error('密碼至少 8 個字');
        s.me = u.id;
        s.auth = { loggedIn: true };
        save();
        return {
          accessToken: 'mock.access.' + u.id,
          refreshToken: 'mock.refresh.' + u.id,
          expiresIn: 1800,
          user: clone(u)
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

        var n = global.DATA.members.reduce(function (mx, m) {
          return Math.max(mx, Number(String(m.id).replace(/\D/g, '')) || 0);
        }, 0) + 1;
        var u = {
          id: 'U' + n, name: name, email: mail, role: 'member',
          avatar: name.slice(-1), age: null,
          joined: new Date().toISOString().slice(0, 10),
          income: 0, expense: 0, budget: 0,
          savingsGoal: Number(p.savingsGoal) || 0
        };
        global.DATA.members.push(u);
        s.newUsers = (s.newUsers || []).concat([clone(u)]);
        s.me = u.id;
        s.auth = { loggedIn: true };
        save();
        return {
          accessToken: 'mock.access.' + u.id,
          refreshToken: 'mock.refresh.' + u.id,
          expiresIn: 1800,
          user: clone(u)
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
        applyPatch(s.patch);
        save();
        return clone(memberOf(s.me));
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
    verifyPassword: function (pw) {
      return sleep(320).then(function () {
        if (String(pw || '').length < 8) throw new Error('密碼不正確');
        return { ok: true };
      });
    },

    changePassword: function (p) {
      p = p || {};
      return sleep(260).then(function () {
        if (String(p.oldPassword || '').length < 8) throw new Error('目前的密碼不對');
        if (String(p.newPassword || '').length < 8) throw new Error('新密碼至少 8 個字');
        if (p.oldPassword === p.newPassword) throw new Error('新密碼不能跟舊的一樣');
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
              return Object.assign(clone(g), {
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
                canEdit: g.owner === s.me
              });
            })
        };
      });
    },

    createGroup: function (p) {
      var s = load(); p = p || {};
      return sleep(300).then(function () {
        var name = String(p.name || '').trim();
        if (!name) throw new Error('群組要有名字');
        if (allGroups().some(function (g) { return g.name === name; })) {
          throw new Error('已經有一本叫「' + name + '」的帳了');
        }
        var n = allGroups().reduce(function (mx, g) {
          return Math.max(mx, Number(String(g.id).replace(/\D/g, '')) || 0);
        }, 0) + 1;
        var g = {
          id: 'G' + n, name: name,
          icon: (p.icon || name).slice(-1),
          color: p.color || '#6C9FFB',
          owner: s.me,
          created: new Date().toISOString().slice(0, 10),
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

    addGroupMember: function (gid, userId) {
      var s = load();
      return sleep(240).then(function () {
        var g = groupOf(gid);
        if (!g) throw new Error('找不到這個群組');
        if (g.owner !== s.me) { var e = new Error('只有建立者可以加人'); e.status = 403; throw e; }
        if (!memberOf(userId)) throw new Error('這個家庭裡沒有這個人');
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
              spent: m.expense || 0
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
        var n = Date.now();
        var a = { id: 'ALN' + n, user: s.me, group: gid, percent: pct,
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
        return { id: aid };
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

        var income = earners.reduce(function (n, u) {
          var m = memberOf(u); return n + (m ? m.income : 0);
        }, 0) + sum(added.filter(function (t) {
          return earners.indexOf(t.user) >= 0;
        }), 'income');

        var wardIncome = wards.reduce(function (n, u) {
          var m = memberOf(u); return n + (m ? m.income : 0);
        }, 0) + sum(added.filter(function (t) {
          return wards.indexOf(t.user) >= 0;
        }), 'income');

        var expense = users.reduce(function (n, u) {
          var m = memberOf(u); return n + (m ? m.expense : 0);
        }, 0) + sum(added, 'expense');
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

        return {
          period: D.meta.period,
          scope: f.scope || 'me',
          income: income, expense: expense, net: income - expense,
          wardIncome: wardIncome,
          allowance: wards.reduce(function (n, u) {
            return n + allowanceOf(s.me, u);
          }, 0),
          wardSpend: wards.reduce(function (n, u) {
            var m = memberOf(u); return n + (m ? m.expense : 0);
          }, 0) + sum(added.filter(function (t) {
            return wards.indexOf(t.user) >= 0;
          }), 'expense'),
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
        var g = groupFor(s.me, items[0] && items[0].groupId);
        var made = items.map(function (p, i) {
          return {
            id: 'N' + (Date.now() + i), user: s.me, date: p.date,
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
          id: 'N' + Date.now(), user: s.me, date: p.date, amount: Number(p.amount),
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
          id: 'N' + Date.now(), user: s.me, date: parsed.date, amount: Number(parsed.amount),
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
        if (t.user !== s.me) throw new Error('這是別人的紀錄，你只能檢視');
        s.transactions = s.transactions.filter(function (x) { return x.id !== id; });
        save();
        return { deleted: id };
      });
    },

    setSavingsGoal: function (userId, goal, groupId) {
      var st = load(), D = global.DATA;
      return sleep(240).then(function () {
        // 設群組目標時不用指定人——設的一定是自己的
        if (!userId) userId = st.me;
        var m = D.members.filter(function (x) { return x.id === userId; })[0];
        if (!m) throw new Error('not found: ' + userId);

        /* 誰能設誰的目標：本人，或監管他的人。
           ⚠️ 不看年齡、也不看角色。系統只提供功能，要不要建立監管關係
              是那一家自己的事——我們不替任何家庭決定幾歲該被管。 */
        var mine = userId === st.me;
        var proxy = wardsOf(st.me).indexOf(userId) >= 0;
        if (!mine && !proxy) throw new Error('只能設定自己、或你監管對象的存款目標');
        if (groupId && !mine) throw new Error('群組目標只能設自己的');

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
            var c = D.categories.filter(function (x) { return x.id === t.cat; })[0] || {};
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

    readNotifications: function (untilId) {
      var s = load();
      return sleep(80).then(function () {
        s.readNotify = s.readNotify || [];
        s.transactions.forEach(function (t) {
          var nid = 'NT' + t.id;
          if (s.readNotify.indexOf(nid) < 0) s.readNotify.push(nid);
        });
        save();
        return { updated: s.readNotify.length, unread: 0 };
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
        /* 名字、角色、監管關係是公開的——被監管的人必須知道自己被誰看著，
           所以這張表不能藏。但「存款目標」是個人財務資料，
           看不到那個人的就不要送過去。⚠️ 後端也要這樣做：
           前端把欄位藏起來不算保護，資料根本不該離開伺服器。 */
        var vis = visibleUsers(s.me);
        return {
          me: s.me,
          visible: vis,
          queryable: queryableUsers(s.me),
          members: D.members.map(function (m) {
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
    changePassword:    function (p)     { return req('/api/auth/password', { method: 'PATCH', body: p }); },
    verifyPassword:    function (pw)    { return req('/api/auth/verify-password', { method: 'POST', body: { password: pw } }); },

    summary:           function (f)     { return req('/api/summary' + qs(f)); },
    transactions:      function (f)     { return req('/api/transactions' + qs(f)); },
    nlpParse:          function (t)     { return req('/api/nlp/parse', { method: 'POST', body: { text: t } }); },
    nlpParseBatch:     function (t)     { return req('/api/nlp/parse-batch', { method: 'POST', body: { text: t } }); },
    nlpConfirm:        function (p)     { return req('/api/nlp/confirm', { method: 'POST', body: p }); },
    nlpConfirmBatch:   function (i)     { return req('/api/nlp/confirm-batch', { method: 'POST', body: { items: i } }); },
    createTransaction: function (p)     { return req('/api/transactions', { method: 'POST', body: p }); },
    deleteTransaction: function (id)    { return req('/api/transactions/' + encodeURIComponent(id), { method: 'DELETE' }); },
    notifications:     function (f)     { return req('/api/notifications' + qs(f)); },
    readNotification:  function (i)     { return req('/api/notifications/' + encodeURIComponent(i), { method: 'PATCH', body: { read: true } }); },
    readNotifications: function (u)     { return req('/api/notifications', { method: 'PATCH', body: { readUntil: u } }); },
    groups:            function (f)     { return req('/api/groups' + qs(f)); },
    createGroup:       function (p)     { return req('/api/groups', { method: 'POST', body: p }); },
    updateGroup:       function (g, p)  { return req('/api/groups/' + encodeURIComponent(g), { method: 'PATCH', body: p }); },
    archiveGroup:      function (g)     { return req('/api/groups/' + encodeURIComponent(g), { method: 'DELETE' }); },
    addGroupMember:    function (g, u)  { return req('/api/groups/' + encodeURIComponent(g) + '/members', { method: 'POST', body: { userId: u } }); },
    removeGroupMember: function (g, u)  { return req('/api/groups/' + encodeURIComponent(g) + '/members/' + encodeURIComponent(u), { method: 'DELETE' }); },
    allowances:        function ()      { return req('/api/allowances'); },
    setAllowance:      function (w, a)  { return req('/api/allowance', { method: 'PUT', body: { wardId: w, amount: a } }); },
    savingsGoals:      function ()      { return req('/api/savings-goals'); },
    alerts:            function ()      { return req('/api/alerts'); },
    createAlert:       function (p)     { return req('/api/alerts', { method: 'POST', body: p }); },
    updateAlert:       function (a, p)  { return req('/api/alerts/' + encodeURIComponent(a), { method: 'PATCH', body: p }); },
    deleteAlert:       function (a)     { return req('/api/alerts/' + encodeURIComponent(a), { method: 'DELETE' }); },
    budgets:           function ()      { return req('/api/budgets'); },
    setSavingsGoal:    function (u, g, gid) { return req('/api/savings-goal', { method: 'PUT', body: { userId: u, goal: g, groupId: gid || null } }); },
    advices:           function (f)     { return req('/api/advices' + qs(f)); },
    members:           function ()      { return req('/api/family'); },
    categories:        function ()      { return req('/api/categories'); },
    reset:             function ()      { return Promise.resolve({ reset: false, note: '真後端不提供重置' }); }
  };

  var impl = MODE === 'http' ? http : mock;

  global.API = {
    mode: MODE, base: BASE,
    me:                function ()     { return impl.me(); },
    authState:         function ()     { return impl.authState(); },
    login:             function (c)    { return impl.login(c); },
    register:          function (p)    { return impl.register(p); },
    logout:            function ()     { return impl.logout(); },
    updateProfile:     function (p)    { return impl.updateProfile(p); },
    uploadAvatar:      function (d)    { return impl.uploadAvatar(d); },
    deleteAvatar:      function ()     { return impl.deleteAvatar(); },
    changePassword:    function (p)    { return impl.changePassword(p); },
    verifyPassword:    function (pw)   { return impl.verifyPassword(pw); },
    summary:           function (f)    { return impl.summary(f); },
    transactions:      function (f)    { return impl.transactions(f); },
    nlpParse:          function (t)    { return impl.nlpParse(t); },
    nlpParseBatch:     function (t)    { return impl.nlpParseBatch(t); },
    nlpConfirm:        function (p)    { return impl.nlpConfirm(p); },
    nlpConfirmBatch:   function (i)    { return impl.nlpConfirmBatch(i); },
    createTransaction: function (p)    { return impl.createTransaction(p); },
    deleteTransaction: function (i)    { return impl.deleteTransaction(i); },
    notifications:     function (f)    { return impl.notifications(f); },
    readNotification:  function (i)    { return impl.readNotification(i); },
    readNotifications: function (u)    { return impl.readNotifications(u); },
    groups:            function (f)    { return impl.groups(f); },
    createGroup:       function (p)    { return impl.createGroup(p); },
    updateGroup:       function (g, p) { return impl.updateGroup(g, p); },
    archiveGroup:      function (g)    { return impl.archiveGroup(g); },
    addGroupMember:    function (g, u) { return impl.addGroupMember(g, u); },
    removeGroupMember: function (g, u) { return impl.removeGroupMember(g, u); },
    allowances:        function ()     { return impl.allowances(); },
    setAllowance:      function (w, a) { return impl.setAllowance(w, a); },
    savingsGoals:      function ()     { return impl.savingsGoals(); },
    alerts:            function ()     { return impl.alerts(); },
    createAlert:       function (p)    { return impl.createAlert(p); },
    updateAlert:       function (a, p) { return impl.updateAlert(a, p); },
    deleteAlert:       function (a)    { return impl.deleteAlert(a); },
    budgets:           function ()     { return impl.budgets(); },
    setSavingsGoal:    function (u, g, gid) { return impl.setSavingsGoal(u, g, gid); },
    advices:           function (f)    { return impl.advices(f); },
    members:           function ()     { return impl.members(); },
    categories:        function ()     { return impl.categories(); },
    reset:             function ()     { return impl.reset(); }
  };
})(window);
