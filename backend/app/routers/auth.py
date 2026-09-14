"""
身分認證：註冊、登入、token、個人資料、忘記密碼。

負責人：成員1（認證）　✦ 分支：m1-auth

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

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.guards import guest_only, login_required, token_required
from app.models import User
from app.routers._stub import not_ready, stub
from app.schemas.auth import AvatarIn, FinanceIn, LoginIn, LogoutIn, PasswordChangeIn, PasswordResetConfirmIn, PasswordResetIn, ProfilePatchIn, RefreshIn, RegisterIn, VerifyPasswordIn
from app.toolkit.db import get_db

router = APIRouter(tags=["身分認證"])
OWNER = "成員1"


@router.post("/auth/register", summary="註冊：名字、email、密碼")
@guest_only
@stub
def register(body: RegisterIn, db: Session = Depends(get_db)):
    """註冊：名字、email、密碼

    POST /api/auth/register

    email 轉小寫、已註冊回 409；密碼 passwords.check_strength()；帶了 savingsGoal 回 400。
    回傳同 login（accessToken、refreshToken、user），user.onboardedAt 是 null。
    """
    raise not_ready("POST /api/auth/register", OWNER)


@router.post("/auth/login", summary="登入")
@stub
def login(body: LoginIn, db: Session = Depends(get_db)):
    """登入

    POST /api/auth/login

    「沒有這個帳號」跟「密碼錯」回同一句話、同一個 401；查無此人也要跑一次雜湊比對（時間一樣）。
    通過之後才 roles.require_active()；寫一列 sessions（只存 refresh token 的雜湊）。
    """
    raise not_ready("POST /api/auth/login", OWNER)


@router.post("/auth/refresh", summary="用 refresh token 換新的 access token")
@stub
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    """用 refresh token 換新的 access token

    POST /api/auth/refresh

    tokens.read_refresh_token() → 用 fingerprint 找 sessions → 沒撤銷才發新的；refresh token 一次性，換發新的、撤銷舊的。
    """
    raise not_ready("POST /api/auth/refresh", OWNER)


@router.post("/auth/logout", summary="登出（撤銷這一台的 refresh token）")
@login_required
@stub
def logout(body: LogoutIn, me: User, db: Session = Depends(get_db)):
    """登出（撤銷這一台的 refresh token）

    POST /api/auth/logout

    sessions.revoked_at = now，不刪列。
    """
    raise not_ready("POST /api/auth/logout", OWNER)


@router.post("/auth/logout-all", summary="登出所有裝置")
@login_required
@stub
def logout_all(me: User, db: Session = Depends(get_db)):
    """登出所有裝置

    POST /api/auth/logout-all

    這個人所有 sessions 設 revoked_at，回 {"revoked": 幾筆}。
    """
    raise not_ready("POST /api/auth/logout-all", OWNER)


@router.get("/auth/me", summary="我是誰")
@login_required
@stub
def get_me(me: User, db: Session = Depends(get_db)):
    """我是誰

    GET /api/auth/me

    回 {user, family, visible, queryable, guardedBy}。user 要有 onboardedAt、theme、savingsGoal；不帶 income／expense（從明細算）。
    crud.to_dict(me, rename={"display_name": "name"})，密碼雜湊與大頭貼原始 bytes 預設不會送出去。
    """
    raise not_ready("GET /api/auth/me", OWNER)


@router.patch("/auth/me", summary="改個人資料、主題、個人化設定走完")
@login_required
@stub
def update_me(body: ProfilePatchIn, me: User, db: Session = Depends(get_db)):
    """改個人資料、主題、個人化設定走完

    PATCH /api/auth/me

    theme 用 theme.clean_theme()；onboarded 只收 true（設 onboarded_at）；email 不給改。
    """
    raise not_ready("PATCH /api/auth/me", OWNER)


@router.patch("/auth/password", summary="改密碼")
@login_required
@stub
def change_password(body: PasswordChangeIn, me: User, db: Session = Depends(get_db)):
    """改密碼

    PATCH /api/auth/password

    舊密碼 verify_password（不對回 400，不是 401）；新密碼 check_strength（422）；成功後撤銷其他 sessions。
    """
    raise not_ready("PATCH /api/auth/password", OWNER)


@router.post("/auth/password-reset", summary="忘記密碼：寄重設信")
@stub
def request_password_reset(body: PasswordResetIn, db: Session = Depends(get_db)):
    """忘記密碼：寄重設信

    POST /api/auth/password-reset

    ⚠️ 有沒有這個帳號都回 {ok: true, message: password_reset.GENERIC_MESSAGE}。
    找得到且 should_send()：new_token → 存 hash_token → mail_content → mailer.send_mail。寄信失敗記 log，回應照舊。
    """
    raise not_ready("POST /api/auth/password-reset", OWNER)


@router.post("/auth/password-reset/confirm", summary="用信裡的 token 設新密碼")
@stub
def confirm_password_reset(
    body: PasswordResetConfirmIn,
    reset_row=Depends(token_required()),
    db: Session = Depends(get_db),
):
    """用信裡的 token 設新密碼

    POST /api/auth/password-reset/confirm

    守衛已經驗過 token（row 就是那一列）。check_strength → 改 password_hash → row.used_at = now → 撤銷這個人所有 sessions，同一個交易。
    """
    raise not_ready("POST /api/auth/password-reset/confirm", OWNER)


@router.get("/auth/me/finance", summary="我的理財習慣")
@login_required
@stub
def get_finance(me: User, db: Session = Depends(get_db)):
    """我的理財習慣

    GET /api/auth/me/finance

    回 {finance: {style, goals, habits, note}, styles, goals, habits}（選項清單跟 data.js 一致）。
    """
    raise not_ready("GET /api/auth/me/finance", OWNER)


@router.put("/auth/me/finance", summary="改理財習慣")
@login_required
@stub
def set_finance(body: FinanceIn, me: User, db: Session = Depends(get_db)):
    """改理財習慣

    PUT /api/auth/me/finance

    只收清單裡的 id；note 用 profile.clean_note()（最多 200 字）。
    """
    raise not_ready("PUT /api/auth/me/finance", OWNER)


@router.post("/auth/verify-password", summary="重大操作前再確認一次密碼")
@login_required
@stub
def verify_password(body: VerifyPasswordIn, me: User, db: Session = Depends(get_db)):
    """重大操作前再確認一次密碼

    POST /api/auth/verify-password

    密碼不對回 400（不是 401——401 會讓前端以為 token 過期去續期）。
    ⚠️ 不發新 token；一定要做速率限制，否則是免費的密碼嘗試器。
    """
    raise not_ready("POST /api/auth/verify-password", OWNER)


@router.get("/auth/sessions", summary="登入中的裝置")
@login_required
@stub
def list_sessions(me: User, db: Session = Depends(get_db)):
    """登入中的裝置

    GET /api/auth/sessions

    回 {sessions: [{id, device, current, lastActiveAt}]}，只列沒撤銷、沒過期的。device 可以只回 userAgent，前端會自己整理。
    """
    raise not_ready("GET /api/auth/sessions", OWNER)


@router.put("/auth/me/avatar", summary="上傳大頭貼")
@login_required
@stub
def upload_avatar(body: AvatarIn, me: User, db: Session = Depends(get_db)):
    """上傳大頭貼

    PUT /api/auth/me/avatar

    images.from_data_uri → validate_avatar；存 users.avatar_bytes／avatar_mime（不存檔案系統）。
    """
    raise not_ready("PUT /api/auth/me/avatar", OWNER)


@router.delete("/auth/me/avatar", summary="移除大頭貼")
@login_required
@stub
def delete_avatar(me: User, db: Session = Depends(get_db)):
    """移除大頭貼

    DELETE /api/auth/me/avatar

    avatar_bytes、avatar_mime 設 NULL，回傳的 avatarUrl 是 null。
    """
    raise not_ready("DELETE /api/auth/me/avatar", OWNER)
