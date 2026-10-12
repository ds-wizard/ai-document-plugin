import asyncio
import logging
import threading
from collections.abc import AsyncIterator, Callable, Coroutine
from concurrent.futures import Future
from contextlib import asynccontextmanager
from contextvars import Context, ContextVar
from typing import Any
from uuid import UUID

from ai_document_plugin_service.ai.common.trace_context import trace_context

logger = logging.getLogger(__name__)

# Each run installs its own set. Child tasks inherit the context and share that
# same set, allowing us to track descendants without touching other runs.
_JOB_TASKS: ContextVar[set[asyncio.Task[Any]] | None] = ContextVar('pipeline_job_tasks', default=None)


def _job_task_factory(
    loop: asyncio.AbstractEventLoop,
    coro: Coroutine[Any, Any, Any],
    **kwargs: Any,  # ruff: ignore[any-type] - forward asyncio task-factory arguments across Python versions
) -> asyncio.Task[Any]:
    task = asyncio.Task(coro, loop=loop, **kwargs)
    # Respect an explicitly supplied task context as well as the default inherited one.
    context: Context | None = kwargs.get('context')
    tasks = context.get(_JOB_TASKS) if context is not None else _JOB_TASKS.get()
    if tasks is not None:
        tasks.add(task)
        task.add_done_callback(tasks.discard)
    return task


@asynccontextmanager
async def _job_tasks() -> AsyncIterator[None]:
    tasks: set[asyncio.Task[Any]] = set()
    token = _JOB_TASKS.set(tasks)
    try:
        yield
    finally:
        # Haystack and section generation spawn tasks which can outlive their parent.
        # Cancel only this run's descendants, then release its concurrency slot.
        try:
            while tasks:
                # Use a snapshot: done callbacks remove tasks from the shared set,
                # and a task's cleanup may spawn descendants that need another pass.
                pending = list(tasks)
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                tasks.difference_update(pending)
        finally:
            _JOB_TASKS.reset(token)


JobFactory = Callable[[], Coroutine[Any, Any, None]]


def format_queue_progress(jobs_ahead: int) -> str:
    if jobs_ahead <= 0:
        return 'Your dmp is next in the queue.'
    if jobs_ahead == 1:
        return '1 dmp ahead of you in the queue.'
    return f'{jobs_ahead} dmps ahead of you in the queue.'


class PipelineQueueManager:
    """FIFO pipeline job queue running coroutines on a dedicated event loop.

    Jobs are coroutines scheduled onto a single background event loop and gated by a
    semaphore so at most ``max_concurrent_jobs`` run at once.
    """

    def __init__(self, max_concurrent_jobs: int) -> None:
        self._max_concurrent_jobs = max_concurrent_jobs
        self._order: list[UUID] = []
        # Thread-safe handles bridge API requests to jobs on the background event loop.
        self._futures: dict[UUID, Future[None]] = {}
        self._order_lock = threading.Lock()
        self._semaphore = asyncio.Semaphore(max_concurrent_jobs)
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop,
            name='pipeline-queue',
            daemon=True,
        )
        self._thread.start()
        logger.info(
            'Initialized pipeline queue manager',
            extra={'max_concurrent_jobs': max_concurrent_jobs, 'thread_name': self._thread.name},
        )

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.set_task_factory(_job_task_factory)
        self._loop.run_forever()

    def enqueue(self, run_id: UUID, job: JobFactory, *, trace_id: UUID | None = None) -> None:
        with self._order_lock:
            self._order.append(run_id)
            queue_size = len(self._order)
        logger.info('Enqueued pipeline job', extra={'run_id': run_id, 'queue_size': queue_size})

        with self._order_lock:
            future = asyncio.run_coroutine_threadsafe(self._run_job(run_id, job, trace_id), self._loop)
            self._futures[run_id] = future
        future.add_done_callback(lambda done_future: self._job_done(run_id, done_future, trace_id))

    def cancel(self, run_id: UUID) -> None:
        with self._order_lock:
            future = self._futures.get(run_id)
        if future is not None:
            # Cancellation schedules CancelledError in the coroutine; cleanup still
            # needs to run. Call outside the lock because done callbacks also take it.
            future.cancel()

    def _job_done(self, run_id: UUID, future: Future[None], trace_id: UUID | None) -> None:
        with self._order_lock:
            self._futures.pop(run_id, None)
        self.remove(run_id)
        # This callback also handles cancellation before _run_job enters its try/finally.
        self._log_job_failure(future, trace_id)

    def progress_message(self, run_id: UUID) -> str | None:
        jobs_waiting_ahead = self._jobs_waiting_ahead(run_id)
        if jobs_waiting_ahead is None:
            return None
        return format_queue_progress(jobs_waiting_ahead)

    def remove(self, run_id: UUID) -> None:
        with self._order_lock:
            if run_id in self._order:
                self._order.remove(run_id)
        logger.debug('Removed pipeline job from queue order tracking', extra={'run_id': run_id})

    def _jobs_waiting_ahead(self, run_id: UUID) -> int | None:
        with self._order_lock:
            try:
                queue_index = self._order.index(run_id)
            except ValueError:
                return None
        return queue_index - self._max_concurrent_jobs

    async def _run_job(self, run_id: UUID, job: JobFactory, trace_id: UUID | None) -> None:
        with trace_context(trace_id):
            try:
                # Context managers exit in reverse order: stop descendants before
                # releasing the semaphore slot to the next waiting run.
                async with self._semaphore, _job_tasks():
                    logger.info('Starting queued pipeline job', extra={'run_id': run_id})
                    await job()
            finally:
                self.remove(run_id)
                logger.info('Finished queued pipeline job', extra={'run_id': run_id})

    @staticmethod
    def _log_job_failure(future: Future[None], trace_id: UUID | None) -> None:
        # Jobs are expected to handle their own errors; this guards against an
        # unhandled exception being silently swallowed by the background loop.
        if future.cancelled():
            return
        with trace_context(trace_id):
            error = future.exception()
            if error is not None:
                logger.error('Pipeline job crashed without handling its error', exc_info=error)
