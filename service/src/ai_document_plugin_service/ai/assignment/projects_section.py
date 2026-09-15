from ai_document_plugin_service.cover_page.schema import CoverPageDefinition


def build_cover_page_assignment_template(definition: CoverPageDefinition) -> dict[str, object]:
    return {
        'sections': [
            {
                'title': section.title,
                'content': section.description,
            }
            for section in definition.assigned_sections
        ],
    }
