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
    def __init__(self, sections: list[SectionRecord]):
        self.sections = sections
        self.leaf_sections = collect_leaf_section_texts(sections)
        self.section_key_to_id: dict[str, str] | None = None
        self.section_id_to_key: dict[str, str] | None = None

    def create_mappings(
        self,
        section_id_generator: SectionIdGenerator,
        stats: AssignmentStats,
    ) -> None:
        section_key_to_id = section_id_generator.generate_leaf_section_ids(
            self.leaf_sections,
            stats,
        )
        self.section_key_to_id = section_key_to_id
        # Build reverse mapping: id -> key, resolve collisions by appending _1, _2, ...
        self.section_id_to_key = {}
        for key, sec_id in section_key_to_id.items():
            new_id = sec_id
            i = 1
            while new_id in self.section_id_to_key:
                new_id = f'{sec_id}_{i}'
                i += 1
            self.section_id_to_key[new_id] = key

    def get_sections_as_xml(self) -> str:
        if self.section_key_to_id is None:
            raise RuntimeError(
                'Class not initialized, call create_mappings first',
            )

        sections_xml = render_section_tree_as_xml(
            sections=self.sections,
            section_key_to_id=self.section_key_to_id,
        )
        return sections_xml

    def get_original_id(self, section_id: str) -> str:
        if self.section_id_to_key is None:
            return section_id
        return self.section_id_to_key.get(section_id, section_id)
