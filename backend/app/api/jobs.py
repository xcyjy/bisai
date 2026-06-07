"""异步任务状态查询（前端轮询转换进度）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from ..core.deps import get_current_user
from ..db.models import Job, User
from ..db.session import get_session

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}")
def get_job(
    job_id: int,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    job = session.get(Job, job_id)
    if job is None or job.user_id != current.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    return {
        "id": job.id,
        "project_id": job.project_id,
        "engine": job.engine,
        "status": job.status,      # queued | running | done | failed
        "progress": job.progress,
        "total": job.total,
        "error": job.error,
    }
