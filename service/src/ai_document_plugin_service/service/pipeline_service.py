import asyncio
import logging
import threading
from asyncio import Task
from uuid import UUID

from openai import AuthenticationError

from ai_document_plugin_service.ai.common.config import (
    Config,
    LLMConfig,
)
from ai_document_plugin_service.ai.common.llm_client import LLMClient
from ai_document_plugin_service.ai.knowledgemodel.dsw_client import DSWClient
from ai_document_plugin_service.ai.persistence.assignment_saver_component import DBSaver
from ai_document_plugin_service.ai.persistence.database import Database, GenerationRecord
from ai_document_plugin_service.ai.run_pipeline import build_pipeline, run_pipeline
from ai_document_plugin_service.api.auth import AuthenticatedUser
from ai_document_plugin_service.api.types import (
    ErrorType,
    PipelineErrorResponse,
    PipelineRunRequest,
    PipelineSaveRequest,
    PipelineStatus,
    PipelineStatusResponse,
    PipelineSummaryResponse,
    _model_from_fields,
)
from ai_document_plugin_service.service.errors import InternalError, NotFoundError
from ai_document_plugin_service.service.pipeline_queue_manager import PipelineQueueManager

logger = logging.getLogger(__name__)

AUTHORIZATION_ERROR_MESSAGE = 'Authorization error, invalid or expired token.'
SERVER_ERROR_MESSAGE = 'The action could not be completed. Please try again later.'
TEMPLATE_NOT_FOUND_MESSAGE = 'Template not found.'


def _pipeline_error_from_exception(error: Exception) -> PipelineErrorResponse:
    if isinstance(error, AuthenticationError) or isinstance(error.__cause__, AuthenticationError):
        return PipelineErrorResponse(
            type=ErrorType.AUTHENTICATION_FAILED,
            message=AUTHORIZATION_ERROR_MESSAGE,
        )

    return PipelineErrorResponse(
        type=ErrorType.SERVER_ERROR,
        message=SERVER_ERROR_MESSAGE,
    )


def _generation_error(record: GenerationRecord) -> PipelineErrorResponse | None:
    if record.error_type is None or record.error_message is None:
        return None
    return PipelineErrorResponse(type=ErrorType(record.error_type), message=record.error_message)


def _generation_record_to_status_response(record: GenerationRecord) -> PipelineStatusResponse:
    return _model_from_fields(
        PipelineStatusResponse,
        run_id=record.run_id,
        status=PipelineStatus(record.status),
        questionnaire_uuid=record.questionnaire_uuid,
        knowledge_model_uuid=record.knowledge_model_uuid,
        template_uuid=record.template_uuid,
        title=record.title,
        error=_generation_error(record),
        result_format='markdown' if record.result_markdown is not None else None,
        result_markdown=record.result_markdown,
        progress_message=record.progress_message,
        updated_at=record.updated_at.isoformat(),
    )


def _generation_record_to_summary_response(record: GenerationRecord) -> PipelineSummaryResponse:
    return _model_from_fields(
        PipelineSummaryResponse,
        run_id=record.run_id,
        status=PipelineStatus(record.status),
        title=record.title,
        error=_generation_error(record),
        progress_message=record.progress_message,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
    )


class LlmClientTenantStore:
    """
    Manages LLM Clients for different tenants. Each tenant has its own LLM client with its own config and limits
    """

    def __init__(self) -> None:
        # tenant id -> llm client
        self._clients: dict[UUID, LLMClient] = {}
        self._lock = threading.Lock()

    def get_llm_client(self, tenant_uuid: UUID) -> LLMClient:
        """
        Returns LLM client, creates a new one if it currently doesn't exist
        :param tenant_uuid: Tenant to get the LLM client for.
        """
        with self._lock:
            if tenant_uuid not in self._clients:
                self._clients[tenant_uuid] = LLMClient(tenant_uuid)
            return self._clients[tenant_uuid]


def _log_background_update_failure(task: Task[object]) -> None:
    # Progress-message updates are best-effort and fired without awaiting; this guards
    # against an unhandled exception being silently swallowed.
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        logger.error('Failed to persist pipeline progress message', exc_info=error)


class PipelineService:
    def __init__(self, pipeline_queue_manager: PipelineQueueManager, database: Database) -> None:
        self.pipeline_queue_manager = pipeline_queue_manager
        self.database = database
        self._llm_clients = LlmClientTenantStore()

    async def get_pipeline_status(self, run_id: UUID, auth: AuthenticatedUser) -> PipelineStatusResponse | None:
        record = await self.database.get_generation(run_id, auth.tenant_uuid, auth.user_uuid)
        if record is None:
            return None

        status = _generation_record_to_status_response(record)
        if status.status != PipelineStatus.QUEUED:
            return status

        # Handle queued progress message (x dmps ahead in queue)
        progress_message = self.pipeline_queue_manager.progress_message(run_id)
        if progress_message is None:
            return status

        return status.model_copy(update={'progress_message': progress_message})

    async def list_history(self, questionnaire_uuid: UUID, auth: AuthenticatedUser) -> list[PipelineSummaryResponse]:
        records = await self.database.list_generations(questionnaire_uuid, auth.tenant_uuid, auth.user_uuid)
        return [_generation_record_to_summary_response(record) for record in records]

    async def enqueue_pipeline_job(
        self,
        payload: PipelineRunRequest,
        title: str,
        auth: AuthenticatedUser,
        config: Config,
    ) -> UUID:
        """Queue a pipeline job; concurrency is limited by ``pipeline_queue_manager``."""
        run_id = await self.database.create_generation(
            questionnaire_uuid=payload.questionnaire_uuid,
            template_uuid=payload.template_uuid,
            title=title,
            user_uuid=auth.user_uuid,
            tenant_uuid=auth.tenant_uuid,
            status=PipelineStatus.QUEUED,
        )

        llm_config = LLMConfig(
            model=payload.llm_model,
            api_key=payload.llm_api_key,
            api_url=payload.llm_api_url,
            parallel_workers=payload.llm_max_workers,
        )
        self.pipeline_queue_manager.enqueue(
            run_id,
            lambda: self._run_pipeline_job(
                run_id,
                payload.questionnaire_uuid,
                payload.template_uuid,
                auth,
                llm_config,
                config,
            ),
        )
        return run_id

    async def update_pipeline_result(
        self, run_id: UUID, save_request: PipelineSaveRequest, auth: AuthenticatedUser
    ) -> PipelineStatusResponse:
        record = await self.database.get_generation(run_id, auth.tenant_uuid, auth.user_uuid)
        if record is None:
            raise NotFoundError(NotFoundError.PIPELINE_RUN_MESSAGE)

        if record.knowledge_model_uuid is None:
            raise InternalError(InternalError.MISSING_KNOWLEDGE_MODEL_MESSAGE)

        await self.database.update_result(
            template_uuid=record.template_uuid,
            knowledge_model_uuid=record.knowledge_model_uuid,
            user_uuid=auth.user_uuid,
            tenant_uuid=auth.tenant_uuid,
            markdown=save_request.result_markdown,
        )

        updated_record = await self.database.update_generation(
            run_id,
            auth.tenant_uuid,
            result_markdown=save_request.result_markdown,
            progress_message=None,
        )
        if updated_record is None:
            raise NotFoundError(NotFoundError.PIPELINE_RUN_MESSAGE)
        return _generation_record_to_status_response(updated_record)

    async def _run_pipeline_job(
        self,
        run_id: UUID,
        questionnaire_uuid: UUID,
        template_uuid: UUID,
        auth: AuthenticatedUser,
        llm_config: LLMConfig,
        config: Config,
    ) -> None:
        try:
            await self._run_pipeline(run_id, questionnaire_uuid, template_uuid, auth, llm_config, config)
        except Exception as error:
            logger.exception('Pipeline run failed')
            pipeline_error = _pipeline_error_from_exception(error)
            await self.database.update_generation(
                run_id,
                auth.tenant_uuid,
                status=PipelineStatus.FAILED,
                error_type=pipeline_error.type,
                error_message=pipeline_error.message,
                progress_message=None,
            )

    async def _run_pipeline(
        self,
        run_id: UUID,
        questionnaire_uuid: UUID,
        template_uuid: UUID,
        auth: AuthenticatedUser,
        llm_config: LLMConfig,
        config: Config,
    ) -> None:
        template = await self.database.get_template(template_uuid, auth.tenant_uuid)
        if template is None:
            await self.database.update_generation(
                run_id,
                auth.tenant_uuid,
                status=PipelineStatus.FAILED,
                error_type=ErrorType.TEMPLATE_NOT_FOUND,
                error_message=TEMPLATE_NOT_FOUND_MESSAGE,
            )
            return

        await self.database.update_generation(
            run_id,
            auth.tenant_uuid,
            status=PipelineStatus.RUNNING,
            progress_message='Starting pipeline...',
        )

        llm_client = self._llm_clients.get_llm_client(auth.tenant_uuid)
        llm_client.update_config(llm_config.model, llm_config.api_key, llm_config.api_url, llm_config.parallel_workers)
        pipeline = build_pipeline(
            database=self.database,
            saver=DBSaver(self.database),
            config=config,
            llm_client=llm_client,
        )

        def on_progress(message: str) -> None:
            # Called synchronously from deep inside the (async) pipeline; fire the DB
            # write without awaiting it so progress reporting never blocks generation.
            task = asyncio.ensure_future(
                self.database.update_generation(run_id, auth.tenant_uuid, progress_message=message),
            )
            task.add_done_callback(_log_background_update_failure)

        knowledge_model_uuid, result = await run_pipeline(
            questionnaire_uuid=questionnaire_uuid,
            template_uuid=template_uuid,
            template_title=template.title,
            template_data=template.content,
            user_uuid=auth.user_uuid,
            tenant_uuid=auth.tenant_uuid,
            pipeline=pipeline,
            database=self.database,
            on_progress=on_progress,
            model_name=llm_client.get_model_name(),
            dsw_client=DSWClient(auth.token, auth.api_url),
        )

        await self.database.update_generation(
            run_id,
            auth.tenant_uuid,
            status=PipelineStatus.SUCCEEDED,
            knowledge_model_uuid=knowledge_model_uuid,
            result_markdown=result,
            progress_message=None,
        )
