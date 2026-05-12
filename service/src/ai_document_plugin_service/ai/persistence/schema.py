from dataclasses import dataclass

from sqlalchemy import JSON, Column, DateTime, MetaData, Table, Text, UniqueConstraint, func
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
        UniqueConstraint('title', name='uq_template_title'),
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
        Column('stats', JSON, nullable=False),
        Column('template_uuid', UUID(as_uuid=True), primary_key=True, foreign_key='template.uuid'),
    )

    result_table = Table(
        'result',
        metadata,
        Column('knowledge_model_uuid', UUID(as_uuid=True), primary_key=True),
        Column('template_uuid', UUID(as_uuid=True), primary_key=True),
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
    )

    return PersistenceSchema(
        metadata=metadata,
        assignment_table=assignment_table,
        template_table=template_table,
        result_table=result_table,
    )
