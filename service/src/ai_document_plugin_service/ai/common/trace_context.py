from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

_TRACE_ID_CONTEXT: ContextVar[str] = ContextVar('trace_id', default='-')


def get_trace_id() -> str:
    return _TRACE_ID_CONTEXT.get()


@contextmanager
def trace_context(trace_id: str) -> 'Iterator[None]':
    token = _TRACE_ID_CONTEXT.set(trace_id)
    try:
        yield
    finally:
        _TRACE_ID_CONTEXT.reset(token)
