import logging
from typing import Any
from uuid import UUID

from haystack import component

from ai_document_plugin_service.ai.assignment.types import SerializedSectionAssignment
from ai_document_plugin_service.ai.persistence.database import Database

logger = logging.getLogger(__name__)


@component
class AssignmentLoaderComponent:
    def __init__(self, database: Database) -> None:
        self.database = database

    @component.output_types(
        assignments=list[SerializedSectionAssignment] | None,
        found=bool,
        up_to_date=bool,
    )
    async def run_async(self, knowledge_model_uuid: UUID, template_uuid: UUID) -> dict[str, Any]:
        logger.debug(
            'Loading stored assignments for pipeline',
            extra={'knowledge_model_uuid': knowledge_model_uuid, 'template_uuid': str(template_uuid)},
        )
        container = await self.database.get_assignments(knowledge_model_uuid, template_uuid)
        if container is None:
            return {'assignments': None, 'found': False, 'up_to_date': False}

        template_updated_at = await self.database.get_template_updated_at(template_uuid)
        logger.info(
            'Assignment load completed',
            extra={
                'knowledge_model_uuid': knowledge_model_uuid,
                'template_uuid': str(template_uuid),
                'found': container is not None,
            },
        )

        return {
            'up_to_date': template_updated_at is not None and container.updated_at >= template_updated_at,
            'assignments': container.assignments,
            'found': True,
        }

    @component.output_types(
        assignments=list[SerializedSectionAssignment] | None,
        found=bool,
        up_to_date=bool,
    )
    def run(self, knowledge_model_uuid: UUID, template_uuid: UUID) -> dict[str, Any]:
        """Async-only component; the sync pipeline entrypoint is intentionally unsupported."""
        msg = f'{type(self).__name__} is async-only; use run_async() / AsyncPipeline.run_async()'
        raise NotImplementedError(
            msg,
        )
