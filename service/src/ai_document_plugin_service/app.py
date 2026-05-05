import fastapi
import fastapi.middleware.cors
import fastapi.responses
import pathlib
import threading
from datetime import UTC, datetime
from uuid import uuid4
from pydantic import BaseModel

from ai_document_plugin_service.ai.common.config import LLMConfigOverride, load_config
from ai_document_plugin_service.ai.persistence.database import PostgresDB
from ai_document_plugin_service.run_pipeline import build_pipeline, run_pipeline


class TemplateListItem(BaseModel):
    uuid: str
    title: str


class TemplateCreateRequest(BaseModel):
    title: str
    content: dict


class PipelineRunRequest(BaseModel):
    questionnaireUuid: str
    templateUuid: str
    token: str
    apiUrl: str | None = None
    llmModel: str | None = None
    llmApiKey: str | None = None
    llmApiUrl: str | None = None


class PipelineRunResponse(BaseModel):
    status: str
    runId: str
    questionnaireUuid: str
    templateUuid: str
    templateTitle: str


class PipelineSaveRequest(BaseModel):
    resultMarkdown: str


class PipelineStatusResponse(BaseModel):
    runId: str
    status: str
    questionnaireUuid: str
    templateUuid: str
    templateTitle: str
    error: str | None = None
    resultFormat: str | None = None
    resultMarkdown: str | None = None
    updatedAt: str


_pipeline_runs: dict[str, PipelineStatusResponse] = {}
_pipeline_runs_lock = threading.Lock()


def _set_pipeline_status(run_id: str, status: PipelineStatusResponse) -> None:
    with _pipeline_runs_lock:
        _pipeline_runs[run_id] = status


def _get_pipeline_status(run_id: str) -> PipelineStatusResponse | None:
    with _pipeline_runs_lock:
        return _pipeline_runs.get(run_id)


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
            PipelineStatusResponse(
                runId=run_id,
                status='failed',
                questionnaireUuid=questionnaire_uuid,
                templateUuid=template_uuid,
                templateTitle=template_title,
                error='Template not found.',
                resultFormat=None,
                resultMarkdown=None,
                updatedAt=datetime.now(tz=UTC).isoformat(),
            ),
        )
        return

    try:
        pipeline = build_pipeline()
        run_pipeline(
            questionnaire_uuid=questionnaire_uuid,
            token=token,
            dsw_api_url=api_url,
            template_uuid=template_uuid,
            template_title=template['title'],
            template_data=template['content'],
            pipeline=pipeline,
            llm_override=llm_override,
        )
        result_markdown = pathlib.Path(config.files.output_markdown).read_text(encoding='utf-8')
        _set_pipeline_status(
            run_id,
            PipelineStatusResponse(
                runId=run_id,
                status='succeeded',
                questionnaireUuid=questionnaire_uuid,
                templateUuid=template_uuid,
                templateTitle=template_title,
                error=None,
                resultFormat='markdown',
                resultMarkdown=result_markdown,
                updatedAt=datetime.now(tz=UTC).isoformat(),
            ),
        )
    except Exception as error:
        _set_pipeline_status(
            run_id,
            PipelineStatusResponse(
                runId=run_id,
                status='failed',
                questionnaireUuid=questionnaire_uuid,
                templateUuid=template_uuid,
                templateTitle=template_title,
                error=str(error),
                resultFormat=None,
                resultMarkdown=None,
                updatedAt=datetime.now(tz=UTC).isoformat(),
            ),
        )


def create_app() -> fastapi.FastAPI:
    app = fastapi.FastAPI(
        title='Plugin Service',
        version='1.0.0',
    )

    app.add_middleware(
        middleware_class=fastapi.middleware.cors.CORSMiddleware,
        allow_origins=['*'],
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )

    @app.get('/health')
    async def health_check() -> fastapi.responses.JSONResponse:
        return fastapi.responses.JSONResponse(content={'status': 'healthy'})

    @app.get('/templates', response_model=list[TemplateListItem])
    async def list_templates() -> list[TemplateListItem]:
        config = load_config()
        database = PostgresDB(config.database)
        return [TemplateListItem.model_validate(item) for item in database.list_templates()]

    @app.post('/templates', response_model=TemplateListItem, status_code=201)
    async def create_template(payload: TemplateCreateRequest) -> TemplateListItem:
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

        return TemplateListItem(
            uuid=template_uuid,
            title=trimmed_title,
        )

    @app.post('/pipelines/run')
    async def start_pipeline(
        payload: PipelineRunRequest,
        background_tasks: fastapi.BackgroundTasks,
    ) -> PipelineRunResponse:
        config = load_config()
        database = PostgresDB(config.database)
        template = database.get_template(payload.templateUuid)

        if template is None:
            raise fastapi.HTTPException(status_code=404, detail='Template not found')

        run_id = str(uuid4())
        _set_pipeline_status(
            run_id,
            PipelineStatusResponse(
                runId=run_id,
                status='running',
                questionnaireUuid=payload.questionnaireUuid,
                templateUuid=payload.templateUuid,
                templateTitle=template['title'],
                error=None,
                resultFormat=None,
                resultMarkdown=None,
                updatedAt=datetime.now(tz=UTC).isoformat(),
            ),
        )
        background_tasks.add_task(
            _run_pipeline_job,
            run_id,
            payload.questionnaireUuid,
            payload.templateUuid,
            template['title'],
            payload.token,
            payload.apiUrl,
            LLMConfigOverride(
                model=payload.llmModel,
                api_key=payload.llmApiKey,
                api_url=payload.llmApiUrl,
            ),
        )
        return PipelineRunResponse(
            status='accepted',
            runId=run_id,
            questionnaireUuid=payload.questionnaireUuid,
            templateUuid=payload.templateUuid,
            templateTitle=template['title'],
        )

    @app.get('/pipelines/status/{run_id}', response_model=PipelineStatusResponse)
    async def get_pipeline_status(run_id: str) -> PipelineStatusResponse:
        status = _get_pipeline_status(run_id)
        if status is None:
            raise fastapi.HTTPException(status_code=404, detail='Pipeline run not found')
        return status

    @app.post('/pipelines/status/{run_id}/save', response_model=PipelineStatusResponse)
    async def save_pipeline_result(
        run_id: str,
        payload: PipelineSaveRequest,
    ) -> PipelineStatusResponse:
        status = _get_pipeline_status(run_id)
        if status is None:
            raise fastapi.HTTPException(status_code=404, detail='Pipeline run not found')

        updated_status = PipelineStatusResponse(
            runId=status.runId,
            status=status.status,
            questionnaireUuid=status.questionnaireUuid,
            templateUuid=status.templateUuid,
            templateTitle=status.templateTitle,
            error=status.error,
            resultFormat='markdown',
            resultMarkdown=payload.resultMarkdown,
            updatedAt=datetime.now(tz=UTC).isoformat(),
        )
        _set_pipeline_status(run_id, updated_status)

        config = load_config()
        pathlib.Path(config.files.output_markdown).write_text(payload.resultMarkdown, encoding='utf-8')

        return updated_status

    return app
