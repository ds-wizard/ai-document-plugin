import itertools
import logging
from collections.abc import Callable
from typing import Any, TypedDict

from haystack import component
from tqdm.contrib.concurrent import thread_map

from ai_document_plugin_service.ai.assignment.compatibility_utils import (
    convert_mappings_to_assignment_tree,
)
from ai_document_plugin_service.ai.assignment.llm import OpenAILayerMatcher
from ai_document_plugin_service.ai.assignment.question_tree import (
    build_question_chunks,
)
from ai_document_plugin_service.ai.assignment.section_tree import (
    build_section_records,
)
from ai_document_plugin_service.ai.assignment.sections.llm import (
    OpenAISectionIdGenerator,
)
from ai_document_plugin_service.ai.assignment.sections.sections_formatter import (
    SectionFormatter,
)
from ai_document_plugin_service.ai.assignment.types import SectionAssignment
from ai_document_plugin_service.ai.common.config import Config
from ai_document_plugin_service.ai.common.llm_client import LLMClient
from ai_document_plugin_service.ai.common.progress import progress_percent
from ai_document_plugin_service.ai.common.types import AssignmentStats
from ai_document_plugin_service.ai.knowledgemodel.types import QuestionData

logger = logging.getLogger(__name__)


class AssignmentComponentResult(TypedDict):
    assignments: list[SectionAssignment]
    stats: AssignmentStats


@component
class AssignmentComponent:
    """
    This component is responsible for assigning questions from the questionnaire to the sections from the dmp template.
    For example, it assigns question 'When will the project start?' to sections Introduction and Project Timeline
    """

    def __init__(self, llm_client: LLMClient, config: Config) -> None:
        self.llm_client = llm_client
        self.config = config
        self.section_id_generator = OpenAISectionIdGenerator(llm_client, config)
        self.section_matcher = OpenAILayerMatcher(self.llm_client, self.config)

    @staticmethod
    def _add_chunk_mapping_to_result(
        *,
        result_mapping: dict[str, list[str]],
        question_to_section_ids: dict[str, list[str]],
        question_id_to_path: dict[str, str],
        section_formatter: SectionFormatter,
    ) -> None:
        for question_id, section_ids in question_to_section_ids.items():
            question_path = question_id_to_path.get(question_id)
            if not question_path:
                logger.debug('Path not found for question id %s', question_id)
                continue
            result_mapping[question_path] = [section_formatter.record_id_for_sid(sid) for sid in section_ids]

    def _match_single_chunk(
        self,
        sections_xml: str,
        question_chunk: str,
        stats: AssignmentStats,
    ) -> dict[str, list[str]]:
        return self.section_matcher.match_questions_to_sections(
            sections_xml,
            question_chunk,
            stats,
        )

    @component.output_types(assignments=list[SectionAssignment], stats=AssignmentStats)
    def run(
        self,
        data: list[QuestionData],
        template_data: dict[str, Any],
        km: dict[str, Any],
        on_progress: Callable[[str], None] | None = None,
    ) -> AssignmentComponentResult:
        """Assign KM questions to template sections using the configured matcher."""
        logger.debug('Step 1: Assigning questions to sections...')

        sections = build_section_records(template_data)
        question_chunks, question_id_to_path = build_question_chunks(data)
        stats = AssignmentStats()

        section_formatter = SectionFormatter(sections)
        section_formatter.create_mappings(self.section_id_generator, stats)
        sections_xml = section_formatter.get_sections_as_xml()

        result_mapping = {}
        total_chunks = len(question_chunks)
        completed_counter = itertools.count(1)

        def match_chunk(question_chunk: str) -> dict[str, list[str]]:
            result = self._match_single_chunk(
                sections_xml=sections_xml,
                question_chunk=question_chunk,
                stats=stats,
            )
            if on_progress is not None:
                chunk_index = next(completed_counter)
                on_progress(
                    f'Preparing document template ({progress_percent(chunk_index, total_chunks)}%)',
                )
            return result

        for question_to_section_ids in thread_map(
            match_chunk,
            question_chunks,
            max_workers=self.llm_client.get_max_workers(),
            desc=f'Assigning questions to sections ({self.llm_client.get_max_workers()} workers)',
        ):
            self._add_chunk_mapping_to_result(
                result_mapping=result_mapping,
                question_to_section_ids=question_to_section_ids,
                question_id_to_path=question_id_to_path,
                section_formatter=section_formatter,
            )

        assignments = convert_mappings_to_assignment_tree(
            sections,
            result_mapping,
            km,
        )

        return {
            'assignments': assignments,
            'stats': stats,
        }
