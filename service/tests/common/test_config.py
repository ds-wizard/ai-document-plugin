import shutil
from pathlib import Path
from unittest.mock import patch

import yaml
from fastapi.testclient import TestClient

from ai_document_plugin_service.ai.common.config import (
    CONFIG_PATH_ENV_VAR,
    AllowedApi,
    load_config,
)
from ai_document_plugin_service.app import create_app

SERVICE_DIR = Path(__file__).resolve().parents[2]
TEST_CONFIG_PATH = SERVICE_DIR / 'config.test.yaml'
TEST_PROMPTS_PATH = SERVICE_DIR / 'prompts.yaml'


def _copy_test_config(
    base_dir: Path,
    *,
    config_name: str = 'config.yaml',
    allowed_apis: list[dict[str, str]] | None = None,
    prompts_path: str | None = None,
) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(TEST_PROMPTS_PATH, base_dir / 'prompts.yaml')

    config = yaml.safe_load(TEST_CONFIG_PATH.read_text(encoding='utf-8'))
    if allowed_apis is not None:
        config['auth']['allowed_apis'] = allowed_apis
    if prompts_path is not None:
        config['files']['prompts_path'] = prompts_path

    config_path = base_dir / config_name
    config_path.write_text(yaml.safe_dump(config), encoding='utf-8')
    return config_path


def test_load_config_uses_env_config_path_and_resolves_prompts_relative_to_it(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(CONFIG_PATH_ENV_VAR, str(TEST_CONFIG_PATH))
    monkeypatch.chdir(tmp_path)

    config = load_config()

    assert config.allowed_apis == (
        AllowedApi(url='https://your-dsw-instance.example.com/wizard-api', tenant_uuid='123e4567-e89b-12d3-a456-426614174000'),
    )
    assert config.files.prompts_path == str(TEST_PROMPTS_PATH)


def test_load_config_warns_on_wildcard_allowed_apis_entry(
    tmp_path: Path,
    monkeypatch,
    caplog,
) -> None:
    config_path = _copy_test_config(
        tmp_path,
        allowed_apis=[{'url': '*', 'tenant_uuid': '*'}],
    )
    monkeypatch.setenv(CONFIG_PATH_ENV_VAR, str(config_path))
    monkeypatch.chdir(tmp_path)

    with caplog.at_level('WARNING'):
        config = load_config()

    assert config.allowed_apis == (AllowedApi(url='*', tenant_uuid='*'),)
    assert any('wildcard' in record.message for record in caplog.records)


def test_load_config_falls_back_to_default_path_when_env_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = _copy_test_config(tmp_path)
    monkeypatch.delenv(CONFIG_PATH_ENV_VAR, raising=False)
    monkeypatch.chdir(tmp_path)

    config = load_config()

    assert config.files.prompts_path == str(config_path.parent / 'prompts.yaml')


def test_load_config_rejects_absolute_prompts_path_in_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    absolute_prompts_path = tmp_path / 'prompts.yaml'
    _copy_test_config(tmp_path, prompts_path=absolute_prompts_path.as_posix())
    monkeypatch.chdir(tmp_path)

    try:
        load_config()
    except ValueError as error:
        assert str(error) == "Invalid config value: 'files.prompts_path' must be a relative path"
    else:
        raise AssertionError('Expected load_config() to reject an absolute prompts path')


def test_create_app_stores_the_resolved_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(CONFIG_PATH_ENV_VAR, str(TEST_CONFIG_PATH))
    monkeypatch.chdir(tmp_path)

    app = create_app(run_migrations=False)

    assert app.state.config.files.prompts_path == str(TEST_PROMPTS_PATH)


@patch('ai_document_plugin_service.app.run_startup_migrations')
def test_app_startup_runs_migrations_with_loaded_config(
    mock_run_startup_migrations,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(CONFIG_PATH_ENV_VAR, str(TEST_CONFIG_PATH))
    monkeypatch.chdir(tmp_path)

    app = create_app()

    client = TestClient(app)
    response = client.get('/health')

    assert response.status_code == 200
    mock_run_startup_migrations.assert_called_once_with(app.state.config, str(TEST_CONFIG_PATH))
