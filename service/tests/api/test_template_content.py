import pytest
from pydantic import ValidationError

from ai_document_plugin_service.api.types import TemplateCreateRequest, TemplateUpdateRequest


@pytest.mark.parametrize('request_type', [TemplateCreateRequest, TemplateUpdateRequest])
def test_template_content_round_trips_nested_json(request_type):
    content = {
        'description': 'Preserved metadata',
        'sections': [
            {'title': 'Parent', 'sections': [{'title': 'Child', 'content': 'Instructions'}]},
            {'title': 'Leaf', 'content': None, 'custom': 'Preserved section metadata'},
        ],
    }
    payload = request_type.model_validate({'title': 'Template', 'content': content})

    assert payload.content.sections[0].sections[0].content == 'Instructions'
    assert payload.content.model_dump(mode='json', exclude_unset=True) == content


@pytest.mark.parametrize('request_type', [TemplateCreateRequest, TemplateUpdateRequest])
@pytest.mark.parametrize(
    'content',
    [
        {},
        {'sections': 'invalid'},
        {'sections': [{'content': 'Missing title'}]},
        {'sections': [{'title': 'Parent', 'sections': [{'title': 123}]}]},
    ],
)
def test_template_requests_reject_invalid_content(request_type, content):
    with pytest.raises(ValidationError):
        request_type.model_validate({'title': 'Template', 'content': content})
