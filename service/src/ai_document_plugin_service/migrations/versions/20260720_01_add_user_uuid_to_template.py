"""Add user_uuid to template table for personal vs tenant-wide templates.

A NULL user_uuid marks a tenant-wide template shared with the whole tenant;
a set user_uuid marks a personal template owned by that user. Existing
templates were visible to the whole tenant, so they are kept as tenant-wide
templates (user_uuid stays NULL).

The single ``uq_template_title_tenant_uuid`` unique constraint is replaced by
two partial unique indexes so that titles are unique per tenant among
tenant-wide templates and unique per user among a user's personal templates.

Revision ID: 20260720_01
Revises: 20260709_01
Create Date: 2026-07-20 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260720_01'
down_revision = '20260709_01'
branch_labels = None
depends_on = None


def _qualified_table_reference(schema: str | None, table: str) -> str:
    if schema:
        return f'{schema}.{table}'
    return table


def upgrade() -> None:
    schema = context.get_context().version_table_schema

    op.add_column(
        'template',
        sa.Column('user_uuid', postgresql.UUID(as_uuid=True), nullable=True),
        schema=schema,
    )

    op.drop_constraint('uq_template_title_tenant_uuid', 'template', schema=schema, type_='unique')

    op.create_index(
        'uq_template_title_tenant_wide',
        'template',
        ['title', 'tenant_uuid'],
        unique=True,
        schema=schema,
        postgresql_where=sa.text('user_uuid IS NULL'),
    )
    op.create_index(
        'uq_template_title_tenant_user',
        'template',
        ['title', 'tenant_uuid', 'user_uuid'],
        unique=True,
        schema=schema,
        postgresql_where=sa.text('user_uuid IS NOT NULL'),
    )


def downgrade() -> None:
    schema = context.get_context().version_table_schema

    op.drop_index('uq_template_title_tenant_user', 'template', schema=schema)
    op.drop_index('uq_template_title_tenant_wide', 'template', schema=schema)

    # Personal templates would collide on the restored (title, tenant_uuid) unique
    # constraint, so drop them before recreating it. The schema comes from Alembic
    # config, not user input.
    template_reference = _qualified_table_reference(schema, 'template')
    op.execute(sa.text(f'DELETE FROM {template_reference} WHERE user_uuid IS NOT NULL'))  # noqa: S608

    op.create_unique_constraint(
        'uq_template_title_tenant_uuid',
        'template',
        ['title', 'tenant_uuid'],
        schema=schema,
    )

    op.drop_column('template', 'user_uuid', schema=schema)
