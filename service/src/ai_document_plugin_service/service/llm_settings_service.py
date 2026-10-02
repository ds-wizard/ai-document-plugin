from ai_document_plugin_service.ai.common.config import LLMConfig
from ai_document_plugin_service.ai.persistence.database import Database
from ai_document_plugin_service.api.auth import AuthenticatedUser
from ai_document_plugin_service.api.types import LlmSettingsResponse, LlmSettingsUpdateRequest
from ai_document_plugin_service.service.errors import AccessDeniedError, ValidationError


class LlmSettingsService:
    ADMIN_ONLY_MESSAGE = 'Only administrators can manage the LLM settings.'
    API_KEY_REQUIRED_MESSAGE = 'API key is required'

    def __init__(self, database: Database) -> None:
        self._database = database

    async def get(self, auth: AuthenticatedUser) -> LlmSettingsResponse:
        self._require_admin(auth)
        return self._to_response(await self._database.get_llm_settings(auth.tenant_uuid))

    async def update(self, auth: AuthenticatedUser, payload: LlmSettingsUpdateRequest) -> LlmSettingsResponse:
        self._require_admin(auth)

        async with self._database.transaction():
            api_key = payload.api_key
            if api_key is None:
                existing = await self._database.get_llm_settings(auth.tenant_uuid)
                if existing is None:
                    raise ValidationError(self.API_KEY_REQUIRED_MESSAGE)
                api_key = existing.api_key

            llm_config = LLMConfig(
                model=payload.model,
                api_key=api_key,
                api_url=payload.api_url,
                parallel_workers=payload.max_workers,
            )
            await self._database.save_llm_settings(auth.tenant_uuid, llm_config, auth.user_uuid)

        return self._to_response(llm_config)

    def _require_admin(self, auth: AuthenticatedUser) -> None:
        if not auth.is_admin:
            raise AccessDeniedError(self.ADMIN_ONLY_MESSAGE)

    @staticmethod
    def _to_response(llm_config: LLMConfig | None) -> LlmSettingsResponse:
        if llm_config is None:
            return LlmSettingsResponse(model=None, api_url=None, max_workers=None, api_key_set=False)
        return LlmSettingsResponse(
            model=llm_config.model,
            api_url=llm_config.api_url,
            max_workers=llm_config.parallel_workers,
            api_key_set=True,
        )
