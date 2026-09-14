"""
家庭：建立、邀請、成員角色、解散、監管關係、零用金、稽核。

負責人：成員4（家庭）　✦ 分支：m4-access

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

from app.guards import admin_required, block_admin, family_required, parent_required, protect
from app.models import User
from app.routers._stub import not_ready, stub
from app.schemas.family import AllowanceIn, FamilyIn, GuardianshipIn, InviteCodeIn, InviteIn, JoinIn, RolePatchIn
from app.toolkit.db import get_db

router = APIRouter(tags=["家庭與權限"])
OWNER = "成員4"


@router.get("/family", summary="家庭、成員、監管關係")
@block_admin
@stub
def get_family(me: User, db: Session = Depends(get_db)):
    """家庭、成員、監管關係

    GET /api/family

    回 {me, myRole, family, visible, queryable, members, roles, guardianships, permissions}；看不到的人不回存款目標。
    """
    raise not_ready("GET /api/family", OWNER)


@router.post("/family", summary="建立家庭（建立的人是家長）")
@protect(family=False, platform_admin=False)
@stub
def create_family(body: FamilyIn, me: User, db: Session = Depends(get_db)):
    """建立家庭（建立的人是家長）

    POST /api/family

    family.clean_family_name；寫 families ＋ family_members（parent）；audit。
    """
    raise not_ready("POST /api/family", OWNER)


@router.delete("/family", summary="解散家庭（唯一的家長）")
@parent_required
@stub
def dissolve_family(me: User, db: Session = Depends(get_db)):
    """解散家庭（唯一的家長）

    DELETE /api/family

    family.require_can_dissolve；每個人 detach（監管 ended_at、零用金結束、帳本互相移出、邀請作廢），紀錄不刪；同一個交易。
    """
    raise not_ready("DELETE /api/family", OWNER)


@router.post("/family/invite", summary="產生邀請碼")
@parent_required
@stub
def create_invite_code(body: InviteCodeIn, me: User, db: Session = Depends(get_db)):
    """產生邀請碼

    POST /api/family/invite

    new_code → 只存 hash_code；expires_at(days=settings.invite_ttl_days)；同身分舊碼作廢。
    """
    raise not_ready("POST /api/family/invite", OWNER)


@router.post("/family/join", summary="用邀請碼加入")
@protect(family=False, platform_admin=False)
@stub
def join_family(body: JoinIn, me: User, db: Session = Depends(get_db)):
    """用邀請碼加入

    POST /api/family/join

    normalize_code → hash 比對 → require_joinable → require_has_parent（沒有家長 409）。
    """
    raise not_ready("POST /api/family/join", OWNER)


@router.get("/family/lookup", summary="用完整 email 找人")
@parent_required
@stub
def lookup_user(me: User, email: str | None = None, db: Session = Depends(get_db)):
    """用完整 email 找人

    GET /api/family/lookup

    family.lookup_status；只回名字、頭像、status，不回財務資料；要做速率限制。
    """
    raise not_ready("GET /api/family/lookup", OWNER)


@router.get("/family/invites", summary="收到的邀請、送出去的、邀請碼")
@block_admin
@stub
def list_invites(me: User, db: Session = Depends(get_db)):
    """收到的邀請、送出去的、邀請碼

    GET /api/family/invites

    received 給被邀請的人；sent、codes 只有家長。
    """
    raise not_ready("GET /api/family/invites", OWNER)


@router.post("/family/invites", summary="用帳號邀請")
@parent_required
@stub
def send_invite(body: InviteIn, me: User, db: Session = Depends(get_db)):
    """用帳號邀請

    POST /api/family/invites

    對方已在家庭、或已有沒回覆的邀請就擋。
    """
    raise not_ready("POST /api/family/invites", OWNER)


@router.post("/family/invites/{invite_id}/accept", summary="接受邀請")
@protect(family=False, platform_admin=False)
@stub
def accept_invite(me: User, db: Session = Depends(get_db)):
    """接受邀請

    POST /api/family/invites/{invite_id}/accept

    只有 invitee 本人；require_joinable；require_has_parent。
    """
    raise not_ready("POST /api/family/invites/{invite_id}/accept", OWNER)


@router.delete("/family/invites/{invite_id}", summary="婉拒或取消邀請")
@block_admin
@stub
def decline_invite(me: User, db: Session = Depends(get_db)):
    """婉拒或取消邀請

    DELETE /api/family/invites/{invite_id}

    被邀請的人 → declined；那一家的家長 → cancelled；不刪列。
    """
    raise not_ready("DELETE /api/family/invites/{invite_id}", OWNER)


@router.patch("/family/members/{user_id}", summary="改角色")
@parent_required
@stub
def change_member_role(body: RolePatchIn, me: User, db: Session = Depends(get_db)):
    """改角色

    PATCH /api/family/members/{user_id}

    family.require_can_change_role；設為家長時結束他被照看的關係；自己改成子女時結束他照看別人的關係。
    """
    raise not_ready("PATCH /api/family/members/{user_id}", OWNER)


@router.delete("/family/members/{user_id}", summary="家長移出子女；{user_id} 寫 me 是自己退出")
@family_required
@stub
def remove_member(me: User, db: Session = Depends(get_db)):
    """家長移出子女；{user_id} 寫 me 是自己退出

    DELETE /api/family/members/{user_id}

    me → family.require_can_leave；其他 → require_can_remove。紀錄不刪，監管／帳本／邀請一起收掉。
    """
    raise not_ready("DELETE /api/family/members/{user_id}", OWNER)


@router.get("/guardianships", summary="監管關係（雙向可見）")
@family_required
@stub
def list_guardianships(me: User, db: Session = Depends(get_db)):
    """監管關係（雙向可見）

    GET /api/guardianships

    同一個家庭、ended_at IS NULL；回 {guardianships: [{id, guardian, ward, since, mine}]}，名字前端會補。
    """
    raise not_ready("GET /api/guardianships", OWNER)


@router.post("/guardianships", summary="開始照看（監管人一定是自己）")
@parent_required
@stub
def create_guardianship(body: GuardianshipIn, me: User, db: Session = Depends(get_db)):
    """開始照看（監管人一定是自己）

    POST /api/guardianships

    family.require_can_guard（監管人一定是自己；只能照看同家庭的子女；已經在照看回 409）；audit。
    """
    raise not_ready("POST /api/guardianships", OWNER)


@router.delete("/guardianships/{gid}", summary="解除監管")
@family_required
@stub
def end_guardianship(me: User, db: Session = Depends(get_db)):
    """解除監管

    DELETE /api/guardianships/{gid}

    family.require_can_end_guard；設 ended_at、零用金歸零；audit。
    """
    raise not_ready("DELETE /api/guardianships/{gid}", OWNER)


@router.get("/allowances", summary="我給每個被照看的人多少零用金")
@block_admin
@stub
def list_allowances(me: User, db: Session = Depends(get_db)):
    """我給每個被照看的人多少零用金

    GET /api/allowances

    只列我照看的人；回 {allowances: [{wardId, wardName, amount, spent}]}，spent 是他這個月的支出（從明細算）。
    """
    raise not_ready("GET /api/allowances", OWNER)


@router.put("/allowance", summary="設定零用金")
@parent_required
@stub
def set_allowance(body: AllowanceIn, me: User, db: Session = Depends(get_db)):
    """設定零用金

    PUT /api/allowance

    ⚠️ 零用金是設定，不是一筆支出紀錄；只有監管他的人能設。
    """
    raise not_ready("PUT /api/allowance", OWNER)


@router.get("/audit", summary="稽核紀錄")
@admin_required
@stub
def list_audit(me: User, db: Session = Depends(get_db)):
    """稽核紀錄

    GET /api/audit

    只記動作，不記金額。回 {logs: [{id, at, actor, actorName, action, target, note}]}，由新到舊。
    at 用 ISO 8601；actorName 要帶（平台管理員沒有家庭，前端沒有成員清單可以對）。
    """
    raise not_ready("GET /api/audit", OWNER)
