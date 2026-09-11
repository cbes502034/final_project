"""
段落記帳。 ✦ 負責人：成員2（記帳）　✦ 分支：m2-ledger　★ 整個系統的核心

===========================================================================
這個檔案負責哪些路由
===========================================================================
掛載前綴是 /api/nlp。

    編號  方法   路徑              權限   用途
    ----------------------------------------------------------------
     24   POST  /parse            登入   一句話 → 一筆。只解析，不寫入
     25   POST  /parse-batch      登入   一段話 → 切成 N 筆。只解析，不寫入
     26   POST  /confirm          登入   單筆確認後才寫入
     27   POST  /confirm-batch    登入   批次確認後一次寫入 N 筆

===========================================================================
為什麼要分成「解析」和「確認」兩支？這是本專題最重要的設計決定
===========================================================================
最直覺的寫法是一支就好：使用者送文字進來，模型解析完直接寫進資料庫。
**我們刻意不這樣做**，理由有三個：

**一、模型會錯，而且錯了使用者只能事後補救**
   如果直接寫入，模型把「在全家買飲料」判斷成家人給的錢，
   使用者要自己去明細裡找出那筆、點編輯、改分類。摩擦比手動記帳還高。

**二、錯誤不會被記錄下來，資料飛輪就轉不起來**
   分成兩步之後，「模型原本解析成什麼」和「使用者改成什麼」
   會一起存進 nlp_parses 表。**使用者每修正一次，就等於免費標了一筆訓練資料。**
   這是本系統最值錢的一步——用得越久，訓練資料越多，模型越準。

**三、模型永遠不碰資料庫，安全邊界很清楚**
   模型只負責「把文字變成結構化欄位」，寫入的權限在使用者確認那一刻才發生。

所以流程長這樣：

    使用者寫一段話
        ↓
    POST /parse-batch  →  模型切分 + 抽欄位 + 給信心度  →  ❌ 不寫入
        ↓
    前端列出來，缺欄位標紅、低信心標黃，使用者逐筆確認或修改
        ↓
    POST /confirm-batch  →  ✅ 這時才寫進 transactions，同時記錄修正

===========================================================================
段落比單句難在哪裡？
===========================================================================
單句只要抽欄位，段落還多一件事：**先判斷這段話裡有幾筆**。

    「早上買早餐55，中午跟同事吃飯320，晚上加油1200，今天打工賺了1500」
     └── 1 ──┘  └───── 2 ─────┘  └── 3 ──┘  └──── 4 ────┘

切錯（把兩筆合成一筆）比抽錯欄位更難發現——欄位再準也沒用。
所以回傳的每一筆都要帶 `span`，標出它對應原句的哪一段，
讓前端顯示給使用者看，**切分結果同樣要被確認**。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user

router = APIRouter()


@router.post("/parse", summary="單句解析（不寫入）")
def parse(me=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    把一句話解析成一筆記帳資料。**只回傳結果，不寫進資料庫。**

    要回傳的東西：

    - `parsed`：日期、金額、收支方向、分類、店家
    - `confidence`：**每一欄各自的信心度**，不是整筆一個分數
    - `parseId`：這次解析的編號，使用者確認時要帶回來，才能把修正對上
    - `note`：給使用者看的說明，例如「「今天」已換算成實際日期」

    為什麼信心度要逐欄給？因為模型常常是「金額很確定、分類不確定」。
    給整筆一個分數的話，前端只能整筆標黃，使用者不知道要檢查哪一欄。
    逐欄給，前端就能精準地只把分類那一格標黃。

    TODO(成員2): 呼叫 services/llm/parse.py 的 parse_one()，
                 用 Pydantic 驗證模型回傳的 JSON，
                 驗不過就帶著錯誤訊息重試一次，再失敗才回錯誤給前端
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員2 尚未實作")


@router.post("/parse-batch", summary="段落解析（不寫入）★ 系統核心")
def parse_batch(me=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    把一整段話切成 N 筆，逐筆抽欄位。**只回傳結果，不寫進資料庫。**

    回傳的 `items` 每一筆要有：

    - `seq`：第幾筆
    - `span`：**對應原句的哪一段**（切分結果要讓使用者驗證）
    - `date` / `amount` / `kind` / `cat` / `merchant`：抽出來的欄位
    - `conf`：逐欄信心度
    - `missing`：**抽不到的欄位名稱清單**，例如 `["amount"]`
    - `hint`：給使用者的提示，例如「這一句抓不到金額」

    `missing` 是前端「把缺的欄位標紅 + 停用送出鈕」的依據，
    一定要回，而且要準——寧可回報缺漏讓使用者填，也不要猜一個數字填進去。

    **猜錯的金額比空白危險得多**：空白使用者一定會發現，
    猜錯的數字他可能直接按下確認就送出去了。

    TODO(成員2): 呼叫 services/llm/parse.py 的 parse_batch()。
                 prompt 要帶 few-shot 範例和這個家庭的分類體系
                 （分類清單打成員3 的 GET /api/categories 拿，不要自己查 categories 表）
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員2 尚未實作")


@router.post("/confirm", summary="確認後寫入一筆")
def confirm(me=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    使用者確認過解析結果，**這時才真的寫進資料庫**。

    要做兩件事，第二件比第一件重要：

    1. 寫進 transactions，`source` 記成 `nlp`
    2. **把修正記錄進 nlp_parses**：原始輸入、模型輸出、使用者改成什麼

    第 2 件是資料飛輪的入口。請求裡的 `corrected` 欄位如果有值，
    就代表使用者改過——那一筆是**含標註的訓練資料**，非常珍貴。

    ⚠️ `source` 一定要記成 `nlp`。手動記帳走的是
    `POST /api/transactions`，那支記 `manual`。
    **兩者不可以混**，否則 nlp_parses 會被手動資料汙染，
    之後算「模型正確率」時分母就錯了。

    TODO(成員2): 實作兩段寫入。建議包在同一個交易裡，
                 避免 transactions 寫進去了但 nlp_parses 沒寫到
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員2 尚未實作")


@router.post("/confirm-batch", summary="確認後一次寫入 N 筆")
def confirm_batch(me=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    批次寫入，回傳 `{"created": 筆數}`。

    ⚠️ **要嘛全部成功，要嘛全部不寫**（同一個資料庫交易）。
    如果寫到第 3 筆失敗，前面 2 筆已經進去了，
    使用者會看到「寫入失敗」但明細裡卻多了兩筆——然後他會再按一次，
    變成重複記帳。這種 bug 很難查，一開始就用交易包起來就不會發生。

    在 SQLAlchemy 裡就是：迴圈裡只 `db.add()`，
    迴圈結束後才 `db.commit()` 一次；中間出錯就 `db.rollback()`。

    TODO(成員2): 實作，記得每一筆也都要寫 nlp_parses
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員2 尚未實作")
