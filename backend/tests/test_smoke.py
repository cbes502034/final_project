"""
冒煙測試：確認整個應用程式組裝正確。

===========================================================================
什麼是冒煙測試？
===========================================================================
名字來自硬體業：新板子做好先通電，看看會不會冒煙。
不檢查功能對不對，只檢查「有沒有當場燒起來」。

軟體上的對應就是：**程式跑得起來嗎？路由都掛上去了嗎？**
這種測試很淺，但它會在你把某個 import 打錯、某個 router 忘記掛上去時
立刻叫出來，而且跑起來只要一秒。

===========================================================================
怎麼跑
===========================================================================
    cd backend
    pytest

pytest 會自動找 `test_` 開頭的檔案和函式來執行。

===========================================================================
為什麼要在檔案最上面設環境變數？
===========================================================================
因為 `app.core.config` 在被 import 的當下就會讀環境變數，
少了 DATABASE_URL 或 JWT_SECRET 它會直接報錯。
所以**一定要在 import app 之前**先把假的值塞進去。

這也順便證明了 config.py 那個「缺設定就啟動失敗」的設計是有效的。
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def test_健康檢查回應正常():
    """服務活著的話 /healthz 要回 200。Render 靠這支判斷要不要重啟。"""
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_自動文件產得出來():
    """
    FastAPI 會自動產生 OpenAPI 規格。這支測試確認它產得出來，
    順便證明所有 router 都成功掛上去了。
    """
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert "paths" in r.json()


def test_三十五支路由都有掛上去():
    """
    API 目錄上有 35 支（第 36 支是 /healthz，第 37 支是 FastAPI 自己的 /docs）。

    這支測試的價值在於：有人新增或刪掉路由時，數字對不上就會紅燈，
    逼他回去更新 API 目錄文件。**讓文件和程式碼不會悄悄地失去同步。**
    """
    paths = client.get("/openapi.json").json()["paths"]
    verbs = ("get", "post", "put", "patch", "delete")
    n = sum(len([m for m in ops if m in verbs]) for ops in paths.values())
    assert n == 36, f"預期 35 支 API + healthz = 36，實際 {n} 支"


def test_分工定義與程式碼一致():
    """
    app/ownership.py 是分工的單一事實來源。這支測試確認它沒有跟程式碼走散。

    會紅燈的情況：有人新增了一支路由卻沒去 ownership.py 認領、
    刪掉了一支路由卻忘了從定義裡移除、或兩個人宣告了同一支。

    **這是避免功能衝突最有效的一道防線** —— 與其靠大家記得更新文件，
    不如讓忘記更新的人在跑測試時就被擋下來。
    """
    from app.ownership import check

    problems = check()
    assert not problems, "分工定義與程式碼對不上：" + "；".join(problems)


def test_沒帶權杖會被擋下來():
    """
    需要登入的路由，沒帶 token 就該回 401。

    這支測試很重要：它守住 core/deps.py 的 get_current_user。
    哪天有人不小心把那段檢查改壞，這裡會立刻紅燈。
    """
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_尚未實作的路由會誠實回報():
    """
    還沒實作的路由回 501（Not Implemented），不是 500 或 404。

    501 的意思是「這支路由存在，但還沒做」——
    前端看到 501 就知道是進度問題，不是自己打錯網址。
    """
    r = client.post(
        "/api/auth/login",
        json={"email": "a@b.c", "password": "x"},
    )
    assert r.status_code == 501
