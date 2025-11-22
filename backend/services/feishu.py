from typing import Any, Dict

import httpx

from backend.config import get_settings


class FeishuClient:
    """
    飞书 API 封装骨架：负责 Token 获取、文档元数据与内容的读写等。
    这里先只定义接口，具体实现后续补全。
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = httpx.AsyncClient(base_url="https://open.feishu.cn")

    async def get_tenant_access_token(self) -> str:
        """
        获取 tenant_access_token。
        """
        raise NotImplementedError

    async def get_doc_meta(self, doc_token: str) -> Dict[str, Any]:
        """
        获取文档元数据（包括 parent_token）。
        """
        raise NotImplementedError

    async def get_doc_content(self, doc_token: str) -> str:
        """
        获取文档纯文本内容。
        """
        raise NotImplementedError

    async def create_child_doc(self, folder_token: str, title: str) -> str:
        """
        在指定目录下创建子文档，返回子文档 token。
        """
        raise NotImplementedError

    async def write_doc_content(self, doc_token: str, content_md: str) -> None:
        """
        将 Markdown 内容写入文档（内部会转换为飞书 Blocks）。
        """
        raise NotImplementedError



