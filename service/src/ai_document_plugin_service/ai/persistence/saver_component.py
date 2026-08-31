import logging
import typing
from typing import TypedDict
from uuid import UUID

from haystack import component

from ai_document_plugin_service.ai.persistence.database import Database

logger = logging.getLogger(__name__)


class FileSaverComponentResult(TypedDict):
    markdown: str


@component
class SaverComponent:
    def __init__(self, database: Database) -> None:
        self.database = database

    @component.output_types(markdown=str)
    async def run_async(
        self,
        template_uuid: UUID,
        knowledge_model_uuid: UUID,
        user_uuid: UUID,
        tenant_uuid: UUID,
        debug_markdown: str,
        markdown: str,
    ) -> FileSaverComponentResult:
        logger.info(
            'Persisting generated markdown result',
            extra={
                'template_uuid': str(template_uuid),
                'knowledge_model_uuid': knowledge_model_uuid,
                'user_uuid': str(user_uuid),
                'tenant_uuid': str(tenant_uuid),
                'debug_markdown_length': len(debug_markdown),
                'markdown_length': len(markdown),
            },
        )
        await self.database.save_result(
            template_uuid,
            knowledge_model_uuid,
            user_uuid,
            tenant_uuid,
            debug_markdown,
            markdown,
        )
        logger.info(
            'Generated markdown result persisted',
            extra={
                'template_uuid': str(template_uuid),
                'knowledge_model_uuid': knowledge_model_uuid,
                'user_uuid': str(user_uuid),
                'tenant_uuid': str(tenant_uuid),
            },
        )

        return {
            'markdown': markdown,
        }

    @typing.override
    @component.output_types(markdown=str)
    def run(
        self,
        template_uuid: UUID,
        knowledge_model_uuid: UUID,
        user_uuid: UUID,
        tenant_uuid: UUID,
        debug_markdown: str,
        markdown: str,
    ) -> FileSaverComponentResult:
        """Async-only component; the sync pipeline entrypoint is intentionally unsupported."""
        msg = f'{type(self).__name__} is async-only; use run_async() / AsyncPipeline.run_async()'
        raise NotImplementedError(
            msg,
        )
