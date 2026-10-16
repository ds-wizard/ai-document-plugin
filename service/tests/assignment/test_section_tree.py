import uuid
from uuid import UUID

from ai_document_plugin_service.ai.assignment.section_tree import (
    collect_leaf_sections,
    render_section_tree_as_xml,
)
from ai_document_plugin_service.ai.assignment.types import SectionRecord
from ai_document_plugin_service.ai.common.types import TemplateSection


def test_collect_leaf_sections_preserves_tree_order() -> None:
    records = [
        SectionRecord(
            id=uuid.uuid4(),
            title='Parent',
            section=TemplateSection(title='Parent', content='Parent content'),
            children=[
                SectionRecord(
                    id=uuid.uuid4(), title='Leaf A', section=TemplateSection(title='Leaf A', content='Alpha')
                ),
                SectionRecord(id=uuid.uuid4(), title='Leaf B', section=TemplateSection(title='Leaf B', content='Beta')),
            ],
        ),
        SectionRecord(id=uuid.uuid4(), title='Leaf C', section=TemplateSection(title='Leaf C', content='Gamma')),
    ]
    leaves = collect_leaf_sections(records)

    assert [leaf.title for leaf in leaves] == ['Leaf A', 'Leaf B', 'Leaf C']
    ids = [leaf.id for leaf in leaves]
    assert len(set(ids)) == len(ids)
    assert all(isinstance(rec_id, UUID) for rec_id in ids)


def test_collect_leaf_section_duplicate_title() -> None:
    records = [
        SectionRecord(
            id=uuid.uuid4(),
            title='Parent',
            section=TemplateSection(title='Parent', content='Parent content'),
            children=[
                SectionRecord(
                    id=uuid.uuid4(), title='Leaf A', section=TemplateSection(title='Leaf A', content='Alpha')
                ),
                SectionRecord(id=uuid.uuid4(), title='Leaf B', section=TemplateSection(title='Leaf B', content='Beta')),
            ],
        ),
        SectionRecord(id=uuid.uuid4(), title='Leaf A', section=TemplateSection(title='Leaf A', content='Gamma')),
    ]
    leaves = collect_leaf_sections(records)

    titles = [leaf.title for leaf in leaves]
    ids = [leaf.id for leaf in leaves]

    assert titles == ['Leaf A', 'Leaf B', 'Leaf A']
    # Duplicate titles must keep distinct synthetic ids.
    assert len(set(ids)) == len(ids)


def test_render_section_tree_as_xml_uses_provided_leaf_ids() -> None:
    records = [
        SectionRecord(
            id=uuid.uuid4(),
            title='Parent',
            section=TemplateSection(title='Parent'),
            children=[
                SectionRecord(id=uuid.uuid4(), title='Leaf A', section=TemplateSection(title='Leaf A', content='A')),
                SectionRecord(id=uuid.uuid4(), title='Leaf B', section=TemplateSection(title='Leaf B', content='B')),
            ],
        )
    ]
    leaves = collect_leaf_sections(records)
    record_id_to_sid = {leaf.id: sid for leaf, sid in zip(leaves, ['alpha', 'beta'])}

    xml = render_section_tree_as_xml(records, record_id_to_sid=record_id_to_sid)

    assert 'id="alpha"' in xml
    assert 'id="beta"' in xml
    assert '<title>Leaf A</title>' in xml
    assert '<title>Leaf B</title>' in xml


def test_render_section_tree_assigns_distinct_sids_to_duplicate_titles() -> None:
    records = [
        SectionRecord(
            id=uuid.uuid4(),
            title='Parent A',
            section=TemplateSection(title='Parent A'),
            children=[
                SectionRecord(
                    id=uuid.uuid4(),
                    title='Description',
                    section=TemplateSection(title='Description', content='Alpha desc'),
                )
            ],
        ),
        SectionRecord(
            id=uuid.uuid4(),
            title='Parent B',
            section=TemplateSection(title='Parent B'),
            children=[
                SectionRecord(
                    id=uuid.uuid4(),
                    title='Description',
                    section=TemplateSection(title='Description', content='Beta desc'),
                )
            ],
        ),
    ]
    leaves = collect_leaf_sections(records)
    assert len(leaves) == 2
    rec_id_a, rec_id_b = leaves[0].id, leaves[1].id
    assert rec_id_a != rec_id_b

    xml = render_section_tree_as_xml(
        records,
        record_id_to_sid={rec_id_a: 'desc-a', rec_id_b: 'desc-b'},
    )
    assert 'id="desc-a"' in xml
    assert 'id="desc-b"' in xml
