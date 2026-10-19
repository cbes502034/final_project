"""放入系統預設分類（正式環境）

版本：0004
上一版：0003
建立時間：2026-10-19

為什麼要這一版：系統分類以前只有 `python -m app.cli init-db` 會放進去，那是本機用的指令。
Render 部署只跑 `alembic upgrade head`，所以正式環境的 categories 表一直是空的——
手動記帳選不到分類、段落解析的模型拿到空的分類清單，每一筆都填不出分類。

這一版只補「還沒有的」系統分類（family_id 是 NULL、名字對不上的才新增），跑幾次結果都一樣；
已經用 init-db 放過的資料庫（本機）不會多出重複的。

⚠️ 這是資料的快照，跟 app/catalog.py 的 SYSTEM_CATEGORIES 一致。之後改了 catalog，要再寫一版遷移補上，
   tests/test_backend_core.py 會檢查升到最新版之後兩邊一樣。
⚠️ 降版不刪：這些分類可能已經被明細、預算用到了，刪掉會讓那些資料失去分類。
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: (名稱, 收支, 顏色)——順序就是 sort_order
SYSTEM_CATEGORIES = [
    ("餐飲", "expense", "cat-food"), ("交通", "expense", "cat-transit"),
    ("居住", "expense", "cat-home"), ("日用品", "expense", "cat-daily"),
    ("娛樂", "expense", "cat-fun"), ("教育", "expense", "cat-study"),
    ("醫療", "expense", "cat-health"), ("其他", "expense", "cat-other"),
    ("薪資", "income", "cat-daily"), ("獎金", "income", "cat-bonus"),
    ("零用金", "income", "cat-transit"), ("其他收入", "income", "cat-other"),
]


def upgrade() -> None:
    conn = op.get_bind()
    have = {row[0] for row in conn.execute(sa.text("SELECT name FROM categories WHERE family_id IS NULL"))}
    categories = sa.table(
        "categories",
        sa.column("name", sa.Text), sa.column("kind", sa.Text),
        sa.column("color", sa.Text), sa.column("sort_order", sa.Integer),
    )
    rows = [{"name": n, "kind": k, "color": c, "sort_order": i}
            for i, (n, k, c) in enumerate(SYSTEM_CATEGORIES) if n not in have]
    if rows:
        op.bulk_insert(categories, rows)


def downgrade() -> None:
    # 不刪：見檔頭
    pass
