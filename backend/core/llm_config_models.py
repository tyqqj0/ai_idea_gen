from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    """
    单个 Provider 的配置。
    """

    type: str = Field(..., description="协议类型，如 google / openai-compatible / custom")
    base_url: str
    model: str
    api_key_env: str


class ChainStepConfig(BaseModel):
    """
    fallback 链中的一步。
    """

    provider: str
    timeout_s: Optional[int] = None


class GlobalConfig(BaseModel):
    max_retries_per_provider: int = 1
    overall_timeout_s: int = 60


class LLMConfig(BaseModel):
    """
    从 llm_config.yml 解析出来的整体配置模型。
    """

    providers: Dict[str, ProviderConfig]
    chains: Dict[str, List[ChainStepConfig]]
    global_: GlobalConfig = Field(
        default_factory=GlobalConfig, alias="global", validation_alias="global"
    )

    class Config:
        populate_by_name = True



