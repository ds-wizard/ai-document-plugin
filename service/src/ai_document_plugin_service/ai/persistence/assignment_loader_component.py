import logging
from typing import Any
from uuid import UUID

from haystack import component

from ai_document_plugin_service.ai.persistence.database import Database, JsonValue

logger = logging.getLogger(__name__)


@component
class AssignmentLoaderComponent:
    def __init__(self, database: Database) -> None:
        self.database = database

    @component.output_types(
        assignments=JsonValue | None,
        found=bool,
    )
    async def run_async(self, knowledge_model_uuid: UUID, template_uuid: UUID) -> dict[str, Any]:
        logger.debug(
            'Loading stored assignments for pipeline',
            extra={'knowledge_model_uuid': knowledge_model_uuid, 'template_uuid': str(template_uuid)},
        )
        assignments = await self.database.get_assignments(knowledge_model_uuid, template_uuid)
        logger.info(
            'Assignment load completed',
            extra={
                'knowledge_model_uuid': knowledge_model_uuid,
                'template_uuid': str(template_uuid),
                'found': assignments is not None,
            },
        )

        return {
            'assignments': assignments,
            'found': assignments is not None,
        }

    @component.output_types(
        assignments=JsonValue | None,
        found=bool,
    )
    def run(self, knowledge_model_uuid: UUID, template_uuid: UUID) -> dict[str, Any]:
        """Async-only component; the sync pipeline entrypoint is intentionally unsupported."""
        msg = f'{type(self).__name__} is async-only; use run_async() / AsyncPipeline.run_async()'
        raise NotImplementedError(
            msg,
        )
