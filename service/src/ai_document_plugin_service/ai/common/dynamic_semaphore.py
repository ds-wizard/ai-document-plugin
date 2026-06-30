import asyncio
from collections import deque
from types import TracebackType
from typing import Self


class _Waiter:
    """A queued acquirer.

    ``granted`` records whether ``_wake_waiters`` has charged a slot to this
    waiter. It is the source of truth for slot ownership during the race between
    a wake (``set_result``) and a cancellation: even on a single loop, cancelling
    a task whose future already holds a result still raises ``CancelledError``
    (via the task's ``_must_cancel`` flag), so ``granted`` tells the cancel
    handler whether a slot must be reclaimed.
    """

    __slots__ = ('future', 'granted')

    def __init__(self, future: asyncio.Future[None]) -> None:
        self.future = future
        self.granted = False


class DynamicSemaphore:
    """Async semaphore with a dynamically adjustable limit.

    Single event loop only: every ``acquire`` / ``release`` / ``set_limit`` call
    must happen on the same loop. There is no internal locking -- correctness
    relies on asyncio's cooperative, single-threaded scheduling. The methods that
    mutate shared state (``release``, ``set_limit``, ``_wake_waiters``) contain no
    ``await`` points, so they run to completion atomically with respect to other
    coroutines. The first ``acquire`` binds the semaphore to its loop; using it
    from another loop afterwards raises ``RuntimeError``.
    """

    def __init__(self, initial_limit: int) -> None:
        if initial_limit < 0:
            msg = 'Initial limit must be >= 0'
            raise ValueError(msg)

        self.limit = initial_limit
        self._active_count = 0
        self._loop: asyncio.AbstractEventLoop | None = None
        self._waiters: deque[_Waiter] = deque()

    def set_limit(self, new_limit: int) -> None:
        """Update the maximum number of allowed concurrent holders.

        Raises:
            ValueError: If ``new_limit`` is negative.
        """
        if new_limit < 0:
            msg = 'Limit must be >= 0'
            raise ValueError(msg)

        self.limit = new_limit
        self._wake_waiters()

    async def acquire(self) -> None:
        loop = self._bind_loop()
        if self._active_count < self.limit:
            self._active_count += 1
            return

        future: asyncio.Future[None] = loop.create_future()
        waiter = _Waiter(future)
        self._waiters.append(waiter)

        try:
            await future
        except asyncio.CancelledError:
            if waiter.granted:
                # A slot was charged to us before the cancellation took effect;
                # hand it back to the next waiter.
                self._active_count -= 1
                self._wake_waiters()
            elif waiter in self._waiters:
                # Cancelled while still queued, never granted a slot.
                self._waiters.remove(waiter)
            raise

    async def release(self) -> None:
        if self._active_count <= 0:
            msg = 'Semaphore released too many times'
            raise ValueError(msg)

        self._active_count -= 1
        self._wake_waiters()

    def _wake_waiters(self) -> None:
        while self._waiters and self._active_count < self.limit:
            waiter = self._waiters.popleft()
            if waiter.future.done():
                # Already cancelled before we reached it; skip without charging
                # a slot. The waiter's own cancel handler is a no-op for it.
                continue
            waiter.granted = True
            self._active_count += 1
            waiter.future.set_result(None)

    def _bind_loop(self) -> asyncio.AbstractEventLoop:
        loop = asyncio.get_running_loop()
        if self._loop is None:
            self._loop = loop
        elif self._loop is not loop:
            msg = 'DynamicSemaphore is bound to a single event loop'
            raise RuntimeError(msg)
        return loop

    async def __aenter__(self) -> Self:
        await self.acquire()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.release()
