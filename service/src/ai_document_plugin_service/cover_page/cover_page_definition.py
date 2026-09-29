"""Extract translation and generation labels from the cover page definition."""


def cover_page_assignment_field_labels(definition: dict) -> dict[str, str]:
    return {field['id']: field['label'] for section in definition['sections'] for field in section['fields']}


def cover_page_translation_labels(definition: dict) -> dict[str, str]:
    metadata = definition['metadata']
    history = definition['history']
    return {
        metadata['title']['id']: metadata['title']['text'],
        **{column['id']: column['text'] for column in metadata['columns']},
        **{field['id']: field['label'] for field in metadata['fields']},
        history['title']['id']: history['title']['text'],
        **{column['id']: column['text'] for column in history['columns']},
        **cover_page_assignment_field_labels(definition),
    }
