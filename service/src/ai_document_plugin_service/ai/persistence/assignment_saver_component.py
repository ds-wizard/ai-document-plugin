from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import TYPE_CHECKING, TypedDict

# UUID must be imported outside TYPE_CHECKING block for haystack to work
from uuid import UUID  # ruff: ignore[typing-only-standard-library-import]

from haystack import component

from ai_document_plugin_service.ai.assignment.compatibility_utils import collect_leaf_question_paths
from ai_document_plugin_service.ai.assignment.types import (
    SectionAssignment,
    SectionQuestionPaths,
    SerializedSectionAssignment,
)

if TYPE_CHECKING:
    from ai_document_plugin_service.ai.persistence.database import Database

logger = logging.getLogger(__name__)


class AssignmentSaverComponentResult(TypedDict):
    assignments: list[SerializedSectionAssignment]


@component
class AssignmentSaverComponent:
    def __init__(self, saver: Saver) -> None:
        self.saver = saver

    @component.output_types(assignments=list[SerializedSectionAssignment])
    async def run_async(
        self,
        knowledge_model_uuid: UUID,
        knowledge_model_name: str,
        knowledge_model_version: str,
        template_uuid: UUID,
        tenant_uuid: UUID,
        assignments: list[SectionAssignment],
        *,
        has_new_assignments: bool = True,
    ) -> AssignmentSaverComponentResult:
        """Save assignments to storage.

        Skips the write when ``has_new_assignments`` is false: everything came from storage unchanged.
        """
        serializable = [assignment.to_dict() for assignment in assignments]
        if not has_new_assignments:
            logger.info(
                'Reusing stored assignments without saving',
                extra={'knowledge_model_uuid': knowledge_model_uuid, 'template_uuid': str(template_uuid)},
            )
            return {'assignments': serializable}

        logger.info(
            'Persisting generated assignments',
            extra={
                'knowledge_model_uuid': knowledge_model_uuid,
                'knowledge_model_version': knowledge_model_version,
                'template_uuid': str(template_uuid),
                'tenant_uuid': str(tenant_uuid),
                'assignment_count': len(assignments),
            },
        )
        question_paths = collect_leaf_question_paths(assignments)

        await self.saver.save(
            knowledge_model_uuid=knowledge_model_uuid,
            knowledge_model_name=knowledge_model_name,
            knowledge_model_version=knowledge_model_version,
            question_paths=question_paths,
            template_uuid=template_uuid,
            tenant_uuid=tenant_uuid,
            created_at=datetime.now(tz=UTC),
        )

        return {'assignments': serializable}

    @component.output_types(assignments=list[SerializedSectionAssignment])
    def run(
        self,
        knowledge_model_uuid: UUID,
        knowledge_model_name: str,
        knowledge_model_version: str,
        template_uuid: UUID,
        tenant_uuid: UUID,
        assignments: list[SectionAssignment],
        *,
        has_new_assignments: bool = True,
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
        question_paths: SectionQuestionPaths,
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
        question_paths: SectionQuestionPaths,
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
            question_paths=question_paths,
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

