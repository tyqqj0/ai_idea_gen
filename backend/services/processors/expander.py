from textwrap import dedent
from typing import Any, Dict

from backend.services.processors.base import BaseDocProcessor, ProcessorResult


class IdeaExpanderProcessor(BaseDocProcessor):
    """
    “扩展思路”模式 Processor。
    强调脑暴式的建议列表。
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
            你是一个产品创意顾问，擅长基于已有文档提出多样化的延伸点子。
            - 输出使用 Markdown，按“摘要 / 延伸方向 / 下一步行动”结构组织。
            - 给出有区分度的要点，每条用序号或小标题。
            - 保持客观、具体，可执行。
            """
        ).strip()
        user_prompt = dedent(
            f"""
            当前文档标题：{doc_title}

            文档正文：
            {doc_content}

            请基于内容生成 3-5 个延伸方向并补充对应的实施建议。
            """
        ).strip()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        completion = await self.llm_client.chat_completion(
            chain=chain, messages=messages, temperature=0.7
        )

        return ProcessorResult(
            title=f"{doc_title} - 思路扩展",
            content_md=completion.strip(),
            summary="扩展思路建议",
            metadata={
                "mode": "idea_expand",
                "trigger_source": (context or {}).get("trigger_source"),
                # 仅保留可序列化的字段，避免包含 report_progress 函数
            },
        )



