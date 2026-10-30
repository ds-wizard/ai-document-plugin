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

    def __init__(self, database: Database, cover_definition: dict) -> None:
        self._database = database
        self._cover_page_version = str(cover_definition['version'])
        self._cover_page_sections = cover_definition['sections']

    async def list(self, auth: AuthenticatedUser) -> list[TemplateListItem]:
        records = await self._database.list_templates(auth.tenant_uuid, auth.user_uuid)
        return [self._to_list_item(record) for record in records]

    async def get(self, auth: AuthenticatedUser, template_uuid: UUID) -> TemplateDetail:
        record = await self._database.get_template(template_uuid, auth.tenant_uuid)
        if record is None or not self._can_view(auth, record):
            raise NotFoundError(self.NOT_FOUND_MESSAGE)
        return self._to_detail(record)

    async def create(self, auth: AuthenticatedUser, payload: TemplateCreateRequest) -> TemplateDetail:
        owner_uuid = None if payload.scope is TemplateScope.TENANT else auth.user_uuid
        if not self._can_mutate(auth, payload.scope, owner_uuid):
            raise AccessDeniedError(self.TENANT_CREATE_MESSAGE)

        trimmed_title = self._validate_payload(payload.title, payload.content)

        content = payload.content.copy()
        sections = payload.content['sections'].copy()
        if payload.has_cover_page:
            sections = self._cover_page_sections + sections
        content['sections'] = sections

        try:
            template_uuid = await self._database.create_template(
                title=trimmed_title,
                content=content,
                tenant_uuid=auth.tenant_uuid,
                user_uuid=owner_uuid,
                cover_page_version=self._cover_page_version if payload.has_cover_page else None,
            )
        except TemplateTitleConflictError as error:
            raise ConflictError(str(error)) from error

        return TemplateDetail(
            uuid=template_uuid,
            title=trimmed_title,
            content=payload.content,
            has_cover_page=payload.has_cover_page,
            scope=payload.scope,
        )

    async def update(
        self,
        auth: AuthenticatedUser,
        template_uuid: UUID,
        payload: TemplateUpdateRequest,
    ) -> TemplateDetail:
        async with self._database.transaction():
            record = await self._database.get_template(template_uuid, auth.tenant_uuid, for_update=True)
            if record is None:
                raise NotFoundError(self.NOT_FOUND_MESSAGE)
            if not self._can_mutate(auth, record.scope, record.user_uuid):
                if record.scope is TemplateScope.TENANT:
                    raise AccessDeniedError(self.TENANT_MUTATION_MESSAGE)
                raise NotFoundError(self.NOT_FOUND_MESSAGE)

            trimmed_title = self._validate_payload(payload.title, payload.content)

            content = payload.content.copy()
            sections = payload.content['sections'].copy()
            if payload.has_cover_page:
                sections = self._cover_page_sections + sections
            content['sections'] = sections

            try:
                await self._database.update_template(
                    template_uuid=template_uuid,
                    tenant_uuid=auth.tenant_uuid,
                    title=trimmed_title,
                    content=content,
                    cover_page_version=self._cover_page_version if payload.has_cover_page else None,
                )
            except TemplateTitleConflictError as error:
                raise ConflictError(str(error)) from error

        return TemplateDetail(
            uuid=template_uuid,
            title=trimmed_title,
            content=payload.content,
            has_cover_page=payload.has_cover_page,
            scope=record.scope,
        )

    async def delete(self, auth: AuthenticatedUser, template_uuid: UUID) -> None:
        async with self._database.transaction():
            record = await self._database.get_template(template_uuid, auth.tenant_uuid, for_update=True)
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
    def _to_list_item(record: TemplateRecord) -> TemplateListItem:
        return TemplateListItem(
            uuid=record.uuid,
            title=record.title,
            scope=record.scope,
            has_cover_page=record.has_cover_page,
        )

    def _to_detail(self, record: TemplateRecord) -> TemplateDetail:
        content = record.content.copy()
        sections = record.content['sections'].copy()
        if record.has_cover_page:
            sections = sections[len(self._cover_page_sections) :]
        content['sections'] = sections

        return TemplateDetail(
            uuid=record.uuid,
            title=record.title,
            content=content,
            scope=record.scope,
            has_cover_page=record.has_cover_page,
        )

    def _validate_payload(self, title: str, content: dict) -> str:
        trimmed_title = title.strip()
        if not trimmed_title:
            raise ValidationError(self.TITLE_REQUIRED_MESSAGE)

        sections = content.get('sections')
        if not isinstance(sections, list):
            raise ValidationError(self.SECTIONS_REQUIRED_MESSAGE)

        return trimmed_title
