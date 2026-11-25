import copy
from typing import Any
from uuid import UUID

from ai_document_plugin_service.ai.knowledgemodel.questionnaire_diff import (
    ChangeKind,
    describe_changes,
    diff_replies,
)
from ai_document_plugin_service.ai.knowledgemodel.questionnaire_snapshot import (
    ReplyType,
    StoredReply,
    build_snapshot,
)


def u(number: int) -> str:
    return str(UUID(int=number))


YES, NO = u(1), u(2)
ITEM_1, ITEM_2 = u(5), u(6)
USER = {'firstName': 'Ada', 'lastName': 'Lovelace'}

KM = {
    'chapterUuids': ['c1'],
    'entities': {
        'chapters': {'c1': {'title': 'Data', 'questionUuids': ['opt', 'items', 'pick', 'plain']}},
        'questions': {
            'opt': {'questionType': 'OptionsQuestion', 'title': 'Reuse?'},
            'items': {'questionType': 'ListQuestion', 'title': 'Datasets', 'itemTemplateQuestionUuids': ['name', 'fmt']},
            'name': {'questionType': 'ValueQuestion', 'title': 'Name'},
            'fmt': {'questionType': 'ValueQuestion', 'title': 'Format'},
            'pick': {'questionType': 'ItemSelectQuestion', 'title': 'Main dataset', 'listQuestionUuid': 'items'},
            'plain': {'questionType': 'ValueQuestion', 'title': 'Notes'},
        },
        'answers': {YES: {'label': 'Yes', 'followUpUuids': []}, NO: {'label': 'No', 'followUpUuids': []}},
        'choices': {},
    },
}


def reply(reply_type: str, value: Any, by: dict[str, str] | None = None) -> dict[str, Any]:
    return {'value': {'type': reply_type, 'value': value}, 'createdAt': '2026-11-20T10:00:00Z', 'createdBy': by}


def text(path: str, value: str) -> StoredReply:
    return StoredReply(path, ReplyType.STRING, text_value=value)


def describe(old_replies: dict[str, Any], new_replies: dict[str, Any], km: dict[str, Any] | None = None) -> list:
    stored = build_snapshot(KM, old_replies)
    return describe_changes(stored, {'knowledgeModel': km or KM, 'replies': new_replies})


def test_diff_reports_added_changed_and_removed_replies_ordered_by_path() -> None:
    old = [text('a', 'same'), text('b', 'before'), text('c', 'gone')]
    new = [text('a', 'same'), text('b', 'after'), text('d', 'new')]

    changes = diff_replies(old, new)

    assert [(change.path, change.kind) for change in changes] == [
        ('b', ChangeKind.CHANGED),
        ('c', ChangeKind.REMOVED),
        ('d', ChangeKind.ADDED),
    ]


def test_diff_of_identical_snapshots_is_empty() -> None:
    assert diff_replies([text('a', 'same')], [text('a', 'same')]) == []


def test_diff_ignores_the_stored_label_since_it_is_not_part_of_the_value() -> None:
    old = StoredReply('a', ReplyType.ANSWER, uuid_value=UUID(YES), display_text='Yes')
    new = StoredReply('a', ReplyType.ANSWER, uuid_value=UUID(YES), display_text='Ano')

    assert diff_replies([old], [new]) == []


def test_diff_sees_a_reordered_item_list_as_a_change() -> None:
    old = StoredReply('l', ReplyType.ITEM_LIST, uuid_values=(UUID(ITEM_1), UUID(ITEM_2)))
    new = StoredReply('l', ReplyType.ITEM_LIST, uuid_values=(UUID(ITEM_2), UUID(ITEM_1)))

    assert [change.kind for change in diff_replies([old], [new])] == [ChangeKind.CHANGED]


def test_describes_a_changed_text_with_titles_values_and_who_changed_it() -> None:
    old = {'c1.plain': reply('StringReply', 'before')}
    new = {'c1.plain': reply('StringReply', 'after', by=USER)}

    [change] = describe(old, new)

    assert (change.kind, change.chapter_title, change.question_title) == (ChangeKind.CHANGED, 'Data', 'Notes')
    assert (change.old_value, change.new_value) == ('before', 'after')
    assert (change.changed_by, change.changed_at) == ('Ada Lovelace', '2026-11-20T10:00:00Z')


def test_describes_answers_by_their_labels() -> None:
    [change] = describe({'c1.opt': reply('AnswerReply', YES)}, {'c1.opt': reply('AnswerReply', NO)})

    assert (change.old_value, change.new_value) == ('Yes', 'No')


def test_a_removed_answer_has_no_new_value_and_no_author() -> None:
    [change] = describe({'c1.plain': reply('StringReply', 'before')}, {})

    assert (change.kind, change.old_value, change.new_value) == (ChangeKind.REMOVED, 'before', None)
    assert (change.changed_by, change.changed_at) == (None, None)


def test_an_answer_the_knowledge_model_no_longer_has_falls_back_to_the_stored_label() -> None:
    km_without_yes = copy.deepcopy(KM)
    del km_without_yes['entities']['answers'][YES]

    [change] = describe({'c1.opt': reply('AnswerReply', YES)}, {'c1.opt': reply('AnswerReply', NO)}, km_without_yes)

    assert change.old_value == 'Yes'


def test_a_question_inside_a_list_item_is_described_with_the_title_of_the_item() -> None:
    old = {'c1.items': reply('ItemListReply', [ITEM_1]), f'c1.items.{ITEM_1}.name': reply('StringReply', 'Survey')}
    new = {
        **old,
        f'c1.items.{ITEM_1}.fmt': reply('StringReply', 'csv'),
    }

    [change] = describe(old, new)

    assert (change.kind, change.question_title, change.context) == (ChangeKind.ADDED, 'Format', ['Survey'])


def test_an_added_item_is_described_by_the_titles_of_the_items() -> None:
    old = {'c1.items': reply('ItemListReply', [ITEM_1]), f'c1.items.{ITEM_1}.name': reply('StringReply', 'Survey')}
    new = {
        'c1.items': reply('ItemListReply', [ITEM_1, ITEM_2]),
        f'c1.items.{ITEM_1}.name': reply('StringReply', 'Survey'),
        f'c1.items.{ITEM_2}.name': reply('StringReply', 'Interviews'),
    }

    changes = {change.path: change for change in describe(old, new)}

    assert changes['c1.items'].old_value == 'Survey'
    assert changes['c1.items'].new_value == 'Survey, Interviews'
    assert changes[f'c1.items.{ITEM_2}.name'].kind == ChangeKind.ADDED


def test_an_item_without_a_title_answer_is_called_untitled() -> None:
    new = {'c1.items': reply('ItemListReply', [ITEM_1])}

    [change] = describe({}, new)

    assert change.new_value == 'Untitled item'


def test_an_item_select_is_described_by_the_title_of_the_selected_item() -> None:
    items = {'c1.items': reply('ItemListReply', [ITEM_1, ITEM_2])}
    titles = {
        f'c1.items.{ITEM_1}.name': reply('StringReply', 'Survey'),
        f'c1.items.{ITEM_2}.name': reply('StringReply', 'Interviews'),
    }
    old = {**items, **titles, 'c1.pick': reply('ItemSelectReply', ITEM_1)}
    new = {**items, **titles, 'c1.pick': reply('ItemSelectReply', ITEM_2)}

    [change] = describe(old, new)

    assert (change.old_value, change.new_value) == ('Survey', 'Interviews')


def test_nothing_is_reported_when_only_unreachable_replies_differ() -> None:
    old = {'c1.opt': reply('AnswerReply', NO)}
    new = {'c1.opt': reply('AnswerReply', NO), f'c1.opt.{YES}.why': reply('StringReply', 'left over')}

    assert describe(old, new) == []
