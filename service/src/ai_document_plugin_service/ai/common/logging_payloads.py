import json
from collections.abc import Mapping, Sequence

from ai_document_plugin_service.ai.common.json_log_writer import make_json_safe

SENSITIVE_FIELD_NAMES = {
    'api_key',
    'apikey',
    'authorization',
    'cookie',
    'llm_api_key',
    'password',
    'refresh_token',
    'secret',
    'set-cookie',
    'token',
}
MAX_LOG_TEXT_LENGTH = 4000


def sanitize_for_logging(value: object) -> object:
    safe_value = make_json_safe(value)
    return _sanitize_value(safe_value)


def summarize_payload(value: object, *, max_chars: int = MAX_LOG_TEXT_LENGTH) -> str:
    sanitized = sanitize_for_logging(value)
    serialized = json.dumps(sanitized, ensure_ascii=False, sort_keys=True)
    return truncate_text(serialized, max_chars=max_chars)


def summarize_headers(headers: Mapping[str, str]) -> dict[str, object]:
    return _sanitize_mapping(headers)


def summarize_http_body(
    body: bytes,
    *,
    content_type: str | None = None,
    max_chars: int = MAX_LOG_TEXT_LENGTH,
) -> str | None:
    if not body:
        return None

    normalized_content_type = (content_type or '').lower()
    if 'application/json' in normalized_content_type:
        try:
            parsed = json.loads(body.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return truncate_text(body.decode('utf-8', errors='replace'), max_chars=max_chars)
        return summarize_payload(parsed, max_chars=max_chars)

    if 'application/x-www-form-urlencoded' in normalized_content_type:
        return truncate_text(body.decode('utf-8', errors='replace'), max_chars=max_chars)

    if normalized_content_type.startswith('multipart/'):
        return f'<multipart body: {len(body)} bytes>'

    return truncate_text(body.decode('utf-8', errors='replace'), max_chars=max_chars)


def truncate_text(value: str, *, max_chars: int = MAX_LOG_TEXT_LENGTH) -> str:
    if len(value) <= max_chars:
        return value
    return f'{value[:max_chars]}... <truncated {len(value) - max_chars} chars>'


def _sanitize_value(value: object) -> object:
    if isinstance(value, Mapping):
        return _sanitize_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, str):
        return truncate_text(value)
    return value


def _sanitize_mapping(value: Mapping[object, object]) -> dict[str, object]:
    sanitized: dict[str, object] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key)
        if key.lower() in SENSITIVE_FIELD_NAMES:
            sanitized[key] = '<redacted>'
            continue
        sanitized[key] = _sanitize_value(raw_value)
    return sanitized
