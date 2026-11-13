import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from ai_document_plugin_service.api.types import PipelineStatus
from ai_document_plugin_service.service.errors import ConflictError, NotFoundError
from ai_document_plugin_service.service.pipeline_service import PipelineService


@pytest.fixture
def admission():
    database = AsyncMock()
    database.transaction = Mock(return_value=AsyncMock())
    database.list_generations.return_value = []
    queue = Mock()
    auth = Mock(tenant_uuid=uuid4(), user_uuid=uuid4())
    payload = Mock(questionnaire_uuid=uuid4(), template_uuid=uuid4(), language='en')
    return database, queue, auth, payload


@pytest.mark.parametrize('status', list(PipelineStatus))
@pytest.mark.parametrize('same_template', [True, False])
async def test_admission_uses_cancellable_states_in_owned_project_history(admission, status, same_template):
    database, queue, auth, payload = admission
    database.list_generations.return_value = [
        Mock(template_uuid=payload.template_uuid if same_template else uuid4(), status=status),
    ]
    service = PipelineService(queue, database)
    with patch('ai_document_plugin_service.service.pipeline_service.DSWClient') as client:
        client.return_value.get_project_versions = AsyncMock(return_value=[])
        if same_template and status in {PipelineStatus.QUEUED, PipelineStatus.RUNNING}:
            with pytest.raises(ConflictError) as error:
                await service.enqueue_pipeline_job(payload, Mock(), auth, Mock(), None)
            assert error.value.status_code == 409
            database.create_generation.assert_not_awaited()
            queue.enqueue.assert_not_called()
        else:
            await service.enqueue_pipeline_job(payload, Mock(), auth, Mock(), None)
            database.create_generation.assert_awaited_once()
            queue.enqueue.assert_called_once()
    database.get_template.assert_awaited_once_with(payload.template_uuid, auth.tenant_uuid, for_update=True)
    database.list_generations.assert_awaited_once_with(payload.questionnaire_uuid, auth.tenant_uuid, auth.user_uuid)


async def test_admission_rejects_deleted_template(admission):
    database, queue, auth, payload = admission
    database.get_template.return_value = None
    with patch('ai_document_plugin_service.service.pipeline_service.DSWClient') as client:
        client.return_value.get_project_versions = AsyncMock(return_value=[])
        with pytest.raises(NotFoundError):
            await PipelineService(queue, database).enqueue_pipeline_job(payload, Mock(), auth, Mock(), None)
    database.create_generation.assert_not_awaited()
    queue.enqueue.assert_not_called()


async def test_concurrent_services_admit_only_one_run(admission):
    database, queue, auth, payload = admission
    lock = asyncio.Lock()
    records = []
    locked = False

    @asynccontextmanager
    async def transaction():
        nonlocal locked
        try:
            yield
        finally:
            if locked:
                locked = False
                lock.release()

    async def get_template(*_args, **_kwargs):
        nonlocal locked
        await lock.acquire()
        locked = True
        return Mock()

    async def list_generations(*_args):
        assert lock.locked()
        await asyncio.sleep(0)
        return list(records)

    async def create_generation(**kwargs):
        assert lock.locked()
        records.append(Mock(template_uuid=kwargs['template_uuid'], status=kwargs['status']))
        return uuid4()

    database.transaction = transaction
    database.get_template.side_effect = get_template
    database.list_generations.side_effect = list_generations
    database.create_generation.side_effect = create_generation
    services = [PipelineService(queue, database), PipelineService(queue, database)]
    with patch('ai_document_plugin_service.service.pipeline_service.DSWClient') as client:
        client.return_value.get_project_versions = AsyncMock(return_value=[])
        results = await asyncio.gather(
            *(service.enqueue_pipeline_job(payload, Mock(), auth, Mock(), None) for service in services),
            return_exceptions=True,
        )
    assert sum(isinstance(result, ConflictError) for result in results) == 1
    assert len(records) == 1
    queue.enqueue.assert_called_once()
