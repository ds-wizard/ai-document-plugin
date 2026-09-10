from typing import TypedDict

from haystack import component

from ai_document_plugin_service.utils.document_markers import DOCUMENT_HEADER_END


class DocumentHeaderComponentResult(TypedDict):
    markdown: str


@component
class DocumentHeaderComponent:
    """Add fixed document metadata after LLM polishing has finished."""

    @component.output_types(markdown=str)
    async def run_async(  # noqa: PLR6301
        self,
        markdown: str,
        document_header: str = '',
    ) -> DocumentHeaderComponentResult:
        separator = f'\n\n{DOCUMENT_HEADER_END}\n\n'
        combined_markdown = separator.join(part for part in (document_header, markdown) if part.strip())
        return {'markdown': combined_markdown}

    @component.output_types(markdown=str)
    def run(self, markdown: str, document_header: str = '') -> DocumentHeaderComponentResult:
        msg = f'{type(self).__name__} is async-only; use run_async() / AsyncPipeline.run_async()'
        raise NotImplementedError(msg)
