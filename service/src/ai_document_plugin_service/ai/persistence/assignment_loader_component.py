from typing import Any
from uuid import UUID

from haystack import component

from ai_document_plugin_service.ai.persistence.database import Database, JsonValue


@component
class AssignmentLoaderComponent:
    @staticmethod
    @component.output_types(
        assignments=JsonValue | None,
        found=bool,
    )
    def run(knowledge_model_uuid: UUID, template_uuid: UUID, database: Database) -> dict[str, Any]:
        assignments = database.get_assignments(knowledge_model_uuid, template_uuid)

        return {
            'assignments': assignments,
            'found': assignments is not None,
        }
