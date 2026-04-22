"""Polish a generated DMP by reorganizing content into the most relevant sections and chapters.

Moves content that appears in one section but belongs thematically in another (e.g. when
a topic is mentioned early but has a dedicated chapter later). Does not add new content.
"""

import json
import logging
import pathlib
from haystack import component

from ai_document_plugin_service.ai.common.config import (
    DEFAULT_CONFIG_PATH,
    load_config,
)
from ai_document_plugin_service.ai.common.types import AssignmentStats
from ai_document_plugin_service.ai.generation.llm import OpenAIGenerationLLM

logger = logging.getLogger(__name__)

@component
class DmpPolisherComponent:
    @component.output_types(markdown=str)
    def run(self,
        markdown: str,
        config_path: str = DEFAULT_CONFIG_PATH,
        stats: AssignmentStats | None = None,
        template_data: dict | None = None,
    ):
        """Polish the DMP by moving content to relevant sections and improving structure.

        Args:
            markdown: The raw DMP markdown to polish.
            config_path: Path to OpenAI config file.
            stats: Optional stats object to record token usage.
            template_data: Template dict with 'sections' key (section tree with 'title' and 'sections').

        Returns:
            The polished DMP markdown.

        """
        structure_str = self._build_template_structure_string(template_data)
        llm = OpenAIGenerationLLM(config_path=config_path)
        file = llm.polish_dmp(
            markdown=markdown,
            structure_str=structure_str,
            stats=stats,
        )
        return {
            'markdown': file,
        }

    def _format_template_structure(self, nodes: list, depth: int = 0) -> list[str]:
        """Format section tree as # Section, ## Subsection, ### Subsubsection, etc."""
        lines = []
        prefix = '#' * (depth + 1) + ' '
        for node in nodes:
            key = node.get('key') or node.get('title', '?')
            lines.append(prefix + str(key))
            children = node.get('children') or node.get('sections')
            if children:
                lines.extend(self._format_template_structure(children, depth + 1))
        return lines


    def _build_template_structure_string(
        self,
        template_data: dict | None = None,
    ) -> str:
        """Build the required section structure string from template data (dict with 'sections' key)."""
        if template_data is None:
            return ''
        nodes = template_data.get('sections', [])
        if not nodes:
            return ''
        lines = self._format_template_structure(nodes)
        return '\n'.join(lines)


if __name__ == '__main__':
    config = load_config()
    file_paths = config.files

    markdown = pathlib.Path(file_paths.output_pre_polish_markdown).read_text(
        encoding='utf-8',
    )

    with pathlib.Path(file_paths.dmp_template).open(encoding='utf-8') as f:
        template_data = json.load(f)

    stats = AssignmentStats()
    dmp_polisher_component = DmpPolisherComponent()
    polished = dmp_polisher_component.run(
        markdown=markdown,
        config_path=file_paths.config_path,
        stats=stats,
        template_data=template_data,
    )['markdown']

    pathlib.Path(file_paths.output_markdown).write_text(
        polished,
        encoding='utf-8',
    )

    logger.debug('Polished DMP saved to %s', file_paths.output_markdown)
    logger.debug(
        'LLM calls: %s, input tokens: %s, output tokens: %s',
        stats.total_calls,
        f'{stats.total_input_tokens:,}',
        f'{stats.total_output_tokens:,}',
    )
