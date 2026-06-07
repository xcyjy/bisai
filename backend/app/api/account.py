"""账户统计：用于登录后 Dashboard 展示。"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlmodel import Session, select

from ..core.config import settings
from ..core.deps import get_current_user
from ..db.models import Project, UsageLog, User
from ..db.session import get_session

router = APIRouter(prefix="/api/me", tags=["account"])


def _as_utc(dt):
    """SQLite 读回的 datetime 不带时区，统一补成 UTC 以便比较。"""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@router.get("/stats")
def my_stats(
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    project_count = session.exec(
        select(func.count()).select_from(Project).where(Project.user_id == current.id)
    ).one()

    # 本月 AI 使用次数（按扣分次数统计）
    month_start = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    ai_used_month = session.exec(
        select(func.coalesce(func.sum(UsageLog.credits_spent), 0))
        .where(UsageLog.user_id == current.id)
        .where(UsageLog.created_at >= month_start)
    ).one()

    expires = _as_utc(current.plan_expires_at)
    is_member = bool(
        current.plan == "pro"
        and expires
        and expires > datetime.now(timezone.utc)
    )
    return {
        "plan": current.plan,
        "is_member": is_member,
        "plan_expires_at": current.plan_expires_at.isoformat() if current.plan_expires_at else None,
        "credits": current.credits,
        "project_count": project_count,
        "ai_used_this_month": ai_used_month,
        "ai_available": settings.ai_available,
    }
