import logging
import threading
from datetime import UTC, datetime

from haystack.core.errors import PipelineRuntimeError
from openai import AuthenticationError

from ai_document_plugin_service.ai.common.config import (
    Config,
    LLMConfigOverride,
    apply_llm_override,
)
from ai_document_plugin_service.ai.generation.llm import OpenAIGenerationLLM
from ai_document_plugin_service.ai.persistence.assignment_saver_component import DBSaver
from ai_document_plugin_service.ai.persistence.database import PostgresDB
from ai_document_plugin_service.api.types import (
    ErrorType,
    PipelineErrorResponse,
    PipelineStatus,
    PipelineStatusResponse,
    _model_from_fields,
)
from ai_document_plugin_service.run_pipeline import build_pipeline, run_pipeline
from ai_document_plugin_service.service.pipeline_queue_manager import pipeline_queue_manager

logger = logging.getLogger(__name__)

_pipeline_runs: dict[str, PipelineStatusResponse] = {}
_pipeline_runs_lock = threading.Lock()

AUTHORIZATION_ERROR_MESSAGE = 'Authorization error, invalid or expired token.'
SERVER_ERROR_MESSAGE = 'The action could not be completed. Please try again later.'
TEMPLATE_NOT_FOUND_MESSAGE = 'Template not found.'


def set_pipeline_status(run_id: str, status: PipelineStatusResponse) -> None:
    with _pipeline_runs_lock:
        _pipeline_runs[run_id] = status


def get_pipeline_status(run_id: str) -> PipelineStatusResponse | None:
    with _pipeline_runs_lock:
        status = _pipeline_runs.get(run_id)

    if status is None or status.status != PipelineStatus.QUEUED:
        return status

    progress_message = pipeline_queue_manager.progress_message(run_id)
    if progress_message is None:
        return status

    return status.model_copy(update={'progress_message': progress_message})


def build_pipeline_status(
    *,
    run_id: str,
    status: PipelineStatus,
    questionnaire_uuid: str,
    user_uuid: str,
    tenant_uuid: str,
    template_uuid: str,
    template_title: str,
    knowledge_model_uuid: str | None = None,
    error: PipelineErrorResponse | None = None,
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


def enqueue_pipeline_job(
    run_id: str,
    questionnaire_uuid: str,
    template_uuid: str,
    template_title: str,
    user_uuid: str,
    tenant_uuid: str,
    token: str,
    api_url: str | None,
    llm_override: LLMConfigOverride | None,
    config: Config,
) -> None:
    """Queue a pipeline job; concurrency is limited by ``pipeline_queue_manager``."""
    set_pipeline_status(
        run_id,
        build_pipeline_status(
            run_id=run_id,
            status=PipelineStatus.QUEUED,
            questionnaire_uuid=questionnaire_uuid,
            user_uuid=user_uuid,
            tenant_uuid=tenant_uuid,
            template_uuid=template_uuid,
            template_title=template_title,
        ),
    )

    pipeline_queue_manager.enqueue(
        run_id,
        lambda: _run_pipeline_job(
            run_id,
            questionnaire_uuid,
            template_uuid,
            template_title,
            user_uuid,
            tenant_uuid,
            token,
            api_url,
            llm_override,
            config,
        ),
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
    with _pipeline_runs_lock:
        current = _pipeline_runs.get(run_id)
    if current is None:
        return

    set_pipeline_status(
        run_id,
        build_pipeline_status(
            run_id=run_id,
            status=PipelineStatus.RUNNING,
            questionnaire_uuid=questionnaire_uuid,
            knowledge_model_uuid=current.knowledge_model_uuid,
            user_uuid=user_uuid,
            tenant_uuid=tenant_uuid,
            template_uuid=template_uuid,
            template_title=template_title,
            progress_message=progress_message,
        ),
    )


def _run_pipeline_job(
    run_id: str,
    questionnaire_uuid: str,
    template_uuid: str,
    template_title: str,
    user_uuid: str,
    tenant_uuid: str,
    token: str,
    api_url: str | None,
    llm_override: LLMConfigOverride | None,
    config: Config,
) -> None:
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
                status=PipelineStatus.FAILED,
                questionnaire_uuid=questionnaire_uuid,
                template_uuid=template_uuid,
                template_title=template_title,
                user_uuid=user_uuid,
                tenant_uuid=tenant_uuid,
                error=PipelineErrorResponse(
                    type=ErrorType.TEMPLATE_NOT_FOUND,
                    message=TEMPLATE_NOT_FOUND_MESSAGE,
                ),
            ),
        )
        return

    set_pipeline_status(
        run_id,
        build_pipeline_status(
            run_id=run_id,
            status=PipelineStatus.RUNNING,
            questionnaire_uuid=questionnaire_uuid,
            user_uuid=user_uuid,
            tenant_uuid=tenant_uuid,
            template_uuid=template_uuid,
            template_title=template_title,
            progress_message='Starting pipeline...',
        ),
    )

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
            config=config,
        )

        set_pipeline_status(
            run_id,
            build_pipeline_status(
                run_id=run_id,
                status=PipelineStatus.SUCCEEDED,
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
    except PipelineRuntimeError as error:
        if isinstance(error.__cause__, AuthenticationError):
            set_pipeline_status(
                run_id,
                build_pipeline_status(
                    run_id=run_id,
                    status=PipelineStatus.FAILED,
                    questionnaire_uuid=questionnaire_uuid,
                    template_uuid=template_uuid,
                    template_title=template_title,
                    user_uuid=user_uuid,
                    tenant_uuid=tenant_uuid,
                    error=PipelineErrorResponse(
                        type=ErrorType.AUTHENTICATION_FAILED,
                        message=AUTHORIZATION_ERROR_MESSAGE,
                    ),
                ),
            )
        else:
            set_pipeline_status(
                run_id,
                build_pipeline_status(
                    run_id=run_id,
                    status=PipelineStatus.FAILED,
                    questionnaire_uuid=questionnaire_uuid,
                    template_uuid=template_uuid,
                    template_title=template_title,
                    user_uuid=user_uuid,
                    tenant_uuid=tenant_uuid,
                    error=PipelineErrorResponse(
                        type=ErrorType.SERVER_ERROR,
                        message=SERVER_ERROR_MESSAGE,
                    ),
                ),
            )

        logger.exception('Pipeline run failed')
    except AuthenticationError:
        set_pipeline_status(
            run_id,
            build_pipeline_status(
                run_id=run_id,
                status=PipelineStatus.FAILED,
                questionnaire_uuid=questionnaire_uuid,
                template_uuid=template_uuid,
                template_title=template_title,
                user_uuid=user_uuid,
                tenant_uuid=tenant_uuid,
                error=PipelineErrorResponse(
                    type=ErrorType.SERVER_ERROR,
                    message=SERVER_ERROR_MESSAGE,
                ),
            ),
        )
        logger.exception('Pipeline run failed')
