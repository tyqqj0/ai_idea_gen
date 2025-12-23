from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Type

from backend.core.llm_client import LLMClient
from backend.services.feishu import FeishuClient
from backend.services.outputs.base import OutputResult, SourceDoc
from backend.services.processors.base import BaseDocProcessor, ProcessorResult
from backend.services.outputs.base import BaseOutputHandler

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
    output_factory: Callable[[FeishuClient, LLMClient], BaseOutputHandler]
    notify_user: bool = True


@dataclass
class ProcessResult:
    child_doc_token: Optional[str]
    child_doc_url: Optional[str]
    processor_result: ProcessorResult
    output_result: OutputResult


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

        output_handler = workflow.output_factory(self._feishu, self._llm_client)
        output_result = await output_handler.handle(
            ctx=ctx,
            source_doc=SourceDoc(
                doc_token=ctx.doc_token, title=doc_title, parent_token=parent_token
            ),
            processor_result=processor_result,
            notify_user=workflow.notify_user,
        )

        return ProcessResult(
            child_doc_token=output_result.child_doc_token,
            child_doc_url=output_result.child_doc_url,
            processor_result=processor_result,
            output_result=output_result,
        )
