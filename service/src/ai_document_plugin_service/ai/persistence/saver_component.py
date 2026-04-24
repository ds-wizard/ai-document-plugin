import logging
import pathlib
import typing
from typing import TypedDict

from haystack import component

logger = logging.getLogger(__name__)


class FileSaverComponentResult(TypedDict):
    markdown: str


@component
class SaverComponent:
    @typing.override
    @component.output_types(markdown=str)
    def run(self, debug_markdown: str, markdown: str, file_path: str) -> FileSaverComponentResult:
        output_path = pathlib.Path(file_path)
        output_path.write_text(debug_markdown, encoding='utf-8')
        logger.debug('Saved markdown to %s', output_path)

        return {
            'markdown': markdown,
        }
