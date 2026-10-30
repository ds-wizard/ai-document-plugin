import uuid

from ai_document_plugin_service.ai.assignment.types import SectionRecord
from ai_document_plugin_service.ai.common.types import TemplateSection


def template_sections_to_records(
    sections: list[TemplateSection],
) -> list[SectionRecord]:
    return [
        SectionRecord(
            id=uuid.uuid4(),
            title=node.title,
            section=node,
            children=template_sections_to_records(node.sections) if node.sections else None,
        )
        for node in sections
    ]
