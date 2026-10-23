import asyncio
import itertools
import logging
import time
from collections.abc import Callable
from typing import Any, TypedDict
from uuid import UUID

from haystack import component

from ai_document_plugin_service.ai.assignment.compatibility_utils import (
    convert_mappings_to_assignment_tree_recursive,
)
from ai_document_plugin_service.ai.assignment.llm import OpenAILayerMatcher
from ai_document_plugin_service.ai.assignment.mappers import template_sections_to_records
from ai_document_plugin_service.ai.assignment.question_tree import (
    build_question_chunks,
)
from ai_document_plugin_service.ai.assignment.section_tree import collect_leaf_sections
from ai_document_plugin_service.ai.assignment.sections.sections_formatter import (
    SectionFormatter,
)
from ai_document_plugin_service.ai.assignment.types import SectionAssignment, SectionQuestionPaths
from ai_document_plugin_service.ai.common.config import Config
from ai_document_plugin_service.ai.common.llm_client import LLMClient
from ai_document_plugin_service.ai.common.progress import progress_percent
from ai_document_plugin_service.ai.common.types import AssignmentStats, TemplateContent
from ai_document_plugin_service.ai.knowledgemodel.types import QuestionData

logger = logging.getLogger(__name__)


class AssignmentComponentResult(TypedDict):
    assignments: list[SectionAssignment]
    # None when every section was stored and no LLM call was made.
    stats: AssignmentStats | None
    has_new_assignments: bool


@component
class AssignmentComponent:
    """
    This component is responsible for assigning questions from the questionnaire to the sections from the dmp template.
    For example, it assigns question 'When will the project start?' to sections Introduction and Project Timeline
    """

    def __init__(self, llm_client: LLMClient, config: Config) -> None:
        self.llm_client = llm_client
        self.config = config
        self.section_matcher = OpenAILayerMatcher(self.llm_client, self.config)

    @staticmethod
    def _add_chunk_mapping_to_result(
        *,
        result_mapping: dict[str, list[UUID]],
        question_to_section_ids: dict[str, list[str]],
        question_id_to_path: dict[str, str],
        section_formatter: SectionFormatter,
    ) -> None:
        for question_id, section_ids in question_to_section_ids.items():
            question_path = question_id_to_path.get(question_id)
            if not question_path:
                logger.debug('Path not found for question id %s', question_id)
                continue
            record_ids = [section_formatter.record_id_for_sid(sid) for sid in section_ids]
            result_mapping[question_path] = [record_id for record_id in record_ids if record_id is not None]

    @component.output_types(assignments=list[SectionAssignment], stats=AssignmentStats | None, has_new_assignments=bool)
    async def run_async(
        self,
        data: list[QuestionData],
        template_data: TemplateContent,
        km: dict[str, Any],
        on_progress: Callable[[str], None] | None = None,
        stored_question_paths: SectionQuestionPaths | None = None,
    ) -> AssignmentComponentResult:
        """Assign questions to the leaf sections missing from ``stored_question_paths`` and merge in the stored ones."""
        started = time.perf_counter()
        logger.debug('Step 1: Assigning questions to sections...')

        # Simple type remapping
        sections = template_sections_to_records(template_data.sections)
        leaf_ids = {leaf.id for leaf in collect_leaf_sections(sections)}
        # Stored sections that were edited or removed since are dropped here, and so on the next save.
        stored = {
            section_id: paths for section_id, paths in (stored_question_paths or {}).items() if section_id in leaf_ids
        }
        missing_ids = leaf_ids - stored.keys()
        # Separate the KM into chunks of given length to avoid overflowing the LLM context and allow parallelization
        question_chunks, question_id_to_path = build_question_chunks(data)
        if not missing_ids:
            question_chunks = []
        logger.info(
            'Starting question-to-section assignment',
            extra={
                'section_count': len(sections),
                'stored_section_count': len(stored),
                'missing_section_count': len(missing_ids),
                'question_chunk_count': len(question_chunks),
                'question_path_count': len(question_id_to_path),
            },
        )
        stats = AssignmentStats()

        # All sections stay in the prompt for context, but only the missing ones get an id the LLM can answer with.
        section_formatter = SectionFormatter(sections, assignable_ids=missing_ids)
        sections_xml = section_formatter.get_sections_as_xml()

        result_mapping: dict[str, list[UUID]] = {}
        total_chunks = len(question_chunks)
        completed_counter = itertools.count(1)
        worker_count = self.llm_client.get_max_workers()
        chunk_semaphore = asyncio.Semaphore(worker_count)

        async def match_chunk(question_chunk: str) -> dict[str, list[str]]:
            async with chunk_semaphore:
                result = await self.section_matcher.match_questions_to_sections(
                    sections_xml,
                    question_chunk,
                    stats,
                )
            if on_progress is not None:
                chunk_index = next(completed_counter)
                on_progress(
                    f'Preparing document template ({progress_percent(chunk_index, total_chunks)}%)',
                )
            return result

        # TaskGroup cancels unfinished chunks on failure/cancellation and awaits their cleanup.
        async with asyncio.TaskGroup() as group:
            tasks = [group.create_task(match_chunk(chunk)) for chunk in question_chunks]
        for task in tasks:
            question_to_section_ids = task.result()
            self._add_chunk_mapping_to_result(
                result_mapping=result_mapping,
                question_to_section_ids=question_to_section_ids,
                question_id_to_path=question_id_to_path,
                section_formatter=section_formatter,
            )

        section_id_to_paths = {section_id: list(paths) for section_id, paths in stored.items()}
        # clear missing section ids because they will be added in the next step
        section_id_to_paths.update({section_id: [] for section_id in missing_ids})
        # add in missing section ids here:
        for path, section_ids in result_mapping.items():
            for section_id in section_ids:
                section_id_to_paths[section_id].append(path)
        assignments = convert_mappings_to_assignment_tree_recursive(sections, section_id_to_paths, km)
        logger.info(
            'Completed question-to-section assignment',
            extra={
                'assignment_count': len(assignments),
                'mapped_question_count': len(result_mapping),
                'llm_call_count': stats.total_calls,
            },
        )
        stats.set_duration_ms(round((time.perf_counter() - started) * 1000, 3))

        return {
            'assignments': assignments,
            'stats': stats if missing_ids else None,
            'has_new_assignments': bool(missing_ids),
        }

    @component.output_types(assignments=list[SectionAssignment], stats=AssignmentStats | None, has_new_assignments=bool)
    def run(
        self,
        data: list[QuestionData],
        template_data: TemplateContent,
        km: dict[str, Any],
        on_progress: Callable[[str], None] | None = None,
        stored_question_paths: SectionQuestionPaths | None = None,
    ) -> AssignmentComponentResult:
        """Async-only component; the sync pipeline entrypoint is intentionally unsupported."""
        msg = f'{type(self).__name__} is async-only; use run_async() / Pipeline.run_async()'
        raise NotImplementedError(
            msg,
        )
