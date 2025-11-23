from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol


class LLMClientLike(Protocol):
    async def chat_completion(
        self, *, chain: str, messages: list[dict], **kwargs: Any
    ) -> str: ...


@dataclass
class ProcessorResult:
    """
    Processor 的标准输出，便于后续写入文档与通知。
    """

    title: str
    content_md: str
    summary: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseDocProcessor(ABC):
    """
    所有具体 Processor 的抽象基类。
    负责约定处理接口与依赖（LLMClient、FeishuClient 等）。
    """

    def __init__(self, llm_client: LLMClientLike) -> None:
        self.llm_client = llm_client

    @abstractmethod
    async def run(
        self,
        *,
        doc_content: str,
        doc_title: str,
        chain: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ProcessorResult:
        """
        处理文档内容，返回标准化结果（Markdown + 摘要等）。
        """

