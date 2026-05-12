import logging
import typing
from typing import TypedDict

from haystack import component

from ai_document_plugin_service.ai.persistence.database import Database

logger = logging.getLogger(__name__)


class FileSaverComponentResult(TypedDict):
    markdown: str


@component
class SaverComponent:
    @typing.override
    @component.output_types(markdown=str)
    def run(
        self, template_uuid: str, knowledge_model_uuid: str, debug_markdown: str, markdown: str, database: Database
    ) -> FileSaverComponentResult:

        database.save_result(template_uuid, knowledge_model_uuid, debug_markdown, markdown)

        return {
            'markdown': markdown,
        }
