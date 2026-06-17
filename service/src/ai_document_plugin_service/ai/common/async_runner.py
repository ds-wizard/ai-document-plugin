import asyncio
from collections.abc import Coroutine
from typing import TypeVar

T = TypeVar('T')


def run_coroutine(coro: Coroutine[object, object, T]) -> T:
    """Run a coroutine from synchronous Haystack components."""
    return asyncio.run(coro)
