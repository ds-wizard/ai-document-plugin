from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ai_document_plugin_service.ai.common.types import TemplateContent
from ai_document_plugin_service.ai.persistence.database import TemplateRecord


def _row(content):
    return SimpleNamespace(
        uuid=uuid4(),
        title='Template',
        content=content,
        tenant_uuid=uuid4(),
        user_uuid=None,
        cover_page_version='1',
    )


def test_from_row_validates_template_content_without_changing_json():
    content = {
        'description': 'Metadata',
        'sections': [{'id': 'projects', 'title': 'Projects', 'sections': [{'title': 'Český projekt'}]}],
    }
    row = _row(content)
    record = TemplateRecord.from_row(row)

    assert isinstance(record.content, TemplateContent)
    assert record.content.sections[0].sections[0].title == 'Český projekt'
    assert record.content.model_dump(mode='json', exclude_unset=True) == content
    assert row.content == content


def test_from_row_rejects_invalid_template_json():
    with pytest.raises(ValidationError):
        TemplateRecord.from_row(_row({'sections': [{'content': 'Missing title'}]}))
