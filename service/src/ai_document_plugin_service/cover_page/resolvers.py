from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from ai_document_plugin_service.cover_page.schema import CoverPageDefinition

type ResolvedCoverData = str | list[dict[str, Any]]


@dataclass(frozen=True)
class CoverDataSources:
    questionnaire_detail: dict[str, Any] | None
    knowledge_model: dict[str, Any]
    project_versions: list[dict[str, Any]]
    generated_on: date


type CoverDataResolver = Callable[[CoverDataSources], ResolvedCoverData]


def _project_name(sources: CoverDataSources) -> str:
    if sources.questionnaire_detail is None:
        return ''
    name = sources.questionnaire_detail.get('name')
    return name if isinstance(name, str) else ''


def _knowledge_model(sources: CoverDataSources) -> str:
    if sources.questionnaire_detail is None:
        return ''
    package = sources.questionnaire_detail.get('knowledgeModelPackage')
    if not isinstance(package, dict):
        return ''
    name = package.get('name')
    version = package.get('version')
    return ', '.join(value for value in (name, version) if isinstance(value, str) and value)


def _project_phase(sources: CoverDataSources) -> str:
    if sources.questionnaire_detail is None:
        return ''
    phase_uuid = sources.questionnaire_detail.get('phaseUuid')
    if not isinstance(phase_uuid, str) or not phase_uuid:
        return ''
    phases = sources.knowledge_model.get('entities', {}).get('phases', {})
    phase = phases.get(phase_uuid, {})
    title = phase.get('title')
    return title if isinstance(title, str) else ''


def _empty(_sources: CoverDataSources) -> str:
    return ''


def _generated_on(sources: CoverDataSources) -> str:
    return sources.generated_on.strftime('%d.%m.%Y')


def _project_versions(sources: CoverDataSources) -> list[dict[str, Any]]:
    def updated_at(version: dict[str, Any]) -> str:
        value = version.get('updatedAt')
        return value if isinstance(value, str) else ''

    return sorted(sources.project_versions, key=updated_at, reverse=True)


COVER_DATA_RESOLVERS: dict[str, CoverDataResolver] = {
    'questionnaire.project_name': _project_name,
    'questionnaire.knowledge_model': _knowledge_model,
    'questionnaire.project_phase': _project_phase,
    'static.empty': _empty,
    'system.generated_on': _generated_on,
    'project.versions': _project_versions,
}


def resolve_cover_data(resolver_id: str, sources: CoverDataSources) -> ResolvedCoverData:
    try:
        resolver = COVER_DATA_RESOLVERS[resolver_id]
    except KeyError as error:
        msg = f"Unknown cover data resolver: '{resolver_id}'"
        raise ValueError(msg) from error
    return resolver(sources)


def validate_cover_data_resolvers(definition: CoverPageDefinition) -> None:
    configured_resolvers = {
        *(field.resolver for field in definition.metadata.fields),
        definition.history.resolver,
    }
    unknown_resolvers = configured_resolvers - COVER_DATA_RESOLVERS.keys()
    if unknown_resolvers:
        names = ', '.join(sorted(unknown_resolvers))
        msg = f'Unknown cover data resolvers: {names}'
        raise ValueError(msg)
