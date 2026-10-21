"""活動獨立邀請與收支明細的來源活動。"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("transactions") as batch:
        batch.add_column(sa.Column("origin_group_id", sa.BigInteger(), nullable=True))
        batch.create_foreign_key("fk_transactions_origin_group", "groups", ["origin_group_id"], ["id"])
        batch.create_index("ix_transactions_origin_group_id", ["origin_group_id"])
    conn = op.get_bind()
    tx = sa.Table("transactions", sa.MetaData(), autoload_with=conn)
    source = tx.alias("source")
    conn.execute(tx.update().where(tx.c.copied_from_id.is_not(None), tx.c.origin_group_id.is_(None))
                 .values(origin_group_id=sa.select(source.c.group_id)
                         .where(source.c.id == tx.c.copied_from_id).scalar_subquery()))
    op.create_table("activity_invites",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("group_id", sa.BigInteger(), sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("inviter_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("invitee_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("code_hash", sa.Text(), unique=True), sa.Column("label", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True)))


def downgrade():
    op.drop_table("activity_invites")
    with op.batch_alter_table("transactions") as batch:
        batch.drop_index("ix_transactions_origin_group_id")
        batch.drop_constraint("fk_transactions_origin_group", type_="foreignkey")
        batch.drop_column("origin_group_id")
