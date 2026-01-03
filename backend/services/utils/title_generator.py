from __future__ import annotations

import logging
from textwrap import dedent
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.core.llm_client import LLMClient

logger = logging.getLogger(__name__)


class TitleGenerator:
    """
    智能标题生成器：基于文档内容自动生成简洁、语义化的标题。
    
    设计目标：
    - 通用性：可被任何 OutputHandler 复用
    - 快速：使用轻量级模型（10秒内完成）
    - 可靠：生成失败时提供 fallback
    - 可配置：提取长度、标题长度等可调整
    """

    def __init__(
        self,
        *,
        llm_client: LLMClient,
        chain: str = "title_generation",
        content_preview_length: int = 800,
        max_title_length: int = 30,
    ) -> None:
        """
        Args:
            llm_client: LLM 客户端实例
            chain: LLM 配置链名称（用于标题生成）
            content_preview_length: 提取内容前 N 字符用于分析
            max_title_length: 生成标题的最大字符数
        """
        self._llm = llm_client
        self._chain = chain
        self._preview_len = content_preview_length
        self._max_title_len = max_title_length

    async def generate_title(
        self,
        *,
        content_md: str,
        mode: str,
        original_doc_title: str | None = None,
    ) -> str:
        """
        基于文档内容生成简洁标题。

        Args:
            content_md: Markdown 格式的文档内容
            mode: 处理模式（如 "idea_expand", "research"）
            original_doc_title: 原始文档标题（用于参考）

        Returns:
            生成的标题（失败时返回基于 mode 的默认标题）
        """
        mode_names = {
            "idea_expand": "思路扩展",
            "research": "深度调研",
        }
        mode_display = mode_names.get(mode, mode)

        # 提取内容预览（前 N 字符）
        content_preview = content_md[: self._preview_len].strip()
        if not content_preview:
            logger.warning("内容为空，无法生成标题，使用默认标题")
            return self._fallback_title(mode_display, original_doc_title)

        # 构造 prompt
        system_prompt = dedent(
            f"""
            你是一个专业的标题生成助手。你的任务是根据给定的文档内容，生成一个简洁、准确、吸引人的标题。
            
            要求：
            - 标题长度不超过 {self._max_title_len} 个字符
            - 直接体现文档的核心主题或价值
            - 避免使用"未命名"、"文档"等通用词汇
            - 使用简洁、专业的语言
            - 只输出标题文本，不要有引号、前缀或其他修饰
            
            当前处理模式：{mode_display}
            """
        ).strip()

        user_prompt = dedent(
            f"""
            请为以下内容生成一个简洁的标题：

            ---
            {content_preview}
            ---

            请直接输出标题（不要包含引号或其他格式）：
            """
        ).strip()

        try:
            logger.info("开始生成标题，mode=%s，内容长度=%d", mode, len(content_preview))
            generated_title = await self._llm.chat_completion(
                chain=self._chain,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
            )

            # 清理生成的标题
            title = self._clean_title(generated_title)
            logger.info("标题生成成功: %s", title)
            return title

        except Exception as exc:
            logger.warning("标题生成失败，使用默认标题: %s", exc)
            return self._fallback_title(mode_display, original_doc_title)

    def _clean_title(self, raw_title: str) -> str:
        """清理生成的标题：去除引号、换行、多余空格等"""
        title = raw_title.strip()
        # 移除可能的引号包裹
        for quote in ['"', "'", """, """, "「", "」"]:
            if title.startswith(quote) and title.endswith(quote):
                title = title[1:-1].strip()
        # 只保留第一行（如果生成了多行）
        title = title.split("\n")[0].strip()
        # 限制长度
        if len(title) > self._max_title_len:
            title = title[: self._max_title_len] + "..."
        # 如果清理后为空，使用占位符
        if not title:
            title = "AI生成内容"
        return title

    def _fallback_title(
        self, mode_display: str, original_doc_title: str | None
    ) -> str:
        """生成 fallback 标题"""
        if original_doc_title and "未命名" not in original_doc_title:
            return f"{original_doc_title} - {mode_display}"
        return f"AI {mode_display}结果"
