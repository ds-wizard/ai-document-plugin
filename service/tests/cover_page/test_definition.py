from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from ai_document_plugin_service.cover_page.schema import CoverPageDefinition

SERVICE_DIR = Path(__file__).resolve().parents[2]
COVER_DEFINITION_PATH = SERVICE_DIR / 'cover-page.yaml'


def _raw_definition() -> dict:
    raw = yaml.safe_load(COVER_DEFINITION_PATH.read_text(encoding='utf-8'))
    assert isinstance(raw, dict)
    return raw


def test_loads_current_cover_definition() -> None:
    definition = CoverPageDefinition.model_validate(_raw_definition())

    assert definition.version == '1'
    assert definition.metadata.title.text == 'Data Management Plan'
    assert [field.id for field in definition.metadata.fields] == [
        'project_name',
        'based_on',
        'project_phase',
        'created_by',
        'generated_on',
    ]
    assert [column.value_key for column in definition.history.columns] == [
        'name',
        'updatedAt',
        'description',
    ]
    assert [field.id for field in definition.assigned_sections[0].fields] == [
        'project_title',
        'project_acronym',
        'project_code',
        'funding',
        'project_duration',
        'project_abstract',
    ]


def test_rejects_unknown_properties() -> None:
    raw = _raw_definition()
    raw['unexpected'] = True

    with pytest.raises(ValidationError, match='Extra inputs are not permitted'):
        CoverPageDefinition.model_validate(raw)


def test_rejects_duplicate_translatable_label_ids() -> None:
    raw = _raw_definition()
    raw['history']['title']['id'] = raw['metadata']['title']['id']

    with pytest.raises(ValidationError, match='duplicate translatable label IDs'):
        CoverPageDefinition.model_validate(raw)


def test_rejects_missing_assignment_heading_field() -> None:
    raw = _raw_definition()
    raw['assigned_sections'][0]['item_heading_field'] = 'missing_field'

    with pytest.raises(ValidationError, match='references missing heading field'):
        CoverPageDefinition.model_validate(raw)
