import fastapi
import fastapi.middleware.cors
import fastapi.responses
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


def _run_pipeline_job(questionnaire_uuid: str, template_uuid: str) -> None:
    config = load_config()
    database = PostgresDB(config.database)
    template = database.get_template(template_uuid)
    if template is None:
        return

    pipeline = build_pipeline()
    run_pipeline(
        questionnaire_uuid=questionnaire_uuid,
        token=config.token,
        template_uuid=template_uuid,
        template_title=template['title'],
        template_data=template['content'],
        pipeline=pipeline,
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
    ) -> fastapi.responses.JSONResponse:
        config = load_config()
        database = PostgresDB(config.database)
        template = database.get_template(payload.templateUuid)

        if template is None:
            raise fastapi.HTTPException(status_code=404, detail='Template not found')

        background_tasks.add_task(
            _run_pipeline_job,
            payload.questionnaireUuid,
            payload.templateUuid,
        )
        return fastapi.responses.JSONResponse(
            status_code=202,
            content={
                'status': 'accepted',
                'questionnaireUuid': payload.questionnaireUuid,
                'templateUuid': payload.templateUuid,
                'templateTitle': template['title'],
            },
        )

    return app
