import logging
from typing import Any
from uuid import UUID

from haystack import component

from ai_document_plugin_service.ai.assignment.compatibility_utils import (
    convert_mappings_to_assignment_tree_recursive,
)
from ai_document_plugin_service.ai.assignment.mappers import template_sections_to_records
from ai_document_plugin_service.ai.assignment.section_tree import collect_leaf_sections
from ai_document_plugin_service.ai.assignment.types import SerializedSectionAssignment

# Haystack inspects component input annotations at runtime.
from ai_document_plugin_service.ai.common.types import TemplateContent
from ai_document_plugin_service.ai.persistence.database import Database

logger = logging.getLogger(__name__)


@component
class AssignmentLoaderComponent:
    def __init__(self, database: Database) -> None:
        self.database = database

    @component.output_types(
        assignments=list[SerializedSectionAssignment] | None,
        complete=bool,
    )
    async def run_async(
        self,
        knowledge_model_uuid: UUID,
        template_uuid: UUID,
        template_data: TemplateContent,
        km: dict[str, Any],
    ) -> dict[str, Any]:
        """Rebuild the stored assignment tree if every current leaf section of the template is stored.

        Section ids change whenever a section or anything above it is edited, so ``complete`` is false
        as soon as the template changed since the assignments were saved.
        """
        logger.debug(
            'Loading stored assignments for pipeline',
            extra={'knowledge_model_uuid': knowledge_model_uuid, 'template_uuid': str(template_uuid)},
        )
        container = await self.database.get_assignments(knowledge_model_uuid, template_uuid)
        stored = container.question_paths if container is not None else {}

        sections = template_sections_to_records(template_data.sections)
        leaf_ids = {leaf.id for leaf in collect_leaf_sections(sections)}
        # Check if there is an assignment for every section
        complete = leaf_ids.issubset(stored.keys())
        logger.info(
            'Assignment load completed',
            extra={
                'knowledge_model_uuid': knowledge_model_uuid,
                'template_uuid': str(template_uuid),
                'section_count': len(leaf_ids),
                'stored_section_count': len(stored),
                'complete': complete,
            },
        )
        if not complete:
            return {'assignments': None, 'complete': False}

        assignments = convert_mappings_to_assignment_tree_recursive(sections, stored, km)
        return {'assignments': [assignment.to_dict() for assignment in assignments], 'complete': True}

    @component.output_types(
        assignments=list[SerializedSectionAssignment] | None,
        complete=bool,
    )
    def run(
        self,
        knowledge_model_uuid: UUID,
        template_uuid: UUID,
        template_data: TemplateContent,
        km: dict[str, Any],
    ) -> dict[str, Any]:
        """Async-only component; the sync pipeline entrypoint is intentionally unsupported."""
        msg = f'{type(self).__name__} is async-only; use run_async() / Pipeline.run_async()'
        raise NotImplementedError(
            msg,
        )
