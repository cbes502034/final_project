"""
身分認證。 ✦ 負責人：成員1（帳號與權限）

===========================================================================
這個檔案負責哪些路由
===========================================================================
掛載前綴是 /api/auth（在 main.py 設定），所以下面寫 "/login" 實際就是 /api/auth/login。

    編號  方法    路徑            權限    用途
    ----------------------------------------------------------------
     1    POST   /register       公開    註冊，同時建立每月存款目標
     2    POST   /login          公開    登入，回傳 access + refresh token
     3    POST   /refresh        公開    用 refresh token 換新的 access token
     4    POST   /logout         登入    撤銷目前這台裝置的 refresh token
     5    POST   /logout-all     登入    撤銷所有裝置
     6    GET    /me             登入    我是誰、我的角色、誰在監管我
     7    PATCH  /password       登入    改密碼，同時讓其他裝置失效
     8    GET    /sessions       登入    列出有效的登入裝置

===========================================================================
這個檔案是「標準範例」，其他 router 都照這個格式寫
===========================================================================
一支路由長這樣：

    @router.post("/login", response_model=TokenPair, summary="登入")
    def login(payload: LoginRequest, db: Session = Depends(get_db)):
        \"\"\"中文說明，會直接顯示在 /docs 上\"\"\"
        ...

四個部分各自的作用：

**@router.post("/login")**
    裝飾器。告訴 FastAPI「有人用 POST 打 /login 時，執行下面這個函式」。
    方法要選對：讀資料用 GET、新增用 POST、整個換掉用 PUT、
    改一部分用 PATCH、刪除用 DELETE。

**payload: LoginRequest**
    請求主體。FastAPI 看到型別是一個 Pydantic 模型，就會自動
    把前端送來的 JSON 轉成這個物件，**順便驗證格式**。
    email 格式不對、少了必填欄位，它會自己回 422 錯誤，
    你的函式根本不會被呼叫——你不用寫任何驗證程式碼。

**db: Session = Depends(get_db)**
    依賴注入。FastAPI 會先幫你準備好資料庫連線再呼叫你。
    看不懂的話回去讀 core/database.py 的說明。

**response_model=TokenPair**
    回傳格式。FastAPI 會照這個模型過濾你回傳的東西——
    **模型裡沒宣告的欄位會被自動拿掉**。
    這是一道安全網：就算你不小心回傳了整個 user 物件（含 password_hash），
    只要 response_model 裡沒有那一欄，它就不會流出去。

===========================================================================
怎麼開始動工
===========================================================================
1. 先把 schemas/auth.py 裡的 Pydantic 模型定義好（決定進出的資料長什麼樣）
2. 再把 models/user.py 的資料表定義好
3. 最後回來把下面每一支的 TODO 填掉
4. 邊寫邊開 http://localhost:8000/docs 直接試打，不需要寫前端也不需要 Postman
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user

# APIRouter 就像一個「子應用程式」，你在這裡定義路由，
# 再由 main.py 用 include_router 掛到主程式上。
# 這樣做的好處是每個人改自己的檔案，git 不會一直衝突。
router = APIRouter()


@router.post("/register", status_code=status.HTTP_201_CREATED, summary="註冊")
def register(db: Session = Depends(get_db)):
    """
    建立一個新帳號。

    這支路由要做四件事，順序不能亂：

    1. **檢查 email 有沒有被註冊過** —— 有的話回 409（衝突）
    2. **把密碼雜湊** —— 用 `hash_password()`，絕對不能存明碼
    3. **寫進 users 表**
    4. **順便建立 savings_goals 的第一筆** —— 註冊表單裡的「每月想存多少」
       要立刻存下來，因為總覽頁的超支警告要用它算

    回 201 而不是 200：201 的意思是「建立成功」，
    這是 HTTP 的慣例，讓前端一看狀態碼就知道發生了什麼事。

    ⚠️ 註冊成功後直接回傳 token 讓使用者登入狀態，
    不要讓他填完表單還要再登入一次——那是很差的體驗。

    TODO(成員1): 實作上面四步。需要先完成 schemas/auth.py 的 RegisterRequest
                 與 models/user.py 的 User、SavingsGoal
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員1 尚未實作")


@router.post("/login", summary="登入")
def login(db: Session = Depends(get_db)):
    """
    驗證帳號密碼，成功就發兩張 token。

    流程：

    1. 用 email 把使用者撈出來
    2. `verify_password(輸入的密碼, user.password_hash)`
    3. 通過 → 發 access token（30 分鐘）+ refresh token（14 天）
    4. **refresh token 的雜湊值**寫進 sessions 表（不是原文！）
    5. 更新 users.last_login_at

    ⚠️ **帳號不存在和密碼錯誤要回一樣的訊息**（「帳號或密碼不正確」）。
    如果分開講，攻擊者可以拿一堆 email 來試，
    從回應的差異整理出「哪些 email 有註冊」，這叫帳號列舉攻擊。

    TODO(成員1): 實作。密碼比對一定要用 verify_password()，不要用 ==
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員1 尚未實作")


@router.post("/refresh", summary="換新的 access token")
def refresh(db: Session = Depends(get_db)):
    """
    access token 過期時，用 refresh token 換一張新的。

    前端的流程是這樣：某支 API 回了 401 → 前端自動打這支 →
    拿到新的 access token → **把剛才失敗的那個請求重送一次**。
    整個過程使用者完全沒有感覺。

    這支一定要檢查三件事：

    1. token 的 `type` 是不是 `refresh`（不是 access）
    2. 它的雜湊值在 sessions 表裡找不找得到
    3. 那筆 session 的 `revoked_at` 是不是還是空的（沒被登出過）

    第 3 點是關鍵：**光驗 JWT 簽名不夠**。
    簽名有效只代表「這張是我們發的」，不代表「這張還能用」。
    使用者登出後那張 token 在過期前簽名仍然有效，
    所以一定要再查一次資料庫確認沒有被撤銷。

    TODO(成員1): 實作，三個檢查一個都不能少
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員1 尚未實作")


@router.post("/logout", summary="登出這台裝置")
def logout(me=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    把目前這台裝置的 refresh token 標記成作廢。

    **注意「登出」在 JWT 系統裡的實際意義**：
    我們沒辦法把已經發出去的 access token 收回來——它不在資料庫裡，
    伺服器也不記得發過哪些。所以登出其實是：

    - 資料庫的 sessions 這筆設 `revoked_at = 現在`
    - 前端把 token 從 localStorage 刪掉

    結果是：手上那張 access token 最多還能用 30 分鐘，
    但 30 分鐘後想續期就會被擋下來。
    這就是為什麼 access token 的有效期要設短。

    ⚠️ **用 revoked_at 標記，不要 DELETE 這筆資料。**
    稽核時要看得到「誰在什麼時候登出的」。

    TODO(成員1): 實作
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員1 尚未實作")


@router.post("/logout-all", summary="登出所有裝置")
def logout_all(me=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    把這個使用者所有還有效的 session 全部作廢。

    使用情境：手機掉了、懷疑帳號被盜。

    TODO(成員1): UPDATE sessions SET revoked_at = now()
                 WHERE user_id = ? AND revoked_at IS NULL
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員1 尚未實作")


@router.get("/me", summary="我是誰")
def me(me=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    回傳目前登入者的資訊、家庭角色，以及「誰看得到我的紀錄」。

    前端一載入就會打這支，用來決定側欄要顯示哪些項目
    （例如成員角色看不到家庭總覽）。

    **`guardedBy` 這個欄位一定要回**，前端會把它顯示在總覽頁上。
    這是刻意的設計：被監管的人**必須知道自己被誰監管**，
    系統不提供「隱藏監管」的選項——偷偷監看家人的消費會破壞信任，
    而信任是家庭記帳能持續下去的前提。

    TODO(成員1): 回傳 { user, family, role, guardedBy: [...] }
                 形狀要跟 site/js/api.js 裡的契約一致
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員1 尚未實作")


@router.patch("/password", summary="修改密碼")
def change_password(me=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    修改密碼。要先驗證舊密碼。

    **改完之後要把其他所有 session 作廢**（等於自動執行一次 logout-all），
    只保留目前這台。

    為什麼？因為使用者會改密碼，往往就是因為他覺得帳號可能被盜了。
    如果改完密碼，攻擊者手上的舊 token 還能繼續用，那改密碼就沒意義了。

    TODO(成員1): 1. verify_password 檢查舊密碼
                 2. hash_password 存新的
                 3. 作廢其他 session
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員1 尚未實作")


@router.get("/sessions", summary="列出登入中的裝置")
def list_sessions(me=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    列出這個帳號目前有效的登入，讓使用者可以個別踢掉。

    ⚠️ **回傳的資料裡不可以有 token 的雜湊值。**
    只回「什麼時候登入的、用什麼裝置、最後活動時間」這類資訊就好。

    TODO(成員1): 查 sessions WHERE user_id = ? AND revoked_at IS NULL
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員1 尚未實作")
