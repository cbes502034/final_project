/* ============================================================
   demo_seed.js — 測試專用的示範資料
   ------------------------------------------------------------
   ⚠️ 只給 backend/tests 的 node 測試用，**不會被前端載入**。
   前端上線的 data.js 已經沒有任何假資料：沒有範例帳號、沒有示範紀錄。

   為什麼測試還要一份：權限、帳本、監管這些規則要有「一家人」才驗得了——
   家長看得到子女、看不到沒指派的人、同帳本的人看得到那一本……
   每支測試自己從零註冊四個人再建關係，測試會比被測的程式還長。

   載入順序：data.js → 這個檔 → api.js（node 測試的 boot() 已經照這個順序）。
   示範的「今天」是 2026-09-10，測試會用 __FAMBUDGET_TODAY__ 固定。
   ============================================================ */
(function (D) {
  D.meta.family = '林家';
  Object.assign(D, {
    groups: [
      { id: 'G1', name: '家用', color: 'book-indigo', owner: 'U1',
        kind: 'standing', created: '2026-01-05', note: '日常開銷，全家共用' },
      { id: 'G2', name: '旅遊基金', color: 'book-violet', owner: 'U1',
        kind: 'standing', created: '2026-03-01', note: '為了出國先存起來的錢' },
      { id: 'G3', name: '宇涵的零用', color: 'book-teal', owner: 'U3',
        kind: 'standing', created: '2026-02-11', note: '打工收入與自己的開銷' },
      /* 到期日已經過了（種子寫的今天是 2026-09-10，載入時對齊真實日期，見檔案最後），畫面上會出現結算提示 */
      { id: 'G4', name: '沖繩旅遊', color: 'book-moss', owner: 'U1',
        kind: 'temp', endsOn: '2026-09-08', settledAt: null,
        created: '2026-08-20', note: '五天四夜，回來就結算' }
    ],

    groupMembers: [
      { group: 'G1', user: 'U1', notify: false }, { group: 'G1', user: 'U2', notify: false },
      { group: 'G1', user: 'U3', notify: false }, { group: 'G1', user: 'U4', notify: false },
      { group: 'G2', user: 'U1', notify: false }, { group: 'G2', user: 'U2', notify: false },
      { group: 'G3', user: 'U3', notify: false }, { group: 'G3', user: 'U1', notify: false },
      { group: 'G4', user: 'U1', notify: false }, { group: 'G4', user: 'U2', notify: false },
      { group: 'G4', user: 'U3', notify: false }, { group: 'G4', user: 'U4', notify: false }
    ],

    groupGoals: [
      { user: 'U1', group: 'G2', goal: 10000 },
      { user: 'U2', group: 'G2', goal: 6000 },
      { user: 'U3', group: 'G3', goal: 1500 }
    ],

    alerts: [
      { id: 'AL1', user: 'U1', group: null, percent: 60,  enabled: true,  firedPeriod: null },
      { id: 'AL2', user: 'U1', group: null, percent: 85,  enabled: true,  firedPeriod: null },
      { id: 'AL3', user: 'U1', group: null, percent: 100, enabled: true,  firedPeriod: null },
      { id: 'AL4', user: 'U1', group: 'G2', percent: 90,  enabled: true,  firedPeriod: null },
      { id: 'AL5', user: 'U3', group: null, percent: 80,  enabled: true,  firedPeriod: null }
    ],

    allowances: [
      { payer: 'U1', ward: 'U3', amount: 4000 },
      { payer: 'U1', ward: 'U4', amount: 3000 },
      { payer: 'U2', ward: 'U4', amount: 0 }
    ],

    members: [
      /* 平台管理員。⚠️ **刻意不屬於任何家庭，也不在任何帳本裡。**

         他能停權，但讀不到任何一筆帳——這一點在畫面上就看得出來：
         用他登入的時候，只有「平台管理」這一頁，沒有總覽、沒有記帳、沒有統計。
         那不是藏起來，是他真的沒有那些資料。

         停權是關門，不是配鑰匙。 */
      { id: 'U0', name: '系統管理員', email: 'admin@fambudget.tw', role: null,
        avatar: '管', age: null, isPlatformAdmin: true,
        joined: '2026-01-01', income: 0, expense: 0, budget: 0, savingsGoal: 0 },
      { id: 'U1', name: '林建國', email: 'jianguo@lin.tw', role: 'parent', familyId: 'F1', avatar: '國', age: 52,
        joined: '2026-01-05', income: 68000, expense: 41230, budget: 45000,
        savingsGoal: 20000,
        finance: { style: 'balanced', goals: ['house', 'education'],
                   habits: ['mortgage', 'insurance'],
                   note: '房貸還有十二年，小孩教育費是最優先的，旅遊可以省。' },
        monthly: [{ m: '2026-04', income: 68000, expense: 39519 }, { m: '2026-05', income: 68000, expense: 37680 }, { m: '2026-06', income: 85000, expense: 44609 }, { m: '2026-07', income: 68000, expense: 50725 }, { m: '2026-08', income: 68000, expense: 41572 }, { m: '2026-09', income: 68000, expense: 41230 }] },
      { id: 'U2', name: '陳淑芬', email: 'shufen@lin.tw', role: 'parent', familyId: 'F1', avatar: '芬', age: 49,
        joined: '2026-01-05', income: 52000, expense: 38900, budget: 40000,
        savingsGoal: 15000 ,
        monthly: [{ m: '2026-04', income: 52000, expense: 37286 }, { m: '2026-05', income: 52000, expense: 35551 }, { m: '2026-06', income: 52000, expense: 42088 }, { m: '2026-07', income: 52000, expense: 47858 }, { m: '2026-08', income: 52000, expense: 39223 }, { m: '2026-09', income: 52000, expense: 38900 }] },
      { id: 'U3', name: '林宇涵', email: 'yuhan@lin.tw', role: 'child', familyId: 'F1', avatar: '涵', age: 19,
        joined: '2026-02-11', income: 8000, expense: 11450, budget: 10000,
        savingsGoal: 2000 ,
        monthly: [{ m: '2026-04', income: 8000, expense: 10975 }, { m: '2026-05', income: 8000, expense: 10464 }, { m: '2026-06', income: 8000, expense: 12388 }, { m: '2026-07', income: 8000, expense: 14087 }, { m: '2026-08', income: 8000, expense: 11545 }, { m: '2026-09', income: 8000, expense: 11450 }] },
      { id: 'U4', name: '林宇軒', email: 'yuxuan@lin.tw', role: 'child', familyId: 'F1', avatar: '軒', age: 16,
        joined: '2026-02-11', income: 3000, expense: 4820, budget: 4000,
        savingsGoal: 500 ,
        monthly: [{ m: '2026-04', income: 3000, expense: 4620 }, { m: '2026-05', income: 3000, expense: 4405 }, { m: '2026-06', income: 3000, expense: 5215 }, { m: '2026-07', income: 3000, expense: 5930 }, { m: '2026-08', income: 3000, expense: 4860 }, { m: '2026-09', income: 3000, expense: 4820 }] },
      /* 還沒加入任何家庭的帳號——拿來示範「家庭綁定」。
         用家長登入，到「家庭成員」輸入 yuzhen@mail.tw 就能邀請她；
         或是用她登入，輸入家長產生的邀請碼加入。 */
      { id: 'U5', name: '林玉珍', email: 'yuzhen@mail.tw', role: null, familyId: null, avatar: '珍', age: 74,
        joined: '2026-09-01', income: 0, expense: 0, budget: 0, savingsGoal: 0,
        monthly: [{ m: '2026-04', income: 0, expense: 0 }, { m: '2026-05', income: 0, expense: 0 }, { m: '2026-06', income: 0, expense: 0 }, { m: '2026-07', income: 0, expense: 0 }, { m: '2026-08', income: 0, expense: 0 }, { m: '2026-09', income: 0, expense: 0 }] }
    ],

    families: [
      { id: 'F1', name: '林家', createdBy: 'U1', createdAt: '2026-01-05' }
    ],

    guardianships: [
      { guardian: 'U1', ward: 'U3', since: '2026-02-11', scope: '全部明細' },
      { guardian: 'U1', ward: 'U4', since: '2026-02-11', scope: '全部明細' },
      { guardian: 'U2', ward: 'U4', since: '2026-02-11', scope: '全部明細' }
    ],

    auditLogs: [
      { id: 'A1003', actor: 'U1', action: 'grant_guardianship',
        target: 'U4', at: '2026-02-11 09:20', note: '建立對林宇軒的監管' },
      { id: 'A1002', actor: 'U1', action: 'change_role',
        target: 'U3', at: '2026-02-11 09:18', note: '把林宇涵設為子女' },
      { id: 'A1001', actor: 'U1', action: 'create_family',
        target: null, at: '2026-01-05 21:04', note: '建立「林家」' }
    ],

    transactions: [
      { id: 'T1045', group: 'G1', user: 'U1', date: '2026-09-02', amount: 640, kind: 'expense',
        cat: 'C01', merchant: '早餐店', note: '', source: 'manual' },
      { id: 'T1046', group: 'G1', user: 'U1', date: '2026-09-04', amount: 980, kind: 'expense',
        cat: 'C01', merchant: '家庭聚餐', note: '', source: 'manual' },
      { id: 'T1047', group: 'G1', user: 'U1', date: '2026-09-06', amount: 1240, kind: 'expense',
        cat: 'C01', merchant: '午餐（週）', note: '', source: 'manual' },
      { id: 'T1048', group: 'G1', user: 'U1', date: '2026-09-03', amount: 1200, kind: 'expense',
        cat: 'C04', merchant: '好市多 補貨', note: '', source: 'manual' },
      { id: 'T1049', group: 'G1', user: 'U1', date: '2026-09-07', amount: 800, kind: 'expense',
        cat: 'C07', merchant: '診所掛號', note: '', source: 'manual' },
      { id: 'T1050', group: 'G1', user: 'U1', date: '2026-09-02', amount: 1200, kind: 'expense',
        cat: 'C02', merchant: '停車費與捷運', note: '', source: 'manual' },
      { id: 'T1051', group: 'G1', user: 'U1', date: '2026-09-09', amount: 900, kind: 'expense',
        cat: 'C08', merchant: '保險費分攤', note: '', source: 'manual' },
      { id: 'T1052', group: 'G1', user: 'U1', date: '2026-09-05', amount: 600, kind: 'expense',
        cat: 'C05', merchant: '第四台月費', note: '', source: 'manual' },
      { id: 'T1053', group: 'G1', user: 'U1', date: '2026-09-08', amount: 900, kind: 'expense',
        cat: 'C06', merchant: '書籍', note: '', source: 'manual' },
      { id: 'T1054', group: 'G1', user: 'U2', date: '2026-09-03', amount: 3200, kind: 'expense',
        cat: 'C01', merchant: '市場採買', note: '', source: 'manual' },
      { id: 'T1055', group: 'G1', user: 'U2', date: '2026-09-07', amount: 3000, kind: 'expense',
        cat: 'C01', merchant: '外食與外送', note: '', source: 'manual' },
      { id: 'T1056', group: 'G1', user: 'U2', date: '2026-09-04', amount: 5400, kind: 'expense',
        cat: 'C04', merchant: '日用品補貨', note: '', source: 'manual' },
      { id: 'T1057', group: 'G1', user: 'U2', date: '2026-09-06', amount: 3100, kind: 'expense',
        cat: 'C02', merchant: '油錢與計程車', note: '', source: 'manual' },
      { id: 'T1058', group: 'G1', user: 'U2', date: '2026-09-05', amount: 4800, kind: 'expense',
        cat: 'C06', merchant: '才藝班學費', note: '', source: 'manual' },
      { id: 'T1059', group: 'G1', user: 'U2', date: '2026-09-08', amount: 2350, kind: 'expense',
        cat: 'C07', merchant: '藥局與回診', note: '', source: 'manual' },
      { id: 'T1060', group: 'G1', user: 'U2', date: '2026-09-09', amount: 3000, kind: 'expense',
        cat: 'C08', merchant: '孝親費', note: '', source: 'manual' },
      { id: 'T1061', group: 'G3', user: 'U3', date: '2026-09-04', amount: 1980, kind: 'expense',
        cat: 'C01', merchant: '外食', note: '', source: 'manual' },
      { id: 'T1062', group: 'G3', user: 'U3', date: '2026-09-05', amount: 800, kind: 'expense',
        cat: 'C02', merchant: '通勤', note: '', source: 'manual' },
      { id: 'T1063', group: 'G3', user: 'U3', date: '2026-09-07', amount: 500, kind: 'expense',
        cat: 'C04', merchant: '生活用品', note: '', source: 'manual' },
      { id: 'T1064', group: 'G3', user: 'U3', date: '2026-09-09', amount: 400, kind: 'expense',
        cat: 'C06', merchant: '參考書', note: '', source: 'manual' },
      { id: 'T1065', group: 'G1', user: 'U4', date: '2026-09-03', amount: 1180, kind: 'expense',
        cat: 'C01', merchant: '學校午餐', note: '', source: 'manual' },
      { id: 'T1066', group: 'G1', user: 'U4', date: '2026-09-06', amount: 995, kind: 'expense',
        cat: 'C01', merchant: '便利商店', note: '', source: 'manual' },
      { id: 'T1067', group: 'G1', user: 'U4', date: '2026-09-05', amount: 630, kind: 'expense',
        cat: 'C02', merchant: '公車儲值', note: '', source: 'manual' },
      { id: 'T1068', group: 'G1', user: 'U4', date: '2026-09-07', amount: 700, kind: 'expense',
        cat: 'C04', merchant: '盥洗用品', note: '', source: 'manual' },
      { id: 'T1069', group: 'G1', user: 'U4', date: '2026-09-08', amount: 700, kind: 'expense',
        cat: 'C08', merchant: '班費', note: '', source: 'manual' },
      { id: 'T1044', group: 'G4', user: 'U1', date: '2026-09-09', amount: 12800, kind: 'expense',
        cat: 'C02', merchant: '訂機票（訂金）', note: '暑假沖繩', source: 'manual' },
      { id: 'T1043', group: 'G4', user: 'U2', date: '2026-09-06', amount: 4800, kind: 'expense',
        cat: 'C08', merchant: '訂房訂金', note: '', source: 'manual' },
      /* ⚠️ 帳本之間的轉帳，不是收入。
         家用轉 15,000 到旅遊基金，錢沒有進到這個家，只是換了一本帳。
         記成 income 的話收入會憑空多一筆——跟「零用金記成支出」同一種錯。
         kind 是 'transfer' 的列不進任何收支加總。 */
      { id: 'T1042', group: 'G2', user: 'U1', date: '2026-09-01', amount: 15000, kind: 'transfer',
        cat: 'I04', merchant: '旅遊基金轉入', note: '每月提撥', source: 'manual' },
      { id: 'T1041', group: 'G3', user: 'U3', date: '2026-09-10', amount: 1280, kind: 'expense',
        cat: 'C05', merchant: '遊戲點數儲值', note: '', source: 'nlp',
        raw: '剛剛儲值遊戲1280', parsed: { conf: 0.93, catConf: 0.88 } },
      { id: 'T1040', group: 'G1', user: 'U1', date: '2026-09-10', amount: 320, kind: 'expense',
        cat: 'C01', merchant: '公司附近自助餐', note: '午餐', source: 'nlp',
        raw: '中午自助餐320', parsed: { conf: 0.97, catConf: 0.95 } },
      { id: 'T1039', group: 'G1', user: 'U4', date: '2026-09-09', amount: 165, kind: 'expense',
        cat: 'C01', merchant: '全家便利商店', note: '', source: 'nlp',
        raw: '全家買了飲料跟麵包165', parsed: { conf: 0.96, catConf: 0.72 } },
      { id: 'T1038', group: 'G1', user: 'U2', date: '2026-09-09', amount: 2450, kind: 'expense',
        cat: 'C04', merchant: '家樂福', note: '週採買', source: 'manual' },
      { id: 'T1037', group: 'G3', user: 'U3', date: '2026-09-08', amount: 890, kind: 'expense',
        cat: 'C01', merchant: '燒烤店', note: '同學聚餐', source: 'manual' },
      { id: 'T1036', group: 'G1', user: 'U1', date: '2026-09-08', amount: 1150, kind: 'expense',
        cat: 'C02', merchant: '加油站', note: '', source: 'nlp',
        raw: '加油1150', parsed: { conf: 0.98, catConf: 0.96 } },
      { id: 'T1035', group: 'G1', user: 'U4', date: '2026-09-07', amount: 450, kind: 'expense',
        cat: 'C06', merchant: '文具行', note: '參考書', source: 'manual' },
      { id: 'T1034', group: 'G3', user: 'U3', date: '2026-09-06', amount: 2200, kind: 'expense',
        cat: 'C05', merchant: '演唱會票', note: '', source: 'manual' },
      { id: 'T1033', group: 'G1', user: 'U2', date: '2026-09-05', amount: 52000, kind: 'income',
        cat: 'I01', merchant: '公司薪轉', note: '9月薪資', source: 'manual' },
      { id: 'T1032', group: 'G1', user: 'U1', date: '2026-09-05', amount: 68000, kind: 'income',
        cat: 'I01', merchant: '公司薪轉', note: '9月薪資', source: 'manual' },
      { id: 'T1031', group: 'G1', user: 'U1', date: '2026-09-05', amount: 18500, kind: 'expense',
        cat: 'C03', merchant: '房貸', note: '', source: 'manual' },
      { id: 'T1030', group: 'G1', user: 'U4', date: '2026-09-04', amount: 3000, kind: 'income',
        cat: 'I03', merchant: '零用錢', note: '', source: 'manual' },
      { id: 'T1029', group: 'G3', user: 'U3', date: '2026-09-03', amount: 8000, kind: 'income',
        cat: 'I03', merchant: '打工薪資', note: '', source: 'manual' },
      { id: 'T1028', group: 'G3', user: 'U3', date: '2026-09-02', amount: 3400, kind: 'expense',
        cat: 'C05', merchant: '線上訂閱', note: '三個平台', source: 'nlp',
        raw: '訂閱費三個平台3400', parsed: { conf: 0.91, catConf: 0.84 } },
      { id: 'T1027', group: 'G1', user: 'U2', date: '2026-09-02', amount: 6800, kind: 'expense',
        cat: 'C07', merchant: '牙醫診所', note: '植牙分期', source: 'manual' }
    ],

    nlpDemo: [
      { raw: '今天午餐吃了120',
        out: { date: '2026-09-10', amount: 120, kind: 'expense', cat: 'C01',
               merchant: '', conf: 0.96, catConf: 0.94 },
        note: '「今天」要換算成實際日期；「午餐」→ 餐飲' },
      { raw: '全家買飲料跟麵包165',
        out: { date: '2026-09-10', amount: 165, kind: 'expense', cat: 'C01',
               merchant: '全家便利商店', conf: 0.96, catConf: 0.72 },
        note: '「全家」是店名不是家人。分類信心較低——便利商店可能是餐飲也可能是日用品' },
      { raw: '昨天加油1150悠遊卡付的',
        out: { date: '2026-09-09', amount: 1150, kind: 'expense', cat: 'C02',
               merchant: '加油站', conf: 0.94, catConf: 0.96 },
        note: '「昨天」相對日期；付款方式要另存到 account 欄位' },
      { raw: '媽媽給我兩千',
        out: { date: '2026-09-10', amount: 2000, kind: 'income', cat: 'I03',
               merchant: '', conf: 0.88, catConf: 0.79 },
        note: '「兩千」中文數字；收入而非支出；「媽媽給」→ 零用金' },
      { raw: '三個平台訂閱費共3400',
        out: { date: '2026-09-10', amount: 3400, kind: 'expense', cat: 'C05',
               merchant: '線上訂閱', conf: 0.91, catConf: 0.84 },
        note: '「共」表示合計；訂閱歸娛樂還是其他，需要標註準則定義' }
    ],

    paragraphDemo: {
      raw: '早上買早餐55，中午跟同事吃飯320，下午在全家買咖啡，晚上加油1200，今天打工賺了1500',
      items: [
        { seq: 1, span: '早上買早餐55',
          date: '2026-09-10', amount: 55, kind: 'expense', cat: 'C01',
          merchant: '', note: '早餐',
          conf: { date: .92, amount: .98, kind: .97, cat: .95 }, missing: [] },
        { seq: 2, span: '中午跟同事吃飯320',
          date: '2026-09-10', amount: 320, kind: 'expense', cat: 'C01',
          merchant: '', note: '與同事聚餐',
          conf: { date: .92, amount: .98, kind: .97, cat: .93 }, missing: [] },
        { seq: 3, span: '下午在全家買咖啡',
          date: '2026-09-10', amount: null, kind: 'expense', cat: 'C01',
          merchant: '全家便利商店', note: '咖啡',
          conf: { date: .92, amount: 0, kind: .94, cat: .68 },
          missing: ['amount'],
          hint: '這一句沒有寫金額。「全家」判定為店名而非家人；便利商店的分類信心較低，可能是餐飲也可能是日用品。' },
        { seq: 4, span: '晚上加油1200',
          date: '2026-09-10', amount: 1200, kind: 'expense', cat: 'C02',
          merchant: '加油站', note: '',
          conf: { date: .92, amount: .98, kind: .97, cat: .96 }, missing: [] },
        { seq: 5, span: '今天打工賺了1500',
          date: '2026-09-10', amount: 1500, kind: 'income', cat: 'I03',
          merchant: '', note: '打工',
          conf: { date: .96, amount: .97, kind: .95, cat: .82 },
          missing: [],
          hint: '「賺了」判定為收入。零用金與其他收入的界線需要由分類準則定義。' }
      ],
      note: '這段話被切成 5 筆。切分本身也是模型的判斷 —— 若切錯（例如把兩筆合成一筆），' +
            '欄位再準也沒用，所以切分結果同樣要讓使用者確認。'
    },

    budgets: [
      { user: 'U1', period: 'month', cat: 'C01', limit: 5000 },
      { user: 'U1', period: 'month', cat: 'C02', limit: 16000 },
      { user: 'U1', period: 'month', cat: 'C03', limit: 20000 },
      { user: 'U3', period: 'month', cat: 'C05', limit: 3000 },
      { user: 'U3', period: 'month', cat: 'C01', limit: 4000 },
      { user: 'U4', period: 'month', cat: 'C01', limit: 2000 },
      { user: 'U4', period: 'month', cat: 'C06', limit: 1500 }
    ],

    monthly: [
      { m: '2026-04', income: 131000, expense: 92400 },
      { m: '2026-05', income: 131000, expense: 88100 },
      { m: '2026-06', income: 148000, expense: 104300 },
      { m: '2026-07', income: 131000, expense: 118600 },
      { m: '2026-08', income: 131000, expense: 97200 },
      { m: '2026-09', income: 131000, expense: 96400 }
    ],

    yearly: [
      { y: '2024', income: 1428000, expense: 1102000 },
      { y: '2025', income: 1512000, expense: 1188000 },
      { y: '2026', income: 1180000, expense: 897000, partial: true }
    ],

    advices: [
      { id: 'A1', scope: 'family', period: '2026-09', level: 'warn',
        title: '娛樂支出連續三個月成長，主要來自宇涵',
        body: '本月家庭娛樂支出 7,480 元，較 6 月成長 62%。其中宇涵佔 6,880 元（92%），' +
              '已超出其個人娛樂預算 3,000 元的 129%。',
        basis: ['宇涵 2026-09 娛樂類支出 6,880 元（預算 3,000 元）',
                '家庭娛樂類：7 月 4,610 → 8 月 5,900 → 9 月 7,480'],
        suggest: ['與宇涵討論調整娛樂預算上限，或改為每季檢視一次',
                  '訂閱類支出 3,400 元佔娛樂支出 45%，可檢視是否有重複或閒置的訂閱'],
        conf: 0.92 },

      { id: 'A2', scope: 'family', period: '2026-09', level: 'info',
        title: '居住支出佔比穩定，房貸為最大單一項目',
        body: '本月居住類 18,500 元，佔家庭總支出 19%，與前六個月平均 19.2% 一致。',
        basis: ['2026-09 居住類 18,500 元 ÷ 總支出 96,400 元 = 19.2%'],
        suggest: ['此項為固定支出，短期無調整空間，建議維持現狀觀察'],
        conf: 0.97 },

      /* 個人建議是寫給**本人**看的，所以用第二人稱、不點名。
         家長在「全家」模式看得到監管對象的這一則，畫面上會標是誰的。 */
      { id: 'A3', scope: 'user', user: 'U4', period: '2026-09', level: 'warn',
        title: '餐飲花得比預算多一點',
        body: '這個月餐飲 2,340 元，比預算 2,000 元多了 17%。' +
              '照現在的速度，月底大約會到 7,020 元。',
        basis: ['2026-09 餐飲類支出 2,340 元（預算 2,000 元）',
                '前 10 天平均每日 234 元 × 30 天 = 7,020 元'],
        suggest: ['看看最近幾筆外食，決定要少吃幾次，還是把預算調高'],
        conf: 0.89 },

      { id: 'A5', scope: 'user', user: 'U3', period: '2026-09', level: 'warn',
        title: '娛樂的錢這個月花得比較多',
        body: '這個月娛樂 6,880 元，是預算 3,000 元的 229%。',
        basis: ['2026-09 娛樂類支出 6,880 元 ÷ 預算 3,000 元 = 229%'],
        suggest: ['訂閱類佔了不少，可以檢查有沒有用不到的',
                  '如果這是常態，把娛樂預算調到比較實際的數字'],
        conf: 0.9 },

      { id: 'A6', scope: 'user', user: 'U1', period: '2026-09', level: 'info',
        title: '交通費快用完這個月的預算',
        body: '這個月交通 15,150 元，已經用掉預算 16,000 元的 95%。',
        basis: ['2026-09 交通類支出 15,150 元 ÷ 預算 16,000 元 = 95%'],
        suggest: ['月底前還有加油或停車的話，大概會稍微超過一點'],
        conf: 0.93 },

      { id: 'A7', scope: 'user', user: 'U2', period: '2026-09', level: 'ok',
        title: '這個月存下了四分之一',
        body: '收入 52,000 元、支出 38,900 元，存下 13,100 元。',
        basis: ['2026-09 收入 52,000 元 − 支出 38,900 元 = 13,100 元',
                '13,100 ÷ 52,000 = 25.2%'],
        suggest: ['照這個節奏，每月存款目標可以維持不變'],
        conf: 0.98 },

      { id: 'A4', scope: 'family', period: '2026-09', level: 'ok',
        title: '本月結餘為正，儲蓄率 26.4%',
        body: '收入 131,000 元、支出 96,400 元，結餘 34,600 元。',
        basis: ['2026-09 收入 131,000 元 − 支出 96,400 元 = 34,600 元',
                '34,600 ÷ 131,000 = 26.4%'],
        suggest: ['近六個月結餘率介於 9.5%–32.8%，本月屬中上水準'],
        conf: 0.99 }
    ]
  });
})(window.DATA);
