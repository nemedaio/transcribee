from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Protocol

from lnkdn_transcripts.logging import get_logger

logger = get_logger(__name__)


class JobRunner(Protocol):
    def enqueue(self, job_id: str) -> None:
        """Schedule a job for background processing."""

    def close(self) -> None:
        """Release any runner resources."""


class InlineJobRunner:
    def __init__(self, processor: Callable[[str], None]) -> None:
        self.processor = processor

    def enqueue(self, job_id: str) -> None:
        logger.info("runner.inline_enqueue job_id=%s", job_id)
        self.processor(job_id)

    def close(self) -> None:
        return None


class ManualJobRunner:
    def __init__(self, processor: Callable[[str], None]) -> None:
        self.processor = processor
        self.pending_job_ids: list[str] = []

    def enqueue(self, job_id: str) -> None:
        logger.info("runner.manual_enqueue job_id=%s", job_id)
        self.pending_job_ids.append(job_id)

    def run_all(self) -> None:
        while self.pending_job_ids:
            job_id = self.pending_job_ids.pop(0)
            logger.info("runner.manual_run job_id=%s", job_id)
            self.processor(job_id)

    def close(self) -> None:
        self.pending_job_ids.clear()


class ThreadedJobRunner:
    def __init__(self, processor: Callable[[str], None], max_workers: int = 2) -> None:
        self.processor = processor
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="job-runner")
        self.futures: set[Future] = set()

    def enqueue(self, job_id: str) -> None:
        logger.info("runner.threaded_enqueue job_id=%s", job_id)
        future = self.executor.submit(self.processor, job_id)
        self.futures.add(future)
        future.add_done_callback(self._complete)

    def close(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=False)

    def _complete(self, future: Future) -> None:
        self.futures.discard(future)
        exception = future.exception()
        if exception is not None:
            logger.exception("runner.threaded_failed error=%s", exception)
