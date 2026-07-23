from uuid import UUID, uuid4

import fastapi

from ai_document_plugin_service.api.auth import verify_authenticated
from ai_document_plugin_service.api.types import (
    PipelineRunRequest,
    PipelineRunResponse,
    PipelineSaveRequest,
    PipelineStatus,
    PipelineStatusResponse,
    TemplateCreateRequest,
    TemplateDetail,
    TemplateListItem,
    TemplateUpdateRequest,
    _model_from_fields,
)
from ai_document_plugin_service.di import AuthenticatedDI, ConfigDI, PipelineServiceDI, TemplateServiceDI
from ai_document_plugin_service.service.errors import NotFoundError

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


@protected_router.post('/pipelines/run')
async def start_pipeline(
    payload: PipelineRunRequest,
    auth: AuthenticatedDI,
    config: ConfigDI,
    templates: TemplateServiceDI,
    pipeline: PipelineServiceDI,
) -> PipelineRunResponse:
    template = await templates.get(auth, payload.template_uuid)

    run_id = str(uuid4())
    pipeline.enqueue_pipeline_job(
        run_id,
        payload,
        template.title,
        auth,
        config,
    )
    return _model_from_fields(
        PipelineRunResponse,
        status=PipelineStatus.ACCEPTED,
        run_id=run_id,
        questionnaire_uuid=payload.questionnaire_uuid,
        user_uuid=auth.user_uuid,
        tenant_uuid=auth.tenant_uuid,
        template_uuid=payload.template_uuid,
        template_title=template.title,
    )


@protected_router.get('/pipelines/status/{run_id}')
def get_pipeline_status(run_id: str, pipeline: PipelineServiceDI) -> PipelineStatusResponse:
    status = pipeline.get_pipeline_status(run_id)
    if status is None:
        raise NotFoundError(NotFoundError.PIPELINE_RUN_MESSAGE)
    return status


@protected_router.post('/pipelines/status/{run_id}/save')
async def save_pipeline_result(
    run_id: str, save_request: PipelineSaveRequest, pipeline: PipelineServiceDI, auth: AuthenticatedDI
) -> PipelineStatusResponse:
    return await pipeline.update_pipeline_result(run_id, save_request, auth)
