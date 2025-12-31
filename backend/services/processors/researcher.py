from textwrap import dedent
from typing import Any, Awaitable, Callable, Dict, Optional

from backend.services.processors.base import BaseDocProcessor, ProcessorResult


ReportFn = Callable[[str, int, str], Awaitable[None]]


class ResearchProcessor(BaseDocProcessor):
    """
    “深度调研”模式 Processor。
    两阶段：
    1) refine：基于原文生成结构化调研指令（快模型）
    2) deep research：调用长时模型生成深度报告
    """

    async def run(
        self,
        *,
        doc_content: str,
        doc_title: str,
        chain: str,
        context: Dict[str, Any] | None = None,
    ) -> ProcessorResult:
        ctx = context or {}
        report: Optional[ReportFn] = ctx.get("report_progress")  # type: ignore[assignment]

        async def _report(stage: str, percent: int, message: str) -> None:
            if report:
                await report(stage, percent, message)

        # Step 1: Refine prompt
        await _report("llm_refine", 45, "优化调研指令")
        refine_system = dedent(
            """
            你是提示词优化器，负责把用户的需求转成可执行的“深度调研指令”。
            要求：
            - 输出简洁要点列表，覆盖：调研主题、核心问题、需验证的假设、关键信息源。
            - 保持中立，避免臆测，必要时明确“不足/待确认”。
            """
        ).strip()
        refine_user = dedent(
            f"""
            原文标题：{doc_title}
            原文内容：
            {doc_content}

            请生成一份“深度调研指令”，便于后续模型据此完成调研。
            """
        ).strip()
        refined_prompt = await self.llm_client.chat_completion(
            chain=f"{chain}_refine",
            messages=[
                {"role": "system", "content": refine_system},
                {"role": "user", "content": refine_user},
            ],
            temperature=0.3,
        )

        # Step 2: Deep research (long-running)
        await _report("llm_research", 70, "深度调研中，可能耗时较长")
        research_system = dedent(
            """
            你是深度研究助手，请基于给定的“调研指令”生成完整的调研报告（Markdown）。
            输出结构建议：
            - 背景与范围
            - 核心发现（分点描述，可含引用或出处说明）
            - 论证与证据（说明依据，标注可能的不确定性）
            - 风险与待验证问题
            - 建议行动（具体、可执行）
            如信息不足，请明确哪些部分缺乏支撑，不要编造。
            """
        ).strip()
        research_user = dedent(
            f"""
            调研指令：
            {refined_prompt.strip()}

            请直接输出 Markdown 调研报告。
            """
        ).strip()
        deep_result = await self.llm_client.chat_completion(
            chain=f"{chain}_deep",
            messages=[
                {"role": "system", "content": research_system},
                {"role": "user", "content": research_user},
            ],
            temperature=0.2,
        )

        await _report("llm_done", 90, "调研结果已生成")

        return ProcessorResult(
            title=f"{doc_title} - 深度调研",
            content_md=deep_result.strip(),
            summary="深度调研输出",
            metadata={
                "mode": "research",
                "refined_prompt": refined_prompt.strip(),
                "trigger_source": ctx.get("trigger_source"),
                # 仅保留可序列化的字段，避免包含 report_progress 函数
            },
        )
