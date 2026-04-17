from typing import Any

from ai_document_plugin_service.ai.assignment.types import SectionAssignment, SectionRecord


def convert_mappings_to_assignment_tree(
        sections: list[SectionRecord],
        path_to_sections_mappings: dict[str, list[str]],
        km: dict[str, Any],
) -> list[SectionAssignment]:
    section_to_paths_mappings: dict[str, list[str]] = {}
    for path, section_names in path_to_sections_mappings.items():
        for section_name in section_names:
            if section_name not in section_to_paths_mappings:
                section_to_paths_mappings[section_name] = []
            section_to_paths_mappings[section_name].append(path)
    return convert_mappings_to_assignment_tree_recursive(sections, section_to_paths_mappings, km)


def convert_mappings_to_assignment_tree_recursive(
        sections: list[SectionRecord],
        section_to_path_mapping: dict[str, list[str]],
        km: dict[str, Any],
) -> list[SectionAssignment]:
    """Convert flat leaf assignments into the section hierarchy."""
    result: list[SectionAssignment] = []
    for section in sections:
        if section.children is not None:
            result.append(
                SectionAssignment(
                    key=section.key,
                    assignments=None,
                    children=convert_mappings_to_assignment_tree(section.children, section_to_path_mapping, km),
                )
            )
            continue
        question_flags = section_to_path_mapping.get(section.key, [])
        result.append(
            SectionAssignment(
                key=section.key,
                assignments=expand_assignment_paths(question_flags, km),
                children=None,
            )
        )
    return result


def expand_assignment_paths(mappings: list[str], km: dict[str, Any]) -> dict[str, Any]:
    """
    Decompose flat dot-separated assignment paths into nested question nodes.

    This preserves the previous hierarchical output shape consumed by downstream steps.
    """
    root: dict[str, Any] = {}
    km_questions = km["entities"]["questions"]
    km_chapters = km["entities"]["chapters"]
    km_answers = km["entities"]["answers"]

    for path in mappings:
        segments = path.split(".")
        current = root
        prefix_parts: list[str] = []

        for i, segment in enumerate(segments):
            prefix_parts.append(segment)
            if segment == "*":
                continue
            is_leaf = i == len(segments) - 1

            if segment not in current:
                full_path = ".".join(prefix_parts)
                if i == 0:
                    question_data = km_chapters[prefix_parts[0]]
                elif prefix_parts[-1] in km_questions:
                    question_data = km_questions[prefix_parts[-1]]
                elif not is_leaf and prefix_parts[-1] in km_answers:
                    continue
                else:
                    raise Exception("Unexpected path as leaf: " + full_path)

                node: dict[str, Any] = {
                    "question_path": full_path,
                    "question_title": question_data["title"],
                    "question_text": question_data["text"],
                    "children": {},
                }
                if is_leaf:
                    node["include"] = True
                current[segment] = node
            elif is_leaf:
                current[segment]["value"] = True

            current = current[segment]["children"]

    return root
