import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, inspect
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from ai_document_plugin_service.ai.common.config import DatabaseConfig
from ai_document_plugin_service.ai.persistence.schema import create_persistence_schema
from ai_document_plugin_service.api.types import TemplateDetail

logger = logging.getLogger(__name__)

JsonValue = Mapping[str, Any] | Sequence[Any]


class Database(ABC):
    @abstractmethod
    async def create_template(
        self,
        uuid: str,
        title: str,
        content: JsonValue,
    ) -> None:
        """Create a new template in a database backend."""

    @abstractmethod
    async def save_assignments(
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
    async def save_template(
        self,
        uuid: str,
        title: str,
        content: JsonValue,
    ) -> None:
        """Persist a template in a database backend."""

    @abstractmethod
    async def get_assignments(
        self,
        knowledge_model_uuid: str,
        template_uuid: str,
    ) -> JsonValue | None:
        """Get assignments from a database backend."""

    @abstractmethod
    async def list_templates(self) -> list[dict[str, str]]:
        """List available templates from a database backend."""

    @abstractmethod
    async def get_template(self, template_uuid: UUID) -> TemplateDetail | None:
        """Get a template record from a database backend."""

    @abstractmethod
    async def save_result(
        self,
        template_uuid: str,
        knowledge_model_uuid: str,
        user_uuid: str,
        tenant_uuid: str,
        prepolished_markdown: str,
        markdown: str,
    ) -> None:
        """Persist a markdown result in a database backend."""

    @abstractmethod
    async def save_stats(
        self,
        template_uuid: UUID,
        knowledge_model_uuid: UUID,
        user_uuid: UUID,
        tenant_uuid: UUID,
        stats: JsonValue,
    ) -> None:
        """Persist a stats result in a database backend."""

    @abstractmethod
    async def update_result(
        self,
        template_uuid: UUID,
        knowledge_model_uuid: UUID,
        user_uuid: UUID,
        tenant_uuid: UUID,
        markdown: str,
    ) -> None:
        """Persist a markdown result in a database backend."""


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
        self.engine = create_async_engine(self.dsn)
        schema = create_persistence_schema(self.schema_name)
        self.metadata = schema.metadata
        self.assignment_table = schema.assignment_table
        self.template_table = schema.template_table
        self.result_table = schema.result_table
        self._database_verified = False

    async def dispose(self) -> None:
        """Close the engine's connection pool. Call on shutdown / when done with this instance."""
        await self.engine.dispose()

    def _list_existing_tables(self, connection: Connection) -> set[str]:
        return set(inspect(connection).get_table_names(schema=self.schema_name))

    async def _ensure_schema(self) -> None:
        if self._database_verified:
            return

        async with self.engine.connect() as connection:
            existing_tables = await connection.run_sync(self._list_existing_tables)

        required_tables = {'alembic_version', 'template', 'assignment', 'result'}
        missing_tables = sorted(required_tables - existing_tables)

        if missing_tables:
            msg = (
                f'Database schema "{self.schema_name}" is not ready. Missing tables: {", ".join(missing_tables)}. '
                'Startup migrations should create or update these tables. Check the application startup logs and '
                'database configuration.'
            )
            raise RuntimeError(msg)

        self._database_verified = True

    async def save_assignments(
        self,
        knowledge_model_uuid: str,
        knowledge_model_name: str,
        knowledge_model_version: str,
        assignments: JsonValue,
        template_uuid: str,
        stats: JsonValue | None = None,
        created_at: datetime | None = None,
    ) -> None:
        await self._ensure_schema()
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

        async with self.engine.begin() as connection:
            await connection.execute(upsert_statement)

        logger.debug(
            'Saved assignments for KM package id=%s to %s.assignments',
            knowledge_model_uuid,
            self.schema_name,
        )

    async def create_template(
        self,
        uuid: str,
        title: str,
        content: JsonValue,
    ) -> None:
        await self._ensure_schema()
        statement = postgresql_insert(self.template_table).values(
            uuid=uuid,
            title=title,
            content=content,
        )

        try:
            async with self.engine.begin() as connection:
                await connection.execute(statement)
        except IntegrityError as exc:
            msg = f'Template with title "{title}" already exists.'
            raise ValueError(msg) from exc

        logger.debug(
            'Created template uuid=%s in %s.template',
            uuid,
            self.schema_name,
        )

    async def save_template(
        self,
        uuid: str,
        title: str,
        content: JsonValue,
    ) -> None:
        await self._ensure_schema()
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

        async with self.engine.begin() as connection:
            await connection.execute(upsert_statement)

        logger.debug(
            'Saved template uuid=%s to %s.template',
            uuid,
            self.schema_name,
        )

    async def get_assignments(
        self,
        knowledge_model_uuid: str,
        template_uuid: str,
    ) -> JsonValue | None:
        await self._ensure_schema()

        statement = self.assignment_table.select().where(
            (self.assignment_table.c.knowledge_model_uuid == knowledge_model_uuid)
            & (self.assignment_table.c.template_uuid == template_uuid),
        )

        async with self.engine.begin() as connection:
            result = await connection.execute(statement)
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

    async def list_templates(self) -> list[dict[str, str]]:
        await self._ensure_schema()
        statement = self.template_table.select().order_by(self.template_table.c.title.asc())

        async with self.engine.begin() as connection:
            result = await connection.execute(statement)
            rows = result.fetchall()

        return [
            {
                'uuid': str(row.uuid),
                'title': row.title,
            }
            for row in rows
        ]

    async def get_template(self, template_uuid: UUID) -> TemplateDetail | None:
        await self._ensure_schema()
        statement = self.template_table.select().where(self.template_table.c.uuid == template_uuid)

        async with self.engine.begin() as connection:
            result = await connection.execute(statement)
            row = result.fetchone()

        if row is None:
            logger.debug(
                'No template found for uuid=%s in %s.template',
                template_uuid,
                self.schema_name,
            )
            return None
        return TemplateDetail(
            uuid=row.uuid,
            title=row.title,
            content=row.content,
        )

    async def save_result(
        self,
        template_uuid: str,
        knowledge_model_uuid: str,
        user_uuid: str,
        tenant_uuid: str,
        prepolished_markdown: str,
        markdown: str,
    ) -> None:
        await self._ensure_schema()
        now = datetime.now(tz=UTC)

        statement = postgresql_insert(self.result_table).values(
            template_uuid=template_uuid,
            knowledge_model_uuid=knowledge_model_uuid,
            user_uuid=user_uuid,
            tenant_uuid=tenant_uuid,
            dmp_pre_polished=prepolished_markdown,
            dmp=markdown,
            created_at=now,
            updated_at=now,
        )

        upsert_statement = statement.on_conflict_do_update(
            constraint='pk_result',
            set_={
                'dmp_pre_polished': statement.excluded.dmp_pre_polished,
                'dmp': statement.excluded.dmp,
                'updated_at': statement.excluded.updated_at,
            },
        )

        async with self.engine.begin() as connection:
            await connection.execute(upsert_statement)

        logger.debug(
            'Saved result for KM package id=%s to %s.result',
            knowledge_model_uuid,
            self.schema_name,
        )

    async def save_stats(
        self,
        template_uuid: UUID,
        knowledge_model_uuid: UUID,
        user_uuid: UUID,
        tenant_uuid: UUID,
        stats: JsonValue,
    ) -> None:
        await self._ensure_schema()
        now = datetime.now(tz=UTC)

        statement = (
            self.result_table.update()
            .where(
                (self.result_table.c.knowledge_model_uuid == knowledge_model_uuid)
                & (self.result_table.c.template_uuid == template_uuid)
                & (self.result_table.c.user_uuid == user_uuid)
                & (self.result_table.c.tenant_uuid == tenant_uuid)
            )
            .values(stats=stats, updated_at=now)
        )

        async with self.engine.begin() as connection:
            result = await connection.execute(statement)

        if result.rowcount == 0:
            msg = 'Cannot save stats because result row does not exist yet. Save dmp and dmp_pre_polished first.'
            raise ValueError(msg)

        logger.debug(
            'Saved stats for KM package id=%s to %s.result',
            knowledge_model_uuid,
            self.schema_name,
        )

    async def update_result(
        self,
        template_uuid: UUID,
        knowledge_model_uuid: UUID,
        user_uuid: UUID,
        tenant_uuid: UUID,
        markdown: str,
    ) -> None:
        await self._ensure_schema()
        now = datetime.now(tz=UTC)

        statement = (
            self.result_table.update()
            .where(
                (self.result_table.c.knowledge_model_uuid == knowledge_model_uuid)
                & (self.result_table.c.template_uuid == template_uuid)
                & (self.result_table.c.user_uuid == user_uuid)
                & (self.result_table.c.tenant_uuid == tenant_uuid)
            )
            .values(
                dmp=markdown,
                updated_at=now,
            )
        )

        async with self.engine.begin() as connection:
            result = await connection.execute(statement)

        if result.rowcount == 0:
            msg = 'Cannot save result because result row does not exist yet. Create the row first before updating dmp.'
            raise ValueError(msg)

        logger.debug(
            'Updated result for KM package id=%s in %s.result',
            knowledge_model_uuid,
            self.schema_name,
        )


def _validate_identifier(value: str) -> str:
    if not value.replace('_', '').isalnum() or not (value[0].isalpha() or value[0] == '_'):
        msg = f'Invalid SQL identifier: {value}'
        raise ValueError(msg)
    return value
