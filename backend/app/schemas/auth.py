"""
身分認證的請求與回應模型。 ✦ 負責人：成員1（身分認證）　✦ 分支：m1-auth

===========================================================================
這個檔案要定義哪些模型
===========================================================================
    RegisterRequest          email、password、display_name、birth_year、savings_goal
    LoginRequest             email、password
    TokenPair                access_token、refresh_token、expires_in、user
    UserResponse             id、display_name、role。**不可以有 password_hash**
    MeResponse               user、family、role、guarded_by

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
"""

# TODO(成員1): 定義上面列的 Pydantic 模型
