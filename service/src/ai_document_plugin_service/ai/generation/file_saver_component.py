import logging
import pathlib

from haystack import component

logger = logging.getLogger(__name__)

@component
class FileSaverComponent:
    @component.output_types(file=str)
    def run(self, debug_markdown: str, markdown: str, file_path: str):
        pathlib.Path(file_path).write_text(
            debug_markdown,
            encoding='utf-8',
        )
        logger.debug(
            'Saved pre-polished DMP to %s',
            file_path,
        )

        return {
            'file': markdown,
        }

