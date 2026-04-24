import logging
import uuid
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Column, DateTime, MetaData, Table, Text, create_engine, func
from sqlalchemy.dialects.postgresql import insert as postgresql_insert

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


class PostgresDB(Database):
    def __init__(
        self,
        dsn: str,
        schema_name: str = 'public',
    ) -> None:
        self.dsn = dsn
        self.schema_name = _validate_identifier(schema_name)
        self.engine = create_engine(self.dsn)
        self.metadata = MetaData(schema=self.schema_name)
        self.assignments_table = Table(
            'assignments',
            self.metadata,
            Column('knowledge_model_uuid', Text, primary_key=True),
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
        )
        self.template_table = Table(
            'template',
            self.metadata,
            Column('uuid', Text, primary_key=True),
            Column('title', Text, nullable=False),
            Column('content', JSON, nullable=False),
        )

    def save_assignments(
        self,
        knowledge_model_uuid: uuid.UUID,
        knowledge_model_name: str,
        knowledge_model_version: str,
        assignments: JsonValue,
        stats: JsonValue | None = None,
        created_at: datetime | None = None,
    ) -> None:
        self.metadata.create_all(self.engine)
        created_at_value = created_at or datetime.now(tz=timezone.utc)
        statement = postgresql_insert(self.assignments_table).values(
            knowledge_model_uuid=knowledge_model_uuid,
            knowledge_model_name=knowledge_model_name,
            knowledge_model_version=knowledge_model_version,
            created_at=created_at_value,
            assignments=assignments,
            stats=stats,
        )
        upsert_statement = statement.on_conflict_do_update(
            index_elements=[
                self.assignments_table.c.knowledge_model_package_id,
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


def _validate_identifier(value: str) -> str:
    if not value.replace('_', '').isalnum() or not (value[0].isalpha() or value[0] == '_'):
        msg = f'Invalid SQL identifier: {value}'
        raise ValueError(msg)
    return value
