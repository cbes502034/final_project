/* ============================================================
   data.js — 前端原型的模擬資料集
   ------------------------------------------------------------
   家庭記帳與財務控管系統

   全部為模擬資料。人名、金額、店家皆為虛構示範樣本。
   欄位結構即為後端 API 與資料表的契約草案。
   ============================================================ */
window.DATA = {

  meta: {
    family: '林家',
    period: '2026-09',
    updated: '2026-09-10 14:20',
    currency: 'TWD'
  },


  /* ---------- 帳本可以選的顏色 ----------
     ⚠️ 帳本色刻意跟分類色**分屬兩套**：分類回答「錢花在什麼」，
     帳本回答「這筆算哪一本帳」，兩者同時出現在圖表上，撞色就分不清。

     區別的方式是**明度**，不是色相：
       分類  飽和、中明度（亮度平均 0.165）
       帳本  墨色系，明顯更深更濁（亮度平均 0.075）

     用色相分會撐不住——分類已經佔掉赭藍紫綠紅琥珀，色輪上剩下的空間
     排不出六個還能彼此分開的顏色。用明度分，兩套都能用滿整個色輪。

     ⚠️ 而且深色在米白上一定安全。上一版用的是深色主題留下來的亮彩
     （#6EE7B7 之類），在米白上對比只有 1.35——那顆小圓點等於看不見。
     測試會擋住太淡的顏色。 */
  groupColors: [
    { hex: '#27405E', name: '墨藍' },
    { hex: '#4A3F6B', name: '墨紫' },
    { hex: '#1F5E63', name: '墨青' },
    { hex: '#2F5D3A', name: '墨綠' },
    { hex: '#7A4A2E', name: '墨赭' },
    { hex: '#7A2F3C', name: '墨酒紅' }
  ],

  /* ---------- 群組（一個家庭可以開好幾本帳） ----------
     仿家族群組的做法：記帳除了有「分類」，還有「這筆算在哪一本帳上」。
     分類回答「錢花在什麼」，群組回答「這筆屬於哪一份預算」。
     每一本帳可以各自設一個每月存款目標。 */
  groups: [
    { id: 'G1', name: '家用', icon: '家', color: '#27405E', owner: 'U1',
      created: '2026-01-05', note: '日常開銷，全家共用' },
    { id: 'G2', name: '旅遊基金', icon: '旅', color: '#4A3F6B', owner: 'U1',
      created: '2026-03-01', note: '存暑假出國的錢，花費也記在這裡' },
    { id: 'G3', name: '宇涵的零用', icon: '涵', color: '#1F5E63', owner: 'U3',
      created: '2026-02-11', note: '打工收入與自己的開銷' }
  ],

  /* 誰在哪個群組裡。這是可見範圍的**另一條路**，不是第二道關卡——
     ⚠️ 跟監管關係是**聯集**：
          A 我監管的人記的，跨所有帳本都看得到（監管不該被帳本切斷）
          B 我有加入的帳本裡的，那本帳的成員彼此看得到（加進來就是給看）
        過一條就看得到。早期版本用交集，那讓監管一鍵可繞：
        被監管的人只要另外開一本不加監管者的帳就躲掉了。 */
  groupMembers: [
    { group: 'G1', user: 'U1' }, { group: 'G1', user: 'U2' },
    { group: 'G1', user: 'U3' }, { group: 'G1', user: 'U4' },
    { group: 'G2', user: 'U1' }, { group: 'G2', user: 'U2' },
    { group: 'G3', user: 'U3' }, { group: 'G3', user: 'U1' }
  ],

  /* 每月存款目標可以分群組設。group 為 null = 不分群組的整體目標。
     整體目標仍然是 members[].savingsGoal，這裡放的是「額外針對某一本帳」的。 */
  groupGoals: [
    { user: 'U1', group: 'G2', goal: 10000 },
    { user: 'U2', group: 'G2', goal: 6000 },
    { user: 'U3', group: 'G3', goal: 1500 }
  ],

  /* 階段性提醒：使用者自己設幾個百分比門檻。
     支出佔可支配上限的比例跨過門檻，就發一則通知（走既有的通知鈴鐺）。
     ⚠️ 同一個門檻一個月只會響一次，靠 firedPeriod 記住。 */
  alerts: [
    { id: 'AL1', user: 'U1', group: null, percent: 60,  enabled: true,  firedPeriod: null },
    { id: 'AL2', user: 'U1', group: null, percent: 85,  enabled: true,  firedPeriod: null },
    { id: 'AL3', user: 'U1', group: null, percent: 100, enabled: true,  firedPeriod: null },
    { id: 'AL4', user: 'U1', group: 'G2', percent: 90,  enabled: true,  firedPeriod: null },
    { id: 'AL5', user: 'U3', group: null, percent: 80,  enabled: true,  firedPeriod: null }
  ],

  /* 每月給被監管者多少零用金。
     ⚠️ 這是設定，不是支出紀錄——家長不要另外記一筆「給小孩 3000」，
     否則小孩把那 3000 花掉之後，同一筆錢會被算兩次。 */
  allowances: [
    { payer: 'U1', ward: 'U3', amount: 4000 },
    { payer: 'U1', ward: 'U4', amount: 3000 },
    { payer: 'U2', ward: 'U4', amount: 0 }
  ],

  /* ---------- 家庭成員與角色 ---------- */
  roles: [
    { id: 'master', name: '平台管理員', layer: '平台',
      desc: '系統層級，不屬於任何家庭。只能停權與查稽核——看不到任何人的收支明細' },
    { id: 'parent', name: '家長', layer: '家庭',
      desc: '家庭治理：邀請成員、設家庭預算、建立監管關係。看得到誰仍然只看監管關係' },
    { id: 'child', name: '子女', layer: '家庭',
      desc: '記自己的帳。被監管時，畫面上一定看得到是誰在看' }
  ],

  /* savingsGoal 是註冊時就要填的「每月想存多少」。
     可支配上限 = 收入 − 存款目標，支出超過就代表這個月存不到目標。 */
  members: [
    { id: 'U1', name: '林建國', email: 'jianguo@lin.tw', role: 'parent', avatar: '國', age: 52,
      joined: '2026-01-05', income: 68000, expense: 41230, budget: 45000,
      savingsGoal: 20000 ,
      monthly: [{ m: '2026-04', income: 68000, expense: 39519 }, { m: '2026-05', income: 68000, expense: 37680 }, { m: '2026-06', income: 85000, expense: 44609 }, { m: '2026-07', income: 68000, expense: 50725 }, { m: '2026-08', income: 68000, expense: 41572 }, { m: '2026-09', income: 68000, expense: 41230 }] },
    { id: 'U2', name: '陳淑芬', email: 'shufen@lin.tw', role: 'parent', avatar: '芬', age: 49,
      joined: '2026-01-05', income: 52000, expense: 38900, budget: 40000,
      savingsGoal: 15000 ,
      monthly: [{ m: '2026-04', income: 52000, expense: 37286 }, { m: '2026-05', income: 52000, expense: 35551 }, { m: '2026-06', income: 52000, expense: 42088 }, { m: '2026-07', income: 52000, expense: 47858 }, { m: '2026-08', income: 52000, expense: 39223 }, { m: '2026-09', income: 52000, expense: 38900 }] },
    { id: 'U3', name: '林宇涵', email: 'yuhan@lin.tw', role: 'child', avatar: '涵', age: 19,
      joined: '2026-02-11', income: 8000, expense: 11450, budget: 10000,
      savingsGoal: 2000 ,
      monthly: [{ m: '2026-04', income: 8000, expense: 10975 }, { m: '2026-05', income: 8000, expense: 10464 }, { m: '2026-06', income: 8000, expense: 12388 }, { m: '2026-07', income: 8000, expense: 14087 }, { m: '2026-08', income: 8000, expense: 11545 }, { m: '2026-09', income: 8000, expense: 11450 }] },
    { id: 'U4', name: '林宇軒', email: 'yuxuan@lin.tw', role: 'child', avatar: '軒', age: 16,
      joined: '2026-02-11', income: 3000, expense: 4820, budget: 4000,
      savingsGoal: 500 ,
      monthly: [{ m: '2026-04', income: 3000, expense: 4620 }, { m: '2026-05', income: 3000, expense: 4405 }, { m: '2026-06', income: 3000, expense: 5215 }, { m: '2026-07', income: 3000, expense: 5930 }, { m: '2026-08', income: 3000, expense: 4860 }, { m: '2026-09', income: 3000, expense: 4820 }] }
  ],

  /* 超支警告的分級門檻。刻意讓使用者看得到，因為每個人對「接近」的定義不同 */
  savingsRule: {
    warnAt: 0.8,          // 支出達可支配上限的 80% → 提醒
    overAt: 1.0,          // 超過 100% → 警告
    note: '可支配上限 = 本月收入 − 每月存款目標。支出超過上限，就代表這個月存不到原本設定的金額。'
  },

  /* 監管關係：誰看得到誰。刻意雙向透明——被監管者自己也看得到這張表 */
  guardianships: [
    { guardian: 'U1', ward: 'U3', since: '2026-02-11', scope: '全部明細' },
    { guardian: 'U1', ward: 'U4', since: '2026-02-11', scope: '全部明細' },
    { guardian: 'U2', ward: 'U4', since: '2026-02-11', scope: '全部明細' }
  ],

  /* ---------- 分類體系 ---------- */
  categories: [
    { id: 'C01', name: '餐飲', kind: 'expense', color: '#C4693C', icon: '食' },
    { id: 'C02', name: '交通', kind: 'expense', color: '#3C5FA0', icon: '行' },
    { id: 'C03', name: '居住', kind: 'expense', color: '#6A5B9E', icon: '住' },
    { id: 'C04', name: '日用品', kind: 'expense', color: '#2C7A56', icon: '用' },
    { id: 'C05', name: '娛樂', kind: 'expense', color: '#BE4239', icon: '樂' },
    { id: 'C06', name: '教育', kind: 'expense', color: '#B0741A', icon: '學' },
    { id: 'C07', name: '醫療', kind: 'expense', color: '#3E8DA8', icon: '醫' },
    { id: 'C08', name: '其他', kind: 'expense', color: '#8A8E95', icon: '他' },
    { id: 'I01', name: '薪資', kind: 'income', color: '#2C7A56', icon: '薪' },
    { id: 'I02', name: '獎金', kind: 'income', color: '#1B6B5A', icon: '獎' },
    { id: 'I03', name: '零用金', kind: 'income', color: '#3C5FA0', icon: '零' },
    { id: 'I04', name: '其他收入', kind: 'income', color: '#8A8E95', icon: '收' }
  ],

  /* ---------- 交易明細（核心表） ---------- */
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
    { id: 'T1044', group: 'G2', user: 'U1', date: '2026-09-09', amount: 12800, kind: 'expense',
      cat: 'C02', merchant: '訂機票（訂金）', note: '暑假沖繩', source: 'manual' },
    { id: 'T1043', group: 'G2', user: 'U2', date: '2026-09-06', amount: 4800, kind: 'expense',
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

  /* ---------- 自然語言記帳的解析範例（給前端展示，也是評測資料來源） ---------- */
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

  /* ---------- 段落批次記帳的示範 ----------
     一段話裡可能有好幾筆。模型要先「切分」再逐筆抽欄位，
     切錯比抽錯更難發現，所以切分結果也要讓使用者確認。 */
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

  /* ---------- 預算（月／年兩個時間基準） ---------- */
  budgets: [
    { user: 'U1', period: 'month', cat: 'C01', limit: 8000, used: 6420 },
    { user: 'U1', period: 'month', cat: 'C02', limit: 4000, used: 3250 },
    { user: 'U1', period: 'month', cat: 'C03', limit: 20000, used: 18500 },
    { user: 'U3', period: 'month', cat: 'C05', limit: 3000, used: 6880 },
    { user: 'U3', period: 'month', cat: 'C01', limit: 4000, used: 3120 },
    { user: 'U4', period: 'month', cat: 'C01', limit: 2000, used: 2340 },
    { user: 'U4', period: 'month', cat: 'C06', limit: 1500, used: 450 }
  ],

  /* ---------- 月度與年度統計 ---------- */
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

  /* ---------- LLM 產生的財務控管建議 ---------- */
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

    { id: 'A3', scope: 'user', user: 'U4', period: '2026-09', level: 'warn',
      title: '宇軒的餐飲支出已超出預算',
      body: '本月餐飲 2,340 元，超出預算 2,000 元的 17%。目前為 9 月 10 日，' +
            '若維持相同速度，月底預估將達 7,020 元。',
      basis: ['宇軒 2026-09 餐飲類支出 2,340 元（預算 2,000 元）',
              '前 10 天平均每日 234 元 × 30 天 = 7,020 元'],
      suggest: ['與宇軒確認是否有特殊支出，或調整預算至合理水準'],
      conf: 0.89 },

    { id: 'A4', scope: 'family', period: '2026-09', level: 'ok',
      title: '本月結餘為正，儲蓄率 26.9%',
      body: '收入 131,000 元、支出 96,400 元，結餘 34,600 元。',
      basis: ['2026-09 收入 131,000 元 − 支出 96,400 元 = 34,600 元',
              '34,600 ÷ 131,000 = 26.4%'],
      suggest: ['近六個月結餘率介於 9.5%–32.8%，本月屬中上水準'],
      conf: 0.99 }
  ],

  /* 系統對建議的邊界規則（畫面上會顯示，也是設計上的硬約束） */
  adviceRules: [
    { rule: '金額一律由資料庫計算', why: '模型只負責敘述與歸納，任何數字都不得由模型生成' },
    { rule: '每一條建議都要附「依據」', why: '使用者要能自己驗算，不能是黑盒子結論' },
    { rule: '不提供投資、保險、稅務建議', why: '這些屬於受規範的專業意見，超出本系統範圍' },
    { rule: '不對個人做價值判斷', why: '只描述數字與趨勢，不說「你太浪費」這類評價' },
    { rule: '受監管者的建議同時送給監管者', why: '監管是本系統的設計目的，但必須雙方都看得到' }
  ],

  /* ---------- 自然語言記帳的評測（明樺的工作） ---------- */
  nlpEval: [
    { task: '金額抽取', metric: 'Exact Match', base: 0.91, ft: 0.98, target: 0.97 },
    { task: '日期解析（含相對日期）', metric: 'Exact Match', base: 0.74, ft: 0.94, target: 0.92 },
    { task: '收支方向判定', metric: 'Accuracy', base: 0.88, ft: 0.97, target: 0.95 },
    { task: '分類指派', metric: 'Macro-F1', base: 0.61, ft: 0.86, target: 0.85 },
    { task: '店家名稱抽取', metric: 'F1', base: 0.55, ft: 0.81, target: 0.78 },
    { task: '一次輸入完全正確率', metric: '全欄位皆對', base: 0.42, ft: 0.79, target: 0.75 }
  ],

  /* ---------- 資料庫架構 ---------- */
  schema: [
    { t: 'users', label: '使用者帳號', note: '登入身分，與家庭角色分開',
      cols: [['id', 'BIGSERIAL', 'PK'], ['email', 'TEXT', 'UNIQUE'],
             ['password_hash', 'TEXT', 'bcrypt / argon2，絕不存明碼'],
             ['display_name', 'TEXT', ''],
             ['birth_year', 'INT', '個人資料。⚠️ 不參與任何權限判斷'],
             ['is_platform_admin', 'BOOLEAN', '平台管理員。與家庭角色無關，且看不到任何財務資料'],
             ['created_at', 'TIMESTAMPTZ', ''], ['last_login_at', 'TIMESTAMPTZ', '']] },

    { t: 'savings_goals', label: '每月存款目標', note: '★ 註冊時就要填。改過的值保留歷史，不覆蓋',
      cols: [['id', 'BIGSERIAL', 'PK'], ['user_id', 'BIGINT', 'FK → users'],
             ['group_id', 'BIGINT', 'FK → groups。NULL = 不分群組的整體目標'],
             ['period_key', 'TEXT', "'2026-09'。NULL = 預設值，套用到所有未指定的月份"],
             ['goal_amount', 'NUMERIC(14,2)', '每月想存多少'],
             ['warn_ratio', 'NUMERIC', '達可支配上限的幾成時提醒，預設 0.8'],
             ['created_at', 'TIMESTAMPTZ', ''],
             ['created_by', 'BIGINT', '本人，或監管我的人代設']] },

    { t: 'sessions', label: '登入工作階段', note: '支援登出與強制下線',
      cols: [['id', 'UUID', 'PK'], ['user_id', 'BIGINT', 'FK → users'],
             ['refresh_token_hash', 'TEXT', '只存雜湊'],
             ['user_agent', 'TEXT', ''], ['ip_hash', 'TEXT', ''],
             ['issued_at', 'TIMESTAMPTZ', ''], ['expires_at', 'TIMESTAMPTZ', ''],
             ['revoked_at', 'TIMESTAMPTZ', 'NULL = 仍有效']] },

    { t: 'families', label: '家庭', note: '一個家庭一列',
      cols: [['id', 'BIGSERIAL', 'PK'], ['name', 'TEXT', '例如「林家」'],
             ['created_by', 'BIGINT', 'FK → users，開這個家的人。⚠️ 僅供稽核，不給任何額外權限'],
             ['currency', 'TEXT', "預設 'TWD'"],
             ['invite_code', 'TEXT', '邀請碼，可重新產生'],
             ['created_at', 'TIMESTAMPTZ', '']] },

    { t: 'family_members', label: '家庭成員與角色', note: '一人可屬於多個家庭',
      cols: [['family_id', 'BIGINT', 'PK, FK → families'],
             ['user_id', 'BIGINT', 'PK, FK → users'],
             ['role', 'TEXT', "'parent' / 'child'。只決定治理動作，不決定可見度"],
             ['joined_at', 'TIMESTAMPTZ', ''],
             ['status', 'TEXT', "'active' / 'invited' / 'removed'"]] },

    { t: 'guardianships', label: '監管關係', note: '誰看得到誰的明細。雙方都看得到這張表',
      cols: [['id', 'BIGSERIAL', 'PK'],
             ['guardian_id', 'BIGINT', 'FK → users'],
             ['ward_id', 'BIGINT', 'FK → users'],
             ['scope', 'TEXT', "'all' / 'summary_only'"],
             ['created_by', 'BIGINT', 'FK → users，只有家長能建立'],
             ['since', 'TIMESTAMPTZ', ''], ['ended_at', 'TIMESTAMPTZ', '']] },

    { t: 'accounts', label: '帳戶／錢包', note: '現金、銀行、悠遊卡、信用卡',
      cols: [['id', 'BIGSERIAL', 'PK'], ['user_id', 'BIGINT', 'FK → users'],
             ['name', 'TEXT', ''], ['kind', 'TEXT', "'cash' / 'bank' / 'card' / 'ecard'"],
             ['balance', 'NUMERIC(14,2)', ''], ['is_active', 'BOOLEAN', '']] },

    { t: 'categories', label: '分類', note: '系統預設 + 家庭自訂',
      cols: [['id', 'BIGSERIAL', 'PK'], ['family_id', 'BIGINT', 'NULL = 系統預設'],
             ['name', 'TEXT', ''], ['kind', 'TEXT', "'income' / 'expense'"],
             ['parent_id', 'BIGINT', '支援兩層分類'],
             ['color', 'TEXT', ''], ['sort_order', 'INT', '']] },

    { t: 'transactions', label: '收支明細', note: '核心表。所有統計都從這裡算',
      cols: [['id', 'BIGSERIAL', 'PK'], ['user_id', 'BIGINT', 'FK → users'],
             ['group_id', 'BIGINT', 'FK → groups，這筆算在哪一本帳上。INDEX'],
             ['family_id', 'BIGINT', 'FK → families，INDEX'],
             ['account_id', 'BIGINT', 'FK → accounts'],
             ['category_id', 'BIGINT', 'FK → categories'],
             ['kind', 'TEXT', "'income' / 'expense' / 'transfer'。⚠️ transfer 不進任何收支加總"],
             ['amount', 'NUMERIC(14,2)', '一律正數，方向看 kind'],
             ['occurred_on', 'DATE', 'INDEX，統計用'],
             ['merchant', 'TEXT', ''], ['note', 'TEXT', ''],
             ['source', 'TEXT', "'manual' / 'nlp' / 'import'"],
             ['created_at', 'TIMESTAMPTZ', ''], ['updated_at', 'TIMESTAMPTZ', '']] },

    { t: 'nlp_parses', label: '自然語言記帳解析紀錄', note: '★ 這是 LLM 評測的資料來源',
      cols: [['id', 'BIGSERIAL', 'PK'],
             ['transaction_id', 'BIGINT', 'FK → transactions，NULL = 使用者放棄'],
             ['user_id', 'BIGINT', 'FK → users'],
             ['raw_text', 'TEXT', '使用者原始輸入'],
             ['parsed_json', 'JSONB', '模型輸出的結構化結果'],
             ['confidence', 'NUMERIC', ''], ['cat_confidence', 'NUMERIC', ''],
             ['user_corrected', 'JSONB', '使用者修正後的值，NULL = 未修正'],
             ['model_ver', 'TEXT', '換模型要能分開比較'],
             ['created_at', 'TIMESTAMPTZ', '']] },

    { t: 'budgets', label: '預算', note: '月與年兩種週期',
      cols: [['id', 'BIGSERIAL', 'PK'], ['user_id', 'BIGINT', 'NULL = 家庭總預算'],
             ['family_id', 'BIGINT', 'FK → families'],
             ['category_id', 'BIGINT', 'NULL = 總額預算'],
             ['period_type', 'TEXT', "'month' / 'year'"],
             ['period_key', 'TEXT', "'2026-09' 或 '2026'"],
             ['limit_amount', 'NUMERIC(14,2)', ''],
             ['created_by', 'BIGINT', 'FK → users']] },

    { t: 'advices', label: 'LLM 財務建議', note: '每月結算後產生，附依據',
      cols: [['id', 'BIGSERIAL', 'PK'], ['family_id', 'BIGINT', 'FK → families'],
             ['user_id', 'BIGINT', 'NULL = 家庭層級建議'],
             ['period_type', 'TEXT', "'month' / 'year'"],
             ['period_key', 'TEXT', ''],
             ['level', 'TEXT', "'ok' / 'info' / 'warn'"],
             ['title', 'TEXT', 'LLM 生成'], ['body', 'TEXT', 'LLM 生成'],
             ['basis_json', 'JSONB', '★ 依據的數字，由後端計算後餵給模型'],
             ['suggestions_json', 'JSONB', 'LLM 生成'],
             ['model_ver', 'TEXT', ''], ['generated_at', 'TIMESTAMPTZ', '']] },

    { t: 'notifications', label: '通知', note: '★ 監管對象記帳、或支出跨過提醒門檻時寫一列',
      cols: [['id', 'BIGSERIAL', 'PK'],
             ['recipient_id', 'BIGINT', 'FK → users，收件人。查詢一律 WHERE recipient_id = 我'],
             ['actor_id', 'BIGINT', 'FK → users，做這件事的人。系統發的為 NULL'],
             ['type', 'TEXT', "'ward_transaction' / 'budget_alert'"],
             ['transaction_id', 'BIGINT', 'FK → transactions，非記帳類通知為 NULL'],
             ['payload_json', 'JSONB', '提醒類通知放門檻百分比、群組、金額'],
             ['read_at', 'TIMESTAMPTZ', 'NULL = 未讀。紅點數字就是數這個'],
             ['created_at', 'TIMESTAMPTZ', '與 recipient_id 做複合索引，輪詢查得快']] },

    { t: 'groups', label: '群組（帳本）', note: '★ 一個家庭可以開好幾本帳，各自有自己的存款目標',
      cols: [['id', 'BIGSERIAL', 'PK'], ['family_id', 'BIGINT', 'FK → families'],
             ['name', 'TEXT', '例如「家用」「旅遊基金」'],
             ['icon', 'TEXT', '一個字，畫面上的圓標'],
             ['color', 'TEXT', '圖表與標籤的顏色'],
             ['created_by', 'BIGINT', 'FK → users'],
             ['created_at', 'TIMESTAMPTZ', ''],
             ['archived_at', 'TIMESTAMPTZ', 'NULL = 使用中。封存不刪除，舊紀錄要留著']] },

    { t: 'group_members', label: '群組成員', note: '可見範圍的另一條路：我在這本帳裡就看得到這本帳',
      cols: [['group_id', 'BIGINT', 'PK, FK → groups'],
             ['user_id', 'BIGINT', 'PK, FK → users'],
             ['joined_at', 'TIMESTAMPTZ', ''],
             ['can_write', 'BOOLEAN', 'false = 只能看這本帳，不能往裡面記']] },

    { t: 'alert_rules', label: '階段性提醒門檻', note: '★ 使用者自己設幾個百分比，跨過就通知',
      cols: [['id', 'BIGSERIAL', 'PK'], ['user_id', 'BIGINT', 'FK → users'],
             ['group_id', 'BIGINT', 'FK → groups。NULL = 針對整體目標'],
             ['percent', 'INT', '支出佔可支配上限的百分比，1~200'],
             ['enabled', 'BOOLEAN', '關掉但不刪除，使用者常常只是暫時不想被吵'],
             ['fired_period', 'TEXT', "'2026-09'。⚠️ 同一個門檻一個月只響一次，靠這欄擋"],
             ['created_at', 'TIMESTAMPTZ', '']] },

    { t: 'allowances', label: '每月零用金', note: '★ 設定，不是支出紀錄。家長每月給某個被監管者多少',
      cols: [['id', 'BIGSERIAL', 'PK'],
             ['payer_id', 'BIGINT', 'FK → users，給錢的人'],
             ['ward_id', 'BIGINT', 'FK → users，收錢的人'],
             ['amount', 'NUMERIC(14,2)', '每月金額'],
             ['period_key', 'TEXT', "'2026-09'。NULL = 預設值，套用到未指定的月份"],
             ['created_at', 'TIMESTAMPTZ', '']] },

    { t: 'audit_logs', label: '稽核紀錄', note: '誰看了誰的資料、誰改了權限',
      cols: [['id', 'BIGSERIAL', 'PK'], ['actor_id', 'BIGINT', 'FK → users'],
             ['action', 'TEXT', "'view_ward' / 'grant_guardianship' / 'change_role' …"],
             ['target_type', 'TEXT', ''], ['target_id', 'BIGINT', ''],
             ['meta_json', 'JSONB', ''], ['created_at', 'TIMESTAMPTZ', '']] }
  ],

  relations: [
    ['sessions', 'users', 'N:1', ''],
    ['allowances', 'users', 'N:1', '給錢的人與收錢的人'],
    ['notifications', 'users', 'N:1', '收件人'],
    ['notifications', 'transactions', 'N:1', '記帳類通知指到那一筆'],
    ['groups', 'families', 'N:1', ''],
    ['group_members', 'groups', 'N:1', ''],
    ['group_members', 'users', 'N:1', ''],
    ['transactions', 'groups', 'N:1', '★每一筆都屬於一本帳'],
    ['savings_goals', 'groups', 'N:1', 'NULL = 整體目標'],
    ['alert_rules', 'users', 'N:1', ''],
    ['alert_rules', 'groups', 'N:1', 'NULL = 針對整體目標'],
    ['savings_goals', 'users', 'N:1', '★存款目標'],
    ['family_members', 'users', 'N:1', ''],
    ['family_members', 'families', 'N:1', ''],
    ['guardianships', 'users', 'N:1', '監管'],
    ['accounts', 'users', 'N:1', ''],
    ['transactions', 'users', 'N:1', ''],
    ['transactions', 'families', 'N:1', ''],
    ['transactions', 'accounts', 'N:1', ''],
    ['transactions', 'categories', 'N:1', ''],
    ['nlp_parses', 'transactions', '1:1', '★評測'],
    ['budgets', 'families', 'N:1', ''],
    ['budgets', 'categories', 'N:1', ''],
    ['advices', 'families', 'N:1', ''],
    ['audit_logs', 'users', 'N:1', '']
  ],

  /* ---------- 權限矩陣（家庭內） ----------
     只有兩層：家長、子女。

     ⚠️ 角色決定的是「能做什麼治理動作」，不是「能看到誰」。
     可見度一律只看監管關係——所以下面有好幾列兩欄一模一樣，
     那正是重點：那些事情跟你在家裡的階級無關。 */
  permissions: [
    { action: '記錄自己的收支', parent: 'Y', child: 'Y' },
    { action: '查看自己的統計', parent: 'Y', child: 'Y' },
    { action: '設定自己的預算', parent: 'Y', child: 'Y' },
    { action: '設定每月存款目標', parent: 'Y', child: 'Y（監管者可代設）' },
    { action: '查看被監管者的明細', parent: 'Y（被指派的）', child: 'Y（被指派的）' },
    { action: '查看沒有指派給自己的人', parent: 'N', child: 'N' },
    { action: '修改／刪除被監管者的紀錄', parent: 'N', child: 'N' },
    { action: '登入被監管者的帳號', parent: 'N', child: 'N' },
    { action: '收到被監管者新增紀錄的通知', parent: 'Y（被指派的）', child: 'Y（被指派的）' },
    { action: '查看家庭總覽', parent: 'Y', child: 'N' },
    { action: '設定家庭預算', parent: 'Y', child: 'N' },
    { action: '邀請／移除成員', parent: 'Y', child: 'N' },
    { action: '建立監管關係', parent: 'Y', child: 'N' },
    /* 群組不看角色：誰都可以開自己的帳本。
       ⚠️ 這是刻意的——記帳的分類方式是個人的事，不該由家裡的階級決定。 */
    { action: '建立群組（帳本）', parent: 'Y', child: 'Y' },
    { action: '管理自己建的群組', parent: 'Y', child: 'Y' },
    { action: '管理別人建的群組', parent: 'N', child: 'N' },
    { action: '設定自己的階段性提醒', parent: 'Y', child: 'Y' },
    { action: '查看「誰看得到我」', parent: 'Y（強制可見）', child: 'Y（強制可見）' },
    { action: '匯出資料', parent: 'Y（限可見範圍）', child: 'Y（限可見範圍）' }
  ],

  /* ---------- 平台管理員能做什麼 ----------
     ⚠️ 全部不碰任何人的財務資料。

     停權是關門，不是配鑰匙——這跟「管理人員不可以進入子女的帳號」
     是同一條原則。一個能讀全系統消費明細的帳號，比家長越權嚴重得多。 */
  platformPermissions: [
    { action: '停權違規帳號', master: 'Y' },
    { action: '解除停權', master: 'Y' },
    { action: '查看稽核紀錄', master: 'Y' },
    { action: '查看任何人的收支明細', master: 'N' },
    { action: '修改任何人的資料', master: 'N' },
    { action: '登入他人帳號', master: 'N' },
    { action: '加入或干預任何家庭', master: 'N' }
  ]
};
