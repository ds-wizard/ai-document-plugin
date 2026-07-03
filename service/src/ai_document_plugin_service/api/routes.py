from uuid import uuid4

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
    _model_from_fields,
)
from ai_document_plugin_service.di import AuthenticatedDI, ConfigDI, DatabaseDI, PipelineServiceDI

public_router = fastapi.APIRouter()
protected_router = fastapi.APIRouter(dependencies=[fastapi.Depends(verify_authenticated)])


@public_router.get('/health')
def health_check() -> dict[str, str]:
    return {'status': 'healthy'}


@protected_router.get('/templates')
async def list_templates(database: DatabaseDI) -> list[TemplateListItem]:
    return [_model_from_fields(TemplateListItem, **item) for item in await database.list_templates()]


@protected_router.get('/templates/{template_uuid}')
async def get_template(template_uuid: str, database: DatabaseDI) -> TemplateDetail:
    template = await database.get_template(template_uuid)

    if template is None:
        raise fastapi.HTTPException(status_code=404, detail='Template not found')

    return _model_from_fields(
        TemplateDetail,
        uuid=template['uuid'],
        title=template['title'],
        content=template['content'],
    )


@protected_router.post('/templates', status_code=201)
async def create_template(payload: TemplateCreateRequest, database: DatabaseDI) -> TemplateDetail:
    trimmed_title = payload.title.strip()
    if not trimmed_title:
        raise fastapi.HTTPException(status_code=400, detail='Template title is required')

    sections = payload.content.get('sections')
    if not isinstance(sections, list):
        raise fastapi.HTTPException(
            status_code=400,
            detail='Template JSON must contain a top-level "sections" array.',
        )

    template_uuid = str(uuid4())

    try:
        await database.create_template(
            uuid=template_uuid,
            title=trimmed_title,
            content=payload.content,
        )
    except ValueError as error:
        raise fastapi.HTTPException(status_code=409, detail=str(error)) from error

    return _model_from_fields(
        TemplateDetail,
        uuid=template_uuid,
        title=trimmed_title,
        content=payload.content,
    )


@protected_router.post('/pipelines/run')
async def start_pipeline(
    payload: PipelineRunRequest,
    auth: AuthenticatedDI,
    config: ConfigDI,
    database: DatabaseDI,
    pipeline: PipelineServiceDI,
) -> PipelineRunResponse:
    template = await database.get_template(payload.template_uuid)

    if template is None:
        raise fastapi.HTTPException(status_code=404, detail='Template not found')

    run_id = str(uuid4())
    pipeline.enqueue_pipeline_job(
        run_id,
        payload,
        template['title'],
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
        template_title=template['title'],
    )


@protected_router.get('/pipelines/status/{run_id}')
def get_pipeline_status(run_id: str, pipeline: PipelineServiceDI) -> PipelineStatusResponse:
    status = pipeline.get_pipeline_status(run_id)
    if status is None:
        raise fastapi.HTTPException(status_code=404, detail='Pipeline run not found')
    return status


@protected_router.post('/pipelines/status/{run_id}/save')
async def save_pipeline_result(
    run_id: str, save_request: PipelineSaveRequest, pipeline: PipelineServiceDI
) -> PipelineStatusResponse:
    return await pipeline.update_pipeline_result(run_id, save_request)
