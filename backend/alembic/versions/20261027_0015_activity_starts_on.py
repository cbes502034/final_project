"""活動的開始日：使用者自己選（預設建立當天），比今天晚就是預先規劃的活動。舊的活動留 NULL＝建立當天。
group_members.start_notified_on：到了開始日通知過這位成員沒有（防同時好幾個請求重複通知）。"""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("groups") as batch:
        batch.add_column(sa.Column("starts_on", sa.Date(), nullable=True))
    with op.batch_alter_table("group_members") as batch:
        batch.add_column(sa.Column("start_notified_on", sa.Date(), nullable=True))


def downgrade():
    with op.batch_alter_table("group_members") as batch:
        batch.drop_column("start_notified_on")
    with op.batch_alter_table("groups") as batch:
        batch.drop_column("starts_on")
