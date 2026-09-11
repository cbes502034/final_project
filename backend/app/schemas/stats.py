"""
統計與預算的請求與回應模型。 ✦ 負責人：成員3（數字與建議）　✦ 分支：m3-analytics

===========================================================================
這個檔案要定義哪些模型
===========================================================================
    SavingsStatus            goal、allowance、used、left、ratio、level、shortfall、actual
    SummaryResponse          income、expense、net、rate、count、savings、members
    StatsResponse            by_cat、trend、incomplete
    BudgetItem               category_id、limit、used、ratio
    SavingsGoalUpdate        user_id、goal、period

===========================================================================
models/ 和 schemas/ 的差別
===========================================================================
    models/    資料庫裡存什麼    User 有 password_hash
    schemas/   API 收送什麼      UserResponse **沒有** password_hash

分開的好處立刻看得到：你**不可能「不小心」把密碼雜湊回傳給前端**，
因為 response model 裡根本沒有那一欄。

===========================================================================
回應形狀要跟前端對得上
===========================================================================
`frontend/js/api.js` 裡有完整的路由契約，而且 mock 模式已經用假資料
把所有畫面跑起來了。**不確定要回什麼形狀時，去看 api.js，那是唯一的真相來源。**

⚠️ `level` 和 `ratio` 都要**後端算好再回傳**，不要讓前端自己判斷門檻。
否則哪天門檻從 80% 改成 75%，前端後端都要改，一定會有人漏掉。

⚠️ `StatsResponse.incomplete`：當年度的年統計一定要標示未完整。
2026 才過 9 個月，總支出當然比 2025 整年少，
使用者會誤以為自己變節省了。**這種誤導比沒有這個功能更糟。**
"""

# TODO(成員3): 定義上面列的 Pydantic 模型
