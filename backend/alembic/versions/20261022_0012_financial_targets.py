"""家庭長期目標、依活動保存財務建議。"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("families") as batch:
        batch.add_column(sa.Column("goal_amount", sa.Numeric(14, 2), nullable=False, server_default="0"))
        batch.add_column(sa.Column("goal_note", sa.Text(), nullable=False, server_default=""))
    with op.batch_alter_table("advices") as batch:
        batch.add_column(sa.Column("group_id", sa.BigInteger(), nullable=True))
        batch.create_foreign_key("fk_advices_group", "groups", ["group_id"], ["id"])


def downgrade():
    with op.batch_alter_table("advices") as batch:
        batch.drop_constraint("fk_advices_group", type_="foreignkey")
        batch.drop_column("group_id")
    with op.batch_alter_table("families") as batch:
        batch.drop_column("goal_note")
        batch.drop_column("goal_amount")
