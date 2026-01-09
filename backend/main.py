import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from dotenv import load_dotenv

load_dotenv()

# 配置日志级别（确保能看到 INFO 级别的调试日志）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

from backend.api.routes import router as api_router


def create_app() -> FastAPI:
    """
    创建 FastAPI 应用，并挂载路由与全局依赖。
    """
    app = FastAPI(
        title="AI Idea Generator Backend",
        version="0.1.0",
    )

    # 配置 CORS - 允许飞书小组件等前端跨域访问
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境可限制为特定域名
        allow_credentials=True,
        allow_methods=["*"],  # 允许所有 HTTP 方法（GET, POST, OPTIONS 等）
        allow_headers=["*"],  # 允许所有请求头
    )

    # 预加载配置，启动时如果 .env 有问题可以尽早暴露
    get_settings()

    # 统一挂载 API 路由
    app.include_router(api_router, prefix="/api")

    @app.get("/health", summary="健康检查")
    async def health_check():
        return {"status": "ok"}

    return app


app = create_app()



