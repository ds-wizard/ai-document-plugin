from datetime import date
from pathlib import Path

import yaml

from ai_document_plugin_service.cover_page.cover_page_renderer import CoverPageRenderer
from ai_document_plugin_service.cover_page.cover_page_resolvers import CoverDataSources

SERVICE_DIR = Path(__file__).resolve().parents[2]


def _renderer() -> CoverPageRenderer:
    raw_definition = yaml.safe_load((SERVICE_DIR / 'cover-page.yaml').read_text(encoding='utf-8'))
    return CoverPageRenderer(raw_definition)


def _sources() -> CoverDataSources:
    return CoverDataSources(
        questionnaire_detail={
            'name': 'Potato project',
            'phaseUuid': 'phase-1',
            'permissions': [
                {
                    'member': {'firstName': 'Hana', 'lastName': 'Litavská', 'type': 'UserMember'},
                    'perms': ['VIEW', 'COMMENT', 'EDIT', 'ADMIN'],
                },
            ],
            'knowledgeModelPackage': {
                'name': 'DSW Knowledge Model',
                'version': '1.2.0',
                'organizationId': 'dsw',
                'kmId': 'root',
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
                'name': 'Version 2',
                'updatedAt': '2018-02-21T00:00:00Z',
                'description': 'Latest version',
            },
            {
                'name': 'Version 1',
                'updatedAt': '2018-01-21T00:00:00Z',
                'description': 'First version',
            },
        ],
        generated_on=date(2026, 9, 1),
    )


def test_render_matches_current_cover_markdown() -> None:
    markdown = _renderer().render(_sources())

    assert markdown == (
        '# Data Management Plan\n'
        '\n'
        '| Metadata      | Details                                     |\n'
        '|:--------------|:--------------------------------------------|\n'
        '| Project Name  | Potato project                              |\n'
        '| Based On      | DSW Knowledge Model, 1.2.0 (dsw:root:1.2.0) |\n'
        '| Project Phase | Before Submitting the Proposal              |\n'
        '| Created By    | Hana Litavská                               |\n'
        '| Generated On  | 01.09.2026                                  |\n'
        '\n'
        'Data Management Plan created in Data Stewardship Wizard «ds-wizard.org» '
        'using AI document generation plugin\n'
        '\n'
        '## History of Changes\n'
        '\n'
        '| Version   | Date       | Changes        |\n'
        '|:----------|:-----------|:---------------|\n'
        '| Version 2 | 21.02.2018 | Latest version |\n'
        '| Version 1 | 21.01.2018 | First version  |'
    )


def test_render_keeps_english_labels_and_original_project_values() -> None:
    sources = _sources()
    assert sources.questionnaire_detail is not None
    sources.questionnaire_detail['name'] = 'Český projekt'
    markdown = _renderer().render(sources)

    assert '# Data Management Plan' in markdown
    assert 'Project Name' in markdown
    assert 'Český projekt' in markdown
    assert '## History of Changes' in markdown


def test_render_escapes_pipe_in_metadata_value() -> None:
    sources = _sources()
    assert sources.questionnaire_detail is not None
    sources.questionnaire_detail['name'] = 'Potato | project'

    markdown = _renderer().render(sources)

    assert 'Potato \\| project' in markdown
