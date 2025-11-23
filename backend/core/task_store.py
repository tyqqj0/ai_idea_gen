from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Dict, Literal, Optional

TaskStatus = Literal["running", "succeeded", "failed"]


class TaskStore:
    """
    简易内存版任务存储，便于查询处理状态。
    后续可替换为 Redis / DB。
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._tasks: Dict[str, Dict[str, Any]] = {}

    async def create_task(self, *, context: Dict[str, Any]) -> str:
        task_id = uuid.uuid4().hex
        async with self._lock:
            self._tasks[task_id] = {
                "status": "running",
                "created_at": time.time(),
                "context": context,
            }
        return task_id

    async def succeed(self, task_id: str, result: Dict[str, Any]) -> None:
        await self._update(
            task_id,
            {
                "status": "succeeded",
                "result": result,
                "updated_at": time.time(),
            },
        )

    async def fail(self, task_id: str, error: str) -> None:
        await self._update(
            task_id,
            {
                "status": "failed",
                "error": error,
                "updated_at": time.time(),
            },
        )

    async def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        async with self._lock:
            if task_id not in self._tasks:
                return None
            # 返回副本避免外部修改
            return dict(self._tasks[task_id])

    async def _update(self, task_id: str, payload: Dict[str, Any]) -> None:
        async with self._lock:
            if task_id not in self._tasks:
                return
            self._tasks[task_id].update(payload)

