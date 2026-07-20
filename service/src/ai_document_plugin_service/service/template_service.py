from uuid import UUID

from ai_document_plugin_service.ai.persistence.database import Database, TemplateRecord
from ai_document_plugin_service.ai.persistence.errors import TemplateTitleConflictError
from ai_document_plugin_service.api.auth import AuthenticatedUser
from ai_document_plugin_service.api.types import (
    TemplateCreateRequest,
    TemplateDetail,
    TemplateListItem,
    TemplateScope,
    TemplateUpdateRequest,
    _model_from_fields,
)
from ai_document_plugin_service.service.errors import (
    AccessDeniedError,
    ConflictError,
    NotFoundError,
    ValidationError,
)


class TemplateService:
    NOT_FOUND_MESSAGE = 'Template not found'
    TENANT_MUTATION_MESSAGE = 'Only administrators can modify tenant-wide templates.'
    TENANT_CREATE_MESSAGE = 'Only administrators can create common templates.'
    TITLE_REQUIRED_MESSAGE = 'Template title is required'
    SECTIONS_REQUIRED_MESSAGE = 'Template JSON must contain a top-level "sections" array.'

    def __init__(self, database: Database) -> None:
        self._database = database

    async def list(self, auth: AuthenticatedUser) -> list[TemplateListItem]:
        rows = await self._database.list_templates(auth.tenant_uuid, auth.user_uuid)
        return [_model_from_fields(TemplateListItem, **row) for row in rows]

    async def get(self, auth: AuthenticatedUser, template_uuid: UUID) -> TemplateDetail:
        record = await self._database.get_template(template_uuid, auth.tenant_uuid)
        if record is None or not self._can_view(auth, record):
            raise NotFoundError(self.NOT_FOUND_MESSAGE)
        return self._to_detail(record)

    async def create(self, auth: AuthenticatedUser, payload: TemplateCreateRequest) -> TemplateDetail:
        trimmed_title = self._validate_payload(payload.title, payload.content)
        owner_uuid = None if payload.scope is TemplateScope.TENANT else auth.user_uuid
        if not self._can_mutate(auth, payload.scope, owner_uuid):
            raise AccessDeniedError(self.TENANT_CREATE_MESSAGE)

        try:
            template_uuid = await self._database.create_template(
                title=trimmed_title,
                content=payload.content,
                tenant_uuid=auth.tenant_uuid,
                user_uuid=owner_uuid,
            )
        except TemplateTitleConflictError as error:
            raise ConflictError(str(error)) from error

        return _model_from_fields(
            TemplateDetail,
            uuid=template_uuid,
            title=trimmed_title,
            content=payload.content,
            scope=payload.scope,
        )

    async def update(
        self,
        auth: AuthenticatedUser,
        template_uuid: UUID,
        payload: TemplateUpdateRequest,
    ) -> TemplateDetail:
        # todo: this needs to be handled in a single transaction!
        trimmed_title = self._validate_payload(payload.title, payload.content)
        record = await self._database.get_template(template_uuid, auth.tenant_uuid)
        if record is None:
            raise NotFoundError(self.NOT_FOUND_MESSAGE)
        if not self._can_mutate(auth, record.scope, record.user_uuid):
            if record.scope is TemplateScope.TENANT:
                raise AccessDeniedError(self.TENANT_MUTATION_MESSAGE)
            raise NotFoundError(self.NOT_FOUND_MESSAGE)

        try:
            await self._database.update_template(
                template_uuid=template_uuid,
                tenant_uuid=auth.tenant_uuid,
                title=trimmed_title,
                content=payload.content,
            )
        except TemplateTitleConflictError as error:
            raise ConflictError(str(error)) from error

        return _model_from_fields(
            TemplateDetail,
            uuid=template_uuid,
            title=trimmed_title,
            content=payload.content,
            scope=record.scope,
        )

    async def delete(self, auth: AuthenticatedUser, template_uuid: UUID) -> None:
        record = await self._database.get_template(template_uuid, auth.tenant_uuid)
        if record is None:
            raise NotFoundError(self.NOT_FOUND_MESSAGE)
        if not self._can_mutate(auth, record.scope, record.user_uuid):
            if record.scope is TemplateScope.TENANT:
                raise AccessDeniedError(self.TENANT_MUTATION_MESSAGE)
            raise NotFoundError(self.NOT_FOUND_MESSAGE)
        await self._database.delete_template(template_uuid, auth.tenant_uuid)

    @staticmethod
    def _can_view(auth: AuthenticatedUser, record: TemplateRecord) -> bool:
        return record.scope is TemplateScope.TENANT or record.user_uuid == auth.user_uuid

    @staticmethod
    def _can_mutate(auth: AuthenticatedUser, scope: TemplateScope, owner_uuid: UUID | None) -> bool:
        if scope is TemplateScope.TENANT:
            return auth.is_admin
        return owner_uuid == auth.user_uuid

    @staticmethod
    def _to_detail(record: TemplateRecord) -> TemplateDetail:
        return _model_from_fields(
            TemplateDetail,
            uuid=record.uuid,
            title=record.title,
            content=record.content,
            scope=record.scope,
        )

    def _validate_payload(self, title: str, content: dict) -> str:
        trimmed_title = title.strip()
        if not trimmed_title:
            raise ValidationError(self.TITLE_REQUIRED_MESSAGE)

        sections = content.get('sections')
        if not isinstance(sections, list):
            raise ValidationError(self.SECTIONS_REQUIRED_MESSAGE)

        return trimmed_title
