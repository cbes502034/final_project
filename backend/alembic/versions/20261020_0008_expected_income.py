"""users 加上 income_mode、expected_income：月底才發薪、日薪、打工的人，月初的可花上限不會變負數

版本：0008
上一版：0007
建立時間：2026-10-20

為什麼要這兩欄：可花上限 = 收入 − 每月想存。月底才領薪水的人，月初收入是 0，上限一開始就是負的，
首頁變成「超出計畫」、提醒一直響（使用者實際遇到）。改成收入用 max(這個月已入帳, 預計收入)，
預計收入從哪裡來由使用者選（services/analytics.py 的 expected_income）：

  income_mode      auto（預設）近 3 個月平均，還沒紀錄用 expected_income／fixed 固定月薪／actual 只算已入帳
  expected_income  每月預計收入（fixed 的金額；auto 還沒有紀錄時的起始估計）
  income_type      收入怎麼來（catalog.INCOME_TYPES：月薪、時薪日薪打工、接案…、other），預先配好算法
  income_note      選「其他」時自己寫的收入方式（最多 30 字）

已經在用的帳號一律是 auto、沒有填金額：有前幾個月紀錄的，月初會自動用平均；沒有的跟以前一樣。
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0008'
down_revision: Union[str, None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('income_mode', sa.Text(), nullable=False, server_default='auto'))
    op.add_column('users', sa.Column('expected_income', sa.Numeric(14, 2), nullable=True))
    op.add_column('users', sa.Column('income_type', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('income_note', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'income_note')
    op.drop_column('users', 'income_type')
    op.drop_column('users', 'expected_income')
    op.drop_column('users', 'income_mode')
