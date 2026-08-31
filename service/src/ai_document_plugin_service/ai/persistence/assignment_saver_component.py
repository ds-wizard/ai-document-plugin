from __future__ import annotations

import asyncio
import json
import logging
import pathlib
import re
import typing
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, TypedDict

# UUID must be imported outside TYPE_CHECKING block for haystack to work
from uuid import UUID  # noqa: TC003

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
StatsJson = dict[str, dict[str, int | float]]


class AssignmentSaverComponentResult(TypedDict):
    assignments: list[SerializedSectionAssignment]
    stats: AssignmentStats | None


@component
class AssignmentSaverComponent:
    def __init__(self, saver: Saver) -> None:
        self.saver = saver

    @component.output_types(assignments=list[SerializedSectionAssignment], stats=AssignmentStats)
    async def run_async(
        self,
        knowledge_model_uuid: UUID,
        knowledge_model_name: str,
        knowledge_model_version: str,
        template_uuid: UUID,
        template_title: str,
        template_data: JsonValue,
        tenant_uuid: UUID,
        assignments: list[SectionAssignment],
        stats: AssignmentStats | None = None,
    ) -> AssignmentSaverComponentResult:
        """Save assignments to storage, optionally including token usage stats."""
        logger.info(
            'Persisting generated assignments',
            extra={
                'knowledge_model_uuid': knowledge_model_uuid,
                'knowledge_model_version': knowledge_model_version,
                'template_uuid': str(template_uuid),
                'template_title': template_title,
                'tenant_uuid': str(tenant_uuid),
                'assignment_count': len(assignments),
                'has_stats': stats is not None,
            },
        )
        serializable = [assignment.to_dict() for assignment in assignments]
        stats_payload = _serialize_stats(stats)

        await self.saver.save(
            knowledge_model_uuid=knowledge_model_uuid,
            knowledge_model_name=knowledge_model_name,
            knowledge_model_version=knowledge_model_version,
            assignments=serializable,
            stats=stats_payload,
            template_uuid=template_uuid,
            template_title=template_title,
            template_data=template_data,
            tenant_uuid=tenant_uuid,
            created_at=datetime.now(tz=UTC),
        )

        return {
            'assignments': serializable,
            'stats': stats,
        }

    @typing.override
    @component.output_types(assignments=list[SerializedSectionAssignment], stats=AssignmentStats)
    def run(
        self,
        knowledge_model_uuid: UUID,
        knowledge_model_name: str,
        knowledge_model_version: str,
        template_uuid: UUID,
        template_title: str,
        template_data: JsonValue,
        tenant_uuid: UUID,
        assignments: list[SectionAssignment],
        stats: AssignmentStats | None = None,
    ) -> AssignmentSaverComponentResult:
        """Async-only component; the sync pipeline entrypoint is intentionally unsupported."""
        msg = f'{type(self).__name__} is async-only; use run_async() / AsyncPipeline.run_async()'
        raise NotImplementedError(
            msg,
        )


class Saver(ABC):
    @abstractmethod
    async def save(
        self,
        knowledge_model_uuid: UUID,
        knowledge_model_name: str,
        knowledge_model_version: str,
        assignments: JsonValue,
        stats: StatsJson | None,
        template_uuid: UUID,
        template_title: str,
        template_data: JsonValue,
        tenant_uuid: UUID,
        created_at: datetime | None = None,
    ) -> None:
        """Persist assignments and their template."""


class FileSaver(Saver):
    async def save(
        self,
        knowledge_model_uuid: UUID,
        knowledge_model_name: str,
        knowledge_model_version: str,
        assignments: JsonValue,
        stats: StatsJson | None,
        template_uuid: UUID,
        template_title: str,
        template_data: JsonValue,
        tenant_uuid: UUID,
        created_at: datetime | None = None,
    ) -> None:
        _ = (template_uuid, template_title, template_data, tenant_uuid)
        output_name = self._build_filename(
            knowledge_model_uuid,
            knowledge_model_name,
            knowledge_model_version,
            created_at,
        )
        output_path = pathlib.Path(f'{output_name}.json')
        output_path_stats = pathlib.Path(f'{output_name}.stats.json')

        await asyncio.to_thread(
            output_path.write_text,
            json.dumps(assignments, indent=2, ensure_ascii=False),
            encoding='utf-8',
        )
        if stats is not None:
            await asyncio.to_thread(
                output_path_stats.write_text,
                json.dumps(stats, indent=2, ensure_ascii=False),
                encoding='utf-8',
            )
        logger.info(
            'Saved assignments to filesystem',
            extra={
                'output_path': str(output_path),
                'stats_output_path': str(output_path_stats) if stats is not None else None,
            },
        )

    @staticmethod
    def _build_filename(
        knowledge_model_uuid: UUID,
        knowledge_model_name: str,
        knowledge_model_version: str,
        created_at: datetime | None = None,
    ) -> str:
        normalized_uuid = _normalize_filename_part(str(knowledge_model_uuid))
        normalized_name = _normalize_filename_part(knowledge_model_name)
        normalized_version = _normalize_filename_part(knowledge_model_version)

        if created_at is not None:
            timestamp = created_at.strftime('%Y%m%d_%H%M%S')
            return f'{normalized_uuid}_{normalized_name}_{normalized_version}_{timestamp}'

        return f'{normalized_uuid}_{normalized_name}_{normalized_version}'


class DBSaver(Saver):
    def __init__(self, database: Database) -> None:
        self.database = database

    async def save(
        self,
        knowledge_model_uuid: UUID,
        knowledge_model_name: str,
        knowledge_model_version: str,
        assignments: JsonValue,
        stats: StatsJson | None,
        template_uuid: UUID,
        template_title: str,
        template_data: JsonValue,
        tenant_uuid: UUID,
        created_at: datetime | None = None,
    ) -> None:
        logger.debug(
            'Saving assignments through database-backed saver',
            extra={
                'knowledge_model_uuid': knowledge_model_uuid,
                'template_uuid': str(template_uuid),
                'tenant_uuid': str(tenant_uuid),
            },
        )
        await self.database.save_template(
            uuid=template_uuid,
            title=template_title,
            content=template_data,
            tenant_uuid=tenant_uuid,
        )
        await self.database.save_assignments(
            knowledge_model_uuid=knowledge_model_uuid,
            knowledge_model_name=knowledge_model_name,
            knowledge_model_version=knowledge_model_version,
            assignments=assignments,
            stats=stats,
            created_at=created_at,
            template_uuid=template_uuid,
        )
        logger.info(
            'Database-backed assignment save completed',
            extra={
                'knowledge_model_uuid': knowledge_model_uuid,
                'template_uuid': str(template_uuid),
                'tenant_uuid': str(tenant_uuid),
            },
        )


def _serialize_stats(stats: AssignmentStats | None) -> StatsJson | None:
    if stats is None:
        return None
    return {
        'stats': {
            'total_calls': stats.total_calls,
            'total_input_tokens': stats.total_input_tokens,
            'total_output_tokens': stats.total_output_tokens,
            'total_llm_wait_ms': stats.total_llm_wait_ms,
            'total_llm_response_ms': stats.total_llm_response_ms,
            'total_duration_ms': stats.total_duration_ms,
        },
    }


def _normalize_filename_part(value: str) -> str:
    normalized = re.sub(r'[^A-Za-z0-9._-]+', '_', value.strip())
    return normalized.strip('._') or 'document'
