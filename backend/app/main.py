"""FastAPI 后端入口。

启动：
    cd backend
    uvicorn app.main:app --reload --port 8000

包含：
- 匿名接口：/api/health、/api/convert、/api/export（兼容原 MVP，可不登录试用）
- 登录态接口：/api/auth/*（注册登录）、/api/projects/*（作品 CRUD + 持久化）
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    load_dotenv()  # 读取 backend/.env（python-dotenv 可选）
except ImportError:
    pass

from .api import auth as auth_api  # noqa: E402
from .api import projects as projects_api  # noqa: E402
from .converter import engine_mode  # noqa: E402
from .core.config import settings  # noqa: E402
from .db.session import init_db  # noqa: E402
from .exporter import to_yaml  # noqa: E402
from .pipeline import convert_novel  # noqa: E402
from .schema import validate_screenplay  # noqa: E402

app = FastAPI(title="AI 小说转剧本工具", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    init_db()  # 首次启动自动建表（生产建议改 Alembic）


app.include_router(auth_api.router)
app.include_router(projects_api.router)


class ConvertRequest(BaseModel):
    text: str
    title: str = "未命名剧本"
    original_work: str = ""
    author: str = ""


class ExportRequest(BaseModel):
    screenplay: Dict[str, Any]


@app.get("/api/health")
def health():
    return {"status": "ok", "engine": engine_mode()}


@app.post("/api/convert")
def convert(req: ConvertRequest):
    """匿名试用：转换但不保存。登录后保存请用 POST /api/projects。"""
    if not req.text or len(req.text.strip()) < 50:
        raise HTTPException(status_code=400, detail="小说文本太短，请提供至少 3 个章节的内容。")
    result = convert_novel(
        text=req.text,
        title=req.title,
        original_work=req.original_work,
        author=req.author,
    )
    result["yaml"] = to_yaml(result["screenplay"])
    return result


@app.post("/api/export")
def export(req: ExportRequest):
    """前端编辑后重新生成干净 YAML，并附带最新校验结果。"""
    problems = validate_screenplay(req.screenplay)
    return {"yaml": to_yaml(req.screenplay), "valid": len(problems) == 0, "problems": problems}
