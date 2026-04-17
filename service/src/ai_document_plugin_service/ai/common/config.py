import os
import pathlib
from dataclasses import dataclass

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
    knowledge_model: str
    dmp_template: str
    config_path: str
    prompts_path: str
    assignments_output: str
    output_markdown: str
    output_pre_polish_markdown: str


@dataclass(frozen=True)
class Config:
    api_key: str
    api_url: str
    model: str
    log_level: str
    files: FilePaths
    assignment: SystemAndUserPrompt
    section_id: SystemAndUserPrompt
    dmp_generation: SystemPrompt
    dmp_polishing: SystemAndUserPrompt


def _expand_env_vars(value: str) -> str:
    return os.path.expandvars(value)


def _get(config: dict, *path: str):
    current = config
    for key in path:
        if not isinstance(current, dict) or key not in current:
            raise ValueError(
                f"Missing required config value: '{'.'.join(path)}'",
            )
        current = current[key]

    if current is None:
        raise ValueError(f"Missing required config value: '{'.'.join(path)}'")
    if isinstance(current, str) and current.strip() == '':
        raise ValueError(f"Missing required config value: '{'.'.join(path)}'")
    return current


def _get_log_level(config: dict) -> str:
    level = str(config.get('logging', {}).get('level', 'DEBUG')).strip().upper()
    allowed_levels = {'CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG', 'NOTSET'}
    if level not in allowed_levels:
        raise ValueError(
            "Invalid config value: 'logging.level' must be one of "
            + ', '.join(sorted(allowed_levels)),
        )
    return level


def _get_file_path(config: dict, key: str) -> str:
    value = _get(config, 'files', key)
    return str(value).strip()


def _resolve_existing_path(path: str) -> str:
    candidates = [path]
    if not pathlib.Path(path).is_absolute():
        candidates.append(os.path.join('jsons', path))

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
        raise ValueError('Invalid config format: expected a top-level mapping')
    if not isinstance(prompts, dict):
        raise ValueError('Invalid prompts format: expected a top-level mapping')

    return Config(
        api_key=_expand_env_vars(
            _get(config, 'llm_response_generation', 'api_key'),
        ),
        api_url=_get(config, 'llm_response_generation', 'api_url'),
        model=_get(config, 'llm_response_generation', 'model'),
        log_level=_get_log_level(config),
        files=FilePaths(
            knowledge_model=_resolve_existing_path(
                _get_file_path(config, 'knowledge_model'),
            ),
            dmp_template=_resolve_existing_path(
                _get_file_path(config, 'dmp_template'),
            ),
            config_path=_get_file_path(config, 'config_path'),
            prompts_path=configured_prompts_path,
            assignments_output=_get_file_path(config, 'assignments_output'),
            output_markdown=_get_file_path(config, 'output_markdown'),
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
    )
