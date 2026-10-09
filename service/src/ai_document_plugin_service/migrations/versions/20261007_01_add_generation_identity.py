"""Persist the named-version snapshot."""

import sqlalchemy as sa
from alembic import context, op

revision = '20261007_01'
down_revision = '20261005_01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = context.get_context().version_table_schema
    op.add_column('generation', sa.Column('named_version', sa.Text(), nullable=True), schema=schema)
