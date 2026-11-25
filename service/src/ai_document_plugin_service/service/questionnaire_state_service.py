"""The state of a questionnaire at the time a document was generated.

The pipeline only asks for a state and stores it with the generation; what the state consists of is decided here.
Today it is the UUID of the newest event in the questionnaire's DSW event log, a cheap check that something changed
since, and the replies themselves (see ``build_snapshot``), which say what changed.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from ai_document_plugin_service.ai.knowledgemodel.dsw_client import DSWClient
from ai_document_plugin_service.ai.knowledgemodel.questionnaire_diff import ChangeDescription, describe_changes
from ai_document_plugin_service.ai.knowledgemodel.questionnaire_snapshot import StoredReply


@dataclass(frozen=True)
class QuestionnaireState:
    event_uuid: UUID


class QuestionnaireStateService:
    @staticmethod
    async def capture(dsw_client: DSWClient, questionnaire_uuid: UUID) -> QuestionnaireState:
        """Read the current state id of the questionnaire."""
        return QuestionnaireState(event_uuid=await dsw_client.get_latest_event_uuid(questionnaire_uuid))

    @staticmethod
    def changes(stored: Iterable[StoredReply], current_detail: dict[str, Any]) -> list[ChangeDescription]:
        """What changed between the stored replies and the questionnaire detail as DSW returns it now."""
        return describe_changes(stored, current_detail)
