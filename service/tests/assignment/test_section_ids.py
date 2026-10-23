from uuid import UUID

from ai_document_plugin_service.ai.assignment.mappers import template_sections_to_records
from ai_document_plugin_service.ai.assignment.section_tree import collect_leaf_sections
from ai_document_plugin_service.ai.assignment.sections.sections_formatter import SectionFormatter
from ai_document_plugin_service.ai.common.types import TemplateContent

RAW_TEMPLATE = {
    'sections': [
        {'title': 'Intro', 'content': 'Introduce the project.'},
        {'title': 'Parent', 'content': 'Data handling.', 'sections': [{'title': 'First child'}, {'title': 'Second child'}]},
    ],
}
TEMPLATE = TemplateContent.model_validate(RAW_TEMPLATE)


def _leaf_ids(template: TemplateContent) -> list[UUID]:
    return [leaf.id for leaf in collect_leaf_sections(template_sections_to_records(template.sections))]


def _edited(path: list[int], **changes: str) -> TemplateContent:
    raw = TEMPLATE.model_dump(mode='json', exclude_unset=True)
    node = raw
    for index in path:
        node = node['sections'][index]
    node.update(changes)
    return TemplateContent.model_validate(raw)


def test_section_ids_are_stable_for_unchanged_templates():
    assert _leaf_ids(TEMPLATE) == _leaf_ids(TemplateContent.model_validate(RAW_TEMPLATE))


def test_editing_a_leaf_changes_only_its_id():
    intro, first_child, second_child = _leaf_ids(TEMPLATE)

    new_intro, new_first_child, new_second_child = _leaf_ids(_edited([1, 0], content='New guidance.'))

    assert new_intro == intro
    assert new_first_child != first_child
    assert new_second_child == second_child


def test_editing_a_parent_changes_the_ids_of_its_leaves():
    intro, first_child, second_child = _leaf_ids(TEMPLATE)

    new_intro, new_first_child, new_second_child = _leaf_ids(_edited([1], title='Renamed parent'))

    assert new_intro == intro
    assert new_first_child != first_child
    assert new_second_child != second_child


def test_whitespace_around_content_does_not_change_ids():
    assert _leaf_ids(_edited([0], content='  Introduce the project.\n')) == _leaf_ids(TEMPLATE)
    assert _leaf_ids(_edited([1, 0], content='   ')) == _leaf_ids(TEMPLATE)


def test_identical_leaves_share_an_id_and_an_sid():
    template = TemplateContent.model_validate({'sections': [{'title': 'Same'}, {'title': 'Same'}, {'title': 'Other'}]})
    sections = template_sections_to_records(template.sections)
    same, same_again, other = collect_leaf_sections(sections)

    formatter = SectionFormatter(sections)

    assert same.id == same_again.id
    assert formatter.id_to_sid == {same.id: 'A', other.id: 'B'}


def test_only_assignable_leaves_get_an_sid_in_the_xml():
    sections = template_sections_to_records(TEMPLATE.sections)
    _intro, first_child, _second_child = collect_leaf_sections(sections)

    xml = SectionFormatter(sections, assignable_ids={first_child.id}).get_sections_as_xml()

    assert xml.count(' id="') == 1
    assert '<section id="A">\n<title>First child</title>' in xml
    assert '<title>Intro</title>' in xml
