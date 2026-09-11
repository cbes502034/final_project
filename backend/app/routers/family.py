"""
家庭與權限。 ✦ 負責人：成員1（帳號與權限）

===========================================================================
這個檔案負責哪些路由
===========================================================================
掛載前綴是 /api。

    編號  方法    路徑                          權限    用途
    ----------------------------------------------------------------------
      9   GET    /family                       登入    家庭資訊、成員清單
     10   POST   /family                       登入    建立家庭，建立者成為 master
     11   POST   /family/invite                master  產生邀請碼
     12   POST   /family/join                  登入    用邀請碼加入
     13   PATCH  /family/members/{user_id}      master  修改成員角色
     14   DELETE /family/members/{user_id}      master  移除成員
     15   GET    /guardianships                登入    監管關係
     16   POST   /guardianships                master  建立監管關係
     17   DELETE /guardianships/{id}           master  解除監管

===========================================================================
這個模組的兩條鐵則
===========================================================================
**一、刪除一律用「標記」，不要真的 DELETE**
    移除成員是 `family_members.status = 'removed'`，
    解除監管是 `guardianships.ended_at = 現在`。
    理由：那個人過去記的帳還在，直接刪掉會讓歷史統計整個對不上；
    而且稽核需要看得到「誰在什麼時候被移除」。

**二、監管關係雙向可見**
    第 15 支路由**被監管者自己也查得到**，這不是漏洞，是刻意的設計。
    系統不提供「隱藏監管」的選項。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_master

router = APIRouter()


@router.get("/family", summary="家庭資訊與成員清單")
def get_family(me=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    回傳我所屬家庭的資訊，以及所有成員的角色。

    TODO(成員1): 回傳形狀要跟 frontend/js/api.js 的 members() 一致
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員1 尚未實作")


@router.post("/family", status_code=status.HTTP_201_CREATED, summary="建立家庭")
def create_family(me=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    建立一個新家庭，**建立者自動成為 master**。

    一個人可以同時屬於多個家庭（例如原生家庭和自己的小家庭），
    所以角色存在 `family_members` 而不是 `users` 上。
    這就是為什麼「帳號」和「家庭角色」要分成兩張表。

    TODO(成員1): 建立 families 一筆 + family_members 一筆（role='master'）
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員1 尚未實作")


@router.post("/family/invite", summary="產生邀請碼")
def create_invite(me=Depends(require_master), db: Session = Depends(get_db)):
    """
    產生一組邀請碼給新成員。

    邀請碼要有三個性質：

    1. **夠隨機** —— 用 `secrets.token_urlsafe()`，不要用 `random`。
       `random` 是可預測的偽隨機，攻擊者猜得出下一組。
    2. **會過期** —— 設個 7 天，過期的邀請碼不該還能用
    3. **用過就失效** —— 一組碼只能加入一個人

    TODO(成員1): 產碼並寫進 family_invites（這張表要自己加進 models）
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員1 尚未實作")


@router.post("/family/join", summary="用邀請碼加入家庭")
def join_family(me=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    輸入邀請碼加入家庭，角色預設是 member。

    TODO(成員1): 驗證碼有效、沒過期、沒被用過，
                 然後建立 family_members 一筆，並把邀請碼標記成已使用
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員1 尚未實作")


@router.patch("/family/members/{user_id}", summary="修改成員角色")
def update_member(user_id: int, me=Depends(require_master), db: Session = Depends(get_db)):
    """
    把某個成員改成 master / parent / member。

    路徑裡的 `{user_id}` 叫做**路徑參數**。你只要在函式參數寫
    `user_id: int`，FastAPI 就會自動把網址裡那一段轉成整數塞給你；
    如果有人打 `/family/members/abc`，它會自己回 422，你不用檢查。

    ⚠️ **要擋住「把自己降級」**。如果家裡唯一的 master 把自己改成 member，
    就再也沒有人能管理這個家庭了，只能進資料庫手動救。

    TODO(成員1): 實作，記得擋掉最後一個 master 自我降級
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員1 尚未實作")


@router.delete("/family/members/{user_id}", summary="移除成員")
def remove_member(user_id: int, me=Depends(require_master), db: Session = Depends(get_db)):
    """
    把成員移出家庭。**標記 status='removed'，不要刪資料。**

    TODO(成員1): 實作
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員1 尚未實作")


@router.get("/guardianships", summary="監管關係")
def list_guardianships(me=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    查詢監管關係：我監管誰、誰監管我。

    ⚠️ **這支路由不是 master 限定**。一般成員也要查得到「誰看得到我」，
    因為那會顯示在他自己的總覽頁上。這是設計，不是疏忽。

    TODO(成員1): 回傳兩個清單 —— guarding（我監管的人）、guardedBy（監管我的人）
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員1 尚未實作")


@router.post("/guardianships", status_code=status.HTTP_201_CREATED, summary="建立監管關係")
def create_guardianship(me=Depends(require_master), db: Session = Depends(get_db)):
    """
    指定「誰看得到誰」。

    TODO(成員1): 檢查兩人都在同一個家庭，避免建立跨家庭的監管關係
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員1 尚未實作")


@router.delete("/guardianships/{gid}", summary="解除監管")
def end_guardianship(gid: int, me=Depends(require_master), db: Session = Depends(get_db)):
    """
    解除監管關係。**設 ended_at，不要 DELETE。**

    TODO(成員1): 實作
    """
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "TODO：成員1 尚未實作")
