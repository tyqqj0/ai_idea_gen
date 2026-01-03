from __future__ import annotations

import asyncio
import json
from json import JSONDecodeError
import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)


class FeishuAPIError(Exception):
    """
    统一的飞书 API 异常。
    """

    def __init__(self, message: str, *, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class FeishuClient:
    """
    飞书 API 封装：负责 Token 获取、文档读写、卡片发送等。
    提供最常用的能力，其余接口可按需扩展。
    """

    FEISHU_HOST = "https://open.feishu.cn"

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = httpx.AsyncClient(base_url=self.FEISHU_HOST, timeout=20.0)
        self._tenant_token: Optional[str] = None
        self._tenant_token_expire_at: float = 0.0
        self._token_lock = asyncio.Lock()

    async def get_tenant_access_token(self) -> str:
        """
        获取并缓存 tenant_access_token，带有简单的 TTL 控制。
        """
        async with self._token_lock:
            if self._tenant_token and time.time() < self._tenant_token_expire_at - 60:
                return self._tenant_token

            payload = {
                "app_id": self.settings.FEISHU_APP_ID,
                "app_secret": self.settings.FEISHU_APP_SECRET,
            }

            logger.info(
                "Requesting tenant_access_token with app_id=%s (secret masked)",
                self.settings.FEISHU_APP_ID,
            )
            resp = await self._client.post(
                "/open-apis/auth/v3/tenant_access_token/internal", json=payload
            )
            data = resp.json()
            if resp.status_code != 200 or data.get("code") != 0:
                logger.error(
                    "Failed to get tenant_access_token: app_id=%s, response=%s",
                    self.settings.FEISHU_APP_ID,
                    data,
                )
                raise FeishuAPIError(
                    f"Failed to get tenant_access_token: {data}",
                    status_code=resp.status_code,
                )

            token = data["tenant_access_token"]
            expire = data.get("expire", 3600)
            self._tenant_token = token
            self._tenant_token_expire_at = time.time() + expire
            # Token 打码显示（前4后4）
            masked_token = f"{token[:4]}...{token[-4:]}" if len(token) > 8 else "***"
            logger.info(
                "Refreshed tenant_access_token: app_id=%s, token=%s, expire_in=%ss",
                self.settings.FEISHU_APP_ID,
                token,
                expire,
            )
            return token

    async def get_doc_meta(self, doc_token: str) -> Dict[str, Any]:
        """
        获取文档元数据（包括 parent_token, title）。
        注意：新版文档（docx）需使用 docx 接口获取信息。
        """
        try:
            # 尝试使用 docx 接口获取元数据
            data = await self._request(
                "GET", f"/open-apis/docx/v1/documents/{doc_token}"
            )
            # docx 接口返回结构: {"data": {"document": {"title": "...", ...}}}
            return data.get("data", {}).get("document", {})
        except FeishuAPIError as e:
            # 如果 docx 接口返回 404 (资源不存在) 或者 400 (Bad Request)，可能是旧版文档或其他情况
            # 但根据测试，drive/v1/files 接口对 docx token 返回 404 Gateway Error，
            # 所以优先使用 docx 接口。
            # 如果需要 fallback，可以在这里处理，但目前直接抛出更清晰
            raise e

    async def get_doc_content(self, doc_token: str) -> str:
        """
        获取文档纯文本内容。
        """
        data = await self._request(
            "GET", f"/open-apis/docx/v1/documents/{doc_token}/raw_content"
        )
        return data.get("data", {}).get("content", "")

    async def get_wiki_node_by_token(self, *, node_token: str) -> Dict[str, Any]:
        """
        通过 node_token 获取知识库节点信息（包含 space_id、obj_token 等）。
        需要应用开通 wiki:node:read（或更高）权限。
        """
        data = await self._request(
            "GET",
            "/open-apis/wiki/v2/spaces/get_node",
            params={"token": node_token},
        )
        node = data.get("data", {}).get("node")
        if not node:
            raise FeishuAPIError(f"Unable to parse wiki node from response: {data}")
        return node

    async def resolve_token(
        self, token: str, *, obj_type: str = "docx"
    ) -> Dict[str, Optional[str]]:
        """
        将任意传入的 token 解析为：
        - doc_token: 文档实体 ID（docx 对应的 obj_token）
        - wiki_node_token: 如果是知识库节点则返回
        - wiki_space_id: 如果是知识库节点则返回

        逻辑：
        1) 尝试按 wiki node 解析（需要 wiki:node:read 权限；若失败则忽略）
        2) 失败则视为普通 doc_token
        """
        try:
            node = await self.get_wiki_node_by_token(node_token=token)
            doc_token = (
                node.get("obj_token")
                or node.get("objToken")
                or node.get("document_id")
                or node.get("doc_token")
            )
            space_id = node.get("space_id") or node.get("spaceId")
            if doc_token:
                return {
                    "doc_token": str(doc_token),
                    "wiki_node_token": token,
                    "wiki_space_id": str(space_id) if space_id else None,
                }
        except FeishuAPIError:
            # 不是 wiki 节点或无权限读取，降级为普通 doc token
            pass

        return {
            "doc_token": token,
            "wiki_node_token": None,
            "wiki_space_id": None,
        }

    async def create_wiki_child_doc(
        self,
        *,
        space_id: str,
        parent_node_token: str,
        title: str,
        obj_type: str = "docx",
        node_type: str = "origin",
    ) -> Dict[str, Any]:
        """
        在知识库指定父节点下创建子节点，并创建/挂载一个 docx 对象。

        说明：
        - 这里优先走“创建节点时指定 obj_type/title”路径（由 Wiki 创建并挂载对象），避免 drive/docx 的 folder_token 挂载问题。
        - 成功返回 node 信息（包含 node_token/obj_token/space_id 等）。
        """
        payload = {
            "parent_node_token": parent_node_token,
            "obj_type": obj_type,
            "node_type": node_type,
            "title": title,
        }
        data = await self._request(
            "POST", f"/open-apis/wiki/v2/spaces/{space_id}/nodes", json=payload
        )
        node = data.get("data", {}).get("node") or data.get("data", {}).get("wiki_node")
        if not node:
            raise FeishuAPIError(f"Unable to parse wiki node from response: {data}")
        return node

    async def create_child_doc(self, folder_token: str, title: str) -> str:
        """
        在指定目录下创建子文档，返回子文档 token。
        """
        payload = {
            "folder_token": folder_token,
            "title": title,
        }
        data = await self._request("POST", "/open-apis/docx/v1/documents", json=payload)
        document = data.get("data", {}).get("document", {})
        token = (
            document.get("document_id")
            or document.get("doc_token")
            or document.get("token")
        )
        if not token:
            raise FeishuAPIError("Unable to parse child document token from response")
        return token

    async def convert_markdown_to_blocks(
        self, content_md: str, *, content_type: str = "markdown"
    ) -> List[Dict[str, Any]]:
        """
        使用飞书官方接口将 Markdown 文本转换为 blocks 结构。
        正式路径：/open-apis/docx/v1/documents/blocks/convert
        """
        payload = {"content": content_md, "content_type": content_type}
        data = await self._request(
            "POST", "/open-apis/docx/v1/documents/blocks/convert", json=payload
        )
        blocks = data.get("data", {}).get("blocks")
        if not isinstance(blocks, list) or not blocks:
            raise FeishuAPIError(f"convert_to_blocks returned invalid blocks: {data}")
        # 飞书要求表格的 merge_info 只读，需移除
        for blk in blocks:
            if blk.get("block_type") == "table":
                blk.pop("merge_info", None)
        # 记录 block 类型分布，便于调试 schema 问题
        block_types = {blk.get("block_type") for blk in blocks}
        logger.info(
            "convert_markdown_to_blocks succeeded: blocks=%d, block_types=%s",
            len(blocks),
            block_types,
        )
        return blocks

    async def write_doc_content(self, doc_token: str, content_md: str) -> None:
        """
        将 Markdown 内容写入文档，带防护与回退：
        1) 长度过长先截断（避免超限）
        2) 优先：convert -> descendant 批量写入
        3) 失败或块数过多时，回退为单一 markdown block（最保守）
        """
        # 1) 长度截断（飞书有长度与块数限制，这里做上限保护）
        max_md_len = 60000
        truncated = False
        content_to_use = content_md
        if len(content_md) > max_md_len:
            content_to_use = content_md[:max_md_len] + "\n\n（内容已截断，长度超出上限）"
            truncated = True
            logger.warning(
                "Markdown length exceeded %d chars, truncated for doc=%s", max_md_len, doc_token
            )

        blocks: Optional[List[Dict[str, Any]]] = None

        # 2) 优先走 convert -> descendant
        try:
            blocks = await self.convert_markdown_to_blocks(content_to_use)
            if len(blocks) > 1000:
                logger.warning(
                    "Converted blocks count %d exceeds 1000, fallback to markdown block", len(blocks)
                )
                blocks = None
        except FeishuAPIError as exc:
            logger.warning("convert_markdown_to_blocks failed, fallback to markdown block: %s", exc)
            blocks = None

        if blocks:
            try:
                logger.info(
                    "write_doc_content: using descendant for doc=%s, blocks=%d",
                    doc_token,
                    len(blocks),
                )
                await self.add_blocks_descendant(doc_token, blocks)
                return
            except FeishuAPIError as exc:
                logger.warning(
                    "add_blocks_descendant failed for doc=%s, fallback to plain text block: %s",
                    doc_token,
                    exc,
                )

        # 3) 回退方案：写一个简单的纯文本块（避免手工构造 Markdown 块）
        # 注意：此处不再使用 markdown block_type，而是使用 text block，符合飞书 schema
        logger.info("write_doc_content: fallback to plain text block for doc=%s", doc_token)
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
        await self.add_blocks_descendant(doc_token, [fallback_block])

    async def append_reference_block(
        self, doc_token: str, child_title: str, child_url: str
    ) -> None:
        """
        在原文档末尾追加一个带链接的引用块（走 Markdown 转换，以保证结构正确）。
        """
        blocks = await self.convert_markdown_to_blocks(f"[{child_title}]({child_url})")
        await self.add_blocks_descendant(doc_token, blocks)

    async def append_blocks(
        self,
        doc_token: str,
        blocks: List[Dict[str, Any]],
        *,
        max_retries: int = 3,
        retry_interval_s: float = 5.0,
        chunk_size: int = 50,
    ) -> None:
        """
        使用“创建块”接口，将一批简单子块追加到文档根节点。
        - 接口：/open-apis/docx/v1/documents/{document_id}/blocks/{block_id}/children
        - 当前用于简单回退场景（无复杂嵌套需求）
        """
        normalized: List[Dict[str, Any]] = []
        for blk in blocks:
            blk_copy = dict(blk)
            normalized.append(blk_copy)

        async def _post_once(batch: List[Dict[str, Any]]) -> None:
            payload = {"children": batch, "index": -1}
            for attempt in range(max_retries):
                try:
                    await self._request(
                        "POST",
                        f"/open-apis/docx/v1/documents/{doc_token}/blocks/{doc_token}/children",
                        json=payload,
                    )
                    return
                except FeishuAPIError as exc:
                    is_last = attempt >= max_retries - 1
                    if exc.status_code in (429, 400) and not is_last:
                        logger.warning(
                            "append_blocks got %s, doc_token=%s, attempt=%d/%d; retry in %.1fs",
                            exc.status_code,
                            doc_token,
                            attempt + 1,
                            max_retries,
                            retry_interval_s,
                        )
                        await asyncio.sleep(retry_interval_s)
                        continue
                    raise

        for idx in range(0, len(normalized), chunk_size):
            batch = normalized[idx : idx + chunk_size]
            await _post_once(batch)

    async def add_blocks_descendant(
        self,
        doc_token: str,
        blocks: List[Dict[str, Any]],
        *,
        parent_block_id: Optional[str] = None,
        max_retries: int = 3,
        retry_interval_s: float = 5.0,
        chunk_size: int = 500,  # 官方上限 1000，这里保守 500 以防超限
    ) -> None:
        """
        使用“创建嵌套块”接口批量插入含父子关系的 blocks。
        - 接口：/open-apis/docx/v1/documents/{doc_id}/blocks/{block_id}/descendant
        - 要求：children_id 为根级块的临时 ID 列表；descendants 为含父子关系的块列表
        - 限制：children_id/descendants 最多 1000，这里按 500 分批发送
        """
        parent_id = parent_block_id or doc_token
        
        # 规范化 blocks：确保所有块都有 block_id 和正确的 parent_id
        normalized_blocks: List[Dict[str, Any]] = []
        for blk in blocks:
            blk_copy = dict(blk)
            # 确保有 block_id（convert 接口应该已经提供了）
            if not blk_copy.get("block_id"):
                raise FeishuAPIError(f"Block missing block_id: {blk_copy}")
            # 规范 parent_id：如果 parent_id 为空或空字符串，设置为目标父块（顶层块）
            blk_parent_id = blk_copy.get("parent_id")
            if not blk_parent_id or blk_parent_id == "":
                blk_copy["parent_id"] = parent_id
            # 清理只读字段（表格 merge_info 已在转换时移除，这里防御性再删）
            if blk_copy.get("block_type") == "table" or isinstance(blk_copy.get("table"), dict):
                blk_copy.pop("merge_info", None)
                if isinstance(blk_copy.get("table"), dict):
                    blk_copy["table"].pop("merge_info", None)
            # 注意：descendant 接口要求扁平化结构，每个块通过 parent_id 表示父子关系
            # convert 接口返回的 blocks 应该已经是扁平化的，不需要 children 字段
            # 但为了安全，我们保留原始结构，只确保 parent_id 正确
            normalized_blocks.append(blk_copy)

        async def _post_once(batch: List[Dict[str, Any]]) -> None:
            # children_id：只包含 parent_id == parent_id 的块（第一级子块）
            children_id = [
                b.get("block_id") for b in batch if b.get("parent_id") == parent_id and b.get("block_id")
            ]
            if not children_id:
                raise FeishuAPIError(
                    f"No top-level blocks found in batch (parent_id={parent_id}, batch_size={len(batch)})"
                )
            # 验证：确保 children_id 中的所有 ID 都在 descendants 中
            batch_block_ids = {b.get("block_id") for b in batch if b.get("block_id")}
            missing_ids = set(children_id) - batch_block_ids
            if missing_ids:
                raise FeishuAPIError(
                    f"children_id contains IDs not in descendants: {missing_ids}"
                )
            # 验证：确保所有块的 parent_id 都指向有效的块（在 batch 中或等于 parent_id）
            valid_parent_ids = batch_block_ids | {parent_id}
            invalid_blocks = [
                b for b in batch
                if b.get("parent_id") and b.get("parent_id") not in valid_parent_ids
            ]
            if invalid_blocks:
                invalid_parent_ids = {b.get("parent_id") for b in invalid_blocks}
                logger.warning(
                    "Some blocks have invalid parent_id (not in batch or parent): %s",
                    invalid_parent_ids,
                )
                # 将无效的 parent_id 重置为 parent_id（防御性处理）
                for blk in invalid_blocks:
                    blk["parent_id"] = parent_id
                    # 如果这个块之前不在 children_id 中，现在应该加入（因为 parent_id 变成了 parent_id）
                    if blk.get("block_id") not in children_id:
                        children_id.append(blk.get("block_id"))
            payload = {
                "children_id": children_id,
                "descendants": batch,
            }
            logger.debug(
                "add_blocks_descendant batch: parent_id=%s, children_id_count=%d, descendants_count=%d",
                parent_id,
                len(children_id),
                len(batch),
            )
            for attempt in range(max_retries):
                try:
                    await self._request(
                        "POST",
                        f"/open-apis/docx/v1/documents/{doc_token}/blocks/{parent_id}/descendant",
                        json=payload,
        )
                    return
                except FeishuAPIError as exc:
                    is_last = attempt >= max_retries - 1
                    if exc.status_code in (404, 429, 99991400) and not is_last:
                        logger.warning(
                            "add_blocks_descendant retry doc=%s parent=%s attempt=%d/%d "
                            "(status=%s) in %.1fs",
                            doc_token,
                            parent_id,
                            attempt + 1,
                            max_retries,
                            exc.status_code,
                            retry_interval_s,
                        )
                        await asyncio.sleep(retry_interval_s)
                        continue
                    raise

        # 分批（<=500）顺序写入
        for idx in range(0, len(normalized_blocks), chunk_size):
            batch = normalized_blocks[idx : idx + chunk_size]
            await _post_once(batch)

    async def send_card(
        self,
        *,
        user_id: str,
        card_content: Dict[str, Any],
        receive_id_type: str = "open_id",
    ) -> None:
        """
        发送飞书卡片消息，默认按照 open_id 发送。
        """
        payload = {
            "receive_id": user_id,
            "msg_type": "interactive",
            "content": json.dumps(card_content, ensure_ascii=False),
        }
        await self._request(
            "POST",
            "/open-apis/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            json=payload,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        token = await self.get_tenant_access_token()
        # Token 打码（用于日志）
        masked_token = f"{token[:4]}...{token[-4:]}" if len(token) > 8 else "***"
        headers = {"Authorization": f"Bearer {token}"}
        logger.debug(
            "Using tenant_access_token=%s (app_id=%s) for %s %s",
            masked_token,
            self.settings.FEISHU_APP_ID,
            method,
            path,
        )

        # 调试日志：打印实际发送的请求信息
        full_url = f"{self.FEISHU_HOST}{path}"
        if params:
            # 简单拼接 query string（实际 httpx 会处理）
            query_str = "&".join(f"{k}={v}" for k, v in params.items())
            full_url = f"{full_url}?{query_str}"
        
        # Token 打码（只显示前4后4）
        masked_token = f"{token[:4]}...{token[-4:]}" if len(token) > 8 else "***"
        masked_headers = {k: (masked_token if k == "Authorization" else v) for k, v in headers.items()}
        
        # 构造精简版请求体摘要，避免在日志中输出超长内容
        body_summary: Dict[str, Any] = {}
        if json is not None:
            if isinstance(json, dict):
                if "content" in json and isinstance(json["content"], str):
                    body_summary["content_len"] = len(json["content"])
                if "children" in json and isinstance(json["children"], list):
                    body_summary["children_count"] = len(json["children"])
                if "descendants" in json and isinstance(json["descendants"], list):
                    body_summary["descendants_count"] = len(json["descendants"])
                # 记录其余关键字段的键名，避免输出大段内容
                other_keys = [
                    k for k in json.keys() if k not in ("content", "children", "descendants")
                ]
                if other_keys:
                    body_summary["keys"] = other_keys
            else:
                body_summary["json_type"] = str(type(json))
        elif params is not None:
            body_summary["params"] = params

        logger.info(
            "Feishu API Request: %s %s\n  Headers: %s\n  BodySummary: %s",
            method,
            full_url,
            masked_headers,
            body_summary or None,
        )

        resp = await self._client.request(
            method,
            path,
            params=params,
            json=json,
            headers=headers,
        )
        
        # 调试日志：打印响应状态和关键字段
        logger.info(
            "Feishu API Response: %s %s -> status=%s",
            method,
            path,
            resp.status_code,
        )
        try:
            data = resp.json()
        except JSONDecodeError:
            # 针对非 JSON 响应（如 404 page not found, 502 Bad Gateway 等）做容错处理
            logger.error(
                "Feishu API non-JSON response: %s %s -> status=%s, body=%s",
                method,
                path,
                resp.status_code,
                resp.text[:200],
            )
            raise FeishuAPIError(
                f"Feishu API returned non-JSON response. Status: {resp.status_code}, Body: {resp.text[:200]}",
                status_code=resp.status_code,
            )

        # 调试日志：打印响应体关键字段
        resp_code = data.get("code")
        resp_msg = data.get("msg")
        logger.info(
            "Feishu API Response body: %s %s -> code=%s, msg=%s",
            method,
            path,
            resp_code,
            resp_msg,
        )

        if resp.status_code != 200 or resp_code != 0:
            # 错误时打印完整响应（便于调试）
            logger.error(
                "Feishu API error: %s %s -> status=%s, code=%s, msg=%s, full_data=%s",
                method,
                path,
                resp.status_code,
                resp_code,
                resp_msg,
                data,
            )
            raise FeishuAPIError(
                f"Feishu API error path={path}, status={resp.status_code}, data={data}",
                status_code=resp.status_code,
            )
        return data



