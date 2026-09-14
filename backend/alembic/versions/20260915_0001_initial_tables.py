"""建立全部 20 張資料表（正本：frontend/js/data.js 的 schema → app/models/）

版本：0001
上一版：
建立時間：2026-09-15

⚠️ autogenerate 產生的內容一定要自己看過再 upgrade：
   「改名」常被判成「刪掉舊的＋加新的」，那會把資料弄丟。
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('users',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('email', sa.Text(), nullable=False),
    sa.Column('password_hash', sa.Text(), nullable=False),
    sa.Column('display_name', sa.Text(), nullable=False),
    sa.Column('birth_year', sa.Integer(), nullable=True),
    sa.Column('theme', sa.Text(), nullable=False),
    sa.Column('is_platform_admin', sa.Boolean(), nullable=False),
    sa.Column('suspended_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('suspended_reason', sa.Text(), nullable=True),
    sa.Column('onboarded_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('avatar_bytes', sa.LargeBinary(), nullable=True),
    sa.Column('avatar_mime', sa.Text(), nullable=True),
    sa.Column('finance_style', sa.Text(), nullable=True),
    sa.Column('finance_goals', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('finance_habits', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('finance_note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    op.create_table('accounts',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('kind', sa.Text(), nullable=True),
    sa.Column('balance', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('allowances',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('payer_id', sa.BigInteger(), nullable=False),
    sa.Column('ward_id', sa.BigInteger(), nullable=False),
    sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('period_key', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['payer_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['ward_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('audit_logs',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('actor_id', sa.BigInteger(), nullable=True),
    sa.Column('action', sa.Text(), nullable=False),
    sa.Column('target_type', sa.Text(), nullable=True),
    sa.Column('target_id', sa.BigInteger(), nullable=True),
    sa.Column('meta_json', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('families',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('created_by', sa.BigInteger(), nullable=False),
    sa.Column('currency', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('guardianships',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('guardian_id', sa.BigInteger(), nullable=False),
    sa.Column('ward_id', sa.BigInteger(), nullable=False),
    sa.Column('scope', sa.Text(), nullable=False),
    sa.Column('created_by', sa.BigInteger(), nullable=True),
    sa.Column('since', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['guardian_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['ward_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('password_resets',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('token_hash', sa.Text(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_table('sessions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('refresh_token_hash', sa.Text(), nullable=False),
    sa.Column('user_agent', sa.Text(), nullable=True),
    sa.Column('ip_hash', sa.Text(), nullable=True),
    sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sessions_user_id'), ['user_id'], unique=False)

    op.create_table('advices',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('family_id', sa.BigInteger(), nullable=True),
    sa.Column('user_id', sa.BigInteger(), nullable=True),
    sa.Column('period_type', sa.Text(), nullable=False),
    sa.Column('period_key', sa.Text(), nullable=False),
    sa.Column('level', sa.Text(), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('basis_json', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('suggestions_json', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('confidence', sa.Numeric(), nullable=True),
    sa.Column('model_ver', sa.Text(), nullable=True),
    sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['family_id'], ['families.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('categories',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('family_id', sa.BigInteger(), nullable=True),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('kind', sa.Text(), nullable=False),
    sa.Column('parent_id', sa.BigInteger(), nullable=True),
    sa.Column('color', sa.Text(), nullable=True),
    sa.Column('sort_order', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['family_id'], ['families.id'], ),
    sa.ForeignKeyConstraint(['parent_id'], ['categories.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('family_invites',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('family_id', sa.BigInteger(), nullable=False),
    sa.Column('inviter_id', sa.BigInteger(), nullable=False),
    sa.Column('invitee_id', sa.BigInteger(), nullable=True),
    sa.Column('code_hash', sa.Text(), nullable=True),
    sa.Column('role', sa.Text(), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['family_id'], ['families.id'], ),
    sa.ForeignKeyConstraint(['invitee_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['inviter_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code_hash')
    )
    op.create_table('family_members',
    sa.Column('family_id', sa.BigInteger(), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('role', sa.Text(), nullable=False),
    sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['family_id'], ['families.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('family_id', 'user_id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_table('groups',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('family_id', sa.BigInteger(), nullable=True),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('color', sa.Text(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_by', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('kind', sa.Text(), nullable=False),
    sa.Column('ends_on', sa.Date(), nullable=True),
    sa.Column('settled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('removed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['family_id'], ['families.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('alert_rules',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('group_id', sa.BigInteger(), nullable=True),
    sa.Column('percent', sa.Integer(), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('fired_period', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'group_id', 'percent', name='uq_alert_rule')
    )
    op.create_table('budgets',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=True),
    sa.Column('family_id', sa.BigInteger(), nullable=True),
    sa.Column('category_id', sa.BigInteger(), nullable=True),
    sa.Column('period_type', sa.Text(), nullable=False),
    sa.Column('period_key', sa.Text(), nullable=True),
    sa.Column('limit_amount', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('created_by', sa.BigInteger(), nullable=True),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['family_id'], ['families.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('group_members',
    sa.Column('group_id', sa.BigInteger(), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('notify', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('group_id', 'user_id')
    )
    op.create_table('savings_goals',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('group_id', sa.BigInteger(), nullable=True),
    sa.Column('period_key', sa.Text(), nullable=True),
    sa.Column('goal_amount', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('warn_ratio', sa.Numeric(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_by', sa.BigInteger(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('transactions',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('group_id', sa.BigInteger(), nullable=False),
    sa.Column('family_id', sa.BigInteger(), nullable=True),
    sa.Column('account_id', sa.BigInteger(), nullable=True),
    sa.Column('category_id', sa.BigInteger(), nullable=False),
    sa.Column('kind', sa.Text(), nullable=False),
    sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('occurred_on', sa.Date(), nullable=False),
    sa.Column('merchant', sa.Text(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('source', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ),
    sa.ForeignKeyConstraint(['family_id'], ['families.id'], ),
    sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_transactions_family_id'), ['family_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_transactions_group_id'), ['group_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_transactions_occurred_on'), ['occurred_on'], unique=False)
        batch_op.create_index(batch_op.f('ix_transactions_user_id'), ['user_id'], unique=False)

    op.create_table('nlp_parses',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('transaction_id', sa.BigInteger(), nullable=True),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('raw_text', sa.Text(), nullable=False),
    sa.Column('parsed_json', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('confidence', sa.Numeric(), nullable=True),
    sa.Column('cat_confidence', sa.Numeric(), nullable=True),
    sa.Column('user_corrected', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('model_ver', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('notifications',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), nullable=False),
    sa.Column('recipient_id', sa.BigInteger(), nullable=False),
    sa.Column('actor_id', sa.BigInteger(), nullable=True),
    sa.Column('type', sa.Text(), nullable=False),
    sa.Column('transaction_id', sa.BigInteger(), nullable=True),
    sa.Column('payload_json', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['recipient_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('recipient_id', 'transaction_id', name='uq_notification_once')
    )
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.create_index('ix_notifications_recipient_created', ['recipient_id', 'created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_notifications_recipient_id'), ['recipient_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_notifications_recipient_id'))
        batch_op.drop_index('ix_notifications_recipient_created')

    op.drop_table('notifications')
    op.drop_table('nlp_parses')
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_transactions_user_id'))
        batch_op.drop_index(batch_op.f('ix_transactions_occurred_on'))
        batch_op.drop_index(batch_op.f('ix_transactions_group_id'))
        batch_op.drop_index(batch_op.f('ix_transactions_family_id'))

    op.drop_table('transactions')
    op.drop_table('savings_goals')
    op.drop_table('group_members')
    op.drop_table('budgets')
    op.drop_table('alert_rules')
    op.drop_table('groups')
    op.drop_table('family_members')
    op.drop_table('family_invites')
    op.drop_table('categories')
    op.drop_table('advices')
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sessions_user_id'))

    op.drop_table('sessions')
    op.drop_table('password_resets')
    op.drop_table('guardianships')
    op.drop_table('families')
    op.drop_table('audit_logs')
    op.drop_table('allowances')
    op.drop_table('accounts')
    op.drop_table('users')
