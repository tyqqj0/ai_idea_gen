from backend.services.processors.base import BaseDocProcessor


class IdeaExpanderProcessor(BaseDocProcessor):
    """
    “扩展思路”模式 Processor。
    目前只保留骨架，后续会补充具体 Prompt 模板与上下文组装。
    """

    async def run(self, *, doc_content: str, doc_title: str) -> str:
        # TODO: 组装适合发散思维的 Prompt，调用 LLMClient 并返回 Markdown
        raise NotImplementedError



