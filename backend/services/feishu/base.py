"""
飞书 API 基础客户端

提供 Token 管理和 HTTP 请求封装，供所有子客户端共享
"""
from __future__ import annotations

import asyncio
import logging
import time
from json import JSONDecodeError
from typing import Any, Dict, Optional

import httpx

from backend.config import get_settings
from backend.services.feishu.errors import FeishuAPIError

logger = logging.getLogger(__name__)


class FeishuBaseClient:
    """
    飞书 API 基础客户端
    
    负责：
    - Tenant Access Token 获取与缓存
    - HTTP 请求封装（带认证、日志、错误处理）
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

            logger.info(
                "Requesting tenant_access_token with app_id=%s (secret masked)",
                self.settings.FEISHU_APP_ID,
            )
            resp = await self._client.post(
                "/open-apis/auth/v3/tenant_access_token/internal", json=payload
            )
            data = resp.json()
            if resp.status_code != 200 or data.get("code") != 0:
                logger.error(
                    "Failed to get tenant_access_token: app_id=%s, response=%s",
                    self.settings.FEISHU_APP_ID,
                    data,
                )
                raise FeishuAPIError(
                    f"Failed to get tenant_access_token: {data}",
                    status_code=resp.status_code,
                )

            token = data["tenant_access_token"]
            expire = data.get("expire", 3600)
            self._tenant_token = token
            self._tenant_token_expire_at = time.time() + expire
            # Token 打码显示（前4后4）
            masked_token = f"{token[:4]}...{token[-4:]}" if len(token) > 8 else "***"
            logger.info(
                "Refreshed tenant_access_token: app_id=%s, token=%s, expire_in=%ss",
                self.settings.FEISHU_APP_ID,
                masked_token,
                expire,
            )
            return token

    async def exchange_code_for_user_token(self, code: str) -> Dict[str, Any]:
        """
        用云文档小组件登录返回的 code 换取用户信息
        
        【重要】云文档小组件必须使用专用接口，不能使用 OIDC 标准接口
        调用飞书小程序接口：
        POST /open-apis/mina/v2/tokenLoginValidate
        
        Args:
            code: 前端通过 DocMiniApp.Service.User.login() 获取的临时授权码
        
        Returns:
            dict: 包含 open_id, employee_id, access_token 等用户信息
            {
                "open_id": "ou_xxx",           # 用户 Open ID（必有）
                "employee_id": "xxx",          # 用户 User ID（需权限）
                "session_key": "xxx",          # 会话密钥
                "tenant_key": "xxx",           # 企业标识
                "access_token": "u-xxx",       # user_access_token
                "expires_in": 1234567890,      # 过期时间戳
                "refresh_token": "ur-xxx"      # 刷新令牌
            }
        
        Raises:
            FeishuAPIError: 认证失败时抛出
                - 10202: app_access_token 无效
                - 10213: code 与 app 不匹配，或 code 重复使用/过期
                - 10226: code 不合法
                - 10228: 用户对应用无可见性
        """
        # 1. 先获取 app_access_token（复用已有的 tenant_access_token 获取逻辑）
        app_token = await self.get_tenant_access_token()
        masked_app_token = f"{app_token[:4]}...{app_token[-4:]}" if len(app_token) > 8 else "***"
        
        logger.info(
            "Exchanging code for user token (app_id=%s, code=%s..., app_token=%s)",
            self.settings.FEISHU_APP_ID,
            code[:8] if len(code) > 8 else "***",
            masked_app_token,
        )

        # 2. 调用小程序专用接口
        payload = {"code": code}
        headers = {"Authorization": f"Bearer {app_token}"}

        try:
            resp = await self._client.post(
                "/open-apis/mina/v2/tokenLoginValidate",
                json=payload,
                headers=headers,
            )
            data = resp.json()

            # 检查响应
            if resp.status_code != 200 or data.get("code") != 0:
                error_code = data.get("code", -1)
                error_msg = data.get("msg", "Unknown error")
                
                # 根据错误码提供更详细的错误信息
                error_hints = {
                    10202: "app_access_token 无效或已过期",
                    10213: "code 与应用不匹配，或 code 已被使用/过期（code 仅能使用一次）",
                    10226: "code 不合法或已过期",
                    10228: "用户对该应用无可见性",
                }
                hint = error_hints.get(error_code, "")
                detailed_msg = f"{error_msg} (错误码: {error_code})" + (f" - {hint}" if hint else "")
                
                logger.error(
                    "Failed to exchange code: status=%d, code=%d, msg=%s, hint=%s",
                    resp.status_code,
                    error_code,
                    error_msg,
                    hint,
                )
                raise FeishuAPIError(
                    f"Authentication failed: {detailed_msg}",
                    status_code=resp.status_code,
                )

            user_data = data.get("data", {})
            open_id = user_data.get("open_id", "")
            
            # 打码日志
            masked_open_id = f"{open_id[:8]}..." if len(open_id) > 8 else "***"
            logger.info(
                "Successfully exchanged code for user token: open_id=%s",
                masked_open_id,
            )

            return user_data

        except httpx.HTTPError as e:
            logger.error("HTTP error during authentication: %s", e)
            raise FeishuAPIError(
                f"Network error during authentication: {e}",
                status_code=502,
            )
        except JSONDecodeError as e:
            logger.error("Failed to parse authentication response: %s", e)
            raise FeishuAPIError(
                "Invalid response from authentication service",
                status_code=502,
            )

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        发送 HTTP 请求到飞书 API
        
        自动处理：
        - Token 注入
        - 请求/响应日志
        - 错误处理
        """
        token = await self.get_tenant_access_token()
        # Token 打码（用于日志）
        masked_token = f"{token[:4]}...{token[-4:]}" if len(token) > 8 else "***"
        headers = {"Authorization": f"Bearer {token}"}
        logger.debug(
            "Using tenant_access_token=%s (app_id=%s) for %s %s",
            masked_token,
            self.settings.FEISHU_APP_ID,
            method,
            path,
        )

        # 调试日志：打印实际发送的请求信息
        full_url = f"{self.FEISHU_HOST}{path}"
        if params:
            # 简单拼接 query string（实际 httpx 会处理）
            query_str = "&".join(f"{k}={v}" for k, v in params.items())
            full_url = f"{full_url}?{query_str}"
        
        masked_headers = {"Authorization": masked_token}
        
        # 构造精简版请求体摘要，避免在日志中输出超长内容
        body_summary: Dict[str, Any] = {}
        if json is not None:
            if isinstance(json, dict):
                if "content" in json and isinstance(json["content"], str):
                    body_summary["content_len"] = len(json["content"])
                if "children" in json and isinstance(json["children"], list):
                    body_summary["children_count"] = len(json["children"])
                if "descendants" in json and isinstance(json["descendants"], list):
                    body_summary["descendants_count"] = len(json["descendants"])
                # 记录其余关键字段的键名，避免输出大段内容
                other_keys = [
                    k for k in json.keys() if k not in ("content", "children", "descendants")
                ]
                if other_keys:
                    body_summary["keys"] = other_keys
            else:
                body_summary["json_type"] = str(type(json))
        elif params is not None:
            body_summary["params"] = params

        logger.info(
            "Feishu API Request: %s %s\n  Headers: %s\n  BodySummary: %s",
            method,
            full_url,
            masked_headers,
            body_summary or None,
        )

        resp = await self._client.request(
            method,
            path,
            params=params,
            json=json,
            headers=headers,
        )
        
        # 调试日志：打印响应状态和关键字段
        logger.info(
            "Feishu API Response: %s %s -> status=%s",
            method,
            path,
            resp.status_code,
        )
        try:
            data = resp.json()
        except JSONDecodeError:
            # 针对非 JSON 响应（如 404 page not found, 502 Bad Gateway 等）做容错处理
            logger.error(
                "Feishu API non-JSON response: %s %s -> status=%s, body=%s",
                method,
                path,
                resp.status_code,
                resp.text[:200],
            )
            raise FeishuAPIError(
                f"Feishu API returned non-JSON response. Status: {resp.status_code}, Body: {resp.text[:200]}",
                status_code=resp.status_code,
            )

        # 调试日志：打印响应体关键字段
        resp_code = data.get("code")
        resp_msg = data.get("msg")
        logger.info(
            "Feishu API Response body: %s %s -> code=%s, msg=%s",
            method,
            path,
            resp_code,
            resp_msg,
        )

        if resp.status_code != 200 or resp_code != 0:
            # 错误时打印完整响应（便于调试）
            logger.error(
                "Feishu API error: %s %s -> status=%s, code=%s, msg=%s, full_data=%s",
                method,
                path,
                resp.status_code,
                resp_code,
                resp_msg,
                data,
            )
            raise FeishuAPIError(
                f"Feishu API error path={path}, status={resp.status_code}, data={data}",
                status_code=resp.status_code,
            )
        return data
