import fastapi

from ai_document_plugin_service.api.auth import verify_authenticated


def api_router() -> fastapi.APIRouter:
    return fastapi.APIRouter(dependencies=[fastapi.Depends(verify_authenticated)])


def unprotected_api_router() -> fastapi.APIRouter:
    return fastapi.APIRouter()
