from typing import Any

from haystack import component

from ai_document_plugin_service.ai.persistence.database import Database, JsonValue


@component
class AssignmentLoaderComponent:
    def __init__(self, database: Database) -> None:
        self.database = database

    @component.output_types(
        assignments=JsonValue | None,
        found=bool,
    )
    def run(self, knowledge_model_uuid: str, template_uuid: str) -> dict[str, Any]:
        assignments = self.database.get_assignments(knowledge_model_uuid, template_uuid)

        return {
            'assignments': assignments,
            'found': assignments is not None,
        }
