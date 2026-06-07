"""全局配置（pydantic-settings 读环境变量 / .env）。

本地默认用 SQLite，零配置即可起；部署时通过环境变量 DATABASE_URL
切到 PostgreSQL（见 docker-compose.cloud.yml）。
"""
from __future__ import annotations

from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---- 数据库 ----
    # 本地默认 SQLite 文件；线上设为 postgresql+psycopg://user:pwd@host:5432/db
    database_url: str = "sqlite:///./local.db"

    # ---- JWT ----
    # ⚠️ 生产务必通过环境变量覆盖为随机长字符串
    jwt_secret: str = "dev-secret-change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 天

    # ---- CORS（逗号分隔的允许来源；本地默认放开 Vite）----
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ---- 大模型（AI 精修引擎）----
    # 本地不配则 AI 引擎不可用，前端仍可用免费离线引擎；云上配置后自动启用。
    anthropic_api_key: str = ""
    # 自定义 API 入口（兼容 Anthropic 协议的中转站）；留空则用官方 api.anthropic.com。
    anthropic_base_url: str = ""
    # 默认用最强的 Opus；高频量产可改 claude-sonnet-4-6 / claude-haiku-4-5 省钱。
    script_model: str = "claude-opus-4-8"
    # 「量活」专用快模型：人物抽取、自检等大量并行调用走它，快且省（智能模型路由）。
    fast_model: str = "claude-haiku-4-5-20251001"
    # 强制离线（即使配了 key，调试时可关掉 AI）
    force_offline: bool = False

    # ---- 注册赠送的初始积分（1 次 AI 转换 = 1 积分；离线转换不扣分）----
    free_signup_credits: int = 3

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def ai_available(self) -> bool:
        return bool(self.anthropic_api_key) and not self.force_offline


settings = Settings()
