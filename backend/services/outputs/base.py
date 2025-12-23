from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from backend.services.processors.base import ProcessorResult

try:
    from typing import TYPE_CHECKING
except ImportError:  # pragma: no cover
    TYPE_CHECKING = False  # type: ignore[assignment]

if TYPE_CHECKING:
    from backend.core.manager import ProcessContext


@dataclass
class SourceDoc:
    """
    表示“被处理的原始文档”的关键信息。
    输出层可以用这些信息决定：产物创建在哪、如何回链等。
    """

    doc_token: str
    title: str
    parent_token: Optional[str] = None


@dataclass
class OutputResult:
    """
    输出层的标准输出。

    说明：
    - 当前为了兼容已有前端/测试流程，保留 child_doc_token/url 字段。
    - 未来如果输出目标不是“子文档”，也可以返回 None，并将更多信息放到 metadata。
    """

    child_doc_token: Optional[str] = None
    child_doc_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseOutputHandler(ABC):
    """
    输出策略抽象。

    - 输入：ProcessContext + 原文档信息 + ProcessorResult
    - 输出：OutputResult（可包含子文档链接、消息 id、外部系统回执等）
    """

    @abstractmethod
    async def handle(
        self,
        *,
        ctx: "ProcessContext",
        source_doc: SourceDoc,
        processor_result: ProcessorResult,
        notify_user: bool = True,
    ) -> OutputResult:
        raise NotImplementedError


