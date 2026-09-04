import logging
from typing import Any, cast
from uuid import UUID

from haystack import component

from ai_document_plugin_service.ai.assignment.types import SerializedSectionAssignment
from ai_document_plugin_service.ai.persistence.database import Database, JsonValue

logger = logging.getLogger(__name__)


@component
class AssignmentLoaderComponent:
    def __init__(self, database: Database) -> None:
        self.database = database

    @component.output_types(
        assignments=JsonValue | None,
        header_assignments=list[SerializedSectionAssignment] | None,
        found=bool,
    )
    async def run_async(
        self,
        knowledge_model_uuid: UUID,
        template_uuid: UUID,
        *,
        include_header_assignments: bool = False,
    ) -> dict[str, Any]:
        logger.debug(
            'Loading stored assignments for pipeline',
            extra={'knowledge_model_uuid': knowledge_model_uuid, 'template_uuid': str(template_uuid)},
        )
        content_assignments = await self.database.get_assignments(
            knowledge_model_uuid,
            template_uuid,
        )
        header_assignments = (
            await self.database.get_assignments(
                knowledge_model_uuid,
                template_uuid,
                include_header_assignments=True,
            )
            if include_header_assignments
            else None
        )
        found = isinstance(content_assignments, list) and (
            not include_header_assignments or isinstance(header_assignments, list)
        )
        logger.info(
            'Assignment load completed',
            extra={
                'knowledge_model_uuid': knowledge_model_uuid,
                'template_uuid': str(template_uuid),
                'include_header_assignments': include_header_assignments,
                'found': found,
            },
        )

        return {
            'assignments': content_assignments,
            'header_assignments': cast('list[SerializedSectionAssignment] | None', header_assignments),
            'found': found,
        }

    @component.output_types(
        assignments=JsonValue | None,
        header_assignments=list[SerializedSectionAssignment] | None,
        found=bool,
    )
    def run(
        self,
        knowledge_model_uuid: UUID,
        template_uuid: UUID,
        *,
        include_header_assignments: bool = False,
    ) -> dict[str, Any]:
        """Async-only component; the sync pipeline entrypoint is intentionally unsupported."""
        msg = f'{type(self).__name__} is async-only; use run_async() / AsyncPipeline.run_async()'
        raise NotImplementedError(
            msg,
        )
