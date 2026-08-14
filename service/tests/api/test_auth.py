import base64
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import httpx
from fastapi.testclient import TestClient

from ai_document_plugin_service.ai.common.config import CONFIG_PATH_ENV_VAR, AllowedApi, normalize_project_url
from ai_document_plugin_service.ai.persistence.database import TemplateRecord
from ai_document_plugin_service.api.auth import DSW_API_URL_HEADER, is_allowed_request
from ai_document_plugin_service.app import create_app

TEST_CONFIG_PATH = Path(__file__).resolve().parents[2] / 'config.test.yaml'

ALLOWED_URL = 'https://your-dsw-instance.example.com/wizard-api'
ALLOWED_TENANT_UUID = '123e4567-e89b-12d3-a456-426614174000'
OTHER_TENANT_UUID = '00000000-0000-0000-0000-000000000000'


def _make_token(*, user_uuid: str, tenant_uuid: str) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({'user_uuid': user_uuid, 'tenant_uuid': tenant_uuid}).encode()).decode()
    return f'header.{payload}'


TEST_TOKEN = _make_token(user_uuid=ALLOWED_TENANT_UUID, tenant_uuid=ALLOWED_TENANT_UUID)


def _use_test_config(monkeypatch) -> None:
    monkeypatch.setenv(CONFIG_PATH_ENV_VAR, str(TEST_CONFIG_PATH))


def _auth_headers(*, api_url: str = ALLOWED_URL, token: str = TEST_TOKEN) -> dict[str, str]:
    return {
        'Authorization': f'Bearer {token}',
        DSW_API_URL_HEADER: api_url,
    }


def test_normalize_project_url_strips_trailing_slash() -> None:
    assert normalize_project_url(f'{ALLOWED_URL}/') == ALLOWED_URL


def test_is_allowed_request_matches_normalized_url_and_tenant() -> None:
    allowed_api = (AllowedApi(url=ALLOWED_URL, tenant_uuid=ALLOWED_TENANT_UUID),AllowedApi(url="https://some-other-url.com", tenant_uuid=OTHER_TENANT_UUID))
    assert is_allowed_request(f'{ALLOWED_URL}/', UUID(ALLOWED_TENANT_UUID), allowed_api)
    assert not is_allowed_request('https://other.example.com', UUID(ALLOWED_TENANT_UUID), allowed_api)
    assert not is_allowed_request(ALLOWED_URL, UUID(OTHER_TENANT_UUID), allowed_api)


def test_is_allowed_request_allows_wildcard_url_or_tenant() -> None:
    wildcard_url = (AllowedApi(url='*', tenant_uuid=ALLOWED_TENANT_UUID),)
    wildcard_tenant = (AllowedApi(url=ALLOWED_URL, tenant_uuid='*'),)

    assert is_allowed_request('https://anything.example.com', UUID(ALLOWED_TENANT_UUID), wildcard_url)
    assert is_allowed_request(ALLOWED_URL, UUID(OTHER_TENANT_UUID), wildcard_tenant)


def test_health_check_does_not_require_auth(monkeypatch) -> None:
    _use_test_config(monkeypatch)

    client = TestClient(create_app(run_migrations=False))
    response = client.get('/health')

    assert response.status_code == 200
    assert response.json() == {'status': 'healthy'}


def test_protected_route_returns_401_without_headers(monkeypatch) -> None:
    _use_test_config(monkeypatch)

    client = TestClient(create_app(run_migrations=False))
    response = client.get('/templates')

    assert response.status_code == 401


def test_protected_route_returns_401_for_disallowed_url(monkeypatch) -> None:
    _use_test_config(monkeypatch)

    client = TestClient(create_app(run_migrations=False))
    response = client.get(
        '/templates',
        headers=_auth_headers(api_url='https://evil.example.com'),
    )

    assert response.status_code == 401


@patch('ai_document_plugin_service.api.auth.httpx.get')
def test_protected_route_returns_401_when_dsw_rejects_token(
    mock_httpx_get: MagicMock,
    monkeypatch,
) -> None:
    mock_httpx_get.return_value = httpx.Response(403, request=httpx.Request('GET', ALLOWED_URL))

    _use_test_config(monkeypatch)

    client = TestClient(create_app(run_migrations=False))
    response = client.get('/templates', headers=_auth_headers())

    assert response.status_code == 401


@patch('ai_document_plugin_service.api.auth.httpx.get')
@patch('ai_document_plugin_service.di.PostgresDB')
def test_protected_route_succeeds_when_dsw_validates_user(
    mock_postgres_db: MagicMock,
    mock_httpx_get: MagicMock,
    monkeypatch,
) -> None:
    mock_httpx_get.return_value = httpx.Response(
        200,
        request=httpx.Request('GET', ALLOWED_URL),
        json={
            'role': {
                'name': 'Researcher',
                'permissions': ['ProjectsViewRolePermission'],
                'uuid': '31ccc093-3ab0-4459-b109-ab1d8dc2313f',
            }
        },
    )
    template_uuid = UUID('99999999-9999-9999-9999-999999999999')
    mock_postgres_db.return_value.list_templates = AsyncMock(
        return_value=[
            TemplateRecord(
                uuid=template_uuid,
                title='Template 1',
                content={'sections': []},
                tenant_uuid=UUID(ALLOWED_TENANT_UUID),
                user_uuid=None,
            ),
        ],
    )
    mock_postgres_db.return_value.dispose = AsyncMock()

    _use_test_config(monkeypatch)

    client = TestClient(create_app(run_migrations=False))
    response = client.get('/templates', headers=_auth_headers())

    assert response.status_code == 200
    assert response.json() == [{'uuid': str(template_uuid), 'title': 'Template 1', 'scope': 'tenant'}]
    mock_httpx_get.assert_called_once()
