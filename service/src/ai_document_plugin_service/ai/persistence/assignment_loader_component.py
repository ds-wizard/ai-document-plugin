import logging
from typing import Any
from uuid import UUID

from haystack import component

from ai_document_plugin_service.ai.assignment.types import SectionQuestionPaths
from ai_document_plugin_service.ai.persistence.database import Database

logger = logging.getLogger(__name__)


@component
class AssignmentLoaderComponent:
    def __init__(self, database: Database) -> None:
        self.database = database

    @component.output_types(stored_question_paths=SectionQuestionPaths)
    async def run_async(self, knowledge_model_uuid: UUID, template_uuid: UUID) -> dict[str, Any]:
        """Load the stored question paths of the template's sections, by section id."""
        logger.debug(
            'Loading stored assignments for pipeline',
            extra={'knowledge_model_uuid': knowledge_model_uuid, 'template_uuid': str(template_uuid)},
        )
        container = await self.database.get_assignments(knowledge_model_uuid, template_uuid)
        stored = container.question_paths if container is not None else {}
        logger.info(
            'Assignment load completed',
            extra={
                'knowledge_model_uuid': knowledge_model_uuid,
                'template_uuid': str(template_uuid),
                'stored_section_count': len(stored),
            },
        )
        return {'stored_question_paths': stored}

    @component.output_types(stored_question_paths=SectionQuestionPaths)
    def run(self, knowledge_model_uuid: UUID, template_uuid: UUID) -> dict[str, Any]:
        """Async-only component; the sync pipeline entrypoint is intentionally unsupported."""
        msg = f'{type(self).__name__} is async-only; use run_async() / Pipeline.run_async()'
        raise NotImplementedError(
            msg,
        )
