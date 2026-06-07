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
    plan: str = Field(default="free")  # free | pro
    plan_expires_at: Optional[datetime] = None  # 会员到期时间（None=非会员）
    credits: int = Field(default=0)  # 积分余额：1 次 AI 转换扣 1 分
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


class Job(SQLModel, table=True):
    """异步转换任务：一部小说的转换可能调用多次大模型，耗时较长，走后台任务。"""
    __tablename__ = "jobs"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    project_id: int = Field(foreign_key="projects.id", index=True)
    engine: str = ""            # 期望引擎：offline | ai
    status: str = "queued"      # queued | running | done | failed
    progress: int = 0           # 已完成章节数
    total: int = 0              # 总章节数
    error: str = ""
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class UsageLog(SQLModel, table=True):
    """每次转换的用量与成本（内部计费/审计用）。"""
    __tablename__ = "usage_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    project_id: Optional[int] = Field(default=None, foreign_key="projects.id")
    engine: str = ""
    in_tokens: int = 0
    out_tokens: int = 0
    cost_usd: float = 0.0
    credits_spent: int = 0
    created_at: datetime = Field(default_factory=_now)


class Order(SQLModel, table=True):
    """订单：购买会员或积分包。本地用 mock 支付，云上可接微信/支付宝回调。"""
    __tablename__ = "orders"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    sku: str = ""               # 套餐/积分包代码，见 core/plans.py
    title: str = ""             # 下单时的商品名快照
    amount_cny: float = 0.0     # 金额（元）
    grant_plan: str = ""        # 购买会员时授予的 plan
    grant_days: int = 0         # 会员天数
    grant_credits: int = 0      # 赠送/购买的积分
    status: str = "pending"     # pending | paid | failed
    created_at: datetime = Field(default_factory=_now)
    paid_at: Optional[datetime] = None
