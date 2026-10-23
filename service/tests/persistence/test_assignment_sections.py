from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from ai_document_plugin_service.ai.assignment.compatibility_utils import (
    collect_leaf_question_paths,
    convert_mappings_to_assignment_tree,
)
from ai_document_plugin_service.ai.assignment.mappers import template_sections_to_records
from ai_document_plugin_service.ai.assignment.section_tree import collect_leaf_sections
from ai_document_plugin_service.ai.assignment.types import SectionQuestionPaths
from ai_document_plugin_service.ai.common.types import TemplateContent
from ai_document_plugin_service.ai.persistence.assignment_loader_component import AssignmentLoaderComponent
from ai_document_plugin_service.ai.persistence.database import PostgresDB, SectionAssignmentsContainer
from ai_document_plugin_service.ai.persistence.schema import create_persistence_schema

KM = {
    'chapterUuids': ['ch1'],
    'entities': {
        'chapters': {
            'ch1': {'uuid': 'ch1', 'title': 'Chapter 1', 'text': 'Chapter text', 'questionUuids': ['q1', 'q2']},
        },
        'questions': {
            'q1': {'uuid': 'q1', 'questionType': 'ValueQuestion', 'title': 'Question 1', 'text': 'Q1 text'},
            'q2': {'uuid': 'q2', 'questionType': 'ValueQuestion', 'title': 'Question 2', 'text': 'Q2 text'},
        },
        'answers': {},
        'choices': {},
    },
}
RAW_TEMPLATE = {
    'sections': [
        {'title': 'Intro', 'content': 'Introduce the project.'},
        {'title': 'Parent', 'content': 'Data handling.', 'sections': [{'title': 'First child'}, {'title': 'Second child'}]},
    ],
}
TEMPLATE = TemplateContent.model_validate(RAW_TEMPLATE)


def _leaf_ids(template: TemplateContent) -> list[UUID]:
    return [leaf.id for leaf in collect_leaf_sections(template_sections_to_records(template.sections))]


def _generated_assignments():
    sections = template_sections_to_records(TEMPLATE.sections)
    intro, _first_child, second_child = collect_leaf_sections(sections)
    mapping = {'ch1.q1': [intro.id, second_child.id], 'ch1.q2': [second_child.id]}
    return convert_mappings_to_assignment_tree(sections, mapping, KM)


def test_leaf_question_paths_are_collected_by_section_id():
    intro, first_child, second_child = _leaf_ids(TEMPLATE)

    assert collect_leaf_question_paths(_generated_assignments()) == {
        intro: ['ch1.q1'],
        first_child: [],
        second_child: ['ch1.q1', 'ch1.q2'],
    }


def _loader(stored: SectionQuestionPaths | None) -> AssignmentLoaderComponent:
    now = datetime.now(tz=UTC)
    database = MagicMock()
    database.get_assignments = AsyncMock(
        return_value=None
        if stored is None
        else SectionAssignmentsContainer(question_paths=stored, created_at=now, updated_at=now),
    )
    return AssignmentLoaderComponent(database)


def _without_ids(nodes):
    return [
        {**node, 'id': None, 'children': _without_ids(node['children']) if node['children'] else None}
        for node in nodes
    ]


async def test_loader_rebuilds_the_tree_when_every_leaf_is_stored():
    generated = _generated_assignments()
    stale_section_id = uuid4()
    stored = {**collect_leaf_question_paths(generated), stale_section_id: ['ch1.q2']}

    result = await _loader(stored).run_async(uuid4(), uuid4(), TEMPLATE, KM)

    assert result['complete'] is True
    assert _without_ids(result['assignments']) == _without_ids([assignment.to_dict() for assignment in generated])


async def test_loader_is_incomplete_when_a_leaf_is_not_stored():
    intro, _first_child, second_child = _leaf_ids(TEMPLATE)

    result = await _loader({intro: ['ch1.q1'], second_child: []}).run_async(uuid4(), uuid4(), TEMPLATE, KM)

    assert result == {'assignments': None, 'complete': False}


async def test_loader_without_stored_assignments_is_incomplete():
    result = await _loader(None).run_async(uuid4(), uuid4(), TEMPLATE, KM)

    assert result == {'assignments': None, 'complete': False}


def _database_with_recorded_statements(monkeypatch) -> tuple[PostgresDB, SimpleNamespace]:
    database = PostgresDB.__new__(PostgresDB)
    schema = create_persistence_schema('test')
    database.schema_name = 'test'
    database.assignment_table = schema.assignment_table
    database.assignment_section_table = schema.assignment_section_table
    database._ensure_schema = AsyncMock()
    connection = SimpleNamespace(execute=AsyncMock())

    @asynccontextmanager
    async def connect():
        yield connection

    @asynccontextmanager
    async def transaction():
        yield

    monkeypatch.setattr(database, '_connect', connect)
    monkeypatch.setattr(database, 'transaction', transaction)
    return database, connection


async def test_save_assignments_replaces_section_rows_with_one_row_per_section_id(monkeypatch):
    database, connection = _database_with_recorded_statements(monkeypatch)
    knowledge_model_uuid = uuid4()
    template_uuid = uuid4()
    first_section, second_section = uuid4(), uuid4()

    await database.save_assignments(
        knowledge_model_uuid, 'Model', '1', {first_section: ['ch1.q1'], second_section: []}, template_uuid,
    )

    upsert, delete, insert = connection.execute.await_args_list
    assert upsert.args[0].table is database.assignment_table
    assert delete.args[0].compile().params == {
        'knowledge_model_uuid_1': knowledge_model_uuid, 'template_uuid_1': template_uuid,
    }
    assert insert.args[0].table is database.assignment_section_table
    assert insert.args[1] == [
        {'knowledge_model_uuid': knowledge_model_uuid, 'template_uuid': template_uuid, 'section_id': first_section,
         'question_paths': ['ch1.q1']},
        {'knowledge_model_uuid': knowledge_model_uuid, 'template_uuid': template_uuid, 'section_id': second_section,
         'question_paths': []},
    ]


async def test_save_assignments_without_sections_only_removes_stored_ones(monkeypatch):
    database, connection = _database_with_recorded_statements(monkeypatch)

    await database.save_assignments(uuid4(), 'Model', '1', {}, uuid4())

    _upsert, delete = connection.execute.await_args_list
    assert delete.args[0].table is database.assignment_section_table
