from textwrap import dedent
from typing import Any, Dict

from backend.services.processors.base import BaseDocProcessor, ProcessorResult


class ResearchProcessor(BaseDocProcessor):
    """
    “深度调研”模式 Processor。
    输出更偏结构化的事实、洞察与风险。
    """

    async def run(
        self,
        *,
        doc_content: str,
        doc_title: str,
        chain: str,
        context: Dict[str, Any] | None = None,
    ) -> ProcessorResult:
        system_prompt = dedent(
            """
            你是资深分析师，需要对输入内容进行结构化调研总结。
            - 输出 Markdown，包含【背景概述】【核心发现】【待验证问题】【建议行动】。
            - 如果信息不足，请明确写出假设与需要补充的数据。
            - 用事实和引用内容支撑结论，保持中立。
            """
        ).strip()
        user_prompt = dedent(
            f"""
            文档标题：{doc_title}

            文档内容：
            {doc_content}

            请完成基于上述内容的调研摘要。
            """
        ).strip()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        completion = await self.llm_client.chat_completion(
            chain=chain, messages=messages, temperature=0.4
        )

        return ProcessorResult(
            title=f"{doc_title} - 调研摘要",
            content_md=completion.strip(),
            summary="深度调研输出",
            metadata={"mode": "research", **(context or {})},
        )



