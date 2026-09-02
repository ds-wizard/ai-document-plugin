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
    async def run_async(
        self,
        knowledge_model_uuid: UUID,
        template_uuid: UUID,
        expected_first_section_title: str | None = None,
        excluded_first_section_title: str | None = None,
    ) -> dict[str, Any]:
        logger.debug(
            'Loading stored assignments for pipeline',
            extra={'knowledge_model_uuid': knowledge_model_uuid, 'template_uuid': str(template_uuid)},
        )
        assignments = await self.database.get_assignments(knowledge_model_uuid, template_uuid)
        if expected_first_section_title is not None and not self._has_expected_first_section(
            assignments,
            expected_first_section_title,
        ):
            assignments = None
        if excluded_first_section_title is not None and self._has_expected_first_section(
            assignments,
            excluded_first_section_title,
        ):
            assignments = None
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

    @staticmethod
    def _has_expected_first_section(assignments: object, title: str) -> bool:
        if not isinstance(assignments, list) or not assignments:
            return False
        first_section = assignments[0]
        return isinstance(first_section, dict) and first_section.get('title') == title

    @component.output_types(
        assignments=JsonValue | None,
        found=bool,
    )
    def run(
        self,
        knowledge_model_uuid: UUID,
        template_uuid: UUID,
        expected_first_section_title: str | None = None,
        excluded_first_section_title: str | None = None,
    ) -> dict[str, Any]:
        """Async-only component; the sync pipeline entrypoint is intentionally unsupported."""
        msg = f'{type(self).__name__} is async-only; use run_async() / AsyncPipeline.run_async()'
        raise NotImplementedError(
            msg,
        )
