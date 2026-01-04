from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, TYPE_CHECKING

from backend.services.feishu import FeishuClient
from backend.services.outputs.base import BaseOutputHandler, OutputResult, SourceDoc
from backend.services.processors.base import ProcessorResult
from backend.services.utils.title_generator import TitleGenerator

if TYPE_CHECKING:
    from backend.core.manager import ProcessContext
    from backend.core.llm_client import LLMClient

logger = logging.getLogger(__name__)

# 模式标签映射（用于文档标题前缀）
MODE_LABELS = {
    "idea_expand": "[思路扩展]",
    "research": "[深度调研]",
}


class FeishuChildDocOutputHandler(BaseOutputHandler):
    """
    默认输出策略：将 ProcessorResult 写入飞书子文档，并在原文档末尾插入引用链接；可选发送通知卡片。
    """

    def __init__(self, *, feishu_client: FeishuClient, llm_client: "LLMClient") -> None:
        self._feishu = feishu_client
        self._title_generator = TitleGenerator(llm_client=llm_client)

    async def handle(
        self,
        *,
        ctx: "ProcessContext",
        source_doc: SourceDoc,
        processor_result: ProcessorResult,
        notify_user: bool = True,
    ) -> OutputResult:
        # 智能标题生成：如果原标题包含"未命名"，则调用 AI 生成标题
        title = processor_result.title or f"{source_doc.title} - AI 生成"
        if "未命名" in title:
            logger.info("检测到未命名文档，启动智能标题生成")
            try:
                title = await self._title_generator.generate_title(
                    content_md=processor_result.content_md,
                    mode=ctx.mode,
                    original_doc_title=source_doc.title,
                )
                logger.info("智能生成标题: %s", title)
            except Exception as exc:
                logger.warning("标题生成失败，使用默认标题: %s", exc)
                # title 保持原值（fallback 已在 TitleGenerator 内部处理）
        
        # 添加模式标签（如 [思路扩展]）
        title = self._add_mode_label(title, ctx.mode)
        logger.info("添加标签后的最终标题: %s", title)

        # 1) 知识库优先：如果前端/触发方提供了 wiki_node_token，则走知识库创建子节点
        wiki_node: Dict[str, Any] | None = None
        wiki_node_token = ctx.wiki_node_token
        wiki_space_id = ctx.wiki_space_id

        if wiki_node_token:
            # === 知识库路径 ===
            if not wiki_space_id:
                wiki_node = await self._feishu.get_wiki_node_by_token(node_token=wiki_node_token)
                wiki_space_id = str(wiki_node.get("space_id") or "")
            if not wiki_space_id:
                raise RuntimeError("Missing wiki_space_id (cannot create child node)")

            child_node = await self._feishu.create_wiki_child_doc(
                space_id=wiki_space_id,
                parent_node_token=wiki_node_token,
                title=title,
                obj_type="docx",
                node_type="origin",
            )

            child_obj_token = (
                child_node.get("obj_token")
                or child_node.get("objToken")
                or child_node.get("document_id")
                or child_node.get("doc_token")
            )
            child_node_token = (
                child_node.get("node_token")
                or child_node.get("nodeToken")
                or child_node.get("token")
            )
            if not child_obj_token or not child_node_token:
                raise RuntimeError(
                    "Unable to parse wiki child node from response. "
                    f"expect obj_token/node_token, got: {child_node}"
                )

            child_doc_token = str(child_obj_token)
            child_doc_url = self._build_wiki_url(str(child_node_token))

            logger.info(
                "Wiki child created: node_token=%s obj_token=%s space_id=%s parent_node=%s",
                child_node_token,
                child_doc_token,
                wiki_space_id,
                wiki_node_token,
            )

            # 部分场景下新建文档的 docx 接口存在短暂可见性延迟，等待片刻再写内容
            await asyncio.sleep(5.0)

            # 写入内容（写内容始终走 docx obj_token）
            # 追加元数据到文档末尾
            from backend.services.utils.metadata_builder import build_metadata_section
            
            # 构建元数据（包含原始内容）
            metadata = build_metadata_section(
                mode=ctx.mode,
                source_title=source_doc.title,
                source_url=f"https://feishu.cn/wiki/{wiki_node_token}",  # 知识库链接
                original_content=ctx.original_content,
                trigger_source=ctx.trigger_source,
            )
            final_content = processor_result.content_md + metadata
            await self._feishu.write_doc_content(child_doc_token, final_content)
        else:
            # === 云盘路径 ===
            # 尽量将子文档创建在原文档所在目录下（folder_token）
            folder_token = source_doc.parent_token or source_doc.doc_token
            child_doc_token = await self._feishu.create_child_doc(
                folder_token=folder_token,
                title=title,
            )
            # 追加元数据到文档末尾
            from backend.services.utils.metadata_builder import build_metadata_section
            
            # 构建元数据（包含原始内容）
            metadata = build_metadata_section(
                mode=ctx.mode,
                source_title=source_doc.title,
                source_url=self._build_doc_url(source_doc.doc_token),
                original_content=ctx.original_content,
                trigger_source=ctx.trigger_source,
            )
            final_content = processor_result.content_md + metadata
            await self._feishu.write_doc_content(child_doc_token, final_content)
            child_doc_url = self._build_doc_url(child_doc_token)

        # 2) 回链到原文档末尾（原文档可为 Wiki 挂载的 docx，仍可用 docx blocks 接口）
        await self._feishu.append_reference_block(
            source_doc.doc_token, title, child_doc_url
        )

        # 可选通知
        if notify_user:
            card = self._build_notify_card(
                ctx=ctx, child_doc_url=child_doc_url, summary=processor_result.summary
            )
            try:
                await self._feishu.send_card(user_id=ctx.user_id, card_content=card)
            except Exception:
                # 通知失败不影响主流程（日志在 FeishuClient 内/外层处理）
                pass

        return OutputResult(
            child_doc_token=child_doc_token,
            child_doc_url=child_doc_url,
            metadata={
                "output": "feishu_child_doc",
                "source_is_wiki": bool(wiki_node_token),
                "wiki_node": wiki_node,
                "wiki_node_token": wiki_node_token,
                "wiki_space_id": wiki_space_id,
            },
        )

    def _build_doc_url(self, doc_token: str) -> str:
        return f"https://feishu.cn/docx/{doc_token}"

    def _build_wiki_url(self, node_token: str) -> str:
        return f"https://feishu.cn/wiki/{node_token}"

    def _add_mode_label(self, title: str, mode: str) -> str:
        """
        为标题添加模式标签（前缀方式）
        
        Args:
            title: 原始标题
            mode: 处理模式
            
        Returns:
            添加标签后的标题
        """
        label = MODE_LABELS.get(mode)
        if not label:
            # 未知模式，不添加标签
            return title
        
        # 检查标题是否已经包含标签（避免重复添加）
        if title.startswith(label):
            return title
        
        # 添加标签，标签和标题之间加一个空格
        return f"{label} {title}"
    
    def _build_notify_card(
        self, *, ctx: "ProcessContext", child_doc_url: str, summary: str | None
    ) -> Dict[str, Any]:
        summary_text = summary or "处理完成，可前往子文档查看详情。"
        return {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": "AI 文档处理完成"}},
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**处理模式**：{ctx.mode}\n"
                            f"**结果**：[点击查看]({child_doc_url})\n\n"
                            f"{summary_text}"
                        ),
                    },
                }
            ],
        }


