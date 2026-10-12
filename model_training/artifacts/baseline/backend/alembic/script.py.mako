"""${message}

版本：${up_revision}
上一版：${down_revision | comma,n}
建立時間：${create_date}

⚠️ autogenerate 產生的內容一定要自己看過再 upgrade：
   「改名」常被判成「刪掉舊的＋加新的」，那會把資料弄丟。
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
