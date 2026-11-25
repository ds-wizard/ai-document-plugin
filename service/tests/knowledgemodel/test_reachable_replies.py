from typing import Any

from ai_document_plugin_service.ai.knowledgemodel.reachable_replies import reachable_replies

# c1
#   opt (options): a1 -> f1 (value), a2 -> f2 (value)
#   items (list): item template t1 (value) and nested (list) with item template n1 (value)
#   plain (value)
KM = {
    'chapterUuids': ['c1'],
    'entities': {
        'chapters': {'c1': {'questionUuids': ['opt', 'items', 'plain']}},
        'questions': {
            'opt': {'questionType': 'OptionsQuestion', 'answerUuids': ['a1', 'a2']},
            'f1': {'questionType': 'ValueQuestion'},
            'f2': {'questionType': 'ValueQuestion'},
            'items': {'questionType': 'ListQuestion', 'itemTemplateQuestionUuids': ['t1', 'nested']},
            't1': {'questionType': 'ValueQuestion'},
            'nested': {'questionType': 'ListQuestion', 'itemTemplateQuestionUuids': ['n1']},
            'n1': {'questionType': 'ValueQuestion'},
            'plain': {'questionType': 'ValueQuestion'},
        },
        'answers': {
            'a1': {'followUpUuids': ['f1']},
            'a2': {'followUpUuids': ['f2']},
        },
    },
}


def _reply(reply_type: str, value: Any) -> dict[str, Any]:
    return {'value': {'type': reply_type, 'value': value}, 'createdAt': '2026-11-20T10:00:00Z', 'createdBy': None}


def _text(value: str) -> dict[str, Any]:
    return _reply('StringReply', value)


def test_keeps_a_reply_of_a_chapter_question() -> None:
    replies = {'c1.plain': _text('kept')}

    assert reachable_replies(KM, replies) == replies


def test_keeps_the_order_of_the_replies() -> None:
    replies = {
        'c1.items.i2.t1': _text('second item'),
        'c1.plain': _text('plain'),
        'c1.items': _reply('ItemListReply', ['i1', 'i2']),
        'c1.items.i1.t1': _text('first item'),
    }

    assert list(reachable_replies(KM, replies)) == list(replies)


def test_keeps_the_reply_object_untouched() -> None:
    replies = {'c1.plain': _text('kept')}

    assert reachable_replies(KM, replies)['c1.plain'] is replies['c1.plain']


def test_keeps_follow_ups_of_the_selected_answer_only() -> None:
    replies = {
        'c1.opt': _reply('AnswerReply', 'a1'),
        'c1.opt.a1.f1': _text('applies'),
        'c1.opt.a2.f2': _text('left over from an earlier answer'),
    }

    assert set(reachable_replies(KM, replies)) == {'c1.opt', 'c1.opt.a1.f1'}


def test_follow_ups_of_an_unanswered_options_question_are_unreachable() -> None:
    replies = {'c1.opt.a1.f1': _text('left over')}

    assert reachable_replies(KM, replies) == {}


def test_follow_ups_are_unreachable_when_the_options_reply_has_another_type() -> None:
    replies = {'c1.opt': _text('not an answer'), 'c1.opt.a1.f1': _text('left over')}

    assert set(reachable_replies(KM, replies)) == {'c1.opt'}


def test_keeps_replies_of_listed_items_only() -> None:
    replies = {
        'c1.items': _reply('ItemListReply', ['i1']),
        'c1.items.i1.t1': _text('listed'),
        'c1.items.i2.t1': _text('deleted item'),
    }

    assert set(reachable_replies(KM, replies)) == {'c1.items', 'c1.items.i1.t1'}


def test_a_list_without_a_reply_has_no_reachable_items() -> None:
    replies = {'c1.items.i1.t1': _text('left over')}

    assert reachable_replies(KM, replies) == {}


def test_follows_lists_nested_in_items() -> None:
    replies = {
        'c1.items': _reply('ItemListReply', ['i1', 'i2']),
        'c1.items.i1.nested': _reply('ItemListReply', ['n']),
        'c1.items.i1.nested.n.n1': _text('listed'),
        'c1.items.i1.nested.gone.n1': _text('deleted nested item'),
        'c1.items.i2.nested.n.n1': _text('item i2 has no nested list reply'),
    }

    assert set(reachable_replies(KM, replies)) == {
        'c1.items',
        'c1.items.i1.nested',
        'c1.items.i1.nested.n.n1',
    }


def test_drops_a_reply_to_a_question_that_is_not_in_the_knowledge_model() -> None:
    replies = {'c1.removed': _text('question no longer exists'), 'c1.plain': _text('kept')}

    assert set(reachable_replies(KM, replies)) == {'c1.plain'}


def test_drops_a_reply_under_the_wrong_chapter() -> None:
    replies = {'other.plain': _text('wrong chapter')}

    assert reachable_replies(KM, replies) == {}
