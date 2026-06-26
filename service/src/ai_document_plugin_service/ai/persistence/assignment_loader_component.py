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
    async def run_async(self, knowledge_model_uuid: str, template_uuid: str) -> dict[str, Any]:
        assignments = await self.database.get_assignments(knowledge_model_uuid, template_uuid)

        return {
            'assignments': assignments,
            'found': assignments is not None,
        }

    @component.output_types(
        assignments=JsonValue | None,
        found=bool,
    )
    def run(self, knowledge_model_uuid: str, template_uuid: str) -> dict[str, Any]:
        """Async-only component; the sync pipeline entrypoint is intentionally unsupported."""
        raise NotImplementedError(
            f'{type(self).__name__} is async-only; use run_async() / AsyncPipeline.run_async()',
        )
