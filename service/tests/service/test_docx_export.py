import io

import docx
import pytest
from docx.document import Document
from docx.text.paragraph import Paragraph

from ai_document_plugin_service.service.docx_export import markdown_to_docx


def _render(markdown: str) -> Document:
    return docx.Document(io.BytesIO(markdown_to_docx(markdown)))


def _style_name(paragraph: Paragraph) -> str | None:
    return paragraph.style.name if paragraph.style is not None else None


def _styles(document: Document) -> list[str | None]:
    return [_style_name(paragraph) for paragraph in document.paragraphs if paragraph.text]


def test_headings_use_word_heading_styles() -> None:
    document = _render('# Title\n\n## Section\n\n###### Deep')

    assert _styles(document) == ['Heading 1', 'Heading 2', 'Heading 6']
    assert [paragraph.text for paragraph in document.paragraphs if paragraph.text] == [
        'Title',
        'Section',
        'Deep',
    ]


def test_inline_formatting_maps_to_runs() -> None:
    document = _render('Plain **bold** and *italic* and ~~struck~~ and `code`.')

    runs = {run.text: run for run in document.paragraphs[0].runs}
    assert runs['bold'].bold is True
    assert runs['italic'].italic is True
    assert runs['struck'].font.strike is True
    assert runs['code'].font.name == 'Consolas'
    # Formatting is only ever switched on, never explicitly off, so styles keep inheriting.
    assert runs['Plain '].bold is None


def test_heading_runs_do_not_disable_inherited_bold() -> None:
    document = _render('# Title with **bold**')

    assert all(run.bold in (None, True) for run in document.paragraphs[0].runs)


def test_nested_emphasis_combines_formats() -> None:
    document = _render('***both***')

    run = document.paragraphs[0].runs[0]
    assert (run.bold, run.italic) == (True, True)


def test_soft_break_becomes_a_space_in_one_paragraph() -> None:
    document = _render('first\nsecond')

    assert [paragraph.text for paragraph in document.paragraphs if paragraph.text] == ['first second']


def test_link_keeps_its_target_as_visible_text() -> None:
    # python-docx cannot write clickable links, so the URL must not be silently dropped.
    document = _render('See [the guide](https://example.org/guide).')

    assert document.paragraphs[0].text == 'See the guide (https://example.org/guide).'


def test_link_whose_text_is_already_the_url_is_not_repeated() -> None:
    document = _render('[https://example.org](https://example.org)')

    assert document.paragraphs[0].text == 'https://example.org'


def test_lists_use_built_in_list_styles() -> None:
    document = _render('- one\n- two\n\ntext\n\n1. first\n2. second')

    assert _styles(document) == [
        'List Bullet',
        'List Bullet',
        'Normal',
        'List Number',
        'List Number',
    ]


def test_nested_lists_step_through_the_style_levels() -> None:
    document = _render('- top\n    - nested\n        - deeper')

    assert _styles(document) == ['List Bullet', 'List Bullet 2', 'List Bullet 3']


def test_list_nesting_deeper_than_three_levels_is_clamped() -> None:
    markdown = '\n'.join(f'{" " * (4 * depth)}- level {depth}' for depth in range(6))
    document = _render(markdown)

    assert _styles(document)[-3:] == ['List Bullet 3', 'List Bullet 3', 'List Bullet 3']


def test_loose_list_item_continuation_is_not_bulleted_again() -> None:
    document = _render('- first para\n\n  second para\n\n- next item')

    assert _styles(document) == ['List Bullet', 'List Continue', 'List Bullet']


def test_consecutive_ordered_lists_share_one_counter() -> None:
    """Documents a known limitation of mapping onto Word's built-in `List Number` style.

    Word gives that style a single numbering definition, so a second list continues 3., 4.
    rather than restarting at 1. Restarting would mean writing numbering XML by hand, which
    this module deliberately avoids. The test exists so the behaviour is a recorded choice
    rather than a surprise.
    """
    document = _render('1. one\n\ntext\n\n1. alpha')

    assert _styles(document) == ['List Number', 'Normal', 'List Number']


def test_table_renders_with_bold_header() -> None:
    document = _render('| Name | Size |\n| --- | ---: |\n| disk | 10 |\n| tape | 20 |')

    table = document.tables[0]
    assert (len(table.rows), len(table.columns)) == (3, 2)
    assert table.cell(0, 0).text == 'Name'
    assert table.cell(2, 1).text == '20'
    assert all(run.bold for run in table.cell(0, 0).paragraphs[0].runs)
    assert not any(run.bold for run in table.cell(1, 0).paragraphs[0].runs)


def test_table_cell_keeps_inline_formatting() -> None:
    document = _render('| a |\n| --- |\n| **strong** |')

    assert document.tables[0].cell(1, 0).paragraphs[0].runs[0].bold is True


def test_fenced_code_keeps_one_paragraph_per_line() -> None:
    document = _render('```python\nfirst = 1\nsecond = 2\n```')

    code = [
        paragraph.text
        for paragraph in document.paragraphs
        if paragraph.runs and paragraph.runs[0].font.name == 'Consolas'
    ]
    assert code == ['first = 1', 'second = 2']


def test_blockquote_uses_the_quote_style() -> None:
    document = _render('> quoted text')

    assert _styles(document) == ['Quote']


def test_horizontal_rule_is_written_as_a_visible_line() -> None:
    document = _render('above\n\n---\n\nbelow')

    texts = [paragraph.text for paragraph in document.paragraphs if paragraph.text]
    assert texts[0] == 'above'
    assert set(texts[1]) == {'―'}
    assert texts[2] == 'below'


def test_raw_html_is_kept_as_literal_text_not_interpreted() -> None:
    document = _render('<script>alert(1)</script>')

    assert 'alert(1)' in '\n'.join(paragraph.text for paragraph in document.paragraphs)


def test_image_falls_back_to_alt_text() -> None:
    document = _render('![a diagram](https://example.org/x.png)')

    assert document.paragraphs[0].text.startswith('[a diagram]')


def test_title_is_stored_as_document_metadata() -> None:
    document = docx.Document(io.BytesIO(markdown_to_docx('# Body', title='My Plan')))

    assert document.core_properties.title == 'My Plan'


@pytest.mark.parametrize('markdown', ['', '   \n\n  '])
def test_empty_markdown_still_produces_a_readable_file(markdown: str) -> None:
    document = _render(markdown)

    assert all(not paragraph.text for paragraph in document.paragraphs)
