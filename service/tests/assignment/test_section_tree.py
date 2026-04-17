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

    assert [key for key, _ in leaves] == ["Leaf A", "Leaf B", "Leaf C"]
    assert all(isinstance(text, str) and text for _, text in leaves)


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

    assert [key for key, _ in leaves] == ["Leaf A", "Leaf B", "Leaf A"]
    assert all(isinstance(text, str) and text for _, text in leaves)


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

    xml = render_section_tree_as_xml(records, section_key_to_id={"Leaf A": "alpha", "Leaf B": "beta"})

    assert 'id="alpha"' in xml
    assert 'id="beta"' in xml
    assert "<title>Leaf A</title>" in xml
    assert "<title>Leaf B</title>" in xml
