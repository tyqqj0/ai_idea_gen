from __future__ import annotations

from typing import Dict

from pydantic import BaseModel, Field


class WorkflowItemConfig(BaseModel):
    """
    单个处理模式（mode）的组合配置。
    """

    processor: str = Field(..., description="processor 注册名，如 idea_expander/research")
    chain: str = Field(..., description="LLM chain 名称，对应 llm_config.yml 的 chains")
    output: str = Field(..., description="output 注册名，如 feishu_child_doc")
    notify_user: bool = Field(default=True, description="是否通知触发用户")


class WorkflowConfigFile(BaseModel):
    """
    从 workflow_config.yml 解析出的整体配置模型。
    """

    workflows: Dict[str, WorkflowItemConfig]
