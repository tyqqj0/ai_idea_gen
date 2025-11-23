from __future__ import annotations

import asyncio
import json
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
        """
        data = await self._request(
            "GET", f"/open-apis/drive/v1/files/{doc_token}/meta"
        )
        return data.get("data", {})

    async def get_doc_content(self, doc_token: str) -> str:
        """
        获取文档纯文本内容。
        """
        data = await self._request(
            "GET", f"/open-apis/docx/v1/documents/{doc_token}/raw_content"
        )
        return data.get("data", {}).get("content", "")

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

        resp = await self._client.request(
            method,
            path,
            params=params,
            json=json,
            headers=headers,
        )
        data = resp.json()
        if resp.status_code != 200 or data.get("code") != 0:
            raise FeishuAPIError(
                f"Feishu API error path={path}, status={resp.status_code}, data={data}",
                status_code=resp.status_code,
            )
        return data



