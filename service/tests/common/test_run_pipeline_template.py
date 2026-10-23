from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from haystack import Pipeline

from ai_document_plugin_service.ai.run_pipeline import run_pipeline
from ai_document_plugin_service.ai.common.types import TemplateContent


async def test_run_pipeline_passes_typed_template_to_components(monkeypatch):
    class StopPipeline(Exception):
        pass

    runner = AsyncMock(side_effect=StopPipeline)
    monkeypatch.setattr('ai_document_plugin_service.ai.run_pipeline.run_haystack_pipeline', runner)
    client = AsyncMock()
    client.get_questionnaire_detail.return_value = {
        'replies': {}, 'knowledgeModel': {},
        'knowledgeModelPackage': {'uuid': str(uuid4()), 'name': 'Model', 'version': '1'},
    }
    raw = {'description': 'Metadata', 'sections': [{'title': 'Parent', 'sections': [{'title': 'Child'}]}]}
    template = TemplateContent.model_validate(raw)

    with pytest.raises(StopPipeline):
        await run_pipeline(
            questionnaire_uuid=uuid4(), template_uuid=uuid4(),
            template_data=template, tenant_uuid=uuid4(), pipeline=Pipeline(), dsw_client=client,
            project_versions=[],
        )

    assert runner.await_args is not None
    data = runner.await_args.kwargs['data']
    for name in ('assignment_component', 'dmp_polisher_component'):
        assert data[name]['template_data'] is template
    assert template.model_dump(mode='json', exclude_unset=True) == raw
