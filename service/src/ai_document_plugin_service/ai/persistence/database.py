import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column, DateTime, MetaData, Table, Text, UniqueConstraint, create_engine, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ai_document_plugin_service.ai.common.config import DatabaseConfig

logger = logging.getLogger(__name__)

JsonValue = Mapping[str, Any] | Sequence[Any]


class Database(ABC):
    @abstractmethod
    def create_template(
        self,
        uuid: str,
        title: str,
        content: JsonValue,
    ) -> None:
        """Create a new template in a database backend."""

    @abstractmethod
    def save_assignments(
        self,
        knowledge_model_uuid: str,
        knowledge_model_name: str,
        knowledge_model_version: str,
        assignments: JsonValue,
        template_uuid: str,
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
        knowledge_model_uuid: str,
        template_uuid: str,
    ) -> JsonValue | None:
        """Get assignments from a database backend."""

    @abstractmethod
    def list_templates(self) -> list[dict[str, str]]:
        """List available templates from a database backend."""

    @abstractmethod
    def get_template(self, template_uuid: str) -> dict[str, Any] | None:
        """Get a template record from a database backend."""


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
        self.assignment_table = Table(
            'assignment',
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
            Column('template_uuid', UUID(as_uuid=True), primary_key=True, foreign_key='template.uuid'),
        )
        self.template_table = Table(
            'template',
            self.metadata,
            Column('uuid', UUID(as_uuid=True), primary_key=True),
            Column('title', Text, nullable=False),
            Column('content', JSON, nullable=False),
            UniqueConstraint('title', name='uq_template_title'),
        )

    def _ensure_schema(self) -> None:
        self.metadata.create_all(self.engine)

        create_unique_index_statement = text(
            f'CREATE UNIQUE INDEX IF NOT EXISTS uq_template_title ON {self.schema_name}.template (title)'
        )

        try:
            with self.engine.begin() as connection:
                connection.execute(create_unique_index_statement)
        except SQLAlchemyError as exc:
            msg = (
                f'Unable to enforce uniqueness for {self.schema_name}.template.title. '
                'Check for duplicate template titles in the database.'
            )
            raise ValueError(msg) from exc

    def save_assignments(
        self,
        knowledge_model_uuid: str,
        knowledge_model_name: str,
        knowledge_model_version: str,
        assignments: JsonValue,
        template_uuid: str,
        stats: JsonValue | None = None,
        created_at: datetime | None = None,
    ) -> None:
        self._ensure_schema()
        created_at_value = created_at or datetime.now(tz=UTC)
        statement = postgresql_insert(self.assignment_table).values(
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
                self.assignment_table.c.knowledge_model_uuid,
                self.assignment_table.c.template_uuid,
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

    def create_template(
        self,
        uuid: str,
        title: str,
        content: JsonValue,
    ) -> None:
        self._ensure_schema()
        statement = postgresql_insert(self.template_table).values(
            uuid=uuid,
            title=title,
            content=content,
        )

        try:
            with self.engine.begin() as connection:
                connection.execute(statement)
        except IntegrityError as exc:
            msg = f'Template with title "{title}" already exists.'
            raise ValueError(msg) from exc

        logger.debug(
            'Created template uuid=%s in %s.template',
            uuid,
            self.schema_name,
        )

    def save_template(
        self,
        uuid: str,
        title: str,
        content: JsonValue,
    ) -> None:
        self._ensure_schema()
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
        knowledge_model_uuid: str,
        template_uuid: str,
    ) -> JsonValue | None:
        self._ensure_schema()

        statement = self.assignment_table.select().where(
            (self.assignment_table.c.knowledge_model_uuid == knowledge_model_uuid)
            & (self.assignment_table.c.template_uuid == template_uuid),
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

    def list_templates(self) -> list[dict[str, str]]:
        self._ensure_schema()
        statement = self.template_table.select().order_by(self.template_table.c.title.asc())

        with self.engine.begin() as connection:
            result = connection.execute(statement)
            rows = result.fetchall()

        return [
            {
                'uuid': str(row.uuid),
                'title': row.title,
            }
            for row in rows
        ]

    def get_template(self, template_uuid: str) -> dict[str, Any] | None:
        self._ensure_schema()
        statement = self.template_table.select().where(self.template_table.c.uuid == template_uuid)

        with self.engine.begin() as connection:
            result = connection.execute(statement)
            row = result.fetchone()

        if row is None:
            logger.debug(
                'No template found for uuid=%s in %s.template',
                template_uuid,
                self.schema_name,
            )
            return None

        return {
            'uuid': str(row.uuid),
            'title': row.title,
            'content': row.content,
        }


def _validate_identifier(value: str) -> str:
    if not value.replace('_', '').isalnum() or not (value[0].isalpha() or value[0] == '_'):
        msg = f'Invalid SQL identifier: {value}'
        raise ValueError(msg)
    return value
