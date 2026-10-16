"""Track template and assignment updates for cache invalidation."""

import sqlalchemy as sa
from alembic import context, op

revision = '20261016_02'
down_revision = '37cb34f64ef7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = context.get_context().version_table_schema
    for table in ('template', 'assignment'):
        op.add_column(
            table,
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )
    assignment = sa.table(
        'assignment',
        sa.column('created_at', sa.DateTime(timezone=True)),
        sa.column('updated_at', sa.DateTime(timezone=True)),
        schema=schema,
    )
    op.execute(assignment.update().values(updated_at=assignment.c.created_at))
