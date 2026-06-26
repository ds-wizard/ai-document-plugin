import asyncio
import logging
import threading
from collections.abc import Callable, Coroutine
from concurrent.futures import Future
from typing import Any

logger = logging.getLogger(__name__)

MAX_CONCURRENT_PIPELINE_JOBS = 2

JobFactory = Callable[[], Coroutine[Any, Any, None]]


def format_queue_progress(jobs_ahead: int) -> str:
    if jobs_ahead <= 0:
        return 'Your dmp is next in the queue.'
    if jobs_ahead == 1:
        return '1 dmp ahead of you in the queue.'
    return f'{jobs_ahead} dmps ahead of you in the queue.'


class PipelineQueueManager:
    """FIFO pipeline job queue running coroutines on a dedicated event loop.

    Jobs are coroutines scheduled onto a single background event loop and gated by an
    """

    def __init__(self, max_concurrent_jobs: int = MAX_CONCURRENT_PIPELINE_JOBS) -> None:
        self._max_concurrent_jobs = max_concurrent_jobs
        self._order: list[str] = []
        self._order_lock = threading.Lock()
        self._semaphore = asyncio.Semaphore(max_concurrent_jobs)
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop,
            name='pipeline-queue',
            daemon=True,
        )
        self._thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def enqueue(self, run_id: str, job: JobFactory) -> None:
        with self._order_lock:
            self._order.append(run_id)

        future = asyncio.run_coroutine_threadsafe(self._run_job(run_id, job), self._loop)
        future.add_done_callback(self._log_job_failure)

    def progress_message(self, run_id: str) -> str | None:
        jobs_waiting_ahead = self._jobs_waiting_ahead(run_id)
        if jobs_waiting_ahead is None:
            return None
        return format_queue_progress(jobs_waiting_ahead)

    def remove(self, run_id: str) -> None:
        with self._order_lock:
            try:
                self._order.remove(run_id)
            except ValueError:
                return

    def _jobs_waiting_ahead(self, run_id: str) -> int | None:
        with self._order_lock:
            try:
                queue_index = self._order.index(run_id)
            except ValueError:
                return None
        return queue_index - self._max_concurrent_jobs

    async def _run_job(self, run_id: str, job: JobFactory) -> None:
        try:
            async with self._semaphore:
                await job()
        finally:
            self.remove(run_id)

    @staticmethod
    def _log_job_failure(future: Future[None]) -> None:
        # Jobs are expected to handle their own errors; this guards against an
        # unhandled exception being silently swallowed by the background loop.
        error = future.exception()
        if error is not None:
            logger.error('Pipeline job crashed without handling its error', exc_info=error)


pipeline_queue_manager = PipelineQueueManager()
