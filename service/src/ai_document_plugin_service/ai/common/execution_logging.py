import logging
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

_run_log_context: ContextVar['RunLogContext | None'] = ContextVar('run_log_context', default=None)
_LLM_EVENT_LOGGER = logging.getLogger('ai_document_plugin_service.execution.llm')
_PIPELINE_EVENT_LOGGER = logging.getLogger('ai_document_plugin_service.execution.pipeline')


@dataclass(frozen=True)
class RunLogContext:
    run_id: str
    questionnaire_uuid: str | None = None
    template_uuid: str | None = None
    template_title: str | None = None
    knowledge_model_uuid: str | None = None
    user_uuid: str | None = None
    tenant_uuid: str | None = None


@contextmanager
def run_log_context(context: RunLogContext) -> 'Iterator[None]':
    token = _run_log_context.set(context)
    try:
        yield
    finally:
        _run_log_context.reset(token)


def get_run_log_context() -> RunLogContext | None:
    return _run_log_context.get()


def utc_now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def log_llm_event(record: dict[str, Any]) -> None:
    _emit_event(_LLM_EVENT_LOGGER, record)


def log_timing_event(event: str, **fields: Any) -> None:  # noqa: ANN401
    _emit_event(_PIPELINE_EVENT_LOGGER, {'event': event, **fields})


def log_semaphore_event(event: str, **fields: Any) -> None:  # noqa: ANN401
    _emit_event(_LLM_EVENT_LOGGER, {'event': event, **fields})


def _with_context(record: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        **record,
    }
    context = get_run_log_context()
    if context is None:
        return payload

    payload.update({field: value for field, value in context.__dict__.items() if value is not None})
    return payload


def _emit_event(logger: logging.Logger, record: dict[str, Any]) -> None:
    payload = _with_context(record)
    logger.log(_event_log_level(payload), 'Execution event', extra=payload)


def _event_log_level(record: dict[str, Any]) -> int:
    if record.get('status') in {'error', 'failed'} or record.get('state') == 'failed' or 'error_type' in record:
        return logging.ERROR
    return logging.INFO

