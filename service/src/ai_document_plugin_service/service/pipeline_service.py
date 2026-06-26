import logging
import threading
from datetime import UTC, datetime
from typing import Any

from openai import AuthenticationError

from ai_document_plugin_service.ai.common.config import (
    Config,
    LLMConfig,
)
from ai_document_plugin_service.ai.common.llm_client import LLMClient
from ai_document_plugin_service.ai.knowledgemodel.dsw_client import DSWClient
from ai_document_plugin_service.ai.persistence.assignment_saver_component import DBSaver
from ai_document_plugin_service.ai.persistence.database import PostgresDB
from ai_document_plugin_service.ai.run_pipeline import build_pipeline, run_pipeline
from ai_document_plugin_service.api.types import (
    ErrorType,
    PipelineErrorResponse,
    PipelineStatus,
    PipelineStatusResponse,
    _model_from_fields,
)
from ai_document_plugin_service.service.pipeline_queue_manager import pipeline_queue_manager

logger = logging.getLogger(__name__)

_pipeline_runs: dict[str, PipelineStatusResponse] = {}
_pipeline_runs_lock = threading.Lock()

AUTHORIZATION_ERROR_MESSAGE = 'Authorization error, invalid or expired token.'
SERVER_ERROR_MESSAGE = 'The action could not be completed. Please try again later.'
TEMPLATE_NOT_FOUND_MESSAGE = 'Template not found.'


def _pipeline_error_from_exception(error: Exception) -> PipelineErrorResponse:
    if isinstance(error, AuthenticationError) or isinstance(
        error.__cause__, AuthenticationError
    ):
        return PipelineErrorResponse(
            type=ErrorType.AUTHENTICATION_FAILED,
            message=AUTHORIZATION_ERROR_MESSAGE,
        )

    return PipelineErrorResponse(
        type=ErrorType.SERVER_ERROR,
        message=SERVER_ERROR_MESSAGE,
    )


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
    api_url: str,
    llm_config: LLMConfig,
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
            llm_config,
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


async def _run_pipeline_job(
    run_id: str,
    questionnaire_uuid: str,
    template_uuid: str,
    template_title: str,
    user_uuid: str,
    tenant_uuid: str,
    token: str,
    dsw_api_url: str,
    llm_config: LLMConfig,
    config: Config,
) -> None:
    database = PostgresDB(config.database)
    saver = DBSaver(database)
    llm_client = LLMClient(llm_config.model, llm_config.api_key, llm_config.api_url, llm_config.parallel_workers)
    try:
        template = await database.get_template(template_uuid)
        if template is None:
            _fail_template_not_found(questionnaire_uuid, run_id, template_title, template_uuid, tenant_uuid,
                                     user_uuid)
            return

        await _start_pipeline(config, database, dsw_api_url, llm_client, questionnaire_uuid, run_id, saver, template,
                              template_title, template_uuid, tenant_uuid, token, user_uuid)
    except Exception as error:
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
                error=_pipeline_error_from_exception(error),
            ),
        )
        logger.exception('Pipeline run failed')
    finally:
        await database.dispose()


async def _start_pipeline(config: Config, database: PostgresDB, dsw_api_url: str, llm_client: LLMClient,
                          questionnaire_uuid: str,
                          run_id: str, saver: DBSaver, template: dict[str, Any], template_title: str,
                          template_uuid: str,
                          tenant_uuid: str, token: str, user_uuid: str) -> None:
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

    pipeline = build_pipeline(database=database, saver=saver, config=config, llm_client=llm_client)
    knowledge_model_uuid, result = await run_pipeline(
        questionnaire_uuid=questionnaire_uuid,
        template_uuid=template_uuid,
        template_title=template['title'],
        template_data=template['content'],
        user_uuid=user_uuid,
        tenant_uuid=tenant_uuid,
        pipeline=pipeline,
        database=database,
        on_progress=on_progress,
        model_name=llm_client.get_model_name(),
        dsw_client=DSWClient(token, dsw_api_url)
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


def _fail_template_not_found(questionnaire_uuid: str, run_id: str, template_title: str, template_uuid: str,
                             tenant_uuid: str, user_uuid: str) -> None:
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
