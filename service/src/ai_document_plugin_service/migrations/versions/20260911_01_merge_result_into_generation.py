"""Replace the result table with a per-run generation_stats table.

Lossy migration. Creates generation_stats (1:1 with generation) for analysis-only data
and the trace id, backfills it from the result table on a best effort basis, then drops
the result table. Result rows that cannot be matched to a succeeded generation are dropped.

Revision ID: 20260911_01
Revises: 20260831_02
Create Date: 2026-09-11 00:00:00
"""

from __future__ import annotations

import logging

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260911_01'
down_revision = '20260831_02'
branch_labels = None
depends_on = None

logger = logging.getLogger(__name__)


def _qualified_table_reference(schema: str | None, table: str) -> str:
    if schema:
        return f'{schema}.{table}'
    return table


def _qualified_column_reference(schema: str | None, table: str, column: str) -> str:
    return f'{_qualified_table_reference(schema, table)}.{column}'


def upgrade() -> None:
    schema = context.get_context().version_table_schema

    op.create_table(
        'generation_stats',
        sa.Column('run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('trace_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('dmp_pre_polished', sa.Text(), nullable=True),
        sa.Column('dmp_polished', sa.Text(), nullable=True),
        sa.Column('assignment_llm_calls', sa.Integer(), nullable=True),
        sa.Column('assignment_input_tokens', sa.Integer(), nullable=True),
        sa.Column('assignment_output_tokens', sa.Integer(), nullable=True),
        sa.Column('generation_llm_calls', sa.Integer(), nullable=True),
        sa.Column('generation_input_tokens', sa.Integer(), nullable=True),
        sa.Column('generation_output_tokens', sa.Integer(), nullable=True),
        sa.Column('polishing_llm_calls', sa.Integer(), nullable=True),
        sa.Column('polishing_input_tokens', sa.Integer(), nullable=True),
        sa.Column('polishing_output_tokens', sa.Integer(), nullable=True),
        sa.Column('elapsed_seconds', sa.Float(), nullable=True),
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
            ['run_id'],
            [_qualified_column_reference(schema, 'generation', 'run_id')],
            name='fk_generation_stats_run_id',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('run_id', name='pk_generation_stats'),
        schema=schema,
    )

    # The schema comes from Alembic config, not user input.
    generation_reference = _qualified_table_reference(schema, 'generation')
    generation_stats_reference = _qualified_table_reference(schema, 'generation_stats')
    result_reference = _qualified_table_reference(schema, 'result')
    connection = op.get_bind()

    total = connection.execute(sa.text(f'SELECT count(*) FROM {result_reference}')).scalar_one()  # ruff: ignore[hardcoded-sql-expression]

    # Result data is attached to the latest succeeded generation matching its DMP.
    backfill = connection.execute(
        sa.text(
            f"""
            INSERT INTO {generation_stats_reference} (
                run_id,
                dmp_pre_polished,
                assignment_llm_calls, assignment_input_tokens, assignment_output_tokens,
                generation_llm_calls, generation_input_tokens, generation_output_tokens,
                polishing_llm_calls, polishing_input_tokens, polishing_output_tokens,
                elapsed_seconds
            )
            SELECT g.run_id,
                   r.dmp_pre_polished,
                   (asg.step ->> 'llm_calls')::integer,
                   (asg.step ->> 'input_tokens')::integer,
                   (asg.step ->> 'output_tokens')::integer,
                   (gen.step ->> 'llm_calls')::integer,
                   (gen.step ->> 'input_tokens')::integer,
                   (gen.step ->> 'output_tokens')::integer,
                   (pol.step ->> 'llm_calls')::integer,
                   (pol.step ->> 'input_tokens')::integer,
                   (pol.step ->> 'output_tokens')::integer,
                   (r.stats -> 'meta' ->> 'elapsed_seconds')::double precision
            FROM {result_reference} AS r
            JOIN LATERAL (
                SELECT g2.run_id FROM {generation_reference} AS g2
                WHERE g2.knowledge_model_uuid = r.knowledge_model_uuid
                  AND g2.template_uuid        = r.template_uuid
                  AND g2.user_uuid            = r.user_uuid
                  AND g2.tenant_uuid          = r.tenant_uuid
                  AND g2.status               = 'succeeded'
                  AND g2.result_markdown      = r.dmp
                ORDER BY g2.updated_at DESC
                LIMIT 1
            ) AS g ON true
            LEFT JOIN LATERAL (
                SELECT e.step FROM json_array_elements(r.stats -> 'rows') AS e(step)
                WHERE e.step ->> 'step' = '1. Hierarchical assignment' LIMIT 1
            ) AS asg ON true
            LEFT JOIN LATERAL (
                SELECT e.step FROM json_array_elements(r.stats -> 'rows') AS e(step)
                WHERE e.step ->> 'step' = '2. DMP generator' LIMIT 1
            ) AS gen ON true
            LEFT JOIN LATERAL (
                SELECT e.step FROM json_array_elements(r.stats -> 'rows') AS e(step)
                WHERE e.step ->> 'step' = '3. DMP polisher' LIMIT 1
            ) AS pol ON true
            """  # ruff: ignore[hardcoded-sql-expression]
        )
    )
    logger.info(
        'Backfilled generation_stats rows from result table: %s matched, %s unmatched (dropped)',
        backfill.rowcount,
        total - backfill.rowcount,
    )

    op.drop_table('result', schema=schema)
