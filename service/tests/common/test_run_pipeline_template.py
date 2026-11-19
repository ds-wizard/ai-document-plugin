from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from haystack import Pipeline

from ai_document_plugin_service.ai.common.source_ids import build_source_ids
from ai_document_plugin_service.ai.common.types import TemplateContent
from ai_document_plugin_service.ai.run_pipeline import run_pipeline


async def test_run_pipeline_passes_typed_template_to_components(monkeypatch):
    class StopPipeline(Exception):
        pass

    runner = AsyncMock(side_effect=StopPipeline)
    monkeypatch.setattr('ai_document_plugin_service.ai.run_pipeline.run_haystack_pipeline', runner)
    client = AsyncMock()
    client.get_questionnaire_detail.return_value = {
        'replies': {},
        'knowledgeModel': {},
        'knowledgeModelPackage': {'uuid': str(uuid4()), 'name': 'Model', 'version': '1'},
    }
    raw = {'description': 'Metadata', 'sections': [{'title': 'Parent', 'sections': [{'title': 'Child'}]}]}
    template = TemplateContent.model_validate(raw)

    with pytest.raises(StopPipeline):
        await run_pipeline(
            questionnaire_uuid=uuid4(),
            template_uuid=uuid4(),
            template_data=template,
            tenant_uuid=uuid4(),
            pipeline=Pipeline(),
            dsw_client=client,
            project_versions=[],
        )

    assert runner.await_args is not None
    data = runner.await_args.kwargs['data']
    for name in ('assignment_component', 'dmp_polisher_component'):
        assert data[name]['template_data'] is template
    assert template.model_dump(mode='json', exclude_unset=True) == raw


async def test_pipeline_restores_sources_in_final_cover_and_pre_polished_outputs(monkeypatch):
    replies = {'ch.list.item2.q': {}, 'ch.list.item1.q': {}}
    runner = AsyncMock(
        return_value={
            'dmp_generator_component': {'markdown': '<statement source="q1">Before.</statement>'},
            'cover_page_component': {
                'markdown': '# Cover\n<statement source="q2">Project.</statement>\n\n'
                '# Body\n<statement source="q1 q2">Combined.</statement>',
            },
        }
    )
    monkeypatch.setattr('ai_document_plugin_service.ai.run_pipeline.run_haystack_pipeline', runner)
    client = AsyncMock()
    client.get_questionnaire_detail.return_value = {
        'replies': replies,
        'knowledgeModel': {},
        'knowledgeModelPackage': {'uuid': str(uuid4()), 'name': 'Model', 'version': '1'},
    }
    result = await run_pipeline(
        questionnaire_uuid=uuid4(),
        template_uuid=uuid4(),
        template_data=TemplateContent.model_validate({'sections': []}),
        tenant_uuid=uuid4(),
        pipeline=Pipeline(),
        dsw_client=client,
        project_versions=[],
    )
    assert runner.await_args is not None
    assert runner.await_args.kwargs['data']['dmp_generator_component']['source_ids'] == build_source_ids(replies)
    assert result.dmp_pre_polished == '<statement source="ch.list.item1.q">Before.</statement>'
    assert result.markdown == (
        '# Cover\n<statement source="ch.list.item2.q">Project.</statement>\n\n'
        '# Body\n<statement source="ch.list.item1.q ch.list.item2.q">Combined.</statement>'
    )
