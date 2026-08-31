"""Store output language per generation instead of per latest result.

The result table is keyed by template, knowledge model, user, and tenant, so
it represents only the latest matching result. Generation has one row per run
and is the persistent history model, making it the correct location for the
selected output language.

Revision ID: 20260831_02
Revises: 20260831_01
Create Date: 2026-08-31 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

# revision identifiers, used by Alembic.
revision = '20260831_02'
down_revision = '20260831_01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = context.get_context().version_table_schema
    op.add_column('generation', sa.Column('language', sa.Text(), nullable=True), schema=schema)
    op.drop_column('result', 'language', schema=schema)


def downgrade() -> None:
    schema = context.get_context().version_table_schema
    op.add_column('result', sa.Column('language', sa.Text(), nullable=True), schema=schema)
    op.drop_column('generation', 'language', schema=schema)
