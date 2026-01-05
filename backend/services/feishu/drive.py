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

# drive/v1/permissions 成员接口支持的文档类型
_PERMISSION_FILE_TYPES = {
    "doc",
    "sheet",
    "file",
    "wiki",
    "bitable",
    "docx",
    "folder",
    "mindnote",
    "minutes",
    "slides",
}


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
    
    async def list_files(
        self,
        *,
        folder_token: str = "",
        page_size: int = 200,
        type_filter: str | None = None,
    ) -> list[Dict[str, Any]]:
        """
        获取指定文件夹下的文件清单（仅当前层级）
        
        API: GET /drive/v1/files
        
        参数:
            - folder_token: 目标文件夹 token（空字符串表示根目录）
            - page_size: 每页数量，最大 200
            - type_filter: 可选，按类型过滤（如 "folder" 只返回文件夹）
        
        返回:
            - files 列表，每项至少包含 name/token/type 等字段
        """
        params: Dict[str, Any] = {
            "folder_token": folder_token,
            "page_size": page_size,
        }
        if type_filter:
            params["type"] = type_filter
        
        data = await self._base.request(
            "GET",
            "/open-apis/drive/v1/files",
            params=params,
        )
        files = data.get("data", {}).get("files", [])
        logger.info(
            "list_files succeeded: folder=%s, type=%s, count=%s",
            folder_token or "(root)",
            type_filter or "*",
            len(files),
        )
        return files
    
    async def create_folder(
        self, *, parent_folder_token: str, name: str
    ) -> str:
        """
        在指定文件夹下创建新文件夹
        
        API: POST /drive/v1/files/create_folder
        参数:
            - parent_folder_token: 父文件夹 token（传空字符串表示在根目录创建）
            - name: 文件夹名称
        
        返回: 新文件夹的 token
        
        注意：
        - 如果同名文件夹已存在，会返回 1062505 错误
        - 调用方需要捕获此错误并处理（如使用现有文件夹或创建带编号的新名称）
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
            parent_folder_token or "(root)",
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
    
    async def add_permission(
        self,
        *,
        token: str,
        file_type: str,
        member_id: str,
        perm: str = "view",
        member_type: str = "openid",
        collaborator_type: str = "user",
        perm_type: str | None = None,
    ) -> bool:
        """
        为文件/文件夹/知识库节点添加协作者权限
        
        API: POST /drive/v1/permissions/{token}/members?type={file_type}
        
        参数:
            - token: 文件/文件夹/wiki节点的 token
            - file_type: 资源类型 ("doc", "sheet", "file", "wiki", "bitable", "docx", "folder", "mindnote", "minutes", "slides")
            - member_id: 协作者 ID（对应 member_type 的值，如 open_id）
            - perm: 权限级别 ("view", "edit", "full_access")
            - member_type: 协作者 ID 类型 ("openid", "email", "unionid" 等)
            - collaborator_type: 协作者类型 ("user", "chat", "department")
            - perm_type: 权限范围类型（仅 wiki 有效，"container" 或 "single_page"）
        
        返回:
            - bool: 是否成功
        """
        payload = {
            "member_type": member_type,
            "member_id": member_id,
            "perm": perm,
            "type": collaborator_type,
        }
        if perm_type:
            payload["perm_type"] = perm_type
        
        if file_type not in _PERMISSION_FILE_TYPES:
            raise ValueError(
                f"Unsupported file_type for add_permission: {file_type}. "
                f"Must be one of: {sorted(_PERMISSION_FILE_TYPES)}"
            )
        
        await self._base.request(
            "POST",
            f"/open-apis/drive/v1/permissions/{token}/members",
            params={"type": file_type},
            json=payload,
        )
        
        logger.info(
            "add_permission succeeded: token=%s, type=%s, member=%s, perm=%s",
            token,
            file_type,
            member_id,
            perm,
        )
        return True
