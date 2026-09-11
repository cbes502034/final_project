"""
家庭與權限的請求與回應模型。 ✦ 負責人：成員4（家庭與權限）　✦ 分支：m4-access

===========================================================================
這個檔案要定義哪些模型
===========================================================================
    FamilyResponse           family、members 陣列
    MemberOut                id、display_name、role、status
    InviteResponse           code、expires_at
    JoinRequest              code
    RoleUpdate               role
    GuardianshipCreate       guardian_id、ward_id
    GuardianshipList         guarding 陣列、guarded_by 陣列

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

⚠️ `GuardianshipList` 要回**兩個**清單：我監管誰、誰監管我。
第二個是給被監管者自己看的，前端會顯示在他的總覽頁上。
"""

# TODO(成員4): 定義上面列的 Pydantic 模型
