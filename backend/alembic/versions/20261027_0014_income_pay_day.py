"""固定收入自動入帳：每月幾號入帳、這個月記過沒有；「月薪（月初發）」「月薪（月底或月中發）」合併成「月薪」。"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("income_pay_day", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("income_posted_period", sa.Text(), nullable=True))
    # 舊的兩種月薪換成「月薪」＋入帳日：月初發是 1 號，月底或月中發先放 28 號（使用者可以自己改）
    users = sa.table("users", sa.column("income_type", sa.Text()), sa.column("income_pay_day", sa.Integer()))
    conn = op.get_bind()
    conn.execute(users.update().where(users.c.income_type == "salary_start").values(income_type="salary", income_pay_day=1))
    conn.execute(users.update().where(users.c.income_type == "salary_end").values(income_type="salary", income_pay_day=28))


def downgrade():
    users = sa.table("users", sa.column("income_type", sa.Text()), sa.column("income_pay_day", sa.Integer()))
    conn = op.get_bind()
    conn.execute(users.update().where(users.c.income_type == "salary", users.c.income_pay_day <= 10)
                 .values(income_type="salary_start"))
    conn.execute(users.update().where(users.c.income_type == "salary").values(income_type="salary_end"))
    with op.batch_alter_table("users") as batch:
        batch.drop_column("income_posted_period")
        batch.drop_column("income_pay_day")
