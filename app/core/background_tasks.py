import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

class TaskStatus:
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class BackgroundTaskManager:
    def __init__(self):
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None

    def start_worker(self):
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._process_queue())

    async def enqueue_task(self, task_name: str, func: Callable, *args, **kwargs) -> str:
        task_id = str(uuid.uuid4())
        task_info = {
            "task_id": task_id,
            "name": task_name,
            "status": TaskStatus.QUEUED,
            "progress_pct": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "result": None,
            "error": None,
        }
        self._tasks[task_id] = task_info
        await self._queue.put((task_id, func, args, kwargs))
        self.start_worker()
        return task_id

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self._tasks.get(task_id)

    async def _process_queue(self):
        while not self._queue.empty():
            task_id, func, args, kwargs = await self._queue.get()
            if task_id in self._tasks:
                self._tasks[task_id]["status"] = TaskStatus.RUNNING
                self._tasks[task_id]["progress_pct"] = 10
                try:
                    if asyncio.iscoroutinefunction(func):
                        res = await func(*args, **kwargs)
                    else:
                        res = await asyncio.to_thread(func, *args, **kwargs)
                    self._tasks[task_id]["status"] = TaskStatus.COMPLETED
                    self._tasks[task_id]["progress_pct"] = 100
                    self._tasks[task_id]["result"] = res
                    self._tasks[task_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
                except Exception as e:
                    self._tasks[task_id]["status"] = TaskStatus.FAILED
                    self._tasks[task_id]["error"] = str(e)
                    self._tasks[task_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
            self._queue.task_done()

task_manager = BackgroundTaskManager()
