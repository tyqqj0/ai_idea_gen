from __future__ import annotations

from typing import Callable, Dict

from backend.core.llm_client import LLMClient
from backend.services.feishu import FeishuClient
from backend.services.outputs.base import BaseOutputHandler
from backend.services.outputs.feishu_child_doc import FeishuChildDocOutputHandler
from backend.config import get_settings
from backend.services.outputs.webhook import WebhookOutputHandler


OutputFactory = Callable[[FeishuClient, LLMClient], BaseOutputHandler]


def _make_feishu_child_doc_output(feishu: FeishuClient, llm: LLMClient) -> BaseOutputHandler:
    # llm 当前未使用，但保留参数以统一工厂签名，便于未来扩展
    _ = llm
    return FeishuChildDocOutputHandler(feishu_client=feishu)


def _make_webhook_output(feishu: FeishuClient, llm: LLMClient) -> BaseOutputHandler:
    _ = feishu
    _ = llm
    settings = get_settings()
    if not settings.WEBHOOK_OUTPUT_URL:
        raise ValueError("WEBHOOK_OUTPUT_URL is not set")
    return WebhookOutputHandler(
        webhook_url=settings.WEBHOOK_OUTPUT_URL,
        timeout_s=settings.WEBHOOK_OUTPUT_TIMEOUT_S,
    )


OUTPUT_REGISTRY: Dict[str, OutputFactory] = {
    "feishu_child_doc": _make_feishu_child_doc_output,
    "webhook": _make_webhook_output,
}


def get_output_factory(name: str) -> OutputFactory:
    try:
        return OUTPUT_REGISTRY[name]
    except KeyError as exc:  # noqa: B904
        raise ValueError(f"Unknown output handler: {name}") from exc


