"""Extract generation labels from the cover page definition."""


def cover_page_assignment_field_labels(definition: dict) -> dict[str, str]:
    return {field['id']: field['label'] for section in definition['sections'] for field in section['fields']}
