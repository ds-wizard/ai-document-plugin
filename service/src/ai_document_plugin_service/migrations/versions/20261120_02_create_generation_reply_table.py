"""Store the replies a run was generated from.

One row per reply with its value as DSW sends it (see questionnaire_snapshot), so that what changed in the
questionnaire since the run can be told. Existing runs have no rows; generation.source_event_uuid being NULL marks them.

Revision ID: 20261120_02
Revises: 20261120_01
Create Date: 2026-11-20 00:00:00
"""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision = '20261120_02'
down_revision = '20261120_01'
branch_labels = None
depends_on = None


def _qualified_column_reference(schema: str | None, table: str, column: str) -> str:
    if schema:
        return f'{schema}.{table}.{column}'
    return f'{table}.{column}'


def upgrade() -> None:
    schema = context.get_context().version_table_schema

    op.create_table(
        'generation_reply',
        sa.Column('run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('path', sa.Text(), nullable=False),
        sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('display_text', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('run_id', 'path', name='pk_generation_reply'),
        sa.ForeignKeyConstraint(
            ['run_id'],
            [_qualified_column_reference(schema, 'generation', 'run_id')],
            name='fk_generation_reply_run_id',
            ondelete='CASCADE',
        ),
        schema=schema,
    )
