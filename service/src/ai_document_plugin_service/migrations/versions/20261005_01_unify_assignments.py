"""Store cover sections in templates and use one assignment cache."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects.postgresql import JSONB

from ai_document_plugin_service.ai.common.config import load_config

revision = '20261005_01'
down_revision = '20260929_01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = context.get_context().version_table_schema
    config = context.config.attributes.get('app_config') or load_config(context.config.attributes.get('config_path'))
    template = sa.table(
        'template',
        sa.column('content', sa.JSON()),
        sa.column('cover_page_version', sa.Text()),
        schema=schema,
    )
    content = sa.cast(template.c.content, JSONB)
    sections = sa.literal(config.cover_definition['sections'], type_=JSONB)
    op.execute(
        template.update()
        .where(template.c.cover_page_version.is_not(None))
        .values(
            content=sa.func.jsonb_set(
                content, sa.cast(['sections'], sa.ARRAY(sa.Text())), sections.op('||')(content['sections'])
            )
        ),
    )

    # Cached assignments are regenerated against the complete stored template.
    op.execute(sa.table('assignment', schema=schema).delete())
    op.add_column('assignment', sa.Column('assignments', sa.JSON(), nullable=False), schema=schema)
    op.drop_column('assignment', 'content_assignments', schema=schema)
    op.drop_column('assignment', 'header_assignments', schema=schema)
