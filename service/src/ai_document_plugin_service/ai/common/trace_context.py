from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from collections.abc import Iterator

_TRACE_UUID_CONTEXT: ContextVar[UUID | None] = ContextVar('trace_id', default=None)


def get_trace_uuid() -> UUID | None:
    return _TRACE_UUID_CONTEXT.get()


@contextmanager
def trace_context(trace_uuid: UUID | None) -> 'Iterator[None]':
    token = _TRACE_UUID_CONTEXT.set(trace_uuid)
    try:
        yield
    finally:
        _TRACE_UUID_CONTEXT.reset(token)
