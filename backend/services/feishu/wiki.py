"""
飞书知识库 API 客户端
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.services.feishu.base import FeishuBaseClient

from backend.services.feishu.errors import FeishuAPIError

logger = logging.getLogger(__name__)


class FeishuWikiClient:
    """
    飞书知识库 API 封装
    
    提供知识库相关操作：
    - 获取节点信息
    - 创建子节点/文档
    - Token 解析
    """
    
    def __init__(self, base: "FeishuBaseClient") -> None:
        self._base = base
    
    async def get_node_by_token(self, *, node_token: str) -> Dict[str, Any]:
        """
        通过 node_token 获取知识库节点信息（包含 space_id、obj_token 等）。
        需要应用开通 wiki:node:read（或更高）权限。
        """
        data = await self._base.request(
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
            node = await self.get_node_by_token(node_token=token)
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
    
    async def create_child_doc(
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
        - 这里优先走"创建节点时指定 obj_type/title"路径（由 Wiki 创建并挂载对象），避免 drive/docx 的 folder_token 挂载问题。
        - 成功返回 node 信息（包含 node_token/obj_token/space_id 等）。
        """
        payload = {
            "parent_node_token": parent_node_token,
            "obj_type": obj_type,
            "node_type": node_type,
            "title": title,
        }
        data = await self._base.request(
            "POST", f"/open-apis/wiki/v2/spaces/{space_id}/nodes", json=payload
        )
        node = data.get("data", {}).get("node") or data.get("data", {}).get("wiki_node")
        if not node:
            raise FeishuAPIError(f"Unable to parse wiki node from response: {data}")
        return node
