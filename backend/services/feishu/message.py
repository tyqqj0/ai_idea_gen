"""
飞书消息 API 客户端
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.services.feishu.base import FeishuBaseClient

logger = logging.getLogger(__name__)


class FeishuMessageClient:
    """
    飞书消息 API 封装
    
    提供消息通知相关操作：
    - 发送卡片消息
    """
    
    def __init__(self, base: "FeishuBaseClient") -> None:
        self._base = base
    
    async def send_card(
        self,
        *,
        user_id: str,
        card_content: Dict[str, Any],
        receive_id_type: str = "open_id",
    ) -> None:
        """
        发送飞书卡片消息
        
        API: POST /im/v1/messages
        
        Args:
            user_id: 接收者 ID
            card_content: 卡片内容（dict 格式）
            receive_id_type: ID 类型（open_id, user_id, union_id 等）
        """
        payload = {
            "receive_id": user_id,
            "msg_type": "interactive",
            "content": json.dumps(card_content, ensure_ascii=False),
        }
        await self._base.request(
            "POST",
            "/open-apis/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            json=payload,
        )
        logger.info(
            "send_card succeeded: user_id=%s, receive_id_type=%s",
            user_id,
            receive_id_type,
        )
