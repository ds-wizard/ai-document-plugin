"""Persist the selected cover-page version for each template."""

import sqlalchemy as sa
from alembic import context, op

revision = '20260929_01'
down_revision = '20260902_01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = context.get_context().version_table_schema
    op.add_column('template', sa.Column('cover_page_version', sa.Text(), nullable=True), schema=schema)
