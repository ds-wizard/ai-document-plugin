from ai_document_plugin_service.ai.knowledgemodel.list_items import find_list_path


def items(*uuids: str) -> dict[str, object]:
    return {'type': 'ItemListReply', 'value': list(uuids)}


def test_finds_a_list_anywhere_in_the_questionnaire() -> None:
    replies = [('c1.other.a1.list', items('i1')), ('c2.deep.pick', {'type': 'ItemSelectReply', 'value': 'i1'})]

    assert find_list_path('list', 'i1', replies) == 'c1.other.a1.list'


def test_picks_the_reply_that_holds_the_item_when_the_list_is_repeated() -> None:
    replies = [('c1.outer.o1.list', items('i1')), ('c1.outer.o2.list', items('i2'))]

    assert find_list_path('list', 'i2', replies) == 'c1.outer.o2.list'


def test_ignores_other_lists_and_non_list_replies() -> None:
    replies = [
        ('c1.mylist', items('i1')),
        ('c1.list', {'type': 'StringReply', 'value': 'i1'}),
    ]

    assert find_list_path('list', 'i1', replies) is None


def test_returns_none_for_an_item_no_list_holds() -> None:
    assert find_list_path('list', 'gone', [('c1.list', items('i1'))]) is None
