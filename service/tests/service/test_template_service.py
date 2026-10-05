import uuid
from contextlib import nullcontext
from pathlib import Path

from ai_document_plugin_service.ai.common.config import load_config
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai_document_plugin_service.ai.persistence.database import TemplateRecord
from ai_document_plugin_service.ai.persistence.errors import TemplateTitleConflictError
from ai_document_plugin_service.api.auth import AuthenticatedUser
from ai_document_plugin_service.api.types import (
    TemplateCreateRequest,
    TemplateScope,
    TemplateUpdateRequest,
)
from ai_document_plugin_service.service.errors import (
    AccessDeniedError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from ai_document_plugin_service.service.template_service import TemplateService

TENANT_UUID = uuid.UUID('11111111-1111-1111-1111-111111111111')
USER_UUID = uuid.UUID('22222222-2222-2222-2222-222222222222')
OTHER_USER_UUID = uuid.UUID('33333333-3333-3333-3333-333333333333')

VALID_CONTENT = {'sections': []}
COVER_DEFINITION = load_config(str(Path(__file__).resolve().parents[2] / 'config.test.yaml')).cover_definition


def _database() -> AsyncMock:
    """A mocked Database whose transaction() is a working no-op async context manager.

    A bare AsyncMock returns a coroutine from transaction(), which can't be used with
    `async with`; nullcontext() gives the service a real (no-op) async context manager.
    """
    database = AsyncMock()
    database.transaction = MagicMock(return_value=nullcontext())
    return database


def _user(*, is_admin: bool = False, user_uuid: uuid.UUID = USER_UUID) -> AuthenticatedUser:
    return AuthenticatedUser(
        token='token',
        api_url='https://dsw.example.com/wizard-api',
        user_uuid=user_uuid,
        tenant_uuid=TENANT_UUID,
        is_admin=is_admin,
    )


def _record(
    *,
    template_uuid: uuid.UUID,
    user_uuid: uuid.UUID | None,
    title: str = 'Existing',
    content: dict | None = None,
) -> TemplateRecord:
    return TemplateRecord(
        uuid=template_uuid,
        title=title,
        content=content if content is not None else VALID_CONTENT,
        tenant_uuid=TENANT_UUID,
        user_uuid=user_uuid,
    )


async def test_list_scopes_query_to_tenant_and_user() -> None:
    tenant_template_uuid = uuid.uuid4()
    personal_template_uuid = uuid.uuid4()
    database = _database()
    database.list_templates.return_value = [
        _record(template_uuid=tenant_template_uuid, user_uuid=None, title='Common'),
        _record(template_uuid=personal_template_uuid, user_uuid=USER_UUID, title='Mine'),
    ]

    result = await TemplateService(database, COVER_DEFINITION).list(_user())

    database.list_templates.assert_awaited_once_with(TENANT_UUID, USER_UUID)
    assert result[0].uuid == tenant_template_uuid
    assert result[0].scope is TemplateScope.TENANT
    assert result[1].uuid == personal_template_uuid
    assert result[1].scope is TemplateScope.PERSONAL


async def test_get_returns_tenant_wide_template() -> None:
    template_uuid = uuid.uuid4()
    database = _database()
    database.get_template.return_value = _record(template_uuid=template_uuid, user_uuid=None)

    detail = await TemplateService(database, COVER_DEFINITION).get(_user(), template_uuid)

    assert detail.uuid == template_uuid
    assert detail.scope is TemplateScope.TENANT


async def test_get_returns_own_personal_template() -> None:
    template_uuid = uuid.uuid4()
    database = _database()
    database.get_template.return_value = _record(template_uuid=template_uuid, user_uuid=USER_UUID)

    detail = await TemplateService(database, COVER_DEFINITION).get(_user(), template_uuid)

    assert detail.scope is TemplateScope.PERSONAL


async def test_get_hides_other_users_personal_template() -> None:
    template_uuid = uuid.uuid4()
    database = _database()
    database.get_template.return_value = _record(template_uuid=template_uuid, user_uuid=OTHER_USER_UUID)

    with pytest.raises(NotFoundError):
        await TemplateService(database, COVER_DEFINITION).get(_user(), template_uuid)


async def test_get_raises_not_found_when_missing() -> None:
    database = _database()
    database.get_template.return_value = None

    with pytest.raises(NotFoundError):
        await TemplateService(database, COVER_DEFINITION).get(_user(), uuid.uuid4())


async def test_create_personal_template_sets_owner() -> None:
    template_uuid = uuid.uuid4()
    database = _database()
    database.create_template.return_value = template_uuid
    payload = TemplateCreateRequest(title='  My template  ', content=VALID_CONTENT, scope=TemplateScope.PERSONAL)

    detail = await TemplateService(database, COVER_DEFINITION).create(_user(), payload)

    database.create_template.assert_awaited_once_with(
        title='My template',
        content=VALID_CONTENT,
        tenant_uuid=TENANT_UUID,
        user_uuid=USER_UUID,
        cover_page_version=None,
    )
    assert detail.title == 'My template'
    assert detail.scope is TemplateScope.PERSONAL


async def test_create_tenant_template_by_admin_has_no_owner() -> None:
    template_uuid = uuid.uuid4()
    database = _database()
    database.create_template.return_value = template_uuid
    payload = TemplateCreateRequest(title='Common', content=VALID_CONTENT, scope=TemplateScope.TENANT)

    detail = await TemplateService(database, COVER_DEFINITION).create(_user(is_admin=True), payload)

    database.create_template.assert_awaited_once_with(
        title='Common',
        content=VALID_CONTENT,
        tenant_uuid=TENANT_UUID,
        user_uuid=None,
        cover_page_version=None,
    )
    assert detail.scope is TemplateScope.TENANT


async def test_create_tenant_template_by_non_admin_is_denied() -> None:
    database = _database()
    payload = TemplateCreateRequest(title='Common', content=VALID_CONTENT, scope=TemplateScope.TENANT)

    with pytest.raises(AccessDeniedError):
        await TemplateService(database, COVER_DEFINITION).create(_user(is_admin=False), payload)

    database.create_template.assert_not_awaited()


async def test_create_authorizes_before_validating() -> None:
    # A non-admin submitting an invalid tenant-wide template must be rejected for
    # lack of permission (403), not for the payload (400).
    database = _database()
    payload = TemplateCreateRequest(title='', content={}, scope=TemplateScope.TENANT)

    with pytest.raises(AccessDeniedError):
        await TemplateService(database, COVER_DEFINITION).create(_user(is_admin=False), payload)


async def test_create_rejects_blank_title() -> None:
    database = _database()
    payload = TemplateCreateRequest(title='   ', content=VALID_CONTENT)

    with pytest.raises(ValidationError):
        await TemplateService(database, COVER_DEFINITION).create(_user(), payload)

    database.create_template.assert_not_awaited()


async def test_create_rejects_content_without_sections() -> None:
    database = _database()
    payload = TemplateCreateRequest(title='My template', content={'not_sections': 1})

    with pytest.raises(ValidationError):
        await TemplateService(database, COVER_DEFINITION).create(_user(), payload)


async def test_create_maps_title_conflict_to_conflict_error() -> None:
    database = _database()
    database.create_template.side_effect = TemplateTitleConflictError('My template')
    payload = TemplateCreateRequest(title='My template', content=VALID_CONTENT)

    with pytest.raises(ConflictError):
        await TemplateService(database, COVER_DEFINITION).create(_user(), payload)


async def test_update_own_personal_template() -> None:
    template_uuid = uuid.uuid4()
    database = _database()
    database.get_template.return_value = _record(template_uuid=template_uuid, user_uuid=USER_UUID)
    database.update_template.return_value = True
    payload = TemplateUpdateRequest(title='  Renamed  ', content=VALID_CONTENT)

    detail = await TemplateService(database, COVER_DEFINITION).update(_user(), template_uuid, payload)

    database.update_template.assert_awaited_once_with(
        template_uuid=template_uuid,
        tenant_uuid=TENANT_UUID,
        title='Renamed',
        content=VALID_CONTENT,
        cover_page_version=None,
    )
    assert detail.title == 'Renamed'
    assert detail.scope is TemplateScope.PERSONAL


async def test_update_tenant_template_by_admin() -> None:
    template_uuid = uuid.uuid4()
    database = _database()
    database.get_template.return_value = _record(template_uuid=template_uuid, user_uuid=None)
    database.update_template.return_value = True
    payload = TemplateUpdateRequest(title='Renamed', content=VALID_CONTENT)

    detail = await TemplateService(database, COVER_DEFINITION).update(_user(is_admin=True), template_uuid, payload)

    assert detail.scope is TemplateScope.TENANT
    database.update_template.assert_awaited_once()


async def test_update_tenant_template_by_non_admin_is_denied() -> None:
    template_uuid = uuid.uuid4()
    database = _database()
    database.get_template.return_value = _record(template_uuid=template_uuid, user_uuid=None)
    payload = TemplateUpdateRequest(title='Renamed', content=VALID_CONTENT)

    with pytest.raises(AccessDeniedError):
        await TemplateService(database, COVER_DEFINITION).update(_user(is_admin=False), template_uuid, payload)

    database.update_template.assert_not_awaited()


async def test_update_other_users_personal_template_is_hidden() -> None:
    template_uuid = uuid.uuid4()
    database = _database()
    database.get_template.return_value = _record(template_uuid=template_uuid, user_uuid=OTHER_USER_UUID)
    payload = TemplateUpdateRequest(title='Renamed', content=VALID_CONTENT)

    with pytest.raises(NotFoundError):
        await TemplateService(database, COVER_DEFINITION).update(_user(), template_uuid, payload)

    database.update_template.assert_not_awaited()


async def test_update_missing_template_raises_not_found() -> None:
    database = _database()
    database.get_template.return_value = None
    payload = TemplateUpdateRequest(title='Renamed', content=VALID_CONTENT)

    with pytest.raises(NotFoundError):
        await TemplateService(database, COVER_DEFINITION).update(_user(), uuid.uuid4(), payload)


async def test_update_maps_title_conflict_to_conflict_error() -> None:
    template_uuid = uuid.uuid4()
    database = _database()
    database.get_template.return_value = _record(template_uuid=template_uuid, user_uuid=USER_UUID)
    database.update_template.side_effect = TemplateTitleConflictError('Renamed')
    payload = TemplateUpdateRequest(title='Renamed', content=VALID_CONTENT)

    with pytest.raises(ConflictError):
        await TemplateService(database, COVER_DEFINITION).update(_user(), template_uuid, payload)


async def test_delete_own_personal_template() -> None:
    template_uuid = uuid.uuid4()
    database = _database()
    database.get_template.return_value = _record(template_uuid=template_uuid, user_uuid=USER_UUID)

    await TemplateService(database, COVER_DEFINITION).delete(_user(), template_uuid)

    database.delete_template.assert_awaited_once_with(template_uuid, TENANT_UUID)


async def test_delete_tenant_template_by_admin() -> None:
    template_uuid = uuid.uuid4()
    database = _database()
    database.get_template.return_value = _record(template_uuid=template_uuid, user_uuid=None)

    await TemplateService(database, COVER_DEFINITION).delete(_user(is_admin=True), template_uuid)

    database.delete_template.assert_awaited_once_with(template_uuid, TENANT_UUID)


async def test_delete_tenant_template_by_non_admin_is_denied() -> None:
    template_uuid = uuid.uuid4()
    database = _database()
    database.get_template.return_value = _record(template_uuid=template_uuid, user_uuid=None)

    with pytest.raises(AccessDeniedError):
        await TemplateService(database, COVER_DEFINITION).delete(_user(is_admin=False), template_uuid)

    database.delete_template.assert_not_awaited()


async def test_delete_other_users_personal_template_is_hidden() -> None:
    template_uuid = uuid.uuid4()
    database = _database()
    database.get_template.return_value = _record(template_uuid=template_uuid, user_uuid=OTHER_USER_UUID)

    with pytest.raises(NotFoundError):
        await TemplateService(database, COVER_DEFINITION).delete(_user(), template_uuid)

    database.delete_template.assert_not_awaited()

async def test_delete_other_users_by_admin_is_hidden() -> None:
    template_uuid = uuid.uuid4()
    database = _database()
    database.get_template.return_value = _record(template_uuid=template_uuid, user_uuid=OTHER_USER_UUID)

    with pytest.raises(NotFoundError):
        await TemplateService(database, COVER_DEFINITION).delete(_user(is_admin=True), template_uuid)

    database.delete_template.assert_not_awaited()


async def test_delete_missing_template_raises_not_found() -> None:
    database = _database()
    database.get_template.return_value = None

    with pytest.raises(NotFoundError):
        await TemplateService(database, COVER_DEFINITION).delete(_user(), uuid.uuid4())

    database.delete_template.assert_not_awaited()


@pytest.mark.parametrize('scope', [TemplateScope.PERSONAL, TemplateScope.TENANT])
@pytest.mark.parametrize('enabled', [False, True])
async def test_cover_page_setting_is_saved_and_returned(scope, enabled):
    database = _database()
    database.create_template.return_value = uuid.uuid4()
    cover_definition = COVER_DEFINITION.copy()
    cover_definition['version'] = '7'
    service = TemplateService(database, cover_definition)
    detail = await service.create(
        _user(is_admin=True),
        TemplateCreateRequest(title='Cover template', content=VALID_CONTENT, scope=scope, has_cover_page=enabled),
    )
    version = '7' if enabled else None
    assert detail.has_cover_page is enabled
    assert database.create_template.await_args.kwargs['cover_page_version'] == version
    record = TemplateRecord(
        uuid=detail.uuid, title=detail.title, content=database.create_template.await_args.kwargs['content'],
        tenant_uuid=TENANT_UUID, user_uuid=None if scope is TemplateScope.TENANT else USER_UUID,
        cover_page_version=version,
    )
    database.get_template.return_value = record
    database.list_templates.return_value = [record]
    reloaded = await service.get(_user(), detail.uuid)
    listed = (await service.list(_user()))[0]
    assert reloaded.has_cover_page is enabled
    assert listed.has_cover_page is enabled


@pytest.mark.parametrize('enabled', [False, True])
async def test_editing_cover_page_setting_updates_version(enabled):
    database = _database()
    template_uuid = uuid.uuid4()
    database.get_template.return_value = TemplateRecord(
        uuid=template_uuid, title='Existing', content=VALID_CONTENT,
        tenant_uuid=TENANT_UUID, user_uuid=USER_UUID,
        cover_page_version='1',
    )
    cover_definition = COVER_DEFINITION.copy()
    cover_definition['version'] = '2'
    detail = await TemplateService(database, cover_definition).update(
        _user(), template_uuid,
        TemplateUpdateRequest(title='Existing', content=VALID_CONTENT, has_cover_page=enabled),
    )
    assert detail.has_cover_page is enabled
    assert database.update_template.await_args.kwargs['cover_page_version'] == ('2' if enabled else None)


async def test_cover_sections_are_stored_but_hidden_when_editing_and_not_duplicated():
    database = _database()
    database.create_template.return_value = uuid.uuid4()
    service = TemplateService(database, COVER_DEFINITION)
    # A user-defined Projects section must remain editable, even with the same title.
    content = {'description': 'Keep metadata', 'sections': [{'title': 'Projects', 'content': 'Custom body'}]}
    detail = await service.create(
        _user(),
        TemplateCreateRequest(title='DMP', content=content, scope=TemplateScope.PERSONAL, has_cover_page=True),
    )
    stored = database.create_template.await_args.kwargs['content']
    expected_content = content.copy()
    expected_content['sections'] = COVER_DEFINITION['sections'] + content['sections']
    assert stored == expected_content
    assert detail.content == content
    record = TemplateRecord(
        uuid=detail.uuid, title=detail.title, content=stored,
        tenant_uuid=TENANT_UUID, user_uuid=USER_UUID, cover_page_version=str(COVER_DEFINITION['version']),
    )
    database.get_template.return_value = record
    for enabled in (True, False, True):
        editable = await service.get(_user(), detail.uuid)
        assert editable.content == content
        updated = await service.update(
            _user(), detail.uuid,
            TemplateUpdateRequest(title=detail.title, content=editable.content, has_cover_page=enabled),
        )
        saved = database.update_template.await_args.kwargs
        expected_sections = content['sections'].copy()
        if enabled:
            expected_sections = COVER_DEFINITION['sections'] + expected_sections
        assert saved['content']['sections'] == expected_sections
        assert updated.content == content
        database.get_template.return_value = TemplateRecord(
            uuid=detail.uuid, title=detail.title, content=saved['content'],
            tenant_uuid=TENANT_UUID, user_uuid=USER_UUID, cover_page_version=saved['cover_page_version'],
        )
    assert content['sections'] == [{'title': 'Projects', 'content': 'Custom body'}]
