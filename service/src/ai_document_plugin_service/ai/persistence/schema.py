from dataclasses import dataclass

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID


@dataclass(frozen=True)
class PersistenceSchema:
    metadata: MetaData
    assignment_table: Table
    template_table: Table
    generation_table: Table


def create_persistence_schema(schema_name: str) -> PersistenceSchema:
    metadata = MetaData(schema=schema_name)

    template_table = Table(
        'template',
        metadata,
        Column('uuid', UUID(as_uuid=True), primary_key=True),
        Column('title', Text, nullable=False),
        Column('content', JSON, nullable=False),
        Column('tenant_uuid', UUID(as_uuid=True), nullable=False),
        # NULL user_uuid marks a tenant-wide template shared with the whole tenant;
        # a set user_uuid marks a personal template owned by that user.
        Column('user_uuid', UUID(as_uuid=True), nullable=True),
        # NULL means the template is live; a set value marks it as (soft) deleted.
        # Soft-deleted templates are excluded from the unique title constraints below
        # so a title can be reused once the template that held it is deleted.
        Column('deleted_at', DateTime(timezone=True), nullable=True),
        Index(
            'uq_template_title_tenant_wide',
            'title',
            'tenant_uuid',
            unique=True,
            postgresql_where=text('user_uuid IS NULL AND deleted_at IS NULL'),
        ),
        # ... and unique per user among that user's personal templates.
        Index(
            'uq_template_title_tenant_user',
            'title',
            'tenant_uuid',
            'user_uuid',
            unique=True,
            postgresql_where=text('user_uuid IS NOT NULL AND deleted_at IS NULL'),
        ),
    )

    assignment_table = Table(
        'assignment',
        metadata,
        Column('knowledge_model_uuid', UUID(as_uuid=True), primary_key=True),
        Column('knowledge_model_name', Text, primary_key=False),
        Column('knowledge_model_version', Text, primary_key=False),
        Column(
            'created_at',
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        Column('assignments', JSON, nullable=False),
        Column('stats', JSON, nullable=True),
        Column('template_uuid', UUID(as_uuid=True), ForeignKey('template.uuid'), primary_key=True, nullable=False),
    )

    generation_table = Table(
        'generation',
        metadata,
        Column('run_id', UUID(as_uuid=True), primary_key=True),
        Column('questionnaire_uuid', UUID(as_uuid=True), nullable=False),
        Column('template_uuid', UUID(as_uuid=True), ForeignKey('template.uuid'), nullable=False),
        Column('title', Text, nullable=False),
        # Only known once the run has fetched the questionnaire from DSW.
        Column('knowledge_model_uuid', UUID(as_uuid=True), nullable=True),
        Column('user_uuid', UUID(as_uuid=True), nullable=False),
        Column('tenant_uuid', UUID(as_uuid=True), nullable=False),
        Column('status', Text, nullable=False),
        Column('error_type', Text, nullable=True),
        Column('error_message', Text, nullable=True),
        Column('result_markdown', Text, nullable=True),
        Column('progress_message', Text, nullable=True),

        # Columns used for analysis only:
        Column('dmp_pre_polished', Text, nullable=True),
        # at start same as result_markdown, but not editable. Older rows don't have the original value saved
        Column('dmp_polished', Text, nullable=True),
        # LLM usage per pipeline step. NULL when the step did not run (assignment is skipped
        # when cached assignments are reused) or the run has no stats (failed or old runs).
        Column('assignment_llm_calls', Integer, nullable=True),
        Column('assignment_input_tokens', Integer, nullable=True),
        Column('assignment_output_tokens', Integer, nullable=True),
        Column('generation_llm_calls', Integer, nullable=True),
        Column('generation_input_tokens', Integer, nullable=True),
        Column('generation_output_tokens', Integer, nullable=True),
        Column('polishing_llm_calls', Integer, nullable=True),
        Column('polishing_input_tokens', Integer, nullable=True),
        Column('polishing_output_tokens', Integer, nullable=True),
        Column('elapsed_seconds', Float, nullable=True),
        Column(
            'created_at',
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        Column(
            'updated_at',
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        Index(
            'ix_generation_questionnaire_user_tenant_created_at',
            'questionnaire_uuid',
            'user_uuid',
            'tenant_uuid',
            'created_at',
        ),
    )

    return PersistenceSchema(
        metadata=metadata,
        assignment_table=assignment_table,
        template_table=template_table,
        generation_table=generation_table,
    )
