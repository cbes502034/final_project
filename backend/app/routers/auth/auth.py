"""
身分認證：註冊、登入、token、個人資料、忘記密碼。

領域：認證

===========================================================================
現在每一支都回 501（後端還沒做這一支），**守衛與主體模型已經接好**
===========================================================================
要做的事：刪掉那一支上面的 `@stub`，再把 `raise not_ready(...)` 那一行換成說明字串裡的第二步。
裝飾器、參數、檔案最上面的 import 都已經放好最終版本，不用動。
* 誰能打這一支：已經由守衛擋好（看 @xxx_required 或 Depends(...)），不用自己再判斷身分
* 前端送什麼、要回什麼：docs/02-前後端串接契約.md 同名的章節
* 增刪改查：app/toolkit/crud.py（find／get／save／remove／to_dict）
* 規則（誰可以、什麼時候不行）：app/toolkit/ 對應的模組，函式說明裡寫了拿來怎麼用
* 回傳的 id 要轉成字串（crud.to_dict 預設就會轉）

`python -m app.ownership` 會列出每個人還剩幾支（有 @stub 的算還沒做）。
"""

from __future__ import annotations

# 這個檔案裡每一支做完之後會用到的 import 都已經放好了。
# 還沒做的那幾支看起來「沒用到」是正常的，不要刪。
import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import catalog
from app.guards import guest_only, login_required, token_required, visible_scope
from app.models import (
    AuditLog, Family, FamilyMember, Group, GroupMember, Guardianship, PasswordReset, SavingsGoal, User, UserSession,
)
from app.routers._stub import not_ready, stub
from app.schemas.auth import AvatarIn, FinanceIn, LoginIn, LogoutIn, PasswordChangeIn, PasswordResetConfirmIn, PasswordResetIn, ProfilePatchIn, RefreshIn, RegisterIn, VerifyEmailIn, VerifyPasswordIn
from app.toolkit import account, crud, email_verify, errors, images, mailer, password_reset, passwords, period, profile, roles, security, theme, tokens
from app.toolkit.config import settings
from app.toolkit.db import get_db
from app.toolkit.deps import current_token_payload

router = APIRouter(tags=["身分認證"])
OWNER = "認證"


@router.post("/auth/register", status_code=201, summary="註冊：名字、email、密碼")
@guest_only
def register(body: RegisterIn, request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    """註冊：名字、email、密碼

    POST /api/auth/register

    【這支做什麼】
        用名字、email、密碼開一個帳號，寄一封驗證信（toolkit/email_verify.py）。**註冊完不登入**：
        前端回到登入頁，請他去收信；點了信裡的連結（POST /api/auth/verify-email）才登入，接著做個人化設定。
        ⚠️ 這是使用者要的流程（2026-10-20）：確認 email 是本人的之後才開始用——email 打錯的人當下就會發現，
           不會等到忘記密碼時才知道信永遠寄不到。沒點信就先登入的人，前端停在「請先到信箱點驗證連結」，可以重寄。
        ⚠️ 寄不出信的環境（本機開發沒設 BREVO_API_KEY、MAIL_FROM）沒有信可以點：直接算驗證過，回 verifySent false。
        新帳號沒有家庭（role 是 null）、主題是 paper、onboardedAt 是 null。
        ⚠️ email 在平台管理員名單裡（ADMIN_EMAILS＋toolkit/config.py 的 BUILTIN_ADMIN_EMAILS）：註冊當下就是平台管理員，
           不開帳本（管理員不記帳），登入後直接到平台管理頁。
        同時開一本「〈名字〉的帳本」：每一筆都要記在某本帳上，沒有帳本的新帳號連第一筆都記不了。
        ⚠️ 存款目標不在註冊時問：帶了 savingsGoal 回 400。默默吃掉的話，使用者會以為設好了。
        ⚠️ 同一個來源一小時內最多註冊 REGISTER_PER_HOUR 個（預設 5）：每註冊一個就寄一封信，
           大量註冊會把每天的寄信額度灌完，真的使用者就收不到驗證信跟重設密碼的信。

    【前端怎麼打】
        frontend/js/api.js 的 API.register({ name, email, password })
        註冊頁（#/register）送出時呼叫。前端檢查回應裡一定要有 user、verifySent；**不登入**，
        回到登入頁、email 先填好，上面顯示 message（「驗證信已寄到…」）。

    【誰能打】
        還沒登入的人。上面的 @guest_only 已經擋好了：
            帶著還有效的 access token → 400「你已經登入了，要換帳號請先登出」
            帶著壞掉或過期的 token → 當作沒登入，照樣可以打
        這支沒有 me 參數（本來就沒有人登入）。
        另外收一個 request（FastAPI 的 Request）：拿來源 IP，限制同一個來源註冊的數量。
        還有 background（FastAPI 的 BackgroundTasks）：驗證信放在回應送出去之後才寄。

    【請求主體】body 是 RegisterIn（app/schemas/auth.py）
        欄位         型別  必填  說明
        name         字串  是    1～30 字（FastAPI 先擋）；整理空白後不能是空的
        email        字串  是    存成小寫；格式不對回 422
        password     字串  是    passwords.check_strength 的規則：至少 8 個字、不能全是數字
        savingsGoal  數字  不收  帶了回 400（欄位留著只是為了講清楚原因）
        範例：{"name": "王大明", "email": "Daming@Wang.tw", "password": "abcd1234"}

    【成功回應】狀態碼 201
        {"verifySent": true, "message": "驗證信已寄到 daming@wang.tw，點信裡的按鈕就會接著開始設定",
         "user": {"id": "3", "name": "王大明", "email": "daming@wang.tw", "role": null, "familyId": null,
                  "avatar": "明", "avatarUrl": null, "age": null, "birthYear": null, "joined": "2026-09-17",
                  "theme": "paper", "onboardedAt": null, "savingsGoal": 0, "isPlatformAdmin": false,
                  "emailVerified": false}}
        · **沒有 token**：註冊完不登入，點了驗證信的連結才登入
        · 寄不出信的環境：verifySent false、message「帳號建好了，請登入」、emailVerified true
        · avatar 是名字的最後一個字

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                            detail
        400     帶了 savingsGoal                    存款目標不在註冊時設定，註冊完的個人化設定會問
        400     已經登入了還來註冊                  你已經登入了，要換帳號請先登出（守衛回）
        409     email 已經註冊過（大小寫不同也算）  這個 email 已經註冊過了
        422     名字整理完是空的                    請填名字
        422     email 格式不對                      email 格式看起來不對
        422     密碼太弱                            密碼至少要 8 個字（passwords 丟出來的那句話）
        429     同一個來源一小時內註冊太多個        這台裝置短時間內註冊太多帳號了，請一小時後再試
        ⚠️ 已經註冊過要回 409（跟現有資料衝突），不是 422。

    【會用到的資料表】
        表        讀／寫  用來做什麼
        users          讀＋寫  email 有沒有人用；新增帳號（只存密碼雜湊；email_verify_sent_at 記下寄驗證信的時間）
        groups         寫      第一本帳本「〈名字〉的帳本」
        group_members  寫      自己是那本帳的成員
        security_events  讀＋寫  這個來源一小時內註冊了幾個；註冊成功記一筆 register

    【每一步用的工具與資料庫方法】
        步驟     呼叫                                        做什麼
        2 email  password_reset.normalize_email(body.email)  去空白、轉小寫、檢查格式；不對丟 ValueError
                 crud.exists(User, {"email": email}, db=db)  有沒有人用過
        3 密碼   passwords.hash_password(body.password)      先檢查強度（太弱丟 WeakPassword），再算雜湊
          限量   security.source_of(request)                 來源 IP（Render 前面有代理，不能用 request.client.host）
                 security.register_blocked(ip, db=db)        太多了回要給使用者看的話（第一次擋下時記一筆 register_limited）
        4 帳本   crud.save(Group, {"name": …, "color": catalog.GROUP_COLORS[0], "created_by": user.id, "personal_owner_id": user.id, "kind": "standing"}, db=db)
                 crud.save(GroupMember, {"group_id": group.id, "user_id": user.id}, db=db)  自己加進去
        4 寄信   mailer.is_configured()                      寄得出信嗎？寄不出（本機開發）就直接算驗證過
        5 記錄   security.record("register", db=db, user_id=…, ip=ip)  記一筆，下一次數得到
                 db.commit()                                 帳號、帳本、紀錄一起寫進去（不建 sessions：不登入）
        6 驗證信 email_verify.make_token(user.id, email)     簽一張驗證權杖（EMAIL_VERIFY_MINUTES 分鐘有效，預設 24 小時）
                 email_verify.verify_link(settings.app_base_url, 權杖)  <前端網址>/#/verify/<權杖>
                 email_verify.mail_content(name, 連結)       回傳（主旨, 純文字, HTML），名字已經 escape
                 background.add_task(send)                   回應送出去之後才寄；寄不出去只記 log

    【寫法步驟】
        1. 帶了 savingsGoal → 400
        2. 整理名字（422）、email（422）；email 用過 → 409
        3. 密碼檢查強度、算雜湊（422）；這個來源一小時內註冊太多個 → 429
        4. 新增帳號：主題 paper、onboarded_at 留 NULL；寄得出信就記下 email_verify_sent_at（重寄的冷卻從這裡算），
           寄不出信就直接填 email_verified_at；開一本「〈名字〉的帳本」（名字最多取 17 字，帳本名最多 20 字）
        5. 記一筆 register，db.commit()（**不登入**，不建 sessions）
        6. 寄得出信才背景寄驗證信
        7. 回傳 verifySent、message 與 user（新帳號的欄位都是固定的：沒有家庭、沒有大頭貼、目標 0）

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            import logging
            import uuid
            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import guest_only, login_required, token_required, visible_scope
            from app.models import (
                AuditLog, Family, FamilyMember, Group, GroupMember, Guardianship, PasswordReset, SavingsGoal, User, UserSession,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.auth import AvatarIn, FinanceIn, LoginIn, LogoutIn, PasswordChangeIn, PasswordResetConfirmIn, PasswordResetIn, ProfilePatchIn, RefreshIn, RegisterIn, VerifyEmailIn, VerifyPasswordIn
            from app.toolkit import account, crud, email_verify, errors, images, mailer, password_reset, passwords, period, profile, roles, security, theme, tokens
            from app.toolkit.config import settings
            from app.toolkit.db import get_db
            from app.toolkit.deps import current_token_payload

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 存款目標不在註冊時問：帶了就講清楚，不要默默吃掉
            if body.savingsGoal is not None:
                raise errors.bad_request("存款目標不在註冊時設定，註冊完的個人化設定會問")

            # 2. 名字、email（一律小寫）、有沒有註冊過
            name = " ".join(body.name.split())
            if not name:
                raise errors.unprocessable("請填名字")
            try:
                email = password_reset.normalize_email(body.email)
            except ValueError as exc:
                raise errors.unprocessable(str(exc)) from None
            if crud.exists(User, {"email": email}, db=db):
                raise errors.conflict("這個 email 已經註冊過了")

            # 3. 密碼：檢查強度，只存雜湊
            try:
                hashed = passwords.hash_password(body.password)
            except passwords.WeakPassword as exc:
                raise errors.unprocessable(str(exc)) from None

            #    同一個來源一小時內註冊太多個 → 429（大量註冊會把每天的寄信額度灌完，真的使用者就收不到信）
            ip = security.source_of(request)
            blocked = security.register_blocked(ip, db=db)
            if blocked:
                db.commit()                                     # 第一次被擋時記的那一筆要留著
                raise HTTPException(status_code=429, detail=blocked)

            # 4. 新增帳號（onboarded_at 是 NULL：點了驗證信、登入之後，前端會帶去個人化設定）
            #    寄不出信的環境（本機開發沒設 BREVO_API_KEY）沒有信可以點，直接算驗證過，不然人會卡在那一步
            now = datetime.now(timezone.utc)
            can_mail = mailer.is_configured()
            admin = email in settings.admin_email_list          # ADMIN_EMAILS 或內建的管理員 email：註冊當下就是平台管理員
            user = crud.save(User, {"email": email, "password_hash": hashed, "display_name": name, "theme": "paper",
                                    "is_platform_admin": admin,
                                    "email_verify_sent_at": now if can_mail else None,
                                    "email_verified_at": None if can_mail else now}, db=db)

            #    順便開一本自己的帳本：每一筆都要記在某本帳上，沒有帳本的新帳號連第一筆都記不了（平台管理員不記帳，不開）
            if not admin:
                group = crud.save(Group, {"name": name[:17] + "的帳本", "color": catalog.GROUP_COLORS[0],
                                          "created_by": user.id, "personal_owner_id": user.id, "kind": "standing"}, db=db)
                crud.save(GroupMember, {"group_id": group.id, "user_id": user.id}, db=db)

            # 5. 註冊完**不登入**：記一筆（數「同一個來源註冊了幾個」用），寫進去
            security.record("register", db=db, user_id=user.id, ip=ip)
            db.commit()

            # 6. 寄驗證信（背景寄，回應不等 Brevo）：點信裡的連結才登入、接著做個人化設定；寄不出去只記 log，帳號照樣建好
            if can_mail:
                subject, text, html = email_verify.mail_content(
                    name, email_verify.verify_link(settings.app_base_url, email_verify.make_token(user.id, email)))

                def send():
                    try:
                        mailer.send_mail(email, subject, text, html, to_name=name)
                    except (mailer.MailNotConfigured, mailer.MailError) as exc:
                        logging.getLogger("fambudget").warning("驗證信寄不出去：%s", exc)

                background.add_task(send)

            # 7. 回傳使用者與下一步（沒有 token：前端回到登入頁，請他去收信）
            return {
                "verifySent": can_mail,
                "message": ("驗證信已寄到 %s，點信裡的按鈕就會接著開始設定" % email) if can_mail else "帳號建好了，請登入",
                "user": {
                    "id": str(user.id),
                    "name": user.display_name,
                    "email": user.email,
                    "role": None,
                    "familyId": None,
                    "avatar": name[-1:],
                    "avatarUrl": None,
                    "age": None,
                    "birthYear": None,
                    "joined": user.created_at.date().isoformat(),
                    "theme": "paper",
                    "onboardedAt": None,
                    "savingsGoal": 0,
                    "isPlatformAdmin": admin,
                    "emailVerified": not can_mail,
                },
            }

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/auth/register
        3. 這支要「沒登入」才能打：不要按 Authorize（按了會回 400）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               {"name": "王大明", "email": "Daming@Wang.tw", "password": "abcd1234"}  → 201，email 變小寫、onboardedAt 是 null
               同一個 email 換大寫再註冊  → 409
               帶 "savingsGoal": 1000     → 400
               password 填 "1234"         → 422
           backend/.env 填了 BREVO_API_KEY 與 MAIL_FROM 的話，信箱會收到「確認你的家庭記帳 email」，回應沒有 token
        5. 點信裡的按鈕（或 POST /api/auth/verify-email 送信裡的權杖）→ 這時才拿到 token
        6. 前端改成連你的後端（frontend/index.html 的 api-base），註冊頁註冊一個帳號：回到登入頁、顯示「驗證信已寄到…」；
           點信裡的按鈕才登入，接著進到「個人化設定」
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "register and 你的"，要全部通過
    """
    # 1. 存款目標不在註冊時問：帶了就講清楚，不要默默吃掉
    if body.savingsGoal is not None:
        raise errors.bad_request("存款目標不在註冊時設定，註冊完的個人化設定會問")

    # 2. 名字、email（一律小寫）、有沒有註冊過
    name = " ".join(body.name.split())
    if not name:
        raise errors.unprocessable("請填名字")
    try:
        email = password_reset.normalize_email(body.email)
    except ValueError as exc:
        raise errors.unprocessable(str(exc)) from None
    if crud.exists(User, {"email": email}, db=db):
        raise errors.conflict("這個 email 已經註冊過了")

    # 3. 密碼：檢查強度，只存雜湊
    try:
        hashed = passwords.hash_password(body.password)
    except passwords.WeakPassword as exc:
        raise errors.unprocessable(str(exc)) from None

    #    同一個來源一小時內註冊太多個 → 429（大量註冊會把每天的寄信額度灌完，真的使用者就收不到信）
    ip = security.source_of(request)
    blocked = security.register_blocked(ip, db=db)
    if blocked:
        db.commit()                                     # 第一次被擋時記的那一筆要留著
        raise HTTPException(status_code=429, detail=blocked)

    # 4. 新增帳號（onboarded_at 是 NULL：點了驗證信、登入之後，前端會帶去個人化設定）
    #    寄不出信的環境（本機開發沒設 BREVO_API_KEY）沒有信可以點，直接算驗證過，不然人會卡在那一步
    now = datetime.now(timezone.utc)
    can_mail = mailer.is_configured()
    admin = email in settings.admin_email_list          # ADMIN_EMAILS 或內建的管理員 email：註冊當下就是平台管理員
    user = crud.save(User, {"email": email, "password_hash": hashed, "display_name": name, "theme": "paper",
                            "is_platform_admin": admin,
                            "email_verify_sent_at": now if can_mail else None,
                            "email_verified_at": None if can_mail else now}, db=db)

    #    順便開一本自己的帳本：每一筆都要記在某本帳上，沒有帳本的新帳號連第一筆都記不了（平台管理員不記帳，不開）
    if not admin:
        group = crud.save(Group, {"name": name[:17] + "的帳本", "color": catalog.GROUP_COLORS[0],
                                  "created_by": user.id, "personal_owner_id": user.id, "kind": "standing"}, db=db)
        crud.save(GroupMember, {"group_id": group.id, "user_id": user.id}, db=db)

    # 5. 註冊完**不登入**：記一筆（數「同一個來源註冊了幾個」用），寫進去
    security.record("register", db=db, user_id=user.id, ip=ip)
    db.commit()

    # 6. 寄驗證信（背景寄，回應不等 Brevo）：點信裡的連結才登入、接著做個人化設定；寄不出去只記 log，帳號照樣建好
    if can_mail:
        subject, text, html = email_verify.mail_content(
            name, email_verify.verify_link(settings.app_base_url, email_verify.make_token(user.id, email)))

        def send():
            try:
                mailer.send_mail(email, subject, text, html, to_name=name)
            except (mailer.MailNotConfigured, mailer.MailError) as exc:
                logging.getLogger("fambudget").warning("驗證信寄不出去：%s", exc)

        background.add_task(send)

    # 7. 回傳使用者與下一步（沒有 token：前端回到登入頁，請他去收信）
    return {
        "verifySent": can_mail,
        "message": ("驗證信已寄到 %s，點信裡的按鈕就會接著開始設定" % email) if can_mail else "帳號建好了，請登入",
        "user": {
            "id": str(user.id),
            "name": user.display_name,
            "email": user.email,
            "role": None,
            "familyId": None,
            "avatar": name[-1:],
            "avatarUrl": None,
            "age": None,
            "birthYear": None,
            "joined": user.created_at.date().isoformat(),
            "theme": "paper",
            "onboardedAt": None,
            "savingsGoal": 0,
            "isPlatformAdmin": admin,
            "emailVerified": not can_mail,
        },
    }


@router.post("/auth/login", summary="登入")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    """登入

    POST /api/auth/login

    【這支做什麼】
        email ＋ 密碼換兩張 token：access token（30 分鐘，每個請求都帶）與 refresh token（14 天，只拿來換新的）。
        ⚠️ 「沒有這個帳號」跟「密碼錯」回同一句話、同一個 401：分開講等於送出一支帳號列舉工具。
        ⚠️ 查無此人也要跑一次雜湊比對：不然「不存在」會比「密碼錯」快很多，用回應時間一樣問得出來。
        ⚠️ 密碼對了才看停權：順序反過來，任何人拿一個 email 亂打密碼，就能試出「這個帳號是不是被停權了」。
        ⚠️ 防暴力猜密碼：同一個 email 15 分鐘內錯 5 次（LOGIN_MAX_FAILURES）就鎖 15 分鐘，這段時間連對的密碼也不收；
           同一個來源錯 20 次（不管哪個帳號，撞庫）也鎖 15 分鐘。**帳號不存在也一樣算、一樣鎖**——
           只鎖存在的帳號的話，「會不會被鎖」就洩漏了帳號在不在。每一次失敗都記進 security_events，平台管理頁看得到。

    【前端怎麼打】
        frontend/js/api.js 的 API.login({ email, password })
        登入頁（#/login）送出時呼叫。前端檢查回應裡一定要有 user，並把兩張 token 存進 localStorage。

    【誰能打】
        任何人都能打，不用登入（上面沒有守衛）。
        另外收一個 request（FastAPI 的 Request）：要記下這一台的瀏覽器（User-Agent）與 IP 的雜湊；
        IP 用 security.source_of(request) 拿（Render 前面有代理，request.client.host 是代理的位址）。

    【請求主體】body 是 LoginIn（app/schemas/auth.py）
        欄位      型別  必填  說明
        email     字串  是    大小寫不拘（比對前轉小寫）
        password  字串  是    明碼，只拿來比對雜湊
        範例：{"email": "daming@wang.tw", "password": "abcd1234"}

    【成功回應】狀態碼 200
        {"accessToken": "eyJ…", "refreshToken": "eyJ…", "expiresIn": 1800,
         "user": {"id": "3", "name": "王大明", "email": "daming@wang.tw", "role": "parent", "familyId": "2",
                  "avatar": "明", "avatarUrl": null, "age": 52, "birthYear": 1974, "joined": "2026-01-05",
                  "theme": "sky", "onboardedAt": "2026-01-05T01:00:00+00:00", "savingsGoal": 20000,
                  "isPlatformAdmin": false}}
        · user 的形狀跟 GET /api/auth/me 的 user 一樣
        · savingsGoal = 最新一筆「整體」存款目標，沒設過是 0

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                detail
        401     沒有這個帳號、或密碼錯  email 或密碼不對
        403     密碼對，但帳號被停權    這個帳號已被停權：（停權理由）
        403     密碼對，但還沒驗證信箱  這個帳號還沒驗證信箱：請先到信箱點驗證連結再登入（平台管理員不擋；沒設定寄信服務的環境也不擋）
        429     同一個 email 錯太多次   密碼錯太多次了，請 15 分鐘後再試
        429     同一個來源錯太多次      這台裝置登入失敗太多次了，請 15 分鐘後再試

    【會用到的資料表】
        表              讀／寫  用來做什麼
        users           讀＋寫  找人、比對密碼；記 last_login_at
        sessions        寫      這一台的登入工作階段
        family_members  讀      角色與家庭
        savings_goals   讀      目前的整體存款目標
        security_events 讀＋寫  數最近錯了幾次、有沒有被鎖；錯一次記一筆 login_failed

    【每一步用的工具與資料庫方法】
        步驟      呼叫                                                           做什麼
        1 鎖住    security.source_of(request)                                    來源 IP（X-Forwarded-For 的第一個）
                  security.login_blocked(email, ip, db=db)                       被鎖住回要給使用者看的話，沒有回 None
                  HTTPException(status_code=429, detail=…)                       errors 裡沒有 429，直接用 FastAPI 的
          找人    crud.get(User, where={"email": …}, db=db)                      找不到回 None
        2 比對    passwords.verify_password(明碼, 雜湊)                          對回 True；雜湊壞掉也只回 False，不會爆
                  一組固定的假雜湊                                               查無此人時拿它比對，花的時間跟真的比對一樣
          記錯    security.login_failed(email, ip, db=db, user_id=…)             記一筆；次數到了順便記 login_locked（開始鎖）
                  db.commit()                                                    要在丟 401 之前 commit，不然這一次不會被算到
        3 停權    roles.require_active(user.suspended_at)                        停權中丟 Forbidden（PermissionError 的一種）
        4 登入    tokens.make_refresh_token／fingerprint／make_access_token      同註冊
                  crud.save(User, {"id": user.id, "last_login_at": now}, db=db)  記最後登入時間
        5 使用者  crud.get(FamilyMember, where={"user_id": …, "status": "active"}, db=db)  角色與家庭（沒有家庭是 None）
                  crud.get(SavingsGoal, where={…, "group_id__isnull": True}, fields="goal_amount", order_by="-id", db=db)  最新的整體目標金額
                  images.to_data_uri(user.avatar_bytes, user.avatar_mime)        有大頭貼才轉

    【寫法步驟】
        1. email 轉小寫；被鎖住 → 429（這時候連比對都不做）；找人
        2. 有沒有人都跑一次 verify_password；沒這個人或密碼錯 → 記一筆失敗、commit，同一句 401
        3. 停權 → 403（附理由）
        4. 新增一列 sessions、記 last_login_at，db.commit()
        5. 查角色、家庭、存款目標，組成 user，跟兩張 token 一起回傳

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            import logging
            import uuid
            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import guest_only, login_required, token_required, visible_scope
            from app.models import (
                AuditLog, Family, FamilyMember, Group, GroupMember, Guardianship, PasswordReset, SavingsGoal, User, UserSession,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.auth import AvatarIn, FinanceIn, LoginIn, LogoutIn, PasswordChangeIn, PasswordResetConfirmIn, PasswordResetIn, ProfilePatchIn, RefreshIn, RegisterIn, VerifyEmailIn, VerifyPasswordIn
            from app.toolkit import account, crud, email_verify, errors, images, mailer, password_reset, passwords, period, profile, roles, security, theme, tokens
            from app.toolkit.config import settings
            from app.toolkit.db import get_db
            from app.toolkit.deps import current_token_payload

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 先看有沒有被鎖住：同一個 email 或同一個來源錯太多次（帳號存不存在都一樣算，見 toolkit/security.py）
            email = body.email.strip().lower()
            ip = security.source_of(request)
            blocked = security.login_blocked(email, ip, db=db)
            if blocked:
                raise HTTPException(status_code=429, detail=blocked)

            #    找人（email 一律小寫比對）
            user = crud.get(User, where={"email": email}, db=db)

            # 2. 比對密碼。查無此人也跑一次（拿一組沒有人用的雜湊），兩種情況花的時間才會一樣
            dummy = "$2b$12$CXOgrZ2hWSUTEYKsghc3uuIaM/ekXB01qlBO04c4x/4cP9.xYOr3G"
            ok = passwords.verify_password(body.password, user.password_hash if user else dummy)
            if user is None or not ok:
                # 記一筆失敗（次數到了就開始鎖）。先 commit 再回 401：不然請求一結束這筆就跟著被丟掉
                security.login_failed(email, ip, db=db, user_id=user.id if user else None)
                db.commit()
                raise errors.unauthorized("email 或密碼不對")

            # 3. 密碼對了才看停權
            try:
                roles.require_active(user.suspended_at)
            except PermissionError:
                raise errors.forbidden("這個帳號已被停權：" + (user.suspended_reason or "違反使用規範")) from None

            # 還沒點驗證信的人不能登入（寄得出信的環境才擋；平台管理員不擋，不然沒人進得了管理頁）
            if user.email_verified_at is None and not user.is_platform_admin and mailer.is_configured():
                raise errors.forbidden("這個帳號還沒驗證信箱：請先到信箱點驗證連結再登入（找不到信的話看一下垃圾信件）")

            # 4. 寫一列 sessions（只存 refresh token 的指紋），記最後登入時間
            now = datetime.now(timezone.utc)
            refresh, expires = tokens.make_refresh_token(user.id)
            session = crud.save(UserSession, {
                "user_id": user.id,
                "refresh_token_hash": tokens.fingerprint(refresh),
                "user_agent": request.headers.get("user-agent", "")[:300],
                "ip_hash": tokens.fingerprint(ip) if ip else None,
                "expires_at": expires,
                "last_seen_at": now,
            }, db=db)
            crud.save(User, {"id": user.id, "last_login_at": now}, db=db)
            db.commit()

            # 5. 回傳 token 與使用者（形狀同 GET /api/auth/me 的 user）
            fm = crud.get(FamilyMember, where={"user_id": user.id, "status": "active"}, db=db)
            goal = crud.get(SavingsGoal, where={"user_id": user.id, "group_id__isnull": True},
                            fields="goal_amount", order_by="-id", db=db)
            this_year = datetime.now(timezone(timedelta(hours=8))).year
            onboarded = user.onboarded_at
            if onboarded is not None and onboarded.tzinfo is None:
                onboarded = onboarded.replace(tzinfo=timezone.utc)          # SQLite 讀回來沒有時區
            return {
                "accessToken": tokens.make_access_token(user.id, extra={"sid": str(session.id)}),
                "refreshToken": refresh,
                "expiresIn": settings.access_token_minutes * 60,
                "user": {
                    "id": str(user.id),
                    "name": user.display_name,
                    "email": user.email,
                    "role": fm.role if fm else None,
                    "familyId": str(fm.family_id) if fm else None,
                    "avatar": user.display_name[-1:],
                    "avatarUrl": images.to_data_uri(user.avatar_bytes, user.avatar_mime) if user.avatar_bytes else None,
                    "age": this_year - user.birth_year if user.birth_year else None,
                    "birthYear": user.birth_year,
                    "joined": user.created_at.date().isoformat(),
                    "theme": user.theme or "paper",
                    "onboardedAt": onboarded.isoformat() if onboarded else None,
                    "savingsGoal": goal or 0,
                    "isPlatformAdmin": user.is_platform_admin,
                },
            }

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/auth/login
        3. 這支不用登入，不用按 Authorize
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               正確的 email（故意打大寫）＋密碼  → 200，有兩張 token
               密碼錯                            → 401「email 或密碼不對」
               沒註冊過的 email                  → 401，而且是同一句話
               被停權的帳號、密碼正確            → 403，附停權理由
               同一個 email 連續錯 5 次之後      → 429，就算打對也一樣（15 分鐘後才解開）
        5. 資料庫 sessions 多一列，refresh_token_hash 不是 token 原文
        6. 前端改成連你的後端（frontend/index.html 的 api-base），登入頁登入，進到總覽（還沒走個人化設定的會先到設定頁）
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "login and 你的"，要全部通過
    """
    # 1. 先看有沒有被鎖住：同一個 email 或同一個來源錯太多次（帳號存不存在都一樣算，見 toolkit/security.py）
    email = body.email.strip().lower()
    ip = security.source_of(request)
    blocked = security.login_blocked(email, ip, db=db)
    if blocked:
        raise HTTPException(status_code=429, detail=blocked)

    #    找人（email 一律小寫比對）
    user = crud.get(User, where={"email": email}, db=db)

    # 2. 比對密碼。查無此人也跑一次（拿一組沒有人用的雜湊），兩種情況花的時間才會一樣
    dummy = "$2b$12$CXOgrZ2hWSUTEYKsghc3uuIaM/ekXB01qlBO04c4x/4cP9.xYOr3G"
    ok = passwords.verify_password(body.password, user.password_hash if user else dummy)
    if user is None or not ok:
        # 記一筆失敗（次數到了就開始鎖）。先 commit 再回 401：不然請求一結束這筆就跟著被丟掉
        security.login_failed(email, ip, db=db, user_id=user.id if user else None)
        db.commit()
        raise errors.unauthorized("email 或密碼不對")

    # 3. 密碼對了才看停權
    try:
        roles.require_active(user.suspended_at)
    except PermissionError:
        raise errors.forbidden("這個帳號已被停權：" + (user.suspended_reason or "違反使用規範")) from None

    # 還沒點驗證信的人不能登入（寄得出信的環境才擋；平台管理員不擋，不然沒人進得了管理頁）
    if user.email_verified_at is None and not user.is_platform_admin and mailer.is_configured():
        raise errors.forbidden("這個帳號還沒驗證信箱：請先到信箱點驗證連結再登入（找不到信的話看一下垃圾信件）")

    # 4. 寫一列 sessions（只存 refresh token 的指紋），記最後登入時間
    now = datetime.now(timezone.utc)
    refresh, expires = tokens.make_refresh_token(user.id)
    session = crud.save(UserSession, {
        "user_id": user.id,
        "refresh_token_hash": tokens.fingerprint(refresh),
        "user_agent": request.headers.get("user-agent", "")[:300],
        "ip_hash": tokens.fingerprint(ip) if ip else None,
        "expires_at": expires,
        "last_seen_at": now,
    }, db=db)
    crud.save(User, {"id": user.id, "last_login_at": now}, db=db)
    db.commit()

    # 5. 回傳 token 與使用者（形狀同 GET /api/auth/me 的 user）
    fm = crud.get(FamilyMember, where={"user_id": user.id, "status": "active"}, db=db)
    goal = crud.get(SavingsGoal, where={"user_id": user.id, "group_id__isnull": True},
                    fields="goal_amount", order_by="-id", db=db)
    this_year = datetime.now(timezone(timedelta(hours=8))).year
    onboarded = user.onboarded_at
    if onboarded is not None and onboarded.tzinfo is None:
        onboarded = onboarded.replace(tzinfo=timezone.utc)          # SQLite 讀回來沒有時區
    return {
        "accessToken": tokens.make_access_token(user.id, extra={"sid": str(session.id)}),
        "refreshToken": refresh,
        "expiresIn": settings.access_token_minutes * 60,
        "user": {
            "id": str(user.id),
            "name": user.display_name,
            "email": user.email,
            "role": fm.role if fm else None,
            "familyId": str(fm.family_id) if fm else None,
            "avatar": user.display_name[-1:],
            "avatarUrl": images.to_data_uri(user.avatar_bytes, user.avatar_mime) if user.avatar_bytes else None,
            "age": this_year - user.birth_year if user.birth_year else None,
            "birthYear": user.birth_year,
            "joined": user.created_at.date().isoformat(),
            "theme": user.theme or "paper",
            "onboardedAt": onboarded.isoformat() if onboarded else None,
            "savingsGoal": goal or 0,
            "isPlatformAdmin": user.is_platform_admin,
        },
    }


@router.post("/auth/refresh", summary="用 refresh token 換新的 access token")
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    """用 refresh token 換新的 access token

    POST /api/auth/refresh

    【這支做什麼】
        access token 過期時，前端拿 refresh token 來換一組新的（前端的 req() 收到 401 會自動打，畫面程式不會直接叫）。
        ⚠️ 這支不驗 access token：它存在的意義就是 access token 已經死了。
        ⚠️ refresh token 要輪替：換發新的，舊的同時作廢（sessions 那一列換成新的指紋）。
           不輪替的話，一張外洩的 refresh token 可以用滿 14 天。
        ⚠️ 同一張舊 token 重送（網路抖一下）：回 401 就好，不要把這個人的所有 session 都撤銷。

    【前端怎麼打】
        frontend/js/api.js 的 doRefresh()（內部用，FN 裡沒有這一支）
        同時只會打一次；換到新的就存起來，再把剛才失敗的請求重送一次。換不到就清掉 token、回登入頁。

    【誰能打】
        任何人都能打，不用登入（上面沒有守衛）。
        token 本身就是身分：簽名、型別、期限、sessions 裡找不找得到，全部要檢查。

    【請求主體】body 是 RefreshIn（app/schemas/auth.py）
        欄位          型別  必填  說明
        refreshToken  字串  是    登入或上次換發拿到的 refresh token
        範例：{"refreshToken": "eyJ…"}

    【成功回應】狀態碼 200
        {"accessToken": "eyJ…", "refreshToken": "eyJ…（新的）", "expiresIn": 1800}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候        detail
        401     簽名不對、過期、拿 access token 來換、sessions 找不到、已撤銷、已過期  登入已經過期，請重新登入
        403     這個人被停權了  這個帳號已被停權：（停權理由）
        · 401 的各種原因回同一句話：不告訴攻擊者到底哪裡不對。

    【會用到的資料表】
        表        讀／寫  用來做什麼
        sessions  讀＋寫  用指紋找這一台；換成新的指紋與期限
        users     讀      人還在嗎、有沒有被停權

    【每一步用的工具與資料庫方法】
        步驟          呼叫                                    做什麼
        1 驗 token    tokens.read_refresh_token(token)        簽名、期限、型別；不對丟 TokenError（過期、型別錯都是它的子類別）
        2 找 session  crud.get(UserSession, where={"refresh_token_hash": 指紋, "revoked_at__isnull": True, "expires_at__gt": now}, for_update=True, db=db)  找得到、沒撤銷、沒過期；for_update 先鎖住這一列，兩個請求同時換只有一個會成功
                      payload["sub"]                          token 裡的使用者 id（字串）
        3 人          crud.get(User, session.user_id, db=db)  用主鍵拿
        4 輪替        crud.save(UserSession, {"id": session.id, "refresh_token_hash": 新指紋, …}, db=db)  同一台沿用同一列，舊的指紋被換掉 = 舊 token 作廢
                      db.commit()                             寫進去

    【寫法步驟】
        1. read_refresh_token（401）
        2. 用指紋找還有效的 session，而且 user_id 要跟 token 裡的一樣（401）
        3. 人不見了 → 401；被停權 → 403
        4. 發新的 refresh token，那一列換成新的指紋、新的期限、記 last_seen_at，db.commit()
        5. 回傳新的兩張 token（access token 一樣帶 sid）

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            import logging
            import uuid
            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import guest_only, login_required, token_required, visible_scope
            from app.models import (
                AuditLog, Family, FamilyMember, Group, GroupMember, Guardianship, PasswordReset, SavingsGoal, User, UserSession,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.auth import AvatarIn, FinanceIn, LoginIn, LogoutIn, PasswordChangeIn, PasswordResetConfirmIn, PasswordResetIn, ProfilePatchIn, RefreshIn, RegisterIn, VerifyEmailIn, VerifyPasswordIn
            from app.toolkit import account, crud, email_verify, errors, images, mailer, password_reset, passwords, period, profile, roles, security, theme, tokens
            from app.toolkit.config import settings
            from app.toolkit.db import get_db
            from app.toolkit.deps import current_token_payload

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            expired = errors.unauthorized("登入已經過期，請重新登入")

            # 1. 驗 refresh token 的簽名、型別、期限
            try:
                payload = tokens.read_refresh_token(body.refreshToken)
            except tokens.TokenError:
                raise expired from None

            # 2. 用指紋找還有效的那一台（先鎖住，兩個請求同時換只有一個會成功）
            now = datetime.now(timezone.utc)
            session = crud.get(UserSession, where={
                "refresh_token_hash": tokens.fingerprint(body.refreshToken),
                "revoked_at__isnull": True,
                "expires_at__gt": now,
            }, for_update=True, db=db)
            if session is None or str(session.user_id) != payload["sub"]:
                raise expired

            # 3. 人還在、沒被停權
            user = crud.get(User, session.user_id, db=db)
            if user is None:
                raise expired
            if user.suspended_at is not None:
                raise errors.forbidden("這個帳號已被停權：" + (user.suspended_reason or "違反使用規範"))

            # 4. 輪替：同一台沿用同一列，換成新的指紋（舊的 token 就此作廢）
            new_refresh, expires = tokens.make_refresh_token(user.id)
            crud.save(UserSession, {"id": session.id, "refresh_token_hash": tokens.fingerprint(new_refresh),
                                    "expires_at": expires, "last_seen_at": now}, db=db)
            db.commit()

            # 5. 回傳新的兩張 token
            return {
                "accessToken": tokens.make_access_token(user.id, extra={"sid": str(session.id)}),
                "refreshToken": new_refresh,
                "expiresIn": settings.access_token_minutes * 60,
            }

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/auth/refresh
        3. 這支不用登入，不用按 Authorize
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               用登入拿到的 refreshToken                    → 200，拿到新的一組
               同一張舊的再換一次                           → 401
               拿 accessToken 來換                          → 401
               先登出（POST /api/auth/logout），再用那張換  → 401
        5. 前端改成連你的後端（frontend/index.html 的 api-base），把 localStorage 裡的 accessToken 改壞，重新整理——畫面照常，Network 裡看得到一次 /refresh
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "refresh and 你的"，要全部通過
    """
    expired = errors.unauthorized("登入已經過期，請重新登入")

    # 1. 驗 refresh token 的簽名、型別、期限
    try:
        payload = tokens.read_refresh_token(body.refreshToken)
    except tokens.TokenError:
        raise expired from None

    # 2. 用指紋找還有效的那一台（先鎖住，兩個請求同時換只有一個會成功）
    now = datetime.now(timezone.utc)
    session = crud.get(UserSession, where={
        "refresh_token_hash": tokens.fingerprint(body.refreshToken),
        "revoked_at__isnull": True,
        "expires_at__gt": now,
    }, for_update=True, db=db)
    if session is None or str(session.user_id) != payload["sub"]:
        raise expired

    # 3. 人還在、沒被停權
    user = crud.get(User, session.user_id, db=db)
    if user is None:
        raise expired
    if user.suspended_at is not None:
        raise errors.forbidden("這個帳號已被停權：" + (user.suspended_reason or "違反使用規範"))

    # 4. 輪替：同一台沿用同一列，換成新的指紋（舊的 token 就此作廢）
    new_refresh, expires = tokens.make_refresh_token(user.id)
    crud.save(UserSession, {"id": session.id, "refresh_token_hash": tokens.fingerprint(new_refresh),
                            "expires_at": expires, "last_seen_at": now}, db=db)
    db.commit()

    # 5. 回傳新的兩張 token
    return {
        "accessToken": tokens.make_access_token(user.id, extra={"sid": str(session.id)}),
        "refreshToken": new_refresh,
        "expiresIn": settings.access_token_minutes * 60,
    }


@router.post("/auth/logout", summary="登出（撤銷這一台的 refresh token）")
@login_required
def logout(
    body: LogoutIn,
    me: User,
    payload: dict = Depends(current_token_payload),
    db: Session = Depends(get_db),
):
    """登出（撤銷這一台的 refresh token）

    POST /api/auth/logout

    【這支做什麼】
        登出這一台：把這一台的 sessions 設 revoked_at（不刪列），之後那張 refresh token 就換不到新的了。
        ⚠️ 要做成冪等：重複登出、token 已經失效都回成功——前端不管成不成功都會清掉本機的 token，
           使用者按了登出就一定要登出。
        access token 撤不掉，它會在 30 分鐘內自己過期；要立刻全部失效用 /api/auth/logout-all。

    【前端怎麼打】
        frontend/js/api.js 的 API.logout()，主體帶著本機的 refreshToken
        右上角帳號選單的「登出」。前端不看回應。

    【誰能打】
        登入、沒被停權就能打（平台管理員也可以）。上面的 @login_required 已經擋好了：
            沒登入、token 過期 → 401；被停權 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）
        另外收一個 payload=Depends(current_token_payload)：access token 解開後的內容，裡面的 sid 是這一台的 sessions.id。

    【請求主體】body 是 LogoutIn（app/schemas/auth.py）
        欄位          型別  必填  說明
        refreshToken  字串  否    帶了就撤銷這一張；沒帶就撤銷 access token 裡 sid 指的那一台
        範例：{"refreshToken": "eyJ…"}

    【成功回應】狀態碼 200
        {"ok": true}（找不到、已經撤銷過也一樣）

    【錯誤回應】
        只有守衛的 401／403。這支本身不回錯。

    【會用到的資料表】
        表        讀／寫  用來做什麼
        sessions  寫      設 revoked_at

    【每一步用的工具與資料庫方法】
        步驟      呼叫                                                           做什麼
        1 哪一台  tokens.fingerprint(body.refreshToken)                          用指紋找
                  uuid.UUID(payload["sid"])                                      sid 字串轉回 UUID，才能跟 sessions.id 比
        2 撤銷    crud.save(UserSession, {"revoked_at": now}, where={…}, db=db)  有 where = 改所有符合的；找不到就改 0 列，不會出錯
                  db.commit()                                                    寫進去
        · where 裡一定帶 user_id = 我：拿別人的 refresh token 來也撤不掉別人的登入。

    【寫法步驟】
        1. 條件：我的、還沒撤銷的；再加上 refreshToken 的指紋，或 sid
        2. 兩個都沒有 → 直接回成功
        3. 設 revoked_at，db.commit()，回 {"ok": true}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            import logging
            import uuid
            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import guest_only, login_required, token_required, visible_scope
            from app.models import (
                AuditLog, Family, FamilyMember, Group, GroupMember, Guardianship, PasswordReset, SavingsGoal, User, UserSession,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.auth import AvatarIn, FinanceIn, LoginIn, LogoutIn, PasswordChangeIn, PasswordResetConfirmIn, PasswordResetIn, ProfilePatchIn, RefreshIn, RegisterIn, VerifyEmailIn, VerifyPasswordIn
            from app.toolkit import account, crud, email_verify, errors, images, mailer, password_reset, passwords, period, profile, roles, security, theme, tokens
            from app.toolkit.config import settings
            from app.toolkit.db import get_db
            from app.toolkit.deps import current_token_payload

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 要撤銷哪一台：帶了 refreshToken 用它的指紋，沒帶用 access token 裡的 sid
            where = {"user_id": me.id, "revoked_at__isnull": True}
            if body.refreshToken:
                where["refresh_token_hash"] = tokens.fingerprint(body.refreshToken)
            elif payload.get("sid"):
                where["id"] = uuid.UUID(payload["sid"])
            else:
                return {"ok": True}

            # 2. 設 revoked_at（不刪列）；找不到也當作成功，重複登出不要噴錯
            crud.save(UserSession, {"revoked_at": datetime.now(timezone.utc)}, where=where, db=db)
            db.commit()
            return {"ok": True}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/auth/logout
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               帶登入拿到的 refreshToken  → 200；再打一次 => 還是 200
               不帶主體（{}）             → 200，這一台的 session 被撤銷
        5. 用那張 refreshToken 打 POST /api/auth/refresh → 401
        6. 前端改成連你的後端（frontend/index.html 的 api-base），右上角「登出」，回到登入頁；按上一頁也進不去
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "logout and 你的"，要全部通過
    """
    # 1. 要撤銷哪一台：帶了 refreshToken 用它的指紋，沒帶用 access token 裡的 sid
    where = {"user_id": me.id, "revoked_at__isnull": True}
    if body.refreshToken:
        where["refresh_token_hash"] = tokens.fingerprint(body.refreshToken)
    elif payload.get("sid"):
        where["id"] = uuid.UUID(payload["sid"])
    else:
        return {"ok": True}

    # 2. 設 revoked_at（不刪列）；找不到也當作成功，重複登出不要噴錯
    crud.save(UserSession, {"revoked_at": datetime.now(timezone.utc)}, where=where, db=db)
    db.commit()
    return {"ok": True}


@router.post("/auth/logout-all", summary="登出所有裝置")
@login_required
def logout_all(me: User, db: Session = Depends(get_db)):
    """登出所有裝置

    POST /api/auth/logout-all

    【這支做什麼】
        登出所有裝置（包含這一台）：這個人所有還沒撤銷的 sessions 都設 revoked_at。
        帳號可能被盜時用。access token 撤不掉，最多再撐 30 分鐘。

    【前端怎麼打】
        frontend/js/api.js 的 API.logoutAll()
        個人資料頁「登入中的裝置」→「登出所有裝置」。前端收到就清掉本機 token、回登入頁。

    【誰能打】
        登入、沒被停權就能打（平台管理員也可以）。上面的 @login_required 已經擋好了：
            沒登入、token 過期 → 401；被停權 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【請求主體】沒有

    【成功回應】狀態碼 200
        {"revoked": 3}（撤銷了幾台，包含這一台）

    【錯誤回應】
        只有守衛的 401／403，這支本身不會出錯。

    【會用到的資料表】
        表        讀／寫  用來做什麼
        sessions  寫      這個人所有還沒撤銷的，設 revoked_at

    【每一步用的工具與資料庫方法】
        步驟    呼叫         做什麼
        1 撤銷  crud.save(UserSession, {"revoked_at": now}, where={"user_id": me.id, "revoked_at__isnull": True}, db=db)  回傳改了幾列
                db.commit()  寫進去

    【寫法步驟】
        1. 我所有還沒撤銷的 sessions 設 revoked_at，記下改了幾列
        2. db.commit()，回 {"revoked": 幾列}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            import logging
            import uuid
            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import guest_only, login_required, token_required, visible_scope
            from app.models import (
                AuditLog, Family, FamilyMember, Group, GroupMember, Guardianship, PasswordReset, SavingsGoal, User, UserSession,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.auth import AvatarIn, FinanceIn, LoginIn, LogoutIn, PasswordChangeIn, PasswordResetConfirmIn, PasswordResetIn, ProfilePatchIn, RefreshIn, RegisterIn, VerifyEmailIn, VerifyPasswordIn
            from app.toolkit import account, crud, email_verify, errors, images, mailer, password_reset, passwords, period, profile, roles, security, theme, tokens
            from app.toolkit.config import settings
            from app.toolkit.db import get_db
            from app.toolkit.deps import current_token_payload

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 這個人所有還沒撤銷的 sessions 一起撤銷（包含這一台）
            revoked = crud.save(UserSession, {"revoked_at": datetime.now(timezone.utc)},
                                where={"user_id": me.id, "revoked_at__isnull": True}, db=db)
            db.commit()
            return {"revoked": revoked}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/auth/logout-all
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               用兩個瀏覽器各登入一次，其中一台打  → 200，revoked 是 2
        5. 兩台的 refreshToken 都換不到新的（POST /api/auth/refresh → 401）
        6. 前端改成連你的後端（frontend/index.html 的 api-base），個人資料頁「登出所有裝置」，回到登入頁
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "logout_all and 你的"，要全部通過
    """
    # 這個人所有還沒撤銷的 sessions 一起撤銷（包含這一台）
    revoked = crud.save(UserSession, {"revoked_at": datetime.now(timezone.utc)},
                        where={"user_id": me.id, "revoked_at__isnull": True}, db=db)
    db.commit()
    return {"revoked": revoked}


@router.get("/auth/me", summary="我是誰")
@login_required
def get_me(me: User, db: Session = Depends(get_db)):
    """我是誰

    GET /api/auth/me

    【這支做什麼】
        我是誰：使用者資料、家庭、看得到誰、查得到誰、誰在照看我。每一頁的權限判斷與路由閘都靠它
        （沒登入帶去登入頁、平台管理員帶去 #/admin、還沒走個人化設定帶去 #/setup）。
        ⚠️ user 不帶 income／expense／budget：收支一律從明細現算（GET /api/summary）。
        ⚠️ age 只是顯示用，任何權限判斷都不准讀它。

    【前端怎麼打】
        frontend/js/api.js 的 API.me()
        總覽、右上角帳號選單、每一頁的權限判斷。前端檢查回應裡一定要有 user。

    【誰能打】
        登入、沒被停權就能打（平台管理員也可以）。上面的 @login_required 已經擋好了：
            沒登入、token 過期 → 401；被停權 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【請求參數】沒有

    【成功回應】狀態碼 200
        {"user": {"id": "3", "name": "王大明", "email": "daming@wang.tw", "role": "parent", "familyId": "2",
                  "avatar": "明", "avatarUrl": null, "age": 52, "birthYear": 1974, "joined": "2026-01-05",
                  "theme": "sky", "onboardedAt": "2026-01-05T01:00:00+00:00", "savingsGoal": 20000,
                  "isPlatformAdmin": false, "emailVerified": true, "incomeMode": "auto", "expectedIncome": null,
                  "incomeType": null, "incomeNote": null},
         "family": {"id": "2", "name": "王家", "period": "2026-09"},
         "visible": ["3", "4", "5"], "queryable": ["3", "4", "5", "6"],
         "guardedBy": [{"id": "4", "name": "陳美玲"}]}
        欄位              怎麼來的
        user.onboardedAt  null = 還沒走個人化設定。⚠️ 一定要回：沒回的話前端當成走過了，新帳號永遠不會被問存款目標
        user.theme        一定有值，沒選過是 paper
        user.savingsGoal  最新一筆整體存款目標，沒設過是 0
        user.emailVerified  點過驗證信的連結沒（users.email_verified_at 有沒有值）；false 時總覽會提醒去收信
        family            沒有家庭是 null；period 是台灣的這個月
        visible           自己＋我照看的人＋同家庭的其他家長（自己排第一個）
        queryable         visible 再加上跟我共用帳本的人
        guardedBy         誰在照看我——被照看的人自己要看得到，這是刻意的
        · 平台管理員：visible、queryable 都是空的（他讀不到任何人的帳），前端會帶他去 #/admin

    【錯誤回應】
        只有守衛的 401／403，這支本身不會出錯。

    【會用到的資料表】
        表                                                    讀／寫  用來做什麼
        guardianships、family_members、group_members、groups  讀      visible_scope()
        group_members                                         讀      共用帳本的人
        guardianships、users                                  讀      誰在照看我、他們的名字
        families                                              讀      家庭名字
        savings_goals                                         讀      目前的整體存款目標

    【每一步用的工具與資料庫方法】
        步驟        呼叫                                          做什麼
        1 看得到誰  users, groups = visible_scope(me, db)         平台管理員不要算，直接給空的
                    sorted(users, key=lambda u: (u != me.id, u))  自己排第一個（False 排在 True 前面），其他照 id
        2 照看我的  crud.find(Guardianship, {"ward_id": me.id, "ended_at__isnull": True}, fields="guardian_id", db=db)  監管人的 id
        3 家庭      crud.get(Family, me.family_id, db=db)         守衛已經把 me.family_id、me.family_role 掛好了
                    period.current_month(台灣的今天)              "2026-09"

    【寫法步驟】
        1. 平台管理員：看得到、查得到都是空的；其他人用 visible_scope，再加上共用帳本的人
        2. 查誰在照看我
        3. 查家庭、目前的整體存款目標
        4. 組成 user（role、familyId 直接用 me 身上的）與其他欄位，回傳
        ⚠️ 只讀不寫，不用 db.commit()。

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            import logging
            import uuid
            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import guest_only, login_required, token_required, visible_scope
            from app.models import (
                AuditLog, Family, FamilyMember, Group, GroupMember, Guardianship, PasswordReset, SavingsGoal, User, UserSession,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.auth import AvatarIn, FinanceIn, LoginIn, LogoutIn, PasswordChangeIn, PasswordResetConfirmIn, PasswordResetIn, ProfilePatchIn, RefreshIn, RegisterIn, VerifyEmailIn, VerifyPasswordIn
            from app.toolkit import account, crud, email_verify, errors, images, mailer, password_reset, passwords, period, profile, roles, security, theme, tokens
            from app.toolkit.config import settings
            from app.toolkit.db import get_db
            from app.toolkit.deps import current_token_payload

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 我看得到誰、查得到誰（平台管理員讀不到任何人的帳：都是空的）
            if me.is_platform_admin:
                users, sharing = set(), []
            else:
                users, groups = visible_scope(me, db)
                sharing = crud.find(GroupMember, {"group_id__in": groups}, fields="user_id", db=db)
            queryable = users.union(sharing)

            # 2. 誰在照看我（被照看的人自己一定看得到）
            guardian_ids = crud.find(Guardianship, {"ward_id": me.id, "ended_at__isnull": True}, fields="guardian_id", db=db)
            guardians = crud.find(User, {"id__in": guardian_ids}, order_by="id", db=db)

            # 3. 我的家庭、目前的整體存款目標
            tw = timezone(timedelta(hours=8))
            fam = crud.get(Family, me.family_id, db=db) if me.family_id else None
            goal = crud.get(SavingsGoal, where={"user_id": me.id, "group_id__isnull": True},
                            fields="goal_amount", order_by="-id", db=db)
            this_year = datetime.now(tw).year
            onboarded = me.onboarded_at
            if onboarded is not None and onboarded.tzinfo is None:
                onboarded = onboarded.replace(tzinfo=timezone.utc)          # SQLite 讀回來沒有時區

            # 4. 組起來
            return {
                "user": {
                    "id": str(me.id),
                    "name": me.display_name,
                    "email": me.email,
                    "role": me.family_role,
                    "familyId": str(me.family_id) if me.family_id else None,
                    "avatar": me.display_name[-1:],
                    "avatarUrl": images.to_data_uri(me.avatar_bytes, me.avatar_mime) if me.avatar_bytes else None,
                    "age": this_year - me.birth_year if me.birth_year else None,
                    "birthYear": me.birth_year,
                    "joined": me.created_at.date().isoformat(),
                    "theme": me.theme or "paper",
                    "onboardedAt": onboarded.isoformat() if onboarded else None,
                    "savingsGoal": goal or 0,
                    "isPlatformAdmin": me.is_platform_admin,
                    "incomeMode": me.income_mode or "auto",
                    "expectedIncome": me.expected_income,
                    "incomeType": me.income_type,
                    "incomeNote": me.income_note,
                    "emailVerified": me.email_verified_at is not None,
                },
                "family": {"id": str(fam.id), "name": fam.name,
                           "period": period.current_month(datetime.now(tw).date())} if fam else None,
                "visible": [str(u) for u in sorted(users, key=lambda u: (u != me.id, u))],
                "queryable": [str(u) for u in sorted(queryable, key=lambda u: (u != me.id, u))],
                "guardedBy": [{"id": str(u.id), "name": u.display_name} for u in guardians],
            }

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 GET /api/auth/me
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               剛註冊的人            → onboardedAt 是 null、family 是 null、visible 只有自己
               家長（照看一個孩子）  → visible 有孩子與另一位家長
               被照看的孩子          → guardedBy 有照看他的家長
               平台管理員            → visible、queryable 都是 []
        5. 前端改成連你的後端（frontend/index.html 的 api-base），登入之後右上角帳號選單的名字、頭像、角色要對
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "get_me and 你的"，要全部通過
    """
    # 1. 我看得到誰、查得到誰（平台管理員讀不到任何人的帳：都是空的）
    if me.is_platform_admin:
        users, sharing = set(), []
    else:
        users, groups = visible_scope(me, db)
        sharing = crud.find(GroupMember, {"group_id__in": groups}, fields="user_id", db=db)
    queryable = users.union(sharing)

    # 2. 誰在照看我（被照看的人自己一定看得到）
    guardian_ids = crud.find(Guardianship, {"ward_id": me.id, "ended_at__isnull": True}, fields="guardian_id", db=db)
    guardians = crud.find(User, {"id__in": guardian_ids}, order_by="id", db=db)

    # 3. 我的家庭、目前的整體存款目標
    tw = timezone(timedelta(hours=8))
    fam = crud.get(Family, me.family_id, db=db) if me.family_id else None
    goal = crud.get(SavingsGoal, where={"user_id": me.id, "group_id__isnull": True},
                    fields="goal_amount", order_by="-id", db=db)
    this_year = datetime.now(tw).year
    onboarded = me.onboarded_at
    if onboarded is not None and onboarded.tzinfo is None:
        onboarded = onboarded.replace(tzinfo=timezone.utc)          # SQLite 讀回來沒有時區

    # 4. 組起來
    return {
        "user": {
            "id": str(me.id),
            "name": me.display_name,
            "email": me.email,
            "role": me.family_role,
            "familyId": str(me.family_id) if me.family_id else None,
            "avatar": me.display_name[-1:],
            "avatarUrl": images.to_data_uri(me.avatar_bytes, me.avatar_mime) if me.avatar_bytes else None,
            "age": this_year - me.birth_year if me.birth_year else None,
            "birthYear": me.birth_year,
            "joined": me.created_at.date().isoformat(),
            "theme": me.theme or "paper",
            "onboardedAt": onboarded.isoformat() if onboarded else None,
            "savingsGoal": goal or 0,
            "isPlatformAdmin": me.is_platform_admin,
            "incomeMode": me.income_mode or "auto",
            "expectedIncome": me.expected_income,
            "incomeType": me.income_type,
            "incomeNote": me.income_note,
            "emailVerified": me.email_verified_at is not None,
        },
        "family": {"id": str(fam.id), "name": fam.name,
                   "period": period.current_month(datetime.now(tw).date())} if fam else None,
        "visible": [str(u) for u in sorted(users, key=lambda u: (u != me.id, u))],
        "queryable": [str(u) for u in sorted(queryable, key=lambda u: (u != me.id, u))],
        "guardedBy": [{"id": str(u.id), "name": u.display_name} for u in guardians],
    }


@router.patch("/auth/me", summary="改個人資料、主題、個人化設定走完")
@login_required
def update_me(body: ProfilePatchIn, me: User, db: Session = Depends(get_db)):
    """改個人資料、主題、個人化設定走完

    PATCH /api/auth/me

    【這支做什麼】
        改自己的個人資料，只送要改的欄位（沒送的保持原樣，所以是 PATCH）：
            displayName 名字、birthYear 出生年、theme 介面主題、onboarded 個人化設定走完了、
            incomeMode／expectedIncome 收入怎麼算（可花上限用，見 services/analytics.py 的 expected_income）
        ⚠️ email 不開放修改：email 是登入帳號，改它等於換帳號（要另外設計驗證新信箱的流程）。
        ⚠️ 換主題不需要新路由、新表，就是 users.theme 一個欄位，只收 toolkit/theme.py 清單裡的。
        onboarded 只收 true：沒有「退回沒走過」這回事；已經設過的不要蓋掉時間。
        ⚠️ 還沒點驗證信的人不能標 onboarded（403）：註冊 → 點信 → 個人化設定，這個順序由後端守住。
           寄不出信的環境（本機開發）沒有信可以點，不擋。

    【前端怎麼打】
        frontend/js/api.js 的 API.updateProfile({...})
        個人資料頁、主題設定（按下去先換，失敗再換回來）、個人化設定走完或「全部先跳過」。
        回應是更新後的 user，前端直接換掉手上的那一份。

    【誰能打】
        登入、沒被停權就能打（平台管理員也可以）。上面的 @login_required 已經擋好了：
            沒登入、token 過期 → 401；被停權 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【請求主體】body 是 ProfilePatchIn（app/schemas/auth.py），只送要改的
        欄位         型別         說明
        displayName  字串         整理空白後 1～30 字
        birthYear    整數或 null  1900～今年；null = 清掉
        theme        字串         paper／sky／tech／literary／pop／girly／cute／art
        onboarded    true         只收 true
        incomeMode   字串         auto 自動估（近 3 個月平均，還沒紀錄用 expectedIncome）／fixed 固定月薪／actual 只算已入帳
        expectedIncome 數字或 null  每月預計收入；0 或 null = 不填。選 fixed 一定要有
        incomeType   字串或 null  收入怎麼來（catalog.INCOME_TYPES：salary_end、hourly、freelance…、other）
        incomeNote   字串或 null  選 other 時自己寫的，洗過（profile.clean_note）、最多 30 字
        範例：{"displayName": "王大明", "birthYear": 1974}　或　{"theme": "sky"}　或　{"onboarded": true}
        · body.model_fields_set 是「有送來的欄位名字」：birthYear 送 null（要清掉）跟沒送（不要動）分得開
        · 不認得的欄位（例如 email）FastAPI 直接回 422（ProfilePatchIn 設了 extra="forbid"）

    【成功回應】狀態碼 200
        更新後的 user（形狀同 GET /api/auth/me 的 user）

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                       detail
        422     名字整理完是空的               名字不能空白
        422     名字超過 30 字                 名字最多 30 個字
        422     出生年不在 1900～今年          出生年份不合理
        422     主題不在清單裡                 沒有這個主題
        422     onboarded 不是 true            onboarded 只能是 true
        422     incomeMode 不在三種裡          收入的算法只能是 auto、fixed 或 actual
        422     expectedIncome 是負的或太大     預計收入要是 0 以上的數字
        422     選 fixed 卻沒有金額            選固定月薪，要填每個月大約多少
        422     incomeType 不在清單裡          沒有這種收入方式
        403     還沒點驗證信就要標 onboarded   先到信箱點驗證連結，才能開始設定
        422     帶了 email 或其他不認得的欄位  （FastAPI 自動回）

    【會用到的資料表】
        表             讀／寫  用來做什麼
        users          寫      display_name、birth_year、theme、onboarded_at、income_mode、expected_income、income_type、income_note
        savings_goals  讀      回傳的 user 要帶 savingsGoal

    【每一步用的工具與資料庫方法】
        步驟        呼叫                                              做什麼
        1 有送什麼  body.model_fields_set                             例如 {"theme"}
        3 主題      theme.clean_theme(body.theme)                     不在清單裡丟 ValueError（不幫你轉大小寫，送錯就是程式的錯）
        5 寫回      crud.save(User, {"id": me.id, **changes}, db=db)  帶主鍵 = 改那一個人；me 物件也會跟著變
                    db.commit()                                       寫進去

    【寫法步驟】
        1. 有送 displayName：整理空白，空的或太長 422
        2. 有送 birthYear：不是 null 就要在 1900～今年
        3. 有送 theme：clean_theme（422）
        4. 有送 onboarded：只收 true；還沒點驗證信（而且寄得出信）→ 403；還沒設過才設 onboarded_at = 現在
        5. 有送 incomeMode／expectedIncome：在清單裡、金額 0 以上；最後是 fixed 卻沒有金額 → 422
        6. 有東西要改才寫回、db.commit()
        7. 回傳改完的 user

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            import logging
            import uuid
            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import guest_only, login_required, token_required, visible_scope
            from app.models import (
                AuditLog, Family, FamilyMember, Group, GroupMember, Guardianship, PasswordReset, SavingsGoal, User, UserSession,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.auth import AvatarIn, FinanceIn, LoginIn, LogoutIn, PasswordChangeIn, PasswordResetConfirmIn, PasswordResetIn, ProfilePatchIn, RefreshIn, RegisterIn, VerifyEmailIn, VerifyPasswordIn
            from app.toolkit import account, crud, email_verify, errors, images, mailer, password_reset, passwords, period, profile, roles, security, theme, tokens
            from app.toolkit.config import settings
            from app.toolkit.db import get_db
            from app.toolkit.deps import current_token_payload

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            sent = body.model_fields_set
            changes = {}
            this_year = datetime.now(timezone(timedelta(hours=8))).year

            # 1. 名字
            if "displayName" in sent:
                name = " ".join((body.displayName or "").split())
                if not name:
                    raise errors.unprocessable("名字不能空白")
                if len(name) > 30:
                    raise errors.unprocessable("名字最多 30 個字")
                changes["display_name"] = name

            # 2. 出生年（null = 清掉）。只是個人資料，任何權限判斷都不讀它
            if "birthYear" in sent:
                if body.birthYear is not None and not 1900 <= body.birthYear <= this_year:
                    raise errors.unprocessable("出生年份不合理")
                changes["birth_year"] = body.birthYear

            # 3. 主題只收清單裡的
            if "theme" in sent:
                try:
                    changes["theme"] = theme.clean_theme(body.theme)
                except ValueError as exc:
                    raise errors.unprocessable(str(exc)) from None

            # 4. 個人化設定走完：只收 true，已經設過的不蓋掉時間
            if "onboarded" in sent:
                if body.onboarded is not True:
                    raise errors.unprocessable("onboarded 只能是 true")
                # 註冊後要先點驗證信，才能開始（完成）設定；寄不出信的環境（本機開發）沒有信可以點，不擋
                if me.email_verified_at is None and me.onboarded_at is None and mailer.is_configured():
                    raise errors.forbidden("先到信箱點驗證連結，才能開始設定")
                if me.onboarded_at is None:
                    changes["onboarded_at"] = datetime.now(timezone.utc)

            # 5. 收入怎麼算（可花上限用）：三種都用同一條 max(這個月已入帳, 預計收入)，只差在預計收入從哪裡來
            if "incomeMode" in sent:
                if body.incomeMode not in catalog.INCOME_MODES:
                    raise errors.unprocessable("收入的算法只能是 auto、fixed 或 actual")
                changes["income_mode"] = body.incomeMode
            if "expectedIncome" in sent:
                if body.expectedIncome is not None and not 0 <= body.expectedIncome <= 100000000:
                    raise errors.unprocessable("預計收入要是 0 以上的數字")
                changes["expected_income"] = body.expectedIncome or None                # 0、null 都是「不填」
            if "incomeType" in sent:
                if body.incomeType is not None and body.incomeType not in {t["id"] for t in catalog.INCOME_TYPES}:
                    raise errors.unprocessable("沒有這種收入方式")
                changes["income_type"] = body.incomeType
            if "incomeNote" in sent:
                changes["income_note"] = profile.clean_note(body.incomeNote)[:30] or None     # 「其他」自己寫的，洗過、最多 30 字
            if {"incomeMode", "expectedIncome"} & sent and changes.get("income_mode", me.income_mode) == "fixed" \
                    and not changes.get("expected_income", me.expected_income):
                raise errors.unprocessable("選固定月薪，要填每個月大約多少")

            # 6. 寫回去
            if changes:
                crud.save(User, {"id": me.id, **changes}, db=db)
                db.commit()

            # 7. 回傳改完的 user（形狀同 GET /api/auth/me）
            goal = crud.get(SavingsGoal, where={"user_id": me.id, "group_id__isnull": True},
                            fields="goal_amount", order_by="-id", db=db)
            onboarded = me.onboarded_at
            if onboarded is not None and onboarded.tzinfo is None:
                onboarded = onboarded.replace(tzinfo=timezone.utc)          # SQLite 讀回來沒有時區
            return {
                "id": str(me.id),
                "name": me.display_name,
                "email": me.email,
                "role": me.family_role,
                "familyId": str(me.family_id) if me.family_id else None,
                "avatar": me.display_name[-1:],
                "avatarUrl": images.to_data_uri(me.avatar_bytes, me.avatar_mime) if me.avatar_bytes else None,
                "age": this_year - me.birth_year if me.birth_year else None,
                "birthYear": me.birth_year,
                "joined": me.created_at.date().isoformat(),
                "theme": me.theme or "paper",
                "onboardedAt": onboarded.isoformat() if onboarded else None,
                "savingsGoal": goal or 0,
                "isPlatformAdmin": me.is_platform_admin,
                "incomeMode": me.income_mode or "auto",
                "expectedIncome": me.expected_income,
                "incomeType": me.income_type,
                "incomeNote": me.income_note,
            }

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 PATCH /api/auth/me
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               {"theme": "sky"}     → 200，theme 是 sky，其他沒變
               {"theme": "Sky"}     → 422
               {"onboarded": true}  → 200，onboardedAt 有值；再送一次時間不變
               {"birthYear": null}  → 200，birthYear 與 age 都是 null
               {"email": "x@x.tw"}  → 422
               {"incomeMode": "fixed", "expectedIncome": 31000} → 200；{"incomeMode": "fixed", "expectedIncome": null} → 422
        5. 前端改成連你的後端（frontend/index.html 的 api-base），個人資料頁改名字、換主題，重新整理後都還在
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "update_me and 你的"，要全部通過
    """
    sent = body.model_fields_set
    changes = {}
    this_year = datetime.now(timezone(timedelta(hours=8))).year

    # 1. 名字
    if "displayName" in sent:
        name = " ".join((body.displayName or "").split())
        if not name:
            raise errors.unprocessable("名字不能空白")
        if len(name) > 30:
            raise errors.unprocessable("名字最多 30 個字")
        changes["display_name"] = name

    # 2. 出生年（null = 清掉）。只是個人資料，任何權限判斷都不讀它
    if "birthYear" in sent:
        if body.birthYear is not None and not 1900 <= body.birthYear <= this_year:
            raise errors.unprocessable("出生年份不合理")
        changes["birth_year"] = body.birthYear

    # 3. 主題只收清單裡的
    if "theme" in sent:
        try:
            changes["theme"] = theme.clean_theme(body.theme)
        except ValueError as exc:
            raise errors.unprocessable(str(exc)) from None

    # 4. 個人化設定走完：只收 true，已經設過的不蓋掉時間
    if "onboarded" in sent:
        if body.onboarded is not True:
            raise errors.unprocessable("onboarded 只能是 true")
        # 註冊後要先點驗證信，才能開始（完成）設定；寄不出信的環境（本機開發）沒有信可以點，不擋
        if me.email_verified_at is None and me.onboarded_at is None and mailer.is_configured():
            raise errors.forbidden("先到信箱點驗證連結，才能開始設定")
        if me.onboarded_at is None:
            changes["onboarded_at"] = datetime.now(timezone.utc)

    # 5. 收入怎麼算（可花上限用）：三種都用同一條 max(這個月已入帳, 預計收入)，只差在預計收入從哪裡來
    if "incomeMode" in sent:
        if body.incomeMode not in catalog.INCOME_MODES:
            raise errors.unprocessable("收入的算法只能是 auto、fixed 或 actual")
        changes["income_mode"] = body.incomeMode
    if "expectedIncome" in sent:
        if body.expectedIncome is not None and not 0 <= body.expectedIncome <= 100000000:
            raise errors.unprocessable("預計收入要是 0 以上的數字")
        changes["expected_income"] = body.expectedIncome or None                # 0、null 都是「不填」
    if "incomeType" in sent:
        if body.incomeType is not None and body.incomeType not in {t["id"] for t in catalog.INCOME_TYPES}:
            raise errors.unprocessable("沒有這種收入方式")
        changes["income_type"] = body.incomeType
    if "incomeNote" in sent:
        changes["income_note"] = profile.clean_note(body.incomeNote)[:30] or None     # 「其他」自己寫的，洗過、最多 30 字
    if {"incomeMode", "expectedIncome"} & sent and changes.get("income_mode", me.income_mode) == "fixed" \
            and not changes.get("expected_income", me.expected_income):
        raise errors.unprocessable("選固定月薪，要填每個月大約多少")

    # 6. 寫回去
    if changes:
        crud.save(User, {"id": me.id, **changes}, db=db)
        db.commit()

    # 7. 回傳改完的 user（形狀同 GET /api/auth/me）
    goal = crud.get(SavingsGoal, where={"user_id": me.id, "group_id__isnull": True},
                    fields="goal_amount", order_by="-id", db=db)
    onboarded = me.onboarded_at
    if onboarded is not None and onboarded.tzinfo is None:
        onboarded = onboarded.replace(tzinfo=timezone.utc)          # SQLite 讀回來沒有時區
    return {
        "id": str(me.id),
        "name": me.display_name,
        "email": me.email,
        "role": me.family_role,
        "familyId": str(me.family_id) if me.family_id else None,
        "avatar": me.display_name[-1:],
        "avatarUrl": images.to_data_uri(me.avatar_bytes, me.avatar_mime) if me.avatar_bytes else None,
        "age": this_year - me.birth_year if me.birth_year else None,
        "birthYear": me.birth_year,
        "joined": me.created_at.date().isoformat(),
        "theme": me.theme or "paper",
        "onboardedAt": onboarded.isoformat() if onboarded else None,
        "savingsGoal": goal or 0,
        "isPlatformAdmin": me.is_platform_admin,
        "incomeMode": me.income_mode or "auto",
        "expectedIncome": me.expected_income,
        "incomeType": me.income_type,
        "incomeNote": me.income_note,
    }


@router.patch("/auth/password", summary="改密碼")
@login_required
def change_password(
    body: PasswordChangeIn,
    me: User,
    payload: dict = Depends(current_token_payload),
    db: Session = Depends(get_db),
):
    """改密碼

    PATCH /api/auth/password

    【這支做什麼】
        知道舊密碼的人改成新密碼。成功後其他裝置全部登出（這一台留著），並寫一筆稽核。
        ⚠️ 舊密碼不對回 400，不是 401：前端收到 401 會以為 token 過期，跑去續期再重送。

    【前端怎麼打】
        frontend/js/api.js 的 API.changePassword({ oldPassword, newPassword })
        個人資料頁「改密碼」。

    【誰能打】
        登入、沒被停權就能打（平台管理員也可以）。上面的 @login_required 已經擋好了：
            沒登入、token 過期 → 401；被停權 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）
        另外收一個 payload=Depends(current_token_payload)：裡面的 sid 是這一台，撤銷其他裝置時要排除它。

    【請求主體】body 是 PasswordChangeIn（app/schemas/auth.py）
        欄位         型別  必填  說明
        oldPassword  字串  是    目前的密碼
        newPassword  字串  是    新密碼，規則同註冊
        範例：{"oldPassword": "abcd1234", "newPassword": "efgh5678"}

    【成功回應】狀態碼 200
        {"ok": true}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候    detail
        400     舊密碼不對  目前的密碼不對
        400     新舊一樣    新密碼不能跟舊的一樣
        422     新密碼太弱  （passwords 丟出來的那句話）

    【會用到的資料表】
        表          讀／寫  用來做什麼
        users       寫      新的密碼雜湊
        sessions    寫      其他裝置設 revoked_at
        audit_logs  寫      change_password（安全類事件留紀錄）

    【每一步用的工具與資料庫方法】
        步驟        呼叫                                                           做什麼
        1 舊密碼    passwords.verify_password(body.oldPassword, me.password_hash)  對回 True
        2 新密碼    passwords.hash_password(body.newPassword)                      太弱丟 WeakPassword
        3 其他裝置  {"id__ne": uuid.UUID(payload["sid"])}                          排除這一台
                    crud.save(UserSession, {"revoked_at": now}, where={…}, db=db)  其他全部撤銷
        4 稽核      crud.save(AuditLog, {"action": "change_password", …}, db=db)   只記動作
                    db.commit()                                                    全部一起寫進去

    【寫法步驟】
        1. 舊密碼不對 → 400；新舊一樣 → 400
        2. 新密碼檢查強度、算雜湊（422），寫回
        3. 我其他還沒撤銷的 sessions 全部撤銷（有 sid 的話排除這一台）
        4. 寫稽核，db.commit()，回 {"ok": true}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            import logging
            import uuid
            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import guest_only, login_required, token_required, visible_scope
            from app.models import (
                AuditLog, Family, FamilyMember, Group, GroupMember, Guardianship, PasswordReset, SavingsGoal, User, UserSession,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.auth import AvatarIn, FinanceIn, LoginIn, LogoutIn, PasswordChangeIn, PasswordResetConfirmIn, PasswordResetIn, ProfilePatchIn, RefreshIn, RegisterIn, VerifyEmailIn, VerifyPasswordIn
            from app.toolkit import account, crud, email_verify, errors, images, mailer, password_reset, passwords, period, profile, roles, security, theme, tokens
            from app.toolkit.config import settings
            from app.toolkit.db import get_db
            from app.toolkit.deps import current_token_payload

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 舊密碼不對回 400（不是 401）
            if not passwords.verify_password(body.oldPassword, me.password_hash):
                raise errors.bad_request("目前的密碼不對")
            if body.oldPassword == body.newPassword:
                raise errors.bad_request("新密碼不能跟舊的一樣")

            # 2. 新密碼：檢查強度，只存雜湊
            try:
                hashed = passwords.hash_password(body.newPassword)
            except passwords.WeakPassword as exc:
                raise errors.unprocessable(str(exc)) from None
            now = datetime.now(timezone.utc)
            crud.save(User, {"id": me.id, "password_hash": hashed}, db=db)

            # 3. 其他裝置全部登出（這一台留著）
            where = {"user_id": me.id, "revoked_at__isnull": True}
            if payload.get("sid"):
                where["id__ne"] = uuid.UUID(payload["sid"])
            crud.save(UserSession, {"revoked_at": now}, where=where, db=db)

            # 4. 寫稽核
            crud.save(AuditLog, {"actor_id": me.id, "action": "change_password", "target_type": "user",
                                 "target_id": me.id}, db=db)
            db.commit()
            return {"ok": True}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 PATCH /api/auth/password
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               正確的舊密碼＋新密碼  → 200
               舊密碼打錯            → 400（不是 401）
               新密碼 "1234"         → 422
        5. 用舊密碼登入 → 401；用新密碼 → 200
        6. 另一台瀏覽器原本的登入，下次換 token 時被登出；這一台不受影響
        7. 前端改成連你的後端（frontend/index.html 的 api-base），個人資料頁「改密碼」，成功後跳提示
        8. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "change_password and 你的"，要全部通過
    """
    # 1. 舊密碼不對回 400（不是 401）
    if not passwords.verify_password(body.oldPassword, me.password_hash):
        raise errors.bad_request("目前的密碼不對")
    if body.oldPassword == body.newPassword:
        raise errors.bad_request("新密碼不能跟舊的一樣")

    # 2. 新密碼：檢查強度，只存雜湊
    try:
        hashed = passwords.hash_password(body.newPassword)
    except passwords.WeakPassword as exc:
        raise errors.unprocessable(str(exc)) from None
    now = datetime.now(timezone.utc)
    crud.save(User, {"id": me.id, "password_hash": hashed}, db=db)

    # 3. 其他裝置全部登出（這一台留著）
    where = {"user_id": me.id, "revoked_at__isnull": True}
    if payload.get("sid"):
        where["id__ne"] = uuid.UUID(payload["sid"])
    crud.save(UserSession, {"revoked_at": now}, where=where, db=db)

    # 4. 寫稽核
    crud.save(AuditLog, {"actor_id": me.id, "action": "change_password", "target_type": "user",
                         "target_id": me.id}, db=db)
    db.commit()
    return {"ok": True}


@router.post("/auth/password-reset", summary="忘記密碼：寄重設信")
def request_password_reset(body: PasswordResetIn, background: BackgroundTasks, db: Session = Depends(get_db)):
    """忘記密碼：寄重設信

    POST /api/auth/password-reset

    【這支做什麼】
        忘記密碼：輸入 email，寄一封「重設密碼」的信，信裡的連結 30 分鐘內有效、只能用一次。
        ⚠️ 有沒有這個帳號，回應都一模一樣（{ok, message}，同一個 200）：講出來的話，這支就是帳號列舉工具。
        ⚠️ token 只存雜湊；連結長成 <APP_BASE_URL>/#/reset/<token>（token 在 # 後面，不會送到伺服器、不會留在紀錄裡）。
        ⚠️ 同一個人 60 秒內不重寄：不然任何人都能拿你的 email 轟炸你的信箱。
        ⚠️ 寄信走 Brevo 的 HTTP API（toolkit/mailer.py），不能用 SMTP：Render 免費方案擋掉了 SMTP 的埠。
        寄信放在背景做（回應先送出去）：寄信要一兩秒，同步寄的話「帳號存在」的請求會明顯比較慢，一樣洩漏。
        寄信失敗只記 log，回應照舊。

    【前端怎麼打】
        frontend/js/api.js 的 API.requestPasswordReset(email)
        登入頁的「忘記密碼？」。前端檢查回應裡一定要有 ok 與 message，直接把 message 顯示出來。
        ⚠️ mock（沒有後端時）會多回 demoMail 把連結攤在畫面上——真後端絕對不能回這個欄位。

    【誰能打】
        任何人都能打，不用登入（上面沒有守衛）。
        另外收一個 background（FastAPI 的 BackgroundTasks）：回應送出去之後才寄信。

    【請求主體】body 是 PasswordResetIn（app/schemas/auth.py）
        欄位   型別  必填  說明
        email  字串  是    大小寫不拘
        範例：{"email": "daming@wang.tw"}

    【成功回應】狀態碼 200（有沒有這個帳號都一樣）
        {"ok": true, "message": "如果這個 email 有註冊，重設密碼的信已經寄出，30 分鐘內有效。"}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候        detail
        400     email 格式不對  email 格式看起來不對
        · 只有這一種錯：格式跟帳號在不在無關，講出來沒關係。其他情況一律回成功。

    【會用到的資料表】
        表               讀／寫  用來做什麼
        users            讀      有沒有這個人
        password_resets  讀＋寫  這個人上一封什麼時候寄的；新增一列（只存 token 雜湊）

    【每一步用的工具與資料庫方法】
        步驟     呼叫                                                        做什麼
        1 email  password_reset.normalize_email(body.email)                  格式不對丟 ValueError
                 password_reset.GENERIC_MESSAGE                              那句「如果這個 email 有註冊…」
        3 冷卻   crud.get(PasswordReset, where={"user_id": …}, fields="created_at", order_by="-created_at", db=db)  上一封的時間（沒有是 None）
                 password_reset.should_send(上一封的時間)                    60 秒內回 False
        4 token  password_reset.new_token()                                  43 字元、網址安全、用 secrets 產生
                 password_reset.hash_token(token)／expires_at()              雜湊、30 分鐘後
        5 信     password_reset.reset_link(settings.app_base_url, token)     組連結
                 password_reset.mail_content(名字, 連結)                     回傳（主旨, 純文字, HTML），名字已經 escape
                 background.add_task(send)                                   回應送出去之後才跑 send()
                 mailer.send_mail(收件人, 主旨, 純文字, HTML, to_name=名字)  寄出；沒設定丟 MailNotConfigured、失敗丟 MailError
                 logging.getLogger("fambudget").warning(…)                   寄不出去記 log（不影響回應）
        ⚠️ send() 裡用的收件人、名字要先存成區域變數：背景跑的時候，這次請求的資料庫連線已經關了。

    【寫法步驟】
        1. 整理 email（400）；準備好固定的回應
        2. 找不到人 → 直接回固定的回應
        3. 60 秒內寄過 → 直接回固定的回應
        4. 產生 token，存雜湊與到期時間，db.commit()
        5. 組信的內容，排進背景寄出（失敗記 log）
        6. 回固定的回應

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            import logging
            import uuid
            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import guest_only, login_required, token_required, visible_scope
            from app.models import (
                AuditLog, Family, FamilyMember, Group, GroupMember, Guardianship, PasswordReset, SavingsGoal, User, UserSession,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.auth import AvatarIn, FinanceIn, LoginIn, LogoutIn, PasswordChangeIn, PasswordResetConfirmIn, PasswordResetIn, ProfilePatchIn, RefreshIn, RegisterIn, VerifyEmailIn, VerifyPasswordIn
            from app.toolkit import account, crud, email_verify, errors, images, mailer, password_reset, passwords, period, profile, roles, security, theme, tokens
            from app.toolkit.config import settings
            from app.toolkit.db import get_db
            from app.toolkit.deps import current_token_payload

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 只有 email 格式不對會回錯；之後不管怎樣，回應都一模一樣
            try:
                email = password_reset.normalize_email(body.email)
            except ValueError as exc:
                raise errors.bad_request(str(exc)) from None
            answer = {"ok": True, "message": password_reset.GENERIC_MESSAGE}

            # 2. 找不到人：不講
            user = crud.get(User, where={"email": email}, db=db)
            if user is None:
                return answer

            # 3. 60 秒內寄過就不寄（不然任何人都能轟炸別人的信箱）
            last = crud.get(PasswordReset, where={"user_id": user.id}, fields="created_at", order_by="-created_at", db=db)
            if not password_reset.should_send(last):
                return answer

            # 4. 產生 token：資料庫只存雜湊
            token = password_reset.new_token()
            crud.save(PasswordReset, {"user_id": user.id, "token_hash": password_reset.hash_token(token),
                                      "expires_at": password_reset.expires_at()}, db=db)
            db.commit()

            # 5. 回應送出去之後才寄信；寄不出去只記 log
            to, who = user.email, user.display_name
            subject, text, html = password_reset.mail_content(who, password_reset.reset_link(settings.app_base_url, token))

            def send():
                try:
                    mailer.send_mail(to, subject, text, html, to_name=who)
                except (mailer.MailNotConfigured, mailer.MailError) as exc:
                    logging.getLogger("fambudget").warning("重設密碼信寄不出去：%s", exc)

            background.add_task(send)
            return answer

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/auth/password-reset
        3. 這支不用登入；backend/.env 要先填 BREVO_API_KEY 與 MAIL_FROM（沒填信寄不出去，但回應一樣是 200）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               註冊過的 email             → 200，信箱收到信
               沒註冊過的 email           → 200，而且回應一字不差
               同一個 email 馬上再按一次  → 200，但不會收到第二封
               email 填 abc               → 400
        5. 資料庫 password_resets 的 token_hash 不是信裡的 token 原文
        6. 前端改成連你的後端（frontend/index.html 的 api-base），登入頁「忘記密碼？」輸入 email，畫面顯示那句固定的話
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "request_password_reset and 你的"，要全部通過
    """
    # 1. 只有 email 格式不對會回錯；之後不管怎樣，回應都一模一樣
    try:
        email = password_reset.normalize_email(body.email)
    except ValueError as exc:
        raise errors.bad_request(str(exc)) from None
    answer = {"ok": True, "message": password_reset.GENERIC_MESSAGE}

    # 2. 找不到人：不講
    user = crud.get(User, where={"email": email}, db=db)
    if user is None:
        return answer

    # 3. 60 秒內寄過就不寄（不然任何人都能轟炸別人的信箱）
    last = crud.get(PasswordReset, where={"user_id": user.id}, fields="created_at", order_by="-created_at", db=db)
    if not password_reset.should_send(last):
        return answer

    # 4. 產生 token：資料庫只存雜湊
    token = password_reset.new_token()
    crud.save(PasswordReset, {"user_id": user.id, "token_hash": password_reset.hash_token(token),
                              "expires_at": password_reset.expires_at()}, db=db)
    db.commit()

    # 5. 回應送出去之後才寄信；寄不出去只記 log
    to, who = user.email, user.display_name
    subject, text, html = password_reset.mail_content(who, password_reset.reset_link(settings.app_base_url, token))

    def send():
        try:
            mailer.send_mail(to, subject, text, html, to_name=who)
        except (mailer.MailNotConfigured, mailer.MailError) as exc:
            logging.getLogger("fambudget").warning("重設密碼信寄不出去：%s", exc)

    background.add_task(send)
    return answer


@router.post("/auth/password-reset/confirm", summary="用信裡的 token 設新密碼")
def confirm_password_reset(
    body: PasswordResetConfirmIn,
    reset_row=Depends(token_required()),
    db: Session = Depends(get_db),
):
    """用信裡的 token 設新密碼

    POST /api/auth/password-reset/confirm

    【這支做什麼】
        點信裡的連結之後設定新密碼。成功後：密碼換掉、這個連結作廢、這個人所有裝置都登出——三件事在同一個交易裡。
        ⚠️ 所有裝置都登出：連結可能是別人翻到信箱拿去用的。前端改完會回登入頁，不會自動登入。

    【前端怎麼打】
        frontend/js/api.js 的 API.confirmPasswordReset(token, password)
        #/reset/<token> 設定新密碼頁。前端拿到 token 後會把它從網址列拿掉。

    【誰能打】
        不用登入（忘記密碼的人本來就登不進去）。參數 reset_row=Depends(token_required()) 已經擋好了：
            主體裡的 token 格式不對、找不到、過期、用過 → 400「這個重設連結已經失效，請重新申請一次」
            （四種情況同一句話，不讓人分辨是哪一種）
        所以函式裡不用再檢查 token。reset_row 就是 password_resets 那一列（PasswordReset 物件），
        reset_row.user_id 是要改密碼的人。守衛只檢查、不作廢：used_at 要在這支裡設。

    【請求主體】body 是 PasswordResetConfirmIn（app/schemas/auth.py）
        欄位      型別  必填  說明
        token     字串  是    信裡連結 #/reset/ 後面那一段（守衛已經驗過）
        password  字串  是    新密碼，規則同註冊
        範例：{"token": "1mO04jDjqJpRQT4V6_buPYtuq5EAZkNb8rJdCcnx_hY", "password": "efgh5678"}

    【成功回應】狀態碼 200
        {"ok": true}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                            detail
        400     token 找不到、過期、用過、格式不對  這個重設連結已經失效，請重新申請一次（守衛回）
        422     新密碼太弱                          （passwords 丟出來的那句話）

    【會用到的資料表】
        表               讀／寫  用來做什麼
        users            寫      新的密碼雜湊
        password_resets  寫      used_at = 現在（只能用一次）
        sessions         寫      這個人所有還沒撤銷的都撤銷
        audit_logs       寫      reset_password

    【每一步用的工具與資料庫方法】
        步驟          呼叫                                    做什麼
        1 新密碼      passwords.hash_password(body.password)  太弱丟 WeakPassword
        2 同一個交易  crud.save(User, {"id": reset_row.user_id, "password_hash": …}, db=db)  換密碼
                      crud.save(PasswordReset, {"id": reset_row.id, "used_at": now}, db=db)  連結作廢
                      crud.save(UserSession, {"revoked_at": now}, where={"user_id": …, "revoked_at__isnull": True}, db=db)  所有裝置登出
                      db.commit()                             三件事一起寫進去
        ⚠️ used_at 一定要跟改密碼在同一個交易：分開的話，改到一半失敗，連結可能被用第二次。

    【寫法步驟】
        1. 新密碼檢查強度、算雜湊（422）
        2. 改密碼、連結作廢、所有 sessions 撤銷、寫稽核
        3. db.commit()，回 {"ok": true}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            import logging
            import uuid
            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import guest_only, login_required, token_required, visible_scope
            from app.models import (
                AuditLog, Family, FamilyMember, Group, GroupMember, Guardianship, PasswordReset, SavingsGoal, User, UserSession,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.auth import AvatarIn, FinanceIn, LoginIn, LogoutIn, PasswordChangeIn, PasswordResetConfirmIn, PasswordResetIn, ProfilePatchIn, RefreshIn, RegisterIn, VerifyEmailIn, VerifyPasswordIn
            from app.toolkit import account, crud, email_verify, errors, images, mailer, password_reset, passwords, period, profile, roles, security, theme, tokens
            from app.toolkit.config import settings
            from app.toolkit.db import get_db
            from app.toolkit.deps import current_token_payload

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 新密碼：檢查強度，只存雜湊
            try:
                hashed = passwords.hash_password(body.password)
            except passwords.WeakPassword as exc:
                raise errors.unprocessable(str(exc)) from None

            # 2. 同一個交易：換密碼、連結作廢、這個人所有裝置登出
            now = datetime.now(timezone.utc)
            crud.save(User, {"id": reset_row.user_id, "password_hash": hashed}, db=db)
            crud.save(PasswordReset, {"id": reset_row.id, "used_at": now}, db=db)
            crud.save(UserSession, {"revoked_at": now},
                      where={"user_id": reset_row.user_id, "revoked_at__isnull": True}, db=db)
            crud.save(AuditLog, {"actor_id": reset_row.user_id, "action": "reset_password", "target_type": "user",
                                 "target_id": reset_row.user_id}, db=db)
            db.commit()
            return {"ok": True}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/auth/password-reset/confirm
        3. 這支不用登入，不用按 Authorize（token 放在請求主體裡）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               信裡的 token ＋ 新密碼  → 200
               同一個 token 再用一次   → 400
               亂打的 token            → 400，而且是同一句話
               新密碼 "1234"           → 422，而且 token 還能用
        5. 用新密碼登入 → 200；原本登入中的裝置換 token 時被登出
        6. 前端改成連你的後端（frontend/index.html 的 api-base），點信裡的連結、設新密碼，回到登入頁
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "confirm_password_reset and 你的"，要全部通過
    """
    # 1. 新密碼：檢查強度，只存雜湊
    try:
        hashed = passwords.hash_password(body.password)
    except passwords.WeakPassword as exc:
        raise errors.unprocessable(str(exc)) from None

    # 2. 同一個交易：換密碼、連結作廢、這個人所有裝置登出
    now = datetime.now(timezone.utc)
    crud.save(User, {"id": reset_row.user_id, "password_hash": hashed}, db=db)
    crud.save(PasswordReset, {"id": reset_row.id, "used_at": now}, db=db)
    crud.save(UserSession, {"revoked_at": now},
              where={"user_id": reset_row.user_id, "revoked_at__isnull": True}, db=db)
    crud.save(AuditLog, {"actor_id": reset_row.user_id, "action": "reset_password", "target_type": "user",
                         "target_id": reset_row.user_id}, db=db)
    db.commit()
    return {"ok": True}


@router.post("/auth/verify-email", summary="點驗證信的連結：確認 email 是本人的")
def verify_email(body: VerifyEmailIn, request: Request, db: Session = Depends(get_db)):
    """點驗證信的連結：確認 email 是本人的

    POST /api/auth/verify-email

    【這支做什麼】
        使用者點了驗證信裡的連結（#/verify/<權杖>），前端把權杖送來：對的話把 users.email_verified_at 填上現在，
        而且**第一次點的時候順便登入**（回 token）：註冊完不登入，點了信才接著做個人化設定。
        ⚠️ 只有第一次點會登入：已經驗證過的再點一次只回確認好了——信可能被轉寄，連結不能變成一直有效的登入連結。
        ⚠️ 停權的人只驗證、不登入。
        ⚠️ 權杖過期就進不來：簽的時候寫了到期時間（EMAIL_VERIFY_MINUTES，預設 24 小時），過了 read_token 直接丟錯。
        ⚠️ 權杖裡放了 email：使用者改過 email 的話，舊信的連結對不上，一樣失效。
        ⚠️ 點兩次不會出錯：已經驗證過的，再點一次也回成功（loggedIn false），不會改掉第一次的時間。
        不另外開表存權杖：第一次點才登入，而第一次點的一定是收到信的人（跟忘記密碼的重設連結一樣，信箱就是鑰匙）。

    【前端怎麼打】
        frontend/js/api.js 的 API.verifyEmail(token)
        #/verify/<權杖> 這一頁一打開就呼叫。不用登入（常常是在手機的信箱 App 裡點開的）。

    【誰能打】
        任何人都能打，不用登入（上面沒有守衛）：拿得出有效權杖的人，就是收得到那封信的人。
        另外收一個 request（FastAPI 的 Request）：第一次點要登入，記下這一台的瀏覽器與 IP 的雜湊（同登入）。

    【請求主體】body 是 VerifyEmailIn（app/schemas/auth.py）
        欄位   型別  必填  說明
        token  字串  是    連結 #/verify/ 後面那一段
        範例：{"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9…"}

    【成功回應】狀態碼 200
        第一次點：{"ok": true, "email": "daming@wang.tw", "loggedIn": true,
                   "accessToken": "eyJ…", "refreshToken": "eyJ…", "expiresIn": 1800,
                   "user": {"id": "3", "name": "王大明", "email": "daming@wang.tw", "onboardedAt": null}}
        再點一次、或停權中：{"ok": true, "email": "daming@wang.tw", "loggedIn": false}
        · user 只放前端換頁要用的；完整的打 GET /api/auth/me

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                              detail
        400     權杖過期                              這個驗證連結過期了，登入後可以在總覽重寄一封
        400     簽章不對、不是驗證信的權杖、格式不對  這個驗證連結無效，登入後可以在總覽重寄一封
        400     帳號不在了、email 已經改掉            這個驗證連結無效，登入後可以在總覽重寄一封
        422     沒帶 token                            （FastAPI 擋）

    【會用到的資料表】
        表     讀／寫  用來做什麼
        users     讀＋寫  權杖裡的那個人；email_verified_at、last_login_at = 現在
        sessions  寫      第一次點：這一台的登入工作階段（只存 refresh token 的指紋）

    【每一步用的工具與資料庫方法】
        步驟    呼叫                                        做什麼
        1 權杖  email_verify.read_token(body.token)         回傳 (user_id, email)；過期、無效丟 email_verify.InvalidToken
        2 帳號  crud.get(User, user_id, db=db)              找不到是 None
        3 寫入  crud.save(User, {"id": …, "email_verified_at": 現在}, db=db)
        4 登入  tokens.make_refresh_token／fingerprint／make_access_token、crud.save(UserSession, {…})  同登入
                security.source_of(request)                  來源 IP
                db.commit()

    【寫法步驟】
        1. 解開權杖，過期或無效 → 400
        2. 帳號不在、email 對不上 → 400
        3. 已經驗證過 → 回 {"ok": true, "email": …, "loggedIn": false}
        4. 第一次：填上時間；停權中就只回 loggedIn false；不然建一列 sessions、發兩張 token，回 loggedIn true

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            import logging
            import uuid
            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import guest_only, login_required, token_required, visible_scope
            from app.models import (
                AuditLog, Family, FamilyMember, Group, GroupMember, Guardianship, PasswordReset, SavingsGoal, User, UserSession,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.auth import AvatarIn, FinanceIn, LoginIn, LogoutIn, PasswordChangeIn, PasswordResetConfirmIn, PasswordResetIn, ProfilePatchIn, RefreshIn, RegisterIn, VerifyEmailIn, VerifyPasswordIn
            from app.toolkit import account, crud, email_verify, errors, images, mailer, password_reset, passwords, period, profile, roles, security, theme, tokens
            from app.toolkit.config import settings
            from app.toolkit.db import get_db
            from app.toolkit.deps import current_token_payload

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 解開權杖：簽章不對、過期、不是驗證信的權杖 → 400（過期的權杖從這裡就進不去了）
            try:
                user_id, email = email_verify.read_token(body.token)
            except email_verify.InvalidToken as exc:
                raise errors.bad_request("%s，登入後可以在總覽重寄一封" % exc) from None

            # 2. 帳號還在、email 沒改過才算數（改過 email，舊信裡的連結自然失效）
            user = crud.get(User, user_id, db=db)
            if user is None or user.email != email:
                raise errors.bad_request("這個驗證連結無效，登入後可以在總覽重寄一封")

            # 3. 已經驗證過：只回確認好了，**不登入**（第二次以後的點擊可能是轉寄出去的信）
            if user.email_verified_at is not None:
                return {"ok": True, "email": user.email, "loggedIn": False}

            # 4. 第一次點：填上驗證時間，順便登入——註冊完沒有登入，點了信才接著做個人化設定。停權的人只驗證、不登入
            now = datetime.now(timezone.utc)
            crud.save(User, {"id": user.id, "email_verified_at": now}, db=db)
            if user.suspended_at is not None:
                db.commit()
                return {"ok": True, "email": user.email, "loggedIn": False}
            refresh, expires = tokens.make_refresh_token(user.id)
            ip = security.source_of(request)
            session = crud.save(UserSession, {
                "user_id": user.id,
                "refresh_token_hash": tokens.fingerprint(refresh),
                "user_agent": request.headers.get("user-agent", "")[:300],
                "ip_hash": tokens.fingerprint(ip) if ip else None,
                "expires_at": expires,
                "last_seen_at": now,
            }, db=db)
            crud.save(User, {"id": user.id, "last_login_at": now}, db=db)
            db.commit()
            return {
                "ok": True,
                "email": user.email,
                "loggedIn": True,
                "accessToken": tokens.make_access_token(user.id, extra={"sid": str(session.id)}),
                "refreshToken": refresh,
                "expiresIn": settings.access_token_minutes * 60,
                "user": {"id": str(user.id), "name": user.display_name, "email": user.email,
                         "onboardedAt": None if user.onboarded_at is None else security.aware(user.onboarded_at).isoformat()},
            }

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 先打 POST /api/auth/register 註冊一個帳號；backend/.env 填了 BREVO_API_KEY 的話，信箱會收到驗證信
           （沒填的話，在 python 裡 email_verify.make_token(他的 id, 他的 email) 自己簽一張）
        3. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/auth/verify-email，不用按 Authorize
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               信裡的權杖                            → 200，loggedIn true、有 token；GET /api/auth/me 的 emailVerified 變 true
               同一個權杖再送一次                    → 200，loggedIn false、沒有 token
               隨便打幾個字                          → 400「這個驗證連結無效…」
               .env 設 EMAIL_VERIFY_MINUTES=1，等 1 分鐘再送  → 400「這個驗證連結過期了…」
        5. 前端：點信裡的按鈕，#/verify/… 確認好了就登入、接著進到「個人化設定」
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "verify_email and 你的"，要全部通過
    """
    # 1. 解開權杖：簽章不對、過期、不是驗證信的權杖 → 400（過期的權杖從這裡就進不去了）
    try:
        user_id, email = email_verify.read_token(body.token)
    except email_verify.InvalidToken as exc:
        raise errors.bad_request("%s，登入後可以在總覽重寄一封" % exc) from None

    # 2. 帳號還在、email 沒改過才算數（改過 email，舊信裡的連結自然失效）
    user = crud.get(User, user_id, db=db)
    if user is None or user.email != email:
        raise errors.bad_request("這個驗證連結無效，登入後可以在總覽重寄一封")

    # 3. 已經驗證過：只回確認好了，**不登入**（第二次以後的點擊可能是轉寄出去的信）
    if user.email_verified_at is not None:
        return {"ok": True, "email": user.email, "loggedIn": False}

    # 4. 第一次點：填上驗證時間，順便登入——註冊完沒有登入，點了信才接著做個人化設定。停權的人只驗證、不登入
    now = datetime.now(timezone.utc)
    crud.save(User, {"id": user.id, "email_verified_at": now}, db=db)
    if user.suspended_at is not None:
        db.commit()
        return {"ok": True, "email": user.email, "loggedIn": False}
    refresh, expires = tokens.make_refresh_token(user.id)
    ip = security.source_of(request)
    session = crud.save(UserSession, {
        "user_id": user.id,
        "refresh_token_hash": tokens.fingerprint(refresh),
        "user_agent": request.headers.get("user-agent", "")[:300],
        "ip_hash": tokens.fingerprint(ip) if ip else None,
        "expires_at": expires,
        "last_seen_at": now,
    }, db=db)
    crud.save(User, {"id": user.id, "last_login_at": now}, db=db)
    db.commit()
    return {
        "ok": True,
        "email": user.email,
        "loggedIn": True,
        "accessToken": tokens.make_access_token(user.id, extra={"sid": str(session.id)}),
        "refreshToken": refresh,
        "expiresIn": settings.access_token_minutes * 60,
        "user": {"id": str(user.id), "name": user.display_name, "email": user.email,
                 "onboardedAt": None if user.onboarded_at is None else security.aware(user.onboarded_at).isoformat()},
    }


@router.post("/auth/verify-email/resend", summary="重寄驗證信")
@login_required
def resend_verify_email(me: User, background: BackgroundTasks, db: Session = Depends(get_db)):
    """重寄驗證信

    POST /api/auth/verify-email/resend

    【這支做什麼】
        還沒驗證 email 的人（總覽上的提醒按「重寄驗證信」），再寄一封新的驗證信給他自己。
        ⚠️ 只寄給登入的這個人自己的 email：不收收件人，不然就變成可以拿我們的信箱幫人寄信。
        ⚠️ 冷卻 60 秒（email_verify.COOLDOWN_SECONDS）：Brevo 免費方案一天只有 300 封。
        已經驗證過：不寄，回 sent false。舊信的連結不會作廢（到期時間一到自己失效）。

    【前端怎麼打】
        frontend/js/api.js 的 API.resendVerifyEmail()
        總覽上方「還沒確認 email」的提醒，按「重寄驗證信」。前端把回應的 message 顯示出來。

    【誰能打】
        登入、沒被停權就能打（平台管理員也可以）。上面的 @login_required 已經擋好了：
            沒登入、token 過期 → 401；被停權 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id                    他的 id
            me.email                 他的 email（信就寄到這裡）
            me.email_verified_at     驗證過的時間（還沒驗證是 None）
            me.email_verify_sent_at  上一封驗證信的時間
        另外收一個 background（FastAPI 的 BackgroundTasks）：回應送出去之後才寄信。

    【請求主體】沒有

    【成功回應】狀態碼 200
        {"ok": true, "sent": true, "message": "驗證信已經寄到 daming@wang.tw，24 小時內有效"}
        已經驗證過：{"ok": true, "sent": false, "message": "你的 email 已經驗證過了"}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候          detail
        429     60 秒內寄過一封  驗證信剛寄出，請 1 分鐘後再試
        · 寄信失敗不回錯（只記 log）：跟忘記密碼一樣，回應不等 Brevo。

    【會用到的資料表】
        表     讀／寫  用來做什麼
        users  讀＋寫  驗證過沒、上一封的時間；email_verify_sent_at = 現在

    【每一步用的工具與資料庫方法】
        步驟    呼叫                                                        做什麼
        2 冷卻  email_verify.should_resend(me.email_verify_sent_at, now)    沒寄過、或隔了 60 秒以上回 True
                HTTPException(status_code=429, detail="…")                  errors 裡沒有 429，直接用 FastAPI 的
        3 寄信  crud.save(User, {"id": me.id, "email_verify_sent_at": now}, db=db)＋db.commit()  先記時間，冷卻才算得到
                email_verify.make_token(me.id, me.email)                    新的權杖（重新算到期時間）
                email_verify.verify_link(settings.app_base_url, 權杖)       <前端網址>/#/verify/<權杖>
                email_verify.mail_content(名字, 連結)                       回傳（主旨, 純文字, HTML）
                background.add_task(send)                                   回應送出去之後才跑 send()
                email_verify.ttl_text()                                     「24 小時」這種給人看的有效期
        ⚠️ send() 裡用的收件人、名字要先存成區域變數：背景跑的時候，這次請求的資料庫連線已經關了。

    【寫法步驟】
        1. 已經驗證過 → 回 sent false
        2. 60 秒內寄過 → 429
        3. 記下時間、commit，排進背景寄出，回 sent true

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            import logging
            import uuid
            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import guest_only, login_required, token_required, visible_scope
            from app.models import (
                AuditLog, Family, FamilyMember, Group, GroupMember, Guardianship, PasswordReset, SavingsGoal, User, UserSession,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.auth import AvatarIn, FinanceIn, LoginIn, LogoutIn, PasswordChangeIn, PasswordResetConfirmIn, PasswordResetIn, ProfilePatchIn, RefreshIn, RegisterIn, VerifyEmailIn, VerifyPasswordIn
            from app.toolkit import account, crud, email_verify, errors, images, mailer, password_reset, passwords, period, profile, roles, security, theme, tokens
            from app.toolkit.config import settings
            from app.toolkit.db import get_db
            from app.toolkit.deps import current_token_payload

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 已經驗證過：不用寄
            if me.email_verified_at is not None:
                return {"ok": True, "sent": False, "message": "你的 email 已經驗證過了"}

            # 2. 冷卻：剛寄過就不寄（不然 Brevo 每天 300 封的額度會被按光）
            now = datetime.now(timezone.utc)
            if not email_verify.should_resend(me.email_verify_sent_at, now):
                raise HTTPException(status_code=429, detail="驗證信剛寄出，請 1 分鐘後再試")

            # 3. 記下這次寄的時間，回應送出去之後才寄；寄不出去只記 log
            crud.save(User, {"id": me.id, "email_verify_sent_at": now}, db=db)
            db.commit()
            to, who = me.email, me.display_name
            subject, text, html = email_verify.mail_content(
                who, email_verify.verify_link(settings.app_base_url, email_verify.make_token(me.id, to)))

            def send():
                try:
                    mailer.send_mail(to, subject, text, html, to_name=who)
                except (mailer.MailNotConfigured, mailer.MailError) as exc:
                    logging.getLogger("fambudget").warning("驗證信寄不出去：%s", exc)

            background.add_task(send)
            return {"ok": True, "sent": True, "message": "驗證信已經寄到 %s，%s內有效" % (to, email_verify.ttl_text())}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload；backend/.env 要先填 BREVO_API_KEY 與 MAIL_FROM
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/auth/verify-email/resend
        3. 按右上角 Authorize，貼上一個還沒驗證的帳號的 accessToken（剛註冊的就是）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               剛註冊完馬上按        → 429（註冊時已經寄了一封）
               等 1 分鐘再按         → 200，sent true，信箱收到新的一封
               驗證完再按            → 200，sent false
        5. 前端：總覽的提醒按「重寄驗證信」，畫面顯示寄到哪個信箱
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "resend_verify_email and 你的"，要全部通過
    """
    # 1. 已經驗證過：不用寄
    if me.email_verified_at is not None:
        return {"ok": True, "sent": False, "message": "你的 email 已經驗證過了"}

    # 2. 冷卻：剛寄過就不寄（不然 Brevo 每天 300 封的額度會被按光）
    now = datetime.now(timezone.utc)
    if not email_verify.should_resend(me.email_verify_sent_at, now):
        raise HTTPException(status_code=429, detail="驗證信剛寄出，請 1 分鐘後再試")

    # 3. 記下這次寄的時間，回應送出去之後才寄；寄不出去只記 log
    crud.save(User, {"id": me.id, "email_verify_sent_at": now}, db=db)
    db.commit()
    to, who = me.email, me.display_name
    subject, text, html = email_verify.mail_content(
        who, email_verify.verify_link(settings.app_base_url, email_verify.make_token(me.id, to)))

    def send():
        try:
            mailer.send_mail(to, subject, text, html, to_name=who)
        except (mailer.MailNotConfigured, mailer.MailError) as exc:
            logging.getLogger("fambudget").warning("驗證信寄不出去：%s", exc)

    background.add_task(send)
    return {"ok": True, "sent": True, "message": "驗證信已經寄到 %s，%s內有效" % (to, email_verify.ttl_text())}


@router.get("/auth/me/finance", summary="我的理財習慣")
@login_required
def get_finance(me: User, db: Session = Depends(get_db)):
    """我的理財習慣

    GET /api/auth/me/finance

    【這支做什麼】
        我填的理財習慣（風格、在意的目標、固定的財務安排、補充說明），外加三份選項清單。
        這些只當財務建議的「背景」，不是拿來給投資建議的。
        還沒填過：finance 是 null。

    【前端怎麼打】
        frontend/js/api.js 的 API.financeProfile()
        個人化設定第二步、個人資料頁「理財習慣」、財務建議頁（顯示建議參考了什麼）。
        前端檢查回應裡一定要有 finance、styles、goals、habits。

    【誰能打】
        登入、沒被停權就能打（平台管理員也可以）。上面的 @login_required 已經擋好了：
            沒登入、token 過期 → 401；被停權 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【請求參數】沒有

    【成功回應】狀態碼 200
        {"finance": {"style": "balanced", "goals": ["emergency", "travel"], "habits": ["dca"], "note": "每月定期定額 3,000"},
         "styles": [{"id": "safe", "name": "保守", "desc": "先求穩，不追高報酬"}],
         "goals": [{"id": "emergency", "name": "緊急預備金"}],
         "habits": [{"id": "dca", "name": "定期定額"}]}
        · 三份清單是 app/catalog.py 的 FINANCE_STYLES／FINANCE_GOALS／FINANCE_HABITS（跟 data.js 一樣）

    【錯誤回應】
        只有守衛的 401／403，這支本身不會出錯。

    【會用到的資料表】
        表     讀／寫  用來做什麼
        users  讀      finance_style、finance_goals、finance_habits、finance_note（守衛已經把 me 撈好了）

    【每一步用的工具與資料庫方法】
        步驟      呼叫                             做什麼
        1 填過沒  四個欄位有沒有任何一個不是 None  PUT 一定會寫 goals（空的也是 []），所以存過一次就不是 None
        2 清單    catalog.FINANCE_STYLES 等        固定清單，直接回

    【寫法步驟】
        1. 四個欄位都是 None → finance 是 null；不然組成 {style, goals, habits, note}
        2. 跟三份清單一起回傳
        ⚠️ 不用查資料庫，也不用 db.commit()。

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            import logging
            import uuid
            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import guest_only, login_required, token_required, visible_scope
            from app.models import (
                AuditLog, Family, FamilyMember, Group, GroupMember, Guardianship, PasswordReset, SavingsGoal, User, UserSession,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.auth import AvatarIn, FinanceIn, LoginIn, LogoutIn, PasswordChangeIn, PasswordResetConfirmIn, PasswordResetIn, ProfilePatchIn, RefreshIn, RegisterIn, VerifyEmailIn, VerifyPasswordIn
            from app.toolkit import account, crud, email_verify, errors, images, mailer, password_reset, passwords, period, profile, roles, security, theme, tokens
            from app.toolkit.config import settings
            from app.toolkit.db import get_db
            from app.toolkit.deps import current_token_payload

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 存過一次就有值（PUT 一定會寫 goals，空的也是 []）；從來沒存過是 null
            fields = (me.finance_style, me.finance_goals, me.finance_habits, me.finance_note)
            finance = None
            if any(value is not None for value in fields):
                finance = {
                    "style": me.finance_style,
                    "goals": me.finance_goals or [],
                    "habits": me.finance_habits or [],
                    "note": me.finance_note or "",
                }

            # 2. 連同三份選項清單一起回
            return {
                "finance": finance,
                "styles": catalog.FINANCE_STYLES,
                "goals": catalog.FINANCE_GOALS,
                "habits": catalog.FINANCE_HABITS,
            }

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 GET /api/auth/me/finance
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               剛註冊的人      → finance 是 null，三份清單都有
               PUT 過一次之後  → finance 是存進去的那一份
        5. 前端改成連你的後端（frontend/index.html 的 api-base），個人資料頁「理財習慣」要勾出已經選的項目
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "get_finance and 你的"，要全部通過
    """
    # 1. 存過一次就有值（PUT 一定會寫 goals，空的也是 []）；從來沒存過是 null
    fields = (me.finance_style, me.finance_goals, me.finance_habits, me.finance_note)
    finance = None
    if any(value is not None for value in fields):
        finance = {
            "style": me.finance_style,
            "goals": me.finance_goals or [],
            "habits": me.finance_habits or [],
            "note": me.finance_note or "",
        }

    # 2. 連同三份選項清單一起回
    return {
        "finance": finance,
        "styles": catalog.FINANCE_STYLES,
        "goals": catalog.FINANCE_GOALS,
        "habits": catalog.FINANCE_HABITS,
    }


@router.put("/auth/me/finance", summary="改理財習慣")
@login_required
def set_finance(body: FinanceIn, me: User, db: Session = Depends(get_db)):
    """改理財習慣

    PUT /api/auth/me/finance

    【這支做什麼】
        存我的理財習慣（整份換掉，所以是 PUT）。
        ⚠️ 只收清單裡的 id，不認得的丟掉（style 變 null、陣列裡濾掉）：不是防呆——
           這些會進財務建議的 prompt，不能讓使用者自己造 id 把任意文字送進去。
        ⚠️ note 用 profile.clean_note() 洗過（壓掉換行、拿掉像指令的標記、最多 200 字）：
           建議會給監管者看，不處理的話子女可以在說明裡下指令，操控父母看到的內容。

    【前端怎麼打】
        frontend/js/api.js 的 API.setFinanceProfile({ style, goals, habits, note })
        個人化設定第二步、個人資料頁「理財習慣」存檔。回應是存好的那一份。

    【誰能打】
        登入、沒被停權就能打（平台管理員也可以）。上面的 @login_required 已經擋好了：
            沒登入、token 過期 → 401；被停權 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【請求主體】body 是 FinanceIn（app/schemas/auth.py）
        欄位    型別         必填  說明
        style   字串或 null  否    safe／balanced／growth
        goals   字串陣列     否    emergency／house／debt／travel／education／retire
        habits  字串陣列     否    dca／mortgage／insurance／rent
        note    字串         否    補充說明，最多 200 字
        範例：{"style": "balanced", "goals": ["emergency"], "habits": ["dca"], "note": "每月定期定額 3,000"}

    【成功回應】狀態碼 200
        {"style": "balanced", "goals": ["emergency"], "habits": ["dca"], "note": "每月定期定額 3,000"}
        · goals、habits 照清單的順序、不重複

    【錯誤回應】
        只有守衛的 401／403。不認得的 id 不回錯，直接濾掉。

    【會用到的資料表】
        表     讀／寫  用來做什麼
        users  寫      finance_style、finance_goals、finance_habits、finance_note

    【每一步用的工具與資料庫方法】
        步驟     呼叫                                                   做什麼
        1 濾 id  [g["id"] for g in catalog.FINANCE_GOALS if g["id"] in body.goals]  從清單出發挑：順序固定、自然不重複、不認得的進不來
                 profile.clean_note(body.note)                          洗過、最多 200 字
        2 寫回   crud.save(User, {"id": me.id, "finance_…": …}, db=db)  JSON 欄位直接放 list
                 db.commit()                                            寫進去

    【寫法步驟】
        1. style 不在清單裡 → None；goals、habits 只留清單裡有的；note 洗過
        2. 寫回四個欄位（note 是空的存 NULL），db.commit()
        3. 回傳存好的那一份

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            import logging
            import uuid
            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import guest_only, login_required, token_required, visible_scope
            from app.models import (
                AuditLog, Family, FamilyMember, Group, GroupMember, Guardianship, PasswordReset, SavingsGoal, User, UserSession,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.auth import AvatarIn, FinanceIn, LoginIn, LogoutIn, PasswordChangeIn, PasswordResetConfirmIn, PasswordResetIn, ProfilePatchIn, RefreshIn, RegisterIn, VerifyEmailIn, VerifyPasswordIn
            from app.toolkit import account, crud, email_verify, errors, images, mailer, password_reset, passwords, period, profile, roles, security, theme, tokens
            from app.toolkit.config import settings
            from app.toolkit.db import get_db
            from app.toolkit.deps import current_token_payload

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 只收清單裡的 id（從清單出發挑，不認得的自然進不來）；說明洗過
            styles = [s["id"] for s in catalog.FINANCE_STYLES]
            finance = {
                "style": body.style if body.style in styles else None,
                "goals": [g["id"] for g in catalog.FINANCE_GOALS if g["id"] in body.goals],
                "habits": [h["id"] for h in catalog.FINANCE_HABITS if h["id"] in body.habits],
                "note": profile.clean_note(body.note),
            }

            # 2. 寫回去
            crud.save(User, {
                "id": me.id,
                "finance_style": finance["style"],
                "finance_goals": finance["goals"],
                "finance_habits": finance["habits"],
                "finance_note": finance["note"] or None,
            }, db=db)
            db.commit()
            return finance

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 PUT /api/auth/me/finance
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               正常的一份                            → 200，回傳跟送出的一樣
               style 填 "yolo"、goals 加一個 "hack"  → 200，style 是 null、goals 沒有 hack
               note 填 300 個字                      → 200，只剩 200 個字
        5. GET /api/auth/me/finance → 就是剛存的
        6. 前端改成連你的後端（frontend/index.html 的 api-base），個人化設定第二步勾幾個選項，個人資料頁看得到
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "set_finance and 你的"，要全部通過
    """
    # 1. 只收清單裡的 id（從清單出發挑，不認得的自然進不來）；說明洗過
    styles = [s["id"] for s in catalog.FINANCE_STYLES]
    finance = {
        "style": body.style if body.style in styles else None,
        "goals": [g["id"] for g in catalog.FINANCE_GOALS if g["id"] in body.goals],
        "habits": [h["id"] for h in catalog.FINANCE_HABITS if h["id"] in body.habits],
        "note": profile.clean_note(body.note),
    }

    # 2. 寫回去
    crud.save(User, {
        "id": me.id,
        "finance_style": finance["style"],
        "finance_goals": finance["goals"],
        "finance_habits": finance["habits"],
        "finance_note": finance["note"] or None,
    }, db=db)
    db.commit()
    return finance


@router.post("/auth/verify-password", summary="重大操作前再確認一次密碼")
@login_required
def verify_password(body: VerifyPasswordIn, me: User, db: Session = Depends(get_db)):
    """重大操作前再確認一次密碼

    POST /api/auth/verify-password

    【這支做什麼】
        重大操作之前（移出家人、退出或解散家庭、改角色、移除帳本）再確認一次密碼。
        ⚠️ 不發新 token、不改任何狀態，只回對不對。
        ⚠️ 一定要速率限制，不然它就是免費的密碼嘗試器（token 被偷的人可以拿它猜密碼）：
           每錯一次在 audit_logs 記一筆，15 分鐘內錯 5 次就回 429。
        ⚠️ 密碼不對回 400，不是 401：401 會讓前端以為 token 過期，每錯一次就白白續期一次。

    【前端怎麼打】
        frontend/js/api.js 的 API.verifyPassword(password)
        各個確認視窗按下「確定」時先呼叫，成功才真的去做那件事。

    【誰能打】
        登入、沒被停權就能打（平台管理員也可以）。上面的 @login_required 已經擋好了：
            沒登入、token 過期 → 401；被停權 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【請求主體】body 是 VerifyPasswordIn（app/schemas/auth.py）
        欄位      型別  必填  說明
        password  字串  是    目前的密碼
        範例：{"password": "abcd1234"}

    【成功回應】狀態碼 200
        {"ok": true}

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候            detail
        400     密碼不對            密碼不正確
        429     15 分鐘內錯了 5 次  密碼錯太多次了，請 15 分鐘後再試

    【會用到的資料表】
        表          讀／寫  用來做什麼
        audit_logs       讀＋寫  數最近 15 分鐘錯了幾次；錯一次記一筆 verify_password_failed
        security_events  寫      錯到第 5 次（開始鎖）記一筆 verify_locked

    【每一步用的工具與資料庫方法】
        步驟    呼叫                                                        做什麼
        1 限速  crud.count(AuditLog, {"actor_id": me.id, "action": "verify_password_failed", "created_at__gte": 15 分鐘前}, db=db)  最近錯了幾次
                HTTPException(status_code=429, detail="…")                  errors 裡沒有 429，直接用 FastAPI 的
        2 比對  passwords.verify_password(body.password, me.password_hash)  對回 True
        3 記錯  crud.save(AuditLog, {…}, db=db)＋db.commit()                要在丟 400 之前 commit，不然這一次不會被算到
                security.record("verify_locked", db=db, user_id=me.id, …)  錯到第 5 次時記：平台管理頁的安全事件
        · 為什麼記在 audit_logs：資料在資料庫裡，重開伺服器、開好幾台都算得到；平台管理員也看得到有人在猜密碼。

    【寫法步驟】
        1. 最近 15 分鐘錯了 5 次以上 → 429（這時候連比對都不做）
        2. 密碼對 → 回 {"ok": true}
        3. 密碼錯 → 記一筆、commit，回 400

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            import logging
            import uuid
            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import guest_only, login_required, token_required, visible_scope
            from app.models import (
                AuditLog, Family, FamilyMember, Group, GroupMember, Guardianship, PasswordReset, SavingsGoal, User, UserSession,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.auth import AvatarIn, FinanceIn, LoginIn, LogoutIn, PasswordChangeIn, PasswordResetConfirmIn, PasswordResetIn, ProfilePatchIn, RefreshIn, RegisterIn, VerifyEmailIn, VerifyPasswordIn
            from app.toolkit import account, crud, email_verify, errors, images, mailer, password_reset, passwords, period, profile, roles, security, theme, tokens
            from app.toolkit.config import settings
            from app.toolkit.db import get_db
            from app.toolkit.deps import current_token_payload

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 速率限制：15 分鐘內錯 5 次就先停
            since = datetime.now(timezone.utc) - timedelta(minutes=15)
            failures = crud.count(AuditLog, {"actor_id": me.id, "action": "verify_password_failed",
                                             "created_at__gte": since}, db=db)
            if failures >= 5:
                raise HTTPException(status_code=429, detail="密碼錯太多次了，請 15 分鐘後再試")

            # 2. 對了只回 ok（不發新 token、不改任何狀態）
            if passwords.verify_password(body.password, me.password_hash):
                return {"ok": True}

            # 3. 錯了記一筆（先存起來才算得到），回 400（不是 401）
            crud.save(AuditLog, {"actor_id": me.id, "action": "verify_password_failed", "target_type": "user",
                                 "target_id": me.id}, db=db)
            if failures + 1 >= 5:
                # 這一次剛好鎖住：記成安全事件，平台管理頁才看得到「有人拿著登入狀態在猜密碼」
                security.record("verify_locked", db=db, user_id=me.id, detail="15 分鐘內錯了 5 次")
            db.commit()
            raise errors.bad_request("密碼不正確")

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 POST /api/auth/verify-password
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               正確的密碼                 → 200
               錯的密碼                   → 400「密碼不正確」
               連續錯 5 次之後，就算打對  → 429
        5. 前端改成連你的後端（frontend/index.html 的 api-base），家庭成員頁「移出家庭」的確認視窗，打錯密碼會提示、打對才會繼續
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "verify_password and 你的"，要全部通過
    """
    # 1. 速率限制：15 分鐘內錯 5 次就先停
    since = datetime.now(timezone.utc) - timedelta(minutes=15)
    failures = crud.count(AuditLog, {"actor_id": me.id, "action": "verify_password_failed",
                                     "created_at__gte": since}, db=db)
    if failures >= 5:
        raise HTTPException(status_code=429, detail="密碼錯太多次了，請 15 分鐘後再試")

    # 2. 對了只回 ok（不發新 token、不改任何狀態）
    if passwords.verify_password(body.password, me.password_hash):
        return {"ok": True}

    # 3. 錯了記一筆（先存起來才算得到），回 400（不是 401）
    crud.save(AuditLog, {"actor_id": me.id, "action": "verify_password_failed", "target_type": "user",
                         "target_id": me.id}, db=db)
    if failures + 1 >= 5:
        # 這一次剛好鎖住：記成安全事件，平台管理頁才看得到「有人拿著登入狀態在猜密碼」
        security.record("verify_locked", db=db, user_id=me.id, detail="15 分鐘內錯了 5 次")
    db.commit()
    raise errors.bad_request("密碼不正確")


@router.get("/auth/sessions", summary="登入中的裝置")
@login_required
def list_sessions(me: User, payload: dict = Depends(current_token_payload), db: Session = Depends(get_db)):
    """登入中的裝置

    GET /api/auth/sessions

    【這支做什麼】
        列出我登入中的裝置（沒撤銷、沒過期的 sessions），標出哪一台是現在這一台。
        ⚠️ 不回 IP（資料表只存 ip_hash）。device 只給粗略的分類。

    【前端怎麼打】
        frontend/js/api.js 的 API.sessions()
        個人資料頁「登入中的裝置」。前端檢查回應裡一定要有 sessions。
        服務暫時叫不動（503）時，前端只列這一台頂著。還沒做（501）不頂，照實壞掉。

    【誰能打】
        登入、沒被停權就能打（平台管理員也可以）。上面的 @login_required 已經擋好了：
            沒登入、token 過期 → 401；被停權 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）
        另外收一個 payload=Depends(current_token_payload)：比對 sid，標出現在這一台。

    【請求參數】沒有

    【成功回應】狀態碼 200
        {"sessions": [{"id": "7f3c…", "device": "電腦瀏覽器", "current": true, "lastActiveAt": "2026-09-14T13:20:05Z"}]}
        · device：User-Agent 有 iPhone／iPad／Android → 手機瀏覽器；有其他內容 → 電腦瀏覽器；空的 → 不明裝置
        · 新登入的在前

    【錯誤回應】
        只有守衛的 401／403，這支本身不會出錯。

    【會用到的資料表】
        表        讀／寫  用來做什麼
        sessions  讀      我還有效的登入

    【每一步用的工具與資料庫方法】
        步驟        呼叫                                                    做什麼
        1 查        crud.find(UserSession, {"user_id": me.id, "revoked_at__isnull": True, "expires_at__gt": now}, order_by="-issued_at", db=db)  還有效的
        2 現在這台  payload.get("sid")                                      access token 裡的 sessions.id（字串）
                    any(k in agent for k in ("iPhone", "iPad", "Android"))  有任何一個字出現就是手機

    【寫法步驟】
        1. 查我還有效的 sessions，新的在前
        2. 一台一台轉成 {id, device, current, lastActiveAt}（最後活動時間沒有就用登入時間，轉成 UTC 的 Z 格式）
        3. 回傳 {"sessions": [...]}
        ⚠️ 只讀不寫，不用 db.commit()。

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            import logging
            import uuid
            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import guest_only, login_required, token_required, visible_scope
            from app.models import (
                AuditLog, Family, FamilyMember, Group, GroupMember, Guardianship, PasswordReset, SavingsGoal, User, UserSession,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.auth import AvatarIn, FinanceIn, LoginIn, LogoutIn, PasswordChangeIn, PasswordResetConfirmIn, PasswordResetIn, ProfilePatchIn, RefreshIn, RegisterIn, VerifyEmailIn, VerifyPasswordIn
            from app.toolkit import account, crud, email_verify, errors, images, mailer, password_reset, passwords, period, profile, roles, security, theme, tokens
            from app.toolkit.config import settings
            from app.toolkit.db import get_db
            from app.toolkit.deps import current_token_payload

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 還有效的登入（沒撤銷、沒過期），新的在前
            rows = crud.find(UserSession, {"user_id": me.id, "revoked_at__isnull": True,
                                           "expires_at__gt": datetime.now(timezone.utc)}, order_by="-issued_at", db=db)

            # 2. 一台一台轉成前端要的樣子（不回 IP）
            out = []
            for s in rows:
                agent = s.user_agent or ""
                if any(k in agent for k in ("iPhone", "iPad", "Android")):
                    device = "手機瀏覽器"
                elif agent:
                    device = "電腦瀏覽器"
                else:
                    device = "不明裝置"
                seen = s.last_seen_at or s.issued_at
                if seen.tzinfo is None:
                    seen = seen.replace(tzinfo=timezone.utc)                 # SQLite 讀回來沒有時區
                out.append({
                    "id": str(s.id),
                    "device": device,
                    "current": str(s.id) == payload.get("sid"),
                    "lastActiveAt": seen.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                })
            return {"sessions": out}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 GET /api/auth/sessions
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               用兩個瀏覽器各登入一次再打  → 兩筆，其中一筆 current 是 true
               其中一台登出後再打          → 剩一筆
        5. 前端改成連你的後端（frontend/index.html 的 api-base），個人資料頁「登入中的裝置」列出兩台，標出「這台裝置」
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "list_sessions and 你的"，要全部通過
    """
    # 1. 還有效的登入（沒撤銷、沒過期），新的在前
    rows = crud.find(UserSession, {"user_id": me.id, "revoked_at__isnull": True,
                                   "expires_at__gt": datetime.now(timezone.utc)}, order_by="-issued_at", db=db)

    # 2. 一台一台轉成前端要的樣子（不回 IP）
    out = []
    for s in rows:
        agent = s.user_agent or ""
        if any(k in agent for k in ("iPhone", "iPad", "Android")):
            device = "手機瀏覽器"
        elif agent:
            device = "電腦瀏覽器"
        else:
            device = "不明裝置"
        seen = s.last_seen_at or s.issued_at
        if seen.tzinfo is None:
            seen = seen.replace(tzinfo=timezone.utc)                 # SQLite 讀回來沒有時區
        out.append({
            "id": str(s.id),
            "device": device,
            "current": str(s.id) == payload.get("sid"),
            "lastActiveAt": seen.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        })
    return {"sessions": out}


@router.put("/auth/me/avatar", summary="上傳大頭貼")
@login_required
def upload_avatar(body: AvatarIn, me: User, db: Session = Depends(get_db)):
    """上傳大頭貼

    PUT /api/auth/me/avatar

    【這支做什麼】
        上傳大頭貼（前端已經縮到 256×256），存進資料庫（users.avatar_bytes／avatar_mime）。
        ⚠️ 不存檔案系統：Render 的磁碟是暫時的，重新部署就不見了。
        ⚠️ 不信副檔名、也不信 data URI 開頭寫的型別：toolkit/images.py 看的是檔案開頭的識別位元組，偽造不了。
        ⚠️ 大小上限 200 KB，超過回 422——沒有上限的話，有人上傳 500 MB 就能把服務打掛。
        用 PUT：「把大頭貼設定成這張」，做幾次結果都一樣。

    【前端怎麼打】
        frontend/js/api.js 的 API.uploadAvatar(dataUri)，主體是 {"image": dataUri}
        個人資料頁選了圖片之後（前端先縮圖、轉 JPEG）。

    【誰能打】
        登入、沒被停權就能打（平台管理員也可以）。上面的 @login_required 已經擋好了：
            沒登入、token 過期 → 401；被停權 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【請求主體】body 是 AvatarIn（app/schemas/auth.py）
        欄位   型別  必填  說明
        image  字串  是    data URI：data:image/jpeg;base64,……（只收 JPEG、PNG、WebP，最多 200 KB）
        範例：{"image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ…"}

    【成功回應】狀態碼 200
        {"avatarUrl": "data:image/jpeg;base64,/9j/4AAQ…", "avatar": "明"}
        · avatarUrl 有值，前端就改用圖片；avatar（名字最後一個字）保留，沒圖的時候用

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                    detail
        422     不是 data URI、base64 壞掉  格式不正確，需要 data URI（images 丟出來的那句話）
        422     超過 200 KB                 圖片太大了，最多 200 KB，這張是 293 KB
        422     內容不是 JPEG／PNG／WebP    這不是有效的圖片檔（只接受 JPEG、PNG、WebP）

    【會用到的資料表】
        表     讀／寫  用來做什麼
        users  寫      avatar_bytes、avatar_mime

    【每一步用的工具與資料庫方法】
        步驟        呼叫                              做什麼
        1 拆開驗證  images.from_data_uri(body.image)  回傳（位元組, 真正的型別）；格式、大小、內容不對丟 InvalidImage
        2 存        crud.save(User, {"id": me.id, "avatar_bytes": data, "avatar_mime": mime}, db=db)  存進資料庫
                    db.commit()                       寫進去
        3 回傳      images.to_data_uri(data, mime)    用「重新嗅探出來的型別」組回 data URI

    【寫法步驟】
        1. from_data_uri 拆開並驗證（422）
        2. 存 avatar_bytes、avatar_mime，db.commit()
        3. 回 {avatarUrl, avatar}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            import logging
            import uuid
            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import guest_only, login_required, token_required, visible_scope
            from app.models import (
                AuditLog, Family, FamilyMember, Group, GroupMember, Guardianship, PasswordReset, SavingsGoal, User, UserSession,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.auth import AvatarIn, FinanceIn, LoginIn, LogoutIn, PasswordChangeIn, PasswordResetConfirmIn, PasswordResetIn, ProfilePatchIn, RefreshIn, RegisterIn, VerifyEmailIn, VerifyPasswordIn
            from app.toolkit import account, crud, email_verify, errors, images, mailer, password_reset, passwords, period, profile, roles, security, theme, tokens
            from app.toolkit.config import settings
            from app.toolkit.db import get_db
            from app.toolkit.deps import current_token_payload

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 拆開並驗證：看檔案開頭的位元組，不信宣告的型別；超過 200 KB 擋掉
            try:
                data, mime = images.from_data_uri(body.image)
            except images.InvalidImage as exc:
                raise errors.unprocessable(str(exc)) from None

            # 2. 存進資料庫（不存檔案系統）
            crud.save(User, {"id": me.id, "avatar_bytes": data, "avatar_mime": mime}, db=db)
            db.commit()
            return {"avatarUrl": images.to_data_uri(data, mime), "avatar": me.display_name[-1:]}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 PUT /api/auth/me/avatar
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               一張小的 JPEG 轉成 data URI                        → 200，avatarUrl 有值
               把一段文字用 base64 包成 data:image/jpeg;base64,…  → 422
               超過 200 KB 的圖                                   → 422
        5. GET /api/auth/me → user.avatarUrl 就是這張
        6. 前端改成連你的後端（frontend/index.html 的 api-base），個人資料頁換大頭貼，右上角頭像跟著換
        7. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "upload_avatar and 你的"，要全部通過
    """
    # 1. 拆開並驗證：看檔案開頭的位元組，不信宣告的型別；超過 200 KB 擋掉
    try:
        data, mime = images.from_data_uri(body.image)
    except images.InvalidImage as exc:
        raise errors.unprocessable(str(exc)) from None

    # 2. 存進資料庫（不存檔案系統）
    crud.save(User, {"id": me.id, "avatar_bytes": data, "avatar_mime": mime}, db=db)
    db.commit()
    return {"avatarUrl": images.to_data_uri(data, mime), "avatar": me.display_name[-1:]}


@router.delete("/auth/me/avatar", summary="移除大頭貼")
@login_required
def delete_avatar(me: User, db: Session = Depends(get_db)):
    """移除大頭貼

    DELETE /api/auth/me/avatar

    【這支做什麼】
        移除大頭貼：avatar_bytes、avatar_mime 設 NULL，前端退回文字頭像。
        沒有大頭貼也是合法狀態：本來就沒有，照樣回成功，不要回 404。

    【前端怎麼打】
        frontend/js/api.js 的 API.deleteAvatar()
        個人資料頁「移除大頭貼」。

    【誰能打】
        登入、沒被停權就能打（平台管理員也可以）。上面的 @login_required 已經擋好了：
            沒登入、token 過期 → 401；被停權 → 403
        所以函式裡不用再檢查身分。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）
            me.family_role   'parent'／'child'（還沒加入家庭是 None）

    【請求主體】沒有

    【成功回應】狀態碼 200
        {"avatarUrl": null, "avatar": "明"}

    【錯誤回應】
        只有守衛的 401／403，這支本身不會出錯。

    【會用到的資料表】
        表     讀／寫  用來做什麼
        users  寫      avatar_bytes、avatar_mime 設 NULL

    【每一步用的工具與資料庫方法】
        步驟    呼叫         做什麼
        1 清掉  crud.save(User, {"id": me.id, "avatar_bytes": None, "avatar_mime": None}, db=db)  帶主鍵改那一個人；None 就是存 NULL
                db.commit()  寫進去

    【寫法步驟】
        1. 兩個欄位設 NULL，db.commit()
        2. 回 {"avatarUrl": null, "avatar": 名字最後一個字}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            import logging
            import uuid
            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import guest_only, login_required, token_required, visible_scope
            from app.models import (
                AuditLog, Family, FamilyMember, Group, GroupMember, Guardianship, PasswordReset, SavingsGoal, User, UserSession,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.auth import AvatarIn, FinanceIn, LoginIn, LogoutIn, PasswordChangeIn, PasswordResetConfirmIn, PasswordResetIn, ProfilePatchIn, RefreshIn, RegisterIn, VerifyEmailIn, VerifyPasswordIn
            from app.toolkit import account, crud, email_verify, errors, images, mailer, password_reset, passwords, period, profile, roles, security, theme, tokens
            from app.toolkit.config import settings
            from app.toolkit.db import get_db
            from app.toolkit.deps import current_token_payload

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 沒有大頭貼也是合法狀態：照樣清掉、照樣回成功
            crud.save(User, {"id": me.id, "avatar_bytes": None, "avatar_mime": None}, db=db)
            db.commit()
            return {"avatarUrl": None, "avatar": me.display_name[-1:]}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 DELETE /api/auth/me/avatar
        3. 按右上角 Authorize，貼上登入拿到的 accessToken（先打 POST /api/auth/login）
        4. 按 Try it out，至少試這幾種，結果要跟右邊一樣：
               有大頭貼時打  → 200，avatarUrl 是 null
               再打一次      → 還是 200
        5. 前端改成連你的後端（frontend/index.html 的 api-base），個人資料頁「移除大頭貼」，頭像變回文字
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "delete_avatar and 你的"，要全部通過
    """
    # 沒有大頭貼也是合法狀態：照樣清掉、照樣回成功
    crud.save(User, {"id": me.id, "avatar_bytes": None, "avatar_mime": None}, db=db)
    db.commit()
    return {"avatarUrl": None, "avatar": me.display_name[-1:]}


@router.delete("/auth/me", summary="刪除自己的帳號")
@login_required
def delete_me(body: VerifyPasswordIn, me: User, db: Session = Depends(get_db)):
    """刪除自己的帳號

    DELETE /api/auth/me

    【這支做什麼】
        刪除自己的帳號（使用者要求「登記的資料都要能刪」）：他記的每一筆帳、只有他在用的帳本、預算、存款目標、
        提醒、建議、通知、登入紀錄全部刪掉；名字、email、密碼、大頭貼、理財習慣抹掉。email 空出來，可以再註冊。
        users 那一列留著當墓碑（deleted_at 填上時間）：稽核紀錄、他建立過的家庭還指著它。規則在 toolkit/account.py。
        ⚠️ 還在家庭裡不能刪：先退出或解散家庭——那兩條路已經處理好照看、零用金、帳本成員，這裡不重寫一次。
        ⚠️ 他開的帳本還有別人在用不能刪：別人的帳不能跟著他一起消失。
        ⚠️ 救不回來，所以**這一支自己核對密碼**（請求裡帶 password）：手上只有 token 的人刪不掉。
           跟 POST /api/auth/verify-password 共用錯誤次數，15 分鐘內錯 5 次就先停。

    【前端怎麼打】
        frontend/js/api.js 的 API.deleteAccount(password)
        個人資料頁最下面的「刪除帳號」：先輸入密碼、再打一段確認文字，成功之後清掉這台的登入、回到首頁。

    【誰能打】
        登入、沒被停權就能打。上面的 @login_required 已經擋好了：
            沒登入、token 過期 → 401；被停權 → 403
        平台管理員的帳號不在這裡刪（由 ADMIN_EMAILS 管）。參數 me 就是目前登入的人（User 物件）：
            me.id            他的 id
            me.family_id     他的家庭 id（還沒加入家庭是 None）

    【請求參數】JSON（DELETE 也帶 body）
        password   必填   目前的密碼

    【成功回應】狀態碼 200
        {"deleted": true}
        · 之後這個人手上的 token 一律 401（守衛看 deleted_at）

    【錯誤回應】detail 會原封不動顯示在畫面上，所以要寫成使用者看得懂的話
        狀態碼  什麼時候                    detail
        400     密碼不對                    密碼不正確
        403     平台管理員                  平台管理員的帳號不能在這裡刪除
        409     還在家庭裡                  你還在一個家庭裡：先到「家庭成員」退出（或解散）家庭，才能刪除帳號
        409     開的帳本還有別人在用        你開的帳本「…」還有別人在用：先把他們移出、或移除這本帳，才能刪除帳號
        429     15 分鐘內密碼錯了 5 次      密碼錯太多次了，請 15 分鐘後再試

    【會用到的資料表】
        表                                                    讀／寫    用來做什麼
        users                                                 讀＋寫    抹掉個資、填 deleted_at（墓碑）
        transactions、nlp_parses、notifications、groups、group_members、budgets、savings_goals、
        alert_rules、advices、allowances、guardianships、family_invites、accounts、sessions、password_resets  刪
        security_events、error_logs                           寫        user_id 改成 NULL（只留次數）
        audit_logs                                            讀＋寫    數密碼錯幾次（verify_password_failed）；delete_account

    【每一步用的工具與資料庫方法】
        步驟      呼叫                                                      做什麼
        1 數次數  crud.count(AuditLog, {…verify_password_failed…}, db=db)   15 分鐘內錯幾次
        2 對密碼  passwords.verify_password(body.password, me.password_hash)
        3 檢查    account.why_not_delete(me.id, me.family_id, db=db)        不能刪的原因；可以刪回 None
        4 刪      account.delete_everything(me.id, db=db)                   刪紀錄、抹個資（只 flush）
        5 稽核    crud.save(AuditLog, {…, "action": "delete_account"}, db=db)＋db.commit()

    【寫法步驟】
        1. 平台管理員 → 403
        2. 15 分鐘內錯 5 次 → 429；密碼不對 → 記一筆、400
        3. 還在家庭裡、開的帳本還有別人 → 409（講清楚要先做什麼）
        4. 刪紀錄、抹個資、寫一筆稽核，同一個交易 db.commit()；回 {"deleted": true}

    【完整寫法】照下面兩步改，改完這支就做好了
        第一步：（已經放好了，不用動）這個檔案最上面的 import 就是下面這段

            import logging
            import uuid
            from datetime import datetime, timedelta, timezone

            from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
            from sqlalchemy.orm import Session

            from app import catalog
            from app.guards import guest_only, login_required, token_required, visible_scope
            from app.models import (
                AuditLog, Family, FamilyMember, Group, GroupMember, Guardianship, PasswordReset, SavingsGoal, User, UserSession,
            )
            from app.routers._stub import not_ready, stub
            from app.schemas.auth import AvatarIn, FinanceIn, LoginIn, LogoutIn, PasswordChangeIn, PasswordResetConfirmIn, PasswordResetIn, ProfilePatchIn, RefreshIn, RegisterIn, VerifyEmailIn, VerifyPasswordIn
            from app.toolkit import account, crud, email_verify, errors, images, mailer, password_reset, passwords, period, profile, roles, security, theme, tokens
            from app.toolkit.config import settings
            from app.toolkit.db import get_db
            from app.toolkit.deps import current_token_payload

        第二步：刪掉上面的 @stub，再把 raise not_ready(...) 那一行換成下面這段。
        裝飾器、函式名稱、參數和這段說明字串都不用動。

            # 1. 平台管理員的帳號不在這裡刪（由 ADMIN_EMAILS 管理）
            if me.is_platform_admin:
                raise errors.forbidden("平台管理員的帳號不能在這裡刪除")

            # 2. 再核對一次密碼：救不回來的動作，不能只靠前端先問過（手上只有 token 的人刪不掉）
            #    跟 verify-password 同一個計數：15 分鐘內錯 5 次就先停
            since = datetime.now(timezone.utc) - timedelta(minutes=15)
            failures = crud.count(AuditLog, {"actor_id": me.id, "action": "verify_password_failed",
                                             "created_at__gte": since}, db=db)
            if failures >= 5:
                raise HTTPException(status_code=429, detail="密碼錯太多次了，請 15 分鐘後再試")
            if not passwords.verify_password(body.password, me.password_hash):
                crud.save(AuditLog, {"actor_id": me.id, "action": "verify_password_failed", "target_type": "user",
                                     "target_id": me.id}, db=db)
                if failures + 1 >= 5:
                    security.record("verify_locked", db=db, user_id=me.id, detail="15 分鐘內錯了 5 次")
                db.commit()
                raise errors.bad_request("密碼不正確")

            # 3. 還在家庭裡、自己開的帳本還有別人 → 409：先走那幾條路處理好，別人的帳不能跟著消失
            reason = account.why_not_delete(me.id, me.family_id, db=db)
            if reason:
                raise errors.conflict(reason)

            # 4. 紀錄全部刪掉、個資抹掉（同一個交易）；稽核留一筆，只記「有人刪了帳號」
            uid = me.id
            account.delete_everything(uid, db=db)
            crud.save(AuditLog, {"actor_id": uid, "action": "delete_account", "target_type": "user", "target_id": uid,
                                 "meta_json": {"note": "刪除自己的帳號"}}, db=db)
            db.commit()
            return {"deleted": True}

    【做完怎麼確認】
        1. 在 backend/ 底下啟動：uvicorn app.main:app --reload
        2. 瀏覽器打開 http://localhost:8000/docs，找到 DELETE /api/auth/me
        3. 按右上角 Authorize，貼上一個測試帳號登入拿到的 accessToken（先記幾筆帳）
        4. 按 Try it out，body 填 {"password": "…"}，至少試這幾種，結果要跟右邊一樣：
               密碼打錯            → 400（連錯 5 次 → 429）
               還在家庭裡          → 409
               沒有家庭            → 200；同一張 token 再打 GET /api/auth/me → 401；用原本的 email 登入 → 401
               原本的 email 再註冊 → 201（email 空出來了）
        5. 前端改成連你的後端（frontend/index.html 的 api-base），個人資料頁「刪除帳號」，輸入密碼與確認文字後回到首頁
        6. 自動檢查：在 backend/ 底下跑 pytest tests/routes -k "delete_me and u4f60" -v，要全部通過
    """
    # 1. 平台管理員的帳號不在這裡刪（由 ADMIN_EMAILS 管理）
    if me.is_platform_admin:
        raise errors.forbidden("平台管理員的帳號不能在這裡刪除")

    # 2. 再核對一次密碼：救不回來的動作，不能只靠前端先問過（手上只有 token 的人刪不掉）
    #    跟 verify-password 同一個計數：15 分鐘內錯 5 次就先停
    since = datetime.now(timezone.utc) - timedelta(minutes=15)
    failures = crud.count(AuditLog, {"actor_id": me.id, "action": "verify_password_failed",
                                     "created_at__gte": since}, db=db)
    if failures >= 5:
        raise HTTPException(status_code=429, detail="密碼錯太多次了，請 15 分鐘後再試")
    if not passwords.verify_password(body.password, me.password_hash):
        crud.save(AuditLog, {"actor_id": me.id, "action": "verify_password_failed", "target_type": "user",
                             "target_id": me.id}, db=db)
        if failures + 1 >= 5:
            security.record("verify_locked", db=db, user_id=me.id, detail="15 分鐘內錯了 5 次")
        db.commit()
        raise errors.bad_request("密碼不正確")

    # 3. 還在家庭裡、自己開的帳本還有別人 → 409：先走那幾條路處理好，別人的帳不能跟著消失
    reason = account.why_not_delete(me.id, me.family_id, db=db)
    if reason:
        raise errors.conflict(reason)

    # 4. 紀錄全部刪掉、個資抹掉（同一個交易）；稽核留一筆，只記「有人刪了帳號」
    uid = me.id
    account.delete_everything(uid, db=db)
    crud.save(AuditLog, {"actor_id": uid, "action": "delete_account", "target_type": "user", "target_id": uid,
                         "meta_json": {"note": "刪除自己的帳號"}}, db=db)
    db.commit()
    return {"deleted": True}
