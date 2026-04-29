import logging
import uuid
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column, DateTime, MetaData, Table, Text, create_engine, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.engine import URL

from ai_document_plugin_service.ai.common.config import DatabaseConfig

logger = logging.getLogger(__name__)

JsonValue = Mapping[str, Any] | Sequence[Any]


class Database(ABC):
    @abstractmethod
    def save_assignments(
        self,
        knowledge_model_uuid: uuid.UUID,
        knowledge_model_name: str,
        knowledge_model_version: str,
        assignments: JsonValue,
        template_uuid: uuid.UUID,
        stats: JsonValue | None = None,
        created_at: datetime | None = None,
    ) -> None:
        """Persist assignments in a database backend."""

    @abstractmethod
    def save_template(
        self,
        uuid: str,
        title: str,
        content: JsonValue,
    ) -> None:
        """Persist a template in a database backend."""

    @abstractmethod
    def get_assignments(
        self,
        knowledge_model_uuid: uuid.UUID,
        template_uuid: uuid.UUID,
    ) -> JsonValue:
        """Get assignments from a database backend."""


class PostgresDB(Database):
    def __init__(
        self,
        config: DatabaseConfig,
    ) -> None:
        self.dsn = URL.create(
            drivername='postgresql+psycopg',
            username=config.user,
            password=config.password,
            host=config.host,
            port=config.port,
            database=config.name,
        )
        self.schema_name = _validate_identifier(config.schema)
        self.engine = create_engine(self.dsn)
        self.metadata = MetaData(schema=self.schema_name)
        self.assignments_table = Table(
            'assignments',
            self.metadata,
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
            Column('template_uuid', Text, primary_key=True, foreign_key='templates.uuid'),
        )
        self.template_table = Table(
            'template',
            self.metadata,
            Column('uuid', UUID(as_uuid=True), primary_key=True),
            Column('title', Text, nullable=False),
            Column('content', JSON, nullable=False),
        )

    def save_assignments(
        self,
        knowledge_model_uuid: uuid.UUID,
        knowledge_model_name: str,
        knowledge_model_version: str,
        assignments: JsonValue,
        template_uuid: uuid.UUID,
        stats: JsonValue | None = None,
        created_at: datetime | None = None,
    ) -> None:
        self.metadata.create_all(self.engine)
        created_at_value = created_at or datetime.now(tz=UTC)
        statement = postgresql_insert(self.assignments_table).values(
            knowledge_model_uuid=knowledge_model_uuid,
            knowledge_model_name=knowledge_model_name,
            knowledge_model_version=knowledge_model_version,
            created_at=created_at_value,
            assignments=assignments,
            stats=stats,
            template_uuid=template_uuid,
        )
        upsert_statement = statement.on_conflict_do_update(
            index_elements=[
                self.assignments_table.c.knowledge_model_uuid,
                self.assignments_table.c.template_uuid,
            ],
            set_={
                'created_at': statement.excluded.created_at,
                'assignments': statement.excluded.assignments,
            },
        )

        with self.engine.begin() as connection:
            connection.execute(upsert_statement)

        logger.debug(
            'Saved assignments for KM package id=%s to %s.assignments',
            knowledge_model_uuid,
            self.schema_name,
        )

    def save_template(
        self,
        uuid: str,
        title: str,
        content: JsonValue,
    ) -> None:
        self.metadata.create_all(self.engine)
        statement = postgresql_insert(self.template_table).values(
            uuid=uuid,
            title=title,
            content=content,
        )
        upsert_statement = statement.on_conflict_do_update(
            index_elements=[self.template_table.c.uuid],
            set_={
                'title': statement.excluded.title,
                'content': statement.excluded.content,
            },
        )

        with self.engine.begin() as connection:
            connection.execute(upsert_statement)

        logger.debug(
            'Saved template uuid=%s to %s.template',
            uuid,
            self.schema_name,
        )

    def get_assignments(
        self,
        knowledge_model_uuid: uuid.UUID,
        template_uuid: uuid.UUID,
    ) -> JsonValue | None:
        self.metadata.create_all(self.engine)

        statement = self.assignments_table.select().where(
            (self.assignments_table.c.knowledge_model_uuid == knowledge_model_uuid)
            & (self.assignments_table.c.template_uuid == template_uuid),
        )

        with self.engine.begin() as connection:
            result = connection.execute(statement)
            row = result.fetchone()

        if row is None:
            logger.debug(
                'No assignments found for KM package id=%s in %s.assignments',
                knowledge_model_uuid,
                self.schema_name,
            )
            return None

        logger.debug(
            'Loaded assignments for KM package id=%s from %s.assignments',
            knowledge_model_uuid,
            self.schema_name,
        )

        return row.assignments


def _validate_identifier(value: str) -> str:
    if not value.replace('_', '').isalnum() or not (value[0].isalpha() or value[0] == '_'):
        msg = f'Invalid SQL identifier: {value}'
        raise ValueError(msg)
    return value
