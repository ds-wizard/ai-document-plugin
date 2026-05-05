import fastapi
import fastapi.middleware.cors
import fastapi.responses
import threading
from datetime import UTC, datetime
from uuid import uuid4
from pydantic import BaseModel

from ai_document_plugin_service.ai.common.config import load_config
from ai_document_plugin_service.ai.persistence.database import PostgresDB
from ai_document_plugin_service.run_pipeline import build_pipeline, run_pipeline


class TemplateListItem(BaseModel):
    uuid: str
    title: str


class PipelineRunRequest(BaseModel):
    questionnaireUuid: str
    templateUuid: str
    token: str
    apiUrl: str | None = None


class PipelineRunResponse(BaseModel):
    status: str
    runId: str
    questionnaireUuid: str
    templateUuid: str
    templateTitle: str


class PipelineStatusResponse(BaseModel):
    runId: str
    status: str
    questionnaireUuid: str
    templateUuid: str
    templateTitle: str
    error: str | None = None
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
        )
        _set_pipeline_status(
            run_id,
            PipelineStatusResponse(
                runId=run_id,
                status='succeeded',
                questionnaireUuid=questionnaire_uuid,
                templateUuid=template_uuid,
                templateTitle=template_title,
                error=None,
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

    return app
