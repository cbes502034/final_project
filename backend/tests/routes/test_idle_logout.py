"""閒置自動登出（使用者 2026-10-28：線上的人不能踢、閒置的可以；期限由我們選 → 30 分鐘）。

規則在 app/toolkit/tokens.py 的 session_deadline 與 app/toolkit/security.py 的 keep_session；
守衛（guards.current_user）每次請求呼叫 keep_session，把這一台的 sessions.expires_at 往後推。
"""
import pathlib
from datetime import timedelta

import pytest

from app.models import UserSession
from app.toolkit import crud, security, tokens
from app.toolkit.config import settings
from tests.routes.conftest import now, user

ME = ("GET", "/api/auth/me")
REFRESH = ("POST", "/api/auth/refresh")
ROOT = pathlib.Path(__file__).resolve().parents[3]


def _device(u, *, idle_minutes):
    """一台最後一次有動作是 idle_minutes 分鐘前的裝置。回傳 (那一列, refresh token, 帶 sid 的 access 標頭)。"""
    t = now() - timedelta(minutes=idle_minutes)
    refresh, _ = tokens.make_refresh_token(u.id)
    row = crud.save(UserSession, {"user_id": u.id, "refresh_token_hash": tokens.fingerprint(refresh),
                                  "issued_at": t, "last_seen_at": t, "expires_at": tokens.session_deadline(t)})
    headers = {"Authorization": "Bearer " + tokens.make_access_token(u.id, extra={"sid": str(row.id)})}
    return row, refresh, headers


def _minutes_left(row_id):
    return (security.aware(crud.get(UserSession, row_id).expires_at) - now()).total_seconds() / 60


def test_預設是30分鐘_而且登入時存的期限就是閒置期限():
    assert settings.session_idle_minutes == 30
    token, expires = tokens.make_refresh_token(1)
    assert 29.9 < (expires - now()).total_seconds() / 60 <= 30
    # token 本身的上限還是 14 天：每換一次重新算，不是閒置期限
    exp = tokens.read_refresh_token(token)["exp"]
    assert exp - now().timestamp() > 13 * 86400


@pytest.mark.route(*ME)
def test_一直在用_每次請求把期限往後推(api):
    me = user("d@x.tw", "爸爸")
    row, _, headers = _device(me, idle_minutes=25)          # 再 5 分鐘就要過期
    assert _minutes_left(row.id) < 6
    assert api.get("/api/auth/me", headers=headers).status_code == 200
    assert _minutes_left(row.id) > 29                        # 又有 30 分鐘
    seen = security.aware(crud.get(UserSession, row.id).last_seen_at)
    assert (now() - seen).total_seconds() < 60               # 「登入中的裝置」看到的是剛剛


@pytest.mark.route(*ME)
def test_30秒內再來_不重寫(api):
    me = user("d@x.tw", "爸爸")
    row, _, headers = _device(me, idle_minutes=0.1)          # 6 秒前才推過
    before = crud.get(UserSession, row.id).expires_at
    assert api.get("/api/auth/me", headers=headers).status_code == 200
    assert crud.get(UserSession, row.id).expires_at == before


@pytest.mark.route(*ME)
def test_閒置超過30分鐘_這一台就登出(api):
    me = user("d@x.tw", "爸爸")
    row, _, headers = _device(me, idle_minutes=31)
    r = api.get("/api/auth/me", headers=headers)              # access token 還沒過期也一樣擋
    assert r.status_code == 401 and r.json()["detail"] == "這台裝置已登出，請重新登入"
    _, _, other = _device(me, idle_minutes=1)                 # 別台還在用的不受影響
    assert api.get("/api/auth/me", headers=other).status_code == 200


@pytest.mark.route(*REFRESH)
def test_閒置超過30分鐘_換不到新的token(api):
    me = user("d@x.tw", "爸爸")
    _, refresh, _ = _device(me, idle_minutes=31)
    r = api.post("/api/auth/refresh", json={"refreshToken": refresh})
    assert r.status_code == 401 and r.json()["detail"] == "登入已經過期，請重新登入"


@pytest.mark.route(*REFRESH)
def test_還在期限內_換發後重新算30分鐘(api):
    me = user("d@x.tw", "爸爸")
    row, refresh, _ = _device(me, idle_minutes=20)
    r = api.post("/api/auth/refresh", json={"refreshToken": refresh})
    assert r.status_code == 200, r.text
    assert 29 < _minutes_left(row.id) <= 30


def test_前端_背景分頁不輪詢_被登出時帶回登入頁():
    notify = (ROOT / "frontend/js/notify.js").read_text(encoding="utf-8")
    api_js = (ROOT / "frontend/js/api.js").read_text(encoding="utf-8")
    app = (ROOT / "frontend/js/app.js").read_text(encoding="utf-8")
    poll = notify[notify.index("function poll(first)"):notify.index("global.API.notifications({ since")]
    assert "document.visibilityState === 'hidden'" in poll, "背景分頁還在問，後端會當成有在用，登入永遠不過期"
    assert "signedOut(e)" in api_js and "fambudget:signedout" in api_js
    assert "addEventListener('fambudget:signedout'" in app
    # 沒有 refresh token 也要是 401，換頁時才會回登入頁，而不是停在「尚未登入」的錯誤畫面
    assert "Object.assign(new Error('尚未登入'), { status: 401 })" in api_js
