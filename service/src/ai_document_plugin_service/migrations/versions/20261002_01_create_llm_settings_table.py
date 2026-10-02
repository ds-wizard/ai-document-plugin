"""Create llm_settings table.

Stores the LLM connection settings (model, API URL, API key, worker limit) per
tenant. They used to live in the DSW plugin settings, which are delivered to
every user's browser, so the API key was readable by any user. The service now
reads them from this table at the start of each pipeline run.

Existing settings are not migrated: the service cannot read the DSW plugin
settings. An administrator has to save them once through the plugin settings.

Revision ID: 20261002_01
Revises: 20260911_01
Create Date: 2026-10-02 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20261002_01'
down_revision = '20260911_01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = context.get_context().version_table_schema

    op.create_table(
        'llm_settings',
        sa.Column('tenant_uuid', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('model', sa.Text(), nullable=False),
        sa.Column('api_url', sa.Text(), nullable=False),
        sa.Column('api_key', sa.Text(), nullable=False),
        sa.Column('max_workers', sa.Integer(), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint('tenant_uuid', name='pk_llm_settings'),
        schema=schema,
    )
