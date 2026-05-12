"""Create result table.

Revision ID: 20260506_01
Revises:
Create Date: 2026-05-06 00:00:00
"""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260506_01'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = context.get_context().version_table_schema
    op.create_table(
        'result',
        sa.Column('knowledge_model_uuid', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('template_uuid', postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.Column('stats', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ['template_uuid'],
            [f'{schema}.template.uuid'],
            name='fk_result_template_uuid',
        ),
        sa.ForeignKeyConstraint(
            ['knowledge_model_uuid', 'template_uuid'],
            [
                f'{schema}.assignment.knowledge_model_uuid',
                f'{schema}.assignment.template_uuid',
            ],
            name='fk_result_assignment',
        ),
        sa.PrimaryKeyConstraint(
            'knowledge_model_uuid',
            'template_uuid',
            name='pk_result',
        ),
        schema=schema,
    )


def downgrade() -> None:
    schema = context.get_context().version_table_schema
    op.drop_table('result', schema=schema)
