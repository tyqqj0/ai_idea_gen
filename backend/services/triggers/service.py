from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from typing import Any, Dict, Optional

from backend.core.manager import ProcessContext, ProcessManager, ProcessResult
from backend.core.task_store import TaskStore

logger = logging.getLogger(__name__)


class TriggerService:
    """
    触发层统一服务：负责幂等、创建任务、启动后台处理，并将结果写回 TaskStore。
    """

    def __init__(self, *, task_store: TaskStore, process_manager: ProcessManager) -> None:
        self._tasks = task_store
        self._pm = process_manager

    async def trigger(
        self,
        *,
        ctx: ProcessContext,
        idempotency_key: Optional[str] = None,
    ) -> str:
        """
        创建任务并异步执行，返回 task_id。

        - idempotency_key：用于事件回调去重；同一 key 将返回同一个 task_id
        """
        task_id = await self._tasks.create_task(
            context=asdict(ctx), idempotency_key=idempotency_key
        )
        await self._tasks.update_progress(
            task_id, stage="queued", percent=0, message="任务已进入队列"
        )
        asyncio.create_task(self._run(task_id, ctx))
        return task_id

    async def _run(self, task_id: str, ctx: ProcessContext) -> None:
        try:
            await self._tasks.update_progress(
                task_id, stage="started", percent=1, message="开始处理"
            )

            async def progress(stage: str, percent: int, message: str) -> None:
                await self._tasks.update_progress(
                    task_id, stage=stage, percent=percent, message=message
                )

            result = await self._pm.process_doc(ctx, progress=progress)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Processing failed task_id=%s doc=%s", task_id, ctx.doc_token)
            await self._tasks.fail(task_id, str(exc))
            return

        await self._tasks.succeed(task_id, self._serialize_process_result(result))

    def _serialize_process_result(self, result: ProcessResult) -> Dict[str, Any]:
        processor_result = result.processor_result
        output_result = result.output_result
        return {
            "child_doc_token": result.child_doc_token,
            "child_doc_url": result.child_doc_url,
            "title": processor_result.title,
            "summary": processor_result.summary,
            "metadata": processor_result.metadata,
            "output": output_result.metadata,
        }


