"""幫還沒有帳本的帳號開第一本帳本

版本：0005
上一版：0004
建立時間：2026-10-19

為什麼要這一版：每一筆都要記在某本帳上，可是以前註冊不會開帳本——
新帳號一進來想記第一筆，就被「你還沒有可以記帳的帳本，先到『帳本』開一本」擋下來。
現在註冊時會自動開一本「〈名字〉的帳本」（routers/auth/auth.py 的 register），
這一版幫「之前註冊、手上一本能用的帳本都沒有」的帳號補一本，名字規則一樣。

只補沒有的：已經在任何一本沒被移除的帳本裡的人不動；平台管理員不記帳，不補。跑幾次結果都一樣。
⚠️ 降版不刪：補上的帳本可能已經記了帳。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: 跟 app/catalog.py 的 GROUP_COLORS[0] 一樣
COLOR = "book-indigo"


def upgrade() -> None:
    conn = op.get_bind()
    users = conn.execute(sa.text(
        "SELECT u.id, u.display_name FROM users u "
        "WHERE u.is_platform_admin = :no AND NOT EXISTS ("
        "  SELECT 1 FROM group_members gm JOIN groups g ON g.id = gm.group_id "
        "  WHERE gm.user_id = u.id AND g.removed_at IS NULL) "
        "ORDER BY u.id"), {"no": False}).fetchall()
    groups = sa.table("groups", sa.column("id", sa.BigInteger), sa.column("name", sa.Text),
                      sa.column("color", sa.Text), sa.column("created_by", sa.BigInteger),
                      sa.column("created_at", sa.DateTime(timezone=True)), sa.column("kind", sa.Text))
    members = sa.table("group_members", sa.column("group_id", sa.BigInteger), sa.column("user_id", sa.BigInteger),
                       sa.column("joined_at", sa.DateTime(timezone=True)), sa.column("notify", sa.Boolean))
    now = datetime.now(timezone.utc)
    for uid, name in users:
        title = str(name or "我")[:17] + "的帳本"
        conn.execute(groups.insert().values(name=title, color=COLOR, created_by=uid, created_at=now,
                                            kind="standing"))
        gid = conn.execute(sa.text("SELECT MAX(id) FROM groups WHERE created_by = :u AND name = :n"),
                           {"u": uid, "n": title}).scalar()
        conn.execute(members.insert().values(group_id=gid, user_id=uid, joined_at=now, notify=False))


def downgrade() -> None:
    # 不刪：見檔頭
    pass
