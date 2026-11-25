import contextlib
import copy
from collections.abc import Iterable
from typing import Any
from uuid import UUID

from ai_document_plugin_service.ai.knowledgemodel.questionnaire_diff import (
    NO_LONGER_IN_QUESTIONNAIRE,
    ChangeKind,
    ChangeNode,
    NodeKind,
    ValueChange,
    change_tree,
    diff_replies,
)
from ai_document_plugin_service.ai.knowledgemodel.questionnaire_snapshot import StoredReply, build_snapshot


def u(number: int) -> str:
    return str(UUID(int=number))


YES, NO = u(1), u(2)
ITEM_1, ITEM_2 = u(5), u(6)

KM: dict[str, Any] = {
    'chapterUuids': ['c1'],
    'entities': {
        'chapters': {'c1': {'title': 'Data', 'questionUuids': ['opt', 'items', 'pick', 'plain']}},
        'questions': {
            'opt': {'questionType': 'OptionsQuestion', 'title': 'Reuse?'},
            'why': {'questionType': 'ValueQuestion', 'title': 'Why?'},
            'items': {
                'questionType': 'ListQuestion',
                'title': 'Datasets',
                'itemTemplateQuestionUuids': ['name', 'fmt'],
            },
            'name': {'questionType': 'ValueQuestion', 'title': 'Name'},
            'fmt': {'questionType': 'ValueQuestion', 'title': 'Format'},
            'pick': {'questionType': 'ItemSelectQuestion', 'title': 'Main dataset', 'listQuestionUuid': 'items'},
            'plain': {'questionType': 'ValueQuestion', 'title': 'Notes'},
        },
        'answers': {YES: {'label': 'Yes', 'followUpUuids': ['why']}, NO: {'label': 'No', 'followUpUuids': []}},
        'choices': {},
    },
}


def reply(reply_type: str, value: Any) -> dict[str, Any]:
    return {'value': {'type': reply_type, 'value': value}, 'createdAt': '2026-11-20T10:00:00Z', 'createdBy': None}


def text(path: str, value: str) -> StoredReply:
    return StoredReply(path, {'type': 'StringReply', 'value': value})


def tree(
    old_replies: dict[str, Any],
    new_replies: dict[str, Any],
    km: dict[str, Any] | None = None,
) -> list[ChangeNode]:
    stored = build_snapshot(KM, old_replies)
    return change_tree(stored, {'knowledgeModel': km or KM, 'replies': new_replies})


def outline(nodes: Iterable[ChangeNode], depth: int = 0) -> list[tuple[int, str | None, ChangeKind | None]]:
    """The tree as (depth, title, kind of change) lines, in order."""
    lines: list[tuple[int, str | None, ChangeKind | None]] = []
    for node in nodes:
        lines.append((depth, node.title, node.change.kind if node.change else None))
        lines.extend(outline(node.children, depth + 1))
    return lines


def find(nodes: Iterable[ChangeNode], path: str) -> ChangeNode:
    for node in nodes:
        if node.path == path:
            return node
        with contextlib.suppress(LookupError):
            return find(node.children, path)
    raise LookupError(path)


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
    old = StoredReply('a', {'type': 'AnswerReply', 'value': YES}, display_text='Yes')
    new = StoredReply('a', {'type': 'AnswerReply', 'value': YES}, display_text='Ano')

    assert diff_replies([old], [new]) == []


def test_diff_sees_a_reordered_item_list_as_a_change() -> None:
    old = StoredReply('l', {'type': 'ItemListReply', 'value': [ITEM_1, ITEM_2]})
    new = StoredReply('l', {'type': 'ItemListReply', 'value': [ITEM_2, ITEM_1]})

    assert [change.kind for change in diff_replies([old], [new])] == [ChangeKind.CHANGED]


def test_diff_sees_a_changed_integration_record_with_the_same_text_as_a_change() -> None:
    def zenodo(record_id: int) -> StoredReply:
        value = {'type': 'IntegrationType', 'value': 'Zenodo', 'raw': {'id': record_id}}
        return StoredReply('i', {'type': 'IntegrationReply', 'value': value})

    old, new = zenodo(1), zenodo(2)

    assert [change.kind for change in diff_replies([old], [new])] == [ChangeKind.CHANGED]


def test_a_changed_text_sits_under_its_chapter_with_both_values() -> None:
    old = {'c1.plain': reply('StringReply', 'before')}
    new = {'c1.plain': reply('StringReply', 'after')}

    assert tree(old, new) == [
        ChangeNode(
            'c1',
            NodeKind.CHAPTER,
            'Data',
            children=(
                ChangeNode(
                    'c1.plain',
                    NodeKind.QUESTION,
                    'Notes',
                    change=ValueChange(ChangeKind.CHANGED, 'before', 'after'),
                ),
            ),
        ),
    ]


def test_describes_integration_replies_by_their_text() -> None:
    old = {'c1.plain': reply('IntegrationReply', {'type': 'IntegrationType', 'value': 'Zenodo', 'raw': {'id': 1}})}
    new = {'c1.plain': reply('IntegrationReply', {'type': 'PlainType', 'value': 'Dryad'})}

    change = find(tree(old, new), 'c1.plain').change

    assert change == ValueChange(ChangeKind.CHANGED, 'Zenodo', 'Dryad')


def test_describes_answers_by_their_labels() -> None:
    change = find(tree({'c1.opt': reply('AnswerReply', YES)}, {'c1.opt': reply('AnswerReply', NO)}), 'c1.opt').change

    assert change == ValueChange(ChangeKind.CHANGED, 'Yes', 'No')


def test_a_removed_answer_has_no_new_value() -> None:
    change = find(tree({'c1.plain': reply('StringReply', 'before')}, {}), 'c1.plain').change

    assert change == ValueChange(ChangeKind.REMOVED, 'before', None)


def test_an_answer_the_knowledge_model_no_longer_has_falls_back_to_the_stored_label() -> None:
    km_without_yes = copy.deepcopy(KM)
    del km_without_yes['entities']['answers'][YES]

    nodes = tree({'c1.opt': reply('AnswerReply', YES)}, {'c1.opt': reply('AnswerReply', NO)}, km_without_yes)

    assert find(nodes, 'c1.opt').change == ValueChange(ChangeKind.CHANGED, 'Yes', 'No')


def test_follows_the_order_of_the_questionnaire_not_of_the_paths() -> None:
    km = copy.deepcopy(KM)
    km['entities']['chapters']['c1']['questionUuids'] = ['plain', 'opt', 'items', 'pick']
    old = {'c1.opt': reply('AnswerReply', NO), 'c1.plain': reply('StringReply', 'before')}
    new = {'c1.opt': reply('AnswerReply', YES), 'c1.plain': reply('StringReply', 'after')}

    assert [title for _, title, _ in outline(tree(old, new, km))] == ['Data', 'Notes', 'Reuse?']


def test_a_question_inside_a_list_item_sits_under_the_list_and_the_item() -> None:
    old = {'c1.items': reply('ItemListReply', [ITEM_1]), f'c1.items.{ITEM_1}.name': reply('StringReply', 'Survey')}
    new = {**old, f'c1.items.{ITEM_1}.fmt': reply('StringReply', 'csv')}

    assert outline(tree(old, new)) == [
        (0, 'Data', None),
        (1, 'Datasets', None),
        (2, 'Survey', None),
        (3, 'Format', ChangeKind.ADDED),
    ]
    assert find(tree(old, new), f'c1.items.{ITEM_1}').kind == NodeKind.ITEM


def test_a_changed_follow_up_shows_the_answer_of_its_unchanged_question() -> None:
    old = {'c1.opt': reply('AnswerReply', YES)}
    new = {**old, f'c1.opt.{YES}.why': reply('StringReply', 'Public data')}

    question = find(tree(old, new), 'c1.opt')

    assert (question.change, question.answer) == (None, 'Yes')
    assert [child.path for child in question.children] == [f'c1.opt.{YES}.why']


def test_a_changed_answer_is_shown_once_with_the_follow_ups_of_the_old_answer_under_it() -> None:
    old = {'c1.opt': reply('AnswerReply', YES), f'c1.opt.{YES}.why': reply('StringReply', 'Public data')}
    new = {'c1.opt': reply('AnswerReply', NO)}

    assert outline(tree(old, new)) == [
        (0, 'Data', None),
        (1, 'Reuse?', ChangeKind.CHANGED),
        (2, 'Why?', ChangeKind.REMOVED),
    ]
    assert find(tree(old, new), 'c1.opt').answer is None


def test_an_added_item_is_shown_under_the_changed_list() -> None:
    old = {'c1.items': reply('ItemListReply', [ITEM_1]), f'c1.items.{ITEM_1}.name': reply('StringReply', 'Survey')}
    new = {
        'c1.items': reply('ItemListReply', [ITEM_1, ITEM_2]),
        f'c1.items.{ITEM_1}.name': reply('StringReply', 'Survey'),
        f'c1.items.{ITEM_2}.name': reply('StringReply', 'Interviews'),
    }

    nodes = tree(old, new)

    assert find(nodes, 'c1.items').change == ValueChange(ChangeKind.CHANGED, 'Survey', 'Survey, Interviews')
    assert outline(nodes)[2:] == [(2, 'Interviews', None), (3, 'Name', ChangeKind.ADDED)]


def test_a_deleted_item_keeps_its_place_and_its_old_title() -> None:
    old = {
        'c1.items': reply('ItemListReply', [ITEM_1, ITEM_2]),
        f'c1.items.{ITEM_1}.name': reply('StringReply', 'Survey'),
        f'c1.items.{ITEM_2}.name': reply('StringReply', 'Interviews'),
    }
    new = {
        'c1.items': reply('ItemListReply', [ITEM_1]),
        f'c1.items.{ITEM_1}.name': reply('StringReply', 'Survey 2025'),
    }

    assert outline(tree(old, new))[1:] == [
        (1, 'Datasets', ChangeKind.CHANGED),
        (2, 'Survey 2025', None),
        (3, 'Name', ChangeKind.CHANGED),
        (2, 'Interviews', None),
        (3, 'Name', ChangeKind.REMOVED),
    ]


def test_an_item_without_a_title_answer_is_called_untitled() -> None:
    nodes = tree({}, {'c1.items': reply('ItemListReply', [ITEM_1])})

    assert find(nodes, 'c1.items').change == ValueChange(ChangeKind.ADDED, None, 'Untitled item')


def test_an_item_select_is_described_by_the_title_of_the_selected_item() -> None:
    items = {'c1.items': reply('ItemListReply', [ITEM_1, ITEM_2])}
    titles = {
        f'c1.items.{ITEM_1}.name': reply('StringReply', 'Survey'),
        f'c1.items.{ITEM_2}.name': reply('StringReply', 'Interviews'),
    }
    old = {**items, **titles, 'c1.pick': reply('ItemSelectReply', ITEM_1)}
    new = {**items, **titles, 'c1.pick': reply('ItemSelectReply', ITEM_2)}

    assert find(tree(old, new), 'c1.pick').change == ValueChange(ChangeKind.CHANGED, 'Survey', 'Interviews')


def test_an_item_select_finds_its_list_outside_its_own_parent() -> None:
    km = copy.deepcopy(KM)
    km['chapterUuids'] = ['c1', 'c2']
    km['entities']['chapters']['c1']['questionUuids'].remove('pick')
    km['entities']['chapters']['c2'] = {'title': 'Use', 'questionUuids': ['pick']}
    items = {'c1.items': reply('ItemListReply', [ITEM_1, ITEM_2])}
    titles = {
        f'c1.items.{ITEM_1}.name': reply('StringReply', 'Survey'),
        f'c1.items.{ITEM_2}.name': reply('StringReply', 'Interviews'),
    }
    old = {**items, **titles, 'c2.pick': reply('ItemSelectReply', ITEM_1)}
    new = {**items, **titles, 'c2.pick': reply('ItemSelectReply', ITEM_2)}

    stored = build_snapshot(km, old)
    nodes = change_tree(stored, {'knowledgeModel': km, 'replies': new})

    assert find(nodes, 'c2.pick').change == ValueChange(ChangeKind.CHANGED, 'Survey', 'Interviews')


def test_a_reply_to_a_question_the_knowledge_model_no_longer_has_goes_into_a_last_group() -> None:
    km_without_notes = copy.deepcopy(KM)
    del km_without_notes['entities']['questions']['plain']
    km_without_notes['entities']['chapters']['c1']['questionUuids'].remove('plain')
    old = {'c1.opt': reply('AnswerReply', YES), 'c1.plain': reply('StringReply', 'gone')}
    new = {'c1.opt': reply('AnswerReply', NO)}

    nodes = tree(old, new, km_without_notes)

    assert [(node.path, node.title) for node in nodes] == [('c1', 'Data'), ('', NO_LONGER_IN_QUESTIONNAIRE)]
    assert nodes[-1].children == (
        ChangeNode('c1.plain', NodeKind.QUESTION, None, change=ValueChange(ChangeKind.REMOVED, 'gone', None)),
    )


def test_nothing_is_reported_when_only_unreachable_replies_differ() -> None:
    old = {'c1.opt': reply('AnswerReply', NO)}
    new = {'c1.opt': reply('AnswerReply', NO), f'c1.opt.{YES}.why': reply('StringReply', 'left over')}

    assert tree(old, new) == []
