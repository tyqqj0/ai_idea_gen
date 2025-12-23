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
        # 幂等键 -> task_id，用于事件回调/重试去重
        self._idempotency: Dict[str, str] = {}

    async def create_task(
        self, *, context: Dict[str, Any], idempotency_key: str | None = None
    ) -> str:
        async with self._lock:
            if idempotency_key:
                existing = self._idempotency.get(idempotency_key)
                if existing and existing in self._tasks:
                    return existing

            task_id = uuid.uuid4().hex
            self._tasks[task_id] = {
                "status": "running",
                "created_at": time.time(),
                "context": context,
            }
            if idempotency_key:
                self._idempotency[idempotency_key] = task_id
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

