"""
子文档写入服务（通用输出能力）

负责：
1. 场景判断（知识库 vs 云盘）
2. 容器创建/复用（文件夹 or 知识库节点）
3. 文档创建
4. 内容写入
5. 权限授予
6. 回链（可选）

不负责：
- 业务逻辑（如调用 LLM 扩展思路）
- 标题生成（由调用方提供或使用 TitleGenerator）
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from backend.services.feishu import FeishuClient

logger = logging.getLogger(__name__)


@dataclass
class WriteChildDocRequest:
    """写子文档请求"""

    content: str  # 要写入的内容（Markdown）
    source_token: str  # 原始文档 token
    user_id: str  # 用户 open_id
    title: str  # 文档标题

    # 可选参数
    wiki_space_id: str | None = None  # 知识库空间 ID（如有）
    wiki_node_token: str | None = None  # 知识库节点 token（如有）

    # 高级选项
    backlink: bool = True  # 是否回链到原文档
    grant_permission: bool = True  # 是否授予用户权限


@dataclass
class WriteChildDocResult:
    """写子文档结果"""

    success: bool

    # 新文档信息
    child_doc_token: str
    child_doc_url: str
    title: str

    # 容器信息（文件夹或知识库节点）
    container_token: str
    container_url: str
    container_name: str
    container_type: str  # 'folder' | 'wiki_node'

    # 状态信息
    permission_granted: bool
    permission_errors: list[str]
    backlink_success: bool
    backlink_error: str | None

    # 来源信息
    source_doc_token: str
    source_doc_url: str


class ChildDocWriter:
    """子文档写入服务"""

    def __init__(self, feishu_client: "FeishuClient") -> None:
        self._feishu = feishu_client

    async def write(self, request: WriteChildDocRequest) -> WriteChildDocResult:
        """
        核心方法：根据请求自动完成子文档创建

        流程：
        1. 判断场景（知识库 or 云盘）
        2. 创建/复用容器
        3. 创建新文档
        4. 写入内容
        5. 授予权限
        6. 回链原文档（可选）
        7. 返回结果
        """
        if request.wiki_node_token:
            return await self._write_to_wiki(request)
        else:
            return await self._write_to_drive(request)

    async def _write_to_wiki(
        self, req: WriteChildDocRequest
    ) -> WriteChildDocResult:
        """知识库场景"""
        # 1. 获取 space_id（如果未提供）
        wiki_space_id = req.wiki_space_id
        if not wiki_space_id:
            wiki_node = await self._feishu.get_wiki_node_by_token(
                node_token=req.wiki_node_token
            )
            wiki_space_id = str(wiki_node.get("space_id") or "")

        if not wiki_space_id:
            raise RuntimeError("Missing wiki_space_id (cannot create child node)")

        # 2. 创建子节点
        child_node = await self._feishu.create_wiki_child_doc(
            space_id=wiki_space_id,
            parent_node_token=req.wiki_node_token,
            title=req.title,
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
            req.wiki_node_token,
        )

        # 3. 添加用户权限（知识库：edit + container）
        permission_errors = []
        perm_ok, perm_err = await self._grant_permission_safe(
            token=child_node_token,
            file_type="wiki",
            user_id=req.user_id,
            perm="edit",
            perm_type="container",
        )
        permission_granted = perm_ok
        if perm_err:
            permission_errors.append(perm_err)

        # 4. 等待文档可见（飞书 API 短暂延迟）
        await asyncio.sleep(5.0)

        # 5. 写入内容
        await self._feishu.write_doc_content(child_doc_token, req.content)

        # 6. 回链到原文档（可选）
        backlink_success = False
        backlink_error = None
        if req.backlink:
            backlink_success, backlink_error = await self._add_backlink_safe(
                source_token=req.source_token,
                child_title=req.title,
                child_url=child_doc_url,
            )

        return WriteChildDocResult(
            success=True,
            child_doc_token=child_doc_token,
            child_doc_url=child_doc_url,
            title=req.title,
            container_token=child_node_token,
            container_url=child_doc_url,  # 知识库节点 URL 即文档 URL
            container_name=req.title,
            container_type="wiki_node",
            permission_granted=permission_granted,
            permission_errors=permission_errors,
            backlink_success=backlink_success,
            backlink_error=backlink_error,
            source_doc_token=req.source_token,
            source_doc_url=f"https://feishu.cn/wiki/{req.wiki_node_token}",
        )

    async def _write_to_drive(
        self, req: WriteChildDocRequest
    ) -> WriteChildDocResult:
        """云盘场景"""
        # 1. 获取原文档元信息
        doc_meta_list = await self._feishu.drive.batch_get_meta([req.source_token])
        if not doc_meta_list:
            raise RuntimeError(f"Cannot get metadata for source doc: {req.source_token}")

        doc_meta = doc_meta_list[0]
        parent_folder = doc_meta.get("parent_token") or ""
        source_title = doc_meta.get("title") or "未命名文档"

        logger.info(
            "云盘场景：准备创建同名文件夹 parent_folder=%s, folder_name=%s",
            parent_folder or "(root)",
            source_title,
        )

        # 2. 查询是否已有同名文件夹
        existing_folders = await self._feishu.drive.list_files(
            folder_token=parent_folder,
            page_size=200,
            type_filter="folder",
        )
        folder_token: str | None = None
        folder_name: str | None = None

        for item in existing_folders:
            item_name = item.get("name") or item.get("title")
            item_token = item.get("token")
            if item_name == source_title and item_token:
                folder_token = str(item_token)
                folder_name = item_name
                logger.info(
                    "发现同名文件夹已存在，将复用: token=%s, name=%s",
                    folder_token,
                    folder_name,
                )
                break

        # 3. 创建/复用文件夹
        if not folder_token:
            try:
                folder_token = await self._feishu.drive.create_folder(
                    parent_folder_token=parent_folder,
                    name=source_title,
                )
                folder_name = source_title
                logger.info("成功创建文件夹：%s", folder_token)
            except Exception as e:
                # 检查是否是"文件夹已存在"错误（1062505）
                error_str = str(e)
                if "1062505" in error_str or "folder already exists" in error_str.lower():
                    logger.info("检测到同名文件夹已存在，重新查询")
                    existing_folders = await self._feishu.drive.list_files(
                        folder_token=parent_folder,
                        page_size=200,
                        type_filter="folder",
                    )
                    for item in existing_folders:
                        item_name = item.get("name") or item.get("title")
                        item_token = item.get("token")
                        if item_name == source_title and item_token:
                            folder_token = str(item_token)
                            folder_name = item_name
                            logger.info("复用现有同名文件夹: token=%s", folder_token)
                            break
                    if not folder_token:
                        raise
                else:
                    raise

        # 4. 添加文件夹权限（云盘：view）
        permission_errors = []
        folder_perm_ok, folder_perm_err = await self._grant_permission_safe(
            token=folder_token,
            file_type="folder",
            user_id=req.user_id,
            perm="view",
        )
        if folder_perm_err:
            permission_errors.append(folder_perm_err)

        # 5. 在文件夹中创建子文档
        child_doc_token = await self._feishu.drive.create_doc(
            folder_token=folder_token,
            title=req.title,
        )
        child_doc_url = self._build_doc_url(child_doc_token)

        # 6. 添加文档权限（云盘：view）
        doc_perm_ok, doc_perm_err = await self._grant_permission_safe(
            token=child_doc_token,
            file_type="docx",
            user_id=req.user_id,
            perm="view",
        )
        if doc_perm_err:
            permission_errors.append(doc_perm_err)

        # 权限添加状态：两个都成功才算成功
        permission_granted = folder_perm_ok and doc_perm_ok

        # 7. 写入内容
        await self._feishu.write_doc_content(child_doc_token, req.content)

        # 8. 回链到原文档（可选）
        backlink_success = False
        backlink_error = None
        if req.backlink:
            backlink_success, backlink_error = await self._add_backlink_safe(
                source_token=req.source_token,
                child_title=req.title,
                child_url=child_doc_url,
            )

        return WriteChildDocResult(
            success=True,
            child_doc_token=child_doc_token,
            child_doc_url=child_doc_url,
            title=req.title,
            container_token=folder_token,
            container_url=f"https://feishu.cn/drive/folder/{folder_token}",
            container_name=folder_name,
            container_type="folder",
            permission_granted=permission_granted,
            permission_errors=permission_errors,
            backlink_success=backlink_success,
            backlink_error=backlink_error,
            source_doc_token=req.source_token,
            source_doc_url=self._build_doc_url(req.source_token),
        )

    async def _grant_permission_safe(
        self,
        token: str,
        file_type: str,
        user_id: str,
        perm: str,
        perm_type: str | None = None,
    ) -> tuple[bool, str | None]:
        """安全添加权限（失败不阻断主流程）"""
        try:
            await self._feishu.drive.add_permission(
                token=token,
                file_type=file_type,
                member_id=user_id,
                perm=perm,
                member_type="openid",
                collaborator_type="user",
                perm_type=perm_type,
            )
            logger.info(
                "权限添加成功: token=%s, type=%s, perm=%s",
                token,
                file_type,
                perm,
            )
            return True, None
        except Exception as e:
            error_msg = str(e)
            logger.warning(
                "权限添加失败（不影响主流程）: token=%s, error=%s",
                token,
                error_msg,
            )
            return False, error_msg

    async def _add_backlink_safe(
        self,
        source_token: str,
        child_title: str,
        child_url: str,
    ) -> tuple[bool, str | None]:
        """安全添加回链（失败不阻断主流程）"""
        try:
            await self._feishu.append_reference_block(
                source_token, child_title, child_url
            )
            logger.info("成功在原文档末尾添加回链引用")
            return True, None
        except Exception as e:
            error_msg = str(e)
            logger.warning(
                "回链到原文档失败（应用可能无编辑权限），但主流程已完成: %s",
                error_msg,
            )
            return False, error_msg

    def _build_doc_url(self, doc_token: str) -> str:
        return f"https://feishu.cn/docx/{doc_token}"

    def _build_wiki_url(self, node_token: str) -> str:
        return f"https://feishu.cn/wiki/{node_token}"
