"""作品接口：转换并保存 / 列表 / 详情 / 保存编辑 / 删除。

所有接口需登录，且按 user_id 强隔离（越权访问返回 404）。
转换复用现有 pipeline.convert_novel，不改核心链路。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from ..core.deps import get_current_user
from ..db.models import Project, Screenplay, User
from ..db.session import get_session
from ..exporter import to_yaml
from ..pipeline import convert_novel
from ..schema import validate_screenplay

router = APIRouter(prefix="/api/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    text: str
    title: str = "未命名剧本"
    original_work: str = ""
    author: str = ""


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
        out.append({
            "id": p.id,
            "title": p.title,
            "author": p.author,
            "char_count": p.char_count,
            "scenes": len(sp.doc.get("scenes", [])) if sp else 0,
            "updated_at": p.updated_at.isoformat(),
        })
    return out


@router.post("")
def create_project(
    req: CreateProjectRequest,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if not req.text or len(req.text.strip()) < 50:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "小说文本太短，请提供至少 3 个章节。")

    result = convert_novel(
        text=req.text, title=req.title, original_work=req.original_work, author=req.author
    )
    doc = result["screenplay"]
    stats = result["stats"]

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

    sp = Screenplay(
        project_id=proj.id, version=1, doc=doc,
        engine=stats["engine"], is_valid=stats["valid"],
    )
    session.add(sp)
    session.commit()

    return {
        "project_id": proj.id,
        "screenplay": doc,
        "stats": stats,
        "yaml": to_yaml(doc),
    }


@router.get("/{project_id}")
def get_project(
    project_id: int,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    proj = _own_project(project_id, current, session)
    sp = _latest_screenplay(project_id, session)
    doc = sp.doc if sp else {}
    return {
        "project_id": proj.id,
        "title": proj.title,
        "author": proj.author,
        "source_text": proj.source_text,
        "screenplay": doc,
        "yaml": to_yaml(doc) if doc else "",
        "version": sp.version if sp else 0,
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
    session.delete(proj)
    session.commit()
    return {"ok": True}
