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

            resp = await self._client.post(
                "/open-apis/auth/v3/tenant_access_token/internal", json=payload
            )
            data = resp.json()
            if resp.status_code != 200 or data.get("code") != 0:
                raise FeishuAPIError(
                    f"Failed to get tenant_access_token: {data}",
                    status_code=resp.status_code,
                )

            token = data["tenant_access_token"]
            expire = data.get("expire", 3600)
            self._tenant_token = token
            self._tenant_token_expire_at = time.time() + expire
            logger.info("Refreshed tenant_access_token, expire_in=%ss", expire)
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

    async def write_doc_content(self, doc_token: str, content_md: str) -> None:
        """
        将 Markdown 内容写入文档。当前实现将整段内容写入一个 markdown block。
        """
        markdown_block = {
            "block_type": "markdown",
            "markdown": {"content": content_md},
        }
        await self.append_blocks(doc_token, [markdown_block])

    async def append_reference_block(
        self, doc_token: str, child_title: str, child_url: str
    ) -> None:
        """
        在原文档末尾追加一个带链接的引用块。
        """
        block = {
            "block_type": "markdown",
            "markdown": {
                "content": f"[{child_title}]({child_url})",
            },
        }
        await self.append_blocks(doc_token, [block])

    async def append_blocks(self, doc_token: str, blocks: List[Dict[str, Any]]) -> None:
        """
        向指定文档追加 blocks。
        """
        payload = {"blocks": blocks}
        await self._request(
            "POST", f"/open-apis/docx/v1/documents/{doc_token}/blocks", json=payload
        )

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
        headers = {"Authorization": f"Bearer {token}"}

        # 调试日志：打印实际发送的请求信息
        full_url = f"{self.FEISHU_HOST}{path}"
        if params:
            # 简单拼接 query string（实际 httpx 会处理）
            query_str = "&".join(f"{k}={v}" for k, v in params.items())
            full_url = f"{full_url}?{query_str}"
        
        # Token 打码（只显示前4后4）
        masked_token = f"{token[:4]}...{token[-4:]}" if len(token) > 8 else "***"
        masked_headers = {k: (masked_token if k == "Authorization" else v) for k, v in headers.items()}
        
        logger.info(
            "Feishu API Request: %s %s\n  Headers: %s\n  Body: %s",
            method,
            full_url,
            masked_headers,
            json if json else (params if params else None),
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



