import pytest

from ai_document_plugin_service.ai.assignment.compatibility_utils import (
    convert_mappings_to_assignment_tree,
    expand_assignment_paths,
)
from ai_document_plugin_service.ai.assignment.section_tree import build_section_records


def _km_fixture() -> dict:
    return {
        "entities": {
            "chapters": {
                "ch1": {"title": "Chapter 1", "text": "Chapter text"},
            },
            "questions": {
                "q1": {"title": "Question 1", "text": "Q1 text"},
                "q2": {"title": "Question 2", "text": "Q2 text"},
                "itemQ": {"title": "Item question", "text": "Item text"},
            },
            "answers": {
                "ans1": {"label": "Yes"},
            },
        }
    }


def test_expand_assignment_paths_builds_nested_tree() -> None:
    km = _km_fixture()
    mappings = ["ch1.q1", "ch1.q2"]

    out = expand_assignment_paths(mappings, km)

    assert "ch1" in out
    assert "q1" in out["ch1"]["children"]
    assert "q2" in out["ch1"]["children"]
    assert out["ch1"]["children"]["q1"]["include"] is True
    assert out["ch1"]["children"]["q2"]["include"] is True


def test_expand_assignment_paths_handles_list_wildcard_segment() -> None:
    km = _km_fixture()
    mappings = ["ch1.q1.*.itemQ"]

    out = expand_assignment_paths(mappings, km)

    assert out["ch1"]["children"]["q1"]["children"]["itemQ"]["include"] is True
    assert out["ch1"]["children"]["q1"]["children"]["itemQ"]["question_path"] == "ch1.q1.*.itemQ"


def test_expand_assignment_paths_raises_for_unknown_leaf() -> None:
    km = _km_fixture()
    with pytest.raises(Exception, match="Unexpected path as leaf"):
        expand_assignment_paths(["ch1.unknown"], km)


def test_convert_mappings_to_assignment_tree_maps_paths_into_leaf_sections() -> None:
    km = _km_fixture()
    template_data = {
        "sections": [
            {"title": "Data", "content": "Section data"},
            {"title": "Methods", "content": "Section methods"},
        ]
    }
    sections = build_section_records(template_data)

    path_to_sections = {
        "ch1.q1": ["Data"],
        "ch1.q2": ["Methods", "Data"],
    }

    assignments = convert_mappings_to_assignment_tree(sections, path_to_sections, km)
    as_dict = {node.key: node.assignments for node in assignments}

    assert "ch1" in as_dict["Data"]
    assert "q1" in as_dict["Data"]["ch1"]["children"]
    assert "q2" in as_dict["Data"]["ch1"]["children"]
    assert "q2" in as_dict["Methods"]["ch1"]["children"]
