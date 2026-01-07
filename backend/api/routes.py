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
from backend.services.feishu import FeishuClient, FeishuAPIError
from backend.services.triggers.service import TriggerService

logger = logging.getLogger(__name__)

router = APIRouter()


class AddonProcessRequest(BaseModel):
    token: Optional[str] = Field(
        default=None,
        description="统一入口：可传 doc_token（doccn/doxc）或 wiki node_token（wikcn...）。不传则使用 doc_token 字段。",
    )
    doc_token: Optional[str] = Field(
        default=None,
        description="飞书文档 token（doccn/doxc，兼容旧版；若提供 token 则优先用 token）",
    )
    user_id: str = Field(..., description="触发用户 open_id")
    mode: str = Field(default="idea_expand", description="处理模式")
    content: Optional[str] = Field(default=None, description="用户选中的文本（划词内容）")
    trigger_source: Optional[str] = Field(default=None, description="触发来源")
    wiki_node_token: Optional[str] = Field(default=None, description="（可选）知识库父节点 node_token")
    wiki_space_id: Optional[str] = Field(default=None, description="（可选）知识库 space_id")


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


@router.get("/addon/modes", summary="获取所有可用的处理模式")
async def get_available_modes() -> Dict[str, Any]:
    """
    返回所有可用的 mode 列表，方便前端验证和显示。
    """
    modes = workflow_registry.list_modes()
    return {
        "modes": modes,
        "default": "idea_expand",
        "count": len(modes),
    }


@router.post(
    "/addon/process",
    summary="触发文档处理",
    response_model=AddonProcessAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_process(payload: AddonProcessRequest) -> AddonProcessAccepted:
    # 记录请求详情（用于 debug）
    logger.info(
        "[POST /addon/process] 收到请求: token=%s, doc_token=%s, user_id=%s, mode=%s, trigger_source=%s",
        payload.token[:10] + "..." if payload.token and len(payload.token) > 10 else payload.token,
        payload.doc_token[:10] + "..." if payload.doc_token and len(payload.doc_token) > 10 else payload.doc_token,
        payload.user_id,
        payload.mode,
        payload.trigger_source,
    )
    
    try:
        workflow_registry.get(payload.mode)
    except ValueError as exc:
        logger.error("[POST /addon/process] 无效的 mode: %s, 错误: %s", payload.mode, exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        doc_token, wiki_node_token, wiki_space_id = await _resolve_tokens(payload)
    except HTTPException as exc:
        logger.error(
            "[POST /addon/process] Token 解析失败: token=%s, doc_token=%s, 错误: %s",
            payload.token,
            payload.doc_token,
            exc.detail,
        )
        raise

    ctx = ProcessContext(
        doc_token=doc_token,
        user_id=payload.user_id,
        mode=payload.mode,
        trigger_source=payload.trigger_source or "docs_addon",
        selected_text=payload.content,  # 传递划词文本
        wiki_node_token=wiki_node_token,
        wiki_space_id=wiki_space_id,
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


async def _resolve_tokens(payload: AddonProcessRequest) -> tuple[str, Optional[str], Optional[str]]:
    """
    统一解析入口 Token：
    - 如果提供 wiki_node_token/space_id，则直接使用（doc_token 需传 doc 实体 ID）
    - 如果提供 token（可能是 node_token 或 doc_token），尝试：
        1) 若 wiki_node_token 未提供，则用 token 先尝试查 wiki node（成功则得到 doc_token/space_id）
        2) 若 wiki 查失败，则把 token 当作 doc_token
    """
    token = payload.token or payload.doc_token
    logger.debug(
        "[_resolve_tokens] 输入: token=%s, doc_token=%s, wiki_node_token=%s",
        token,
        payload.doc_token,
        payload.wiki_node_token,
    )
    if not token:
        error_msg = f"token 或 doc_token 必须提供（收到: token={payload.token}, doc_token={payload.doc_token}）"
        logger.error("[_resolve_tokens] %s", error_msg)
        raise HTTPException(status_code=400, detail=error_msg)

    # 若前端已显式提供 wiki_node_token/space_id，则直接信任并使用传入的 doc_token（若空则回退 token）
    if payload.wiki_node_token or payload.wiki_space_id:
        return (
            payload.doc_token or token,
            payload.wiki_node_token,
            payload.wiki_space_id,
        )

    # 尝试将 token 视为 node_token，查询 wiki 信息；失败则降级为 doc_token
    feishu = trigger_service._pm._feishu  # type: ignore[attr-defined]
    try:
        logger.debug("[_resolve_tokens] 尝试将 token 作为 Wiki 节点解析: %s", token)
        wiki_node = await feishu.get_wiki_node_by_token(node_token=token)
        doc_token = (
            wiki_node.get("obj_token")
            or wiki_node.get("objToken")
            or wiki_node.get("document_id")
            or wiki_node.get("doc_token")
        )
        space_id = wiki_node.get("space_id")
        if doc_token:
            logger.info(
                "[_resolve_tokens] Wiki 节点解析成功: node_token=%s -> doc_token=%s, space_id=%s",
                token,
                doc_token,
                space_id,
            )
            return str(doc_token), token, str(space_id) if space_id else None
    except FeishuAPIError as e:
        # 不是 wiki 节点或无权限，则降级为普通 doc_token
        logger.info(
            "[_resolve_tokens] 不是 Wiki 节点（或无权限），降级为普通 doc_token: %s, 错误: %s",
            token,
            str(e),
        )
        pass

    # 默认当作 doc_token（云盘或普通文档）
    logger.info("[_resolve_tokens] 使用普通 doc_token 模式: %s", token)
    return token, None, None


class FeishuEventCallback(BaseModel):
    """
    飞书事件回调（最小兼容骨架）
    - URL 校验：challenge
    - 事件：schema 2.0 结构（header/event）
    """

    challenge: Optional[str] = None
    schema_: Optional[str] = Field(default=None, alias="schema")
    header: Optional[Dict[str, Any]] = None
    event: Optional[Dict[str, Any]] = None

    model_config = {"populate_by_name": True}


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
