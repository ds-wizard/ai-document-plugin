from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID

_RUN_CONTEXT: ContextVar['RunLogContext | None'] = ContextVar('run_log_context', default=None)


@dataclass(frozen=True)
class RunLogContext:
    """Identifiers of the pipeline run in progress; the logging filter adds them to every log record."""

    run_id: UUID
    questionnaire_uuid: UUID | None = None
    template_uuid: UUID | None = None
    template_title: str | None = None
    knowledge_model_uuid: UUID | None = None
    user_uuid: UUID | None = None
    tenant_uuid: UUID | None = None


def get_run_log_context() -> RunLogContext | None:
    return _RUN_CONTEXT.get()


@contextmanager
def run_log_context(context: RunLogContext) -> Iterator[None]:
    token = _RUN_CONTEXT.set(context)
    try:
        yield
    finally:
        _RUN_CONTEXT.reset(token)
