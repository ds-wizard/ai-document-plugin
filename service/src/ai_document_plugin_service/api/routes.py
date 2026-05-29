from uuid import uuid4

import fastapi

from ai_document_plugin_service.ai.common.config import LLMConfigOverride, load_config
from ai_document_plugin_service.ai.persistence.database import PostgresDB
from ai_document_plugin_service.api.jwt import extract_identity_from_token
from ai_document_plugin_service.api.types import (
    PipelineStatus,
    PipelineRunRequest,
    PipelineRunResponse,
    PipelineSaveRequest,
    PipelineStatusResponse,
    TemplateCreateRequest,
    TemplateListItem,
    _model_from_fields,
)
from ai_document_plugin_service.service import pipeline_service as pipeline

router = fastapi.APIRouter()

@router.get('/health')
def health_check() -> dict[str, str]:
    return {'status': 'healthy'}


@router.get('/templates')
def list_templates() -> list[TemplateListItem]:
    config = load_config()
    database = PostgresDB(config.database)
    return [_model_from_fields(TemplateListItem, **item) for item in database.list_templates()]


@router.post('/templates', status_code=201)
def create_template(payload: TemplateCreateRequest) -> TemplateListItem:
    trimmed_title = payload.title.strip()
    if not trimmed_title:
        raise fastapi.HTTPException(status_code=400, detail='Template title is required')

    sections = payload.content.get('sections')
    if not isinstance(sections, list):
        raise fastapi.HTTPException(
            status_code=400,
            detail='Template JSON must contain a top-level "sections" array.',
        )

    config = load_config()
    database = PostgresDB(config.database)
    template_uuid = str(uuid4())

    try:
        database.create_template(
            uuid=template_uuid,
            title=trimmed_title,
            content=payload.content,
        )
    except ValueError as error:
        raise fastapi.HTTPException(status_code=409, detail=str(error)) from error

    return _model_from_fields(
        TemplateListItem,
        uuid=template_uuid,
        title=trimmed_title,
    )


@router.post('/pipelines/run')
def start_pipeline(
    payload: PipelineRunRequest,
    background_tasks: fastapi.BackgroundTasks,
) -> PipelineRunResponse:
    config = load_config()
    database = PostgresDB(config.database)
    template = database.get_template(payload.template_uuid)

    if template is None:
        raise fastapi.HTTPException(status_code=404, detail='Template not found')

    try:
        user_uuid, tenant_uuid = extract_identity_from_token(payload.token)
    except ValueError as error:
        raise fastapi.HTTPException(status_code=400, detail=str(error)) from error

    run_id = str(uuid4())
    pipeline.set_pipeline_status(
        run_id,
        pipeline.build_pipeline_status(
            run_id=run_id,
            status=PipelineStatus.RUNNING,
            questionnaire_uuid=payload.questionnaire_uuid,
            user_uuid=user_uuid,
            tenant_uuid=tenant_uuid,
            template_uuid=payload.template_uuid,
            template_title=template['title'],
        ),
    )
    background_tasks.add_task(
        pipeline.run_pipeline_job,
        run_id,
        payload.questionnaire_uuid,
        payload.template_uuid,
        template['title'],
        user_uuid,
        tenant_uuid,
        payload.token,
        payload.api_url,
        LLMConfigOverride(
            model=payload.llm_model,
            api_key=payload.llm_api_key,
            api_url=payload.llm_api_url,
            parallel_workers=payload.llm_max_workers,
        ),
    )
    return _model_from_fields(
        PipelineRunResponse,
        status=PipelineStatus.ACCEPTED,
        run_id=run_id,
        questionnaire_uuid=payload.questionnaire_uuid,
        user_uuid=user_uuid,
        tenant_uuid=tenant_uuid,
        template_uuid=payload.template_uuid,
        template_title=template['title'],
    )


@router.get('/pipelines/status/{run_id}')
def get_pipeline_status(
    run_id: str,
) -> PipelineStatusResponse:
    status = pipeline.get_pipeline_status(run_id)
    if status is None:
        raise fastapi.HTTPException(status_code=404, detail='Pipeline run not found')
    return status


@router.post('/pipelines/status/{run_id}/save')
def save_pipeline_result(
    run_id: str,
    payload: PipelineSaveRequest,
) -> PipelineStatusResponse:
    status = pipeline.get_pipeline_status(run_id)
    if status is None:
        raise fastapi.HTTPException(status_code=404, detail='Pipeline run not found')

    if status.knowledge_model_uuid is None:
        raise fastapi.HTTPException(status_code=500, detail='Missing knowledge_model_uuid')

    config = load_config()
    database = PostgresDB(config.database)

    database.update_result(
        template_uuid=status.template_uuid,
        knowledge_model_uuid=status.knowledge_model_uuid,
        user_uuid=status.user_uuid,
        tenant_uuid=status.tenant_uuid,
        markdown=payload.result_markdown,
    )

    updated_status = pipeline.build_pipeline_status(
        run_id=status.run_id,
        status=status.status,
        questionnaire_uuid=status.questionnaire_uuid,
        knowledge_model_uuid=status.knowledge_model_uuid,
        user_uuid=status.user_uuid,
        tenant_uuid=status.tenant_uuid,
        template_uuid=status.template_uuid,
        template_title=status.template_title,
        error=status.error,
        result_format='markdown',
        result_markdown=payload.result_markdown,
    )
    pipeline.set_pipeline_status(run_id, updated_status)
    return updated_status
