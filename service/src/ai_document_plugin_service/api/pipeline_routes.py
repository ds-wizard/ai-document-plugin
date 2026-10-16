import logging
from typing import Annotated
from uuid import UUID

import fastapi

from ai_document_plugin_service.api.router_helper import api_router
from ai_document_plugin_service.api.types import (
    PipelineExportRequest,
    PipelineRunRequest,
    PipelineSaveRequest,
    PipelineStatusResponse,
    PipelineSummaryResponse,
)
from ai_document_plugin_service.di import (
    AuthenticatedDI,
    ConfigDI,
    ExportServiceDI,
    PipelineServiceDI,
    TemplateServiceDI,
)
from ai_document_plugin_service.service.errors import NotFoundError
from ai_document_plugin_service.utils.docx_export import DOCX_MEDIA_TYPE

logger = logging.getLogger(__name__)
pipeline_router = api_router()


@pipeline_router.post('/pipelines/run')
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
        template,
        auth,
        config,
        getattr(request.state, 'trace_uuid', None),
    )
    status = await pipeline.get_pipeline_status(run_id, auth)
    if status is None:
        raise NotFoundError(NotFoundError.PIPELINE_RUN_MESSAGE)
    return status


@pipeline_router.get('/pipelines')
async def list_pipeline_history(
    pipeline: PipelineServiceDI,
    auth: AuthenticatedDI,
    questionnaire_uuid: Annotated[UUID, fastapi.Query(alias='questionnaireUuid')],
) -> list[PipelineSummaryResponse]:
    return await pipeline.list_history(questionnaire_uuid, auth)


@pipeline_router.get('/pipelines/status/{run_id}')
async def get_pipeline_status(
    run_id: UUID,
    pipeline: PipelineServiceDI,
    auth: AuthenticatedDI,
) -> PipelineStatusResponse:
    status = await pipeline.get_pipeline_status(run_id, auth)
    if status is None:
        raise NotFoundError(NotFoundError.PIPELINE_RUN_MESSAGE)
    return status


@pipeline_router.post('/pipelines/status/{run_id}/save')
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


@pipeline_router.post(
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
