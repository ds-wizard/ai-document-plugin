import logging
from typing import Any

from ai_document_plugin_service.ai.assignment.types import (
    AssignmentQuestionNode,
    AssignmentTree,
    SectionAssignment,
    SectionQuestionPaths,
    SectionRecord,
)

logger = logging.getLogger(__name__)


def convert_mappings_to_assignment_tree_recursive(
    sections: list[SectionRecord],
    section_id_to_paths: SectionQuestionPaths,
    km: dict[str, Any],
) -> list[SectionAssignment]:
    """Convert flat leaf assignments into the section hierarchy."""
    result: list[SectionAssignment] = []
    for section in sections:
        if section.children is not None:
            result.append(
                SectionAssignment(
                    id=section.id,
                    title=section.title,
                    assignments=None,
                    children=convert_mappings_to_assignment_tree_recursive(
                        section.children,
                        section_id_to_paths,
                        km,
                    ),
                ),
            )
            continue
        question_flags = section_id_to_paths.get(section.id, [])
        result.append(
            SectionAssignment(
                id=section.id,
                title=section.title,
                assignments=expand_assignment_paths(question_flags, km),
                children=None,
                question_paths=question_flags,
            ),
        )
    return result


def collect_leaf_question_paths(assignments: list[SectionAssignment]) -> SectionQuestionPaths:
    """Return the question paths of every leaf section by section id.

    Identical leaves share an id and were assigned together, so they collapse into one entry.
    """
    paths: SectionQuestionPaths = {}
    for assignment in assignments:
        if assignment.children is not None:
            paths.update(collect_leaf_question_paths(assignment.children))
            continue
        paths[assignment.id] = assignment.question_paths or []
    return paths


def _path_exists_in_km(segments: list[str], km: dict[str, Any]) -> bool:
    entities = km['entities']
    last_index = len(segments) - 1
    for index, segment in enumerate(segments):
        if segment == '*':
            continue
        if index == 0:
            found = segment in entities['chapters']
        else:
            found = segment in entities['questions'] or (index < last_index and segment in entities['answers'])
        if not found:
            return False
    return True


def expand_assignment_paths(
    mappings: list[str],
    km: dict[str, Any],
) -> AssignmentTree:
    """Decompose flat dot-separated assignment paths into nested question nodes.

    This preserves the previous hierarchical output shape consumed by downstream steps.
    Paths not found in the KM are skipped with a warning, because stored assignments are shared
    between projects whose KMs can differ.
    """
    root: AssignmentTree = {}
    km_questions = km['entities']['questions']
    km_chapters = km['entities']['chapters']

    for path in mappings:
        segments = path.split('.')
        if not _path_exists_in_km(segments, km):
            logger.warning('Skipping assignment path not found in the knowledge model', extra={'question_path': path})
            continue
        current = root
        prefix_parts: list[str] = []

        for i, segment in enumerate(segments):
            prefix_parts.append(segment)
            if segment == '*':
                continue
            is_leaf = i == len(segments) - 1

            if segment not in current:
                full_path = '.'.join(prefix_parts)
                if i == 0:
                    question_data = km_chapters[prefix_parts[0]]
                elif prefix_parts[-1] in km_questions:
                    question_data = km_questions[prefix_parts[-1]]
                else:
                    # An answer segment, which has no node of its own.
                    continue

                node: AssignmentQuestionNode = {
                    'question_path': full_path,
                    'question_title': question_data['title'],
                    'question_text': question_data['text'],
                    'children': {},
                }
                if is_leaf:
                    node['include'] = True
                current[segment] = node
            elif is_leaf:
                current[segment]['value'] = True

            current = current[segment]['children']

    return root
