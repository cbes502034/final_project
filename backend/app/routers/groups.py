"""
帳本：開、改、封存、移除、成員、結算、通知。

負責人：成員2（記帳）　✦ 分支：m2-ledger

===========================================================================
現在每一支都回 501（後端還沒做這一支），**守衛與主體模型已經接好**
===========================================================================
要做的事：把函式裡的 `raise not_ready(...)` 換成真的實作，然後拿掉 `@stub`。
* 誰能打這一支：已經由守衛擋好（看 @xxx_required 或 Depends(...)），不用自己再判斷身分
* 前端送什麼、要回什麼：docs/02-前後端串接契約.md 同名的章節
* 增刪改查：app/toolkit/crud.py（find／get／save／remove／to_dict）
* 規則（誰可以、什麼時候不行）：app/toolkit/ 對應的模組，函式說明裡寫了拿來怎麼用
* 回傳的 id 要轉成字串（crud.to_dict 預設就會轉）

`python -m app.ownership` 會列出每個人還剩幾支（有 @stub 的算還沒做）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.guards import block_admin, in_group
from app.models import User
from app.routers._stub import not_ready, stub
from app.schemas.group import GroupIn, GroupMemberIn, GroupPatchIn, NotifyIn
from app.toolkit.db import get_db

router = APIRouter(tags=["帳本"])
OWNER = "成員2"


@router.get("/groups", summary="我加入的帳本")
@block_admin
@stub
def list_groups(me: User, includeArchived: bool = False, db: Session = Depends(get_db)):
    """我加入的帳本

    GET /api/groups

    只回 group_members 有我的、removed_at IS NULL；includeArchived 才含封存的。
    """
    raise not_ready("GET /api/groups", OWNER)


@router.post("/groups", summary="開一本帳")
@block_admin
@stub
def create_group(body: GroupIn, me: User, db: Session = Depends(get_db)):
    """開一本帳

    POST /api/groups

    建立者自動寫一筆 group_members；temp 要有 endsOn；同一個家庭裡重名（含封存的）回 409。
    """
    raise not_ready("POST /api/groups", OWNER)


@router.patch("/groups/{gid}", summary="改名稱、顏色、說明")
@stub
def update_group(
    body: GroupPatchIn,
    group=Depends(in_group("gid", owner=True)),
    db: Session = Depends(get_db),
):
    """改名稱、顏色、說明

    PATCH /api/groups/{gid}

    守衛已經確認是建立的人。可以改 name／color／note；archived: false = 復原封存；同一個家庭裡重名回 409。
    """
    raise not_ready("PATCH /api/groups/{gid}", OWNER)


@router.delete("/groups/{gid}", summary="封存；permanent=true 是移除")
@stub
def archive_or_remove_group(
    permanent: bool = False,
    group=Depends(in_group("gid", owner=True)),
    db: Session = Depends(get_db),
):
    """封存；permanent=true 是移除

    DELETE /api/groups/{gid}

    封存設 archived_at；移除用 ledger.require_removable（只限結算過的），設 removed_at，紀錄一筆都不刪。
    """
    raise not_ready("DELETE /api/groups/{gid}", OWNER)


@router.post("/groups/{gid}/members", summary="把家人加進這本帳")
@stub
def add_group_member(
    body: GroupMemberIn,
    group=Depends(in_group("gid", owner=True)),
    db: Session = Depends(get_db),
):
    """把家人加進這本帳

    POST /api/groups/{gid}/members

    只能加同一個家庭的人；平台管理員不行。
    """
    raise not_ready("POST /api/groups/{gid}/members", OWNER)


@router.delete("/groups/{gid}/members/{user_id}", summary="把人移出這本帳")
@stub
def remove_group_member(user_id: str, group=Depends(in_group("gid", owner=True)), db: Session = Depends(get_db)):
    """把人移出這本帳

    DELETE /api/groups/{gid}/members/{user_id}

    他自己記過的紀錄不動（仍在他自己的明細裡）。
    """
    raise not_ready("DELETE /api/groups/{gid}/members/{user_id}", OWNER)


@router.post("/groups/{gid}/settle", summary="結算活動帳本")
@stub
def settle_group(group=Depends(in_group("gid", owner=True)), db: Session = Depends(get_db)):
    """結算活動帳本

    POST /api/groups/{gid}/settle

    設 settled_at，之後唯讀；不搬動任何紀錄。
    """
    raise not_ready("POST /api/groups/{gid}/settle", OWNER)


@router.patch("/groups/{gid}/notify", summary="這本帳有動靜要不要通知我")
@stub
def set_group_notify(body: NotifyIn, group=Depends(in_group("gid")), db: Session = Depends(get_db)):
    """這本帳有動靜要不要通知我

    PATCH /api/groups/{gid}/notify

    改 group_members.notify（預設關）。
    """
    raise not_ready("PATCH /api/groups/{gid}/notify", OWNER)
