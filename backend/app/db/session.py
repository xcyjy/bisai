"""数据库引擎与会话。"""
from __future__ import annotations

from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine

from ..core.config import settings

# SQLite 需要 check_same_thread=False 才能在 FastAPI 多线程下使用
_connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(settings.database_url, echo=False, connect_args=_connect_args)


def init_db() -> None:
    """建表（首次启动用）。生产环境建议改用 Alembic 迁移。"""
    # 确保模型被导入注册到 metadata
    from . import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
