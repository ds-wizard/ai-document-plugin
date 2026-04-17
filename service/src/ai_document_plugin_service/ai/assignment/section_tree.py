from typing import Any
from xml.sax.saxutils import escape

from ai_document_plugin_service.ai.assignment.types import SectionNode, SectionRecord


def build_section_records(template_data: dict[str, Any]) -> list[SectionRecord]:
    """Build section records from loaded template JSON data."""
    return _build_records_recursively(template_data["sections"], [])


def collect_leaf_section_texts(sections: list[SectionRecord]) -> list[tuple[str, str]]:
    """Return all leaf sections as (section_key, section_text) in tree order."""
    leaves: list[tuple[str, str]] = []
    for section in sections:
        if section.children is None:
            leaves.append((section.key, section.text or ""))
            continue
        leaves.extend(collect_leaf_section_texts(section.children))
    return leaves


def render_section_tree_as_xml(
        sections: list[SectionRecord],
        section_key_to_id: dict[str, str] | None = None,
) -> str:
    """
    Render the section tree as XML.

    Only leaf sections receive an `id` attribute.
    Returns (xml, id_to_section_key).
    """
    leaf_index = [0]

    root_children: list[dict[str, Any]] = []
    for section in sections:
        root_children.append(
            _section_record_to_xml_node(
                section=section,
                leaf_index=leaf_index,
                section_key_to_id=section_key_to_id,
            )
        )

    xml_parts = ["<sections>"]
    for child in root_children:
        xml_parts.append(_xml_node_to_string(child))
    xml_parts.append("</sections>")
    return "\n".join(xml_parts)


def _build_records_recursively(
        sections: list[dict[str, Any]],
        parent_sections: list[SectionNode],
) -> list[SectionRecord]:
    records: list[SectionRecord] = []
    for section_dict in sections:
        node = SectionNode(section_dict)
        title = node.title
        if not node.subsections:
            records.append(
                SectionRecord(
                    key=title,
                    section=node,
                    text=_format_section(node, parent_sections),
                    children=None,
                )
            )
            continue
        records.append(
            SectionRecord(
                key=title,
                section=node,
                text=None,
                children=_build_records_recursively(node.subsections, parent_sections + [node]),
            )
        )
    return records


def _section_index_to_letter_id(index: int) -> str:
    """Generate section IDs: A, B, ..., Z, AA, AB, ... (0-based)."""
    section_id = ""
    i = index
    while i >= 0:
        section_id = chr(65 + (i % 26)) + section_id
        i = i // 26 - 1
    return section_id


def _section_record_to_xml_node(
        section: SectionRecord,
        leaf_index: list[int],
        section_key_to_id: dict[str, str] | None,
) -> dict[str, Any]:
    if section.children is not None:
        node: dict[str, Any] = {
            "tag": "section",
            "title": section.key,
            "children": [
                _section_record_to_xml_node(
                    section=child,
                    leaf_index=leaf_index,
                    section_key_to_id=section_key_to_id,
                )
                for child in section.children
            ],
        }
        if section.section.content:
            node["content"] = section.section.content.strip()
        return node

    if section_key_to_id is not None and section.key in section_key_to_id:
        section_id = section_key_to_id[section.key]
    else:
        section_id = _section_index_to_letter_id(leaf_index[0])
        leaf_index[0] += 1

    node = {"tag": "section", "id": section_id, "title": section.key}
    if section.section.content:
        node["content"] = section.section.content.strip()
    return node


def _xml_node_to_string(node: dict[str, Any]) -> str:
    tag = node["tag"]
    title = node.get("title", "")
    content = node.get("content")
    children = node.get("children", [])
    attrs = f' id="{escape(str(node["id"]))}"' if "id" in node else ""

    parts = [f"<{tag}{attrs}>"]
    if title:
        parts.append(f"<title>{escape(title)}</title>")
    if content:
        parts.append(f"<content>{escape(content)}</content>")
    for child in children:
        parts.append(_xml_node_to_string(child))
    parts.append(f"</{tag}>")
    return "\n".join(parts)


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
            lines.append(f"[PARENT SECTION]")
        else:
            lines.append(f"[PARENT SUB-SECTION {i}]")

        lines.append(f"Title: {parent_section.title}")

        if parent_section.content:
            lines.append(f"Content:")
            lines.append(parent_section.content)

        lines.append("")  # Add spacing between sections

    # Format the main section
    lines.append(f"[MOST SPECIFIC SECTION]")
    lines.append(f"Title: {section.title}")

    if section.content:
        lines.append(f"Content:")
        lines.append(section.content)

    return "\n".join(lines)
