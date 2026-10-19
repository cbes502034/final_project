"""users 加上 email 驗證的兩欄

版本：0003
上一版：0002
建立時間：2026-10-19

為什麼要這兩欄：註冊之後寄一封驗證信，點連結才算確認 email 是本人的。
沒有驗證的話，email 打錯的人帳號照樣建得起來，但忘記密碼的信永遠寄不到，而且他不會知道。

  email_verified_at      點了驗證連結的時間；NULL = 還沒驗證（照樣能用，首頁會提醒）
  email_verify_sent_at   上一次寄驗證信的時間；重寄要隔 60 秒

⚠️ 現有的帳號都會是 NULL（以前沒有這個流程），登入後首頁會請他們去收信驗證。
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('email_verify_sent_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'email_verify_sent_at')
    op.drop_column('users', 'email_verified_at')
