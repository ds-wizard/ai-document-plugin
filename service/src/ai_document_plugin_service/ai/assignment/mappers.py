import json
import uuid

from ai_document_plugin_service.ai.assignment.types import SectionRecord
from ai_document_plugin_service.ai.common.types import TemplateSection

# Namespace for section ids derived from section content. Changing it invalidates every stored assignment.
SECTION_ID_NAMESPACE = uuid.UUID('6f1c2d3e-8a4b-4c5d-9e6f-7a8b9c0d1e2f')


def template_sections_to_records(
    sections: list[TemplateSection],
    parent_uuid: uuid.UUID | None = None,
) -> list[SectionRecord]:
    """
    Map template sections to records whose ids are derived from their content.

    A section's id is a hash of its title, its content and its parent's id (``None`` for top-level
    sections).
    """
    records: list[SectionRecord] = []
    for node in sections:
        section_id = _section_id(node, parent_uuid)
        records.append(
            SectionRecord(
                id=section_id,
                title=node.title,
                section=node,
                children=template_sections_to_records(node.sections, section_id) if node.sections else None,
            ),
        )
    return records


def _section_id(section: TemplateSection, parent_uuid: uuid.UUID | None) -> uuid.UUID:
    """
    Creates id for a section.

    WARNING!
     Changing this part will lead to all assignments being invalidated because assignments are linked to those ids.
     All Section to Knowledge Model mappings will have to be re-created.
    """
    return uuid.uuid5(
        SECTION_ID_NAMESPACE,
        json.dumps(
            {
                'title': section.title.strip(),
                'content': section.content.strip() if section.content else None,
                'parent_uuid': str(parent_uuid)
            },
            ensure_ascii=False
        )
    )
