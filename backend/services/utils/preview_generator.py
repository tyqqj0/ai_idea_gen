from __future__ import annotations

import logging
from textwrap import dedent
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from backend.core.llm_client import LLMClient

logger = logging.getLogger(__name__)


class PreviewGenerator:
    """
    智能预览文本生成器：为消息通知生成语义化的文档预览。
    
    设计目标：
    - 通用性：可被任何 OutputHandler 复用
    - 快速：使用summary_generation chain
    - 可靠：生成失败时自动降级到简单截取
    - 可配置：支持 auto / simple 模式
    """

    def __init__(
        self,
        *,
        llm_client: LLMClient,
        chain: str = "summary_generation",
        max_preview_length: int = 150,
    ) -> None:
        """
        Args:
            llm_client: LLM 客户端实例
            chain: LLM 配置链名称（用于预览生成）
            max_preview_length: 预览文本的最大字符数
        """
        self._llm = llm_client
        self._chain = chain
        self._max_len = max_preview_length

    async def generate_preview(
        self,
        *,
        content_md: str,
        mode: str,
        preview_mode: Literal["auto", "simple"] = "auto",
    ) -> str:
        """
        生成预览文本。

        Args:
            content_md: Markdown 格式的文档内容
            mode: 处理模式（如 "idea_expand", "research"）
            preview_mode: 预览模式
                - "auto": 智能模式（优先 LLM 总结，失败则降级到简单截取）
                - "simple": 简单模式（直接截取前 N 字符）

        Returns:
            预览文本（最大 max_preview_length 字符）
        """
        if preview_mode == "simple":
            return self._simple_preview(content_md)

        # auto 模式：先尝试智能生成，失败则降级
        try:
            return await self._smart_preview(content_md, mode)
        except Exception as exc:
            logger.warning("智能预览生成失败，降级到简单截取: %s", exc)
            return self._simple_preview(content_md)

    async def _smart_preview(self, content_md: str, mode: str) -> str:
        """智能模式：调用 LLM 总结一句话"""
        # 提取前 1000 字用于总结
        snippet = content_md[:1000].strip()
        if not snippet:
            logger.warning("内容为空，无法生成预览")
            return "处理完成，可前往子文档查看详情。"

        mode_names = {
            "idea_expand": "思路扩展",
            "research": "深度调研",
        }
        mode_display = mode_names.get(mode, mode)

        # 构造 prompt（简洁版，适合快速模型）
        system_prompt = dedent(
            f"""
            你是一个专业的内容总结助手。你的任务是用一句话概括文档的核心内容。
            
            要求：
            - 一句话说清楚主题和核心思想
            - 格式：当前文档主要围绕"XXX"展开，核心思想是...
            - 不超过 {self._max_len} 字
            - 只输出总结文本，不要有引号或其他修饰
            
            当前处理模式：{mode_display}
            """
        ).strip()

        user_prompt = dedent(
            f"""
            请用一句话总结以下内容：

            ---
            {snippet}
            ---

            请直接输出总结：
            """
        ).strip()

        logger.info("开始生成智能预览，mode=%s，内容长度=%d", mode, len(snippet))
        generated = await self._llm.chat_completion(
            chain=self._chain,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )

        # 清理格式
        preview = self._clean_preview(generated)
        logger.info("智能预览生成成功（%d字）: %s", len(preview), preview[:50])
        return preview

    def _simple_preview(self, content_md: str) -> str:
        """简单模式：直接截取前 N 字符"""
        plain_text = content_md[:self._max_len].replace("\n", " ").strip()
        if len(content_md) > self._max_len:
            plain_text += "..."
        logger.info("使用简单预览（%d字）: %s", len(plain_text), plain_text[:50])
        return plain_text

    def _clean_preview(self, raw: str) -> str:
        """清理生成的预览文本"""
        preview = raw.strip()
        # 移除可能的引号包裹
        for quote in ['"', "'", """, """, "「", "」"]:
            if preview.startswith(quote) and preview.endswith(quote):
                preview = preview[1:-1].strip()
        # 只保留第一行
        preview = preview.split("\n")[0].strip()
        # 限制长度
        if len(preview) > self._max_len:
            preview = preview[:self._max_len] + "..."
        # 如果清理后为空，使用默认文案
        if not preview:
            preview = "处理完成，可前往子文档查看详情。"
        return preview
