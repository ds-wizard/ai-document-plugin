"""Store assignments as one row per leaf section and track template and assignment updates for cache invalidation.

Assignments move from a JSON list to one row per leaf section, keyed by a content-derived section id.

Revision ID: 20261023_01
Revises: 37cb34f64ef7
Create Date: 2026-10-23 00:00:00
"""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision = '20261023_01'
down_revision = '37cb34f64ef7'
branch_labels = None
depends_on = None


def _qualified_column_reference(schema: str | None, table: str, column: str) -> str:
    if schema:
        return f'{schema}.{table}.{column}'
    return f'{table}.{column}'


def upgrade() -> None:
    schema = context.get_context().version_table_schema

    # Cached assignments are regenerated in the new format on the next run.
    op.execute(sa.table('assignment', schema=schema).delete())
    op.drop_column('assignment', 'assignments', schema=schema)

    for table in ('template', 'assignment'):
        op.add_column(
            table,
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            schema=schema,
        )

    op.create_table(
        'assignment_section',
        sa.Column('knowledge_model_uuid', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('template_uuid', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('section_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('question_paths', postgresql.ARRAY(sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ['knowledge_model_uuid', 'template_uuid'],
            [
                _qualified_column_reference(schema, 'assignment', 'knowledge_model_uuid'),
                _qualified_column_reference(schema, 'assignment', 'template_uuid'),
            ],
            name='fk_assignment_section_assignment',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('knowledge_model_uuid', 'template_uuid', 'section_id', name='pk_assignment_section'),
        schema=schema,
    )
