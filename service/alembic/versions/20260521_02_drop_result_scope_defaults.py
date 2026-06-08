"""Drop default UUID values from result scope columns.

Revision ID: 20260521_02
Revises: 20260506_01
Create Date: 2026-05-21 00:00:01
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260521_02'
down_revision = '20260506_01'
branch_labels = None
depends_on = None

DEFAULT_RESULT_SCOPE_UUID = '00000000-0000-0000-0000-000000000000'


def upgrade() -> None:
    schema = context.get_context().version_table_schema

    op.alter_column(
        'result',
        'user_uuid',
        schema=schema,
        existing_type=postgresql.UUID(as_uuid=True),
        server_default=None,
    )
    op.alter_column(
        'result',
        'tenant_uuid',
        schema=schema,
        existing_type=postgresql.UUID(as_uuid=True),
        server_default=None,
    )


def downgrade() -> None:
    schema = context.get_context().version_table_schema
    default_uuid_sql = sa.text(f"'{DEFAULT_RESULT_SCOPE_UUID}'::uuid")

    op.alter_column(
        'result',
        'user_uuid',
        schema=schema,
        existing_type=postgresql.UUID(as_uuid=True),
        server_default=default_uuid_sql,
    )
    op.alter_column(
        'result',
        'tenant_uuid',
        schema=schema,
        existing_type=postgresql.UUID(as_uuid=True),
        server_default=default_uuid_sql,
    )
