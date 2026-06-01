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
    def __init__(self, database: Database) -> None:
        self.database = database

    @typing.override
    @component.output_types(markdown=str)
    def run(
        self,
        template_uuid: str,
        knowledge_model_uuid: str,
        user_uuid: str,
        tenant_uuid: str,
        debug_markdown: str,
        markdown: str,
    ) -> FileSaverComponentResult:
        self.database.save_result(
            template_uuid,
            knowledge_model_uuid,
            user_uuid,
            tenant_uuid,
            debug_markdown,
            markdown,
        )

        return {
            'markdown': markdown,
        }
