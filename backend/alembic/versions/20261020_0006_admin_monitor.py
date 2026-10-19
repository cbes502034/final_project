"""平台管理頁的即時監控：最後活動時間、安全事件、錯誤紀錄

版本：0006
上一版：0005
建立時間：2026-10-20

為什麼要這一版：平台管理頁要即時看到三件事——
  users.last_active_at   誰現在在線上（紅綠燈）。守衛每 30 秒最多寫一次
  security_events        登入失敗、被規則擋下的請求（登入鎖住、註冊太多、AI 額度用完…）
  error_logs             後端沒接住的錯誤、使用者畫面上出的錯

⚠️ 兩張新表都不放任何財務內容（金額、備註、記帳的那句話），平台管理員看得到它們。
現有的帳號 last_active_at 都是 NULL，下一次有請求就會補上。
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=True))

    op.create_table('security_events',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('kind', sa.Text(), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=True),
    sa.Column('subject', sa.Text(), nullable=True),
    sa.Column('ip_hash', sa.Text(), nullable=True),
    sa.Column('detail', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('security_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_security_events_kind'), ['kind'], unique=False)
        batch_op.create_index(batch_op.f('ix_security_events_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_security_events_subject'), ['subject'], unique=False)
        batch_op.create_index(batch_op.f('ix_security_events_created_at'), ['created_at'], unique=False)

    op.create_table('error_logs',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('source', sa.Text(), nullable=False),
    sa.Column('status', sa.Integer(), nullable=True),
    sa.Column('method', sa.Text(), nullable=True),
    sa.Column('path', sa.Text(), nullable=True),
    sa.Column('location', sa.Text(), nullable=True),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('error_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_error_logs_created_at'), ['created_at'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('error_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_error_logs_created_at'))
    op.drop_table('error_logs')
    with op.batch_alter_table('security_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_security_events_created_at'))
        batch_op.drop_index(batch_op.f('ix_security_events_subject'))
        batch_op.drop_index(batch_op.f('ix_security_events_user_id'))
        batch_op.drop_index(batch_op.f('ix_security_events_kind'))
    op.drop_table('security_events')
    op.drop_column('users', 'last_active_at')
