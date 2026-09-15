from datetime import date
from pathlib import Path

import yaml

from ai_document_plugin_service.cover_page.renderer import CoverPageRenderer
from ai_document_plugin_service.cover_page.resolvers import CoverDataSources
from ai_document_plugin_service.cover_page.schema import CoverPageDefinition

SERVICE_DIR = Path(__file__).resolve().parents[2]


def _renderer() -> CoverPageRenderer:
    raw_definition = yaml.safe_load((SERVICE_DIR / 'cover-page.yaml').read_text(encoding='utf-8'))
    return CoverPageRenderer(CoverPageDefinition.model_validate(raw_definition))


def _sources() -> CoverDataSources:
    return CoverDataSources(
        questionnaire_detail={
            'name': 'Potato project',
            'phaseUuid': 'phase-1',
            'knowledgeModelPackage': {
                'name': 'DSW Knowledge Model',
                'version': '1.2.0',
            },
        },
        knowledge_model={
            'entities': {
                'phases': {
                    'phase-1': {'title': 'Before Submitting the Proposal'},
                },
            },
        },
        project_versions=[
            {
                'name': 'Version 1',
                'updatedAt': '2018-01-21T00:00:00Z',
                'description': 'First version',
            },
            {
                'name': 'Version 2',
                'updatedAt': '2018-02-21T00:00:00Z',
                'description': 'Latest version',
            },
        ],
        generated_on=date(2026, 9, 1),
    )


def test_render_matches_current_cover_markdown() -> None:
    markdown = _renderer().render(_sources())

    assert markdown == (
        '# Data Management Plan\n'
        '\n'
        '| Field | Value |\n'
        '| --- | --- |\n'
        '| Project Name | Potato project |\n'
        '| Based On | DSW Knowledge Model, 1.2.0 |\n'
        '| Project Phase | Before Submitting the Proposal |\n'
        '| Created By |  |\n'
        '| Generated On | 01.09.2026 |\n'
        '\n'
        'Data Management Plan created in Data Stewardship Wizard «ds-wizard.org» '
        'using AI document generation plugin\n'
        '\n'
        '## History of Changes\n'
        '\n'
        '| Version | Date | Changes |\n'
        '| --- | --- | --- |\n'
        '| Version 2 | 21.02.2018 | Latest version |\n'
        '| Version 1 | 21.01.2018 | First version |'
    )


def test_render_uses_translated_labels_without_changing_values() -> None:
    markdown = _renderer().render(
        _sources(),
        labels={
            'document_title': 'Plán správy dat',
            'project_name': 'Název projektu',
            'history_title': 'Historie změn',
        },
    )

    assert '# Plán správy dat' in markdown
    assert '| Název projektu | Potato project |' in markdown
    assert '## Historie změn' in markdown


def test_render_escapes_pipe_in_metadata_value() -> None:
    sources = _sources()
    assert sources.questionnaire_detail is not None
    sources.questionnaire_detail['name'] = 'Potato | project'

    markdown = _renderer().render(sources)

    assert '| Project Name | Potato \\| project |' in markdown
