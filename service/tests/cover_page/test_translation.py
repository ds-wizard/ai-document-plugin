from pathlib import Path

import yaml

from ai_document_plugin_service.ai.generation.header_translation import cover_translation_labels
from ai_document_plugin_service.cover_page.schema import CoverPageDefinition

SERVICE_DIR = Path(__file__).resolve().parents[2]


def test_builds_translation_labels_from_cover_definition() -> None:
    raw_definition = yaml.safe_load((SERVICE_DIR / 'cover-page.yaml').read_text(encoding='utf-8'))
    definition = CoverPageDefinition.model_validate(raw_definition)

    assert cover_translation_labels(definition) == {
        'document_title': 'Data Management Plan',
        'field': 'Field',
        'value': 'Value',
        'project_name': 'Project Name',
        'based_on': 'Based On',
        'project_phase': 'Project Phase',
        'created_by': 'Created By',
        'generated_on': 'Generated On',
        'history_title': 'History of Changes',
        'version': 'Version',
        'date': 'Date',
        'changes': 'Changes',
        'project_title': 'Project title',
        'project_acronym': 'Project acronym',
        'project_code': 'Project number/code',
        'funding': 'Funding',
        'project_duration': 'Project duration',
        'project_abstract': 'Project abstract',
    }
