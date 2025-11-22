from backend.services.processors.base import BaseDocProcessor


class ResearchProcessor(BaseDocProcessor):
    """
    “深度调研”模式 Processor。
    后续会补充更偏结构化、事实核查的 Prompt 模板。
    """

    async def run(self, *, doc_content: str, doc_title: str) -> str:
        # TODO: 组装适合深度调研的 Prompt，调用 LLMClient 并返回 Markdown
        raise NotImplementedError



