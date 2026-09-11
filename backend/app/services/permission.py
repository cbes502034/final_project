"""
權限計算：誰看得到誰的資料。 ✦ 負責人：成員4（家庭與可見範圍）　✦ 分支：m4-access
✦ 這是共用元件，成員2 與成員3 都要用，第 1 週要最優先完成

===========================================================================
為什麼這段邏輯一定要獨立成一個檔案？
===========================================================================
「我看得到哪些人的資料」這個問題，在下面這些地方都會被問到：

    GET /api/transactions    要列出誰的明細
    GET /api/summary         要加總誰的收支
    GET /api/stats           要統計誰的資料
    GET /api/advices         要看誰的建議

如果每支路由各寫一次，只要有**一支寫錯**，那支就變成資料外洩的破口。
而且權限規則之後一定會改（例如新增一種角色），
散在四個地方改，漏掉一個就出事。

**寫一次，四個地方共用。這是安全性的問題，不是程式碼美感的問題。**

===========================================================================
規則本身
===========================================================================
    master  →  看得到全家所有人
    parent  →  看得到自己 + 被指派監管的人
    member  →  只看得到自己

另外還有一條反向的規則：**被監管者看得到「誰在監管我」**。
這不是漏洞，是刻意的設計——系統不提供隱藏監管的選項。
"""

from sqlalchemy.orm import Session


def visible_user_ids(db: Session, me_id: int, family_id: int) -> list[int]:
    """
    算出「這個人看得到哪些人的資料」，回傳 user_id 的清單。

    用法：

        ids = visible_user_ids(db, me.id, me.family_id)
        rows = db.query(Transaction).filter(Transaction.user_id.in_(ids)).all()

    ⚠️ **回傳的清單一定要包含自己**。漏掉的話使用者會看不到自己的帳，
    這是很容易犯的錯（寫查詢時只想到「監管的人」，忘了自己）。

    TODO(成員4): 1. 查 family_members 拿到我的角色
                 2. role == 'master' → 回傳全家所有 active 成員
                 3. 否則 → [自己] + guardianships 裡 guardian_id 是我
                    且 ended_at 是 NULL 的那些 ward_id
    """
    # 還沒實作前先回傳只有自己，這是最安全的預設值——
    # 權限相關的程式碼，未完成時要往「看不到」的方向倒，不能往「看得到」倒
    return [me_id]


def can_view(db: Session, me_id: int, target_id: int, family_id: int) -> bool:
    """
    我能不能看 target 這個人的資料。

    用在「帶了 user_id 參數」的查詢上：不能看就回 403。

    TODO(成員4): return target_id in visible_user_ids(db, me_id, family_id)
    """
    return me_id == target_id


def can_edit(db: Session, me_id: int, owner_id: int) -> bool:
    """
    我能不能修改 owner 的那筆紀錄。

    ⚠️ **修改和刪除的權限不一樣**：
    監管者可以改（幫忙補資料），但**不能刪**。
    刪除只有本人可以——否則被監管者無法信任這份紀錄的完整性。

    TODO(成員4): 實作。刪除請另外用 can_delete（本人限定）
    """
    return me_id == owner_id
