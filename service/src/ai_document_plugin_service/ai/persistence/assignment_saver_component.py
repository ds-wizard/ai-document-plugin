from __future__ import annotations

import json
import logging
import pathlib
import re
import typing
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, TypedDict

from haystack import component

from ai_document_plugin_service.ai.assignment.types import (
    SectionAssignment,
    SerializedSectionAssignment,
)
from ai_document_plugin_service.ai.common.types import AssignmentStats

if TYPE_CHECKING:
    from ai_document_plugin_service.ai.persistence.database import Database

logger = logging.getLogger(__name__)

JsonValue = Mapping[str, object] | Sequence[object]
StatsJson = dict[str, dict[str, int]]


class AssignmentSaverComponentResult(TypedDict):
    assignments: list[SerializedSectionAssignment]
    stats: AssignmentStats | None


@component
class AssignmentSaverComponent:
    def __init__(self, saver: Saver) -> None:
        self.saver = saver

    @typing.override
    @component.output_types(assignments=list[SerializedSectionAssignment], stats=AssignmentStats)
    def run(
        self,
        knowledge_model_uuid: str,
        knowledge_model_name: str,
        knowledge_model_version: str,
        template_uuid: str,
        template_title: str,
        template_data: JsonValue,
        assignments: list[SectionAssignment],
        stats: AssignmentStats | None = None,
    ) -> AssignmentSaverComponentResult:
        """Save assignments to storage, optionally including token usage stats."""
        serializable = [assignment.to_dict() for assignment in assignments]
        stats_payload = _serialize_stats(stats)

        self.saver.save(
            knowledge_model_uuid=knowledge_model_uuid,
            knowledge_model_name=knowledge_model_name,
            knowledge_model_version=knowledge_model_version,
            assignments=serializable,
            stats=stats_payload,
            template_uuid=template_uuid,
            template_title=template_title,
            template_data=template_data,
            created_at=datetime.now(tz=UTC),
        )

        return {
            'assignments': serializable,
            'stats': stats,
        }


class Saver(ABC):
    @abstractmethod
    def save(
        self,
        knowledge_model_uuid: str,
        knowledge_model_name: str,
        knowledge_model_version: str,
        assignments: JsonValue,
        stats: StatsJson | None,
        template_uuid: str,
        template_title: str,
        template_data: JsonValue,
        created_at: datetime | None = None,
    ) -> None:
        """Persist assignments and their template."""


class FileSaver(Saver):
    def save(
        self,
        knowledge_model_uuid: str,
        knowledge_model_name: str,
        knowledge_model_version: str,
        assignments: JsonValue,
        stats: StatsJson | None,
        template_uuid: str,
        template_title: str,
        template_data: JsonValue,
        created_at: datetime | None = None,
    ) -> None:
        _ = (template_uuid, template_title, template_data)
        output_name = self._build_filename(
            knowledge_model_uuid,
            knowledge_model_name,
            knowledge_model_version,
            created_at,
        )
        output_path = pathlib.Path(f'{output_name}.json')
        output_path_stats = pathlib.Path(f'{output_name}.stats.json')

        output_path.write_text(
            json.dumps(assignments, indent=2, ensure_ascii=False),
            encoding='utf-8',
        )
        if stats is not None:
            output_path_stats.write_text(
                json.dumps(stats, indent=2, ensure_ascii=False),
                encoding='utf-8',
            )
        logger.debug('Saved assignments to %s', output_path)

    @staticmethod
    def _build_filename(
        knowledge_model_uuid: str,
        knowledge_model_name: str,
        knowledge_model_version: str,
        created_at: datetime | None = None,
    ) -> str:
        normalized_uuid = _normalize_filename_part(knowledge_model_uuid)
        normalized_name = _normalize_filename_part(knowledge_model_name)
        normalized_version = _normalize_filename_part(knowledge_model_version)

        if created_at is not None:
            timestamp = created_at.strftime('%Y%m%d_%H%M%S')
            return f'{normalized_uuid}_{normalized_name}_{normalized_version}_{timestamp}'

        return f'{normalized_uuid}_{normalized_name}_{normalized_version}'


class DBSaver(Saver):
    def __init__(self, database: Database) -> None:
        self.database = database

    def save(
        self,
        knowledge_model_uuid: str,
        knowledge_model_name: str,
        knowledge_model_version: str,
        assignments: JsonValue,
        stats: StatsJson | None,
        template_uuid: str,
        template_title: str,
        template_data: JsonValue,
        created_at: datetime | None = None,
    ) -> None:
        self.database.save_template(
            uuid=template_uuid,
            title=template_title,
            content=template_data,
        )
        self.database.save_assignments(
            knowledge_model_uuid=knowledge_model_uuid,
            knowledge_model_name=knowledge_model_name,
            knowledge_model_version=knowledge_model_version,
            assignments=assignments,
            stats=stats,
            created_at=created_at,
            template_uuid=template_uuid,
        )


def _serialize_stats(stats: AssignmentStats | None) -> StatsJson | None:
    if stats is None:
        return None
    return {
        'stats': {
            'total_calls': stats.total_calls,
            'total_input_tokens': stats.total_input_tokens,
            'total_output_tokens': stats.total_output_tokens,
        },
    }


def _normalize_filename_part(value: str) -> str:
    normalized = re.sub(r'[^A-Za-z0-9._-]+', '_', value.strip())
    return normalized.strip('._') or 'document'
