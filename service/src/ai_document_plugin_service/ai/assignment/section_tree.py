import uuid
from typing import Any
from xml.sax.saxutils import escape

from ai_document_plugin_service.ai.assignment.types import (
    SectionNode,
    SectionRecord,
)


def build_section_records(template_data: dict[str, Any]) -> list[SectionRecord]:
    """Build section records from loaded template JSON data.

    Each record receives a synthetic UUID id. Ids are unique across the whole tree and
    decoupled from the section title, so duplicate titles never collide downstream.
    """
    return _build_records_recursively(template_data['sections'])


def collect_leaf_sections(
    sections: list[SectionRecord],
) -> list[SectionRecord]:
    """Return all leaf sections in tree order."""
    leaves: list[SectionRecord] = []
    for section in sections:
        if section.children is None:
            leaves.append(section)
            continue
        leaves.extend(collect_leaf_sections(section.children))
    return leaves


def render_section_tree_as_xml(
    sections: list[SectionRecord],
    record_id_to_sid: dict[uuid.UUID, str],
) -> str:
    """Render the section tree as XML.

    Only leaf sections receive a short `id` attribute (the LLM-facing sid), looked up
    in `record_id_to_sid` by the leaf's `SectionRecord.id`. record_id_to_sid must contain all leaf sections.
    """
    root_children: list[dict[str, Any]] = [
        _section_record_to_xml_node(
            section=section,
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
) -> list[SectionRecord]:
    records: list[SectionRecord] = []
    for section_dict in sections:
        node = SectionNode(section_dict)
        title = node.title
        record_id = uuid.uuid4()
        if not node.subsections:
            records.append(
                SectionRecord(
                    id=record_id,
                    title=title,
                    section=node,
                    children=None,
                ),
            )
            continue
        records.append(
            SectionRecord(
                id=record_id,
                title=title,
                section=node,
                children=_build_records_recursively(node.subsections),
            ),
        )
    return records


def section_index_to_letter_id(index: int) -> str:
    """Generate section IDs: A, B, ..., Z, AA, AB, ... (0-based)."""
    section_id = ''
    i = index
    while i >= 0:
        section_id = chr(65 + (i % 26)) + section_id
        i = i // 26 - 1
    return section_id


def _section_record_to_xml_node(
    section: SectionRecord,
    record_id_to_sid: dict[uuid.UUID, str],
) -> dict[str, Any]:
    if section.children is not None:
        node: dict[str, Any] = {
            'tag': 'section',
            'title': section.title,
            'children': [
                _section_record_to_xml_node(
                    section=child,
                    record_id_to_sid=record_id_to_sid,
                )
                for child in section.children
            ],
        }
        if section.section.content:
            node['content'] = section.section.content.strip()
        return node

    node = {'tag': 'section', 'id': record_id_to_sid[section.id], 'title': section.title}
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
