"""
工具箱。第三方套件的包裝，**完整可用，不是骨架**。

===========================================================================
這個資料夾跟其他資料夾的差別
===========================================================================
    toolkit/    已經寫好了。你 import 來用，不用改也不用讀懂內部
    其他        你們自己寫

工具箱的存在意義是：**讓你不用去讀 PyJWT、passlib、httpx 的文件**。
你只要知道「呼叫這個函式會得到什麼」就好，那些寫在每支函式的說明裡。

===========================================================================
有哪些工具
===========================================================================
    config      設定（環境變數）        settings.database_url
    db          資料庫                  Base / get_db / engine
    passwords   密碼雜湊                hash_password / verify_password
    tokens      JWT                     make_access_token / read_access_token
    deps        FastAPI 依賴            current_user_id / paging
    errors      統一的錯誤回應          not_found / forbidden / unauthorized
    period      期間與日期              month_range / recent_months
    money       金額（Decimal）         to_decimal / ratio / quantize
    images      大頭貼驗證              validate_avatar / to_data_uri
    alerts      階段性提醒的門檻計算    usage_percent / crossed / should_fire
    scope       可見範圍的兩道篩選      visible_users / visible_groups

===========================================================================
怎麼查一個工具怎麼用
===========================================================================
每支函式的說明裡都寫了**參數、回傳、丟出什麼例外、範例**。
在編輯器裡把游標移到函式上就看得到，或是：

    python -c "from app.toolkit import period; help(period.month_range)"

===========================================================================
⚠️ 三個約定
===========================================================================
1. **不要改 toolkit/ 裡的東西。** 有問題在群組講，改了別人會踩到。
2. **不要在 toolkit/ 裡寫跟「記帳」有關的邏輯。** 這裡的東西
   換一個題目也要能用。記帳的規則寫在你們自己的 services/。
3. **金額一律走 money 模組，不要用 float。** 這不是風格建議，
   浮點數累加會產生 12345.670000000002 這種結果。
"""
