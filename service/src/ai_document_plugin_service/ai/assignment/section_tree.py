import uuid
from typing import Any
from xml.sax.saxutils import escape

from ai_document_plugin_service.ai.assignment.types import (
    LeafSection,
    SectionNode,
    SectionRecord,
)


def build_section_records(template_data: dict[str, Any]) -> list[SectionRecord]:
    """Build section records from loaded template JSON data.

    Each record receives a synthetic UUID id. Ids are unique across the whole tree and
    decoupled from the section title, so duplicate titles never collide downstream.
    """
    return _build_records_recursively(template_data['sections'], [])


def collect_leaf_section_texts(
    sections: list[SectionRecord],
) -> list[LeafSection]:
    """Return all leaf sections as `LeafSection` records in tree order."""
    leaves: list[LeafSection] = []
    for section in sections:
        if section.children is None:
            leaves.append(LeafSection(id=section.id, title=section.title, text=section.text or ''))
            continue
        leaves.extend(collect_leaf_section_texts(section.children))
    return leaves


def render_section_tree_as_xml(
    sections: list[SectionRecord],
    record_id_to_sid: dict[str, str] | None = None,
) -> str:
    """Render the section tree as XML.

    Only leaf sections receive a short `id` attribute (the LLM-facing sid). When
    `record_id_to_sid` is provided, the leaf's `SectionRecord.id` is looked up in it;
    otherwise a sequential letter id (A, B, ...) is generated.
    """
    leaf_index = [0]

    root_children: list[dict[str, Any]] = [
        _section_record_to_xml_node(
            section=section,
            leaf_index=leaf_index,
            record_id_to_sid=record_id_to_sid,
        )
        for section in sections
    ]

    xml_parts = ['<sections>']
    xml_parts.extend(_xml_node_to_string(child) for child in root_children)
    xml_parts.append('</sections>')
    return '\n'.join(xml_parts)


def _build_records_recursively(
    sections: list[dict[str, Any]],
    parent_sections: list[SectionNode],
) -> list[SectionRecord]:
    records: list[SectionRecord] = []
    for section_dict in sections:
        node = SectionNode(section_dict)
        title = node.title
        record_id = str(uuid.uuid4())
        if not node.subsections:
            records.append(
                SectionRecord(
                    id=record_id,
                    title=title,
                    section=node,
                    text=_format_section(node, parent_sections),
                    children=None,
                ),
            )
            continue
        records.append(
            SectionRecord(
                id=record_id,
                title=title,
                section=node,
                text=None,
                children=_build_records_recursively(
                    node.subsections,
                    [*parent_sections, node],
                ),
            ),
        )
    return records


def _section_index_to_letter_id(index: int) -> str:
    """Generate section IDs: A, B, ..., Z, AA, AB, ... (0-based)."""
    section_id = ''
    i = index
    while i >= 0:
        section_id = chr(65 + (i % 26)) + section_id
        i = i // 26 - 1
    return section_id


def _section_record_to_xml_node(
    section: SectionRecord,
    leaf_index: list[int],
    record_id_to_sid: dict[str, str] | None,
) -> dict[str, Any]:
    if section.children is not None:
        node: dict[str, Any] = {
            'tag': 'section',
            'title': section.title,
            'children': [
                _section_record_to_xml_node(
                    section=child,
                    leaf_index=leaf_index,
                    record_id_to_sid=record_id_to_sid,
                )
                for child in section.children
            ],
        }
        if section.section.content:
            node['content'] = section.section.content.strip()
        return node

    if record_id_to_sid is not None and section.id in record_id_to_sid:
        sid = record_id_to_sid[section.id]
    else:
        sid = _section_index_to_letter_id(leaf_index[0])
        leaf_index[0] += 1

    node = {'tag': 'section', 'id': sid, 'title': section.title}
    if section.section.content:
        node['content'] = section.section.content.strip()
    return node


def _xml_node_to_string(node: dict[str, Any]) -> str:
    tag = node['tag']
    title = node.get('title', '')
    content = node.get('content')
    children = node.get('children', [])
    attrs = f' id="{escape(str(node["id"]))}"' if 'id' in node else ''

    parts = [f'<{tag}{attrs}>']
    if title:
        parts.append(f'<title>{escape(title)}</title>')
    if content:
        parts.append(f'<content>{escape(content)}</content>')
    parts.extend(_xml_node_to_string(child) for child in children)
    parts.append(f'</{tag}>')
    return '\n'.join(parts)


def _format_section(
    section: SectionNode,
    parent_sections: list[SectionNode] | None = None,
) -> str:
    if parent_sections is None:
        parent_sections = []

    lines = []

    # Format preceding context sections
    for i, parent_section in enumerate(parent_sections):
        if i == 0:
            lines.append('[PARENT SECTION]')
        else:
            lines.append(f'[PARENT SUB-SECTION {i}]')

        lines.append(f'Title: {parent_section.title}')

        if parent_section.content:
            lines.extend(('Content:', parent_section.content))

        lines.append('')  # Add spacing between sections

    # Format the main section
    lines.extend(('[MOST SPECIFIC SECTION]', f'Title: {section.title}'))

    if section.content:
        lines.extend(('Content:', section.content))

    return '\n'.join(lines)
