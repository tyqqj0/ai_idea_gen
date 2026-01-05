"""
飞书 API 异常定义
"""
from typing import Optional


class FeishuAPIError(Exception):
    """
    统一的飞书 API 异常。
    """

    def __init__(self, message: str, *, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
