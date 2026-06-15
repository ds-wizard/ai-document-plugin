import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

MAX_CONCURRENT_PIPELINE_JOBS = 2


def format_queue_progress(jobs_ahead: int) -> str:
    if jobs_ahead <= 0:
        return 'Your dmp is next in the queue.'
    if jobs_ahead == 1:
        return '1 dmp ahead of you in the queue.'
    return f'{jobs_ahead} dmps ahead of you in the queue.'


class PipelineQueueManager:
    """FIFO pipeline job queue with a bounded worker pool."""

    def __init__(self, max_concurrent_jobs: int = MAX_CONCURRENT_PIPELINE_JOBS) -> None:
        self._max_concurrent_jobs = max_concurrent_jobs
        self._order: list[str] = []
        self._order_lock = threading.Lock()
        self._executor = ThreadPoolExecutor(
            max_workers=max_concurrent_jobs,
            thread_name_prefix='pipeline-job',
        )

    def enqueue(self, run_id: str, job: Callable[[], None]) -> None:
        with self._order_lock:
            self._order.append(run_id)

        self._executor.submit(self._run_job, run_id, job)

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

    def _run_job(self, run_id: str, job: Callable[[], None]) -> None:
        try:
            job()
        finally:
            self.remove(run_id)


pipeline_queue_manager = PipelineQueueManager()
