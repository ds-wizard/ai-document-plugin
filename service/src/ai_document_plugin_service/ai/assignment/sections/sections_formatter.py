from ai_document_plugin_service.ai.assignment.section_tree import (
    collect_leaf_section_texts,
    render_section_tree_as_xml,
)
from ai_document_plugin_service.ai.assignment.sections.llm import (
    SectionIdGenerator,
)
from ai_document_plugin_service.ai.assignment.types import SectionRecord
from ai_document_plugin_service.ai.common import AssignmentStats


class SectionFormatter:
    def __init__(self, sections: list[SectionRecord]) -> None:
        self.sections = sections
        self.leaf_sections = collect_leaf_section_texts(sections)
        self.id_to_sid: dict[str, str] | None = None
        self.sid_to_id: dict[str, str] | None = None

    def create_mappings(
        self,
        section_id_generator: SectionIdGenerator,
        stats: AssignmentStats,
    ) -> None:
        id_to_sid = section_id_generator.generate_leaf_section_ids(
            self.leaf_sections,
            stats,
        )
        self.id_to_sid = id_to_sid
        # Forward keys (record ids) and sid values are both unique by construction:
        # record ids come from _build_records_recursively (monotonic counter) and the
        # sid generator de-duplicates via its own `used_ids` set. So a clean inverse exists.
        self.sid_to_id = {sid: rec_id for rec_id, sid in id_to_sid.items()}

    def get_sections_as_xml(self) -> str:
        if self.id_to_sid is None:
            msg = 'Class not initialized, call create_mappings first'
            raise RuntimeError(msg)

        return render_section_tree_as_xml(
            sections=self.sections,
            record_id_to_sid=self.id_to_sid,
        )

    def record_id_for_sid(self, sid: str) -> str:
        """Resolve an LLM-facing sid back to the synthetic record id.

        Falls back to returning the input unchanged when no mapping is registered yet,
        matching the previous lenient behaviour.
        """
        if self.sid_to_id is None:
            return sid
        return self.sid_to_id.get(sid, sid)
