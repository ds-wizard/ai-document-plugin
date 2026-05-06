import logging
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
from ai_document_plugin_service.ai.common.types import AssignmentStats
from ai_document_plugin_service.ai.knowledgemodel.types import QuestionData

logger = logging.getLogger(__name__)


class AssignmentComponentResult(TypedDict):
    assignments: list[SectionAssignment]
    stats: AssignmentStats


@component
class AssignmentComponent:
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

    @staticmethod
    def _match_single_chunk(
        *,
        config: Config,
        sections_xml: str,
        question_chunk: str,
        stats: AssignmentStats,
    ) -> dict[str, list[str]]:
        matcher = OpenAILayerMatcher(config)
        return matcher.match_questions_to_sections(
            sections_xml,
            question_chunk,
            stats,
        )

    @component.output_types(assignments=list[SectionAssignment], stats=AssignmentStats)
    def run(
        self,
        data: list[QuestionData],
        template_data: dict[str, Any],
        config: Config,
        km: dict[str, Any],
    ) -> AssignmentComponentResult:
        """Assign KM questions to template sections using the configured matcher."""
        logger.debug('Step 1: Assigning questions to sections...')

        sections = build_section_records(template_data)
        question_chunks, question_id_to_path = build_question_chunks(data)
        stats = AssignmentStats()

        section_formatter = SectionFormatter(sections)
        section_formatter.create_mappings(OpenAISectionIdGenerator(config), stats)
        sections_xml = section_formatter.get_sections_as_xml()

        result_mapping = {}

        def match_chunk(question_chunk: str) -> dict[str, list[str]]:
            return self._match_single_chunk(
                config=config,
                sections_xml=sections_xml,
                question_chunk=question_chunk,
                stats=stats,
            )

        for question_to_section_ids in thread_map(
            match_chunk,
            question_chunks,
            max_workers=config.parallel_workers,
            desc=f'Assigning questions to sections ({config.parallel_workers} workers)',
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
