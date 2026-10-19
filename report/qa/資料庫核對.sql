-- 家庭記帳：線上資料庫核對（2026-10-19 測試輪）
-- HeidiSQL 連上 fambudget-db-tdvg 後，整份貼進查詢視窗，按 F9（全部執行）。
-- 會出現 6 個結果分頁，每一頁截一張圖貼回對話就好。

-- ① 各表筆數
SELECT '系統分類（應 12）' AS 項目, COUNT(*) AS 筆數 FROM categories WHERE family_id IS NULL
UNION ALL SELECT '帳本（每個帳號至少 1）', COUNT(*) FROM groups
UNION ALL SELECT '明細（應 13：家長 9、子女 4）', COUNT(*) FROM transactions
UNION ALL SELECT '模型解析紀錄（應 11）', COUNT(*) FROM nlp_parses
UNION ALL SELECT '家庭（應 1）', COUNT(*) FROM families
UNION ALL SELECT '家庭成員（應 2）', COUNT(*) FROM family_members
UNION ALL SELECT '照看關係（應 1）', COUNT(*) FROM guardianships
UNION ALL SELECT '零用金設定（應 1）', COUNT(*) FROM allowances
UNION ALL SELECT '邀請碼（應 2）', COUNT(*) FROM family_invites
UNION ALL SELECT '財務建議', COUNT(*) FROM advices
UNION ALL SELECT '通知（應 5：子女記帳 4、預算提醒 1）', COUNT(*) FROM notifications
UNION ALL SELECT '預算（應 1）', COUNT(*) FROM budgets
UNION ALL SELECT '存款目標（應 1）', COUNT(*) FROM savings_goals;

-- ② 帳號與 email 驗證（邱冠文的 email_verified_at 要有時間；冠文_user 是空的）
SELECT id, email, display_name, email_verified_at, email_verify_sent_at, created_at
FROM users ORDER BY id;

-- ③ 明細（source 是 nlp 的是 AI 解析後確認寫入的）
SELECT t.id, u.display_name, g.name AS 帳本, t.occurred_on, t.kind, t.amount, c.name AS 分類, t.source, t.merchant, t.note
FROM transactions t
JOIN users u ON u.id = t.user_id
JOIN groups g ON g.id = t.group_id
JOIN categories c ON c.id = t.category_id
ORDER BY t.id;

-- ④ 邀請碼（第一個應該 status 沒變成 accepted、到期時間約建立後 2 分 53 秒；第二個 accepted）
SELECT id, role, label, status, created_at, expires_at, expires_at - created_at AS 有效期, responded_at
FROM family_invites ORDER BY id;

-- ⑤ 重設密碼連結（最新一筆：有效期 3 分鐘、used_at 是空的＝過期後沒被用掉）
SELECT id, user_id, created_at, expires_at, expires_at - created_at AS 有效期, used_at
FROM password_resets ORDER BY id DESC LIMIT 3;

-- ⑥ 模型解析紀錄：每一筆 AI 寫入的明細都有一列，model_ver 是線上用的模型
SELECT model_ver, COUNT(*) AS 筆數, MIN(created_at) AS 最早, MAX(created_at) AS 最晚,
       SUM(CASE WHEN user_corrected IS NOT NULL THEN 1 ELSE 0 END) AS 使用者改過
FROM nlp_parses GROUP BY model_ver;
