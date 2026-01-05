from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, TYPE_CHECKING

from backend.services.feishu import FeishuClient
from backend.services.outputs.base import BaseOutputHandler, OutputResult, SourceDoc
from backend.services.processors.base import ProcessorResult
from backend.services.utils.title_generator import TitleGenerator

if TYPE_CHECKING:
    from backend.core.manager import ProcessContext
    from backend.core.llm_client import LLMClient

logger = logging.getLogger(__name__)

# 模式标签映射（用于文档标题前缀）
MODE_LABELS = {
    "idea_expand": "[思路扩展]",
    "research": "[深度调研]",
}


class FeishuChildDocOutputHandler(BaseOutputHandler):
    """
    默认输出策略：将 ProcessorResult 写入飞书子文档，并在原文档末尾插入引用链接；可选发送通知卡片。
    """

    def __init__(self, *, feishu_client: FeishuClient, llm_client: "LLMClient") -> None:
        self._feishu = feishu_client
        self._title_generator = TitleGenerator(llm_client=llm_client)

    async def handle(
        self,
        *,
        ctx: "ProcessContext",
        source_doc: SourceDoc,
        processor_result: ProcessorResult,
        notify_user: bool = True,
    ) -> OutputResult:
        # 智能标题生成：如果原标题包含"未命名"，则调用 AI 生成标题
        title = processor_result.title or f"{source_doc.title} - AI 生成"
        if "未命名" in title:
            logger.info("检测到未命名文档，启动智能标题生成")
            try:
                title = await self._title_generator.generate_title(
                    content_md=processor_result.content_md,
                    mode=ctx.mode,
                    original_doc_title=source_doc.title,
                )
                logger.info("智能生成标题: %s", title)
            except Exception as exc:
                logger.warning("标题生成失败，使用默认标题: %s", exc)
                # title 保持原值（fallback 已在 TitleGenerator 内部处理）
        
        # 添加模式标签（如 [思路扩展]）
        title = self._add_mode_label(title, ctx.mode)
        logger.info("添加标签后的最终标题: %s", title)

        # 1) 知识库优先：如果前端/触发方提供了 wiki_node_token，则走知识库创建子节点
        wiki_node: Dict[str, Any] | None = None
        wiki_node_token = ctx.wiki_node_token
        wiki_space_id = ctx.wiki_space_id
        
        # 云盘场景变量（用于返回结果）
        folder_token: str | None = None
        folder_name: str | None = None
        backlink_success: bool = False
        backlink_error: str | None = None
        
        # 权限添加状态
        permission_granted: bool = False
        permission_errors: list[str] = []

        if wiki_node_token:
            # === 知识库路径 ===
            if not wiki_space_id:
                wiki_node = await self._feishu.get_wiki_node_by_token(node_token=wiki_node_token)
                wiki_space_id = str(wiki_node.get("space_id") or "")
            if not wiki_space_id:
                raise RuntimeError("Missing wiki_space_id (cannot create child node)")

            child_node = await self._feishu.create_wiki_child_doc(
                space_id=wiki_space_id,
                parent_node_token=wiki_node_token,
                title=title,
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
                wiki_node_token,
            )
            
            # 添加用户权限（知识库：edit + container）
            perm_ok, perm_err = await self._grant_permission_safe(
                token=child_node_token,
                file_type="wiki",
                user_id=ctx.user_id,
                perm="edit",
                perm_type="container",
            )
            permission_granted = perm_ok
            if perm_err:
                permission_errors.append(perm_err)

            # 部分场景下新建文档的 docx 接口存在短暂可见性延迟，等待片刻再写内容
            await asyncio.sleep(5.0)

            # 写入内容（写内容始终走 docx obj_token）
            # 追加元数据到文档末尾
            from backend.services.utils.metadata_builder import build_metadata_section
            
            # 构建元数据（包含原始内容）
            metadata = build_metadata_section(
                mode=ctx.mode,
                source_title=source_doc.title,
                source_url=f"https://feishu.cn/wiki/{wiki_node_token}",  # 知识库链接
                original_content=ctx.original_content,
                trigger_source=ctx.trigger_source,
            )
            final_content = processor_result.content_md + metadata
            await self._feishu.write_doc_content(child_doc_token, final_content)
        else:
            # === 云盘路径 ===
            # 飞书官方建议的流程：
            # 1. 在原文档同级目录（或根目录）创建同名文件夹
            # 2. 在新文件夹中创建子文档
            
            # 确定父文件夹 token（None 或空字符串表示根目录）
            parent_folder = source_doc.parent_token or ""
            
            logger.info(
                "云盘场景：准备创建同名文件夹 parent_folder=%s, folder_name=%s",
                parent_folder or "(root)",
                source_doc.title,
            )
            
            # 1) 先查询同级目录下是否已有同名文件夹
            existing_folders = await self._feishu.drive.list_files(
                folder_token=parent_folder,
                page_size=200,
                type_filter="folder",
            )
            new_folder_token: str | None = None
            for item in existing_folders:
                item_name = item.get("name") or item.get("title")
                item_token = item.get("token")
                if item_name == source_doc.title and item_token:
                    new_folder_token = str(item_token)
                    folder_name = item_name  # 记录复用的文件夹名
                    logger.info(
                        "发现同名文件夹已存在，将复用: token=%s, name=%s",
                        new_folder_token,
                        folder_name,
                    )
                    break
            
            # 如未找到同名文件夹，则创建新文件夹
            if not new_folder_token:
                try:
                    new_folder_token = await self._feishu.drive.create_folder(
                        parent_folder_token=parent_folder,
                        name=source_doc.title,
                    )
                    folder_name = source_doc.title  # 记录实际创建的文件夹名
                    logger.info(
                        "成功创建文件夹：%s，现在在其中创建子文档",
                        new_folder_token,
                    )
                except Exception as e:
                    # 检查是否是“文件夹已存在”错误（1062505）——可能是并发场景下其他请求刚创建了同名文件夹
                    error_str = str(e)
                    if "1062505" in error_str or "folder already exists" in error_str.lower():
                        logger.info(
                            "检测到同名文件夹已存在，重新查询以获取现有文件夹 token，name=%s",
                            source_doc.title,
                        )
                        existing_folders = await self._feishu.drive.list_files(
                            folder_token=parent_folder,
                            page_size=200,
                            type_filter="folder",
                        )
                        for item in existing_folders:
                            item_name = item.get("name") or item.get("title")
                            item_token = item.get("token")
                            if item_name == source_doc.title and item_token:
                                new_folder_token = str(item_token)
                                folder_name = item_name
                                logger.info(
                                    "复用现有同名文件夹: token=%s, name=%s",
                                    new_folder_token,
                                    folder_name,
                                )
                                break
                        if not new_folder_token:
                            # 理论上不应发生：返回“已存在”但又查不到；此时向上抛出便于排查
                            raise
                    else:
                        # 其他错误，直接抛出
                        raise
            # 保存文件夹信息供后续返回
            folder_token = new_folder_token
            
            # 添加文件夹权限（云盘：view）
            folder_perm_ok, folder_perm_err = await self._grant_permission_safe(
                token=new_folder_token,
                file_type="folder",
                user_id=ctx.user_id,
                perm="view",
            )
            if folder_perm_err:
                permission_errors.append(folder_perm_err)
            
            # 2) 在新文件夹中创建子文档
            child_doc_token = await self._feishu.drive.create_doc(
                folder_token=new_folder_token,
                title=title,
            )
            child_doc_url = self._build_doc_url(child_doc_token)
            
            # 添加文档权限（云盘：view）
            doc_perm_ok, doc_perm_err = await self._grant_permission_safe(
                token=child_doc_token,
                file_type="docx",
                user_id=ctx.user_id,
                perm="view",
            )
            if doc_perm_err:
                permission_errors.append(doc_perm_err)
            
            # 权限添加状态：两个都成功才算成功
            permission_granted = folder_perm_ok and doc_perm_ok
            
            # 追加元数据到文档末尾
            from backend.services.utils.metadata_builder import build_metadata_section
            
            metadata = build_metadata_section(
                mode=ctx.mode,
                source_title=source_doc.title,
                source_url=self._build_doc_url(source_doc.doc_token),
                original_content=ctx.original_content,
                trigger_source=ctx.trigger_source,
            )
            final_content = processor_result.content_md + metadata
            await self._feishu.write_doc_content(child_doc_token, final_content)

        # 2) 回链到原文档末尾（原文档可为 Wiki 挂载的 docx，仍可用 docx blocks 接口）
        # 注意：回链可能失败（如应用无编辑原文档权限），不影响主流程
        try:
            await self._feishu.append_reference_block(
                source_doc.doc_token, title, child_doc_url
            )
            logger.info("成功在原文档末尾添加回链引用")
            backlink_success = True
        except Exception as e:
            error_msg = str(e)
            backlink_error = error_msg
            logger.warning(
                "回链到原文档失败（应用可能无编辑权限），但主流程已完成: %s",
                error_msg,
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
            metadata={
                "output": "feishu_child_doc",
                "source_is_wiki": bool(wiki_node_token),
                "wiki_node": wiki_node,
                "wiki_node_token": wiki_node_token,
                "wiki_space_id": wiki_space_id,
                # 云盘场景：文件夹信息
                "folder_token": folder_token,
                "folder_url": f"https://feishu.cn/drive/folder/{folder_token}" if folder_token else None,
                "folder_name": folder_name,
                # 回链信息
                "backlink_success": backlink_success,
                "backlink_error": backlink_error,
                "source_doc_token": source_doc.doc_token,
                "source_doc_url": self._build_doc_url(source_doc.doc_token) if not wiki_node_token else f"https://feishu.cn/wiki/{wiki_node_token}",
                # 权限添加状态
                "permission_granted": permission_granted,
                "permission_errors": permission_errors if permission_errors else None,
            },
        )

    def _build_doc_url(self, doc_token: str) -> str:
        return f"https://feishu.cn/docx/{doc_token}"

    def _build_wiki_url(self, node_token: str) -> str:
        return f"https://feishu.cn/wiki/{node_token}"

    def _add_mode_label(self, title: str, mode: str) -> str:
        """
        为标题添加模式标签（前缀方式）
        
        Args:
            title: 原始标题
            mode: 处理模式
            
        Returns:
            添加标签后的标题
        """
        label = MODE_LABELS.get(mode)
        if not label:
            # 未知模式，不添加标签
            return title
        
        # 检查标题是否已经包含标签（避免重复添加）
        if title.startswith(label):
            return title
        
        # 添加标签，标签和标题之间加一个空格
        return f"{label} {title}"
    
    async def _grant_permission_safe(
        self,
        token: str,
        file_type: str,
        user_id: str,
        perm: str,
        perm_type: str | None = None,
    ) -> tuple[bool, str | None]:
        """
        安全添加权限（失败不阻断主流程）
        
        参数:
            - token: 文件/文件夹/wiki节点 token
            - file_type: 资源类型 ("file", "wiki")
            - user_id: 用户 open_id
            - perm: 权限级别 ("view", "edit")
            - perm_type: wiki 权限范围 ("container", "single_page")
        
        返回: (是否成功, 错误信息)
        """
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
                "权限添加成功: token=%s, type=%s, user=%s, perm=%s",
                token,
                file_type,
                user_id[:10] + "..." if len(user_id) > 10 else user_id,
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


