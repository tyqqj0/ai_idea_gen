from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

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

        # 这里不要用过小的 httpx 超时（否则会抢在上层链路超时之前触发 ReadTimeout）。
        # 统一由上层 LLMClient 的 asyncio.wait_for(step.timeout_s/overall_timeout_s) 控制超时更清晰。
        self._client = httpx.AsyncClient(base_url=config.base_url, timeout=120.0)
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
            raise LLMProviderError(
                f"Network error for provider {self.name}: {type(exc).__name__} {exc!r}"
            ) from exc

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


class GeminiProvider(LLMProvider):
    """
    调用 Google Gemini GenerateContent 接口的 Provider。
    """

    async def chat(self, messages: List[Dict[str, Any]], **kwargs: Any) -> str:
        payload = self._build_payload(messages, **kwargs)

        try:
            resp = await self._client.post(
                f"/models/{self.config.model}:generateContent",
                params={"key": self._api_key},
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                },
            )
        except httpx.RequestError as exc:
            raise LLMProviderError(
                f"Network error for Gemini provider {self.name}: {type(exc).__name__} {exc!r}"
            ) from exc

        if resp.status_code >= 500:
            raise LLMProviderError(
                f"Server error from Gemini provider {self.name}: {resp.status_code} {resp.text}"
            )

        if resp.status_code == 429:
            raise LLMProviderError(
                f"Rate limited by Gemini provider {self.name}: {resp.status_code} {resp.text}"
            )

        if resp.status_code >= 400:
            # Gemini 大部分 4xx 代表请求问题，视为不可重试
            raise NonRetryableLLMError(
                f"Client error from Gemini provider {self.name}: {resp.status_code} {resp.text}"
            )

        data = resp.json()
        try:
            candidates = data["candidates"]
            for candidate in candidates:
                content = candidate.get("content", {})
                parts = content.get("parts", [])
                text = "".join(part.get("text", "") for part in parts if "text" in part).strip()
                if text:
                    return text
        except (KeyError, TypeError) as exc:
            raise LLMProviderError(
                f"Invalid response format from Gemini provider {self.name}: {data}"
            ) from exc

        raise LLMProviderError(
            f"Gemini provider {self.name} returned empty response: {data}"
        )

    def _build_payload(
        self, messages: List[Dict[str, Any]], **kwargs: Any
    ) -> Dict[str, Any]:
        system_instruction: Optional[str] = None
        contents: List[Dict[str, Any]] = []

        for message in messages:
            role = message.get("role")
            content = message.get("content")
            if not content:
                continue

            if role == "system":
                system_instruction = (
                    f"{system_instruction}\n\n{content}"
                    if system_instruction
                    else str(content)
                )
                continue

            contents.append(
                {
                    "role": "user" if role != "assistant" else "model",
                    "parts": [{"text": str(content)}],
                }
            )

        payload: Dict[str, Any] = {"contents": contents}

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}],
            }

        generation_config: Dict[str, Any] = {}
        for key in ("temperature", "top_p", "top_k", "max_output_tokens"):
            if key in kwargs and kwargs[key] is not None:
                generation_config[key] = kwargs[key]

        if generation_config:
            payload["generationConfig"] = generation_config

        return payload


def build_provider(name: str, cfg: ProviderConfig) -> LLMProvider:
    """
    工厂方法：根据 type 创建不同的 Provider 实例。
    目前先支持 openai-compatible，其它类型后续按需实现。
    """
    if cfg.type == "openai-compatible":
        return OpenAICompatibleProvider(name, cfg)
    if cfg.type == "gemini":
        return GeminiProvider(name, cfg)

    # 预留其它协议类型
    raise NonRetryableLLMError(f"Unsupported provider type={cfg.type} for {name}")



