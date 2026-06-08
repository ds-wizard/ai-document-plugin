import os
import pathlib
from dataclasses import dataclass, replace
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = 'config.yaml'
CONFIG_PATH_ENV_VAR = 'AI_DOCUMENT_PLUGIN_CONFIG_PATH'


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
    prompts_path: str


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
    allowed_project_urls: tuple[str, ...]
    model: str
    log_level: str
    database: DatabaseConfig
    files: FilePaths
    assignment: SystemAndUserPrompt
    section_id: SystemAndUserPrompt
    dmp_generation: SystemPrompt
    dmp_polishing: SystemAndUserPrompt
    parallel_workers: int


@dataclass(frozen=True)
class LLMConfigOverride:
    model: str | None = None
    api_key: str | None = None
    api_url: str | None = None
    parallel_workers: int | None = None


def _expand_env_vars(value: str) -> str:
    return os.path.expandvars(value)


def _normalize_path(path: str) -> str:
    return str(pathlib.Path(_expand_env_vars(path).strip()).expanduser())


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
    return _normalize_path(str(value))


def _get_relative_file_path(config: dict, key: str) -> str:
    value = _get_file_path(config, key)
    if pathlib.Path(value).is_absolute():
        msg = f"Invalid config value: 'files.{key}' must be a relative path"
        raise ValueError(msg)
    return value


def normalize_project_url(url: str) -> str:
    return url.strip().rstrip('/')


def _get_allowed_project_urls(config: dict[str, Any]) -> tuple[str, ...]:
    raw_urls = _get(config, 'auth', 'allowed_project_urls')
    if not isinstance(raw_urls, list) or not raw_urls:
        msg = "Invalid config value: 'auth.allowed_project_urls' must be a non-empty list"
        raise ValueError(msg)

    normalized: list[str] = []
    for index, entry in enumerate(raw_urls):
        if not isinstance(entry, str) or not entry.strip():
            msg = f"Invalid config value: 'auth.allowed_project_urls[{index}]' must be a non-empty string"
            raise ValueError(msg)
        normalized.append(normalize_project_url(entry))

    return tuple(normalized)


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


def _resolve_existing_path(path: str, *, base_dir: pathlib.Path | None = None) -> str:
    normalized_path = _normalize_path(path)
    path_obj = pathlib.Path(normalized_path)
    candidates: list[pathlib.Path] = []
    if base_dir is not None and not path_obj.is_absolute():
        candidates.append(base_dir / path_obj)

    candidates.append(path_obj)
    if not path_obj.is_absolute():
        candidates.append(pathlib.Path('jsons') / path_obj)

    for candidate in candidates:
        if candidate.exists():
            return str(candidate.resolve())
    return str(candidates[0].resolve(strict=False))


def resolve_config_path(config_path: str | None = None) -> str:
    if config_path is not None:
        normalized_path = _normalize_path(config_path)
        if not normalized_path:
            msg = 'Config path must not be empty'
            raise ValueError(msg)
        return normalized_path

    env_config_path = os.getenv(CONFIG_PATH_ENV_VAR)
    if env_config_path is not None and env_config_path.strip():
        return _normalize_path(env_config_path)
    return DEFAULT_CONFIG_PATH


def load_config(config_path: str | None = None) -> Config:
    resolved_config_path = _resolve_existing_path(resolve_config_path(config_path))
    config_dir = pathlib.Path(resolved_config_path).parent

    with pathlib.Path(resolved_config_path).open(encoding='utf-8') as handle:
        config = yaml.safe_load(handle)

    configured_prompts_path = _get_relative_file_path(config, 'prompts_path')
    resolved_prompts_path = _resolve_existing_path(configured_prompts_path, base_dir=config_dir)

    with pathlib.Path(resolved_prompts_path).open(encoding='utf-8') as handle:
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
        allowed_project_urls=_get_allowed_project_urls(config),
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
            prompts_path=resolved_prompts_path,
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


def apply_llm_override(config: Config, override: LLMConfigOverride | None = None) -> Config:
    if override is None:
        return config

    return replace(
        config,
        model=override.model or config.model,
        api_key=override.api_key or config.api_key,
        api_url=override.api_url or config.api_url,
        parallel_workers=override.parallel_workers or config.parallel_workers,
    )
