from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from collections.abc import Iterator

_TRACE_ID_CONTEXT: ContextVar[UUID | None] = ContextVar('trace_id', default=None)


def get_trace_id() -> UUID | None:
    return _TRACE_ID_CONTEXT.get()


@contextmanager
def trace_context(trace_id: UUID | None) -> 'Iterator[None]':
    token = _TRACE_ID_CONTEXT.set(trace_id)
    try:
        yield
    finally:
        _TRACE_ID_CONTEXT.reset(token)
