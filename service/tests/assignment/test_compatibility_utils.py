import json
import os

import pytest

from ai_document_plugin_service.ai.assignment.compatibility_utils import (
    convert_mappings_to_assignment_tree,
    expand_assignment_paths,
)
from ai_document_plugin_service.ai.assignment.section_tree import build_section_records
from ai_document_plugin_service.ai.assignment.types import SectionRecord, SectionNode


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
    data_assignments = as_dict["Data"]
    methods_assignments = as_dict["Methods"]

    assert data_assignments is not None
    assert methods_assignments is not None

    assert "ch1" in data_assignments
    assert "q1" in data_assignments["ch1"]["children"]
    assert "q2" in data_assignments["ch1"]["children"]
    assert "q2" in methods_assignments["ch1"]["children"]


def test_convert_mappings_real_km():
    test_dir = os.path.dirname(os.path.abspath(__file__))
    resource_path = os.path.join(test_dir, "../resources/dsw_root_km.json.json")
    with open(resource_path, encoding='utf-8', mode='r') as f:
        km = json.load(f)

    sections = [
        SectionRecord(
            'Data management plan',
            SectionNode({
                'title': 'Data management plan'
            }),
            None,
            [
                SectionRecord(
                    'Project',
                    SectionNode({'title': 'Project'}),
                    "[PARENT SECTION]\nTitle: Data management plan\n\n[MOST SPECIFIC SECTION]\nTitle: Project\nContent:\nIt contains project number, project acronym, project name.'",
                    None
                )
            ]
        )
    ]
    result_mapping = {
        '1e85da40-bbfc-4180-903e-6c569ed2da38.c3dabaaf-c946-4a0d-889c-ede966f97667.*.f0ef08fd-d733-465c-bc66-5de0b826c41b':
            ['Project']
    }

    mappings = convert_mappings_to_assignment_tree(sections, result_mapping, km, )
    sec_dmp = mappings[0]
    assert sec_dmp.assignments is None
    sec_project = sec_dmp.children[0]
    assert sec_project.children is None
    assert len(sec_project.assignments) > 0
    administrative_info = list(sec_project.assignments.values())[0]
    assert administrative_info['question_title'] == 'Administrative information'

    # Research Project
    research_proj_key = list(administrative_info['children'])[0]
    assert research_proj_key == 'c3dabaaf-c946-4a0d-889c-ede966f97667'
    research_proj = administrative_info['children'][research_proj_key]
    assert research_proj['question_title'] == 'Research Project(s)'

    # Project name
    proj_name_key = list(research_proj['children'])[0]
    assert proj_name_key == 'f0ef08fd-d733-465c-bc66-5de0b826c41b'
    proj_name = research_proj['children'][proj_name_key]
    assert proj_name['question_title'] == 'Project name'
