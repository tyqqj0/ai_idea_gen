from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING

from backend.services.feishu import FeishuClient
from backend.services.outputs.base import BaseOutputHandler, OutputResult, SourceDoc
from backend.services.processors.base import ProcessorResult

if TYPE_CHECKING:
    from backend.core.manager import ProcessContext


class FeishuChildDocOutputHandler(BaseOutputHandler):
    """
    默认输出策略：将 ProcessorResult 写入飞书子文档，并在原文档末尾插入引用链接；可选发送通知卡片。
    """

    def __init__(self, *, feishu_client: FeishuClient) -> None:
        self._feishu = feishu_client

    async def handle(
        self,
        *,
        ctx: "ProcessContext",
        source_doc: SourceDoc,
        processor_result: ProcessorResult,
        notify_user: bool = True,
    ) -> OutputResult:
        # 兼容现有逻辑：尽量将子文档创建在原文档所在目录下
        folder_token = source_doc.parent_token or source_doc.doc_token

        child_doc_token = await self._feishu.create_child_doc(
            folder_token=folder_token,
            title=processor_result.title or f"{source_doc.title} - AI 生成",
        )
        await self._feishu.write_doc_content(child_doc_token, processor_result.content_md)

        child_doc_url = self._build_doc_url(child_doc_token)

        # 回链到原文档末尾
        await self._feishu.append_reference_block(
            source_doc.doc_token, processor_result.title, child_doc_url
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
            metadata={"output": "feishu_child_doc"},
        )

    def _build_doc_url(self, doc_token: str) -> str:
        return f"https://feishu.cn/docx/{doc_token}"

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


