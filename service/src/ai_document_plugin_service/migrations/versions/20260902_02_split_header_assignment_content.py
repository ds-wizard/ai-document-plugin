"""Split incorrectly combined header assignment caches.

Revision ID: 20260902_02
Revises: 20260902_01
Create Date: 2026-09-02 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = '20260902_02'
down_revision = '20260902_01'
branch_labels = None
depends_on = None


def _assignment_table(schema: str | None) -> str:
    return f'{schema}.assignment' if schema else 'assignment'


def upgrade() -> None:
    schema = context.get_context().version_table_schema
    assignment_table = _assignment_table(schema)
    op.execute(
        sa.text(
            f"UPDATE {assignment_table} "  # noqa: S608
            "SET header_assignments = json_build_array(header_assignments -> 0), "
            "content_assignments = ("
            "SELECT json_agg(item.value) "
            "FROM json_array_elements(header_assignments) WITH ORDINALITY AS item(value, position) "
            "WHERE item.position > 1"
            ") "
            "WHERE json_typeof(header_assignments) = 'array' "
            "AND json_array_length(header_assignments) > 1 "
            "AND header_assignments -> 0 ->> 'title' = 'Projects'"
        )
    )


def downgrade() -> None:
    # The split is lossless, but restoring the accidental combined format is undesirable.
    return
