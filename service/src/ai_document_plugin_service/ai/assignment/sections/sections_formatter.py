from uuid import UUID

from ai_document_plugin_service.ai.assignment.section_tree import (
    collect_leaf_sections,
    render_section_tree_as_xml,
    section_index_to_letter_id,
)
from ai_document_plugin_service.ai.assignment.types import SectionRecord


class SectionFormatter:
    def __init__(self, sections: list[SectionRecord]) -> None:
        """
        Give each leaf an LLM-facing sid.

        Leaves sharing an id (identical sections) share one sid.
        """
        self.sections = sections
        # All sections which have no children
        leaf_sections = collect_leaf_sections(sections)
        # Ids of leaf sections
        leaf_ids = dict.fromkeys(leaf.id for leaf in leaf_sections)
        # Mapping - simple letters A, B, C, ... -> UUIDs of each section. Easier for LLMs to compute.
        self.id_to_sid = {leaf_id: section_index_to_letter_id(index) for index, leaf_id in enumerate(leaf_ids)}
        self.sid_to_id = {sid: rec_id for rec_id, sid in self.id_to_sid.items()}

    def get_sections_as_xml(self) -> str:
        return render_section_tree_as_xml(
            sections=self.sections,
            record_id_to_sid=self.id_to_sid,
        )

    def record_id_for_sid(self, sid: str) -> UUID | None:
        """Resolve an LLM-facing sid back to the synthetic record id.

        Returns ``None`` when the sid is unknown (e.g. hallucinated by the LLM).
        """
        return self.sid_to_id.get(sid)
