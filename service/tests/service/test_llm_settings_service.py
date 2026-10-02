import uuid
from contextlib import nullcontext
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError as PydanticValidationError

from ai_document_plugin_service.ai.common.config import LLMConfig
from ai_document_plugin_service.api.auth import AuthenticatedUser
from ai_document_plugin_service.api.types import LlmSettingsUpdateRequest
from ai_document_plugin_service.service.errors import AccessDeniedError, ValidationError
from ai_document_plugin_service.service.llm_settings_service import LlmSettingsService

TENANT_UUID = uuid.UUID('11111111-1111-1111-1111-111111111111')
USER_UUID = uuid.UUID('22222222-2222-2222-2222-222222222222')

STORED = LLMConfig(model='stored-model', api_key='stored-key', api_url='https://llm.example.com/v1', parallel_workers=4)


def _database(stored: LLMConfig | None = None) -> AsyncMock:
    database = AsyncMock()
    database.transaction = MagicMock(return_value=nullcontext())
    database.get_llm_settings.return_value = stored
    return database


def _user(*, is_admin: bool = True) -> AuthenticatedUser:
    return AuthenticatedUser(
        token='token',
        api_url='https://dsw.example.com/wizard-api',
        user_uuid=USER_UUID,
        tenant_uuid=TENANT_UUID,
        is_admin=is_admin,
    )


def _payload(**overrides: object) -> LlmSettingsUpdateRequest:
    values = {'model': 'new-model', 'api_url': 'https://new.example.com/v1', 'api_key': 'new-key', 'max_workers': 2}
    return LlmSettingsUpdateRequest.model_validate({**values, **overrides})


async def test_get_rejects_non_admin() -> None:
    database = _database(STORED)

    with pytest.raises(AccessDeniedError):
        await LlmSettingsService(database).get(_user(is_admin=False))

    database.get_llm_settings.assert_not_awaited()


async def test_get_never_returns_api_key() -> None:
    response = await LlmSettingsService(_database(STORED)).get(_user())

    assert response.api_key_set is True
    assert response.model == 'stored-model'
    assert response.max_workers == 4
    assert 'stored-key' not in response.model_dump_json()


async def test_get_reports_unconfigured_tenant() -> None:
    response = await LlmSettingsService(_database()).get(_user())

    assert response.api_key_set is False
    assert response.model is None


async def test_update_rejects_non_admin() -> None:
    database = _database(STORED)

    with pytest.raises(AccessDeniedError):
        await LlmSettingsService(database).update(_user(is_admin=False), _payload())

    database.save_llm_settings.assert_not_awaited()


async def test_update_saves_trimmed_settings() -> None:
    database = _database()

    response = await LlmSettingsService(database).update(_user(), _payload(model='  new-model  ', api_key=' new-key '))

    database.save_llm_settings.assert_awaited_once_with(
        TENANT_UUID,
        LLMConfig(model='new-model', api_key='new-key', api_url='https://new.example.com/v1', parallel_workers=2),
        USER_UUID,
    )
    assert response.api_key_set is True
    assert 'new-key' not in response.model_dump_json()


async def test_update_without_api_key_keeps_stored_key() -> None:
    database = _database(STORED)

    await LlmSettingsService(database).update(_user(), _payload(api_key=None))

    saved = database.save_llm_settings.await_args.args[1]
    assert saved.api_key == 'stored-key'
    assert saved.model == 'new-model'


async def test_update_requires_api_key_when_none_is_stored() -> None:
    database = _database()

    with pytest.raises(ValidationError):
        await LlmSettingsService(database).update(_user(), _payload(api_key=None))

    database.save_llm_settings.assert_not_awaited()


@pytest.mark.parametrize('field', ['model', 'api_url', 'api_key'])
def test_update_request_rejects_blank_values(field: str) -> None:
    with pytest.raises(PydanticValidationError):
        _payload(**{field: '  '})
