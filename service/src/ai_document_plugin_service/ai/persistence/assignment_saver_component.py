from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import TYPE_CHECKING, TypedDict

# UUID must be imported outside TYPE_CHECKING block for haystack to work
from uuid import UUID  # ruff: ignore[typing-only-standard-library-import]

from haystack import component

from ai_document_plugin_service.ai.assignment.types import (
    SectionAssignment,
    SerializedSectionAssignment,
)

# Haystack inspects component input annotations at runtime.
from ai_document_plugin_service.ai.common.types import AssignmentStats

if TYPE_CHECKING:
    from ai_document_plugin_service.ai.persistence.database import Database

logger = logging.getLogger(__name__)

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
            tenant_uuid=tenant_uuid,
            created_at=datetime.now(tz=UTC),
        )

        return {
            'assignments': serializable,
            'stats': stats,
        }

    @component.output_types(assignments=list[SerializedSectionAssignment], stats=AssignmentStats)
    def run(
        self,
        knowledge_model_uuid: UUID,
        knowledge_model_name: str,
        knowledge_model_version: str,
        template_uuid: UUID,
        tenant_uuid: UUID,
        assignments: list[SectionAssignment],
        stats: AssignmentStats | None = None,
    ) -> AssignmentSaverComponentResult:
        """Async-only component; the sync pipeline entrypoint is intentionally unsupported."""
        msg = f'{type(self).__name__} is async-only; use run_async() / Pipeline.run_async()'
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
        assignments: list[SerializedSectionAssignment],
        stats: StatsJson | None,
        template_uuid: UUID,
        tenant_uuid: UUID,
        created_at: datetime | None = None,
    ) -> None:
        """Persist assignments."""


class DBSaver(Saver):
    def __init__(self, database: Database) -> None:
        self.database = database

    async def save(
        self,
        knowledge_model_uuid: UUID,
        knowledge_model_name: str,
        knowledge_model_version: str,
        assignments: list[SerializedSectionAssignment],
        stats: StatsJson | None,
        template_uuid: UUID,
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
