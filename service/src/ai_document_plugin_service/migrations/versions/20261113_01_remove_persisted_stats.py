"""Remove persisted run statistics.

Lossy migration. Drops the LLM call counts, token counts and elapsed time from generation_stats (the table keeps
the pre-polished and polished documents) and drops assignment.stats. The statistics are emitted to the
application log instead. Existing values are discarded.
"""

from alembic import context, op

revision = '20261113_01'
down_revision = '20261023_01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = context.get_context().version_table_schema
    op.drop_column('generation_stats', 'assignment_llm_calls', schema=schema)
    op.drop_column('generation_stats', 'assignment_input_tokens', schema=schema)
    op.drop_column('generation_stats', 'assignment_output_tokens', schema=schema)
    op.drop_column('generation_stats', 'generation_llm_calls', schema=schema)
    op.drop_column('generation_stats', 'generation_input_tokens', schema=schema)
    op.drop_column('generation_stats', 'generation_output_tokens', schema=schema)
    op.drop_column('generation_stats', 'polishing_llm_calls', schema=schema)
    op.drop_column('generation_stats', 'polishing_input_tokens', schema=schema)
    op.drop_column('generation_stats', 'polishing_output_tokens', schema=schema)
    op.drop_column('generation_stats', 'elapsed_seconds', schema=schema)

    op.drop_column('assignment', 'stats', schema=schema)
