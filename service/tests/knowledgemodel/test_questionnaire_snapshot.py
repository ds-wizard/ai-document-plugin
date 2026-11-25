from typing import Any
from uuid import UUID

from ai_document_plugin_service.ai.knowledgemodel.questionnaire_snapshot import StoredReply, build_snapshot


def u(number: int) -> str:
    return str(UUID(int=number))


YES, NO = u(1), u(2)
CSV, JSON = u(3), u(4)
ITEM_1, ITEM_2 = u(5), u(6)

KM = {
    'chapterUuids': ['c1'],
    'entities': {
        'chapters': {'c1': {'title': 'Data', 'questionUuids': ['opt', 'multi', 'items', 'plain', 'integ', 'file']}},
        'questions': {
            'opt': {'questionType': 'OptionsQuestion', 'title': 'Reuse?'},
            'why': {'questionType': 'ValueQuestion', 'title': 'Why'},
            'multi': {'questionType': 'MultiChoiceQuestion', 'title': 'Formats'},
            'items': {'questionType': 'ListQuestion', 'title': 'Datasets', 'itemTemplateQuestionUuids': ['name']},
            'name': {'questionType': 'ValueQuestion', 'title': 'Name'},
            'plain': {'questionType': 'ValueQuestion', 'title': 'Notes'},
            'integ': {'questionType': 'IntegrationQuestion', 'title': 'Repository'},
            'file': {'questionType': 'FileQuestion', 'title': 'Attachment'},
        },
        'answers': {
            YES: {'label': 'Yes', 'followUpUuids': ['why']},
            NO: {'label': 'No', 'followUpUuids': []},
        },
        'choices': {CSV: {'label': 'CSV'}, JSON: {'label': 'JSON'}},
    },
}


def reply(reply_type: str, value: Any) -> dict[str, Any]:
    return {'value': {'type': reply_type, 'value': value}, 'createdAt': '2026-11-20T10:00:00Z', 'createdBy': None}


def test_stores_the_value_as_dsw_sends_it_without_who_made_it_and_when() -> None:
    snapshot = build_snapshot(KM, {'c1.plain': reply('StringReply', 'Some notes')})

    assert snapshot == [StoredReply('c1.plain', {'type': 'StringReply', 'value': 'Some notes'})]


def test_stores_integration_replies_with_the_raw_payload() -> None:
    value = {'type': 'IntegrationType', 'value': 'Zenodo', 'raw': {'id': 1}}

    assert build_snapshot(KM, {'c1.integ': reply('IntegrationReply', value)}) == [
        StoredReply('c1.integ', {'type': 'IntegrationReply', 'value': value}),
    ]


def test_stores_the_selected_answer_with_its_label() -> None:
    assert build_snapshot(KM, {'c1.opt': reply('AnswerReply', YES)}) == [
        StoredReply('c1.opt', {'type': 'AnswerReply', 'value': YES}, display_text='Yes'),
    ]


def test_stores_selected_choices_with_their_labels() -> None:
    assert build_snapshot(KM, {'c1.multi': reply('MultiChoiceReply', [JSON, CSV])}) == [
        StoredReply('c1.multi', {'type': 'MultiChoiceReply', 'value': [JSON, CSV]}, display_text='JSON, CSV'),
    ]


def test_stores_list_items_in_order() -> None:
    snapshot = build_snapshot(KM, {'c1.items': reply('ItemListReply', [ITEM_2, ITEM_1])})

    assert snapshot == [StoredReply('c1.items', {'type': 'ItemListReply', 'value': [ITEM_2, ITEM_1]})]


def test_stores_replies_of_types_it_does_not_know() -> None:
    snapshot = build_snapshot(KM, {'c1.plain': reply('FutureReply', {'anything': 1})})

    assert snapshot == [StoredReply('c1.plain', {'type': 'FutureReply', 'value': {'anything': 1}})]


def test_leaves_out_empty_replies() -> None:
    replies = {
        'c1.plain': reply('StringReply', '   '),
        'c1.multi': reply('MultiChoiceReply', []),
        'c1.items': reply('ItemListReply', []),
        'c1.integ': reply('IntegrationReply', {'type': 'PlainType', 'value': ''}),
    }

    assert build_snapshot(KM, replies) == []


def test_leaves_out_file_replies() -> None:
    assert build_snapshot(KM, {'c1.file': reply('FileReply', u(9))}) == []


def test_leaves_out_unreachable_replies() -> None:
    replies = {
        'c1.opt': reply('AnswerReply', NO),
        f'c1.opt.{YES}.why': reply('StringReply', 'left over from an earlier answer'),
        f'c1.items.{ITEM_1}.name': reply('StringReply', 'item of a list without items'),
    }

    assert [stored.path for stored in build_snapshot(KM, replies)] == ['c1.opt']


def test_skips_a_reply_without_a_type_and_keeps_the_others() -> None:
    replies = {
        'c1.multi': {'value': {'value': [CSV]}},
        'c1.plain': reply('StringReply', 'kept'),
    }

    assert [stored.path for stored in build_snapshot(KM, replies)] == ['c1.plain']


def test_orders_the_snapshot_by_path() -> None:
    replies = {'c1.plain': reply('StringReply', 'b'), 'c1.opt': reply('AnswerReply', NO)}

    assert [stored.path for stored in build_snapshot(KM, replies)] == ['c1.opt', 'c1.plain']
