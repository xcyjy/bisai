"""数据库模型（SQLModel）。

对应文档《05_C端产品化方案》第四节，Phase 1 先落地三张核心表：
users / projects / screenplays。jobs / usage_logs 待 Phase 2 异步化时再加。

JSON 字段用 SQLAlchemy 通用 JSON 类型，SQLite 与 PostgreSQL 均可用。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    nickname: str = ""
    plan: str = Field(default="free")  # free | pro | admin
    created_at: datetime = Field(default_factory=_now)


class Project(SQLModel, table=True):
    """一篇小说 = 一个作品。"""
    __tablename__ = "projects"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    title: str = "未命名剧本"
    original_work: str = ""
    author: str = ""
    source_text: str = ""  # 原文（本地直接入库；量大时改存对象存储）
    char_count: int = 0
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Screenplay(SQLModel, table=True):
    """剧本版本（支持编辑历史 / 回滚）。"""
    __tablename__ = "screenplays"

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id", index=True)
    version: int = 1
    doc: dict = Field(default_factory=dict, sa_column=Column(JSON))
    engine: str = ""
    is_valid: bool = True
    created_at: datetime = Field(default_factory=_now)
