"""family_invites 加上 label：這組邀請碼是給誰用的

版本：0002
上一版：0001
建立時間：2026-09-25

為什麼要這一欄：邀請碼的明碼只在產生的當下出現一次（資料庫只存雜湊），
所以清單上每一組長得都一樣（••••-••••）。家長要刪掉其中一組的時候，
沒有東西可以分辨哪一組是哪一組——label 就是那個名字，家長自己填。

⚠️ 現有的資料列都會是 NULL（以前產生的碼沒有名字），所以 nullable=True。
   用帳號邀請的那幾列本來就用不到這一欄，也是 NULL。
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('family_invites', sa.Column('label', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('family_invites', 'label')
