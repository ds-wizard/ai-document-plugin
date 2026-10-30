"""Add the selected output language to persisted results.

Existing result rows do not contain reliable language information, so they
remain NULL. Every result generated after this migration records its selected
language code.

Revision ID: 20260831_01
Revises: 20260807_01
Create Date: 2026-08-31 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

# revision identifiers, used by Alembic.
revision = '20260831_01'
down_revision = '20260807_01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = context.get_context().version_table_schema
    op.add_column('result', sa.Column('language', sa.Text(), nullable=True), schema=schema)


def downgrade() -> None:
    schema = context.get_context().version_table_schema
    op.drop_column('result', 'language', schema=schema)
