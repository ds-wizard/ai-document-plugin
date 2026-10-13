import asyncio
from collections.abc import Iterable
from typing import Any


async def cancel_and_wait(tasks: Iterable[asyncio.Task[Any]]) -> None:
    """Stop explicitly owned jobs and wait for their cleanup, leaving library tasks alone."""
    # Do not inspect descendants: e.g. SQLAlchemy's shielded connection-close task
    # must be allowed to finish even after its caller has been cancelled.
    owned = tuple(tasks)
    for task in owned:
        # A second cancel can interrupt a finally block already cleaning up resources.
        if not task.done() and not task.cancelling():
            task.cancel()
    await asyncio.gather(*owned, return_exceptions=True)
