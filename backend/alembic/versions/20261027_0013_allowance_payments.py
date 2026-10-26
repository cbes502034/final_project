"""零用金自動記帳：每位家長的發放日、每月實際發放的那一對帳、家長那邊的「給零用金」分類。"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("allowances") as batch:
        batch.add_column(sa.Column("pay_day", sa.Integer(), nullable=True))
    op.create_table("allowance_payments",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("payer_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("ward_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("period_key", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("payer_tx_id", sa.BigInteger()),
        sa.Column("ward_tx_id", sa.BigInteger()),
        sa.Column("status", sa.Text(), nullable=False, server_default="paid"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("payer_id", "ward_id", "period_key", name="uq_allowance_payment_month"))
    # 系統分類放最後，舊的排序不動
    conn = op.get_bind()
    cats = sa.Table("categories", sa.MetaData(), autoload_with=conn)
    have = conn.execute(sa.select(cats.c.id).where(cats.c.name == "給零用金", cats.c.kind == "expense",
                                                   cats.c.family_id.is_(None))).first()
    if have is None:
        values = {"name": "給零用金", "kind": "expense", "color": "cat-transit", "sort_order": 12}
        if "created_at" in cats.c:
            values["created_at"] = datetime.now(timezone.utc)
        conn.execute(cats.insert().values(**values))


def downgrade():
    op.drop_table("allowance_payments")
    with op.batch_alter_table("allowances") as batch:
        batch.drop_column("pay_day")
