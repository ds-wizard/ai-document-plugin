import logging
import threading
from datetime import UTC, datetime

import fastapi
from openai import AuthenticationError

from ai_document_plugin_service.ai.common.config import (
    Config,
    LLMConfig,
)
from ai_document_plugin_service.ai.common.llm_client import LLMClient
from ai_document_plugin_service.ai.knowledgemodel.dsw_client import DSWClient
from ai_document_plugin_service.ai.persistence.assignment_saver_component import DBSaver
from ai_document_plugin_service.ai.persistence.database import Database
from ai_document_plugin_service.ai.run_pipeline import build_pipeline, run_pipeline
from ai_document_plugin_service.api.auth import AuthenticatedUser
from ai_document_plugin_service.api.types import (
    ErrorType,
    PipelineErrorResponse,
    PipelineRunRequest,
    PipelineSaveRequest,
    PipelineStatus,
    PipelineStatusResponse,
    _model_from_fields,
)
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


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


class LlmClientTenantStore:
    """
    Manages LLM Clients for different tenants. Each tenant has its own LLM client with its own config and limits
    """

    def __init__(self) -> None:
        # tenant id -> llm client
        self._clients: dict[str, LLMClient] = {}
        self._lock = threading.Lock()

    def get_llm_client(self, tenant_uuid: str) -> LLMClient:
        """
        Returns LLM client, creates a new one if it currently doesn't exist
        :param tenant_uuid: Tenant to get the LLM client for.
        """
        with self._lock:
            if tenant_uuid not in self._clients:
                self._clients[tenant_uuid] = LLMClient(tenant_uuid)
            return self._clients[tenant_uuid]


class PipelineRunStore:
    """Thread-safe in-memory store of pipeline run statuses."""

    def __init__(self) -> None:
        self._runs: dict[str, PipelineStatusResponse] = {}
        self._lock = threading.Lock()

    def get(self, run_id: str) -> PipelineStatusResponse | None:
        with self._lock:
            return self._runs.get(run_id)

    def set(self, run_id: str, status: PipelineStatusResponse) -> None:
        with self._lock:
            self._runs[run_id] = status

    def update(self, run_id: str, **updates: object) -> PipelineStatusResponse | None:
        """Store a copy of the current status with ``updates`` applied and a fresh ``updated_at``."""
        with self._lock:
            current = self._runs.get(run_id)
            if current is None:
                return None
            status = current.model_copy(update={**updates, 'updated_at': _now()})
            self._runs[run_id] = status
            return status


class PipelineService:
    def __init__(self, pipeline_queue_manager: PipelineQueueManager, database: Database) -> None:
        self.pipeline_queue_manager = pipeline_queue_manager
        self.database = database
        self._runs = PipelineRunStore()
        self._llm_clients = LlmClientTenantStore()

    def get_pipeline_status(self, run_id: str) -> PipelineStatusResponse | None:
        status = self._runs.get(run_id)
        if status is None or status.status != PipelineStatus.QUEUED:
            return status

        progress_message = self.pipeline_queue_manager.progress_message(run_id)
        if progress_message is None:
            return status

        return status.model_copy(update={'progress_message': progress_message})

    def enqueue_pipeline_job(
        self,
        run_id: str,
        payload: PipelineRunRequest,
        template_title: str,
        auth: AuthenticatedUser,
        config: Config,
    ) -> None:
        """Queue a pipeline job; concurrency is limited by ``pipeline_queue_manager``."""
        run = _model_from_fields(
            PipelineStatusResponse,
            run_id=run_id,
            status=PipelineStatus.QUEUED,
            questionnaire_uuid=payload.questionnaire_uuid,
            template_uuid=payload.template_uuid,
            template_title=template_title,
            updated_at=_now(),
        )
        self._runs.set(run_id, run)

        llm_config = LLMConfig(
            model=payload.llm_model,
            api_key=payload.llm_api_key,
            api_url=payload.llm_api_url,
            parallel_workers=payload.llm_max_workers,
        )
        self.pipeline_queue_manager.enqueue(
            run_id,
            lambda: self._run_pipeline_job(run, auth, llm_config, config),
        )

    async def update_pipeline_result(
        self, run_id: str, save_request: PipelineSaveRequest, auth: AuthenticatedUser
    ) -> PipelineStatusResponse:
        pipeline_status = self.get_pipeline_status(run_id)
        if pipeline_status is None:
            raise fastapi.HTTPException(status_code=404, detail='Pipeline run not found')

        if pipeline_status.knowledge_model_uuid is None:
            raise fastapi.HTTPException(status_code=500, detail='Missing knowledge_model_uuid')

        await self.database.update_result(
            template_uuid=pipeline_status.template_uuid,
            knowledge_model_uuid=pipeline_status.knowledge_model_uuid,
            user_uuid=auth.user_uuid,
            tenant_uuid=auth.tenant_uuid,
            markdown=save_request.result_markdown,
        )

        updated_status = self._runs.update(
            run_id,
            result_format='markdown',
            result_markdown=save_request.result_markdown,
            progress_message=None,
        )
        if updated_status is None:
            raise fastapi.HTTPException(status_code=404, detail='Pipeline run not found')
        return updated_status

    async def _run_pipeline_job(
        self,
        run: PipelineStatusResponse,
        auth: AuthenticatedUser,
        llm_config: LLMConfig,
        config: Config,
    ) -> None:
        try:
            await self._run_pipeline(run, auth, llm_config, config)
        except Exception as error:
            logger.exception('Pipeline run failed')
            self._runs.update(
                run.run_id,
                status=PipelineStatus.FAILED,
                error=_pipeline_error_from_exception(error),
                progress_message=None,
            )

    async def _run_pipeline(
        self,
        run: PipelineStatusResponse,
        auth: AuthenticatedUser,
        llm_config: LLMConfig,
        config: Config,
    ) -> None:
        run_id = run.run_id
        template = await self.database.get_template(run.template_uuid)
        if template is None:
            self._runs.update(
                run_id,
                status=PipelineStatus.FAILED,
                error=PipelineErrorResponse(
                    type=ErrorType.TEMPLATE_NOT_FOUND,
                    message=TEMPLATE_NOT_FOUND_MESSAGE,
                ),
            )
            return

        self._runs.update(run_id, status=PipelineStatus.RUNNING, progress_message='Starting pipeline...')

        llm_client = self._llm_clients.get_llm_client(auth.tenant_uuid)
        llm_client.update_config(llm_config.model, llm_config.api_key, llm_config.api_url, llm_config.parallel_workers)
        pipeline = build_pipeline(
            database=self.database,
            saver=DBSaver(self.database),
            config=config,
            llm_client=llm_client,
        )

        def on_progress(message: str) -> None:
            self._runs.update(run_id, progress_message=message)

        knowledge_model_uuid, result = await run_pipeline(
            questionnaire_uuid=run.questionnaire_uuid,
            template_uuid=run.template_uuid,
            template_title=template['title'],
            template_data=template['content'],
            user_uuid=auth.user_uuid,
            tenant_uuid=auth.tenant_uuid,
            pipeline=pipeline,
            database=self.database,
            on_progress=on_progress,
            model_name=llm_client.get_model_name(),
            dsw_client=DSWClient(auth.token, auth.api_url),
        )

        self._runs.update(
            run_id,
            status=PipelineStatus.SUCCEEDED,
            knowledge_model_uuid=knowledge_model_uuid,
            result_format='markdown',
            result_markdown=result,
            progress_message=None,
        )
