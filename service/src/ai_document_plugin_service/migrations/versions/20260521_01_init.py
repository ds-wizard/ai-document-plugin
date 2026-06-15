"""Create result table.

Revision ID: 20260521_01
Revises:
Create Date: 2026-05-21 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260506_01'
down_revision = None
branch_labels = None
depends_on = None


def _qualified_column_reference(schema: str | None, table: str, column: str) -> str:
    if schema:
        return f'{schema}.{table}.{column}'
    return f'{table}.{column}'


def upgrade() -> None:
    schema = context.get_context().version_table_schema
    op.create_table(
        'template',
        sa.Column('uuid', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('content', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint('uuid'),
        sa.UniqueConstraint('title', name='uq_template_title'),
        schema=schema,
    )

    op.create_table(
        'assignment',
        sa.Column('knowledge_model_uuid', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('knowledge_model_name', sa.Text(), nullable=True),
        sa.Column('knowledge_model_version', sa.Text(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column('assignments', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('stats', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('template_uuid', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['template_uuid'],
            [_qualified_column_reference(schema, 'template', 'uuid')],
            name='fk_assignment_template_uuid',
        ),
        sa.PrimaryKeyConstraint(
            'knowledge_model_uuid',
            'template_uuid',
            name='pk_assignment',
        ),
        schema=schema,
    )

    op.create_table(
        'result',
        sa.Column('knowledge_model_uuid', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('template_uuid', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            'user_uuid',
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            'tenant_uuid',
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
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
        sa.Column('dmp', sa.Text(), nullable=False),
        sa.Column('dmp_pre_polished', sa.Text(), nullable=False),
        sa.Column('stats', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(
            ['template_uuid'],
            [_qualified_column_reference(schema, 'template', 'uuid')],
            name='fk_result_template_uuid',
        ),
        sa.ForeignKeyConstraint(
            ['knowledge_model_uuid', 'template_uuid'],
            [
                _qualified_column_reference(schema, 'assignment', 'knowledge_model_uuid'),
                _qualified_column_reference(schema, 'assignment', 'template_uuid'),
            ],
            name='fk_result_assignment',
        ),
        sa.PrimaryKeyConstraint(
            'knowledge_model_uuid',
            'template_uuid',
            'user_uuid',
            'tenant_uuid',
            name='pk_result',
        ),
        schema=schema,
    )


def downgrade() -> None:
    schema = context.get_context().version_table_schema
    op.drop_table('result', schema=schema)
    op.drop_table('assignment', schema=schema)
    op.drop_table('template', schema=schema)
