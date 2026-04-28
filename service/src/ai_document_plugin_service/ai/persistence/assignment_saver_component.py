import json
import logging
import os
import re
import typing
import uuid
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, TypedDict

from haystack import component

from ai_document_plugin_service.ai.assignment.types import SectionAssignment
from ai_document_plugin_service.ai.common.config import DatabaseConfig
from ai_document_plugin_service.ai.common.types import AssignmentStats
from ai_document_plugin_service.ai.persistence.database import Database, PostgresDB

logger = logging.getLogger(__name__)

JsonValue = Mapping[str, Any] | Sequence[Any]


class AssignmentSaverComponentResult(TypedDict):
    assignments: list[SectionAssignment]
    stats: AssignmentStats | None


@component
class AssignmentSaverComponent:
    @typing.override
    @component.output_types(assignments=JsonValue, stats=AssignmentStats)
    def run(
        self,
        saver: Saver,
        knowledge_model_uuid: uuid.UUID,
        knowledge_model_name: str,
        knowledge_model_version: str,
        template_uuid: str,
        template_title: str,
        template_data: JsonValue,
        assignments: list[SectionAssignment],
        stats: AssignmentStats | None = None,
    ) -> AssignmentSaverComponentResult:
        """Save assignments to JSON, optionally including token usage stats."""
        serializable = [assignment.to_dict() for assignment in assignments]

        if stats is not None:
            stats = {
                'stats': {
                    'total_calls': stats.total_calls,
                    'total_input_tokens': stats.total_input_tokens,
                    'total_output_tokens': stats.total_output_tokens,
                },
            }

        saver.save(
            knowledge_model_uuid=knowledge_model_uuid,
            knowledge_model_name=knowledge_model_name,
            knowledge_model_version=knowledge_model_version,
            assignments=serializable,
            stats=stats,
            template_uuid=template_uuid,
            template_title=template_title,
            template_data=template_data,
            created_at=datetime.now(),
        )

        assignments = [a.to_dict() for a in assignments]

        return {
            'assignments': assignments,
            'stats': stats,
        }


class Saver(ABC):
    @abstractmethod
    def save(
        self,
        knowledge_model_uuid: uuid.UUID,
        knowledge_model_name: str,
        knowledge_model_version: str,
        assignments: JsonValue,
        stats: AssignmentStats,
        template_uuid: str,
        template_title: str,
        template_data: JsonValue,
        created_at: datetime | None = None,
    ) -> None:
        """Persist assignments and their template."""


class FileSaver(Saver):
    def save(
        self,
        knowledge_model_uuid: uuid.UUID,
        knowledge_model_name: str,
        knowledge_model_version: str,
        assignments: JsonValue,
        stats: JsonValue,
        template_uuid: str,
        template_title: str,
        template_data: JsonValue,
        created_at: datetime | None = None,
    ) -> None:
        output_name = self._build_filename(knowledge_model_uuid, knowledge_model_name, knowledge_model_version, created_at)
        output_path = output_name + '.json'
        output_path_stats = output_name + '.stats.json'

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(
                json.dumps(assignments, indent=2, ensure_ascii=False),
            )
        if stats is not None:
            with open(output_path_stats, 'w', encoding='utf-8') as f:
                f.write(
                    json.dumps(stats, indent=2, ensure_ascii=False),
                )
        logger.debug('Saved assignments to %s', output_path)

    def _build_filename(
        self,
        knowledge_model_uuid: uuid.UUID,
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
        knowledge_model_uuid: uuid.UUID,
        knowledge_model_name: str,
        knowledge_model_version: str,
        assignments: JsonValue,
        stats: JsonValue,
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


def _normalize_filename_part(value: str) -> str:
    normalized = re.sub(r'[^A-Za-z0-9._-]+', '_', value.strip())
    return normalized.strip('._') or 'document'
