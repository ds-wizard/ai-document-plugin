import base64
import json
from pathlib import Path
from textwrap import dedent
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import httpx
from fastapi.testclient import TestClient

from ai_document_plugin_service.ai.common.config import CONFIG_PATH_ENV_VAR, AllowedApi, normalize_project_url
from ai_document_plugin_service.api.auth import DSW_API_URL_HEADER, is_allowed_request
from ai_document_plugin_service.app import create_app


def _make_token(*, user_uuid: str, tenant_uuid: str) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({'user_uuid': user_uuid, 'tenant_uuid': tenant_uuid}).encode()).decode()
    return f'header.{payload}'


def _write_config_files(base_dir: Path) -> Path:
    prompts_path = base_dir / 'prompts.yaml'
    prompts_path.write_text(
        dedent(
            '''
            assignment:
              temperature: 0.1
              max_tokens: 100
              system_message: "assignment system"
              user_message: "assignment user"
            section_id:
              temperature: 0.2
              max_tokens: 110
              system_message: "section system"
              user_message: "section user"
            dmp_generation:
              temperature: 0.3
              max_tokens: 120
              system_message: "generation system"
            dmp_polishing:
              temperature: 0.4
              max_tokens: 130
              system_message: "polishing system"
              user_message: "polishing user"
            '''
        ).strip()
        + '\n',
        encoding='utf-8',
    )

    config_path = base_dir / 'config.yaml'
    config_path.write_text(
        dedent(
            f'''
            llm_response_generation:
              api_key: "$TEST_API_KEY"
              api_url: "https://example.com/v1"
              model: "test-model"
              workers: 2
            dsw:
              api_url: "{ALLOWED_URL}"
            auth:
              allowed_apis:
                - url: "{ALLOWED_URL}"
                  tenant_uuid: "{ALLOWED_TENANT_UUID}"
            logging:
              level: "INFO"
            database:
              host: "localhost"
              port: 5432
              name: "ai_document_plugin"
              user: "plugin_user"
              password: "plugin_password"
              schema: "public"
            files:
              prompts_path: "prompts.yaml"
            '''
        ).strip()
        + '\n',
        encoding='utf-8',
    )
    return config_path

ALLOWED_URL = 'https://dsw.example.com'
ALLOWED_TENANT_UUID = '123e4567-e89b-12d3-a456-426614174000'
OTHER_TENANT_UUID = '00000000-0000-0000-0000-000000000000'
TEST_TOKEN = _make_token(user_uuid=ALLOWED_TENANT_UUID, tenant_uuid=ALLOWED_TENANT_UUID)


def _auth_headers(*, api_url: str = ALLOWED_URL, token: str = TEST_TOKEN) -> dict[str, str]:
    return {
        'Authorization': f'Bearer {token}',
        DSW_API_URL_HEADER: api_url,
    }


def test_normalize_project_url_strips_trailing_slash() -> None:
    assert normalize_project_url('https://dsw.example.com/') == ALLOWED_URL


def test_is_allowed_request_matches_normalized_url_and_tenant() -> None:
    allowed = (AllowedApi(url=ALLOWED_URL, tenant_uuid=ALLOWED_TENANT_UUID),)
    assert is_allowed_request(f'{ALLOWED_URL}/', UUID(ALLOWED_TENANT_UUID), allowed)
    assert not is_allowed_request('https://other.example.com', UUID(ALLOWED_TENANT_UUID), allowed)
    assert not is_allowed_request(ALLOWED_URL, UUID(OTHER_TENANT_UUID), allowed)


def test_is_allowed_request_allows_wildcard_url_or_tenant() -> None:
    wildcard_url = (AllowedApi(url='*', tenant_uuid=ALLOWED_TENANT_UUID),)
    wildcard_tenant = (AllowedApi(url=ALLOWED_URL, tenant_uuid='*'),)

    assert is_allowed_request('https://anything.example.com', UUID(ALLOWED_TENANT_UUID), wildcard_url)
    assert is_allowed_request(ALLOWED_URL, UUID(OTHER_TENANT_UUID), wildcard_tenant)


def test_health_check_does_not_require_auth(tmp_path: Path, monkeypatch) -> None:
    config_path = _write_config_files(tmp_path)
    monkeypatch.setenv(CONFIG_PATH_ENV_VAR, str(config_path))
    monkeypatch.setenv('TEST_API_KEY', 'test-secret')
    monkeypatch.chdir(tmp_path)

    client = TestClient(create_app(run_migrations=False))
    response = client.get('/health')

    assert response.status_code == 200
    assert response.json() == {'status': 'healthy'}


def test_protected_route_returns_401_without_headers(tmp_path: Path, monkeypatch) -> None:
    config_path = _write_config_files(tmp_path)
    monkeypatch.setenv(CONFIG_PATH_ENV_VAR, str(config_path))
    monkeypatch.setenv('TEST_API_KEY', 'test-secret')
    monkeypatch.chdir(tmp_path)

    client = TestClient(create_app(run_migrations=False))
    response = client.get('/templates')

    assert response.status_code == 401


def test_protected_route_returns_401_for_disallowed_url(tmp_path: Path, monkeypatch) -> None:
    config_path = _write_config_files(tmp_path)
    monkeypatch.setenv(CONFIG_PATH_ENV_VAR, str(config_path))
    monkeypatch.setenv('TEST_API_KEY', 'test-secret')
    monkeypatch.chdir(tmp_path)

    client = TestClient(create_app(run_migrations=False))
    response = client.get(
        '/templates',
        headers=_auth_headers(api_url='https://evil.example.com'),
    )

    assert response.status_code == 401


@patch('ai_document_plugin_service.api.auth.httpx.get')
def test_protected_route_returns_401_when_dsw_rejects_token(
    mock_httpx_get: MagicMock,
    tmp_path: Path,
    monkeypatch,
) -> None:
    mock_httpx_get.return_value = httpx.Response(403, request=httpx.Request('GET', ALLOWED_URL))

    config_path = _write_config_files(tmp_path)
    monkeypatch.setenv(CONFIG_PATH_ENV_VAR, str(config_path))
    monkeypatch.setenv('TEST_API_KEY', 'test-secret')
    monkeypatch.chdir(tmp_path)

    client = TestClient(create_app(run_migrations=False))
    response = client.get('/templates', headers=_auth_headers())

    assert response.status_code == 401


@patch('ai_document_plugin_service.api.auth.httpx.get')
@patch('ai_document_plugin_service.app.PostgresDB')
def test_protected_route_succeeds_when_dsw_validates_user(
    mock_postgres_db: MagicMock,
    mock_httpx_get: MagicMock,
    tmp_path: Path,
    monkeypatch,
) -> None:
    mock_httpx_get.return_value = httpx.Response(200, request=httpx.Request('GET', ALLOWED_URL))
    mock_postgres_db.return_value.list_templates = AsyncMock(
        return_value=[{'uuid': 'template-1', 'title': 'Template 1'}],
    )
    mock_postgres_db.return_value.dispose = AsyncMock()

    config_path = _write_config_files(tmp_path)
    monkeypatch.setenv(CONFIG_PATH_ENV_VAR, str(config_path))
    monkeypatch.setenv('TEST_API_KEY', 'test-secret')
    monkeypatch.chdir(tmp_path)

    client = TestClient(create_app(run_migrations=False))
    response = client.get('/templates', headers=_auth_headers())

    assert response.status_code == 200
    assert response.json() == [{'uuid': 'template-1', 'title': 'Template 1'}]
    mock_httpx_get.assert_called_once()
