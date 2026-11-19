import pytest

from ai_document_plugin_service.ai.common.source_ids import build_source_ids, restore_source_paths


def test_ids_are_stable_unique_and_distinguish_list_items() -> None:
    paths = ['ch.list.item2.question', 'ch.list.item1.question', 'ch.list.item2.question']
    assert build_source_ids(paths) == {
        'ch.list.item1.question': 'q1',
        'ch.list.item2.question': 'q2',
    }
    assert build_source_ids(reversed(paths)) == build_source_ids(paths)
    assert build_source_ids([]) == {}


def test_restore_changes_only_source_attributes_and_removes_duplicates() -> None:
    markdown = """# q1

<statement source="q2 q1 q2">**q1** and [q2](https://example.org/q1).</statement>
<statement source='q1'>Another sentence.</statement>"""
    assert (
        restore_source_paths(markdown, {'ch.a': 'q1', 'ch.b': 'q2'})
        == """# q1

<statement source="ch.b ch.a">**q1** and [q2](https://example.org/q1).</statement>
<statement source='ch.a'>Another sentence.</statement>"""
    )


@pytest.mark.parametrize('source', ['q99', 'q1 q99', 'ch.a', ''])
def test_restore_rejects_unknown_or_empty_sources(source: str) -> None:
    with pytest.raises(ValueError, match='source'):
        restore_source_paths(f'<statement source="{source}">Text.</statement>', {'ch.a': 'q1'})


def test_plain_markdown_is_unchanged() -> None:
    assert restore_source_paths('# Title\n\nNo data', {}) == '# Title\n\nNo data'
