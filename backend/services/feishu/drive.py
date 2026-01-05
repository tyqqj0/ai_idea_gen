"""
飞书云盘 Drive API 客户端
"""
from __future__ import annotations

import logging
from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.services.feishu.base import FeishuBaseClient

from backend.services.feishu.errors import FeishuAPIError

logger = logging.getLogger(__name__)


class FeishuDriveClient:
    """
    飞书云盘 API 封装
    
    提供云盘相关操作：
    - 获取文件元数据（包含 parent_token）
    - 创建文件夹
    - 在文件夹中创建文档
    """
    
    def __init__(self, base: "FeishuBaseClient") -> None:
        self._base = base
    
    async def get_file_meta(self, file_token: str, *, file_type: str = "docx", with_url: bool = False) -> Dict[str, Any]:
        """
        获取云盘文件的元数据（包含父文件夹 token）
        
        API: POST /drive/v1/metas/batch_query（飞书官方推荐接口）
        
        参数:
            - file_token: 文件 token
            - file_type: 文件类型（docx, sheet, bitable, folder 等）
            - with_url: 是否获取文件的访问链接
        
        返回字段示例：
            - name/title: 文件名
            - parent_token: 父文件夹 token
            - owner_id: 所有者 ID
            - url: 文件访问链接（如果 with_url=True）
        """
        payload = {
            "request_docs": [
                {
                    "doc_token": file_token,
                    "doc_type": file_type,
                }
            ],
            "with_url": with_url,
        }
        
        data = await self._base.request(
            "POST",
            "/open-apis/drive/v1/metas/batch_query",
            json=payload,
        )
        
        # 解析响应
        metas = data.get("data", {}).get("metas", [])
        if not metas or len(metas) == 0:
            raise FeishuAPIError(
                f"No metadata found for file_token={file_token}. "
                f"The file may not exist or the app lacks permission."
            )
        
        # 获取第一个（也是唯一的）结果
        meta = metas[0]
        
        # 检查是否有错误
        if "has_error" in meta and meta.get("has_error"):
            error_msg = meta.get("error_msg", "Unknown error")
            raise FeishuAPIError(
                f"Failed to get metadata for file_token={file_token}: {error_msg}"
            )
        
        logger.info(
            "get_file_meta succeeded: file_token=%s, name=%s, parent_token=%s, type=%s",
            file_token,
            meta.get("name") or meta.get("title"),
            meta.get("parent_token"),
            meta.get("type"),
        )
        return meta
    
    async def create_folder(
        self, *, parent_folder_token: str, name: str
    ) -> str:
        """
        在指定文件夹下创建新文件夹
        
        API: POST /drive/v1/files/create_folder
        参数:
            - parent_folder_token: 父文件夹 token
            - name: 文件夹名称
        
        返回: 新文件夹的 token
        """
        payload = {
            "folder_token": parent_folder_token,
            "name": name,
        }
        data = await self._base.request(
            "POST",
            "/open-apis/drive/v1/files/create_folder",
            json=payload,
        )
        folder_token = data.get("data", {}).get("token")
        if not folder_token:
            raise FeishuAPIError(f"Unable to parse folder token from response: {data}")
        
        logger.info(
            "create_folder succeeded: parent=%s, name=%s, new_folder_token=%s",
            parent_folder_token,
            name,
            folder_token,
        )
        return str(folder_token)
    
    async def create_doc(self, *, folder_token: str, title: str) -> str:
        """
        在指定文件夹下创建新版文档（docx）
        
        API: POST /docx/v1/documents
        参数:
            - folder_token: 文件夹 token
            - title: 文档标题
        
        返回: 新文档的 doc_token
        """
        payload = {
            "folder_token": folder_token,
            "title": title,
        }
        data = await self._base.request(
            "POST",
            "/open-apis/docx/v1/documents",
            json=payload,
        )
        document = data.get("data", {}).get("document", {})
        doc_token = (
            document.get("document_id")
            or document.get("doc_token")
            or document.get("token")
        )
        if not doc_token:
            raise FeishuAPIError(f"Unable to parse document token from response: {data}")
        
        logger.info(
            "create_doc succeeded: folder=%s, title=%s, doc_token=%s",
            folder_token,
            title,
            doc_token,
        )
        return str(doc_token)
