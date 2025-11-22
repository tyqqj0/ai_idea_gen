from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List

import httpx

from backend.core.llm_config_models import ProviderConfig


class LLMProviderError(Exception):
    """
    Provider 层统一异常基类。
    """


class NonRetryableLLMError(LLMProviderError):
    """
    不应该触发 fallback 的错误（例如用户输入不合法）。
    """


class LLMProvider(ABC):
    """
    Provider 抽象基类。
    """

    def __init__(self, name: str, config: ProviderConfig) -> None:
        self.name = name
        self.config = config

        api_key = os.getenv(config.api_key_env)
        if not api_key:
            raise NonRetryableLLMError(
                f"Missing API key for provider {name}, env={config.api_key_env}"
            )

        # 这里先简单用一个 client，后续可以加连接池参数
        self._client = httpx.AsyncClient(base_url=config.base_url, timeout=30.0)
        self._api_key = api_key

    @abstractmethod
    async def chat(self, messages: List[Dict[str, Any]], **kwargs: Any) -> str:
        """
        子类实现具体协议。
        """
        ...


class OpenAICompatibleProvider(LLMProvider):
    """
    兼容 OpenAI Chat Completions 协议的 Provider。
    可用于 OpenAI、本地兼容服务等。
    """

    async def chat(self, messages: List[Dict[str, Any]], **kwargs: Any) -> str:
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
        }
        payload.update(kwargs)

        try:
            resp = await self._client.post(
                "/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                },
            )
        except httpx.RequestError as exc:
            # 网络级错误，交给上层 fallback
            raise LLMProviderError(f"Network error for provider {self.name}: {exc}") from exc

        if resp.status_code >= 500:
            # 服务器错误，允许 fallback
            raise LLMProviderError(
                f"Server error from provider {self.name}: {resp.status_code} {resp.text}"
            )

        if resp.status_code == 429:
            # 限流，也允许 fallback
            raise LLMProviderError(
                f"Rate limited by provider {self.name}: {resp.status_code} {resp.text}"
            )

        if resp.status_code >= 400:
            # 其它 4xx 视为不可重试（大概率是请求问题）
            raise NonRetryableLLMError(
                f"Client error from provider {self.name}: {resp.status_code} {resp.text}"
            )

        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except Exception as exc:  # noqa: BLE001
            raise LLMProviderError(
                f"Invalid response format from provider {self.name}: {data}"
            ) from exc


def build_provider(name: str, cfg: ProviderConfig) -> LLMProvider:
    """
    工厂方法：根据 type 创建不同的 Provider 实例。
    目前先支持 openai-compatible，其它类型后续按需实现。
    """
    if cfg.type == "openai-compatible":
        return OpenAICompatibleProvider(name, cfg)

    # 预留其它协议类型
    raise NonRetryableLLMError(f"Unsupported provider type={cfg.type} for {name}")



