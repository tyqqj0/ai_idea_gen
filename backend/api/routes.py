from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.core.llm_client import LLMClient
from backend.core.manager import (
    ProcessContext,
    ProcessManager,
    ProcessResult,
    WorkflowConfig,
    WorkflowRegistry,
)
from backend.core.task_store import TaskStatus, TaskStore
from backend.services.feishu import FeishuClient
from backend.services.processors.expander import IdeaExpanderProcessor
from backend.services.processors.researcher import ResearchProcessor

logger = logging.getLogger(__name__)

router = APIRouter()


class AddonProcessRequest(BaseModel):
    doc_token: str = Field(..., description="飞书文档 token")
    user_id: str = Field(..., description="触发用户 open_id")
    mode: str = Field(default="idea_expand", description="处理模式")
    trigger_source: Optional[str] = Field(default=None, description="触发来源")


class AddonProcessAccepted(BaseModel):
    task_id: str
    status: Literal["accepted"] = "accepted"
    message: str = "Processing started"


class TaskStatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: float
    updated_at: Optional[float] = None


task_store = TaskStore()
workflow_registry = WorkflowRegistry(
    {
        "idea_expand": WorkflowConfig(
            processor_cls=IdeaExpanderProcessor,
            chain="idea_expand",
            notify_user=True,
        ),
        "research": WorkflowConfig(
            processor_cls=ResearchProcessor,
            chain="research",
            notify_user=True,
        ),
    }
)
process_manager = ProcessManager(
    feishu_client=FeishuClient(),
    llm_client=LLMClient(),
    workflow_registry=workflow_registry,
)


@router.get("/ping", summary="简单连通性测试")
async def ping() -> Dict[str, str]:
    return {"message": "pong"}


@router.post(
    "/addon/process",
    summary="触发文档处理",
    response_model=AddonProcessAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_process(payload: AddonProcessRequest) -> AddonProcessAccepted:
    try:
        workflow_registry.get(payload.mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ctx = ProcessContext(
        doc_token=payload.doc_token,
        user_id=payload.user_id,
        mode=payload.mode,
        trigger_source=payload.trigger_source or "docs_addon",
    )

    task_id = await task_store.create_task(context=asdict(ctx))
    asyncio.create_task(_run_processing_task(task_id, ctx))

    return AddonProcessAccepted(task_id=task_id)


@router.get(
    "/addon/tasks/{task_id}",
    summary="查询任务状态",
    response_model=TaskStatusResponse,
)
async def get_task_status(task_id: str) -> TaskStatusResponse:
    task = await task_store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskStatusResponse(
        task_id=task_id,
        status=task["status"],
        result=task.get("result"),
        error=task.get("error"),
        created_at=task.get("created_at", 0.0),
        updated_at=task.get("updated_at"),
    )


async def _run_processing_task(task_id: str, ctx: ProcessContext) -> None:
    try:
        result = await process_manager.process_doc(ctx)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Processing failed task_id=%s doc=%s", task_id, ctx.doc_token)
        await task_store.fail(task_id, str(exc))
        return

    await task_store.succeed(task_id, _serialize_process_result(result))


def _serialize_process_result(result: ProcessResult) -> Dict[str, Any]:
    processor_result = result.processor_result
    return {
        "child_doc_token": result.child_doc_token,
        "child_doc_url": result.child_doc_url,
        "title": processor_result.title,
        "summary": processor_result.summary,
        "metadata": processor_result.metadata,
    }
