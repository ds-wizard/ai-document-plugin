import logging
import threading
from datetime import UTC, datetime

from ai_document_plugin_service.ai.common.config import (
    LLMConfigOverride,
    apply_llm_override,
    load_config,
)
from ai_document_plugin_service.ai.generation.llm import OpenAIGenerationLLM
from ai_document_plugin_service.ai.persistence.assignment_saver_component import DBSaver
from ai_document_plugin_service.ai.persistence.database import PostgresDB
from ai_document_plugin_service.api.types import PipelineStatusResponse, _model_from_fields
from ai_document_plugin_service.run_pipeline import build_pipeline, run_pipeline

logger = logging.getLogger(__name__)

_pipeline_runs: dict[str, PipelineStatusResponse] = {}
_pipeline_runs_lock = threading.Lock()


def set_pipeline_status(run_id: str, status: PipelineStatusResponse) -> None:
    with _pipeline_runs_lock:
        _pipeline_runs[run_id] = status


def get_pipeline_status(run_id: str) -> PipelineStatusResponse | None:
    with _pipeline_runs_lock:
        return _pipeline_runs.get(run_id)


def build_pipeline_status(
    *,
    run_id: str,
    status: str,
    questionnaire_uuid: str,
    user_uuid: str,
    tenant_uuid: str,
    template_uuid: str,
    template_title: str,
    knowledge_model_uuid: str | None = None,
    error: str | None = None,
    result_format: str | None = None,
    result_markdown: str | None = None,
    progress_message: str | None = None,
) -> PipelineStatusResponse:
    return _model_from_fields(
        PipelineStatusResponse,
        run_id=run_id,
        status=status,
        questionnaire_uuid=questionnaire_uuid,
        knowledge_model_uuid=knowledge_model_uuid,
        user_uuid=user_uuid,
        tenant_uuid=tenant_uuid,
        template_uuid=template_uuid,
        template_title=template_title,
        error=error,
        result_format=result_format,
        result_markdown=result_markdown,
        progress_message=progress_message,
        updated_at=datetime.now(tz=UTC).isoformat(),
    )


def _update_running_progress(
    run_id: str,
    *,
    questionnaire_uuid: str,
    user_uuid: str,
    tenant_uuid: str,
    template_uuid: str,
    template_title: str,
    progress_message: str,
) -> None:
    current = get_pipeline_status(run_id)
    if current is None:
        return

    set_pipeline_status(
        run_id,
        build_pipeline_status(
            run_id=run_id,
            status='running',
            questionnaire_uuid=questionnaire_uuid,
            knowledge_model_uuid=current.knowledge_model_uuid,
            user_uuid=user_uuid,
            tenant_uuid=tenant_uuid,
            template_uuid=template_uuid,
            template_title=template_title,
            progress_message=progress_message,
        ),
    )


def run_pipeline_job(
    run_id: str,
    questionnaire_uuid: str,
    template_uuid: str,
    template_title: str,
    user_uuid: str,
    tenant_uuid: str,
    token: str,
    api_url: str | None,
    llm_override: LLMConfigOverride | None,
) -> None:
    config = load_config()
    resolved_config = apply_llm_override(config, llm_override)
    database = PostgresDB(config.database)
    saver = DBSaver(database)
    generation_llm = OpenAIGenerationLLM(config=resolved_config)
    template = database.get_template(template_uuid)
    if template is None:
        set_pipeline_status(
            run_id,
            build_pipeline_status(
                run_id=run_id,
                status='failed',
                questionnaire_uuid=questionnaire_uuid,
                template_uuid=template_uuid,
                template_title=template_title,
                user_uuid=user_uuid,
                tenant_uuid=tenant_uuid,
                error='Template not found.',
            ),
        )
        return

    def on_progress(message: str) -> None:
        _update_running_progress(
            run_id,
            questionnaire_uuid=questionnaire_uuid,
            user_uuid=user_uuid,
            tenant_uuid=tenant_uuid,
            template_uuid=template_uuid,
            template_title=template_title,
            progress_message=message,
        )

    try:
        pipeline = build_pipeline(database=database, saver=saver, generation_llm=generation_llm)
        knowledge_model_uuid, result = run_pipeline(
            questionnaire_uuid=questionnaire_uuid,
            token=token,
            dsw_api_url=api_url,
            template_uuid=template_uuid,
            template_title=template['title'],
            template_data=template['content'],
            user_uuid=user_uuid,
            tenant_uuid=tenant_uuid,
            pipeline=pipeline,
            llm_override=llm_override,
            database=database,
            on_progress=on_progress,
        )

        set_pipeline_status(
            run_id,
            build_pipeline_status(
                run_id=run_id,
                status='succeeded',
                questionnaire_uuid=questionnaire_uuid,
                knowledge_model_uuid=knowledge_model_uuid,
                user_uuid=user_uuid,
                tenant_uuid=tenant_uuid,
                template_uuid=template_uuid,
                template_title=template_title,
                result_format='markdown',
                result_markdown=result,
            ),
        )
    except Exception as error:
        set_pipeline_status(
            run_id,
            build_pipeline_status(
                run_id=run_id,
                status='failed',
                questionnaire_uuid=questionnaire_uuid,
                template_uuid=template_uuid,
                template_title=template_title,
                user_uuid=user_uuid,
                tenant_uuid=tenant_uuid,
                error=str(error),
            ),
        )
        logger.exception('Pipeline run failed')
