"""users 加上 deleted_at：使用者可以刪除自己的帳號

版本：0007
上一版：0006
建立時間：2026-10-20

為什麼要這一欄：使用者要求「登記的資料都要能刪」，包含帳號本身（DELETE /api/auth/me）。
刪除帳號會把這個人的紀錄全部刪掉、名字與 email 抹掉（email 空出來，可以再註冊），
但 users 那一列留著當墓碑：稽核紀錄、他建立過的家庭還指著它，整列刪掉的話外鍵會斷。

  deleted_at   刪除帳號的時間；NULL = 正常。不是 NULL 的帳號登不進來、平台管理頁不列
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0007'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'deleted_at')
