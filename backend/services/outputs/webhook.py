from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from backend.core.manager import ProcessContext
from backend.services.outputs.base import BaseOutputHandler, OutputResult, SourceDoc
from backend.services.processors.base import ProcessorResult


class WebhookOutputHandler(BaseOutputHandler):
    """
    示例输出策略：将处理结果推送到外部 Webhook（用于对接其他系统）。

    - 不创建飞书子文档，因此 OutputResult.child_doc_* 为 None
    - 将关键字段作为 JSON 推送：mode/doc_token/title/content_md/summary/metadata
    """

    def __init__(
        self,
        *,
        webhook_url: str,
        timeout_s: float = 10.0,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self._url = webhook_url
        self._timeout = timeout_s
        self._headers = headers or {}

    async def handle(
        self,
        *,
        ctx: ProcessContext,
        source_doc: SourceDoc,
        processor_result: ProcessorResult,
        notify_user: bool = True,
    ) -> OutputResult:
        _ = notify_user  # webhook 输出一般不“通知用户”，这里保留参数以统一接口

        payload: Dict[str, Any] = {
            "mode": ctx.mode,
            "trigger_source": ctx.trigger_source,
            "user_id": ctx.user_id,
            "source_doc": {
                "doc_token": source_doc.doc_token,
                "title": source_doc.title,
                "parent_token": source_doc.parent_token,
            },
            "result": {
                "title": processor_result.title,
                "content_md": processor_result.content_md,
                "summary": processor_result.summary,
                "metadata": processor_result.metadata,
            },
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(self._url, json=payload, headers=self._headers)
            resp.raise_for_status()

        return OutputResult(
            child_doc_token=None,
            child_doc_url=None,
            metadata={
                "output": "webhook",
                "webhook_url": self._url,
                "http_status": resp.status_code,
            },
        )


