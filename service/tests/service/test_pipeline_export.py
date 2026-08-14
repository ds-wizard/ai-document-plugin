import io
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import docx
import pytest

from ai_document_plugin_service.api.auth import AuthenticatedUser
from ai_document_plugin_service.api.types import PipelineExportRequest
from ai_document_plugin_service.service.errors import NotFoundError, ValidationError
from ai_document_plugin_service.service.pipeline_service import PipelineService, _docx_file_name

TENANT_UUID = uuid.UUID('11111111-1111-1111-1111-111111111111')
USER_UUID = uuid.UUID('22222222-2222-2222-2222-222222222222')
RUN_ID = uuid.UUID('33333333-3333-3333-3333-333333333333')


def _auth() -> AuthenticatedUser:
    return AuthenticatedUser(
        token='token',
        api_url='https://dsw.example.com/wizard-api',
        user_uuid=USER_UUID,
        tenant_uuid=TENANT_UUID,
        is_admin=False,
    )


def _database(record: object | None) -> AsyncMock:
    database = AsyncMock()
    database.get_generation = AsyncMock(return_value=record)
    return database


def _service(record: object | None) -> PipelineService:
    return PipelineService(MagicMock(), _database(record))


async def test_export_renders_the_submitted_markdown_not_the_stored_result() -> None:
    # The editor sends its current text so unsaved edits are exported.
    stored = SimpleNamespace(title='My Plan', result_markdown='# Stored version')
    service = _service(stored)

    export = await service.export_result_as_docx(
        RUN_ID, PipelineExportRequest(result_markdown='# Edited version'), _auth()
    )

    document = docx.Document(io.BytesIO(export.content))
    assert document.paragraphs[0].text == '# Edited version'[2:]
    assert export.file_name == 'My Plan.docx'


async def test_export_scopes_the_lookup_to_the_caller() -> None:
    database = _database(SimpleNamespace(title='Plan'))
    service = PipelineService(MagicMock(), database)

    await service.export_result_as_docx(RUN_ID, PipelineExportRequest(result_markdown='body'), _auth())

    # A run belonging to another user or tenant must not be exportable.
    database.get_generation.assert_awaited_once_with(RUN_ID, TENANT_UUID, USER_UUID)


async def test_export_rejects_an_unknown_run() -> None:
    service = _service(None)

    with pytest.raises(NotFoundError):
        await service.export_result_as_docx(RUN_ID, PipelineExportRequest(result_markdown='body'), _auth())


@pytest.mark.parametrize('markdown', ['', '   ', '\n\n'])
async def test_export_rejects_empty_markdown(markdown: str) -> None:
    service = _service(SimpleNamespace(title='Plan'))

    with pytest.raises(ValidationError):
        await service.export_result_as_docx(RUN_ID, PipelineExportRequest(result_markdown=markdown), _auth())


@pytest.mark.parametrize(
    ('title', 'expected'),
    [
        ('Simple Plan', 'Simple Plan.docx'),
        ('Plan: v2 / draft', 'Plan v2 draft.docx'),
        # Quotes and newlines would otherwise break out of the Content-Disposition header.
        ('bad"name\r\nInjected: header', 'bad name Injected header.docx'),
        ('  ', 'document.docx'),
        ('★☆✩', 'document.docx'),
        ('x' * 200, f'{"x" * 80}.docx'),
    ],
)
def test_file_names_are_safe_for_a_content_disposition_header(title: str, expected: str) -> None:
    file_name = _docx_file_name(title)

    assert file_name == expected
    assert not set(file_name) & set('"\r\n')
