"""FastAPI 后端入口。

启动：
    cd backend
    uvicorn app.main:app --reload --port 8000
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

from .converter import engine_mode  # noqa: E402
from .exporter import to_yaml  # noqa: E402
from .pipeline import convert_novel  # noqa: E402
from .schema import validate_screenplay  # noqa: E402

app = FastAPI(title="AI 小说转剧本工具", version="0.1.0")

# 允许前端（Vite 默认 5173）跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
