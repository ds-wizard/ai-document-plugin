import threading
from types import TracebackType
from typing import Self


class DynamicSemaphore:
    """A semaphore where the maximum capacity can be changed dynamically at runtime."""

    def __init__(self, initial_limit: int) -> None:
        if initial_limit < 0:
            msg = 'Initial limit must be >= 0'
            raise ValueError(msg)

        self.limit = initial_limit
        self.active_count = 0
        self.condition = threading.Condition()

    def set_limit(self, new_limit: int) -> None:
        """Update the maximum number of allowed concurrent threads.

        Raises:
            ValueError: If ``new_limit`` is negative.
        """
        if new_limit < 0:
            msg = 'Limit must be >= 0'
            raise ValueError(msg)

        with self.condition:
            self.limit = new_limit
            # Wake up all waiting threads so they can re-evaluate the limit
            self.condition.notify_all()

    def acquire(self) -> None:
        """Acquire a semaphore. Blocks indefinitely until a slot is available."""
        with self.condition:
            # Wait until the active count is strictly less than the current limit
            while self.active_count >= self.limit:
                self.condition.wait()
            self.active_count += 1

    def release(self) -> None:
        """Release a semaphore, decrementing the active count.

        Raises:
            ValueError: If release is called when no slot is held.
        """
        with self.condition:
            if self.active_count <= 0:
                msg = 'Semaphore released too many times'
                raise ValueError(msg)

            self.active_count -= 1
            # Wake up one waiting thread
            self.condition.notify()

    def __enter__(self) -> Self:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.release()
