import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypedDict, Unpack
from uuid import UUID, uuid4

from sqlalchemy import ColumnElement, Connection, Row, and_, inspect, or_
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from ai_document_plugin_service.ai.common.config import DatabaseConfig
from ai_document_plugin_service.ai.persistence.errors import TemplateTitleConflictError
from ai_document_plugin_service.ai.persistence.schema import create_persistence_schema
from ai_document_plugin_service.api.types import TemplateScope

logger = logging.getLogger(__name__)

JsonValue = Mapping[str, Any] | Sequence[Any]

# Holds the connection of the transaction currently active on this asyncio task, if any.
# Set by PostgresDB.transaction(); read by every operation so it can join that transaction
# instead of opening its own. ContextVar is per-task, so concurrent requests stay isolated.
_active_connection: ContextVar[AsyncConnection | None] = ContextVar('active_connection', default=None)


@dataclass(frozen=True)
class TemplateRecord:
    """A raw template row. Carries the owner so callers can apply access rules."""

    uuid: UUID
    title: str
    content: dict
    tenant_uuid: UUID
    user_uuid: UUID | None

    @property
    def scope(self) -> TemplateScope:
        return TemplateScope.for_user(self.user_uuid)

    @classmethod
    def from_row(cls, row: Row) -> 'TemplateRecord':
        return cls(
            uuid=row.uuid,
            title=row.title,
            content=row.content,
            tenant_uuid=row.tenant_uuid,
            user_uuid=row.user_uuid,
        )


class GenerationUpdate(TypedDict, total=False):
    status: str
    knowledge_model_uuid: UUID | None
    error_type: str | None
    error_message: str | None
    result_markdown: str | None
    progress_message: str | None


@dataclass(frozen=True)
class GenerationRecord:
    """A raw generation (pipeline run) row."""

    run_id: UUID
    questionnaire_uuid: UUID
    template_uuid: UUID
    title: str
    knowledge_model_uuid: UUID | None
    user_uuid: UUID
    tenant_uuid: UUID
    status: str
    error_type: str | None
    error_message: str | None
    result_markdown: str | None
    progress_message: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: Row) -> 'GenerationRecord':
        return cls(
            run_id=row.run_id,
            questionnaire_uuid=row.questionnaire_uuid,
            template_uuid=row.template_uuid,
            title=row.title,
            knowledge_model_uuid=row.knowledge_model_uuid,
            user_uuid=row.user_uuid,
            tenant_uuid=row.tenant_uuid,
            status=row.status,
            error_type=row.error_type,
            error_message=row.error_message,
            result_markdown=row.result_markdown,
            progress_message=row.progress_message,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class Database(ABC):
    @abstractmethod
    def transaction(self) -> AbstractAsyncContextManager[None]:
        """Run several operations as one atomic transaction.

        Usage:
        async with database.transaction():
                record = await database.get_template(uuid, tenant, for_update=True)
                ...
                await database.update_template(...)

        Nesting is safe: an inner ``transaction()`` joins the outer one.
        """

    @abstractmethod
    async def create_template(
        self,
        title: str,
        content: JsonValue,
        tenant_uuid: UUID,
        user_uuid: UUID | None,
    ) -> UUID:
        """Create a new template in a database backend. Return created template UUID.

        A NULL user_uuid creates a tenant-wide template; a set user_uuid creates a
        personal template owned by that user.
        """

    @abstractmethod
    async def update_template(
        self,
        template_uuid: UUID,
        tenant_uuid: UUID,
        title: str,
        content: JsonValue,
    ) -> bool:
        """Update an existing template's title and content. Return whether a row was updated."""

    @abstractmethod
    async def delete_template(
        self,
        template_uuid: UUID,
        tenant_uuid: UUID,
    ) -> bool:
        """Soft-delete a template by marking it deleted. Return whether a row was updated."""

    @abstractmethod
    async def save_assignments(
        self,
        knowledge_model_uuid: UUID,
        knowledge_model_name: str,
        knowledge_model_version: str,
        assignments: JsonValue,
        template_uuid: UUID,
        stats: JsonValue | None = None,
        created_at: datetime | None = None,
    ) -> None:
        """Persist assignments in a database backend."""

    @abstractmethod
    async def save_template(
        self,
        uuid: UUID,
        title: str,
        content: JsonValue,
        tenant_uuid: UUID,
    ) -> None:
        """Persist a template in a database backend."""

    @abstractmethod
    async def get_assignments(
        self,
        knowledge_model_uuid: UUID,
        template_uuid: UUID,
    ) -> JsonValue | None:
        """Get assignments from a database backend."""

    @abstractmethod
    async def list_templates(self, tenant_uuid: UUID, user_uuid: UUID) -> list[TemplateRecord]:
        """List common templates plus the given user's personal templates."""

    @abstractmethod
    async def get_template(
        self,
        template_uuid: UUID,
        tenant_uuid: UUID,
        *,
        for_update: bool = False,
    ) -> TemplateRecord | None:
        """Get a raw template row by uuid and tenant, without visibility filtering.

        Pass ``for_update=True`` inside a ``transaction()`` to lock the row (SELECT ... FOR
        UPDATE) so it cannot change between this read and a follow-up write.
        """

    @abstractmethod
    async def save_result(
        self,
        template_uuid: UUID,
        knowledge_model_uuid: UUID,
        user_uuid: UUID,
        tenant_uuid: UUID,
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

    @abstractmethod
    async def create_generation(
        self,
        questionnaire_uuid: UUID,
        template_uuid: UUID,
        title: str,
        user_uuid: UUID,
        tenant_uuid: UUID,
        status: str,
    ) -> UUID:
        """Create a new generation (pipeline run) row. Return the created run id."""

    @abstractmethod
    async def update_generation(
        self,
        run_id: UUID,
        tenant_uuid: UUID,
        **updates: Unpack[GenerationUpdate],
    ) -> GenerationRecord | None:
        """Partially update a generation row and return the updated record.

        Only the fields passed in ``updates`` are changed; any nullable field may be
        set to ``None`` to clear it. Returns ``None`` if no row matches
        ``run_id``/``tenant_uuid``.
        """

    @abstractmethod
    async def get_generation(
        self,
        run_id: UUID,
        tenant_uuid: UUID,
        user_uuid: UUID,
    ) -> GenerationRecord | None:
        """Get a single generation row, scoped to its owning tenant and user."""

    @abstractmethod
    async def list_generations(
        self,
        questionnaire_uuid: UUID,
        tenant_uuid: UUID,
        user_uuid: UUID,
    ) -> list[GenerationRecord]:
        """List a user's generations for a project, newest first."""


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
        self.generation_table = schema.generation_table
        self._database_verified = False

    async def dispose(self) -> None:
        """Close the engine's connection pool. Call on shutdown / when done with this instance."""
        await self.engine.dispose()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        if _active_connection.get() is not None:
            # Already inside a transaction on this task: join it so we commit as one unit.
            yield
            return
        await self._ensure_schema()
        async with self.engine.begin() as connection:
            token = _active_connection.set(connection)
            try:
                yield
            finally:
                _active_connection.reset(token)

    @asynccontextmanager
    async def _connect(self) -> AsyncIterator[AsyncConnection]:
        """Yield a connection, joining the active transaction if one is open, else its own.

        Every operation goes through this instead of ``self.engine.begin()`` directly, so a
        call made inside ``transaction()`` reuses that transaction's connection rather than
        opening a second, independent one.

        Yields:
            AsyncConnection: A database connection for the current operation.
        """
        existing = _active_connection.get()
        if existing is not None:
            yield existing
            return
        async with self.engine.begin() as connection:
            yield connection

    def _list_existing_tables(self, connection: Connection) -> set[str]:
        return set(inspect(connection).get_table_names(schema=self.schema_name))

    async def _ensure_schema(self) -> None:
        if self._database_verified:
            return

        async with self.engine.connect() as connection:
            existing_tables = await connection.run_sync(self._list_existing_tables)

        required_tables = {'alembic_version', 'template', 'assignment', 'result', 'generation'}
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
        knowledge_model_uuid: UUID,
        knowledge_model_name: str,
        knowledge_model_version: str,
        assignments: JsonValue,
        template_uuid: UUID,
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

        async with self._connect() as connection:
            await connection.execute(upsert_statement)

        logger.debug(
            'Saved assignments for KM package id=%s to %s.assignments',
            knowledge_model_uuid,
            self.schema_name,
        )

    async def create_template(
        self,
        title: str,
        content: JsonValue,
        tenant_uuid: UUID,
        user_uuid: UUID | None,
    ) -> UUID:
        template_uuid = uuid4()
        await self._ensure_schema()
        statement = postgresql_insert(self.template_table).values(
            uuid=template_uuid,
            title=title,
            content=content,
            tenant_uuid=tenant_uuid,
            user_uuid=user_uuid,
        )

        try:
            async with self._connect() as connection:
                await connection.execute(statement)
        except IntegrityError as exc:
            raise TemplateTitleConflictError(title) from exc

        logger.debug(
            'Created template uuid=%s in %s.template',
            template_uuid,
            self.schema_name,
        )
        return template_uuid

    async def update_template(
        self,
        template_uuid: UUID,
        tenant_uuid: UUID,
        title: str,
        content: JsonValue,
    ) -> bool:
        await self._ensure_schema()
        statement = (
            self.template_table.update()
            .where(
                (self.template_table.c.uuid == template_uuid)
                & (self.template_table.c.tenant_uuid == tenant_uuid)
                & (self.template_table.c.deleted_at.is_(None)),
            )
            .values(title=title, content=content)
        )

        try:
            async with self._connect() as connection:
                result = await connection.execute(statement)
        except IntegrityError as exc:
            raise TemplateTitleConflictError(title) from exc

        logger.debug('Updated template uuid=%s in %s.template', template_uuid, self.schema_name)
        return result.rowcount > 0

    async def delete_template(
        self,
        template_uuid: UUID,
        tenant_uuid: UUID,
    ) -> bool:
        await self._ensure_schema()

        statement = (
            self.template_table.update()
            .where(
                (self.template_table.c.uuid == template_uuid)
                & (self.template_table.c.tenant_uuid == tenant_uuid)
                & (self.template_table.c.deleted_at.is_(None)),
            )
            .values(deleted_at=datetime.now(tz=UTC))
        )

        async with self._connect() as connection:
            result = await connection.execute(statement)

        logger.debug('Soft-deleted template uuid=%s in %s.template', template_uuid, self.schema_name)
        return result.rowcount > 0

    async def save_template(
        self,
        uuid: UUID,
        title: str,
        content: JsonValue,
        tenant_uuid: UUID,
    ) -> None:
        await self._ensure_schema()
        statement = postgresql_insert(self.template_table).values(
            uuid=uuid,
            title=title,
            content=content,
            tenant_uuid=tenant_uuid,
        )
        upsert_statement = statement.on_conflict_do_update(
            index_elements=[self.template_table.c.uuid],
            set_={
                'title': statement.excluded.title,
                'content': statement.excluded.content,
            },
        )

        async with self._connect() as connection:
            await connection.execute(upsert_statement)

        logger.debug(
            'Saved template uuid=%s to %s.template',
            uuid,
            self.schema_name,
        )

    async def get_assignments(
        self,
        knowledge_model_uuid: UUID,
        template_uuid: UUID,
    ) -> JsonValue | None:
        await self._ensure_schema()

        statement = self.assignment_table.select().where(
            (self.assignment_table.c.knowledge_model_uuid == knowledge_model_uuid)
            & (self.assignment_table.c.template_uuid == template_uuid),
        )

        async with self._connect() as connection:
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

    def _template_visible_to_user(self, tenant_uuid: UUID, user_uuid: UUID) -> ColumnElement[bool]:
        """Templates visible to a user: tenant-wide (NULL user) plus their own personal ones."""
        return and_(
            self.template_table.c.tenant_uuid == tenant_uuid,
            self.template_table.c.deleted_at.is_(None),
            or_(
                self.template_table.c.user_uuid.is_(None),
                self.template_table.c.user_uuid == user_uuid,
            ),
        )

    async def list_templates(self, tenant_uuid: UUID, user_uuid: UUID) -> list[TemplateRecord]:
        await self._ensure_schema()
        statement = (
            self.template_table.select()
            .where(self._template_visible_to_user(tenant_uuid, user_uuid))
            .order_by(self.template_table.c.title.asc())
        )

        async with self._connect() as connection:
            result = await connection.execute(statement)
            rows = result.fetchall()

        return [TemplateRecord.from_row(row) for row in rows]

    async def get_template(
        self,
        template_uuid: UUID,
        tenant_uuid: UUID,
        *,
        for_update: bool = False,
    ) -> TemplateRecord | None:
        await self._ensure_schema()
        statement = self.template_table.select().where(
            and_(
                self.template_table.c.uuid == template_uuid,
                self.template_table.c.tenant_uuid == tenant_uuid,
                self.template_table.c.deleted_at.is_(None),
            )
        )
        if for_update:
            statement = statement.with_for_update()

        async with self._connect() as connection:
            result = await connection.execute(statement)
            row = result.fetchone()

        if row is None:
            logger.debug(
                'No template found for uuid=%s tenant_uuid=%s in %s.template',
                template_uuid,
                tenant_uuid,
                self.schema_name,
            )
            return None
        return TemplateRecord.from_row(row)

    async def save_result(
        self,
        template_uuid: UUID,
        knowledge_model_uuid: UUID,
        user_uuid: UUID,
        tenant_uuid: UUID,
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

        async with self._connect() as connection:
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

        async with self._connect() as connection:
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

        async with self._connect() as connection:
            result = await connection.execute(statement)

        if result.rowcount == 0:
            msg = 'Cannot save result because result row does not exist yet. Create the row first before updating dmp.'
            raise ValueError(msg)

        logger.debug(
            'Updated result for KM package id=%s in %s.result',
            knowledge_model_uuid,
            self.schema_name,
        )

    async def create_generation(
        self,
        questionnaire_uuid: UUID,
        template_uuid: UUID,
        title: str,
        user_uuid: UUID,
        tenant_uuid: UUID,
        status: str,
    ) -> UUID:
        run_id = uuid4()
        await self._ensure_schema()
        statement = self.generation_table.insert().values(
            run_id=run_id,
            questionnaire_uuid=questionnaire_uuid,
            template_uuid=template_uuid,
            title=title,
            user_uuid=user_uuid,
            tenant_uuid=tenant_uuid,
            status=status,
        )

        async with self._connect() as connection:
            await connection.execute(statement)

        logger.debug(
            'Created generation run_id=%s in %s.generation',
            run_id,
            self.schema_name,
        )
        return run_id

    async def update_generation(
        self,
        run_id: UUID,
        tenant_uuid: UUID,
        **updates: Unpack[GenerationUpdate],
    ) -> GenerationRecord | None:
        await self._ensure_schema()

        unknown_fields = set(updates) - GenerationUpdate.__optional_keys__
        if unknown_fields:
            msg = f'Cannot update unknown generation fields: {sorted(unknown_fields)}'
            raise ValueError(msg)

        now = datetime.now(tz=UTC)
        statement = (
            self.generation_table.update()
            .where((self.generation_table.c.run_id == run_id) & (self.generation_table.c.tenant_uuid == tenant_uuid))
            .values(**updates, updated_at=now)
            .returning(*self.generation_table.c)
        )

        async with self._connect() as connection:
            result = await connection.execute(statement)
            row = result.fetchone()

        if row is None:
            return None

        logger.debug(
            'Updated generation run_id=%s in %s.generation',
            run_id,
            self.schema_name,
        )
        return GenerationRecord.from_row(row)

    async def get_generation(
        self,
        run_id: UUID,
        tenant_uuid: UUID,
        user_uuid: UUID,
    ) -> GenerationRecord | None:
        await self._ensure_schema()
        statement = self.generation_table.select().where(
            and_(
                self.generation_table.c.run_id == run_id,
                self.generation_table.c.tenant_uuid == tenant_uuid,
                self.generation_table.c.user_uuid == user_uuid,
            ),
        )

        async with self._connect() as connection:
            result = await connection.execute(statement)
            row = result.fetchone()

        return GenerationRecord.from_row(row) if row is not None else None

    async def list_generations(
        self,
        questionnaire_uuid: UUID,
        tenant_uuid: UUID,
        user_uuid: UUID,
    ) -> list[GenerationRecord]:
        await self._ensure_schema()
        statement = (
            self.generation_table.select()
            .where(
                and_(
                    self.generation_table.c.questionnaire_uuid == questionnaire_uuid,
                    self.generation_table.c.tenant_uuid == tenant_uuid,
                    self.generation_table.c.user_uuid == user_uuid,
                ),
            )
            .order_by(self.generation_table.c.created_at.desc())
        )

        async with self._connect() as connection:
            result = await connection.execute(statement)
            rows = result.fetchall()

        return [GenerationRecord.from_row(row) for row in rows]


def _validate_identifier(value: str) -> str:
    if not value.replace('_', '').isalnum() or not (value[0].isalpha() or value[0] == '_'):
        msg = f'Invalid SQL identifier: {value}'
        raise ValueError(msg)
    return value
