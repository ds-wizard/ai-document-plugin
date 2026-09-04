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


def _assignment_table(schema: str | None) -> str:
    return f'{schema}.assignment' if schema else 'assignment'


def upgrade() -> None:
    schema = context.get_context().version_table_schema
    op.add_column('assignment', sa.Column('content_assignments', sa.JSON(), nullable=True), schema=schema)
    op.add_column('assignment', sa.Column('header_assignments', sa.JSON(), nullable=True), schema=schema)

    # Support both the original list and the short-lived JSON cache with two named variants.
    assignment_table = _assignment_table(schema)
    op.execute(
        sa.text(
            f'UPDATE {assignment_table} '  # noqa: S608
            "SET content_assignments = CASE WHEN json_typeof(assignments) = 'array' THEN assignments "
            "ELSE assignments -> 'standard' END, "
            "header_assignments = CASE WHEN json_typeof(assignments) = 'object' "
            "THEN assignments -> 'dmp_metadata' END"
        ).execution_options(schema_translate_map={None: schema})
    )
    op.drop_column('assignment', 'assignments', schema=schema)


def downgrade() -> None:
    schema = context.get_context().version_table_schema
    op.add_column('assignment', sa.Column('assignments', sa.JSON(), nullable=True), schema=schema)
    assignment_table = _assignment_table(schema)
    op.execute(
        sa.text(
            f"UPDATE {assignment_table} SET assignments = COALESCE(content_assignments, header_assignments, '[]'::json)"  # noqa: S608
        )
    )
    op.alter_column('assignment', 'assignments', nullable=False, schema=schema)
    op.drop_column('assignment', 'header_assignments', schema=schema)
    op.drop_column('assignment', 'content_assignments', schema=schema)
