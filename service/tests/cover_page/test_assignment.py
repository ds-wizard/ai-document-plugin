from pathlib import Path

import yaml

from ai_document_plugin_service.ai.assignment.projects_section import build_header_assignment_template
from ai_document_plugin_service.cover_page.schema import CoverPageDefinition

SERVICE_DIR = Path(__file__).resolve().parents[2]


def test_builds_assignment_template_from_cover_definition() -> None:
    raw_definition = yaml.safe_load((SERVICE_DIR / 'cover-page.yaml').read_text(encoding='utf-8'))
    definition = CoverPageDefinition.model_validate(raw_definition)

    assert build_header_assignment_template(definition) == {
        'sections': [
            {
                'title': 'Projects',
                'content': (
                    'Summarize project details from the questionnaire: project title, project acronym, '
                    'project number or code, funding, project duration, and project abstract. '
                    'Use only answers supplied by the questionnaire.'
                ),
            },
        ],
    }
