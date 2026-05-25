"""Polish a generated DMP by reorganizing content into the most relevant sections and chapters.

Moves content that appears in one section but belongs thematically in another (e.g. when
a topic is mentioned early but has a dedicated chapter later). Does not add new content.
"""

import logging
import typing
from typing import TypedDict

from haystack import component

from ai_document_plugin_service.ai.common.config import (
    Config,
)
from ai_document_plugin_service.ai.common.types import AssignmentStats
from ai_document_plugin_service.ai.generation.llm import OpenAIGenerationLLM

logger = logging.getLogger(__name__)


class DmpPolisherComponentResult(TypedDict):
    markdown: str
    stats: AssignmentStats


@component
class DmpPolisherComponent:
    @typing.override
    @component.output_types(markdown=str, stats=AssignmentStats)
    def run(
        self,
        markdown: str,
        config: Config | None = None,
        template_data: dict | None = None,
    ) -> DmpPolisherComponentResult:
        """Polish the DMP by moving content to relevant sections and improving structure.

        Args:
            markdown: The raw DMP markdown to polish.
            config: Config with up to date llm config
            template_data: Template dict with 'sections' key (section tree with 'title' and 'sections').

        Returns:
            The polished DMP markdown.

        """
        stats = AssignmentStats()
        structure_str = DmpPolisherComponent._build_template_structure_string(template_data)
        llm = OpenAIGenerationLLM(config=config)
        file = llm.polish_dmp(
            markdown=markdown,
            structure_str=structure_str,
            stats=stats,
        )
        return {
            'markdown': file,
            'stats': stats,
        }

    @staticmethod
    def _format_template_structure(nodes: list, depth: int = 0) -> list[str]:
        """Format section tree as # Section, ## Subsection, ### Subsubsection, etc."""
        lines = []
        prefix = '#' * (depth + 1) + ' '
        for node in nodes:
            key = node.get('key') or node.get('title', '?')
            lines.append(prefix + str(key))
            children = node.get('children') or node.get('sections')
            if children:
                lines.extend(DmpPolisherComponent._format_template_structure(children, depth + 1))
        return lines

    @staticmethod
    def _build_template_structure_string(
        template_data: dict | None = None,
    ) -> str:
        """Build the required section structure string from template data (dict with 'sections' key)."""
        if template_data is None:
            return ''
        nodes = template_data.get('sections', [])
        if not nodes:
            return ''
        lines = DmpPolisherComponent._format_template_structure(nodes)
        return '\n'.join(lines)
