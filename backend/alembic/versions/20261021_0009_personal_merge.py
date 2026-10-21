"""個人大帳本及逐人合併；補回舊版結算紀錄，不複製或刪除明細。"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("groups") as batch:
        batch.add_column(sa.Column("personal_owner_id", sa.BigInteger(), nullable=True))
        batch.create_foreign_key("fk_groups_personal_owner", "users", ["personal_owner_id"], ["id"])
        batch.create_unique_constraint("uq_groups_personal_owner_id", ["personal_owner_id"])
    backfill(op.get_bind())


def backfill(conn):
    """保留既有的單人預設帳本；無可辨認的大帳本時另外建立。可重跑。"""
    meta = sa.MetaData()
    users = sa.Table("users", meta, autoload_with=conn)
    groups = sa.Table("groups", meta, autoload_with=conn)
    members = sa.Table("group_members", meta, autoload_with=conn)
    tx = sa.Table("transactions", meta, autoload_with=conn)
    now = datetime.now(timezone.utc)
    personal = {}
    active = conn.execute(sa.select(users.c.id, users.c.display_name).where(
        users.c.is_platform_admin.is_(False), users.c.deleted_at.is_(None))).all()
    for uid, name in active:
        gid = conn.execute(sa.select(groups.c.id).where(groups.c.personal_owner_id == uid)).scalar()
        if gid is None:
            title = str(name or "我")[:17] + "的帳本"
            gid = conn.execute(sa.select(groups.c.id).where(
                groups.c.created_by == uid, groups.c.name == title, groups.c.kind == "standing",
                groups.c.removed_at.is_(None), groups.c.settled_at.is_(None),
                ~sa.exists().where(members.c.group_id == groups.c.id, members.c.user_id != uid),
                ~sa.exists().where(tx.c.group_id == groups.c.id, tx.c.user_id != uid),
            ).order_by(groups.c.id).limit(1)).scalar()
            if gid is None:
                gid = conn.execute(groups.insert().values(
                    name=title, color="book-indigo", created_by=uid, created_at=now,
                    kind="standing", personal_owner_id=uid,
                ).returning(groups.c.id)).scalar_one()
            else:
                conn.execute(groups.update().where(groups.c.id == gid).values(
                    personal_owner_id=uid, archived_at=None))
            if not conn.execute(sa.select(members.c.user_id).where(
                    members.c.group_id == gid, members.c.user_id == uid)).first():
                conn.execute(members.insert().values(group_id=gid, user_id=uid, joined_at=now, notify=False))
        personal[uid] = gid

    # 舊版結算是整本鎖住；把每人的舊明細移回自己的大帳本，再關閉舊帳本。
    settled = sa.select(groups.c.id).where(groups.c.settled_at.is_not(None))
    for uid, gid in personal.items():
        conn.execute(tx.update().where(tx.c.user_id == uid, tx.c.group_id.in_(settled)).values(group_id=gid))
    conn.execute(members.delete().where(members.c.group_id.in_(settled)))
    conn.execute(groups.update().where(groups.c.settled_at.is_not(None), groups.c.removed_at.is_(None))
                 .values(removed_at=now))


def downgrade():
    # 明細已回到本人帳本，不倒搬，避免把部署後新增的資料混回舊帳。
    with op.batch_alter_table("groups") as batch:
        batch.drop_constraint("uq_groups_personal_owner_id", type_="unique")
        batch.drop_constraint("fk_groups_personal_owner", type_="foreignkey")
        batch.drop_column("personal_owner_id")
