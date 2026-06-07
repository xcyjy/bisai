"""作品接口：转换（异步任务）/ 列表 / 详情 / 保存编辑 / 删除。

所有接口需登录，且按 user_id 强隔离（越权访问返回 404）。
转换走后台任务（Job）：免费"快速版"用离线规则；"AI 精修版"调 Claude，扣 1 积分。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from ..core.billing import cost_usd
from ..core.config import settings
from ..core.deps import get_current_user
from ..db.models import Job, Project, Screenplay, UsageLog, User
from ..db.session import engine, get_session
from ..exporter import to_yaml
from ..pipeline import convert_novel
from ..schema import validate_screenplay

router = APIRouter(prefix="/api/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    text: str
    title: str = "未命名剧本"
    original_work: str = ""
    author: str = ""
    engine: str = "offline"  # offline=免费快速版 | ai=AI 精修版（扣 1 积分）


class SaveScreenplayRequest(BaseModel):
    screenplay: Dict[str, Any]


def _own_project(project_id: int, user: User, session: Session) -> Project:
    proj = session.get(Project, project_id)
    if proj is None or proj.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "作品不存在")
    return proj


def _latest_screenplay(project_id: int, session: Session) -> Screenplay | None:
    return session.exec(
        select(Screenplay)
        .where(Screenplay.project_id == project_id)
        .order_by(Screenplay.version.desc())
    ).first()


def _latest_job(project_id: int, session: Session) -> Job | None:
    return session.exec(
        select(Job)
        .where(Job.project_id == project_id)
        .order_by(Job.id.desc())
    ).first()


# =========================================================
# 后台转换任务
# =========================================================

def run_conversion_job(job_id: int) -> None:
    """在后台线程中执行：自带独立 DB 会话。"""
    with Session(engine) as session:
        job = session.get(Job, job_id)
        if job is None:
            return
        proj = session.get(Project, job.project_id)
        user = session.get(User, job.user_id)
        if proj is None or user is None:
            job.status = "failed"
            job.error = "作品或用户不存在"
            session.add(job)
            session.commit()
            return

        use_ai = job.engine == "ai"
        job.status = "running"
        job.updated_at = datetime.now(timezone.utc)
        session.add(job)
        session.commit()

        def on_progress(done: int, total: int) -> None:
            job.progress = done
            job.total = total
            job.updated_at = datetime.now(timezone.utc)
            session.add(job)
            session.commit()

        try:
            result = convert_novel(
                text=proj.source_text,
                title=proj.title,
                original_work=proj.original_work,
                author=proj.author,
                use_ai=use_ai,
                progress=on_progress,
            )
            doc = result["screenplay"]
            stats = result["stats"]

            sp = Screenplay(
                project_id=proj.id, version=1, doc=doc,
                engine=stats["engine"], is_valid=stats["valid"],
            )
            session.add(sp)

            # 计费：仅 AI 引擎且真的调用了大模型时扣 1 积分并记账
            spent = 0
            if use_ai and stats["engine"].startswith("claude"):
                spent = 1
                user.credits = max(0, user.credits - spent)
                session.add(user)
            session.add(UsageLog(
                user_id=user.id, project_id=proj.id, engine=stats["engine"],
                in_tokens=stats.get("in_tokens", 0), out_tokens=stats.get("out_tokens", 0),
                cost_usd=cost_usd(settings.script_model, stats.get("in_tokens", 0),
                                  stats.get("out_tokens", 0)) if spent else 0.0,
                credits_spent=spent,
            ))

            proj.updated_at = datetime.now(timezone.utc)
            session.add(proj)
            job.status = "done"
            job.updated_at = datetime.now(timezone.utc)
            session.add(job)
            session.commit()
        except Exception as e:  # noqa: BLE001
            job.status = "failed"
            job.error = str(e)[:500]
            job.updated_at = datetime.now(timezone.utc)
            session.add(job)
            session.commit()


# =========================================================
# 接口
# =========================================================

@router.get("")
def list_projects(
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    projs = session.exec(
        select(Project)
        .where(Project.user_id == current.id)
        .order_by(Project.updated_at.desc())
    ).all()
    out = []
    for p in projs:
        sp = _latest_screenplay(p.id, session)
        job = _latest_job(p.id, session)
        if sp:
            st = "ready"
        elif job and job.status == "failed":
            st = "failed"
        elif job and job.status in ("queued", "running"):
            st = "converting"
        else:
            st = "empty"
        out.append({
            "id": p.id,
            "title": p.title,
            "author": p.author,
            "char_count": p.char_count,
            "scenes": len(sp.doc.get("scenes", [])) if sp else 0,
            "status": st,
            "updated_at": p.updated_at.isoformat(),
        })
    return out


@router.post("")
def create_project(
    req: CreateProjectRequest,
    background: BackgroundTasks,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if not req.text or len(req.text.strip()) < 50:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "小说文本太短，请提供至少 3 个章节。")

    # AI 引擎门禁
    if req.engine == "ai":
        if not settings.ai_available:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "AI 精修引擎暂未开通（管理员未配置密钥）。请先用免费快速版。")
        if current.credits < 1:
            raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, "积分不足，请升级会员或购买积分包。")

    proj = Project(
        user_id=current.id,
        title=req.title,
        original_work=req.original_work,
        author=req.author,
        source_text=req.text,
        char_count=len(req.text),
    )
    session.add(proj)
    session.commit()
    session.refresh(proj)

    job = Job(user_id=current.id, project_id=proj.id, engine=req.engine, status="queued")
    session.add(job)
    session.commit()
    session.refresh(job)

    background.add_task(run_conversion_job, job.id)

    return {"project_id": proj.id, "job_id": job.id, "engine": req.engine}


@router.get("/{project_id}")
def get_project(
    project_id: int,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    proj = _own_project(project_id, current, session)
    sp = _latest_screenplay(project_id, session)
    job = _latest_job(project_id, session)
    doc = sp.doc if sp else {}
    return {
        "project_id": proj.id,
        "title": proj.title,
        "author": proj.author,
        "source_text": proj.source_text,
        "screenplay": doc,
        "yaml": to_yaml(doc) if doc else "",
        "version": sp.version if sp else 0,
        "job": {
            "id": job.id, "status": job.status, "progress": job.progress,
            "total": job.total, "error": job.error,
        } if job else None,
    }


@router.put("/{project_id}/screenplay")
def save_screenplay(
    project_id: int,
    req: SaveScreenplayRequest,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    proj = _own_project(project_id, current, session)
    problems = validate_screenplay(req.screenplay)
    prev = _latest_screenplay(project_id, session)
    new_ver = (prev.version + 1) if prev else 1

    sp = Screenplay(
        project_id=proj.id, version=new_ver, doc=req.screenplay,
        engine=prev.engine if prev else "edited", is_valid=len(problems) == 0,
    )
    proj.updated_at = datetime.now(timezone.utc)
    session.add(sp)
    session.add(proj)
    session.commit()

    return {
        "yaml": to_yaml(req.screenplay),
        "valid": len(problems) == 0,
        "problems": problems,
        "version": new_ver,
    }


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    proj = _own_project(project_id, current, session)
    for sp in session.exec(
        select(Screenplay).where(Screenplay.project_id == project_id)
    ).all():
        session.delete(sp)
    for jb in session.exec(select(Job).where(Job.project_id == project_id)).all():
        session.delete(jb)
    session.delete(proj)
    session.commit()
    return {"ok": True}
