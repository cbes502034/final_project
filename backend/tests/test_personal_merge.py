"""舊資料搬移與前端帳本選擇的回歸測試。"""
import importlib.util
from pathlib import Path
import shutil
import subprocess

import pytest

from app.models import Group, GroupMember, Transaction
from app.toolkit import crud
from tests.test_backend_core import sqlite  # noqa: F401
from tests.routes.conftest import categories, ledger_of, now, spend, user

REPO = Path(__file__).resolve().parents[2]


def test_legacy_settlement_returns_each_users_rows_to_their_own_book(sqlite):
    a, b, admin = user("a@x.tw", "甲"), user("b@x.tw", "乙"), user("admin@x.tw", "管理", is_platform_admin=True)
    personal = ledger_of(a, name="甲的帳本")
    # Another person's shared book with the default name must remain a shared book.
    shared = ledger_of(b, a, name="乙的帳本")
    old = ledger_of(a, b, name="已結算旅行", kind="temp", settled_at=now())
    removed = ledger_of(b, name="已移除旅行", kind="temp", settled_at=now(), removed_at=now())
    cat = categories()["餐飲"]
    first, second, third = spend(a, old, cat, 10), spend(b, old, cat, 20), spend(b, removed, cat, 30)
    untouched = spend(a, shared, cat, 40)
    before = [(t.id, t.user_id, t.amount, t.occurred_on) for t in crud.find(Transaction, order_by="id")]
    path = REPO / "backend/alembic/versions/20261021_0009_personal_merge.py"
    spec = importlib.util.spec_from_file_location("personal_merge_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with sqlite.engine.begin() as conn:
        migration.backfill(conn)
        migration.backfill(conn)  # Running the repair again cannot duplicate books or entries.
    assert crud.get(Group, personal.id).personal_owner_id == a.id
    assert crud.get(Group, shared.id).personal_owner_id is None
    theirs = crud.get(Group, where={"personal_owner_id": b.id})
    assert theirs and theirs.id != shared.id
    assert crud.get(Transaction, first.id).group_id == personal.id
    assert crud.get(Transaction, second.id).group_id == theirs.id
    assert crud.get(Transaction, third.id).group_id == theirs.id
    assert crud.get(Transaction, untouched.id).group_id == shared.id
    assert crud.get(Group, old.id).removed_at
    assert not crud.exists(GroupMember, {"group_id": old.id})
    assert crud.count(Group, {"personal_owner_id__isnull": False}) == 2
    assert not crud.exists(Group, {"personal_owner_id": admin.id})
    assert [(t.id, t.user_id, t.amount, t.occurred_on) for t in crud.find(Transaction, order_by="id")] == before


def test_ledger_switcher_and_mock_merge_behaviour():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    subprocess.run([node, str(REPO / "backend/tests/fixtures/personal_merge.js"), str(REPO)],
                   check=True, capture_output=True, text=True)
