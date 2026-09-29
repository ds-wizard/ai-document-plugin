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
        cover_page_assignments=list[SerializedSectionAssignment],
        found=bool,
        reuse_content=bool,
    )
    async def run_async(
        self,
        knowledge_model_uuid: UUID,
        template_uuid: UUID,
        *,
        include_cover_page_assignments: bool = False,
    ) -> dict[str, Any]:
        logger.debug(
            'Loading stored assignments for pipeline',
            extra={'knowledge_model_uuid': knowledge_model_uuid, 'template_uuid': str(template_uuid)},
        )
        content_assignments = await self.database.get_assignments(
            knowledge_model_uuid,
            template_uuid,
        )
        cover_page_assignments = (
            await self.database.get_assignments(
                knowledge_model_uuid,
                template_uuid,
                include_cover_page_assignments=True,
            )
            if include_cover_page_assignments
            else None
        )
        found = content_assignments is not None and (
            not include_cover_page_assignments or cover_page_assignments is not None
        )
        logger.info(
            'Assignment load completed',
            extra={
                'knowledge_model_uuid': knowledge_model_uuid,
                'template_uuid': str(template_uuid),
                'include_cover_page_assignments': include_cover_page_assignments,
                'found': found,
            },
        )

        return {
            'assignments': content_assignments,
            'cover_page_assignments': cover_page_assignments or [],
            'found': found,
            'reuse_content': content_assignments is not None,
        }

    @component.output_types(
        assignments=list[SerializedSectionAssignment] | None,
        cover_page_assignments=list[SerializedSectionAssignment],
        found=bool,
        reuse_content=bool,
    )
    def run(
        self,
        knowledge_model_uuid: UUID,
        template_uuid: UUID,
        *,
        include_cover_page_assignments: bool = False,
    ) -> dict[str, Any]:
        """Async-only component; the sync pipeline entrypoint is intentionally unsupported."""
        msg = f'{type(self).__name__} is async-only; use run_async() / AsyncPipeline.run_async()'
        raise NotImplementedError(
            msg,
        )
