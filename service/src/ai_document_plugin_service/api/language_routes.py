import logging
from uuid import UUID

from ai_document_plugin_service.ai.knowledgemodel.dsw_client import DSWClient
from ai_document_plugin_service.api.router_helper import api_router
from ai_document_plugin_service.api.types import (
    LanguageOptionResponse,
    QuestionnaireLanguageResponse,
)
from ai_document_plugin_service.data.languages import get_available_languages
from ai_document_plugin_service.di import (
    AuthenticatedDI,
)

logger = logging.getLogger(__name__)
languages_router = api_router()


@languages_router.get('/language/{questionnaire_uuid}')
async def get_questionnaire_language(questionnaire_uuid: UUID, auth: AuthenticatedDI) -> QuestionnaireLanguageResponse:
    questionnaire = await DSWClient(auth.token, auth.api_url).get_questionnaire_detail(questionnaire_uuid)
    language = questionnaire.get('language') if isinstance(questionnaire, dict) else None
    return QuestionnaireLanguageResponse(language=language if isinstance(language, str) else None)


@languages_router.get('/languages')
def list_languages() -> list[LanguageOptionResponse]:
    return [LanguageOptionResponse.model_validate(language) for language in get_available_languages()]
