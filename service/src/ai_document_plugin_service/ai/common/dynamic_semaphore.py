import threading

class DynamicSemaphore:
    """A semaphore where the maximum capacity can be changed dynamically at runtime."""

    def __init__(self, initial_limit: int):
        if initial_limit < 0:
            raise ValueError("Initial limit must be >= 0")

        self.limit = initial_limit
        self.active_count = 0
        self.condition = threading.Condition()

    def set_limit(self, new_limit: int) -> None:
        """Update the maximum number of allowed concurrent threads."""
        if new_limit < 0:
            raise ValueError("Limit must be >= 0")

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
        """Release a semaphore, decrementing the active count."""
        with self.condition:
            if self.active_count <= 0:
                raise ValueError("Semaphore released too many times")

            self.active_count -= 1
            # Wake up one waiting thread
            self.condition.notify()

    # Context Manager Protocol
    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()