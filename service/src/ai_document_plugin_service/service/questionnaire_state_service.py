"""The state of a questionnaire at the time a document was generated."""

from dataclasses import dataclass
from uuid import UUID

from ai_document_plugin_service.ai.knowledgemodel.dsw_client import DSWClient


@dataclass(frozen=True)
class QuestionnaireState:
    event_uuid: UUID


class QuestionnaireStateService:
    @staticmethod
    async def capture(dsw_client: DSWClient, questionnaire_uuid: UUID) -> QuestionnaireState:
        """Read the current state id of the questionnaire."""
        return QuestionnaireState(event_uuid=await dsw_client.get_latest_event_uuid(questionnaire_uuid))
