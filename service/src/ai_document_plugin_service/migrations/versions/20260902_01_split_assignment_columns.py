"""Store regular and DMP-header assignments in separate columns.

Revision ID: 20260902_01
Revises: 20260831_02
Create Date: 2026-09-02 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = '20260902_01'
down_revision = '20260831_02'
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = context.get_context().version_table_schema
    op.add_column('assignment', sa.Column('content_assignments', sa.JSON(), nullable=True), schema=schema)
    op.add_column('assignment', sa.Column('header_assignments', sa.JSON(), nullable=True), schema=schema)

    # Cached assignments are regenerated on demand instead of converted.
    op.drop_column('assignment', 'assignments', schema=schema)


def downgrade() -> None:
    schema = context.get_context().version_table_schema
    op.add_column(
        'assignment',
        sa.Column('assignments', sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        schema=schema,
    )
    op.alter_column('assignment', 'assignments', server_default=None, schema=schema)
    op.drop_column('assignment', 'header_assignments', schema=schema)
    op.drop_column('assignment', 'content_assignments', schema=schema)
