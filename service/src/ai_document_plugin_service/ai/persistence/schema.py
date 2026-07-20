from dataclasses import dataclass

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
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
    result_table: Table


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
        Index(
            'uq_template_title_tenant_wide',
            'title',
            'tenant_uuid',
            unique=True,
            postgresql_where=text('user_uuid IS NULL'),
        ),
        # ... and unique per user among that user's personal templates.
        Index(
            'uq_template_title_tenant_user',
            'title',
            'tenant_uuid',
            'user_uuid',
            unique=True,
            postgresql_where=text('user_uuid IS NOT NULL'),
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

    result_table = Table(
        'result',
        metadata,
        Column('knowledge_model_uuid', UUID(as_uuid=True), primary_key=True),
        Column('template_uuid', UUID(as_uuid=True), primary_key=True),
        Column(
            'user_uuid',
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        Column(
            'tenant_uuid',
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
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
        Column('dmp', Text, nullable=False),
        Column('dmp_pre_polished', Text, nullable=False),
        Column('stats', JSON, nullable=True),
        ForeignKeyConstraint(['template_uuid'], ['template.uuid'], name='fk_result_template_uuid'),
        ForeignKeyConstraint(
            ['knowledge_model_uuid', 'template_uuid'],
            ['assignment.knowledge_model_uuid', 'assignment.template_uuid'],
            name='fk_result_assignment',
        ),
    )

    return PersistenceSchema(
        metadata=metadata,
        assignment_table=assignment_table,
        template_table=template_table,
        result_table=result_table,
    )
