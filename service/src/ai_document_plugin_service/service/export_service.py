import asyncio
import re
from dataclasses import dataclass
from uuid import UUID

from ai_document_plugin_service.ai.persistence.database import Database
from ai_document_plugin_service.api.auth import AuthenticatedUser
from ai_document_plugin_service.api.types import (
    PipelineExportRequest,
)
from ai_document_plugin_service.service.errors import NotFoundError, ValidationError
from ai_document_plugin_service.utils.docx_export import markdown_to_docx

DEFAULT_EXPORT_FILE_NAME = 'document'
MAX_EXPORT_FILE_NAME_LENGTH = 80
_UNSAFE_FILE_NAME_CHARACTERS = re.compile(r'[^A-Za-z0-9._ -]+')


@dataclass(frozen=True)
class DocxExport:
    content: bytes
    file_name: str


def _docx_file_name(title: str) -> str:
    """Build a filename safe to interpolate into a Content-Disposition header."""
    cleaned = _UNSAFE_FILE_NAME_CHARACTERS.sub(' ', title).strip()
    collapsed = ' '.join(cleaned.split())[:MAX_EXPORT_FILE_NAME_LENGTH].strip()
    return f'{collapsed or DEFAULT_EXPORT_FILE_NAME}.docx'


class ExportService:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def export_result_as_docx(
        self, run_id: UUID, export_request: PipelineExportRequest, auth: AuthenticatedUser
    ) -> DocxExport:
        """Render markdown as a Word document.

        The markdown comes from the request rather than the stored run so the editor can export
        unsaved edits.

        Raises:
            NotFoundError: The run does not exist or does not belong to the caller.
            ValidationError: The submitted markdown is empty.

        """
        record = await self.database.get_generation(run_id, auth.tenant_uuid, auth.user_uuid)
        if record is None:
            raise NotFoundError(NotFoundError.PIPELINE_RUN_MESSAGE)

        if not export_request.result_markdown.strip():
            raise ValidationError(ValidationError.EMPTY_MARKDOWN_MESSAGE)

        # python-docx is synchronous and CPU-bound; keep it off the event loop.
        content = await asyncio.to_thread(
            markdown_to_docx,
            export_request.result_markdown,
            title=record.title,
        )
        return DocxExport(content=content, file_name=_docx_file_name(record.title))
