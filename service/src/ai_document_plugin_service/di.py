from typing import Annotated

import fastapi

from ai_document_plugin_service.ai.common import Config
from ai_document_plugin_service.ai.persistence.database import Database, PostgresDB
from ai_document_plugin_service.api.auth import AuthenticatedUser, verify_authenticated
from ai_document_plugin_service.service.pipeline_queue_manager import PipelineQueueManager
from ai_document_plugin_service.service.pipeline_service import PipelineService


def setup_app_state(app: fastapi.FastAPI, config: Config) -> None:
    app.state.config = config
    app.state.database = PostgresDB(config.database)
    app.state.pipeline_queue_manager = PipelineQueueManager(config.max_parallel_executions)
    app.state.pipeline_service = PipelineService(app.state.pipeline_queue_manager)


AuthenticatedDI = Annotated[AuthenticatedUser, fastapi.Depends(verify_authenticated)]


def _get_pipeline_service(request: fastapi.Request) -> PipelineService:
    return request.app.state.pipeline_service


PipelineServiceDI = Annotated[PipelineService, fastapi.Depends(_get_pipeline_service)]


def _get_app_config(request: fastapi.Request) -> Config:
    return request.app.state.config


ConfigDI = Annotated[Config, fastapi.Depends(_get_app_config)]


def _get_database(request: fastapi.Request) -> Database:
    return request.app.state.database


DatabaseDI = Annotated[Database, fastapi.Depends(_get_database)]
