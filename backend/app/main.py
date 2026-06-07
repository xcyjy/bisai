"""FastAPI 后端入口。

启动：
    cd backend
    uvicorn app.main:app --reload --port 8000

包含：
- 匿名接口：/api/health、/api/convert、/api/export（兼容原 MVP，可不登录试用）
- 登录态接口：/api/auth/*（注册登录）、/api/projects/*（作品 CRUD + 持久化）
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session

try:
    from dotenv import load_dotenv
    load_dotenv()  # 读取 backend/.env（python-dotenv 可选）
except ImportError:
    pass

from .api import account as account_api  # noqa: E402
from .api import auth as auth_api  # noqa: E402
from .api import jobs as jobs_api  # noqa: E402
from .api import orders as orders_api  # noqa: E402
from .api import projects as projects_api  # noqa: E402
from .converter import engine_mode  # noqa: E402
from .core.config import settings  # noqa: E402
from .db.session import init_db  # noqa: E402
from .core.billing import cost_usd  # noqa: E402
from .core.deps import get_current_user  # noqa: E402
from .db.models import UsageLog, User  # noqa: E402
from .db.session import engine as db_engine  # noqa: E402
from .exporter import to_yaml  # noqa: E402
from .models import list_models  # noqa: E402
from .orchestrator import orchestrate  # noqa: E402
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
app.include_router(jobs_api.router)
app.include_router(orders_api.router)
app.include_router(account_api.router)


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
    if len(req.text) > 100_000:
        raise HTTPException(status_code=400, detail="小说文本过长（>10万字），请分批转换。")
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


@app.get("/api/models")
def models():
    """可用模型列表（中转站 claude 系，分质量/均衡/经济三档），供前端模型下拉。"""
    return list_models()


class AgentConvertRequest(BaseModel):
    text: str
    title: str = "未命名剧本"
    author: str = ""
    model: Optional[str] = None
    engine: str = "agents"  # agents=多Agent(AI) | offline=多Agent(离线，0 token)


# ---- 成本/滥用防护：输入上限 + 进程内按用户限流 ----
MAX_TEXT_CHARS = 100_000          # 单次输入上限，防超长文本烧 token
_RATE_MAX = 5                     # 每窗口最多次数
_RATE_WINDOW = 60.0              # 限流窗口（秒）
_rate_hits: Dict[int, List[float]] = {}
_rate_lock = threading.Lock()


def _check_rate(user_id: int) -> None:
    now = time.time()
    with _rate_lock:
        hits = [t for t in _rate_hits.get(user_id, []) if now - t < _RATE_WINDOW]
        if len(hits) >= _RATE_MAX:
            raise HTTPException(status_code=429, detail=f"操作过于频繁，请 {int(_RATE_WINDOW)} 秒后再试。")
        hits.append(now)
        _rate_hits[user_id] = hits


def _charge_agent_run(user_id: int, stats: dict) -> None:
    """转换真正用了 AI 才扣 1 积分并记账（用独立 DB 会话，避免请求会话已关闭）。"""
    toks = stats.get("tokens", {})
    in_t, out_t = toks.get("in", 0), toks.get("out", 0)
    model = stats.get("model") or settings.script_model
    with Session(db_engine) as s:
        u = s.get(User, user_id)
        if u is None:
            return
        u.credits = max(0, u.credits - 1)
        s.add(u)
        s.add(UsageLog(
            user_id=user_id, project_id=None, engine=stats.get("engine", ""),
            in_tokens=in_t, out_tokens=out_t,
            cost_usd=cost_usd(model, in_t, out_t), credits_spent=1,
        ))
        s.commit()


@app.post("/api/convert/agents")
async def convert_agents(
    req: AgentConvertRequest,
    current: User = Depends(get_current_user),
):
    """多 Agent 编排转换（SSE 流式）：实时推送每个 Agent 的活动事件，最后推 result。

    需登录；AI 模式（engine!=offline）需 ≥1 积分，转换成功后扣 1 积分；带输入上限与限流。
    事件：event: agent  data:{seq,agent,status,in,out,cache_read,...}
    结束：event: result data:{screenplay,yaml,stats}  或  event: error
    """
    text = req.text or ""
    if len(text.strip()) < 50:
        raise HTTPException(status_code=400, detail="小说文本太短，请提供至少 3 个章节的内容。")
    if len(text) > MAX_TEXT_CHARS:
        raise HTTPException(status_code=400, detail=f"小说文本过长（>{MAX_TEXT_CHARS} 字），请分批转换。")

    _check_rate(current.id)

    use_ai = req.engine != "offline"
    if use_ai:
        if not settings.ai_available:
            raise HTTPException(status_code=400, detail="AI 引擎暂未开通（未配置密钥），请用离线模式。")
        if current.credits < 1:
            raise HTTPException(status_code=402, detail="积分不足，请升级会员或购买积分包。")

    uid = current.id

    async def gen():
        queue: asyncio.Queue = asyncio.Queue()
        task = asyncio.create_task(orchestrate(
            text, title=req.title, author=req.author,
            use_ai=use_ai, model=req.model, emit=queue.put_nowait,
        ))
        def _fmt(e: dict) -> str:
            ev = "partial" if e.get("partial") else "agent"
            return f"event: {ev}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n"

        # 流式吐出 Agent 事件 + 渐进式 partial（边转边出），直到编排任务结束
        while True:
            try:
                e = await asyncio.wait_for(queue.get(), timeout=0.3)
                yield _fmt(e)
            except asyncio.TimeoutError:
                if task.done():
                    break
        while not queue.empty():
            yield _fmt(queue.get_nowait())
        try:
            result = await task
            stats = result["stats"]
            # 计费：真的调用了大模型（engine=agents:claude-*）才扣分记账
            if use_ai and str(stats.get("engine", "")).startswith("agents:claude"):
                _charge_agent_run(uid, stats)
            payload = {
                "screenplay": result["screenplay"],
                "stats": stats,
                "yaml": to_yaml(result["screenplay"]),
            }
            yield f"event: result\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        except Exception as ex:  # noqa: BLE001
            yield f"event: error\ndata: {json.dumps({'message': str(ex)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
