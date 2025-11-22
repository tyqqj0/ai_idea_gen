from dataclasses import dataclass

from backend.services.processors.base import BaseDocProcessor


@dataclass
class ProcessContext:
    doc_token: str
    user_id: str
    mode: str
    trigger_source: str | None = None


class ProcessManager:
    """
    负责根据 mode 选择合适的 Processor，并编排整个 process_doc 流程。
    目前只定义接口与骨架，具体逻辑后续按设计文档逐步填充。
    """

    def __init__(self) -> None:
        # 未来可以在这里注入 FeishuClient、LLMClient 等依赖
        ...

    async def process_doc(self, ctx: ProcessContext) -> str:
        """
        执行文档处理主流程，返回新生成子文档的 token 或 URL。
        """
        processor = self._select_processor(ctx.mode)
        # TODO: 衔接 Feishu API 与 LLMClient 的调用
        raise NotImplementedError("ProcessManager.process_doc 尚未实现")

    def _select_processor(self, mode: str) -> BaseDocProcessor:
        """
        根据 mode 选择具体 Processor（策略模式）。
        """
        # TODO: 根据 mode 返回 IdeaExpanderProcessor / ResearchProcessor 等
        raise NotImplementedError("ProcessManager._select_processor 尚未实现")



