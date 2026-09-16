"""
路由守衛。擋在路由前面：沒登入、被停權、角色不對、不是自己的資料——路由裡的程式一行都不會跑。

負責人：成員1（共用元件）——四個人的路由都用它，改之前先在群組講一聲

===========================================================================
從 MineMarket 的 AuthDecorator.py 來的
===========================================================================
    MineMarket（Flask）              這裡（FastAPI）
    @guestOnly                       @guest_only
    @userRequired                    @login_required
    @adminRequired                   @admin_required
    @blockAdmin                      @block_admin
    @tokenRequired(refresh=...)      Depends(token_required("password_reset"))
    ── 家庭記帳多出來的 ──
                                     @parent_required、@family_required、@onboarded_required
                                     Depends(own(Transaction, "tx_id"))       這筆是不是我的
                                     Depends(in_group("gid", owner=False))    我在不在這本帳裡
                                     Depends(can_see_user("user_id"))         我能不能看這個人

    MineMarket 擋下來是 redirect 回登入頁；這裡是 API，擋下來回 401／403／404，前端自己帶去登入頁。

===========================================================================
兩種寫法，功能一樣，挑順手的
===========================================================================
1. 裝飾器（MineMarket 的習慣）。函式有 `me` 參數，登入的人會自動塞進來：

        @router.get("/family")
        @login_required
        def get_family(me: User, db: Session = Depends(get_db)):
            ...

        @router.delete("/family")
        @parent_required
        def dissolve(me: User): ...

   ⚠️ 裝飾器要寫在 @router.xxx 的**下面**（先套守衛，再掛路由）。

2. FastAPI 的 Depends：

        @router.get("/family")
        def get_family(me: User = Depends(guard()), db: Session = Depends(get_db)): ...

===========================================================================
一支 guard() 管所有「看身分」的規則
===========================================================================
    guard()                         要登入、沒被停權（每一個 guard 都先檢查這兩件事）
    guard(role="parent")            家長（"child" 子女；("parent","child") 任一個）
    guard(family=True)              已經在某個家庭裡（False：還沒有家庭，例如建立家庭）
    guard(platform_admin=True)      平台管理員
    guard(platform_admin=False)     不是平台管理員——他沒有任何財務資料，財務路由一律擋
    guard(onboarded=True)           走完註冊後的個人化設定
    guard(guest=True)               還沒登入才能用（例如註冊）；已經登入回 400

回傳的 `me` 是 User 物件，另外掛了兩個屬性，路由不用再查一次：
    me.family_id     我在哪個家庭（沒有是 None）
    me.family_role   'parent'／'child'／None

===========================================================================
⚠️ 守衛擋的是「誰」，不是全部
===========================================================================
「這筆紀錄我能不能看」要看可見範圍（監管 ∪ 同帳本），規則在 toolkit/scope.py；
own()／in_group()／can_see_user() 已經幫你接好，其他查詢請照 scope.py 檔頭的寫法用 or_。
**權限一律在後端判斷。** 前端藏按鈕不是權限控制。
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any

from fastapi import Depends, Path, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.toolkit import crud, errors, password_reset, tokens
from app.toolkit.db import get_db
from app.toolkit.deps import bearer, current_user_id

__all__ = [
    "current_user", "guard", "protect",
    "login_required", "guest_only", "parent_required", "family_required", "onboarded_required",
    "admin_required", "block_admin",
    "own", "in_group", "can_see_user", "token_required", "visible_scope",
]


def _models():
    # 延後匯入：models 匯入 toolkit.db，toolkit.db 又要讀設定；避免 import 這個檔就連帶載入全部
    from app import models
    return models


# ===========================================================================
# 目前登入的人
# ===========================================================================
def current_user(uid: int = Depends(current_user_id), db: Session = Depends(get_db)):
    """驗 token → 撈使用者 → 擋停權 → 掛上家庭與角色。每一個守衛的第一步。"""
    m = _models()
    user = db.get(m.User, uid)
    if user is None:
        raise errors.unauthorized("登入資訊無效，請重新登入")
    if user.suspended_at is not None:
        # ⚠️ 已經登入的人被停權，下一次請求就要擋，不是等他 token 過期
        raise errors.forbidden("這個帳號已被停權：" + (user.suspended_reason or "違反使用規範"))
    fm = crud.get(m.FamilyMember, where={"user_id": user.id, "status": "active"}, db=db)
    user.family_id = fm.family_id if fm else None
    user.family_role = fm.role if fm else None
    return user


def guard(
    *,
    role: str | tuple[str, ...] | None = None,
    family: bool | None = None,
    platform_admin: bool | None = None,
    onboarded: bool | None = None,
    guest: bool = False,
) -> Callable[..., Any]:
    """產生一個 FastAPI 依賴。規則全部過了回傳 `me`（guest=True 時回傳 None）。見檔頭。"""
    if guest:
        def _guest(creds: HTTPAuthorizationCredentials | None = Depends(bearer)):
            if creds and creds.credentials:
                try:
                    tokens.read_access_token(creds.credentials)
                except tokens.TokenError:
                    return None                      # 帶了壞掉或過期的 token：當作沒登入
                raise errors.bad_request("你已經登入了，要換帳號請先登出")
            return None
        return _guest

    roles = (role,) if isinstance(role, str) else role

    def _dep(me=Depends(current_user)):
        if platform_admin is True and not me.is_platform_admin:
            raise errors.forbidden("只有平台管理員可以用")
        if platform_admin is False and me.is_platform_admin:
            # 平台管理員沒有財務資料，這些路由對他沒有意義——那正是這個角色的定義
            raise errors.forbidden("平台管理員不能使用財務功能")
        if onboarded is True and me.onboarded_at is None:
            raise errors.forbidden("先完成註冊後的個人化設定")
        if family is True and me.family_id is None:
            raise errors.forbidden("你還沒有加入任何家庭")
        if family is False and me.family_id is not None:
            raise errors.conflict("你已經在一個家庭裡了")
        if roles and me.family_role not in roles:
            names = {"parent": "家長", "child": "子女"}
            raise errors.forbidden("只有%s可以做這件事" % "或".join(names.get(r, r) for r in roles))
        return me

    return _dep


# ===========================================================================
# 裝飾器（MineMarket 的寫法）
# ===========================================================================
def protect(**rules: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """把 guard(**rules) 套在一個路由函式上。函式有 `me` 參數就把登入的人塞進去。

        @router.post("/family/invite")
        @protect(role="parent")
        def create_code(me: User, body: InviteIn): ...
    """
    dep = guard(**rules)

    def decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
        sig = inspect.signature(fn)
        has_me = "me" in sig.parameters
        # 全部改成關鍵字參數：FastAPI 本來就用關鍵字呼叫，而且這樣「有預設值的參數在前面」也合法
        params = [p.replace(kind=inspect.Parameter.KEYWORD_ONLY,
                            default=Depends(dep) if p.name == "me" else p.default)
                  for p in sig.parameters.values()]
        if not has_me:
            params.append(inspect.Parameter("_guard", inspect.Parameter.KEYWORD_ONLY, default=Depends(dep)))

        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def wrapper(**kwargs: Any) -> Any:
                if not has_me:
                    kwargs.pop("_guard", None)
                return await fn(**kwargs)
        else:
            @functools.wraps(fn)
            def wrapper(**kwargs: Any) -> Any:
                if not has_me:
                    kwargs.pop("_guard", None)
                return fn(**kwargs)

        wrapper.__signature__ = sig.replace(parameters=params)   # type: ignore[attr-defined]
        return wrapper

    return decorate


def _shortcut(**rules: Any):
    """@login_required 跟 @login_required(onboarded=True) 兩種都能用。"""
    def entry(fn: Callable[..., Any] | None = None, **more: Any):
        if fn is not None and callable(fn):
            return protect(**rules)(fn)
        return protect(**{**rules, **more})
    return entry


login_required = _shortcut()                              # MineMarket 的 userRequired
guest_only = _shortcut(guest=True)                        # MineMarket 的 guestOnly
parent_required = _shortcut(role="parent")
family_required = _shortcut(family=True)
onboarded_required = _shortcut(onboarded=True)
admin_required = _shortcut(platform_admin=True)           # MineMarket 的 adminRequired
block_admin = _shortcut(platform_admin=False)             # MineMarket 的 blockAdmin


# ===========================================================================
# 看資料本身的守衛：回傳那一筆，路由直接用
# ===========================================================================
def _path_id(raw: Any) -> Any:
    try:
        return int(raw)          # 契約：前端傳的是字串 id，資料庫是整數
    except (TypeError, ValueError):
        raise errors.not_found("找不到這筆資料") from None


def _reads_path(param: str, **deps: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """讓依賴宣告它讀的路徑參數 {param}：/docs 上才看得到那一格、試打時填得進去。

    被包的函式收 (raw, **deps)——raw 是路徑上的原始字串。
    """
    def wrap(fn: Callable[..., Any]) -> Callable[..., Any]:
        def _dep(**kw: Any) -> Any:
            raw = kw.pop(param)
            return fn(raw, **kw)

        params = [inspect.Parameter(param, inspect.Parameter.KEYWORD_ONLY, annotation=str,
                                    default=Path(..., description="路徑上的 id（字串）"))]
        params += [inspect.Parameter(k, inspect.Parameter.KEYWORD_ONLY, default=v) for k, v in deps.items()]
        _dep.__signature__ = inspect.Signature(params)   # type: ignore[attr-defined]
        _dep.__name__ = fn.__name__
        return _dep
    return wrap


def own(model: Any, param: str = "id", field: str = "user_id", *, missing: str = "找不到這筆資料",
        not_mine: str = "這是別人的資料，你只能檢視") -> Callable[..., Any]:
    """這一筆是不是我的（例如修改、刪除紀錄）。回傳那一筆。

        @router.patch("/transactions/{tx_id}")
        def update_tx(tx=Depends(own(Transaction, "tx_id")), body: TxPatch, db=Depends(get_db)): ...

    ⚠️ 監管是唯讀的：家長看得到子女的紀錄，但改不動——所以這裡只認「本人」。
    """
    @_reads_path(param, me=Depends(current_user), db=Depends(get_db))
    def _dep(raw: str, me: Any, db: Session):
        row = db.get(model, _path_id(raw))
        if row is None:
            raise errors.not_found(missing)
        if getattr(row, field) != me.id:
            raise errors.forbidden(not_mine)
        return row
    return _dep


def in_group(param: str = "gid", *, owner: bool = False) -> Callable[..., Any]:
    """我在不在這本帳裡（owner=True：還要是建立的人）。回傳 Group。移除的帳本一律當作不存在。"""
    @_reads_path(param, me=Depends(current_user), db=Depends(get_db))
    def _dep(raw: str, me: Any, db: Session):
        m = _models()
        gid = _path_id(raw)
        group = crud.get(m.Group, gid, db=db)
        if group is None or group.removed_at is not None:
            raise errors.not_found("找不到這本帳")
        if owner:
            if group.created_by != me.id:
                raise errors.forbidden("只有建立這本帳的人可以做這件事")
        elif not crud.exists(m.GroupMember, {"group_id": gid, "user_id": me.id}, db=db):
            raise errors.forbidden("你不在這本帳裡")
        return group
    return _dep


def visible_scope(me: Any, db: Session) -> tuple[set, set]:
    """我看得到的人、看得到的帳本（toolkit/scope.py 的兩條路），查明細的路由直接用。

        users, groups = visible_scope(me, db)
        rows = find(Transaction, {"or": [{"user_id__in": users}, {"group_id__in": groups}]})
    """
    from app.toolkit import scope
    m = _models()
    guards_rows = crud.find(m.Guardianship, {"guardian_id": me.id, "ended_at__isnull": True}, db=db)
    fam_rows = crud.find(m.FamilyMember, {"family_id": me.family_id, "status": "active"}, db=db) if me.family_id else []
    gm_rows = crud.find(m.GroupMember, {"user_id": me.id}, db=db)
    live = set(crud.find(m.Group, {"id__in": [g.group_id for g in gm_rows], "removed_at__isnull": True}, fields="id", db=db)) \
        if gm_rows else set()
    users = scope.visible_users(me.id, guards_rows, fam_rows)
    groups = {g for g in scope.visible_groups(me.id, gm_rows) if g in live}
    return users, groups


def can_see_user(param: str = "user_id") -> Callable[..., Any]:
    """我能不能查這個人的資料（監管、同家庭家長、或同帳本）。回傳那個 User。沒權限回 403，不回空的。"""
    @_reads_path(param, me=Depends(current_user), db=Depends(get_db))
    def _dep(raw: str, me: Any, db: Session):
        m = _models()
        target_id = _path_id(raw)
        target = db.get(m.User, target_id)
        if target is None:
            raise errors.not_found("找不到這個人")
        users, groups = visible_scope(me, db)
        members = crud.find(m.GroupMember, {"group_id__in": list(groups)}, db=db) if groups else []
        if target_id not in users and target_id not in {r.user_id for r in members}:
            raise errors.forbidden("你沒有權限看這個人的紀錄")
        return target
    return _dep


def token_required(kind: str = "password_reset", field: str = "token") -> Callable[..., Any]:
    """一次性連結的 token 還能不能用（MineMarket 的 tokenRequired）。回傳那一列。

        @router.post("/auth/password-reset/confirm")
        def confirm(body: ResetConfirmIn, row=Depends(token_required()), db=Depends(get_db)): ...

    ⚠️ 找不到、過期、用過一律回同一句話（400），不讓人分辨是哪一種。
    ⚠️ 這裡只檢查、不作廢——改完密碼之後，路由要在同一個交易裡設 used_at。
    """
    if kind != "password_reset":
        raise ValueError("目前只有 password_reset 這一種一次性連結")

    async def _dep(request: Request, db: Session = Depends(get_db)):
        # 從請求主體讀 token。用 request 而不是 Body(...)：路由自己也要宣告主體模型，兩個 Body 會打架
        m = _models()
        try:
            payload = await request.json()
        except ValueError:
            payload = {}
        try:
            digest = password_reset.hash_token((payload or {}).get(field))
        except ValueError:
            raise errors.bad_request(password_reset.INVALID_MESSAGE) from None
        row = crud.get(m.PasswordReset, where={"token_hash": digest}, db=db)
        try:
            password_reset.require_usable(row.expires_at if row else None, row.used_at if row else None)
        except ValueError:
            raise errors.bad_request(password_reset.INVALID_MESSAGE) from None
        return row
    return _dep
