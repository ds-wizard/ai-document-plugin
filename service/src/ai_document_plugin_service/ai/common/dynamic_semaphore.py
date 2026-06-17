import asyncio
import threading
from collections import deque
from types import TracebackType
from typing import Self


class DynamicSemaphore:
    """Process-wide async semaphore with a dynamically adjustable limit.

    Waiters on different event loops share one counter. A lightweight thread lock
    protects shared state; waiting coroutines suspend on loop-local futures instead
    of blocking threads.
    """

    def __init__(self, initial_limit: int) -> None:
        if initial_limit < 0:
            msg = 'Initial limit must be >= 0'
            raise ValueError(msg)

        self.limit = initial_limit
        self._active_count = 0
        self._lock = threading.Lock()
        self._waiters: deque[tuple[asyncio.AbstractEventLoop, asyncio.Future[None]]] = deque()

    def set_limit(self, new_limit: int) -> None:
        """Update the maximum number of allowed concurrent holders."""
        if new_limit < 0:
            msg = 'Limit must be >= 0'
            raise ValueError(msg)

        with self._lock:
            self.limit = new_limit
            self._wake_waiters()

    async def acquire(self) -> None:
        loop = asyncio.get_running_loop()
        with self._lock:
            if self._active_count < self.limit:
                self._active_count += 1
                return
            future: asyncio.Future[None] = loop.create_future()
            waiter = (loop, future)
            self._waiters.append(waiter)

        try:
            await future
        except asyncio.CancelledError:
            with self._lock:
                if waiter in self._waiters:
                    self._waiters.remove(waiter)
                elif future.done() and not future.cancelled():
                    self._active_count -= 1
                    self._wake_waiters()
            raise

    async def release(self) -> None:
        with self._lock:
            if self._active_count <= 0:
                msg = 'Semaphore released too many times'
                raise ValueError(msg)

            self._active_count -= 1
            self._wake_waiters()

    def _wake_waiters(self) -> None:
        while self._waiters and self._active_count < self.limit:
            loop, future = self._waiters.popleft()
            self._active_count += 1
            if future.done():
                continue
            loop.call_soon_threadsafe(future.set_result, None)

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
