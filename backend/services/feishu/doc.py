"""
飞书文档 API 客户端
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.services.feishu.base import FeishuBaseClient

from backend.services.feishu.errors import FeishuAPIError

logger = logging.getLogger(__name__)


class FeishuDocClient:
    """
    飞书文档 API 封装
    
    提供文档内容相关操作：
    - 获取文档元数据和内容
    - 写入文档内容（Markdown 转换）
    - 追加引用链接
    """
    
    def __init__(self, base: "FeishuBaseClient") -> None:
        self._base = base
    
    async def get_meta(self, doc_token: str) -> Dict[str, Any]:
        """
        获取文档元数据（title 等，但不包含 parent_token）
        
        注意：docx API 不返回父文件夹信息，如需获取请使用 drive.get_file_meta()
        """
        data = await self._base.request(
            "GET", f"/open-apis/docx/v1/documents/{doc_token}"
        )
        return data.get("data", {}).get("document", {})
    
    async def get_content(self, doc_token: str) -> str:
        """获取文档纯文本内容"""
        data = await self._base.request(
            "GET", f"/open-apis/docx/v1/documents/{doc_token}/raw_content"
        )
        return data.get("data", {}).get("content", "")
    
    async def convert_markdown_to_blocks(
        self, content_md: str, *, content_type: str = "markdown"
    ) -> Dict[str, Any]:
        """
        使用飞书官方接口将 Markdown 文本转换为 blocks 结构
        
        API: POST /docx/v1/documents/blocks/convert
        
        返回：
            {
                "blocks": List[Dict],  # 所有块的列表（无序）
                "first_level_block_ids": List[str]  # 顶层块的 ID 列表（按 Markdown 原始顺序）
            }
        """
        payload = {"content": content_md, "content_type": content_type}
        data = await self._base.request(
            "POST", "/open-apis/docx/v1/documents/blocks/convert", json=payload
        )
        blocks = data.get("data", {}).get("blocks")
        first_level_block_ids = data.get("data", {}).get("first_level_block_ids", [])
        
        if not isinstance(blocks, list) or not blocks:
            raise FeishuAPIError(f"convert_to_blocks returned invalid blocks: {data}")
        
        # 飞书要求表格的 merge_info 只读，需移除
        for blk in blocks:
            if blk.get("block_type") == "table":
                blk.pop("merge_info", None)
        
        logger.info(
            "convert_markdown_to_blocks succeeded: blocks=%d, first_level_blocks=%d",
            len(blocks),
            len(first_level_block_ids),
        )
        
        return {
            "blocks": blocks,
            "first_level_block_ids": first_level_block_ids,
        }
    
    async def write_content(self, doc_token: str, content_md: str) -> None:
        """
        将 Markdown 内容写入文档，带防护与回退：
        1) 长度过长先截断（避免超限）
        2) 优先：convert -> descendant 批量写入
        3) 失败或块数过多时，回退为单一纯文本块
        """
        # 1) 长度截断（飞书有长度与块数限制，这里做上限保护）
        max_md_len = 60000
        content_to_use = content_md
        if len(content_md) > max_md_len:
            content_to_use = content_md[:max_md_len] + "\n\n（内容已截断，长度超出上限）"
            logger.warning(
                "Markdown length exceeded %d chars, truncated for doc=%s", max_md_len, doc_token
            )

        convert_result: Optional[Dict[str, Any]] = None

        # 2) 优先走 convert -> descendant
        try:
            convert_result = await self.convert_markdown_to_blocks(content_to_use)
            blocks = convert_result["blocks"]
            
            if len(blocks) > 1000:
                logger.warning(
                    "Converted blocks count %d exceeds 1000, fallback to plain text block", len(blocks)
                )
                convert_result = None
        except FeishuAPIError as exc:
            logger.warning("convert_markdown_to_blocks failed, fallback to plain text block: %s", exc)
            convert_result = None

        if convert_result:
            try:
                logger.info(
                    "write_content: using descendant for doc=%s, blocks=%d, first_level_blocks=%d",
                    doc_token,
                    len(convert_result["blocks"]),
                    len(convert_result["first_level_block_ids"]),
                )
                await self.add_blocks_descendant(
                    doc_token, 
                    convert_result["blocks"],
                    convert_result["first_level_block_ids"],
                )
                return
            except FeishuAPIError as exc:
                logger.warning(
                    "add_blocks_descendant failed for doc=%s, fallback to plain text block: %s",
                    doc_token,
                    exc,
                )

        # 3) 回退方案：写一个简单的纯文本块
        logger.info("write_content: fallback to plain text block for doc=%s", doc_token)
        fallback_block = {
            "block_id": "plain_text_1",
            "block_type": 2,  # 文本块
            "text": {
                "elements": [
                    {"text_run": {"content": content_to_use}}
                ]
            },
            "children": [],
        }
        await self.add_blocks_descendant(doc_token, [fallback_block], ["plain_text_1"])
    
    async def append_reference_block(
        self, doc_token: str, child_title: str, child_url: str
    ) -> None:
        """在原文档末尾追加一个带链接的引用块"""
        convert_result = await self.convert_markdown_to_blocks(f"[{child_title}]({child_url})")
        await self.add_blocks_descendant(
            doc_token, 
            convert_result["blocks"],
            convert_result["first_level_block_ids"],
        )
    
    async def add_blocks_descendant(
        self,
        doc_token: str,
        blocks: List[Dict[str, Any]],
        first_level_block_ids: List[str],
        *,
        parent_block_id: Optional[str] = None,
        max_retries: int = 3,
        retry_interval_s: float = 5.0,
        chunk_size: int = 500,
    ) -> None:
        """
        使用"创建嵌套块"接口批量插入含父子关系的 blocks
        
        API: POST /docx/v1/documents/{doc_id}/blocks/{block_id}/descendant
        
        Args:
            doc_token: 文档 ID
            blocks: 所有块的列表（包括顶层和子块）
            first_level_block_ids: 顶层块的 ID 列表，按 Markdown 原始顺序排列（由 convert 接口返回）
            chunk_size: 分批大小（默认 500，最大 1000）
        """
        parent_id = parent_block_id or doc_token
        
        # 验证 blocks 结构
        normalized_blocks: List[Dict[str, Any]] = []
        for blk in blocks:
            blk_copy = dict(blk)
            if not blk_copy.get("block_id"):
                raise FeishuAPIError(f"Block missing block_id: {blk_copy}")
            normalized_blocks.append(blk_copy)
        
        logger.info(
            "add_blocks_descendant: total_blocks=%d, first_level_blocks=%d",
            len(normalized_blocks),
            len(first_level_block_ids),
        )

        async def _post_once(batch: List[Dict[str, Any]], batch_first_level_ids: List[str]) -> None:
            children_id = batch_first_level_ids
            
            if not children_id:
                raise FeishuAPIError(
                    f"No first_level_block_ids provided for batch (batch_size={len(batch)})"
                )
            
            payload = {
                "children_id": children_id,
                "descendants": batch,
            }
            
            for attempt in range(max_retries):
                try:
                    await self._base.request(
                        "POST",
                        f"/open-apis/docx/v1/documents/{doc_token}/blocks/{parent_id}/descendant",
                        json=payload,
                    )
                    logger.info(
                        "add_blocks_descendant succeeded: doc=%s, blocks=%d, first_level=%d",
                        doc_token,
                        len(batch),
                        len(children_id),
                    )
                    return
                except FeishuAPIError as exc:
                    # 只对 429（限频）重试，其他错误直接抛出
                    is_last = attempt >= max_retries - 1
                    if exc.status_code == 429 and not is_last:
                        logger.warning(
                            "add_blocks_descendant rate limited (429), retry %d/%d in %.1fs",
                            attempt + 1,
                            max_retries,
                            retry_interval_s,
                        )
                        await asyncio.sleep(retry_interval_s)
                        continue
                    # 其他错误（404/400/99991400等）直接抛出
                    raise

        # 分批（<=500）顺序写入，每批传入对应的 first_level_block_ids
        for idx in range(0, len(normalized_blocks), chunk_size):
            batch = normalized_blocks[idx : idx + chunk_size]
            # 找出这个 batch 中包含的顶层块 ID（按顺序）
            batch_block_ids = {b.get("block_id") for b in batch}
            batch_first_level_ids = [
                bid for bid in first_level_block_ids if bid in batch_block_ids
            ]
            await _post_once(batch, batch_first_level_ids)
