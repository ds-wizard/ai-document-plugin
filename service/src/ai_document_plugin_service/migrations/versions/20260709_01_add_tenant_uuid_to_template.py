"""Add tenant_uuid to template table.

Templates were not previously scoped per tenant, so there is no way to
backfill tenant_uuid for existing rows. This migration drops all existing
data in template (and, via cascade, assignment and result which reference
it) before adding the column as NOT NULL.

Revision ID: 20260709_01
Revises: 20260521_02
Create Date: 2026-07-09 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260709_01'
down_revision = '20260521_02'
branch_labels = None
depends_on = None


def _qualified_table_reference(schema: str | None, table: str) -> str:
    if schema:
        return f'{schema}.{table}'
    return table


def upgrade() -> None:
    schema = context.get_context().version_table_schema
    # Deletes the current template table -
    # I think it is ok trade of to making this backwards compatible with nullable tenant_uuid.
    # Alternative is making the tenant_uuid nullable and showing null templates to everyone,
    # but then there are issues with deleting...
    op.execute(
        sa.text(
            f'TRUNCATE TABLE {_qualified_table_reference(schema, "result")}, '
            f'{_qualified_table_reference(schema, "assignment")}, '
            f'{_qualified_table_reference(schema, "template")} CASCADE',
        ),
    )

    op.add_column(
        'template',
        sa.Column('tenant_uuid', postgresql.UUID(as_uuid=True), nullable=False),
        schema=schema,
    )


def downgrade() -> None:
    schema = context.get_context().version_table_schema
    op.drop_column('template', 'tenant_uuid', schema=schema)
