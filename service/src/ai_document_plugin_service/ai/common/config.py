import logging
import os
import pathlib
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import yaml

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = 'config.yaml'
CONFIG_PATH_ENV_VAR = 'AI_DOCUMENT_PLUGIN_CONFIG_PATH'
WILDCARD = '*'


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
class AllowedApi:
    url: str
    tenant_uuid: str


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
    allowed_apis: tuple[AllowedApi, ...]
    log_level: str
    database: DatabaseConfig
    files: FilePaths
    assignment: SystemAndUserPrompt
    section_id: SystemAndUserPrompt
    dmp_generation: SystemPrompt
    dmp_polishing: SystemAndUserPrompt
    max_parallel_executions: int


@dataclass(frozen=True)
class LLMConfig:
    model: str
    api_key: str
    api_url: str
    parallel_workers: int | None = None


def _expand_env_vars(value: str) -> str:
    return os.path.expandvars(value)


def _normalize_path(path: str) -> str:
    return str(pathlib.Path(_expand_env_vars(path).strip()).expanduser())


def _get(config: dict[str, Any], *path: str, allow_empty_string: bool = False) -> Any:  # noqa: ANN401
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
    if isinstance(current, str) and not current.strip() and not allow_empty_string:
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


def _get_allowed_apis(config: dict[str, Any]) -> tuple[AllowedApi, ...]:
    raw_apis = _get(config, 'auth', 'allowed_apis')
    if not isinstance(raw_apis, list) or not raw_apis:
        msg = "Invalid config value: 'auth.allowed_apis' must be a non-empty list"
        raise TypeError(msg)

    allowed_apis: list[AllowedApi] = []
    for index, entry in enumerate(raw_apis):
        if not isinstance(entry, dict):
            msg = f"Invalid config value: 'auth.allowed_apis[{index}]' must be a mapping"
            raise TypeError(msg)

        raw_url = entry.get('url')
        raw_tenant_uuid = entry.get('tenant_uuid')
        if not isinstance(raw_url, str) or not raw_url.strip():
            msg = f"Invalid config value: 'auth.allowed_apis[{index}].url' must be a non-empty string"
            raise ValueError(msg)
        if not isinstance(raw_tenant_uuid, str) or not raw_tenant_uuid.strip():
            msg = f"Invalid config value: 'auth.allowed_apis[{index}].tenant_uuid' must be a non-empty string"
            raise ValueError(msg)

        url = raw_url.strip()
        tenant_uuid = raw_tenant_uuid.strip()
        normalized_url = url if url == WILDCARD else normalize_project_url(url)
        if tenant_uuid != WILDCARD:
            try:
                tenant_uuid = str(UUID(tenant_uuid))
            except ValueError as error:
                msg = f"Invalid config value: 'auth.allowed_apis[{index}].tenant_uuid' must be a UUID or '*'"
                raise ValueError(msg) from error

        if WILDCARD in {normalized_url, tenant_uuid}:
            logger.warning(
                "Do not use in production! Config 'auth.allowed_apis[%d]' uses a wildcard (url=%s, tenant_uuid=%s) "
                'which allows anyone to use this API.',
                index,
                normalized_url,
                tenant_uuid,
            )

        allowed_apis.append(AllowedApi(url=normalized_url, tenant_uuid=tenant_uuid))

    return tuple(allowed_apis)


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
    try:
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
            allowed_apis=_get_allowed_apis(config),
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
            max_parallel_executions=int(_get(config, 'max_parallel_executions')),
        )
    except (OSError, TypeError, ValueError, yaml.YAMLError):
        logger.exception('Failed to load application config', extra={'config_path': resolved_config_path})
        raise
