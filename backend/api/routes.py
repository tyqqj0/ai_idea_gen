from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.core.llm_client import LLMClient
from backend.core.manager import (
    ProcessContext,
    ProcessManager,
    ProcessResult,
    WorkflowRegistry,
)
from backend.core.workflow_loader import build_default_workflow_registry, load_workflow_registry
from backend.core.task_store import TaskStatus, TaskStore
from backend.services.feishu import FeishuClient
from backend.services.triggers.service import TriggerService

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
    progress: Optional[Dict[str, Any]] = None
    created_at: float
    updated_at: Optional[float] = None


task_store = TaskStore()

try:
    workflow_registry = load_workflow_registry()
except Exception as exc:  # noqa: BLE001
    # 配置文件缺失/配置错误时兜底（便于本地快速启动），同时打印告警
    logger.warning("Failed to load workflow_config.yml, fallback to default registry: %s", exc)
    workflow_registry = build_default_workflow_registry()

process_manager = ProcessManager(
    feishu_client=FeishuClient(),
    llm_client=LLMClient(),
    workflow_registry=workflow_registry,
)
trigger_service = TriggerService(task_store=task_store, process_manager=process_manager)


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

    task_id = await trigger_service.trigger(ctx=ctx)

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
        progress=task.get("progress"),
        created_at=task.get("created_at", 0.0),
        updated_at=task.get("updated_at"),
    )


class FeishuEventCallback(BaseModel):
    """
    飞书事件回调（最小兼容骨架）
    - URL 校验：challenge
    - 事件：schema 2.0 结构（header/event）
    """

    challenge: Optional[str] = None
    schema: Optional[str] = None
    header: Optional[Dict[str, Any]] = None
    event: Optional[Dict[str, Any]] = None


@router.post("/feishu/event", summary="飞书事件订阅回调（最小骨架）")
async def feishu_event(payload: FeishuEventCallback) -> Dict[str, Any]:
    # 1) URL 校验
    if payload.challenge:
        return {"challenge": payload.challenge}

    header = payload.header or {}
    event = payload.event or {}

    event_id = header.get("event_id") or header.get("eventId")

    # 2) 尝试从事件中解析 doc_token/user_id（不同事件字段略有差异，这里做宽松兼容）
    doc_token = (
        event.get("doc_token")
        or event.get("file_token")
        or event.get("docx_token")
        or (event.get("object") or {}).get("token")
        or (event.get("file") or {}).get("token")
    )
    user_id = (
        event.get("operator_id")
        or event.get("open_id")
        or event.get("user_id")
        or (event.get("operator") or {}).get("open_id")
    )

    # 3) mode 选择：优先 event 显式传入，否则默认 idea_expand
    mode = event.get("mode") or "idea_expand"

    if not doc_token or not user_id:
        # 按飞书习惯返回 code=0 表示已接收，避免重试风暴；详细错误留日志
        logger.warning("Feishu event missing doc_token/user_id, header=%s event=%s", header, event)
        return {"code": 0, "msg": "ok"}

    # 4) 幂等：用 event_id 去重（如果没有 event_id，就退化为非幂等）
    ctx = ProcessContext(
        doc_token=str(doc_token),
        user_id=str(user_id),
        mode=str(mode),
        trigger_source="feishu_event",
    )
    await trigger_service.trigger(ctx=ctx, idempotency_key=str(event_id) if event_id else None)
    return {"code": 0, "msg": "ok"}


class FeishuCardCallback(BaseModel):
    """
    飞书卡片回调（预留骨架）
    """

    action: Optional[Dict[str, Any]] = None
    open_id: Optional[str] = None


@router.post("/feishu/card_callback", summary="飞书交互卡片回调（预留骨架）")
async def feishu_card_callback(payload: FeishuCardCallback) -> Dict[str, Any]:
    action = payload.action or {}
    value = action.get("value") or {}
    doc_token = value.get("doc_token")
    mode = value.get("mode") or "idea_expand"
    user_id = payload.open_id or value.get("user_id")

    if doc_token and user_id:
        ctx = ProcessContext(
            doc_token=str(doc_token),
            user_id=str(user_id),
            mode=str(mode),
            trigger_source="card_callback",
        )
        # 卡片回调一般用 request_id 做幂等，这里先留空
        await trigger_service.trigger(ctx=ctx)

    return {"code": 0, "msg": "ok"}
