from pathlib import Path

from ai_document_plugin_service.ai.common.config import load_config
from typing import Optional, cast
import pytest

from ai_document_plugin_service.ai.assignment.types import SectionAssignment, SerializedSectionAssignment
from ai_document_plugin_service.ai.common.types import AssignmentStats
from ai_document_plugin_service.ai.common.llm_client import LLMClient
from ai_document_plugin_service.ai.generation.cover_page_component import CoverPageComponent
from ai_document_plugin_service.ai.generation.dmp_generator_component import (
    DmpGeneratorComponent,
)
from ai_document_plugin_service.ai.generation.cover_page_translation import CoverPageTranslator
from ai_document_plugin_service.ai.generation.llm import GenerationLLM
from ai_document_plugin_service.ai.generation.parse_answers import parse_answer
from ai_document_plugin_service.ai.knowledgemodel.parser_component import ParserComponent
from ai_document_plugin_service.cover_page.renderer import CoverPageRenderer

TEST_CONFIG_PATH = str(Path(__file__).resolve().parents[2] / 'config.test.yaml')
TEST_CONFIG = load_config(TEST_CONFIG_PATH)


def _component(
    gen_llm: GenerationLLM | None = None,
    cover_page_generation_prompt: str = '',
) -> DmpGeneratorComponent:
    return DmpGeneratorComponent(
        dmp_generator_llm=gen_llm or StubGenerationLLM(),
        cover_page_translator=CoverPageTranslator(
            cast(LLMClient, object()),
            'en',
            TEST_CONFIG.cover_page_translation,
            TEST_CONFIG.cover_definition,
        ),
        cover_page_generation_prompt=cover_page_generation_prompt,
        cover_page_renderer=CoverPageRenderer(TEST_CONFIG.cover_definition),
    )


def _serialize_assignments(assignments: list[SectionAssignment]) -> list[SerializedSectionAssignment]:
    return [assignment.to_dict() for assignment in assignments]


def _km_fixture() -> dict:
    return {
        'entities': {
            'phases': {},
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
            'phases': {},
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


def _questionnaire_detail_fixture() -> dict:
    return {
        'name': 'Potato project',
        'phaseUuid': 'phase-1',
        'knowledgeModelPackage': {
            'name': 'DSW Knowledge Model',
            'version': '1.2.0',
        },
    }


def _km_with_phase_fixture() -> dict:
    return {
        'entities': {
            'phases': {
                'phase-1': {
                    'title': 'Before Submitting the Proposal',
                },
            },
            'questions': {},
            'answers': {},
            'chapters': {},
            'choices': {},
        },
    }


def _project_versions_fixture() -> list[dict]:
    return [
        {
            'name': 'Version 1',
            'updatedAt': '2018-01-21T00:00:00Z',
            'description': 'First version',
        },
        {
            'name': 'Version 2',
            'updatedAt': '2018-02-21T00:00:00Z',
            'description': 'Latest version',
        },
    ]


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


async def test_disabled_cover_page_is_omitted_even_when_source_data_are_available() -> None:
    result = await _component().run_async(
        replies={},
        km=_km_with_phase_fixture(),
        questionnaire_detail=_questionnaire_detail_fixture(),
        project_versions=_project_versions_fixture(),
        new_assignments=[],
        include_cover_page=False,
    )

    assert result['cover_page'] == ''


async def test_cover_page_component_prepends_cover_page_after_polishing() -> None:
    result = await CoverPageComponent().run_async(
        markdown='# Polished section',
        cover_page='# Data Management Plan',
    )

    assert result['markdown'] == '# Data Management Plan\n\n<!-- ai-cover-page-end -->\n\n# Polished section'


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

    assert parsed == ('{"name": "Zenodo", "homepage": null, "url": null, "doi": null, "description": null} value')


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

    assert parsed == ('{"homepage": "https://tools.ietf.org/html/rfc4180", "doi": "10.25504/FAIRsharing.1943d4"} value')


async def test_run_renders_parent_and_leaf_sections() -> None:
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

    result = await component.run_async(
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


@pytest.mark.parametrize('cached', [False, True])
@pytest.mark.parametrize('nested', [False, True])
async def test_run_uses_cover_page_assignments_regardless_of_title(cached: bool, nested: bool) -> None:
    stub = StubGenerationLLM(
        section_response=(
            '### Potato project\n\n- Project title: Potato project\n- Project acronym: PP\n- Project number/code: 123'
        ),
    )
    component = _component(
        stub, cover_page_generation_prompt='Use the answered project title as each subsection heading.'
    )
    cover_page_assignments = [
        SectionAssignment(
            id='cover-page-details',
            title='Research overview',
            assignments={
                'itemQ': {
                    'question_path': 'ch.itemQ',
                    'question_title': 'Item',
                    'question_text': 'Item text',
                    'children': {},
                },
            },
        )
    ]
    assignments = [
        SectionAssignment(
            id='document',
            title='Projects',
            assignments={
                'itemQ': {
                    'question_path': 'ch.itemQ',
                    'question_title': 'Item',
                    'question_text': 'Item text',
                    'children': {},
                },
            },
        ),
    ]
    if nested:
        cover_page_assignments = [
            SectionAssignment(id='cover-page-root', title='Overview', children=cover_page_assignments)
        ]
    replies = {'ch.itemQ': {'value': {'type': 'AnswerReply', 'value': 'yes'}}}

    result = await component.run_async(
        replies=replies,
        km=_km_fixture(),
        questionnaire_detail=_questionnaire_detail_fixture(),
        new_assignments=None if cached else _serialize_assignments(assignments),
        new_cover_page_assignments=None if cached else _serialize_assignments(cover_page_assignments),
        db_assignments=_serialize_assignments(assignments) if cached else None,
        db_cover_page_assignments=_serialize_assignments(cover_page_assignments) if cached else None,
        include_cover_page=True,
    )

    assert 'Research overview' in result['cover_page']
    assert '### Potato project' in result['cover_page']
    assert 'Research overview' not in result['markdown']
    assert '# Projects' in result['markdown']
    assert len(stub.section_calls) == 2
    cover_page_prompt = next(prompt for prompt in stub.section_calls if 'Research overview' in prompt)
    body_prompt = next(prompt for prompt in stub.section_calls if 'Projects' in prompt)
    assert 'Use the answered project title' in cover_page_prompt
    assert 'Use the answered project title' not in body_prompt


async def test_run_reuses_assignments_without_cover_page() -> None:
    stub = StubGenerationLLM()
    component = _component(stub, cover_page_generation_prompt='Cover-page-only instruction')
    assignments = _serialize_assignments(
        [
            SectionAssignment(
                id='document',
                title='Document section',
                assignments={
                    'itemQ': {
                        'question_path': 'ch.itemQ',
                        'question_title': 'Item',
                        'question_text': 'Item text',
                        'children': {},
                    },
                },
            ),
        ]
    )
    replies = {'ch.itemQ': {'value': {'type': 'AnswerReply', 'value': 'yes'}}}

    first = await component.run_async(
        replies=replies,
        km=_km_fixture(),
        new_assignments=assignments,
        new_cover_page_assignments=None,
    )
    repeated = await component.run_async(
        replies=replies,
        km=_km_fixture(),
        db_assignments=assignments,
        db_cover_page_assignments=None,
    )

    assert repeated['markdown'] == first['markdown']
    assert '# Document section' in repeated['markdown']
    assert repeated['cover_page'] == first['cover_page'] == ''
    assert len(stub.section_calls) == 2
    assert all('Cover-page-only instruction' not in prompt for prompt in stub.section_calls)


async def test_run_handles_empty_section() -> None:
    stub = StubGenerationLLM()
    component = _component(stub)
    km = _km_fixture()
    assignments = [
        SectionAssignment(id='s0', title='Empty'),
    ]

    result = await component.run_async(
        replies={},
        km=km,
        new_assignments=_serialize_assignments(assignments),
    )
    markdown = result['markdown']

    assert '# Empty' in markdown
    assert 'No data' in markdown
    assert len(stub.section_calls) == 0


@pytest.mark.parametrize(('cover_page', 'body'), [('', '# Body'), ('# Cover page', ''), ('   ', '# Body')])
async def test_cover_page_boundary_requires_both_parts(cover_page: str, body: str) -> None:
    result = await CoverPageComponent().run_async(markdown=body, cover_page=cover_page)
    assert '<!-- ai-cover-page-end -->' not in result['markdown']


async def test_localized_cover_page_keeps_project_values_and_body_assignments():
    import json
    from copy import deepcopy
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from ai_document_plugin_service.ai.generation.cover_page_translation import cover_page_translation_labels

    translations = {
        **cover_page_translation_labels(TEST_CONFIG.cover_definition),
        'document_title': 'Plán správy dat',
        'project_name': 'Název projektu',
        'history_title': 'Historie změn',
        'section_0': 'Přehled výzkumu',
        'funding': 'Financování',
    }
    client = SimpleNamespace(
        completion=AsyncMock(
            return_value=SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(translations)))],
                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
            )
        )
    )
    stub = StubGenerationLLM()
    component = DmpGeneratorComponent(
        stub,
        cover_page_translator=CoverPageTranslator(
            cast(LLMClient, client),
            'cs',
            load_config(TEST_CONFIG_PATH).cover_page_translation,
            TEST_CONFIG.cover_definition,
        ),
        cover_page_renderer=CoverPageRenderer(TEST_CONFIG.cover_definition),
    )
    cover_page_assignments = [
        SectionAssignment(
            id='cover-page',
            title='Research overview',
            assignments={
                'itemQ': {
                    'question_path': 'ch.itemQ',
                    'question_title': 'Item',
                    'question_text': 'Item text',
                    'children': {},
                },
            },
        ).to_dict()
    ]
    original = deepcopy(cover_page_assignments)
    result = await component.run_async(
        replies={'ch.itemQ': {'value': {'type': 'AnswerReply', 'value': 'yes'}}},
        km=_km_fixture(),
        questionnaire_detail=_questionnaire_detail_fixture(),
        db_assignments=[SectionAssignment(id='body', title='Research overview').to_dict()],
        db_cover_page_assignments=cover_page_assignments,
        include_cover_page=True,
    )
    assert '# Plán správy dat' in result['cover_page']
    assert '| Název projektu | Potato project |' in result['cover_page']
    assert '## Historie změn' in result['cover_page']
    assert '# Přehled výzkumu' in result['cover_page']
    assert '# Research overview' in result['markdown']
    assert 'Funding: Financování' in stub.section_calls[0]
    assert cover_page_assignments == original
    client.completion.assert_awaited_once()


async def test_no_cover_page_skips_translation():
    from unittest.mock import AsyncMock

    translator = AsyncMock()
    component = DmpGeneratorComponent(StubGenerationLLM(), cover_page_translator=translator)
    await component.run_async(replies={}, km=_km_fixture(), new_assignments=[])
    translator.translate.assert_not_called()
