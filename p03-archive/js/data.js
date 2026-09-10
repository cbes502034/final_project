/* ============================================================
   data.js — 前端原型的模擬資料集
   ------------------------------------------------------------
   第 3 題：使用者回報釣魚郵件自動分流與話術辨識平台

   全部為模擬資料。郵件內容、寄件人、網域都是虛構的示範樣本，
   不含任何真實郵件或個資。話術句式參考公開報導中的常見手法改寫。

   欄位結構即為之後後端 API 與資料表的契約草案。
   ============================================================ */
window.DATA = {

  meta: {
    org: '示範組織',
    shift: '2026-09-09 早班（08:00–16:00）',
    synced: '2026-09-09 15:42',
    source: '模擬資料。郵件內容為虛構示範樣本，不含真實郵件或個資。'
  },

  /* 六類話術體系 —— 由囷洧定義，技術指標抓不到的用 ✕ 標記 */
  tactics: [
    { id: 'T1', code: 'urgency', name: '急迫性',
      desc: '製造時間壓力，讓人來不及查證',
      example: '「24 小時內未處理將停用帳號」',
      techDetectable: false, loss: '中' },
    { id: 'T2', code: 'authority', name: '權威冒充',
      desc: '假冒銀行、政府、公司內部單位',
      example: '「本行資安部門通知」',
      techDetectable: 'partial', loss: '中高' },
    { id: 'T3', code: 'reward', name: '獎勵誘餌',
      desc: '以中獎、回饋、補助誘使點擊',
      example: '「您已獲得 3,000 元回饋金」',
      techDetectable: false, loss: '低' },
    { id: 'T4', code: 'threat', name: '恐嚇威脅',
      desc: '宣稱掌握隱私或違法紀錄',
      example: '「已掌握您的瀏覽紀錄」',
      techDetectable: false, loss: '中' },
    { id: 'T5', code: 'process_hijack', name: '流程劫持（BEC）',
      desc: '冒充內部或供應商要求變更匯款流程',
      example: '「本次請改匯至新帳戶」',
      techDetectable: false, loss: '最高' },
    { id: 'T6', code: 'tech_support', name: '技術支援詐騙',
      desc: '謊稱裝置中毒，誘導安裝工具',
      example: '「您的電腦已中毒，請安裝此工具」',
      techDetectable: 'partial', loss: '中' }
  ],

  /* 三層收斂：由便宜到貴，LLM 只在最後對群組跑一次 */
  dedup: [
    { level: 'L1', name: '精確比對',
      how: 'Message-ID／主旨雜湊／附件雜湊完全相同',
      cost: '幾乎為零', collapsed: 118, ms: 40 },
    { level: 'L2', name: '特徵比對',
      how: '寄件網域＋連結網域＋主旨模板相似度',
      cost: '低（字串運算）', collapsed: 104, ms: 310 },
    { level: 'L3', name: '語意分群',
      how: 'Sentence embedding ＋ 階層式分群',
      cost: '中（一次向量化）', collapsed: 76, ms: 2840 },
    { level: 'LLM', name: '群組命名與說明',
      how: '每個群組跑一次生成，不是每封信',
      cost: '高，但只跑 14 次', collapsed: 0, ms: 9600 }
  ],

  /* 收斂後的 campaign —— 一個 campaign 一張卡片 */
  campaigns: [
    { id: 'C03', name: '冒充財務主管要求變更匯款帳戶', verdict: 'phishing',
      tactics: ['T5', 'T2'], reports: 3, confidence: 0.94, level: 'L3',
      first: '09-09 09:14', last: '09-09 11:02', status: 'open', priority: 1,
      from: 'cfo-lin@company-tw<span>.</span>net', fromReal: 'company-tw.net',
      spoof: '顯示名稱寫「林財務長」，實際網域與公司網域差一個字',
      subject: '【急】本月供應商匯款帳戶變更',
      snippet: '因原帳戶審計凍結，本月款項請改匯下列新帳戶，請於今日下班前完成並回覆確認。',
      why: '寄件網域 company-tw.net 與公司網域 companytw.com.tw 僅差一個連字號，' +
           '網域註冊僅 6 天。內容要求變更既有匯款流程且施加時間壓力，符合 BEC 特徵。',
      indicators: { spf: 'fail', dkim: 'none', dmarc: 'fail', domainAge: 6, urls: 0, mismatch: false },
      action: '立即通知財務部門暫停匯款，封鎖寄件網域' },

    { id: 'C01', name: '假冒銀行 OTP 驗證頁面', verdict: 'phishing',
      tactics: ['T1', 'T2'], reports: 31, confidence: 0.97, level: 'L2',
      first: '09-09 08:22', last: '09-09 14:51', status: 'open', priority: 2,
      from: 'service@bank-secure-tw<span>.</span>com', fromReal: 'bank-secure-tw.com',
      spoof: '冒用銀行標誌與版型，連結文字寫官網網址但實際指向其他網域',
      subject: '您的網路銀行帳號將於今日停用',
      snippet: '偵測到異常登入，請於 24 小時內完成身分驗證，逾期將暫停所有交易功能。',
      why: '連結顯示文字為銀行官網，實際指向 bank-secure-tw.com，網域註冊 11 天。' +
           '內容同時具備時間壓力與權威冒充。31 封信主旨模板相同僅收件人不同。',
      indicators: { spf: 'fail', dkim: 'fail', dmarc: 'fail', domainAge: 11, urls: 2, mismatch: true },
      action: '封鎖網域，發送全員提醒，比對是否有人已點擊' },

    { id: 'C04', name: '假冒資訊部門通知密碼到期', verdict: 'phishing',
      tactics: ['T2', 'T1'], reports: 8, confidence: 0.91, level: 'L2',
      first: '09-09 10:03', last: '09-09 13:20', status: 'open', priority: 3,
      from: 'it-helpdesk@mail-service<span>.</span>info', fromReal: 'mail-service.info',
      spoof: '冒充內部 IT 服務台，登入頁面仿造公司單一登入畫面',
      subject: '[IT 通知] 您的密碼將於 48 小時後到期',
      snippet: '請點擊下方連結完成密碼更新，未更新者將無法存取公司系統。',
      why: '冒充內部單位但寄件網域為外部 .info。連結指向仿造的登入頁面。',
      indicators: { spf: 'fail', dkim: 'none', dmarc: 'none', domainAge: 23, urls: 1, mismatch: true },
      action: '封鎖網域，提醒同仁 IT 不會以郵件要求輸入密碼' },

    { id: 'C05', name: '恐嚇信：宣稱掌握瀏覽紀錄', verdict: 'phishing',
      tactics: ['T4'], reports: 2, confidence: 0.88, level: 'L1',
      first: '09-09 11:47', last: '09-09 12:05', status: 'open', priority: 4,
      from: 'noreply@tempmail-x<span>.</span>xyz', fromReal: 'tempmail-x.xyz',
      spoof: '偽造成受害者自己的信箱寄出（From 偽造）',
      subject: '我已經取得您的裝置存取權',
      snippet: '我已錄下您的畫面與攝影機影像，請於 48 小時內以加密貨幣支付，否則將公開。',
      why: 'From 偽造為收件人本人信箱，但 SPF 檢查失敗。內容為典型勒索話術，' +
           '無實際攻擊證據，屬大量群發型恐嚇。',
      indicators: { spf: 'fail', dkim: 'none', dmarc: 'fail', domainAge: 3, urls: 0, mismatch: false },
      action: '告知同仁不必理會、不要付款，封鎖寄件網域' },

    { id: 'C02', name: '假冒人資年度調薪通知', verdict: 'phishing',
      tactics: ['T2', 'T3'], reports: 14, confidence: 0.93, level: 'L1',
      first: '09-09 08:55', last: '09-09 10:31', status: 'open', priority: 5,
      from: 'hr-notice@companytw-hr<span>.</span>com', fromReal: 'companytw-hr.com',
      spoof: '冒充人資部門，附件為含巨集的試算表',
      subject: '2026 年度調薪作業通知（請查收附件）',
      snippet: '請下載附件確認個人調薪幅度，並於 9/12 前回覆確認。',
      why: '附件為 .xlsm 含巨集。寄件網域非公司網域，註冊 18 天。' +
           '以調薪為誘餌提高開啟意願。',
      indicators: { spf: 'fail', dkim: 'fail', dmarc: 'fail', domainAge: 18, urls: 0, mismatch: false, attach: '.xlsm（含巨集）' },
      action: '封鎖網域與附件雜湊，檢查是否有人已開啟附件' },

    { id: 'C06', name: '電商促銷群發廣告', verdict: 'spam',
      tactics: ['T3'], reports: 47, confidence: 0.96, level: 'L1',
      first: '09-09 08:01', last: '09-09 15:12', status: 'closed', priority: 6,
      from: 'promo@shop-newsletter<span>.</span>com', fromReal: 'shop-newsletter.com',
      spoof: '', subject: '限時 5 折｜今日最後一天',
      snippet: '全館服飾五折起，輸入折扣碼再折 100 元。',
      why: 'SPF/DKIM 通過，為合法商業電子郵件。含正常退訂連結。非威脅，' +
           '但同仁誤以為是釣魚而大量回報。',
      indicators: { spf: 'pass', dkim: 'pass', dmarc: 'pass', domainAge: 1420, urls: 6, mismatch: false },
      action: '加入廣告白名單，不需處置' },

    { id: 'C07', name: '保險業務開發信', verdict: 'spam',
      tactics: [], reports: 38, confidence: 0.94, level: 'L2',
      first: '09-09 09:30', last: '09-09 14:02', status: 'closed', priority: 7,
      from: 'agent@insurance-plan<span>.</span>tw', fromReal: 'insurance-plan.tw',
      spoof: '', subject: '為您規劃退休保障方案',
      snippet: '想與您約時間說明適合的保障規劃，方便的話請回覆。',
      why: 'SPF 通過，網域註冊 3 年以上，內容無惡意連結或附件。屬未經同意的行銷信。',
      indicators: { spf: 'pass', dkim: 'pass', dmarc: 'none', domainAge: 1180, urls: 1, mismatch: false },
      action: '加入垃圾規則，不需人工處理' },

    { id: 'C08', name: '海外代購廣告', verdict: 'spam',
      tactics: ['T3'], reports: 21, confidence: 0.92, level: 'L1',
      first: '09-09 10:15', last: '09-09 13:44', status: 'closed', priority: 8,
      from: 'buy@daigou-shop<span>.</span>net', fromReal: 'daigou-shop.net',
      spoof: '', subject: '日本藥妝代購 現貨供應',
      snippet: '本週開團，滿三千免運。',
      why: '無惡意指標，屬一般垃圾廣告。',
      indicators: { spf: 'pass', dkim: 'none', dmarc: 'none', domainAge: 640, urls: 3, mismatch: false },
      action: '加入垃圾規則' },

    { id: 'C09', name: '研討會邀請（多人轉寄）', verdict: 'spam',
      tactics: [], reports: 15, confidence: 0.89, level: 'L2',
      first: '09-09 09:05', last: '09-09 11:38', status: 'closed', priority: 9,
      from: 'event@conf-invite<span>.</span>org', fromReal: 'conf-invite.org',
      spoof: '', subject: '誠摯邀請您參加 2026 數位轉型論壇',
      snippet: '本論壇免費參加，名額有限，敬請把握。',
      why: '合法主辦單位發出的邀請信，被多位同仁轉寄回報。非威脅。',
      indicators: { spf: 'pass', dkim: 'pass', dmarc: 'pass', domainAge: 2100, urls: 2, mismatch: false },
      action: '不需處置' },

    { id: 'C10', name: '內部公告被大量轉寄回報', verdict: 'benign',
      tactics: [], reports: 52, confidence: 0.99, level: 'L1',
      first: '09-09 08:10', last: '09-09 09:02', status: 'closed', priority: 10,
      from: 'announce@companytw.com<span>.</span>tw', fromReal: 'companytw.com.tw',
      spoof: '', subject: '【全體同仁】颱風假出勤規定說明',
      snippet: '依人事行政總處公告，本週五停止上班上課。',
      why: '**公司自己發的內部公告**，寄件網域為公司網域且 SPF/DKIM/DMARC 全數通過。' +
           '因主旨含「【全體同仁】」被誤認為釣魚。',
      indicators: { spf: 'pass', dkim: 'pass', dmarc: 'pass', domainAge: 4200, urls: 1, mismatch: false },
      action: '不需處置。建議加強同仁對內部公告格式的認識' },

    { id: 'C11', name: '客戶正常詢價信', verdict: 'benign',
      tactics: [], reports: 31, confidence: 0.95, level: 'L3',
      first: '09-09 08:44', last: '09-09 15:20', status: 'closed', priority: 11,
      from: '多個客戶網域', fromReal: '多來源',
      spoof: '', subject: '（各式詢價主旨）',
      snippet: '想詢問貴公司產品報價與交期。',
      why: '31 封來自不同客戶的正常詢價信，因含附件與外部連結被回報。' +
           '語意分群後歸為同一類，全部為正常商務往來。',
      indicators: { spf: 'pass', dkim: 'pass', dmarc: 'pass', domainAge: null, urls: 1, mismatch: false },
      action: '不需處置' },

    { id: 'C12', name: '系統自動通知（備份完成）', verdict: 'benign',
      tactics: [], reports: 24, confidence: 0.99, level: 'L1',
      first: '09-09 08:00', last: '09-09 08:00', status: 'closed', priority: 12,
      from: 'backup@companytw.com<span>.</span>tw', fromReal: 'companytw.com.tw',
      spoof: '', subject: '[AUTO] Nightly backup completed',
      snippet: 'Backup job finished successfully. 0 errors.',
      why: '內部系統自動信，英文主旨被誤認為國外釣魚。',
      indicators: { spf: 'pass', dkim: 'pass', dmarc: 'pass', domainAge: 4200, urls: 0, mismatch: false },
      action: '不需處置。建議把自動信加入回報白名單' },

    { id: 'C13', name: '供應商發票（正常）', verdict: 'benign',
      tactics: [], reports: 15, confidence: 0.9, level: 'L2',
      first: '09-09 09:22', last: '09-09 14:35', status: 'closed', priority: 13,
      from: 'billing@supplier-co<span>.</span>tw', fromReal: 'supplier-co.tw',
      spoof: '', subject: '9 月份請款單',
      snippet: '附件為本月請款明細，如有問題請聯繫。',
      why: '長期往來供應商，網域與過往一致，附件為 PDF 無巨集。' +
           '**注意：這類信與 BEC（C03）外觀相近，是最需要謹慎判斷的一類。**',
      indicators: { spf: 'pass', dkim: 'pass', dmarc: 'pass', domainAge: 2900, urls: 0, mismatch: false, attach: '.pdf' },
      action: '不需處置，但保留紀錄供 BEC 比對' },

    { id: 'C14', name: '求職應徵信', verdict: 'benign',
      tactics: [], reports: 11, confidence: 0.93, level: 'L2',
      first: '09-09 10:40', last: '09-09 15:05', status: 'closed', priority: 14,
      from: '多個個人信箱', fromReal: '多來源',
      spoof: '', subject: '應徵貴公司職缺',
      snippet: '附上履歷，期待有機會面談。',
      why: '正常求職信，因含附件被回報。',
      indicators: { spf: 'pass', dkim: 'none', dmarc: 'none', domainAge: null, urls: 0, mismatch: false, attach: '.pdf' },
      action: '轉交人資，不需資安處置' }
  ],

  /* 本班次統計 */
  shift: {
    reports: 312,
    cards: 14,
    ratio: 22.3,
    phishing: 58,
    spam: 121,
    benign: 133,
    reporters: 87,
    llmCalls: 14,
    llmCallsIfNoDedup: 312,
    analystMinutesBefore: 260,
    analystMinutesAfter: 35
  },

  /* 近 8 個班次的回報量與收斂後卡片數 */
  trend: [
    { d: '09-02', reports: 188, cards: 11 },
    { d: '09-03', reports: 143, cards: 9 },
    { d: '09-04', reports: 291, cards: 13 },
    { d: '09-05', reports: 96, cards: 7 },
    { d: '09-06', reports: 41, cards: 4 },
    { d: '09-07', reports: 38, cards: 4 },
    { d: '09-08', reports: 167, cards: 10 },
    { d: '09-09', reports: 312, cards: 14 }
  ],

  /* 標註進度（囷洧的工作） */
  annotation: {
    target: 1000, done: 340,
    agreement: 0.87, agreementTarget: 0.85,
    byTactic: [
      { id: 'T1', n: 96 }, { id: 'T2', n: 88 }, { id: 'T3', n: 54 },
      { id: 'T4', n: 31 }, { id: 'T5', n: 12 }, { id: 'T6', n: 27 }
    ]
  },

  /* 模型評測（明樺的工作）—— base 對照 fine-tuned */
  eval: [
    { task: '釣魚二分類', metric: 'F1', base: 0.76, ft: 0.93, target: 0.92 },
    { task: '釣魚二分類', metric: 'Recall', base: 0.71, ft: 0.96, target: 0.95 },
    { task: '話術多標籤', metric: 'Macro-F1', base: 0.52, ft: 0.79, target: 0.78 },
    { task: 'Campaign 聚類', metric: 'Purity', base: null, ft: 0.92, target: 0.90 },
    { task: '收斂率', metric: '倍', base: 1.0, ft: 22.3, target: 8.0 },
    { task: '理由品質', metric: '人工評分', base: null, ft: 4.2, target: 4.0 }
  ],

  /* 資料庫架構（同時給 ER 圖與後端建表用） */
  schema: [
    { t: 'reports', label: '回報', note: '誰在什麼時候回報了哪封信',
      cols: [['id', 'BIGSERIAL', 'PK'], ['message_id', 'BIGINT', 'FK → messages'],
             ['reporter_hash', 'TEXT', '回報者（去識別化）'], ['reported_at', 'TIMESTAMPTZ', ''],
             ['source', 'TEXT', "'button' / 'forward' / 'upload'"]] },

    { t: 'messages', label: '郵件本體', note: '去識別化後的郵件，一封一列',
      cols: [['id', 'BIGSERIAL', 'PK'], ['message_id_hdr', 'TEXT', 'UNIQUE，L1 精確比對用'],
             ['subject', 'TEXT', ''], ['subject_hash', 'TEXT', 'L1 比對用'],
             ['from_display', 'TEXT', '顯示名稱'], ['from_addr', 'TEXT', ''],
             ['from_domain', 'TEXT', 'INDEX，L2 特徵比對用'],
             ['reply_to', 'TEXT', ''], ['received_at', 'TIMESTAMPTZ', ''],
             ['body_redacted', 'TEXT', '已去識別化的內文'],
             ['attach_hash', 'TEXT', 'L1 比對用'], ['raw_hash', 'TEXT', '']] },

    { t: 'indicators', label: '技術指標', note: '程式判斷的部分，一封信一列',
      cols: [['message_id', 'BIGINT', 'PK, FK → messages'],
             ['spf', 'TEXT', "'pass' / 'fail' / 'none'"], ['dkim', 'TEXT', ''],
             ['dmarc', 'TEXT', ''], ['domain_age_days', 'INT', '網域註冊天數'],
             ['url_count', 'INT', ''], ['url_mismatch', 'BOOLEAN', '顯示文字與實際網址不符'],
             ['punycode', 'BOOLEAN', ''], ['attach_type', 'TEXT', '']] },

    { t: 'urls', label: '信中連結', note: '一封信可能多個連結',
      cols: [['id', 'BIGSERIAL', 'PK'], ['message_id', 'BIGINT', 'FK → messages'],
             ['url_redacted', 'TEXT', ''], ['display_text', 'TEXT', ''],
             ['real_domain', 'TEXT', ''], ['is_mismatch', 'BOOLEAN', '']] },

    { t: 'campaigns', label: '收斂後群組', note: '一個 campaign 一張卡片，這是系統的產出',
      cols: [['id', 'BIGSERIAL', 'PK'], ['name', 'TEXT', 'LLM 生成的群組名稱'],
             ['verdict', 'TEXT', "'phishing' / 'spam' / 'benign' / 'unknown'"],
             ['confidence', 'NUMERIC', ''], ['dedup_level', 'TEXT', "'L1' / 'L2' / 'L3'"],
             ['summary', 'TEXT', 'LLM 生成的判定理由'],
             ['first_seen', 'TIMESTAMPTZ', ''], ['last_seen', 'TIMESTAMPTZ', ''],
             ['status', 'TEXT', "'open' / 'closed'"]] },

    { t: 'campaign_members', label: '群組成員', note: '哪些信屬於哪個群組，多對多',
      cols: [['campaign_id', 'BIGINT', 'PK, FK → campaigns'],
             ['message_id', 'BIGINT', 'PK, FK → messages'],
             ['similarity', 'NUMERIC', ''], ['joined_by', 'TEXT', "'L1' / 'L2' / 'L3'"]] },

    { t: 'tactics', label: '話術體系', note: '囷洧定義的六類，固定資料表',
      cols: [['id', 'TEXT', 'PK，例如 T5'], ['code', 'TEXT', ''],
             ['name_zh', 'TEXT', ''], ['description', 'TEXT', ''],
             ['example', 'TEXT', ''], ['tech_detectable', 'TEXT', "'yes'/'partial'/'no'"]] },

    { t: 'message_tactics', label: '話術標籤', note: '多標籤：一封信可能同時有多種話術',
      cols: [['message_id', 'BIGINT', 'PK, FK → messages'],
             ['tactic_id', 'TEXT', 'PK, FK → tactics'],
             ['score', 'NUMERIC', '模型信心'],
             ['source', 'TEXT', "'model' / 'human'"]] },

    { t: 'embeddings', label: '語意向量', note: 'L3 分群用，需 pgvector 擴充',
      cols: [['message_id', 'BIGINT', 'PK, FK → messages'],
             ['vector', 'VECTOR(768)', 'pgvector'],
             ['model_ver', 'TEXT', '換模型要重算，所以記版本']] },

    { t: 'annotations', label: '人工標註', note: '囷洧的產出，訓練資料來源',
      cols: [['id', 'BIGSERIAL', 'PK'], ['message_id', 'BIGINT', 'FK → messages'],
             ['annotator', 'TEXT', ''], ['is_phishing', 'BOOLEAN', ''],
             ['tactic_ids', 'TEXT[]', ''], ['note', 'TEXT', ''],
             ['annotated_at', 'TIMESTAMPTZ', '']] },

    { t: 'actions', label: '處置紀錄', note: '分析師做了什麼，稽核用',
      cols: [['id', 'BIGSERIAL', 'PK'], ['campaign_id', 'BIGINT', 'FK → campaigns'],
             ['analyst', 'TEXT', ''],
             ['action', 'TEXT', "'block' / 'ignore' / 'escalate' / 'notify'"],
             ['note', 'TEXT', ''], ['acted_at', 'TIMESTAMPTZ', '']] }
  ],

  /* ER 圖的關聯線 */
  relations: [
    ['reports', 'messages', 'N:1', '一封信可能被多人回報'],
    ['indicators', 'messages', '1:1', '技術指標'],
    ['urls', 'messages', 'N:1', '信中連結'],
    ['embeddings', 'messages', '1:1', '語意向量'],
    ['annotations', 'messages', 'N:1', '人工標註'],
    ['campaign_members', 'messages', 'N:1', ''],
    ['campaign_members', 'campaigns', 'N:1', '收斂結果'],
    ['message_tactics', 'messages', 'N:1', ''],
    ['message_tactics', 'tactics', 'N:1', '多標籤'],
    ['actions', 'campaigns', 'N:1', '處置紀錄']
  ]
};
