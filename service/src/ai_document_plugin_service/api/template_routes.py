import logging
from uuid import UUID

import fastapi

from ai_document_plugin_service.api.router_helper import api_router
from ai_document_plugin_service.api.types import (
    CoverPagePreviewDefinition,
    TemplateCreateRequest,
    TemplateDetail,
    TemplateListItem,
    TemplateUpdateRequest,
)
from ai_document_plugin_service.di import (
    AuthenticatedDI,
    ConfigDI,
    ExportServiceDI,
    TemplateServiceDI,
)
from ai_document_plugin_service.service.export_service import JSON_MEDIA_TYPE

logger = logging.getLogger(__name__)
templates_router = api_router()


@templates_router.get('/cover-page/preview')
def get_cover_page_preview(config: ConfigDI) -> CoverPagePreviewDefinition:
    return CoverPagePreviewDefinition.from_definition(config.cover_definition)


@templates_router.get('/templates')
async def list_templates(templates: TemplateServiceDI, auth: AuthenticatedDI) -> list[TemplateListItem]:
    return await templates.list(auth)


@templates_router.get('/templates/{template_uuid}')
async def get_template(template_uuid: UUID, templates: TemplateServiceDI, auth: AuthenticatedDI) -> TemplateDetail:
    return await templates.get(auth, template_uuid)


@templates_router.post('/templates', status_code=201)
async def create_template(
    payload: TemplateCreateRequest, templates: TemplateServiceDI, auth: AuthenticatedDI
) -> TemplateDetail:
    return await templates.create(auth, payload)


@templates_router.put('/templates/{template_uuid}')
async def update_template(
    template_uuid: UUID,
    payload: TemplateUpdateRequest,
    templates: TemplateServiceDI,
    auth: AuthenticatedDI,
) -> TemplateDetail:
    return await templates.update(auth, template_uuid, payload)


@templates_router.delete('/templates/{template_uuid}', status_code=204)
async def delete_template(template_uuid: UUID, templates: TemplateServiceDI, auth: AuthenticatedDI) -> None:
    await templates.delete(auth, template_uuid)


@templates_router.get(
    '/templates/{template_uuid}/export',
    response_class=fastapi.Response,
    responses={200: {'content': {JSON_MEDIA_TYPE: {}}}},
)
async def export_template_as_json(
    template_uuid: UUID, exports: ExportServiceDI, auth: AuthenticatedDI
) -> fastapi.Response:
    export = await exports.export_template_as_json(template_uuid, auth)
    return fastapi.Response(content=export.content, media_type=JSON_MEDIA_TYPE)
