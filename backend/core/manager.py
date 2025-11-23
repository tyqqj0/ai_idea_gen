from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Type

from backend.core.llm_client import LLMClient
from backend.services.feishu import FeishuClient
from backend.services.processors.base import BaseDocProcessor, ProcessorResult

logger = logging.getLogger(__name__)


@dataclass
class ProcessContext:
    doc_token: str
    user_id: str
    mode: str
    trigger_source: str | None = None


@dataclass
class WorkflowConfig:
    processor_cls: Type[BaseDocProcessor]
    chain: str
    notify_user: bool = True


@dataclass
class ProcessResult:
    child_doc_token: str
    child_doc_url: str
    processor_result: ProcessorResult


class WorkflowRegistry:
    """
    维护 mode -> WorkflowConfig 的映射，便于扩展。
    """

    def __init__(self, mapping: Dict[str, WorkflowConfig]) -> None:
        self._mapping = mapping

    def get(self, mode: str) -> WorkflowConfig:
        try:
            return self._mapping[mode]
        except KeyError as exc:  # noqa: B904
            raise ValueError(f"Unsupported processing mode: {mode}") from exc


class ProcessManager:
    """
    负责根据 mode 选择合适的 Processor，并串联 Feishu / LLM 的调用。
    """

    def __init__(
        self,
        *,
        feishu_client: FeishuClient,
        llm_client: LLMClient,
        workflow_registry: WorkflowRegistry,
    ) -> None:
        self._feishu = feishu_client
        self._llm_client = llm_client
        self._registry = workflow_registry

    async def process_doc(self, ctx: ProcessContext) -> ProcessResult:
        workflow = self._registry.get(ctx.mode)
        file_meta = await self._feishu.get_doc_meta(ctx.doc_token)
        file_info = file_meta.get("file") or file_meta
        doc_title = file_info.get("name") or file_info.get("title") or "未命名文档"
        parent_token = (
            file_info.get("parent_token")
            or file_info.get("folder_token")
            or file_info.get("parent_id")
        )

        doc_content = await self._feishu.get_doc_content(ctx.doc_token)
        processor = workflow.processor_cls(self._llm_client)
        processor_result = await processor.run(
            doc_content=doc_content,
            doc_title=doc_title,
            chain=workflow.chain,
            context={"trigger_source": ctx.trigger_source},
        )

        folder_token = parent_token or ctx.doc_token
        child_doc_token = await self._feishu.create_child_doc(
            folder_token=folder_token,
            title=processor_result.title or f"{doc_title} - AI 生成",
        )

        await self._feishu.write_doc_content(
            child_doc_token, processor_result.content_md
        )

        child_doc_url = self._build_doc_url(child_doc_token)
        await self._feishu.append_reference_block(
            ctx.doc_token, processor_result.title, child_doc_url
        )

        if workflow.notify_user:
            card = self._build_notify_card(
                ctx=ctx,
                child_doc_url=child_doc_url,
                summary=processor_result.summary,
            )
            try:
                await self._feishu.send_card(user_id=ctx.user_id, card_content=card)
            except Exception as exc:  # noqa: BLE001
                # 通知失败不应影响主流程
                logger.warning("Failed to send Feishu card: %s", exc)

        return ProcessResult(
            child_doc_token=child_doc_token,
            child_doc_url=child_doc_url,
            processor_result=processor_result,
        )

    def _build_doc_url(self, doc_token: str) -> str:
        return f"https://feishu.cn/docx/{doc_token}"

    def _build_notify_card(
        self,
        *,
        ctx: ProcessContext,
        child_doc_url: str,
        summary: str | None,
    ) -> Dict[str, Any]:
        summary_text = summary or "处理完成，可前往子文档查看详情。"
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "AI 文档处理完成",
                }
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**处理模式**：{ctx.mode}\n"
                            f"**结果**：[点击查看]({child_doc_url})\n\n"
                            f"{summary_text}"
                        ),
                    },
                }
            ],
        }
