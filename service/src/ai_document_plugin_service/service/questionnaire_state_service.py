"""Utility for comparing and managing state of a questionnaire"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from ai_document_plugin_service.ai.knowledgemodel.dsw_client import DSWClient
from ai_document_plugin_service.ai.knowledgemodel.questionnaire_diff import ChangeNode, change_tree
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
    def changes(stored: Iterable[StoredReply], current_detail: dict[str, Any]) -> list[ChangeNode]:
        """What changed between the stored replies and the questionnaire detail as DSW returns it now, as a tree."""
        return change_tree(stored, current_detail)
