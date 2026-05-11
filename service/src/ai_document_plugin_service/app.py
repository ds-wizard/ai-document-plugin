import threading
from datetime import UTC, datetime
from uuid import uuid4

import fastapi
import fastapi.middleware.cors
import fastapi.responses

from ai_document_plugin_service.ai.common.config import LLMConfigOverride, load_config
from ai_document_plugin_service.ai.persistence.database import PostgresDB
from ai_document_plugin_service.api.types import ApiModel, PipelineStatusResponse, TemplateListItem, \
    TemplateCreateRequest, PipelineRunRequest, PipelineRunResponse, PipelineSaveRequest, _model_from_fields
from ai_document_plugin_service.run_pipeline import build_pipeline, run_pipeline

_pipeline_runs: dict[str, PipelineStatusResponse] = {}
_pipeline_runs_lock = threading.Lock()


def _set_pipeline_status(run_id: str, status: PipelineStatusResponse) -> None:
    with _pipeline_runs_lock:
        _pipeline_runs[run_id] = status


def _get_pipeline_status(run_id: str) -> PipelineStatusResponse | None:
    with _pipeline_runs_lock:
        return _pipeline_runs.get(run_id)


def _build_pipeline_status(
    *,
    run_id: str,
    status: str,
    questionnaire_uuid: str,
    template_uuid: str,
    template_title: str,
    knowledge_model_uuid: str | None = None,
    error: str | None = None,
    result_format: str | None = None,
    result_markdown: str | None = None,
) -> PipelineStatusResponse:
    return _model_from_fields(
        PipelineStatusResponse,
        run_id=run_id,
        status=status,
        questionnaire_uuid=questionnaire_uuid,
        knowledge_model_uuid=knowledge_model_uuid,
        template_uuid=template_uuid,
        template_title=template_title,
        error=error,
        result_format=result_format,
        result_markdown=result_markdown,
        updated_at=datetime.now(tz=UTC).isoformat(),
    )


def _run_pipeline_job(
    run_id: str,
    questionnaire_uuid: str,
    template_uuid: str,
    template_title: str,
    token: str,
    api_url: str | None,
    llm_override: LLMConfigOverride | None,
) -> None:
    config = load_config()
    database = PostgresDB(config.database)
    template = database.get_template(template_uuid)
    if template is None:
        _set_pipeline_status(
            run_id,
            _build_pipeline_status(
                run_id=run_id,
                status='failed',
                questionnaire_uuid=questionnaire_uuid,
                template_uuid=template_uuid,
                template_title=template_title,
                error='Template not found.',
            ),
        )
        return

    try:
        pipeline = build_pipeline()
        knowledge_model_uuid, result = run_pipeline(
            questionnaire_uuid=questionnaire_uuid,
            token=token,
            dsw_api_url=api_url,
            template_uuid=template_uuid,
            template_title=template['title'],
            template_data=template['content'],
            pipeline=pipeline,
            llm_override=llm_override,
        )

        _set_pipeline_status(
            run_id,
            _build_pipeline_status(
                run_id=run_id,
                status='succeeded',
                questionnaire_uuid=questionnaire_uuid,
                knowledge_model_uuid=knowledge_model_uuid,
                template_uuid=template_uuid,
                template_title=template_title,
                result_format='markdown',
                result_markdown=result,
            ),
        )
    except (KeyError, RuntimeError, TypeError, ValueError) as error:
        _set_pipeline_status(
            run_id,
            _build_pipeline_status(
                run_id=run_id,
                status='failed',
                questionnaire_uuid=questionnaire_uuid,
                template_uuid=template_uuid,
                template_title=template_title,
                error=str(error),
            ),
        )


def health_check() -> fastapi.responses.JSONResponse:
    return fastapi.responses.JSONResponse(content={'status': 'healthy'})


def list_templates() -> list[TemplateListItem]:
    config = load_config()
    database = PostgresDB(config.database)
    return [_model_from_fields(TemplateListItem, **item) for item in database.list_templates()]


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


def start_pipeline(
    payload: PipelineRunRequest,
    background_tasks: fastapi.BackgroundTasks,
) -> PipelineRunResponse:
    config = load_config()
    database = PostgresDB(config.database)
    template = database.get_template(payload.template_uuid)

    if template is None:
        raise fastapi.HTTPException(status_code=404, detail='Template not found')

    run_id = str(uuid4())
    _set_pipeline_status(
        run_id,
        _build_pipeline_status(
            run_id=run_id,
            status='running',
            questionnaire_uuid=payload.questionnaire_uuid,
            template_uuid=payload.template_uuid,
            template_title=template['title'],
        ),
    )
    background_tasks.add_task(
        _run_pipeline_job,
        run_id,
        payload.questionnaire_uuid,
        payload.template_uuid,
        template['title'],
        payload.token,
        payload.api_url,
        LLMConfigOverride(
            model=payload.llm_model,
            api_key=payload.llm_api_key,
            api_url=payload.llm_api_url,
        ),
    )
    return _model_from_fields(
        PipelineRunResponse,
        status='accepted',
        run_id=run_id,
        questionnaire_uuid=payload.questionnaire_uuid,
        template_uuid=payload.template_uuid,
        template_title=template['title'],
    )


def get_pipeline_status(run_id: str) -> PipelineStatusResponse:
    status = _get_pipeline_status(run_id)
    if status is None:
        raise fastapi.HTTPException(status_code=404, detail='Pipeline run not found')
    return status


def save_pipeline_result(
    run_id: str,
    payload: PipelineSaveRequest,
) -> PipelineStatusResponse:
    status = _get_pipeline_status(run_id)
    if status is None:
        raise fastapi.HTTPException(status_code=404, detail='Pipeline run not found')

    if status.knowledge_model_uuid is None:
        raise fastapi.HTTPException(status_code=500, detail='Missing knowledge_model_uuid')

    config = load_config()
    database = PostgresDB(config.database)

    database.update_result(
        template_uuid=status.template_uuid,
        knowledge_model_uuid=status.knowledge_model_uuid,
        markdown=payload.result_markdown,
    )

    updated_status = _build_pipeline_status(
        run_id=status.run_id,
        status=status.status,
        questionnaire_uuid=status.questionnaire_uuid,
        knowledge_model_uuid=status.knowledge_model_uuid,
        template_uuid=status.template_uuid,
        template_title=status.template_title,
        error=status.error,
        result_format='markdown',
        result_markdown=payload.result_markdown,
    )
    _set_pipeline_status(run_id, updated_status)
    return updated_status


def create_app() -> fastapi.FastAPI:
    app = fastapi.FastAPI(title='Plugin Service', version='1.0.0')
    app.add_middleware(
        middleware_class=fastapi.middleware.cors.CORSMiddleware,
        allow_origins=['*'],
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )
    app.add_api_route('/health', health_check, methods=['GET'])
    app.add_api_route('/templates', list_templates, methods=['GET'])
    app.add_api_route('/templates', create_template, methods=['POST'], status_code=201)
    app.add_api_route('/pipelines/run', start_pipeline, methods=['POST'])
    app.add_api_route('/pipelines/status/{run_id}', get_pipeline_status, methods=['GET'])
    app.add_api_route('/pipelines/status/{run_id}/save', save_pipeline_result, methods=['POST'])
    return app
