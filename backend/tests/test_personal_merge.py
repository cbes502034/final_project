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


def test_legacy_settlement_copies_each_users_rows_and_preserves_originals(sqlite):
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
    spec = importlib.util.spec_from_file_location("ledger_copies_migration", REPO / "backend/alembic/versions/20261021_0010_ledger_copies.py")
    copies_migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copies_migration)
    with sqlite.engine.begin() as conn:
        copies_migration.backfill(conn)
        copies_migration.backfill(conn)
    assert crud.get(Group, personal.id).personal_owner_id == a.id
    assert crud.get(Group, shared.id).personal_owner_id is None
    theirs = crud.get(Group, where={"personal_owner_id": b.id})
    assert theirs and theirs.id != shared.id
    assert crud.get(Transaction, first.id).group_id == old.id
    assert crud.get(Transaction, where={"copied_from_id": first.id}).group_id == personal.id
    assert crud.get(Transaction, second.id).group_id == old.id
    assert crud.get(Transaction, where={"copied_from_id": second.id}).group_id == theirs.id
    assert crud.get(Transaction, third.id).group_id == removed.id
    assert crud.get(Transaction, where={"copied_from_id": third.id}).group_id == theirs.id
    assert crud.get(Transaction, untouched.id).group_id == shared.id
    assert crud.get(Group, old.id).removed_at
    assert not crud.exists(GroupMember, {"group_id": old.id})
    assert crud.count(Group, {"personal_owner_id__isnull": False}) == 2
    assert not crud.exists(Group, {"personal_owner_id": admin.id})
    assert [(t.id, t.user_id, t.amount, t.occurred_on) for t in crud.find(Transaction, {"copied_from_id__isnull": True}, order_by="id")] == before
    assert crud.count(Transaction) == 7
    assert crud.count(Transaction, {"is_snapshot": False}) == 4
    # Removing the snapshot markers would make the old app count both copies.
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    with sqlite.engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
        with pytest.raises(RuntimeError, match="不能自動降版"):
            copies_migration.downgrade()
    assert crud.count(Transaction) == 7


def test_ledger_switcher_and_mock_merge_behaviour():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    subprocess.run([node, str(REPO / "backend/tests/fixtures/personal_merge.js"), str(REPO)],
                   check=True, capture_output=True, text=True)
