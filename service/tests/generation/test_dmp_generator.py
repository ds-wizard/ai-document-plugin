from typing import Optional

from ai_document_plugin_service.ai.common.types import AssignmentStats
from ai_document_plugin_service.ai.generation import dmp_generator
from ai_document_plugin_service.ai.generation.llm import GenerationLLM


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _km_fixture() -> dict:
    return {
        "entities": {
            "questions": {
                "listQ": {"title": "List", "text": "List text"},
                "itemQ": {"title": "Item", "text": "Item text"},
                "neighborQ": {"title": "Neighbor", "text": "Neighbor text"},
            },
            "answers": {
                "yes": {"label": "Yes", "advice": None},
                "no": {"label": "No", "advice": None},
            },
            "chapters": {},
            "choices": {},
        }
    }


class StubGenerationLLM(GenerationLLM):
    """Deterministic LLM stub that records calls."""

    def __init__(self, section_response: str = "Generated section body"):
        self.section_calls: list[str] = []
        self.polish_calls: list[str] = []
        self._section_response = section_response

    def section_from_qa(
            self,
            prompt: str,
            stats: Optional[AssignmentStats] = None,
            previously_generated: str = "",
    ) -> str:
        self.section_calls.append(prompt)
        return self._section_response

    def polish_dmp(
            self,
            markdown: str,
            structure_str: str = "",
            stats: Optional[AssignmentStats] = None,
    ) -> str:
        self.polish_calls.append(markdown)
        return markdown


# ---------------------------------------------------------------------------
# Pure function tests
# ---------------------------------------------------------------------------

def test_heading_depth_zero() -> None:
    assert dmp_generator._heading(0, "Title") == "# Title"


def test_heading_depth_two() -> None:
    assert dmp_generator._heading(2, "Sub") == "### Sub"


def test_sanitize_replaces_newlines() -> None:
    assert dmp_generator.sanitize("a\nb\nc") == "a b c"


def test_sanitize_returns_none_for_none() -> None:
    assert dmp_generator.sanitize(None) is None


def test_sanitize_table_cell_escapes_pipe() -> None:
    assert "&#124;" in dmp_generator._sanitize_table_cell("a|b")


def test_sanitize_table_cell_handles_nan() -> None:
    assert dmp_generator._sanitize_table_cell(float("nan")) == ""


def test_get_wildcard_uuids_extracts_matches() -> None:
    template = "ch.listQ.*.itemQ"
    paths = ["ch.listQ.uuid1.itemQ", "ch.listQ.uuid2.itemQ", "ch.other.uuid3.itemQ"]
    result = dmp_generator.get_wildcard_uuids(template, paths)
    assert result == ["uuid1", "uuid2"]


def test_get_wildcard_uuids_returns_empty_for_no_matches() -> None:
    result = dmp_generator.get_wildcard_uuids("a.*.b", ["x.y.z"])
    assert result == []


def test_get_question_path_replaces_wildcards() -> None:
    question = {"question_path": "ch.*.sub.*.leaf"}
    assert dmp_generator.get_question_path(question, ["a", "b"]) == "ch.a.sub.b.leaf"


def test_get_reply_keys_at_level_filters_by_depth() -> None:
    replies = {
        "ch.a": "x",
        "ch.b": "y",
        "ch.a.deep": "z",
    }
    assert sorted(dmp_generator._get_reply_keys_at_level(replies, "ch")) == ["ch.a", "ch.b"]


def test_get_reply_keys_at_level_root() -> None:
    replies = {"a": 1, "b": 2, "a.c": 3}
    assert sorted(dmp_generator._get_reply_keys_at_level(replies, "")) == ["a", "b"]


def test_flatten_matched_questions_extracts_leaf_rows() -> None:
    matches = [
        {
            "type": "wrapper",
            "children": [
                {"type": "question", "question_path": "p1", "question_title": "Q1",
                 "question_text": "t1", "reply": "r1", "children": []},
            ],
        },
        {"type": "question", "question_path": "p2", "question_title": "Q2",
         "question_text": "t2", "reply": None, "children": []},
    ]
    rows = dmp_generator._flatten_matched_questions(matches, "sec")
    assert len(rows) == 2
    assert rows[0]["reply"] == "r1"
    assert rows[0]["has_reply"] is True
    assert rows[1]["has_reply"] is False


def test_construct_chapter_prompt_returns_none_for_empty() -> None:
    assert dmp_generator.construct_chapter_prompt("Ch", []) is None


def test_construct_chapter_prompt_formats_questions() -> None:
    replies = [
        {"type": "question", "question_title": "Q1", "reply": "A1", "children": []},
    ]
    prompt = dmp_generator.construct_chapter_prompt("Data", replies)
    assert prompt is not None
    assert "Chapter name: Data" in prompt
    assert "Q1" in prompt
    assert "A1" in prompt


# ---------------------------------------------------------------------------
# Reply matching tests
# ---------------------------------------------------------------------------

def test_match_replies_selection_handles_multianswer_groups() -> None:
    km = _km_fixture()
    questions = {
        "itemQ": {
            "question_path": "ch.listQ.*.itemQ",
            "question_title": "Item",
            "question_text": "Item text",
            "children": {},
        }
    }
    replies = {
        "ch.listQ.uuidA.itemQ": {"value": {"type": "AnswerReply", "value": "yes"}},
        "ch.listQ.uuidB.itemQ": {"value": {"type": "AnswerReply", "value": "no"}},
    }

    result, has_answer = dmp_generator.match_replies_selection(questions, replies, km)

    assert has_answer is True
    assert len(result) == 2
    assert all(item["type"] == "wrapper" for item in result)
    flattened = [child["reply"] for wrapper in result for child in wrapper["children"]]
    assert sorted(flattened) == ["No", "Yes"]


def test_handle_single_reply_adds_synthetic_neighbour_answers_from_depth_two() -> None:
    km = _km_fixture()
    questions = {
        "itemQ": {
            "question_path": "ch.listQ.itemQ",
            "question_title": "Item",
            "question_text": "Item text",
            "children": {},
        }
    }
    replies = {
        "ch.listQ.itemQ": {"value": {"type": "AnswerReply", "value": "yes"}},
        "ch.listQ.neighborQ": {"value": {"type": "AnswerReply", "value": "no"}},
    }

    result, has_answer = dmp_generator.handle_single_reply(
        questions=questions,
        replies=replies,
        km=km,
        depth=2,
        override_uuids=[],
    )

    assert has_answer is True
    assert len(result) == 2
    assert result[0]["question_path"] == "ch.listQ.itemQ"
    synthetic = next(item for item in result if item["question_path"] == "ch.listQ.neighborQ")
    assert synthetic["question_title"] == "Neighbor"
    assert synthetic["reply"] == "No"
    assert synthetic["debug-info"]


def test_match_replies_selection_returns_empty_for_no_questions() -> None:
    result, has_answer = dmp_generator.match_replies_selection({}, {}, _km_fixture())
    assert result == []
    assert has_answer is False


# ---------------------------------------------------------------------------
# Integration test with stub LLM
# ---------------------------------------------------------------------------

def test_generate_dmp_markdown_renders_parent_and_leaf_sections() -> None:
    km = _km_fixture()
    assignments_tree = [
        {
            "key": "Root",
            "children": [
                {
                    "key": "Leaf",
                    "assignments": {
                        "itemQ": {
                            "question_path": "ch.listQ.itemQ",
                            "question_title": "Item",
                            "question_text": "Item text",
                            "children": {},
                        }
                    },
                }
            ],
        }
    ]
    replies = {
        "ch.listQ.itemQ": {"value": {"type": "AnswerReply", "value": "yes"}},
    }

    stub = StubGenerationLLM()
    markdown, debug_markdown, stats = dmp_generator.generate_dmp_markdown(
        assignments_tree, replies, km, llm=stub,
    )

    assert stub.section_calls
    assert "# Root" in markdown
    assert "## Leaf" in markdown
    assert "Generated section body" in markdown
    assert "<details>" in debug_markdown
    assert "Source questions" in debug_markdown
    assert stats is not None


def test_generate_dmp_markdown_handles_empty_section() -> None:
    km = _km_fixture()
    assignments_tree = [
        {"key": "Empty", "children": None, "assignments": None},
    ]

    stub = StubGenerationLLM()
    markdown, _, _ = dmp_generator.generate_dmp_markdown(
        assignments_tree, {}, km, llm=stub,
    )

    assert "# Empty" in markdown
    assert "No data" in markdown
    assert len(stub.section_calls) == 0
