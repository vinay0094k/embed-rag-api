"""Background task processing for async uploads."""

import threading
import queue
import logging
from typing import Callable, Any, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class Task:
    """Background task to process."""
    task_id: str
    func: Callable
    args: tuple
    kwargs: dict
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


class BackgroundTaskQueue:
    """Simple in-process task queue for background processing."""

    def __init__(self, num_workers: int = 2):
        self.queue = queue.Queue()
        self.workers = []
        self.num_workers = num_workers
        self.running = False

    def start(self):
        """Start background worker threads."""
        if self.running:
            return

        self.running = True
        for i in range(self.num_workers):
            worker = threading.Thread(
                target=self._worker,
                name=f"BackgroundWorker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)

        logger.info(f"Started {self.num_workers} background workers")

    def stop(self):
        """Stop background worker threads."""
        self.running = False
        # Wait for queue to empty
        self.queue.join()

    def enqueue(self, task: Task):
        """Add task to queue."""
        self.queue.put(task)
        logger.info(f"Enqueued task: {task.task_id}")

    def _worker(self):
        """Worker thread that processes tasks."""
        while self.running:
            try:
                # Get task with timeout to allow shutdown
                task = self.queue.get(timeout=1)

                try:
                    logger.info(f"Processing task: {task.task_id}")
                    result = task.func(*task.args, **task.kwargs)
                    logger.info(f"Completed task: {task.task_id}")
                except Exception as e:
                    logger.error(
                        f"Task failed: {task.task_id}",
                        exc_info=True
                    )
                finally:
                    self.queue.task_done()

            except queue.Empty:
                # Timeout - check if still running
                continue
            except Exception as e:
                logger.error("Worker error", exc_info=True)


# Global task queue
_task_queue: Optional[BackgroundTaskQueue] = None


def get_task_queue() -> BackgroundTaskQueue:
    """Get or create the global task queue."""
    global _task_queue
    if _task_queue is None:
        _task_queue = BackgroundTaskQueue(num_workers=2)
        _task_queue.start()
    return _task_queue


def enqueue_task(
    task_id: str,
    func: Callable,
    *args,
    **kwargs
) -> Task:
    """Enqueue a background task."""
    task = Task(
        task_id=task_id,
        func=func,
        args=args,
        kwargs=kwargs
    )
    queue = get_task_queue()
    queue.enqueue(task)
    return task


def shutdown_tasks():
    """Shutdown background task queue."""
    global _task_queue
    if _task_queue:
        _task_queue.stop()
