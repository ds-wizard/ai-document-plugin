import logging

from ai_document_plugin_service.api.router_helper import api_router
from ai_document_plugin_service.api.types import (
    LlmSettingsResponse,
    LlmSettingsUpdateRequest,
)
from ai_document_plugin_service.di import (
    AuthenticatedDI,
    LlmSettingsServiceDI,
)

logger = logging.getLogger(__name__)
settings_router = api_router()


@settings_router.get('/settings/llm')
async def get_llm_settings(llm_settings: LlmSettingsServiceDI, auth: AuthenticatedDI) -> LlmSettingsResponse:
    return await llm_settings.get(auth)


@settings_router.put('/settings/llm')
async def update_llm_settings(
    payload: LlmSettingsUpdateRequest, llm_settings: LlmSettingsServiceDI, auth: AuthenticatedDI
) -> LlmSettingsResponse:
    return await llm_settings.update(auth, payload)
