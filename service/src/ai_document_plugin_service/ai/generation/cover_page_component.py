from typing import TypedDict

from haystack import component

from ai_document_plugin_service.utils.document_markers import COVER_PAGE_END


class CoverPageComponentResult(TypedDict):
    markdown: str


@component
class CoverPageComponent:
    """Prepend the cover page after LLM polishing has finished."""

    @component.output_types(markdown=str)
    async def run_async(  # noqa: PLR6301
        self,
        markdown: str,
        cover_page: str = '',
    ) -> CoverPageComponentResult:
        separator = f'\n\n{COVER_PAGE_END}\n\n'
        combined_markdown = separator.join(part for part in (cover_page, markdown) if part.strip())
        return {'markdown': combined_markdown}

    @component.output_types(markdown=str)
    def run(self, markdown: str, cover_page: str = '') -> CoverPageComponentResult:
        msg = f'{type(self).__name__} is async-only; use run_async() / AsyncPipeline.run_async()'
        raise NotImplementedError(msg)
