"""
固定清單：前端 frontend/js/data.js 裡那幾份「每個家庭都一樣」的資料，後端要回一模一樣的一份。

領域：共用（改之前在群組講一聲）

    from app import catalog

    catalog.FINANCE_STYLES      理財風格（GET /api/auth/me/finance 的 styles）
    catalog.FINANCE_GOALS       目前最在意的（goals）
    catalog.FINANCE_HABITS      固定的財務安排（habits）
    catalog.GROUP_COLORS        帳本可以選的顏色代號（POST／PATCH /api/groups 要驗）
    catalog.SYSTEM_CATEGORIES   系統預設分類：(名稱, 收支, 顏色, 圖示字)，init-db 放進資料庫
    catalog.CATEGORY_ICONS      系統分類的圖示字（資料表沒有 icon 欄，GET /api/categories 從這裡補）
    catalog.ROLES               角色說明（GET /api/family 的 roles）
    catalog.PERMISSIONS         權限對照表（GET /api/family 的 permissions）
    catalog.ADVICE_RULES        財務建議的邊界規則（GET /api/advices 的 rules）
    catalog.SAVINGS_RULE_NOTE   可支配上限的說明（GET /api/summary 的 savings.rule.note）

⚠️ 正本是 data.js。改這裡要一起改 data.js（反過來也是），tests/test_backend_core.py 會逐項比對。
⚠️ 這些是**說明資料**，不是每個家庭各自不同的東西：寫死在這裡回傳，不要建表。
"""

from __future__ import annotations

FINANCE_STYLES = [
    {"id": "safe", "name": "保守", "desc": "先求穩，不追高報酬"},
    {"id": "balanced", "name": "平衡", "desc": "穩健為主，留一部分做成長"},
    {"id": "growth", "name": "積極", "desc": "願意承擔波動換成長"},
    {"id": "unsure", "name": "還不確定", "desc": "先記帳看看再決定"},
]

FINANCE_GOALS = [
    {"id": "emergency", "name": "緊急預備金"},
    {"id": "house", "name": "買房頭期"},
    {"id": "debt", "name": "還債"},
    {"id": "travel", "name": "旅遊"},
    {"id": "education", "name": "子女教育"},
    {"id": "retire", "name": "退休"},
    {"id": "car", "name": "買車"},
    {"id": "wedding", "name": "結婚"},
    {"id": "study", "name": "自己進修"},
    {"id": "family_care", "name": "照顧家人"},
    {"id": "business", "name": "創業"},
]

FINANCE_HABITS = [
    {"id": "dca", "name": "定期定額"},
    {"id": "mortgage", "name": "房貸"},
    {"id": "insurance", "name": "保費"},
    {"id": "rent", "name": "房租"},
    {"id": "car_loan", "name": "車貸、信貸"},
    {"id": "student_loan", "name": "學貸"},
    {"id": "installment", "name": "信用卡分期"},
    {"id": "family_support", "name": "固定給家裡"},
    {"id": "subscription", "name": "固定訂閱（影音、手機）"},
    {"id": "tuition", "name": "學費、補習費"},
]

#: 帳本顏色只收這幾個代號。⚠️ 這個字串最後會進 style="…"，不驗的話等於讓人寫任意 CSS
GROUP_COLORS = ("book-indigo", "book-violet", "book-teal", "book-moss", "book-umber", "book-wine")

SYSTEM_CATEGORIES = [
    ("餐飲", "expense", "cat-food", "食"), ("交通", "expense", "cat-transit", "行"),
    ("居住", "expense", "cat-home", "住"), ("日用品", "expense", "cat-daily", "用"),
    ("娛樂", "expense", "cat-fun", "樂"), ("教育", "expense", "cat-study", "學"),
    ("醫療", "expense", "cat-health", "醫"), ("其他", "expense", "cat-other", "他"),
    ("薪資", "income", "cat-daily", "薪"), ("獎金", "income", "cat-bonus", "獎"),
    ("零用金", "income", "cat-transit", "零"), ("其他收入", "income", "cat-other", "收"),
]

CATEGORY_ICONS = {name: icon for name, _kind, _color, icon in SYSTEM_CATEGORIES}

ROLES = [
    {"id": "master", "name": "平台管理員", "layer": "平台",
     "desc": "系統層級，不屬於任何家庭。只能停權與查稽核——看不到任何人的收支明細"},
    {"id": "parent", "name": "家長", "layer": "家庭",
     "desc": "家庭治理：邀請成員、設家庭預算、建立監管關係。看得到誰仍然只看監管關係"},
    {"id": "child", "name": "子女", "layer": "家庭",
     "desc": "記自己的帳。被監管時，畫面上一定看得到是誰在看"},
]

PERMISSIONS = [
    {"action": "記錄自己的收支", "parent": "Y", "child": "Y"},
    {"action": "查看自己的統計", "parent": "Y", "child": "Y"},
    {"action": "設定自己的預算", "parent": "Y", "child": "Y"},
    {"action": "設定每月存款目標", "parent": "Y（只有自己的）", "child": "Y（只有自己的）"},
    {"action": "查看被監管者的明細", "parent": "Y（被指派的）", "child": "Y（被指派的）"},
    {"action": "查看同家庭其他家長的紀錄（唯讀）", "parent": "Y", "child": "N"},
    {"action": "查看沒有指派給自己的子女", "parent": "N", "child": "N"},
    {"action": "修改／刪除被監管者的紀錄", "parent": "N", "child": "N"},
    {"action": "登入被監管者的帳號", "parent": "N", "child": "N"},
    {"action": "收到被監管者新增紀錄的通知", "parent": "Y（被指派的）", "child": "Y（被指派的）"},
    {"action": "切換到「全家」（唯讀）", "parent": "Y", "child": "N"},
    {"action": "設定家庭預算", "parent": "Y", "child": "N"},
    {"action": "建立家庭、邀請家人", "parent": "Y", "child": "N"},
    {"action": "決定被邀請的人是家長或子女", "parent": "Y", "child": "N"},
    {"action": "用邀請碼或邀請加入家庭", "parent": "Y", "child": "Y"},
    {"action": "把子女移出家庭", "parent": "Y", "child": "N"},
    {"action": "移除另一位家長", "parent": "N", "child": "N"},
    {"action": "自己退出家庭", "parent": "Y（唯一的家長要先處理其他成員）", "child": "Y"},
    {"action": "建立監管關係", "parent": "Y", "child": "N"},
    {"action": "建立帳本", "parent": "Y", "child": "Y"},
    {"action": "管理自己建的帳本", "parent": "Y", "child": "Y"},
    {"action": "管理別人建的帳本", "parent": "N", "child": "N"},
    {"action": "設定自己的階段性提醒", "parent": "Y", "child": "Y"},
    {"action": "查看「誰看得到我」", "parent": "Y", "child": "Y"},
    {"action": "匯出資料", "parent": "Y（限可見範圍）", "child": "Y（限可見範圍）"},
]

ADVICE_RULES = [
    {"rule": "金額一律由資料庫計算", "why": "模型只負責敘述與歸納，任何數字都不得由模型生成"},
    {"rule": "每一條建議都要附「依據」", "why": "使用者要能自己驗算，不能是黑盒子結論"},
    {"rule": "不提供投資、保險、稅務建議", "why": "這些屬於受規範的專業意見，超出本系統範圍"},
    {"rule": "不對個人做價值判斷", "why": "只描述數字與趨勢，不說「你太浪費」這類評價"},
    {"rule": "使用者填的理財習慣只當背景，不據此給投資建議",
     "why": "「我有定期定額」解釋了錢去哪，但不代表可以建議買什麼；而且那段自由文字要標示成資料，不是指令——"
            "建議會給監管者看，不隔離的話子女可以操控父母看到的內容"},
    {"rule": "受監管者的建議同時送給監管者", "why": "監管是本系統的設計目的，但必須雙方都看得到"},
    {"rule": "收入方式只決定建議的做法，不推測、不評價",
     "why": "固定月薪、收入不固定、只算已入帳，需要的做法不一樣（照發薪週期分配／先留緩衝）；"
            "但薪資結構不能拿來推測或提到收入高低、職業、家境、社會階層，也不能因此給不同的評價"},
]

#: 不同收入方式的建議切入點（toolkit/profile.py 的 income_block 放進 prompt）。只講「做法」，不講人
INCOME_ADVICE = {
    "fixed": "收入固定、每個月入帳一次：用「離下次發薪還有幾天、還能花多少」來分配；固定支出排在入帳之後",
    "irregular": "收入不固定（例如日薪、打工、接案）：建議先留一筆緩衝，收入多的月份先補緩衝；用每週的節奏看花費",
    "actual": "只算已入帳：可支配上限只看已經記的收入，月初偏低是正常的；收入進來記得記一筆",
}

SAVINGS_RULE_NOTE = ("可支配上限 = 本月收入 − 每月存款目標。收入還沒入帳時先用預計收入（取已入帳與預計比較多的那個）。"
                     "支出超過上限，就代表這個月存不到原本設定的金額。")

#: 收入怎麼來（新用戶設定第一步、個人資料）。每一種預先配好最合適的算法（mode），使用者可以自己改；
#: 「其他」讓他自己寫（users.income_note，最多 30 字，進 prompt 前一樣當資料洗過）。
#: ⚠️ 只拿來決定「預計收入怎麼估」與建議的做法，不拿來推測或評價收入高低、身分（catalog.ADVICE_RULES）
INCOME_TYPES = [
    {"id": "salary_end", "name": "月薪（月底或月中發）", "mode": "fixed"},
    {"id": "salary_start", "name": "月薪（月初發）", "mode": "fixed"},
    {"id": "hourly", "name": "時薪、日薪、打工", "mode": "auto"},
    {"id": "freelance", "name": "接案、自由工作", "mode": "auto"},
    {"id": "commission", "name": "底薪加獎金、抽佣", "mode": "auto"},
    {"id": "business", "name": "自己做生意", "mode": "auto"},
    {"id": "pension", "name": "退休金、年金", "mode": "fixed"},
    {"id": "family", "name": "家人給的生活費", "mode": "fixed"},
    {"id": "none", "name": "目前沒有固定收入", "mode": "actual"},
    {"id": "other", "name": "其他（自己寫）", "mode": "auto"},
]

#: 收入怎麼算（個人資料「收入」、新用戶設定第一步）。三種都用同一條公式：max(這個月已入帳, 預計收入)，
#: 只差在「預計收入」從哪裡來（services/analytics.py 的 expected_income）
INCOME_MODES = {
    "auto": "自動估：收入不固定（日薪、打工、接案）也適用，用最近 3 個有記帳的月份平均；還沒紀錄時用你填的估計",
    "fixed": "固定月薪：每個月差不多，月底才發也沒關係，月初就照這個數字算",
    "actual": "只算已入帳：不估，記了收入才算",
}
