from abc import ABC, abstractmethod
from typing import Protocol


class LLMClientLike(Protocol):
    async def chat_completion(self, messages: list[dict]) -> str: ...


class BaseDocProcessor(ABC):
    """
    所有具体 Processor 的抽象基类。
    负责约定处理接口与依赖（LLMClient、FeishuClient 等）。
    """

    def __init__(self, llm_client: LLMClientLike) -> None:
        self.llm_client = llm_client

    @abstractmethod
    async def run(self, *, doc_content: str, doc_title: str) -> str:
        """
        处理文档内容，返回要写入子文档的 Markdown 文本。
        """
        ...



