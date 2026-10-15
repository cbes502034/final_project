"""
還沒做的路由用的兩個小工具。

負責人：成員1（共用）

    @router.get("/summary")
    @block_admin
    @stub                               ← 還沒做：ownership.progress() 會算成「待辦」
    def get_summary(me: User, db: Session = Depends(get_db)):
        raise not_ready("GET /api/summary", "成員3")   ← 回 501，前端會講出是哪一支、誰負責

做完之後把 @stub 和 raise not_ready 一起拿掉。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import HTTPException

from app.toolkit import errors

STUB_FLAG = "__fambudget_stub__"


def stub(fn: Callable[..., Any]) -> Callable[..., Any]:
    """標記「這一支還沒做」。守衛的裝飾器會把這個標記一起帶上去（functools.wraps）。"""
    setattr(fn, STUB_FLAG, True)
    return fn


def not_ready(route: str, owner: str) -> HTTPException:
    """回 501：後端還沒做這一支。"""
    return errors.not_implemented(route, owner)


def is_stub(endpoint: Any) -> bool:
    return bool(getattr(endpoint, STUB_FLAG, False))
