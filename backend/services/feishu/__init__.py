"""
飞书 API 客户端模块

统一封装飞书各 API 能力，按领域划分：
- wiki: 知识库操作
- drive: 云盘文件/文件夹操作
- doc: 文档内容读写
- message: 消息通知
"""
from __future__ import annotations

from backend.services.feishu.base import FeishuBaseClient
from backend.services.feishu.errors import FeishuAPIError
from backend.services.feishu.wiki import FeishuWikiClient
from backend.services.feishu.drive import FeishuDriveClient
from backend.services.feishu.doc import FeishuDocClient
from backend.services.feishu.message import FeishuMessageClient


class FeishuClient:
    """
    飞书 API 统一入口客户端
    
    组合各子客户端，提供清晰的 API 调用接口：
    - feishu.wiki.xxx - 知识库操作
    - feishu.drive.xxx - 云盘操作
    - feishu.doc.xxx - 文档操作
    - feishu.message.xxx - 消息操作
    """
    
    def __init__(self) -> None:
        self._base = FeishuBaseClient()
        
        # 子客户端（共享 base 的 token 和 http 能力）
        self.wiki = FeishuWikiClient(self._base)
        self.drive = FeishuDriveClient(self._base)
        self.doc = FeishuDocClient(self._base)
        self.message = FeishuMessageClient(self._base)
    
    # ==================== 向后兼容的快捷方法 ====================
    # 保留常用方法，便于旧代码无缝迁移
    
    async def get_tenant_access_token(self) -> str:
        """获取 tenant_access_token（向后兼容）"""
        return await self._base.get_tenant_access_token()
    
    async def get_doc_meta(self, doc_token: str):
        """获取文档元数据（向后兼容）"""
        return await self.doc.get_meta(doc_token)
    
    async def get_doc_content(self, doc_token: str) -> str:
        """获取文档内容（向后兼容）"""
        return await self.doc.get_content(doc_token)
    
    async def get_wiki_node_by_token(self, *, node_token: str):
        """获取知识库节点（向后兼容）"""
        return await self.wiki.get_node_by_token(node_token=node_token)
    
    async def resolve_token(self, token: str, *, obj_type: str = "docx"):
        """解析 token 类型（向后兼容）"""
        return await self.wiki.resolve_token(token, obj_type=obj_type)
    
    async def create_wiki_child_doc(
        self, *, space_id: str, parent_node_token: str, title: str,
        obj_type: str = "docx", node_type: str = "origin"
    ):
        """创建知识库子文档（向后兼容）"""
        return await self.wiki.create_child_doc(
            space_id=space_id,
            parent_node_token=parent_node_token,
            title=title,
            obj_type=obj_type,
            node_type=node_type,
        )
    
    async def create_child_doc(self, folder_token: str, title: str) -> str:
        """在云盘文件夹创建文档（向后兼容，实际应使用 drive.create_doc）"""
        return await self.drive.create_doc(folder_token=folder_token, title=title)
    
    async def write_doc_content(self, doc_token: str, content_md: str) -> None:
        """写入文档内容（向后兼容）"""
        await self.doc.write_content(doc_token, content_md)
    
    async def append_reference_block(
        self, doc_token: str, child_title: str, child_url: str
    ) -> None:
        """追加引用链接（向后兼容）"""
        await self.doc.append_reference_block(doc_token, child_title, child_url)
    
    async def send_card(
        self, *, user_id: str, card_content: dict, receive_id_type: str = "open_id"
    ) -> None:
        """发送消息卡片（向后兼容）"""
        await self.message.send_card(
            user_id=user_id,
            card_content=card_content,
            receive_id_type=receive_id_type,
        )


__all__ = [
    "FeishuClient",
    "FeishuAPIError",
]
