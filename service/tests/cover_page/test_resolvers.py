from datetime import date
from pathlib import Path

import pytest
import yaml

from ai_document_plugin_service.cover_page.resolvers import (
    COVER_DATA_RESOLVERS,
    CoverDataSources,
    resolve_cover_data,
    validate_cover_data_resolvers,
)
from ai_document_plugin_service.cover_page.schema import CoverPageDefinition

SERVICE_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture
def sources() -> CoverDataSources:
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
            {'name': 'Version 1', 'updatedAt': '2018-01-21T00:00:00Z'},
            {'name': 'Version 2', 'updatedAt': '2018-02-21T00:00:00Z'},
        ],
        generated_on=date(2026, 9, 1),
    )


def test_registry_resolves_current_cover_data(sources: CoverDataSources) -> None:
    assert resolve_cover_data('questionnaire.project_name', sources) == 'Potato project'
    assert resolve_cover_data('questionnaire.knowledge_model', sources) == 'DSW Knowledge Model, 1.2.0'
    assert resolve_cover_data('questionnaire.project_phase', sources) == 'Before Submitting the Proposal'
    assert resolve_cover_data('static.empty', sources) == ''
    assert resolve_cover_data('system.generated_on', sources) == '01.09.2026'
    assert resolve_cover_data('project.versions', sources) == [
        {'name': 'Version 2', 'updatedAt': '2018-02-21T00:00:00Z'},
        {'name': 'Version 1', 'updatedAt': '2018-01-21T00:00:00Z'},
    ]


def test_questionnaire_resolvers_return_empty_values_for_missing_data() -> None:
    sources = CoverDataSources(
        questionnaire_detail=None,
        knowledge_model={},
        project_versions=[],
        generated_on=date(2026, 9, 1),
    )

    assert resolve_cover_data('questionnaire.project_name', sources) == ''
    assert resolve_cover_data('questionnaire.knowledge_model', sources) == ''
    assert resolve_cover_data('questionnaire.project_phase', sources) == ''
    assert resolve_cover_data('project.versions', sources) == []


def test_unknown_resolver_is_rejected(sources: CoverDataSources) -> None:
    with pytest.raises(ValueError, match="Unknown cover data resolver: 'unknown.value'"):
        resolve_cover_data('unknown.value', sources)


def test_default_cover_definition_only_uses_registered_resolvers() -> None:
    raw_definition = yaml.safe_load((SERVICE_DIR / 'cover-page.yaml').read_text(encoding='utf-8'))
    definition = CoverPageDefinition.model_validate(raw_definition)

    validate_cover_data_resolvers(definition)

    configured_resolvers = {
        *(field.resolver for field in definition.metadata.fields),
        definition.history.resolver,
    }
    assert configured_resolvers <= COVER_DATA_RESOLVERS.keys()
