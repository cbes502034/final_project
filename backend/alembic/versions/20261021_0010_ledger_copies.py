"""合併時保留原帳本歷史、建立獨立個人副本，整體收支只算一次。"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("transactions") as batch:
        batch.add_column(sa.Column("is_snapshot", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("copied_from_id", sa.BigInteger(), nullable=True))
        batch.create_foreign_key("fk_transactions_copied_from", "transactions", ["copied_from_id"], ["id"],
                                 ondelete="SET NULL")
        batch.create_unique_constraint("uq_transactions_copied_from_id", ["copied_from_id"])
    backfill(op.get_bind())


def backfill(conn):
    """舊版整本結算的紀錄仍留在原帳本；逐人補個人副本。可重跑。"""
    meta = sa.MetaData()
    tx = sa.Table("transactions", meta, autoload_with=conn)
    groups = sa.Table("groups", meta, autoload_with=conn)
    parses = sa.Table("nlp_parses", meta, autoload_with=conn)
    personal = dict(conn.execute(sa.select(groups.c.personal_owner_id, groups.c.id)
                                 .where(groups.c.personal_owner_id.is_not(None))).all())
    closed = sa.select(groups.c.id).where(groups.c.settled_at.is_not(None))
    originals = conn.execute(sa.select(tx).where(tx.c.group_id.in_(closed), tx.c.is_snapshot.is_(False))).mappings().all()
    for original in originals:
        gid = personal.get(original["user_id"])
        if gid is None:
            continue
        existing = conn.execute(sa.select(tx.c.id).where(tx.c.copied_from_id == original["id"])).scalar()
        if existing is None:
            values = {k: v for k, v in original.items() if k not in {"id", "group_id", "is_snapshot", "copied_from_id"}}
            copied_id = conn.execute(tx.insert().values(**values, group_id=gid, is_snapshot=False,
                                                       copied_from_id=original["id"]).returning(tx.c.id)).scalar_one()
            for parsed in conn.execute(sa.select(parses).where(parses.c.transaction_id == original["id"])).mappings().all():
                values = {k: v for k, v in parsed.items() if k not in {"id", "transaction_id"}}
                conn.execute(parses.insert().values(**values, transaction_id=copied_id))
        conn.execute(tx.update().where(tx.c.id == original["id"]).values(is_snapshot=True))


def downgrade():
    # 拿掉快照標記會讓舊版把原紀錄和副本重複加總，不能無條件降版。
    conn = op.get_bind()
    if conn.execute(sa.text(
            "SELECT COUNT(*) FROM transactions WHERE is_snapshot = :yes OR copied_from_id IS NOT NULL"
    ), {"yes": True}).scalar():
        raise RuntimeError("已有合併副本，不能自動降版；請先保留備份並處理副本，避免收支重複計算")
    with op.batch_alter_table("transactions") as batch:
        batch.drop_constraint("uq_transactions_copied_from_id", type_="unique")
        batch.drop_constraint("fk_transactions_copied_from", type_="foreignkey")
        batch.drop_column("copied_from_id")
        batch.drop_column("is_snapshot")
