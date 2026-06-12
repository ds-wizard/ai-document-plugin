from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

from fastapi.testclient import TestClient

from ai_document_plugin_service.ai.common.config import (
    CONFIG_PATH_ENV_VAR,
    load_config,
)
from ai_document_plugin_service.app import create_app


def _write_config_files(
    base_dir: Path,
    *,
    config_name: str = 'config.yaml',
    prompts_name: str = 'prompts.yaml',
    model: str = 'test-model',
) -> Path:
    prompts_path = base_dir / prompts_name
    prompts_path.parent.mkdir(parents=True, exist_ok=True)
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

    config_path = base_dir / config_name
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        dedent(
            f'''
            llm_response_generation:
              api_key: "$TEST_API_KEY"
              api_url: "https://example.com/v1"
              model: "{model}"
              workers: 2
            dsw:
              api_url: "https://dsw.example.com"
            auth:
              allowed_project_urls:
                - "https://dsw.example.com"
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
              prompts_path: "{prompts_name}"
            '''
        ).strip()
        + '\n',
        encoding='utf-8',
    )
    return config_path


def test_load_config_uses_env_config_path_and_resolves_prompts_relative_to_it(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = _write_config_files(
        tmp_path / 'custom-config',
        config_name='service.custom.yaml',
        prompts_name='nested/prompts.custom.yaml',
        model='env-model',
    )
    monkeypatch.setenv(CONFIG_PATH_ENV_VAR, str(config_path))
    monkeypatch.setenv('TEST_API_KEY', 'secret-from-env')
    monkeypatch.chdir(tmp_path)

    config = load_config()

    assert config.allowed_project_urls == ('https://dsw.example.com',)
    assert config.files.prompts_path == str(config_path.parent / 'nested/prompts.custom.yaml')


def test_load_config_falls_back_to_default_path_when_env_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = _write_config_files(tmp_path, model='default-model')
    monkeypatch.delenv(CONFIG_PATH_ENV_VAR, raising=False)
    monkeypatch.setenv('TEST_API_KEY', 'default-secret')
    monkeypatch.chdir(tmp_path)

    config = load_config()

    assert config.files.prompts_path == str(config_path.parent / 'prompts.yaml')


def test_load_config_rejects_absolute_prompts_path_in_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    absolute_prompts_path = tmp_path / 'external-prompts.yaml'
    absolute_prompts_path.write_text(
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
    config_path = tmp_path / 'config.yaml'
    config_path.write_text(
        dedent(
            f'''
            llm_response_generation:
              api_key: "$TEST_API_KEY"
              api_url: "https://example.com/v1"
              model: "invalid-prompts-model"
              workers: 2
            dsw:
              api_url: "https://dsw.example.com"
            auth:
              allowed_project_urls:
                - "https://dsw.example.com"
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
              prompts_path: "{absolute_prompts_path.as_posix()}"
            '''
        ).strip()
        + '\n',
        encoding='utf-8',
    )
    monkeypatch.setenv('TEST_API_KEY', 'default-secret')
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
    config_path = _write_config_files(
        tmp_path / 'runtime',
        config_name='runtime-config.yaml',
        prompts_name='runtime-prompts.yaml',
    )
    monkeypatch.setenv(CONFIG_PATH_ENV_VAR, str(config_path))
    monkeypatch.setenv('TEST_API_KEY', 'create-app-secret')
    monkeypatch.chdir(tmp_path)

    app = create_app(run_migrations=False)

    assert app.state.config.files.prompts_path == str(config_path.parent / 'runtime-prompts.yaml')


@patch('ai_document_plugin_service.app.run_startup_migrations')
def test_app_startup_runs_migrations_with_loaded_config(
    mock_run_startup_migrations,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = _write_config_files(
        tmp_path / 'runtime',
        config_name='runtime-config.yaml',
        prompts_name='runtime-prompts.yaml',
    )
    monkeypatch.setenv(CONFIG_PATH_ENV_VAR, str(config_path))
    monkeypatch.setenv('TEST_API_KEY', 'create-app-secret')
    monkeypatch.chdir(tmp_path)

    app = create_app()

    client = TestClient(app)
    response = client.get('/health')

    assert response.status_code == 200
    mock_run_startup_migrations.assert_called_once_with(app.state.config, str(config_path))
