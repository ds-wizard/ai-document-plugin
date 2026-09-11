"""

Lossy migration. Merges Results table into Generation table on best effort basis.

Revision ID: 20260911_01
Revises: 20260807_01
Create Date: 2026-09-11 00:00:00
"""

from __future__ import annotations

import logging

import sqlalchemy as sa
from alembic import context, op

# revision identifiers, used by Alembic.
revision = '20260911_01'
down_revision = '20260807_01'
branch_labels = None
depends_on = None

logger = logging.getLogger(__name__)


def _qualified_table_reference(schema: str | None, table: str) -> str:
    if schema:
        return f'{schema}.{table}'
    return table


def upgrade() -> None:
    schema = context.get_context().version_table_schema

    op.add_column('generation', sa.Column('dmp_pre_polished', sa.Text(), nullable=True), schema=schema)
    op.add_column('generation', sa.Column('dmp_polished', sa.Text(), nullable=True), schema=schema)
    op.add_column('generation', sa.Column('llm_calls', sa.Integer(), nullable=True), schema=schema)
    op.add_column('generation', sa.Column('input_tokens', sa.Integer(), nullable=True), schema=schema)
    op.add_column('generation', sa.Column('output_tokens', sa.Integer(), nullable=True), schema=schema)
    op.add_column('generation', sa.Column('elapsed_seconds', sa.Float(), nullable=True), schema=schema)

    # The schema comes from Alembic config, not user input.
    generation_reference = _qualified_table_reference(schema, 'generation')
    result_reference = _qualified_table_reference(schema, 'result')
    connection = op.get_bind()

    total = connection.execute(sa.text(f'SELECT count(*) FROM {result_reference}')).scalar_one()  # noqa: S608

    # The stats JSON has the shape built by the old PipelineMetricsCollector._build_summary_section.
    # A NULL stats leaves all four stat columns NULL (json_array_elements(NULL) yields no rows).
    backfill = connection.execute(
        sa.text(
            f"""
            UPDATE {generation_reference} AS g
            SET dmp_pre_polished = r.dmp_pre_polished,
                input_tokens     = (r.stats -> 'totals' ->> 'input_tokens')::integer,
                output_tokens    = (r.stats -> 'totals' ->> 'output_tokens')::integer,
                llm_calls        = (SELECT sum((step ->> 'llm_calls')::integer)
                                    FROM json_array_elements(r.stats -> 'rows') AS step),
                elapsed_seconds  = (r.stats -> 'meta' ->> 'elapsed_seconds')::double precision
            FROM {result_reference} AS r
            WHERE g.run_id = (
                SELECT g2.run_id FROM {generation_reference} AS g2
                WHERE g2.knowledge_model_uuid = r.knowledge_model_uuid
                  AND g2.template_uuid        = r.template_uuid
                  AND g2.user_uuid            = r.user_uuid
                  AND g2.tenant_uuid          = r.tenant_uuid
                  AND g2.status               = 'succeeded'
                  AND g2.result_markdown      = r.dmp
                ORDER BY g2.updated_at DESC
                LIMIT 1
            )
            """  # noqa: S608
        )
    )
    logger.info(
        'Backfilled generation rows from result table: %s matched, %s unmatched (dropped)',
        backfill.rowcount,
        total - backfill.rowcount,
    )

    op.drop_table('result', schema=schema)
