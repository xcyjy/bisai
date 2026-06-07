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

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
