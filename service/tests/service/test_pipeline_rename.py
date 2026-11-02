from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ai_document_plugin_service.ai.persistence.database import GenerationRecord
from ai_document_plugin_service.api.auth import AuthenticatedUser
from ai_document_plugin_service.api.types import PipelineRenameRequest, PipelineStatus
from ai_document_plugin_service.service.errors import NotFoundError
from ai_document_plugin_service.service.pipeline_service import PipelineService


@pytest.fixture
def auth():
    return AuthenticatedUser(
        token='token', api_url='https://dsw.example.com', user_uuid=uuid4(), tenant_uuid=uuid4(), is_admin=False
    )


@pytest.mark.parametrize('status', list(PipelineStatus))
async def test_rename_persists_title_for_every_run_status(auth, status):
    record = GenerationRecord(
        run_id=uuid4(),
        questionnaire_uuid=uuid4(),
        template_uuid=uuid4(),
        title='Original',
        language='en',
        knowledge_model_uuid=None,
        user_uuid=auth.user_uuid,
        tenant_uuid=auth.tenant_uuid,
        status=status,
        error_type=None,
        error_message=None,
        result_markdown='# Document',
        progress_message=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    database = AsyncMock()
    database.get_generation.return_value = record
    database.update_generation.return_value = replace(record, title='New title')
    service = PipelineService(Mock(), database)

    result = await service.rename_pipeline(record.run_id, PipelineRenameRequest(title='  New title  '), auth)

    database.get_generation.assert_awaited_once_with(record.run_id, auth.tenant_uuid, auth.user_uuid)
    database.update_generation.assert_awaited_once_with(record.run_id, auth.tenant_uuid, title='New title')
    assert result.template_title == 'New title'
    assert result.status == status
    assert result.result_markdown == record.result_markdown


async def test_rename_does_not_update_a_run_outside_the_users_scope(auth):
    database = AsyncMock()
    database.get_generation.return_value = None
    service = PipelineService(Mock(), database)
    run_id = uuid4()

    with pytest.raises(NotFoundError):
        await service.rename_pipeline(run_id, PipelineRenameRequest(title='New title'), auth)

    database.get_generation.assert_awaited_once_with(run_id, auth.tenant_uuid, auth.user_uuid)
    database.update_generation.assert_not_awaited()


async def test_rename_handles_a_run_removed_before_update(auth):
    database = AsyncMock()
    database.update_generation.return_value = None
    service = PipelineService(Mock(), database)

    with pytest.raises(NotFoundError):
        await service.rename_pipeline(uuid4(), PipelineRenameRequest(title='New title'), auth)


@pytest.mark.parametrize('title', ['', '   ', '\n\t'])
def test_rename_rejects_blank_titles(title):
    with pytest.raises(ValidationError):
        PipelineRenameRequest(title=title)
