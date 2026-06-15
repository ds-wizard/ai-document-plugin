from typing import Annotated
from uuid import uuid4

import fastapi

from ai_document_plugin_service.ai.common.config import Config, LLMConfigOverride
from ai_document_plugin_service.ai.persistence.database import PostgresDB
from ai_document_plugin_service.api.auth import AuthenticatedUser, verify_authenticated
from ai_document_plugin_service.api.jwt import extract_identity_from_token
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
from ai_document_plugin_service.service import pipeline_service as pipeline

public_router = fastapi.APIRouter()
protected_router = fastapi.APIRouter(dependencies=[fastapi.Depends(verify_authenticated)])


def _load_app_config(request: fastapi.Request) -> Config:
    return request.app.state.config


@public_router.get('/health')
def health_check() -> dict[str, str]:
    return {'status': 'healthy'}


@protected_router.get('/templates')
def list_templates(request: fastapi.Request) -> list[TemplateListItem]:
    config = _load_app_config(request)
    database = PostgresDB(config.database)
    return [_model_from_fields(TemplateListItem, **item) for item in database.list_templates()]


@protected_router.get('/templates/{template_uuid}')
def get_template(template_uuid: str, request: fastapi.Request) -> TemplateDetail:
    config = _load_app_config(request)
    database = PostgresDB(config.database)
    template = database.get_template(template_uuid)

    if template is None:
        raise fastapi.HTTPException(status_code=404, detail='Template not found')

    return _model_from_fields(
        TemplateDetail,
        uuid=template['uuid'],
        title=template['title'],
        content=template['content'],
    )


@protected_router.post('/templates', status_code=201)
def create_template(payload: TemplateCreateRequest, request: fastapi.Request) -> TemplateDetail:
    trimmed_title = payload.title.strip()
    if not trimmed_title:
        raise fastapi.HTTPException(status_code=400, detail='Template title is required')

    sections = payload.content.get('sections')
    if not isinstance(sections, list):
        raise fastapi.HTTPException(
            status_code=400,
            detail='Template JSON must contain a top-level "sections" array.',
        )

    config = _load_app_config(request)
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
        TemplateDetail,
        uuid=template_uuid,
        title=trimmed_title,
        content=payload.content,
    )


@protected_router.post('/pipelines/run')
def start_pipeline(
    payload: PipelineRunRequest,
    request: fastapi.Request,
    auth: Annotated[AuthenticatedUser, fastapi.Depends(verify_authenticated)],
) -> PipelineRunResponse:
    config = _load_app_config(request)
    database = PostgresDB(config.database)
    template = database.get_template(payload.template_uuid)

    if template is None:
        raise fastapi.HTTPException(status_code=404, detail='Template not found')

    try:
        user_uuid, tenant_uuid = extract_identity_from_token(auth.token)
    except ValueError as error:
        raise fastapi.HTTPException(status_code=400, detail=str(error)) from error

    run_id = str(uuid4())
    pipeline.enqueue_pipeline_job(
        run_id,
        payload.questionnaire_uuid,
        payload.template_uuid,
        template['title'],
        user_uuid,
        tenant_uuid,
        auth.token,
        auth.api_url,
        LLMConfigOverride(
            model=payload.llm_model,
            api_key=payload.llm_api_key,
            api_url=payload.llm_api_url,
            parallel_workers=payload.llm_max_workers,
        ),
        config,
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


@protected_router.get('/pipelines/status/{run_id}')
def get_pipeline_status(
    run_id: str,
) -> PipelineStatusResponse:
    status = pipeline.get_pipeline_status(run_id)
    if status is None:
        raise fastapi.HTTPException(status_code=404, detail='Pipeline run not found')
    return status


@protected_router.post('/pipelines/status/{run_id}/save')
def save_pipeline_result(
    run_id: str,
    payload: PipelineSaveRequest,
    request: fastapi.Request,
) -> PipelineStatusResponse:
    status = pipeline.get_pipeline_status(run_id)
    if status is None:
        raise fastapi.HTTPException(status_code=404, detail='Pipeline run not found')

    if status.knowledge_model_uuid is None:
        raise fastapi.HTTPException(status_code=500, detail='Missing knowledge_model_uuid')

    config = _load_app_config(request)
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
