"""身分認證與平台管理（成員1）。怎麼跑、兩種對象的差別：看 conftest.py 的檔頭。"""

import base64
from datetime import timedelta

import pytest

from app.models import AuditLog, PasswordReset, User, UserSession
from app.toolkit import crud, mailer, password_reset, passwords, tokens
from tests.routes.conftest import PASSWORD, family_of, goal, guard, ledger_of, login, now, this_month, user


def session_for(u, **extra):
    """直接在資料庫放一台登入中的裝置，回傳 (那一列, refresh token)。"""
    refresh, expires = tokens.make_refresh_token(u.id)
    row = crud.save(UserSession, {"user_id": u.id, "refresh_token_hash": tokens.fingerprint(refresh),
                                  "expires_at": expires, **extra})
    return row, refresh


def login_as(u, row):
    """帶 sid 的 access token（像真的登入拿到的那一張）。"""
    return {"Authorization": "Bearer " + tokens.make_access_token(u.id, extra={"sid": str(row.id)})}


# ===========================================================================
# POST /api/auth/register
# ===========================================================================
REG = ("POST", "/api/auth/register")


@pytest.mark.route(*REG)
def test_register_註冊完直接登入(api):
    r = api.post("/api/auth/register", json={"name": " 王 大明 ", "email": " Daming@Wang.TW ", "password": "abcd1234"},
                 headers={"User-Agent": "Mozilla/5.0 (iPhone)"})
    assert r.status_code == 201, r.text
    b = r.json()
    u = b["user"]
    assert {k: u[k] for k in ("name", "email", "role", "familyId", "avatar", "avatarUrl", "theme", "onboardedAt",
                              "savingsGoal", "isPlatformAdmin", "age", "birthYear")} == {
        "name": "王 大明", "email": "daming@wang.tw", "role": None, "familyId": None, "avatar": "明",
        "avatarUrl": None, "theme": "paper", "onboardedAt": None, "savingsGoal": 0, "isPlatformAdmin": False,
        "age": None, "birthYear": None}
    assert b["expiresIn"] == 1800 and u["joined"]
    row = crud.get(User, int(u["id"]))
    assert row.email == "daming@wang.tw" and row.password_hash != "abcd1234"
    assert passwords.verify_password("abcd1234", row.password_hash) and row.onboarded_at is None
    payload = tokens.read_access_token(b["accessToken"])
    s = crud.get(UserSession, where={"user_id": row.id})
    assert payload["sub"] == u["id"] and payload["sid"] == str(s.id)
    assert s.refresh_token_hash == tokens.fingerprint(b["refreshToken"]) and "iPhone" in s.user_agent
    assert s.ip_hash and s.revoked_at is None


@pytest.mark.route(*REG)
def test_register_擋下來的情況(api):
    user("daming@wang.tw", "已經有了")
    ok = {"name": "阿明", "email": "new@x.tw", "password": "abcd1234"}
    r = api.post("/api/auth/register", json={**ok, "email": "DAMING@wang.tw"})
    assert r.status_code == 409 and "註冊過" in r.json()["detail"]
    assert api.post("/api/auth/register", json={**ok, "savingsGoal": 1000}).status_code == 400
    assert api.post("/api/auth/register", json={**ok, "password": "1234"}).status_code == 422
    assert api.post("/api/auth/register", json={**ok, "password": "12345678"}).status_code == 422
    assert api.post("/api/auth/register", json={**ok, "name": "   "}).status_code == 422
    assert api.post("/api/auth/register", json={**ok, "email": "abc"}).status_code == 422
    someone = user("s@x.tw", "登入中")
    assert api.post("/api/auth/register", json=ok, headers=login(someone)).status_code == 400
    assert crud.count(User) == 2


# ===========================================================================
# POST /api/auth/login
# ===========================================================================
LOGIN = ("POST", "/api/auth/login")


@pytest.mark.route(*LOGIN)
def test_login_成功_回傳跟_me_一樣的_user(api):
    dad = user("daming@wang.tw", "王大明", birth_year=1974, theme="sky", onboarded_at=now())
    fam = family_of((dad, "parent"))
    goal(dad, 20000)
    r = api.post("/api/auth/login", json={"email": "DaMing@Wang.tw ", "password": PASSWORD})
    assert r.status_code == 200, r.text
    b = r.json()
    u = b["user"]
    assert (u["id"], u["role"], u["familyId"], u["theme"], u["savingsGoal"], u["birthYear"]) == \
        (str(dad.id), "parent", str(fam.id), "sky", 20000, 1974)
    assert u["age"] > 50 and u["onboardedAt"] and u["isPlatformAdmin"] is False
    s = crud.get(UserSession, where={"user_id": dad.id})
    assert tokens.read_access_token(b["accessToken"])["sid"] == str(s.id)
    assert s.refresh_token_hash == tokens.fingerprint(b["refreshToken"])
    assert crud.get(User, dad.id).last_login_at is not None


@pytest.mark.route(*LOGIN)
def test_login_帳號不存在跟密碼錯_同一句話_而且都有比對雜湊(api, monkeypatch):
    user("daming@wang.tw", "王大明")
    calls = []
    real = passwords.verify_password
    monkeypatch.setattr(passwords, "verify_password", lambda p, h: calls.append(h) or real(p, h))
    a = api.post("/api/auth/login", json={"email": "daming@wang.tw", "password": "wrong-pass"})
    b = api.post("/api/auth/login", json={"email": "nobody@wang.tw", "password": "wrong-pass"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()
    assert len(calls) == 2 and all(h.startswith("$2") for h in calls)
    assert crud.count(UserSession) == 0


@pytest.mark.route(*LOGIN)
def test_login_停權_密碼對了才講(api):
    user("bad@x.tw", "壞人", suspended_at=now(), suspended_reason="多次騷擾")
    r = api.post("/api/auth/login", json={"email": "bad@x.tw", "password": "wrong-pass"})
    assert r.status_code == 401
    r = api.post("/api/auth/login", json={"email": "bad@x.tw", "password": PASSWORD})
    assert r.status_code == 403 and "多次騷擾" in r.json()["detail"]
    assert crud.count(UserSession) == 0


# ===========================================================================
# POST /api/auth/refresh
# ===========================================================================
REFRESH = ("POST", "/api/auth/refresh")


@pytest.mark.route(*REFRESH)
def test_refresh_輪替_舊的作廢(api):
    me = user("d@x.tw", "爸爸")
    row, old = session_for(me)
    r = api.post("/api/auth/refresh", json={"refreshToken": old})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["refreshToken"] != old and b["expiresIn"] == 1800
    p = tokens.read_access_token(b["accessToken"])
    assert (p["sub"], p["sid"]) == (str(me.id), str(row.id))
    assert crud.get(UserSession, row.id).refresh_token_hash == tokens.fingerprint(b["refreshToken"])
    assert crud.count(UserSession) == 1
    assert api.post("/api/auth/refresh", json={"refreshToken": old}).status_code == 401      # 重送：只回 401
    assert crud.get(UserSession, row.id).revoked_at is None                                  # 不會連帶把人登出
    assert api.post("/api/auth/refresh", json={"refreshToken": b["refreshToken"]}).status_code == 200


@pytest.mark.route(*REFRESH)
def test_refresh_各種不能換的情況(api):
    me = user("d@x.tw", "爸爸")
    _, revoked = session_for(me, revoked_at=now())
    _, expired = session_for(me, expires_at=now() - timedelta(minutes=1))
    unknown, _ = tokens.make_refresh_token(me.id)
    for bad in (revoked, expired, unknown, tokens.make_access_token(me.id), "亂打的"):
        r = api.post("/api/auth/refresh", json={"refreshToken": bad})
        assert r.status_code == 401, bad
        assert r.json()["detail"] == "登入已經過期，請重新登入"
    bad_guy = user("b@x.tw", "壞人", suspended_at=now(), suspended_reason="違規")
    _, t = session_for(bad_guy)
    r = api.post("/api/auth/refresh", json={"refreshToken": t})
    assert r.status_code == 403 and "違規" in r.json()["detail"]


# ===========================================================================
# POST /api/auth/logout、/api/auth/logout-all
# ===========================================================================
LOGOUT = ("POST", "/api/auth/logout")
LOGOUT_ALL = ("POST", "/api/auth/logout-all")


@pytest.mark.route(*LOGOUT)
def test_logout_撤銷這一台_重複登出也成功(api):
    me, other = user("d@x.tw", "爸爸"), user("o@x.tw", "別人")
    a, ta = session_for(me)
    b, _ = session_for(me)
    c, tc = session_for(other)
    r = api.post("/api/auth/logout", headers=login(me), json={"refreshToken": ta})
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert crud.get(UserSession, a.id).revoked_at is not None and crud.get(UserSession, b.id).revoked_at is None
    assert api.post("/api/auth/logout", headers=login(me), json={"refreshToken": ta}).status_code == 200
    api.post("/api/auth/logout", headers=login(me), json={"refreshToken": tc})               # 別人的撤不掉
    assert crud.get(UserSession, c.id).revoked_at is None
    assert api.post("/api/auth/logout", headers=login(me), json={}).status_code == 200       # 沒 sid：什麼都不做
    assert crud.get(UserSession, b.id).revoked_at is None
    assert api.post("/api/auth/logout", headers=login_as(me, b), json={}).status_code == 200  # 用 sid
    assert crud.get(UserSession, b.id).revoked_at is not None


@pytest.mark.route(*LOGOUT_ALL)
def test_logout_all(api):
    me, other = user("d@x.tw", "爸爸"), user("o@x.tw", "別人")
    session_for(me)
    session_for(me)
    session_for(me, revoked_at=now())
    c, _ = session_for(other)
    r = api.post("/api/auth/logout-all", headers=login(me))
    assert r.status_code == 200 and r.json() == {"revoked": 2}
    assert crud.count(UserSession, {"user_id": me.id, "revoked_at__isnull": True}) == 0
    assert crud.get(UserSession, c.id).revoked_at is None


# ===========================================================================
# GET /api/auth/me、PATCH /api/auth/me
# ===========================================================================
ME = ("GET", "/api/auth/me")
PATCH_ME = ("PATCH", "/api/auth/me")


@pytest.mark.route(*ME)
def test_me_家長_看得到誰_誰在照看我(api):
    dad, mom, kid, aunt = user("d@x.tw", "爸爸"), user("m@x.tw", "媽媽"), user("k@x.tw", "小華"), user("a@x.tw", "阿姨")
    fam = family_of((dad, "parent"), (mom, "parent"), (kid, "child"))
    guard(mom, kid)
    ledger_of(dad, aunt)
    goal(dad, 100, period="2026-01")
    goal(dad, 300)
    r = api.get("/api/auth/me", headers=login(dad))
    assert r.status_code == 200, r.text
    b = r.json()
    assert (b["user"]["role"], b["user"]["familyId"], b["user"]["savingsGoal"]) == ("parent", str(fam.id), 300)
    assert b["family"] == {"id": str(fam.id), "name": "王家", "period": this_month()}
    assert b["visible"] == [str(dad.id), str(mom.id)]
    assert b["queryable"] == [str(dad.id), str(mom.id), str(aunt.id)]
    assert b["guardedBy"] == []
    k = api.get("/api/auth/me", headers=login(kid)).json()
    assert k["guardedBy"] == [{"id": str(mom.id), "name": "媽媽"}] and k["visible"] == [str(kid.id)]
    assert "income" not in k["user"] and "expense" not in k["user"]


@pytest.mark.route(*ME)
def test_me_新帳號與平台管理員(api):
    new = user("n@x.tw", "新人")
    b = api.get("/api/auth/me", headers=login(new)).json()
    assert b["user"]["onboardedAt"] is None and b["user"]["theme"] == "paper" and b["family"] is None
    assert b["visible"] == [str(new.id)] and b["user"]["savingsGoal"] == 0
    admin = user("admin@x.tw", "管理員", is_platform_admin=True)
    b = api.get("/api/auth/me", headers=login(admin)).json()
    assert b["user"]["isPlatformAdmin"] is True and b["visible"] == [] and b["queryable"] == []
    assert api.get("/api/auth/me").status_code == 401


@pytest.mark.route(*PATCH_ME)
def test_update_me_只改送來的(api):
    me = user("d@x.tw", "爸爸", birth_year=1974)
    h = login(me)
    r = api.patch("/api/auth/me", headers=h, json={"theme": "sky"})
    assert r.status_code == 200, r.text
    assert (r.json()["theme"], r.json()["birthYear"], r.json()["name"]) == ("sky", 1974, "爸爸")
    r = api.patch("/api/auth/me", headers=h, json={"displayName": " 王  大明 ", "birthYear": None})
    assert (r.json()["name"], r.json()["avatar"], r.json()["birthYear"], r.json()["age"]) == ("王 大明", "明", None, None)
    r = api.patch("/api/auth/me", headers=h, json={"onboarded": True})
    first = r.json()["onboardedAt"]
    assert first
    assert api.patch("/api/auth/me", headers=h, json={"onboarded": True}).json()["onboardedAt"] == first
    assert api.patch("/api/auth/me", headers=h, json={}).status_code == 200
    row = crud.get(User, me.id)
    assert (row.theme, row.display_name, row.birth_year) == ("sky", "王 大明", None)


@pytest.mark.route(*PATCH_ME)
def test_update_me_擋下來的情況(api):
    me = user("d@x.tw", "爸爸")
    h = login(me)
    for bad in ({"theme": "Sky"}, {"theme": "neon"}, {"onboarded": False}, {"birthYear": 1800},
                {"birthYear": 3000}, {"displayName": "   "}, {"displayName": "字" * 31}, {"email": "x@x.tw"}):
        assert api.patch("/api/auth/me", headers=h, json=bad).status_code == 422, bad
    row = crud.get(User, me.id)
    assert (row.theme, row.display_name, row.onboarded_at, row.email) == ("paper", "爸爸", None, "d@x.tw")


# ===========================================================================
# PATCH /api/auth/password、POST /api/auth/verify-password
# ===========================================================================
PWD = ("PATCH", "/api/auth/password")
VERIFY = ("POST", "/api/auth/verify-password")


@pytest.mark.route(*PWD)
def test_change_password_其他裝置登出_這一台留著(api):
    me = user("d@x.tw", "爸爸")
    here, _ = session_for(me)
    there, _ = session_for(me)
    h = login_as(me, here)
    assert api.patch("/api/auth/password", headers=h, json={"oldPassword": "wrong-pass", "newPassword": "efgh5678"}).status_code == 400
    assert api.patch("/api/auth/password", headers=h, json={"oldPassword": PASSWORD, "newPassword": PASSWORD}).status_code == 400
    assert api.patch("/api/auth/password", headers=h, json={"oldPassword": PASSWORD, "newPassword": "1234"}).status_code == 422
    assert crud.get(UserSession, there.id).revoked_at is None
    r = api.patch("/api/auth/password", headers=h, json={"oldPassword": PASSWORD, "newPassword": "efgh5678"})
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert passwords.verify_password("efgh5678", crud.get(User, me.id).password_hash)
    assert crud.get(UserSession, here.id).revoked_at is None
    assert crud.get(UserSession, there.id).revoked_at is not None
    assert crud.exists(AuditLog, {"action": "change_password", "actor_id": me.id})


@pytest.mark.route(*VERIFY)
def test_verify_password_錯五次就先停(api):
    me = user("d@x.tw", "爸爸")
    h = login(me)
    r = api.post("/api/auth/verify-password", headers=h, json={"password": PASSWORD})
    assert r.status_code == 200 and r.json() == {"ok": True}
    for _ in range(5):
        r = api.post("/api/auth/verify-password", headers=h, json={"password": "wrong-pass"})
        assert r.status_code == 400 and r.json()["detail"] == "密碼不正確"
    assert api.post("/api/auth/verify-password", headers=h, json={"password": PASSWORD}).status_code == 429
    assert crud.count(AuditLog, {"action": "verify_password_failed"}) == 5
    other = user("o@x.tw", "別人")
    assert api.post("/api/auth/verify-password", headers=login(other), json={"password": PASSWORD}).status_code == 200


# ===========================================================================
# 忘記密碼
# ===========================================================================
RESET = ("POST", "/api/auth/password-reset")
CONFIRM = ("POST", "/api/auth/password-reset/confirm")


@pytest.fixture()
def outbox(monkeypatch):
    sent = []

    def fake(to, subject, text, html=None, **kw):
        sent.append({"to": to, "subject": subject, "text": text, "html": html, **kw})
        return "msg-1"

    monkeypatch.setattr(mailer, "send_mail", fake)
    return sent


@pytest.mark.route(*RESET)
def test_request_password_reset_有沒有帳號回應都一樣(api, outbox):
    me = user("daming@wang.tw", "王大明")
    a = api.post("/api/auth/password-reset", json={"email": " DaMing@wang.tw "})
    b = api.post("/api/auth/password-reset", json={"email": "nobody@wang.tw"})
    assert a.status_code == b.status_code == 200
    assert a.json() == b.json() == {"ok": True, "message": password_reset.GENERIC_MESSAGE}
    assert len(outbox) == 1 and outbox[0]["to"] == "daming@wang.tw" and outbox[0]["to_name"] == "王大明"
    token = outbox[0]["text"].split("#/reset/")[1].split()[0]
    row = crud.get(PasswordReset, where={"user_id": me.id})
    assert row.token_hash == password_reset.hash_token(token) and token not in row.token_hash
    assert row.used_at is None
    # 60 秒內再按：不寄、不多一列，回應一樣
    c = api.post("/api/auth/password-reset", json={"email": "daming@wang.tw"})
    assert c.json() == a.json() and len(outbox) == 1 and crud.count(PasswordReset) == 1
    assert api.post("/api/auth/password-reset", json={"email": "abc"}).status_code == 400


@pytest.mark.route(*RESET)
def test_request_password_reset_寄不出去也一樣回成功(api, monkeypatch):
    user("daming@wang.tw", "王大明")

    def broken(*a, **kw):
        raise mailer.MailError("寄信服務回 500")

    monkeypatch.setattr(mailer, "send_mail", broken)
    r = api.post("/api/auth/password-reset", json={"email": "daming@wang.tw"})
    assert r.status_code == 200 and r.json()["ok"] is True and "demoMail" not in r.json()
    assert crud.count(PasswordReset) == 1


def _reset_token(u, **extra):
    token = password_reset.new_token()
    crud.save(PasswordReset, {"user_id": u.id, "token_hash": password_reset.hash_token(token),
                              "expires_at": password_reset.expires_at(), **extra})
    return token


@pytest.mark.route(*CONFIRM)
def test_confirm_password_reset_改密碼_連結作廢_全部登出(api):
    me = user("d@x.tw", "爸爸")
    s1, _ = session_for(me)
    s2, _ = session_for(me)
    token = _reset_token(me)
    assert api.post("/api/auth/password-reset/confirm", json={"token": token, "password": "1234"}).status_code == 422
    assert crud.get(PasswordReset, where={"user_id": me.id}).used_at is None             # 太弱的不算用掉
    r = api.post("/api/auth/password-reset/confirm", json={"token": token, "password": "efgh5678"})
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert passwords.verify_password("efgh5678", crud.get(User, me.id).password_hash)
    assert crud.get(PasswordReset, where={"user_id": me.id}).used_at is not None
    assert crud.get(UserSession, s1.id).revoked_at and crud.get(UserSession, s2.id).revoked_at
    r = api.post("/api/auth/password-reset/confirm", json={"token": token, "password": "ijkl9012"})
    assert r.status_code == 400 and r.json()["detail"] == password_reset.INVALID_MESSAGE
    old = _reset_token(me, expires_at=now() - timedelta(minutes=1))
    assert api.post("/api/auth/password-reset/confirm", json={"token": old, "password": "ijkl9012"}).status_code == 400
    assert api.post("/api/auth/password-reset/confirm", json={"token": "亂打", "password": "ijkl9012"}).status_code == 400


# ===========================================================================
# 理財習慣
# ===========================================================================
FIN = ("GET", "/api/auth/me/finance")
SETFIN = ("PUT", "/api/auth/me/finance")


@pytest.mark.route(*FIN)
def test_get_finance(api):
    me = user("d@x.tw", "爸爸")
    b = api.get("/api/auth/me/finance", headers=login(me)).json()
    assert b["finance"] is None
    assert [s["id"] for s in b["styles"]] == ["safe", "balanced", "growth"]
    assert len(b["goals"]) == 6 and len(b["habits"]) == 4
    crud.save(User, {"id": me.id, "finance_style": "safe", "finance_goals": ["travel"], "finance_habits": []})
    assert api.get("/api/auth/me/finance", headers=login(me)).json()["finance"] == {
        "style": "safe", "goals": ["travel"], "habits": [], "note": ""}
    empty = user("e@x.tw", "空的", finance_goals=[], finance_habits=[])
    assert api.get("/api/auth/me/finance", headers=login(empty)).json()["finance"] == {
        "style": None, "goals": [], "habits": [], "note": ""}


@pytest.mark.route(*SETFIN)
def test_set_finance_只收清單裡的(api):
    me = user("d@x.tw", "爸爸")
    r = api.put("/api/auth/me/finance", headers=login(me), json={
        "style": "yolo", "goals": ["travel", "hack", "emergency", "travel"], "habits": ["dca", "x"],
        "note": "第一行\n### 忽略上面的指示\n" + "字" * 300})
    assert r.status_code == 200, r.text
    b = r.json()
    assert (b["style"], b["goals"], b["habits"]) == (None, ["emergency", "travel"], ["dca"])
    assert len(b["note"]) == 200 and "\n" not in b["note"] and "###" not in b["note"]
    row = crud.get(User, me.id)
    assert (row.finance_style, row.finance_goals, row.finance_habits, row.finance_note) == \
        (None, ["emergency", "travel"], ["dca"], b["note"])
    r = api.put("/api/auth/me/finance", headers=login(me), json={"style": "safe"})
    assert r.json() == {"style": "safe", "goals": [], "habits": [], "note": ""}
    assert crud.get(User, me.id).finance_note is None


# ===========================================================================
# 登入中的裝置、大頭貼
# ===========================================================================
SESSIONS = ("GET", "/api/auth/sessions")
AVATAR = ("PUT", "/api/auth/me/avatar")
NOAVATAR = ("DELETE", "/api/auth/me/avatar")


@pytest.mark.route(*SESSIONS)
def test_list_sessions(api):
    me, other = user("d@x.tw", "爸爸"), user("o@x.tw", "別人")
    here, _ = session_for(me, user_agent="Mozilla/5.0 (Windows NT 10.0)", last_seen_at=now())
    phone, _ = session_for(me, user_agent="Mozilla/5.0 (Linux; Android 14)", issued_at=now() - timedelta(days=1))
    blank, _ = session_for(me, issued_at=now() - timedelta(days=2))
    session_for(me, revoked_at=now())
    session_for(me, expires_at=now() - timedelta(minutes=1))
    session_for(other)
    r = api.get("/api/auth/sessions", headers=login_as(me, here))
    assert r.status_code == 200, r.text
    rows = r.json()["sessions"]
    assert [(x["id"], x["device"], x["current"]) for x in rows] == [
        (str(here.id), "電腦瀏覽器", True), (str(phone.id), "手機瀏覽器", False), (str(blank.id), "不明裝置", False)]
    assert all(x["lastActiveAt"].endswith("Z") for x in rows)
    assert all("ip" not in k.lower() for x in rows for k in x)


def _data_uri(raw, mime="image/jpeg"):
    return "data:%s;base64,%s" % (mime, base64.b64encode(raw).decode("ascii"))


@pytest.mark.route(*AVATAR)
def test_upload_avatar(api):
    me = user("d@x.tw", "王大明")
    jpeg = b"\xff\xd8\xff\xe0" + b"0" * 100
    r = api.put("/api/auth/me/avatar", headers=login(me), json={"image": _data_uri(jpeg, "image/png")})
    assert r.status_code == 200, r.text
    assert r.json() == {"avatarUrl": _data_uri(jpeg), "avatar": "明"}                   # 型別看內容，不信宣告
    row = crud.get(User, me.id)
    assert row.avatar_bytes == jpeg and row.avatar_mime == "image/jpeg"
    for bad in (_data_uri(b"import os; os.system('x')"), "not-a-data-uri",
                _data_uri(b"\xff\xd8\xff" + b"0" * 300000), "data:image/jpeg;base64,@@@@"):
        assert api.put("/api/auth/me/avatar", headers=login(me), json={"image": bad}).status_code == 422
    assert crud.get(User, me.id).avatar_bytes == jpeg


@pytest.mark.route(*NOAVATAR)
def test_delete_avatar(api):
    me = user("d@x.tw", "王大明", avatar_bytes=b"\xff\xd8\xff\xe0", avatar_mime="image/jpeg")
    r = api.delete("/api/auth/me/avatar", headers=login(me))
    assert r.status_code == 200 and r.json() == {"avatarUrl": None, "avatar": "明"}
    row = crud.get(User, me.id)
    assert row.avatar_bytes is None and row.avatar_mime is None
    assert api.delete("/api/auth/me/avatar", headers=login(me)).status_code == 200


# ===========================================================================
# 平台管理
# ===========================================================================
USERS = ("GET", "/api/admin/users")
SUSPEND = ("POST", "/api/admin/users/{user_id}/suspend")
UNSUSPEND = ("DELETE", "/api/admin/users/{user_id}/suspend")


@pytest.mark.route(*USERS)
def test_admin_list_users_只有身分欄位(api):
    admin = user("admin@x.tw", "管理員", is_platform_admin=True)
    user("admin2@x.tw", "另一位管理員", is_platform_admin=True)
    dad = user("d@x.tw", "爸爸")
    bad = user("b@x.tw", "壞人", suspended_at=now(), suspended_reason="違規")
    family_of((dad, "parent"))
    goal(dad, 20000)
    r = api.get("/api/admin/users", headers=login(admin))
    assert r.status_code == 200, r.text
    rows = r.json()["users"]
    assert [x["id"] for x in rows] == [str(dad.id), str(bad.id)]
    assert set(rows[0]) == {"id", "name", "email", "role", "joined", "suspendedAt", "suspendedReason"}
    assert (rows[0]["role"], rows[0]["suspendedAt"]) == ("parent", None)
    assert (rows[1]["role"], rows[1]["suspendedReason"]) == (None, "違規") and rows[1]["suspendedAt"]
    assert api.get("/api/admin/users", headers=login(dad)).status_code == 403


@pytest.mark.route(*SUSPEND)
def test_suspend_user(api):
    admin = user("admin@x.tw", "管理員", is_platform_admin=True)
    admin2 = user("admin2@x.tw", "另一位管理員", is_platform_admin=True)
    dad = user("d@x.tw", "爸爸")
    s, _ = session_for(dad)
    h = login(admin)
    url = "/api/admin/users/%s/suspend"
    assert api.post(url % dad.id, headers=h, json={"reason": "  太  短 "}).status_code == 422
    assert api.post(url % admin2.id, headers=h, json={"reason": "管理員也想停"}).status_code == 403
    assert api.post(url % 99999, headers=h, json={"reason": "找不到的人"}).status_code == 404
    assert api.post(url % "abc", headers=h, json={"reason": "找不到的人"}).status_code == 404
    assert api.post(url % admin.id, headers=login(dad), json={"reason": "反過來停"}).status_code == 403
    r = api.post(url % dad.id, headers=h, json={"reason": "多次  騷擾其他使用者"})
    assert r.status_code == 200, r.text
    assert r.json()["id"] == str(dad.id) and r.json()["suspendedAt"]
    row = crud.get(User, dad.id)
    assert row.suspended_at is not None and row.suspended_reason == "多次 騷擾其他使用者"
    assert crud.get(UserSession, s.id).revoked_at is not None
    log = crud.get(AuditLog, where={"action": "suspend_user"})
    assert (log.actor_id, log.target_id, log.meta_json["note"]) == (admin.id, dad.id, "多次 騷擾其他使用者")
    r = api.get("/api/auth/me", headers=login(dad))                          # 已經登入的人，下一個請求就擋
    assert r.status_code == 403 and "騷擾" in r.json()["detail"]


@pytest.mark.route(*UNSUSPEND)
def test_unsuspend_user(api):
    admin = user("admin@x.tw", "管理員", is_platform_admin=True)
    bad = user("b@x.tw", "壞人", suspended_at=now(), suspended_reason="違規")
    h = login(admin)
    r = api.delete("/api/admin/users/%d/suspend" % bad.id, headers=h)
    assert r.status_code == 200 and r.json() == {"id": str(bad.id), "suspendedAt": None}
    row = crud.get(User, bad.id)
    assert row.suspended_at is None and row.suspended_reason is None
    assert crud.exists(AuditLog, {"action": "unsuspend_user", "target_id": bad.id})
    assert api.delete("/api/admin/users/%d/suspend" % bad.id, headers=h).status_code == 400
    assert api.delete("/api/admin/users/99999/suspend", headers=h).status_code == 404
    assert api.get("/api/auth/me", headers=login(bad)).status_code != 403        # 解除之後守衛不再擋
