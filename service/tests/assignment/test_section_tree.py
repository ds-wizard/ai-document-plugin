from ai_document_plugin_service.ai.assignment.section_tree import (
    build_section_records,
    collect_leaf_section_texts,
    render_section_tree_as_xml,
)


def test_collect_leaf_section_texts_preserves_tree_order() -> None:
    template_data = {
        "sections": [
            {
                "title": "Parent",
                "content": "Parent content",
                "sections": [
                    {"title": "Leaf A", "content": "Alpha"},
                    {"title": "Leaf B", "content": "Beta"},
                ],
            },
            {"title": "Leaf C", "content": "Gamma"},
        ]
    }

    records = build_section_records(template_data)
    leaves = collect_leaf_section_texts(records)

    assert [leaf.title for leaf in leaves] == ["Leaf A", "Leaf B", "Leaf C"]
    assert all(isinstance(leaf.text, str) and leaf.text for leaf in leaves)
    ids = [leaf.id for leaf in leaves]
    assert len(set(ids)) == len(ids)
    assert all(isinstance(rec_id, str) and rec_id for rec_id in ids)


def test_collect_leaf_section_duplicate_title() -> None:
    template_data = {
        "sections": [
            {
                "title": "Parent",
                "content": "Parent content",
                "sections": [
                    {"title": "Leaf A", "content": "Alpha"},
                    {"title": "Leaf B", "content": "Beta"},
                ],
            },
            {"title": "Leaf A", "content": "Gamma"},
        ]
    }

    records = build_section_records(template_data)
    leaves = collect_leaf_section_texts(records)

    titles = [leaf.title for leaf in leaves]
    ids = [leaf.id for leaf in leaves]

    assert titles == ["Leaf A", "Leaf B", "Leaf A"]
    # Duplicate titles must keep distinct synthetic ids.
    assert len(set(ids)) == len(ids)


def test_render_section_tree_as_xml_uses_provided_leaf_ids() -> None:
    template_data = {
        "sections": [
            {
                "title": "Parent",
                "sections": [
                    {"title": "Leaf A", "content": "A"},
                    {"title": "Leaf B", "content": "B"},
                ],
            }
        ]
    }
    records = build_section_records(template_data)
    leaves = collect_leaf_section_texts(records)
    record_id_to_sid = {leaf.id: sid for leaf, sid in zip(leaves, ["alpha", "beta"])}

    xml = render_section_tree_as_xml(records, record_id_to_sid=record_id_to_sid)

    assert 'id="alpha"' in xml
    assert 'id="beta"' in xml
    assert "<title>Leaf A</title>" in xml
    assert "<title>Leaf B</title>" in xml


def test_render_section_tree_assigns_distinct_sids_to_duplicate_titles() -> None:
    template_data = {
        "sections": [
            {
                "title": "Parent A",
                "sections": [
                    {"title": "Description", "content": "Alpha desc"},
                ],
            },
            {
                "title": "Parent B",
                "sections": [
                    {"title": "Description", "content": "Beta desc"},
                ],
            },
        ]
    }
    records = build_section_records(template_data)
    leaves = collect_leaf_section_texts(records)
    assert len(leaves) == 2
    rec_id_a, rec_id_b = leaves[0].id, leaves[1].id
    assert rec_id_a != rec_id_b

    xml = render_section_tree_as_xml(
        records,
        record_id_to_sid={rec_id_a: 'desc-a', rec_id_b: 'desc-b'},
    )
    assert 'id="desc-a"' in xml
    assert 'id="desc-b"' in xml
