from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from haystack import Pipeline

from ai_document_plugin_service.ai.assignment.assignment_component import AssignmentComponent
from ai_document_plugin_service.ai.common.config import load_config
from ai_document_plugin_service.ai.common.types import TemplateContent, TemplateSection
from ai_document_plugin_service.ai.polishing.dmp_polisher_component import DmpPolisherComponent


async def test_haystack_assignment_accepts_typed_template():
    config = load_config(str(Path(__file__).resolve().parents[2] / 'config.test.yaml'))
    llm = MagicMock()
    llm.get_max_workers.return_value = 1
    pipeline = Pipeline()
    assign = AssignmentComponent(llm, config)
    assign.section_matcher.match_questions_to_sections = AsyncMock(return_value={})
    pipeline.add_component('assign', assign)
    template = TemplateContent(sections=[TemplateSection(title='Body')])

    km = {'entities': {'questions': {}, 'chapters': {}, 'answers': {}}}
    result = await pipeline.run_async({'assign': {'data': [], 'template_data': template, 'km': km}})

    assert result['assign']['assignments'][0].title == 'Body'


async def test_haystack_polisher_uses_typed_nested_sections():
    llm = AsyncMock()
    llm.polish_dmp.return_value = '# Body\n\nPolished'
    pipeline = Pipeline()
    pipeline.add_component('polish', DmpPolisherComponent(llm, cover_page_section_count=1))
    template = TemplateContent(sections=[
        TemplateSection(title='Cover'),
        TemplateSection(title='Body', sections=[TemplateSection(title='Child')]),
    ])

    await pipeline.run_async({'polish': {
        'markdown': '# Body', 'template_data': template, 'include_cover_page': True,
    }})

    assert llm.polish_dmp.await_args.kwargs['structure_str'] == '# Body\n## Child'
    assert len(template.sections) == 2
    assert template.sections[0].title == 'Cover'
