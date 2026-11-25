from dataclasses import dataclass

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID


@dataclass(frozen=True)
class PersistenceSchema:
    metadata: MetaData
    assignment_table: Table
    assignment_section_table: Table
    template_table: Table
    generation_table: Table
    generation_stats_table: Table
    generation_reply_table: Table
    llm_settings_table: Table


def create_persistence_schema(schema_name: str) -> PersistenceSchema:
    metadata = MetaData(schema=schema_name)

    template_table = Table(
        'template',
        metadata,
        Column('uuid', UUID(as_uuid=True), primary_key=True),
        Column('title', Text, nullable=False),
        Column('content', JSON, nullable=False),
        Column('updated_at', DateTime(timezone=True), nullable=False, server_default=func.now()),
        # NULL means the template has no cover page; a value identifies the selected version.
        Column('cover_page_version', Text, nullable=True),
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
        Column('updated_at', DateTime(timezone=True), nullable=False, server_default=func.now()),
        Column('template_uuid', UUID(as_uuid=True), ForeignKey('template.uuid'), primary_key=True, nullable=False),
    )

    # Question paths assigned to one leaf section, one row per distinct leaf of the template tree.
    assignment_section_table = Table(
        'assignment_section',
        metadata,
        Column('knowledge_model_uuid', UUID(as_uuid=True), primary_key=True),
        Column('template_uuid', UUID(as_uuid=True), primary_key=True),
        # Derived from the section's title and content and those of its ancestors (see template_sections_to_records).
        Column('section_id', UUID(as_uuid=True), primary_key=True),
        Column('question_paths', ARRAY(Text), nullable=False),
        ForeignKeyConstraint(
            ['knowledge_model_uuid', 'template_uuid'],
            ['assignment.knowledge_model_uuid', 'assignment.template_uuid'],
            ondelete='CASCADE',
        ),
    )

    generation_table = Table(
        'generation',
        metadata,
        Column('run_id', UUID(as_uuid=True), primary_key=True),
        Column('questionnaire_uuid', UUID(as_uuid=True), nullable=False),
        Column('template_uuid', UUID(as_uuid=True), ForeignKey('template.uuid'), nullable=False),
        Column('title', Text, nullable=False),
        # Existing rows predate language selection and keep a NULL value after migration.
        Column('language', Text, nullable=True),
        # Only known once the run has fetched the questionnaire from DSW.
        Column('knowledge_model_uuid', UUID(as_uuid=True), nullable=True),
        Column('user_uuid', UUID(as_uuid=True), nullable=False),
        Column('tenant_uuid', UUID(as_uuid=True), nullable=False),
        Column('status', Text, nullable=False),
        Column('error_type', Text, nullable=True),
        Column('error_message', Text, nullable=True),
        Column('result_markdown', Text, nullable=True),
        Column('progress_message', Text, nullable=True),
        Column('named_version', Text, nullable=True),
        # Newest DSW event of the questionnaire when the run read it (see QuestionnaireStateService).
        # The nil UUID for a questionnaire without events; NULL for runs from before this column existed.
        Column('source_event_uuid', UUID(as_uuid=True), nullable=True),
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

    # Analysis-only documents, one row per generation (created together with it).
    generation_stats_table = Table(
        'generation_stats',
        metadata,
        Column('run_id', UUID(as_uuid=True), ForeignKey('generation.run_id', ondelete='CASCADE'), primary_key=True),
        # Request trace id; NULL for runs created before it was recorded.
        Column('trace_id', UUID(as_uuid=True), nullable=True),
        Column('dmp_pre_polished', Text, nullable=True),
        # at start same as generation.result_markdown, but not editable. Older rows don't have the original value saved
        Column('dmp_polished', Text, nullable=True),
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
    )

    # The replies a generation was made from, one row per reply (see questionnaire_snapshot). Written together with
    # the generation succeeding; a generation without rows predates this table or had no replies, and the former
    # is told by generation.source_event_uuid being NULL.
    generation_reply_table = Table(
        'generation_reply',
        metadata,
        Column('run_id', UUID(as_uuid=True), ForeignKey('generation.run_id', ondelete='CASCADE'), primary_key=True),
        Column('path', Text, primary_key=True),
        Column('reply_type', Text, nullable=False),
        # Which one is set depends on the reply type, see StoredReply.
        Column('text_value', Text, nullable=True),
        Column('uuid_value', UUID(as_uuid=True), nullable=True),
        Column('uuid_values', ARRAY(UUID(as_uuid=True)), nullable=True),
        Column('display_text', Text, nullable=True),
        CheckConstraint(
            "reply_type IN ('string', 'integration', 'answer', 'item_select', 'multi_choice', 'item_list')",
            name='ck_generation_reply_type',
        ),
        CheckConstraint(
            "(reply_type IN ('string', 'integration')"
            ' AND text_value IS NOT NULL AND uuid_value IS NULL AND uuid_values IS NULL)'
            " OR (reply_type IN ('answer', 'item_select')"
            ' AND uuid_value IS NOT NULL AND text_value IS NULL AND uuid_values IS NULL)'
            " OR (reply_type IN ('multi_choice', 'item_list')"
            ' AND uuid_values IS NOT NULL AND text_value IS NULL AND uuid_value IS NULL)',
            name='ck_generation_reply_value',
        ),
    )

    # LLM connection settings, one row per tenant. Managed by tenant administrators.
    llm_settings_table = Table(
        'llm_settings',
        metadata,
        Column('tenant_uuid', UUID(as_uuid=True), primary_key=True),
        Column('model', Text, nullable=False),
        Column('api_url', Text, nullable=False),
        # Encrypted with the 'encryption_key' config value, never stored in plaintext.
        Column('api_key', Text, nullable=False),
        # NULL lets the LLM client fall back to its default worker count.
        Column('max_workers', Integer, nullable=True),
        Column('updated_by', UUID(as_uuid=True), nullable=False),
        Column(
            'updated_at',
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )

    return PersistenceSchema(
        metadata=metadata,
        assignment_table=assignment_table,
        assignment_section_table=assignment_section_table,
        template_table=template_table,
        generation_table=generation_table,
        generation_stats_table=generation_stats_table,
        generation_reply_table=generation_reply_table,
        llm_settings_table=llm_settings_table,
    )
