"""Create generation table.

Persists pipeline run status and history (previously only kept in an
in-memory, per-process store), scoped per user so each user's project tab
only ever lists their own generations.

Revision ID: 20260807_01
Revises: 20260720_01
Create Date: 2026-08-07 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260807_01'
down_revision = '20260720_01'
branch_labels = None
depends_on = None


def _qualified_column_reference(schema: str | None, table: str, column: str) -> str:
    if schema:
        return f'{schema}.{table}.{column}'
    return f'{table}.{column}'


def upgrade() -> None:
    schema = context.get_context().version_table_schema

    op.create_table(
        'generation',
        sa.Column('run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('questionnaire_uuid', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('template_uuid', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('knowledge_model_uuid', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('user_uuid', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_uuid', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('error_type', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('result_markdown', sa.Text(), nullable=True),
        sa.Column('progress_message', sa.Text(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ['template_uuid'],
            [_qualified_column_reference(schema, 'template', 'uuid')],
            name='fk_generation_template_uuid',
        ),
        sa.PrimaryKeyConstraint('run_id', name='pk_generation'),
        schema=schema,
    )

    op.create_index(
        'ix_generation_questionnaire_user_tenant_created_at',
        'generation',
        ['questionnaire_uuid', 'user_uuid', 'tenant_uuid', 'created_at'],
        schema=schema,
    )


def downgrade() -> None:
    schema = context.get_context().version_table_schema
    op.drop_index('ix_generation_questionnaire_user_tenant_created_at', 'generation', schema=schema)
    op.drop_table('generation', schema=schema)
