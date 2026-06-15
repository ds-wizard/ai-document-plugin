from fastapi import Request

from ai_document_plugin_service.ai.common.config import Config
from ai_document_plugin_service.ai.persistence.database import PostgresDB


def get_app_config(request: Request) -> Config:
    return request.app.state.config


def get_database(request: Request) -> PostgresDB:
    return request.app.state.database
