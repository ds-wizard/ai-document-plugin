"""Remove token counts from generation and assignment statistics.

Existing token counts are discarded; call counts and timing metrics are retained.
"""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision = '20261113_01'
down_revision = '20261023_01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = context.get_context().version_table_schema
    for step in ('assignment', 'generation', 'polishing'):
        for direction in ('input', 'output'):
            op.drop_column('generation_stats', f'{step}_{direction}_tokens', schema=schema)

    assignment = sa.table('assignment', sa.column('stats', sa.JSON()), schema=schema)
    stats = sa.cast(assignment.c.stats, postgresql.JSONB())
    for direction in ('input', 'output'):
        stats = stats.op('#-')(postgresql.array(['stats', f'total_{direction}_tokens']))
    op.execute(assignment.update().where(assignment.c.stats.is_not(None)).values(stats=sa.cast(stats, sa.JSON())))
