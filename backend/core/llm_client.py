from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from backend.core.llm_config_models import ChainStepConfig, LLMConfig
from backend.core.providers import LLMProviderError, NonRetryableLLMError, build_provider

logger = logging.getLogger(__name__)


class FallbackExhaustedError(Exception):
    """
    所有 provider 都尝试失败。
    """


class LLMClient:
    """
    Layer 1: 与 LLM 的基础通信 + Fallback 机制。

    - 从 llm_config.yml 读取 providers / chains 配置。
    - 对外按「链名」调用，内部顺序尝试链上的多个 provider。
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        self._config = self._load_config(config_path)
        # 预构建 provider 实例池
        self._providers = {
            name: build_provider(name, cfg)
            for name, cfg in self._config.providers.items()
        }

    def _load_config(self, config_path: Optional[str]) -> LLMConfig:
        path = Path(config_path or "llm_config.yml")
        if not path.exists():
            raise RuntimeError(f"llm_config.yml not found at {path}")

        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return LLMConfig.model_validate(raw)

    async def chat_completion(
        self,
        *,
        chain: str,
        messages: List[Dict[str, Any]],
        **options: Any,
    ) -> str:
        """
        对外统一接口：按 chain 名称选择 fallback 链，返回 LLM 文本回复。
        """
        if chain not in self._config.chains:
            raise ValueError(f"Unknown LLM chain: {chain}")

        steps: List[ChainStepConfig] = self._config.chains[chain]

        last_error: Optional[Exception] = None

        for step in steps:
            provider_name = step.provider
            provider = self._providers.get(provider_name)
            if provider is None:
                logger.error("Provider %s not found in config.providers", provider_name)
                continue

            # 单 provider 超时配置
            timeout_s = step.timeout_s or self._config.global_.overall_timeout_s

            try:
                logger.info("Calling LLM provider=%s, chain=%s", provider_name, chain)

                result = await asyncio.wait_for(
                    provider.chat(messages, **options), timeout=timeout_s
                )
                logger.info(
                    "LLM provider=%s succeeded for chain=%s", provider_name, chain
                )
                return result

            except NonRetryableLLMError as exc:
                # 不可重试错误，直接抛出
                logger.error(
                    "Non-retryable error from provider=%s, chain=%s: %s",
                    provider_name,
                    chain,
                    exc,
                )
                raise
            except (LLMProviderError, asyncio.TimeoutError) as exc:
                # 可重试 / 可 fallback 的错误，记录后尝试下一个
                logger.warning(
                    "Provider=%s failed for chain=%s, will try next if any: %s",
                    provider_name,
                    chain,
                    exc,
                )
                last_error = exc
                continue

        # 所有 provider 都失败
        raise FallbackExhaustedError(
            f"All providers failed for chain={chain}, last_error={last_error}"
        )



