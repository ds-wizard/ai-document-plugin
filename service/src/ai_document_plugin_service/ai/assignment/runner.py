import json
import logging
from typing import Any

from tqdm import tqdm

from ai.assignment.compatibility_utils import convert_mappings_to_assignment_tree
from ai.assignment.io import save_assignments
from ai.assignment.llm import OpenAILayerMatcher
from ai.assignment.question_tree import build_question_chunks
from ai.assignment.section_tree import (
    build_section_records,
)
from ai.assignment.sections.llm import OpenAISectionIdGenerator
from ai.assignment.sections.sections_formatter import SectionFormatter
from ai.assignment.types import SectionAssignment
from ai.common.config import Config, load_config
from ai.common.types import AssignmentStats
from ai.knowledgemodel.parse_types import parse_questionnaire
from ai.knowledgemodel.types import QuestionData

logger = logging.getLogger(__name__)


def run_assignment(
        template_data: dict[str, Any],
        top_questions: list[QuestionData],
        config: Config,
        km: dict[str, Any],
) -> tuple[list[SectionAssignment], AssignmentStats]:
    """Assign KM questions to template sections using the configured matcher."""
    sections = build_section_records(template_data)
    question_chunks, question_id_to_path = build_question_chunks(top_questions)
    matcher = OpenAILayerMatcher(config)
    stats = AssignmentStats()

    section_formatter = SectionFormatter(sections)
    section_formatter.create_mappings(OpenAISectionIdGenerator(config), stats)
    sections_xml = section_formatter.get_sections_as_xml()

    result_mapping = {}
    for question_chunk in tqdm(question_chunks, desc="Question chunks"):
        question_to_section_ids = matcher.match_questions_to_sections(
            sections_xml,
            question_chunk,
            stats
        )

        for question_id, section_ids in question_to_section_ids.items():
            question_path = question_id_to_path.get(question_id)
            if not question_path:
                logger.debug("Path not found for question id %s", question_id)
                continue
            result_mapping[question_path] = [
                section_formatter.get_original_id(section_id) for section_id in section_ids
            ]

    assignments = convert_mappings_to_assignment_tree(sections, result_mapping, km)
    return assignments, stats


def main() -> None:
    config = load_config()
    file_paths = config.files

    with open(file_paths.dmp_template, "r", encoding="utf-8") as f:
        template_data = json.load(f)
    with open(file_paths.knowledge_model, "r", encoding="utf-8") as f:
        km_data = json.load(f)

    top_questions = parse_questionnaire(km_data)
    assignments, stats = run_assignment(
        template_data,
        top_questions,
        config,
        km_data["knowledgeModel"],
    )
    save_assignments(assignments, file_paths.assignments_output, stats=stats)

    logger.debug("Saved assignments to %s", file_paths.assignments_output)
    logger.debug("Total LLM calls: %s", stats.total_calls)
    logger.debug("Total input tokens: %s", f"{stats.total_input_tokens:,}")
    logger.debug("Total output tokens: %s", f"{stats.total_output_tokens:,}")

    cost_per_mil_input = 0.25
    cost_per_mil_output = 2.0
    model_name = config.model
    input_cost = stats.total_input_tokens * cost_per_mil_input / 1_000_000
    output_cost = stats.total_output_tokens * cost_per_mil_output / 1_000_000
    logger.debug("Estimated price (model %s):", model_name)
    logger.debug("Input: %.2f USD", input_cost)
    logger.debug("Output: %.2f USD", output_cost)
    logger.debug("Total: %.2f USD", input_cost + output_cost)


if __name__ == "__main__":
    main()
