"""Record the newest DSW questionnaire event a run was generated from.

Lets the plugin tell whether the questionnaire answers changed since the run. Existing runs have no value (NULL)
and are reported as unknown.

Revision ID: 20261120_01
Revises: 20261113_01
Create Date: 2026-11-20 00:00:00
"""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision = '20261120_01'
down_revision = '20261113_01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = context.get_context().version_table_schema
    op.add_column(
        'generation',
        sa.Column('source_event_uuid', postgresql.UUID(as_uuid=True), nullable=True),
        schema=schema,
    )
