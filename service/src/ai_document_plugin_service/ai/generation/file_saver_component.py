import logging
import pathlib
import typing

from haystack import component

logger = logging.getLogger(__name__)


@component
class FileSaverComponent:
    @typing.override
    @component.output_types(markdown=str)
    def run(self, debug_markdown: str, markdown: str, file_path: str) -> dict[str, str]:
        content = debug_markdown if debug_markdown is not None else markdown
        pathlib.Path(file_path).write_text(
            content,
            encoding='utf-8',
        )
        logger.debug(
            'Saved markdown to %s',
            file_path,
        )

        return {
            'markdown': markdown,
        }
