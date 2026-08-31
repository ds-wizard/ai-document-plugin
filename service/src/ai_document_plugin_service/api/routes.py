import logging
from typing import Annotated
from uuid import UUID

import fastapi

from ai_document_plugin_service.api.auth import verify_authenticated
from ai_document_plugin_service.api.types import (
    PipelineExportRequest,
    PipelineRunRequest,
    PipelineSaveRequest,
    PipelineStatusResponse,
    PipelineSummaryResponse,
    TemplateCreateRequest,
    TemplateDetail,
    TemplateListItem,
    TemplateUpdateRequest,
)
from ai_document_plugin_service.di import (
    AuthenticatedDI,
    ConfigDI,
    ExportServiceDI,
    PipelineServiceDI,
    TemplateServiceDI,
)
from ai_document_plugin_service.service.errors import NotFoundError
from ai_document_plugin_service.service.export_service import JSON_MEDIA_TYPE
from ai_document_plugin_service.utils.docx_export import DOCX_MEDIA_TYPE

logger = logging.getLogger(__name__)

public_router = fastapi.APIRouter()
protected_router = fastapi.APIRouter(dependencies=[fastapi.Depends(verify_authenticated)])


@public_router.get('/health')
def health_check() -> dict[str, str]:
    return {'status': 'healthy'}


@protected_router.get('/templates')
async def list_templates(templates: TemplateServiceDI, auth: AuthenticatedDI) -> list[TemplateListItem]:
    return await templates.list(auth)


@protected_router.get('/templates/{template_uuid}')
async def get_template(template_uuid: UUID, templates: TemplateServiceDI, auth: AuthenticatedDI) -> TemplateDetail:
    return await templates.get(auth, template_uuid)


@protected_router.post('/templates', status_code=201)
async def create_template(
    payload: TemplateCreateRequest, templates: TemplateServiceDI, auth: AuthenticatedDI
) -> TemplateDetail:
    return await templates.create(auth, payload)


@protected_router.put('/templates/{template_uuid}')
async def update_template(
    template_uuid: UUID,
    payload: TemplateUpdateRequest,
    templates: TemplateServiceDI,
    auth: AuthenticatedDI,
) -> TemplateDetail:
    return await templates.update(auth, template_uuid, payload)


@protected_router.delete('/templates/{template_uuid}', status_code=204)
async def delete_template(template_uuid: UUID, templates: TemplateServiceDI, auth: AuthenticatedDI) -> None:
    await templates.delete(auth, template_uuid)


@protected_router.get(
    '/templates/{template_uuid}/export',
    response_class=fastapi.Response,
    responses={200: {'content': {JSON_MEDIA_TYPE: {}}}},
)
async def export_template_as_json(
    template_uuid: UUID, exports: ExportServiceDI, auth: AuthenticatedDI
) -> fastapi.Response:
    export = await exports.export_template_as_json(template_uuid, auth)
    return fastapi.Response(
        content=export.content,
        media_type=JSON_MEDIA_TYPE
    )


@protected_router.post('/pipelines/run')
async def start_pipeline(
    request: fastapi.Request,
    payload: PipelineRunRequest,
    auth: AuthenticatedDI,
    config: ConfigDI,
    templates: TemplateServiceDI,
    pipeline: PipelineServiceDI,
) -> PipelineStatusResponse:
    template = await templates.get(auth, payload.template_uuid)

    run_id = await pipeline.enqueue_pipeline_job(
        payload,
        template.title,
        auth,
        config,
        getattr(request.state, 'trace_uuid', '-'),
    )
    status = await pipeline.get_pipeline_status(run_id, auth)
    if status is None:
        raise NotFoundError(NotFoundError.PIPELINE_RUN_MESSAGE)
    return status


@protected_router.get('/pipelines')
async def list_pipeline_history(
    pipeline: PipelineServiceDI,
    auth: AuthenticatedDI,
    questionnaire_uuid: Annotated[UUID, fastapi.Query(alias='questionnaireUuid')],
) -> list[PipelineSummaryResponse]:
    return await pipeline.list_history(questionnaire_uuid, auth)


@protected_router.get('/pipelines/status/{run_id}')
async def get_pipeline_status(
    run_id: UUID,
    pipeline: PipelineServiceDI,
    auth: AuthenticatedDI,
) -> PipelineStatusResponse:
    status = await pipeline.get_pipeline_status(run_id, auth)
    if status is None:
        raise NotFoundError(NotFoundError.PIPELINE_RUN_MESSAGE)
    return status


@protected_router.post('/pipelines/status/{run_id}/save')
async def save_pipeline_result(
    run_id: UUID, save_request: PipelineSaveRequest, pipeline: PipelineServiceDI, auth: AuthenticatedDI
) -> PipelineStatusResponse:
    logger.info(
        'Pipeline result update requested',
        extra={
            'run_id': run_id,
            'tenant_uuid': str(auth.tenant_uuid),
            'user_uuid': str(auth.user_uuid),
            'result_markdown_length': len(save_request.result_markdown),
        },
    )
    return await pipeline.update_pipeline_result(run_id, save_request, auth)


@protected_router.post(
    '/pipelines/status/{run_id}/export/docx',
    response_class=fastapi.Response,
    responses={200: {'content': {DOCX_MEDIA_TYPE: {}}}},
)
async def export_pipeline_result_as_docx(
    run_id: UUID, export_request: PipelineExportRequest, exports: ExportServiceDI, auth: AuthenticatedDI
) -> fastapi.Response:
    export = await exports.export_result_as_docx(run_id, export_request, auth)
    return fastapi.Response(
        content=export.content,
        media_type=DOCX_MEDIA_TYPE,
        headers={'Content-Disposition': f'attachment; filename="{export.file_name}"'},
    )
