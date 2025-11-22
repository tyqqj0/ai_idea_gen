from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    全局配置，从 .env 中读取。
    """

    # 飞书应用配置
    FEISHU_APP_ID: str
    FEISHU_APP_SECRET: str

    # 通用业务配置
    PROCESS_TIMEOUT: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """
    获取全局单例配置实例。
    """
    return Settings()



