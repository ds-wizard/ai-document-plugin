import os
import pathlib
from dataclasses import dataclass
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = 'config.yaml'


@dataclass(frozen=True)
class SystemAndUserPrompt:
    temperature: float
    max_tokens: int
    system_message: str
    user_message: str


@dataclass(frozen=True)
class SystemPrompt:
    temperature: float
    max_tokens: int
    system_message: str


@dataclass(frozen=True)
class FilePaths:
    config_path: str
    prompts_path: str
    output_markdown: str
    output_with_stats: str
    output_pre_polish_markdown: str


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    name: str
    user: str
    password: str
    schema: str


@dataclass(frozen=True)
class Config:
    api_key: str
    api_url: str
    dsw_api_url: str
    model: str
    log_level: str
    database: DatabaseConfig
    files: FilePaths
    assignment: SystemAndUserPrompt
    section_id: SystemAndUserPrompt
    dmp_generation: SystemPrompt
    dmp_polishing: SystemAndUserPrompt
    parallel_workers: int


def _expand_env_vars(value: str) -> str:
    return os.path.expandvars(value)


def _get(config: dict[str, Any], *path: str) -> Any:  # noqa: ANN401
    current = config
    for key in path:
        if not isinstance(current, dict) or key not in current:
            msg = f"Missing required config value: '{'.'.join(path)}'"
            raise ValueError(
                msg,
            )
        current = current[key]

    if current is None:
        msg = f"Missing required config value: '{'.'.join(path)}'"
        raise ValueError(msg)
    if isinstance(current, str) and not current.strip():
        msg = f"Missing required config value: '{'.'.join(path)}'"
        raise ValueError(msg)
    return current


def _get_log_level(config: dict) -> str:
    level = str(config.get('logging', {}).get('level', 'DEBUG')).strip().upper()
    allowed_levels = {'CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG', 'NOTSET'}
    if level not in allowed_levels:
        raise ValueError(
            "Invalid config value: 'logging.level' must be one of " + ', '.join(sorted(allowed_levels)),
        )
    return level


def _get_file_path(config: dict, key: str) -> str:
    value = _get(config, 'files', key)
    return str(value).strip()


def _get_parallel_workers(config: dict[str, Any]) -> int:
    workers = config.get('llm_response_generation', {}).get('workers', 1)
    try:
        workers_int = int(workers)
    except (TypeError, ValueError) as exc:
        msg = "Invalid config value: 'parallelism.workers' must be an integer >= 1"
        raise ValueError(msg) from exc
    if workers_int < 1:
        msg = "Invalid config value: 'parallelism.workers' must be >= 1"
        raise ValueError(msg)
    return workers_int


def _resolve_existing_path(path: str) -> str:
    candidates = [path]
    if not pathlib.Path(path).is_absolute():
        candidates.append(str(pathlib.Path('jsons') / path))

    for candidate in candidates:
        if pathlib.Path(candidate).exists():
            return candidate
    return path


def load_config(
    config_path: str = DEFAULT_CONFIG_PATH,
    prompts_path: str | None = None,
) -> Config:
    with pathlib.Path(config_path).open(encoding='utf-8') as handle:
        config = yaml.safe_load(handle)

    configured_prompts_path = prompts_path
    if configured_prompts_path is None:
        configured_prompts_path = _get_file_path(config, 'prompts_path')
    with pathlib.Path(configured_prompts_path).open(encoding='utf-8') as handle:
        prompts = yaml.safe_load(handle)

    if not isinstance(config, dict):
        msg = 'Invalid config format: expected a top-level mapping'
        raise TypeError(msg)
    if not isinstance(prompts, dict):
        msg = 'Invalid prompts format: expected a top-level mapping'
        raise TypeError(msg)

    return Config(
        api_key=_expand_env_vars(
            _get(config, 'llm_response_generation', 'api_key'),
        ),
        api_url=_get(config, 'llm_response_generation', 'api_url'),
        model=_get(config, 'llm_response_generation', 'model'),
        dsw_api_url=_get(config, 'dsw', 'api_url'),
        log_level=_get_log_level(config),
        database=DatabaseConfig(
            host=_expand_env_vars(_get(config, 'database', 'host')),
            port=int(_expand_env_vars(str(_get(config, 'database', 'port')))),
            name=_expand_env_vars(_get(config, 'database', 'name')),
            user=_expand_env_vars(_get(config, 'database', 'user')),
            password=_expand_env_vars(_get(config, 'database', 'password')),
            schema=_expand_env_vars(_get(config, 'database', 'schema')),
        ),
        files=FilePaths(
            config_path=_get_file_path(config, 'config_path'),
            prompts_path=configured_prompts_path,
            output_markdown=_get_file_path(config, 'output_markdown'),
            output_with_stats=_get_file_path(config, 'output_with_stats'),
            output_pre_polish_markdown=_get_file_path(
                config,
                'output_pre_polish_markdown',
            ),
        ),
        assignment=SystemAndUserPrompt(
            temperature=float(_get(prompts, 'assignment', 'temperature')),
            max_tokens=int(_get(prompts, 'assignment', 'max_tokens')),
            system_message=_get(prompts, 'assignment', 'system_message'),
            user_message=_get(prompts, 'assignment', 'user_message'),
        ),
        section_id=SystemAndUserPrompt(
            temperature=float(_get(prompts, 'section_id', 'temperature')),
            max_tokens=int(_get(prompts, 'section_id', 'max_tokens')),
            system_message=_get(prompts, 'section_id', 'system_message'),
            user_message=_get(prompts, 'section_id', 'user_message'),
        ),
        dmp_generation=SystemPrompt(
            temperature=float(_get(prompts, 'dmp_generation', 'temperature')),
            max_tokens=int(_get(prompts, 'dmp_generation', 'max_tokens')),
            system_message=_get(prompts, 'dmp_generation', 'system_message'),
        ),
        dmp_polishing=SystemAndUserPrompt(
            temperature=float(_get(prompts, 'dmp_polishing', 'temperature')),
            max_tokens=int(_get(prompts, 'dmp_polishing', 'max_tokens')),
            system_message=_get(prompts, 'dmp_polishing', 'system_message'),
            user_message=_get(prompts, 'dmp_polishing', 'user_message'),
        ),
        parallel_workers=_get_parallel_workers(config),
    )
