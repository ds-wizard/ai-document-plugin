from typing import Optional

from ai_document_plugin_service.ai.assignment.types import SectionAssignment, SerializedSectionAssignment
from ai_document_plugin_service.ai.common.types import AssignmentStats
from ai_document_plugin_service.ai.generation.dmp_generator_component import (
    DmpGeneratorComponent,
)
from ai_document_plugin_service.ai.generation.llm import GenerationLLM
from ai_document_plugin_service.ai.generation.parse_answers import parse_answer
from ai_document_plugin_service.ai.knowledgemodel.parser_component import ParserComponent


def _component(gen_llm: GenerationLLM | None = None) -> DmpGeneratorComponent:
    return DmpGeneratorComponent(
        dmp_generator_llm=gen_llm or StubGenerationLLM(),
    )


def _serialize_assignments(assignments: list[SectionAssignment]) -> list[SerializedSectionAssignment]:
    return [assignment.to_dict() for assignment in assignments]


def _km_fixture() -> dict:
    return {
        'entities': {
            'questions': {
                'listQ': {'title': 'List', 'text': 'List text', 'questionType': 'ListQuestion'},
                'itemQ': {'title': 'Item', 'text': 'Item text', 'questionType': 'ValueQuestion'},
                'neighborQ': {'title': 'Neighbor', 'text': 'Neighbor text', 'questionType': 'ValueQuestion'},
            },
            'answers': {
                'yes': {'label': 'Yes', 'advice': None},
                'no': {'label': 'No', 'advice': None},
            },
            'chapters': {},
            'choices': {},
        },
    }


def _reachable_km_fixture() -> dict:
    return {
        'chapterUuids': ['chapter'],
        'entities': {
            'chapters': {
                'chapter': {
                    'uuid': 'chapter',
                    'title': 'Chapter',
                    'questionUuids': ['rootQ', 'datasetsQ'],
                },
            },
            'questions': {
                'rootQ': {
                    'questionType': 'OptionsQuestion',
                    'title': 'Root',
                    'text': 'Root text',
                    'answerUuids': ['yes', 'no'],
                },
                'childQ': {
                    'questionType': 'ValueQuestion',
                    'title': 'Child',
                    'text': 'Child text',
                },
                'datasetsQ': {
                    'questionType': 'ListQuestion',
                    'title': 'Datasets',
                    'text': 'Datasets text',
                    'itemTemplateQuestionUuids': ['datasetNameQ'],
                },
                'datasetNameQ': {
                    'questionType': 'ValueQuestion',
                    'title': 'Dataset name',
                    'text': 'Dataset name text',
                },
            },
            'answers': {
                'yes': {'label': 'Yes', 'advice': None, 'followUpUuids': ['childQ']},
                'no': {'label': 'No', 'advice': None, 'followUpUuids': []},
            },
            'choices': {},
        },
    }


class StubGenerationLLM(GenerationLLM):
    """Deterministic LLM stub that records calls."""

    def get_max_workers(self) -> int:
        return 1

    def __init__(self, section_response: str = 'Generated section body'):
        self.section_calls: list[str] = []
        self._section_response = section_response

    async def section_from_qa(
        self,
        prompt: str,
        stats: Optional[AssignmentStats] = None,
        previously_generated: str = '',
    ) -> str:
        self.section_calls.append(prompt)
        return self._section_response


def test_heading_depth_zero() -> None:
    assert _component()._heading(0, 'Title') == '# Title'


def test_heading_depth_two() -> None:
    assert _component()._heading(2, 'Sub') == '### Sub'


def test_sanitize_replaces_newlines() -> None:
    assert _component().sanitize('a\nb\nc') == 'a b c'


def test_sanitize_returns_none_for_none() -> None:
    assert _component().sanitize(None) is None


def test_sanitize_table_cell_escapes_pipe() -> None:
    assert '&#124;' in _component()._sanitize_table_cell('a|b')


def test_sanitize_table_cell_handles_nan() -> None:
    assert _component()._sanitize_table_cell(float('nan')) == ''


def test_get_wildcard_uuids_extracts_matches() -> None:
    component = _component()
    template = 'ch.listQ.*.itemQ'
    paths = ['ch.listQ.uuid1.itemQ', 'ch.listQ.uuid2.itemQ', 'ch.other.uuid3.itemQ']
    result = component.get_wildcard_uuids(template, paths)
    assert result == ['uuid1', 'uuid2']


def test_get_wildcard_uuids_returns_empty_for_no_matches() -> None:
    result = _component().get_wildcard_uuids('a.*.b', ['x.y.z'])
    assert result == []


def test_get_question_path_replaces_wildcards() -> None:
    question = {'question_path': 'ch.*.sub.*.leaf'}
    assert _component().get_question_path(question, ['a', 'b']) == 'ch.a.sub.b.leaf'


def test_get_reply_keys_at_level_filters_by_depth() -> None:
    replies = {
        'ch.a': 'x',
        'ch.b': 'y',
        'ch.a.deep': 'z',
    }
    assert sorted(_component()._get_reply_keys_at_level(replies, 'ch')) == ['ch.a', 'ch.b']


def test_get_reply_keys_at_level_root() -> None:
    replies = {'a': 1, 'b': 2, 'a.c': 3}
    assert sorted(_component()._get_reply_keys_at_level(replies, '')) == ['a', 'b']


def test_flatten_matched_questions_extracts_leaf_rows() -> None:
    matches = [
        {
            'type': 'wrapper',
            'children': [
                {
                    'type': 'question',
                    'question_path': 'p1',
                    'question_title': 'Q1',
                    'question_text': 't1',
                    'reply': 'r1',
                    'children': [],
                },
            ],
        },
        {
            'type': 'question',
            'question_path': 'p2',
            'question_title': 'Q2',
            'question_text': 't2',
            'reply': None,
            'children': [],
        },
    ]
    rows = _component()._flatten_matched_questions(matches, 'sec')
    assert len(rows) == 2
    assert rows[0]['reply'] == 'r1'
    assert rows[0]['has_reply'] is True
    assert rows[1]['has_reply'] is False


def test_construct_chapter_prompt_returns_none_for_empty() -> None:
    assert _component().construct_chapter_prompt('Ch', []) is None


def test_construct_chapter_prompt_formats_questions() -> None:
    replies = [
        {'type': 'question', 'question_title': 'Q1', 'reply': 'A1', 'children': []},
    ]
    prompt = _component().construct_chapter_prompt('Data', replies)
    assert prompt is not None
    assert 'Chapter name: Data' in prompt
    assert 'Q1' in prompt
    assert 'A1' in prompt


def test_match_replies_selection_handles_multianswer_groups() -> None:
    component = _component()
    km = _km_fixture()
    questions = {
        'itemQ': {
            'question_path': 'ch.listQ.*.itemQ',
            'question_title': 'Item',
            'question_text': 'Item text',
            'children': {},
        },
    }
    replies = {
        'ch.listQ.uuidA.itemQ': {'value': {'type': 'AnswerReply', 'value': 'yes'}},
        'ch.listQ.uuidB.itemQ': {'value': {'type': 'AnswerReply', 'value': 'no'}},
    }

    result, has_answer = component.match_replies_selection(questions, replies, km)

    assert has_answer is True
    assert len(result) == 2
    assert all(item['type'] == 'wrapper' for item in result)
    flattened = [child['reply'] for wrapper in result for child in wrapper['children']]
    assert sorted(flattened) == ['No', 'Yes']


def test_handle_single_reply_adds_synthetic_neighbour_answers_from_depth_two() -> None:
    component = _component()
    km = _km_fixture()
    questions = {
        'itemQ': {
            'question_path': 'ch.listQ.itemQ',
            'question_title': 'Item',
            'question_text': 'Item text',
            'children': {},
        },
    }
    replies = {
        'ch.listQ.itemQ': {'value': {'type': 'AnswerReply', 'value': 'yes'}},
        'ch.listQ.neighborQ': {'value': {'type': 'AnswerReply', 'value': 'no'}},
    }

    result, has_answer = component.handle_single_reply(
        questions=questions,
        replies=replies,
        km=km,
        depth=2,
        override_uuids=[],
    )

    assert has_answer is True
    assert len(result) == 2
    assert result[0]['question_path'] == 'ch.listQ.itemQ'
    synthetic = next(item for item in result if item['question_path'] == 'ch.listQ.neighborQ')
    assert synthetic['question_title'] == 'Neighbor'
    assert synthetic['reply'] == 'No'
    assert synthetic['debug-info']


def test_filter_reachable_replies_drops_stale_option_branch() -> None:
    component = _component()
    km = _reachable_km_fixture()
    replies = {
        'chapter.rootQ': {'value': {'type': 'AnswerReply', 'value': 'no'}},
        'chapter.rootQ.yes.childQ': {
            'value': {
                'type': 'StringReply',
                'value': 'stale child',
            },
        },
    }

    filtered = component._filter_reachable_replies(replies, km)

    assert filtered == {
        'chapter.rootQ': {'value': {'type': 'AnswerReply', 'value': 'no'}},
    }


def test_filter_reachable_replies_drops_removed_list_item_branch() -> None:
    component = _component()
    km = _reachable_km_fixture()
    replies = {
        'chapter.datasetsQ': {
            'value': {
                'type': 'ItemListReply',
                'value': ['active-item'],
            },
        },
        'chapter.datasetsQ.active-item.datasetNameQ': {
            'value': {
                'type': 'StringReply',
                'value': 'active',
            },
        },
        'chapter.datasetsQ.removed-item.datasetNameQ': {
            'value': {
                'type': 'StringReply',
                'value': 'stale',
            },
        },
    }

    filtered = component._filter_reachable_replies(replies, km)

    assert filtered == {
        'chapter.datasetsQ': {
            'value': {
                'type': 'ItemListReply',
                'value': ['active-item'],
            },
        },
        'chapter.datasetsQ.active-item.datasetNameQ': {
            'value': {
                'type': 'StringReply',
                'value': 'active',
            },
        },
    }


def test_match_replies_selection_returns_empty_for_no_questions() -> None:
    result, has_answer = _component().match_replies_selection({}, {}, _km_fixture())
    assert result == []
    assert has_answer is False


def test_parse_answer_item_select_reply_returns_selected_item_value() -> None:
    km = {
        'entities': {
            'questions': {
                'listQ': {'questionType': 'ListQuestion', 'title': 'Languages', 'text': 'List languages'},
                'selectQ': {
                    'questionType': 'ItemSelectQuestion',
                    'listQuestionUuid': 'listQ',
                    'title': 'Preferred language',
                    'text': 'Your preferred language for communication',
                },
                'levelQ': {'questionType': 'OptionsQuestion', 'title': 'Level', 'text': None},
                'languageQ': {'questionType': 'IntegrationQuestion', 'title': 'Language', 'text': None},
            },
            'answers': {
                'native': {'label': 'Native', 'advice': None},
            },
            'chapters': {},
            'choices': {},
        },
    }
    replies = {
        'chapter.listQ': {
            'value': {
                'type': 'ItemListReply',
                'value': ['item-a', 'selected-item'],
            },
        },
        'chapter.listQ.selected-item.levelQ': {
            'value': {
                'type': 'AnswerReply',
                'value': 'native',
            },
        },
        'chapter.listQ.selected-item.languageQ': {
            'value': {
                'type': 'IntegrationReply',
                'value': {
                    'type': 'PlainType',
                    'value': 'English',
                },
            },
        },
        'chapter.selectQ': {
            'value': {
                'type': 'ItemSelectReply',
                'value': 'selected-item',
            },
        },
    }

    parsed = parse_answer(
        replies['chapter.selectQ']['value'],
        km,
        replies=replies,
        question_path='chapter.selectQ',
    )

    assert parsed == 'English'


def test_parse_answer_integration_reply_returns_first_raw_and_url() -> None:
    km = {
        'entities': {
            'answers': {},
            'chapters': {},
            'choices': {},
            'questions': {},
        },
    }
    answer = {
        'type': 'IntegrationReply',
        'value': {
            'type': 'IntegrationType',
            'value': '![Logo](data:image/svg+xml;base64,abc) [**Comma-separated Values**](https://fairsharing.org/1398)',
            'raw': {
                'abbreviation': 'CSV',
                'description': (
                    'A comma-separated values (CSV) file is a delimited text file that uses a '
                    'comma to separate values. Each line of the file is a data record. Each '
                    'record consists of one or more fields, separated by commas. The use of the '
                    'comma as a field separator is the source of the name for this file format. '
                    'A CSV file typically stores tabular data (numbers and text) in plain text, '
                    'in which case each line will have the same number of fields.'
                ),
                'homepage': 'https://tools.ietf.org/html/rfc4180',
                'doi': '10.25504/FAIRsharing.1943d4',
                'name': 'Comma-separated Values',
            },
        },
    }

    parsed = parse_answer(answer, km)

    assert parsed == (
        '{"abbreviation": "CSV", "description": "A comma-separated values (CSV) file is a '
        'delimited text file that uses a comma to separate values. Each line of the file is a '
        'data record. Each record consists of one or more fields, separated by commas. The use '
        'of the comma as a field separator is the source of the name for this file format. A '
        'CSV file typically stores tabular data (numbers and text) in plain text, in which case '
        'each line will have the same number of fields.", "homepage": '
        '"https://tools.ietf.org/html/rfc4180", "doi": "10.25504/FAIRsharing.1943d4", "name": '
        '"Comma-separated Values"} https://fairsharing.org/1398'
    )


def test_parse_answer_integration_reply_handles_none_values_in_raw_mapping() -> None:
    km = {
        'entities': {
            'answers': {},
            'chapters': {},
            'choices': {},
            'questions': {},
        },
    }
    answer = {
        'type': 'IntegrationReply',
        'value': {
            'type': 'IntegrationType',
            'value': 'value',
            'raw': {
                'name': 'Zenodo',
                'homepage': None,
                'url': None,
                'doi': None,
                'description': None,
            },
        },
    }

    parsed = parse_answer(answer, km)

    assert parsed == (
        '{"name": "Zenodo", "homepage": null, "url": null, "doi": null, "description": null} value'
    )


def test_parser_component_item_select_reply_uses_integration_raw_url() -> None:
    parser = ParserComponent()
    parser.km = {
        'entities': {
            'questions': {
                'integrationQ': {'questionType': 'IntegrationQuestion'},
            },
        },
    }
    replies = {
        'chapter.selectQ': {
            'value': {
                'type': 'ItemSelectReply',
                'value': 'selected-item',
            },
        },
        'chapter.listQ.selected-item.reply.integrationQ': {
            'value': {
                'type': 'IntegrationReply',
                'value': {
                    'type': 'IntegrationType',
                    'value': 'value',
                    'raw': {
                        'homepage': 'https://tools.ietf.org/html/rfc4180',
                        'doi': '10.25504/FAIRsharing.1943d4',
                    },
                },
            },
        },
    }

    parsed = parser.get_item_select_question_reply(
        replies,
        path='chapter.selectQ',
    )

    assert parsed == (
        '{"homepage": "https://tools.ietf.org/html/rfc4180", "doi": "10.25504/FAIRsharing.1943d4"} value'
    )


def test_run_renders_parent_and_leaf_sections() -> None:
    stub = StubGenerationLLM()
    component = _component(stub)
    km = _km_fixture()
    assignments = [
        SectionAssignment(
            id='s0',
            title='Root',
            children=[
                SectionAssignment(
                    id='s1',
                    title='Leaf',
                    assignments={
                        'itemQ': {
                            'question_path': 'ch.listQ.itemQ',
                            'question_title': 'Item',
                            'question_text': 'Item text',
                            'children': {},
                        },
                    },
                ),
            ],
        ),
    ]
    replies = {
        'ch.listQ.itemQ': {'value': {'type': 'AnswerReply', 'value': 'yes'}},
    }

    result = component.run(
        replies=replies,
        km=km,
        new_assignments=_serialize_assignments(assignments),
    )
    markdown = result['markdown']
    debug_markdown = result['debug_markdown']
    stats = result['stats']

    assert stub.section_calls
    assert '# Root' in markdown
    assert '## Leaf' in markdown
    assert 'Generated section body' in markdown
    assert '<details>' in debug_markdown
    assert 'Source questions' in debug_markdown
    assert stats is not None


def test_run_handles_empty_section() -> None:
    stub = StubGenerationLLM()
    component = _component(stub)
    km = _km_fixture()
    assignments = [
        SectionAssignment(id='s0', title='Empty'),
    ]

    result = component.run(
        replies={},
        km=km,
        new_assignments=_serialize_assignments(assignments),
    )
    markdown = result['markdown']

    assert '# Empty' in markdown
    assert 'No data' in markdown
    assert len(stub.section_calls) == 0
