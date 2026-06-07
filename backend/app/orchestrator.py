"""多 Agent 编排器（异步）。

把「小说→剧本」做成可编排、可并发、可自我纠错的 Agent 流程：

- 并发：AsyncAnthropic + asyncio.gather + Semaphore 限流，逐章并发执行。
- 双层缓存：① 结果缓存(命中=0 token, agentcache)；② Prompt 缓存(静态前缀打 cache_control)。
- Token 账本：每个 Agent 记录 in/out/cache_read/cache_creation + 耗时 + 是否命中。
- 黑板：characters/scenes/... 单一事实源；各 Agent 读写不同键，互不喊话。
- Critic 回环：装配后 validate，失败则对「出问题的章」做一次纠错重跑（有界轮数）。
- 事件流：每个 Agent start/done/cache/error 发事件，供 SSE 可视化。
- 降级：任一 Agent 失败→落回离线规则，保证「再差也有合法 YAML」。

对外：run_agents(text, ...) 同步包装；orchestrate(...) 异步内核（SSE 端点直接 await）。
"""
from __future__ import annotations

import asyncio
import re
from time import perf_counter
from typing import Callable, Dict, List, Optional

from .agentcache import cache, make_key
from .chapters import split_chapters
from .converter import (
    RULES,
    _convert_chapter_offline,
    _extract_characters_offline,
    _is_offline,
)
from .core.config import settings
from .pipeline import _compact, _enrich_scene, _name_index
from .schema import (
    Character,
    CharacterList,
    Scene,
    SceneList,
    StoryMeta,
    validate_screenplay,
)

SCHEMA_VERSION = "1.0"
MAX_CRITIC_ROUNDS = 2
DEFAULT_CONCURRENCY = 5

EmitCb = Optional[Callable[[dict], None]]


# =========================================================
# Token 账本 + 事件流
# =========================================================

class Ledger:
    def __init__(self, emit: EmitCb = None) -> None:
        self._emit = emit
        self.events: List[dict] = []
        self.seq = 0
        self.t_in = self.t_out = self.c_read = self.c_create = 0
        self.result_hits = 0
        self.result_total = 0

    def _push(self, e: dict) -> None:
        self.seq += 1
        e["seq"] = self.seq
        self.events.append(e)
        if self._emit:
            try:
                self._emit(e)
            except Exception:
                pass

    def start(self, agent: str, note: str = "") -> None:
        self._push({"agent": agent, "status": "start", "note": note})

    def done(self, agent: str, usage, ms: float) -> None:
        ci = int(getattr(usage, "input_tokens", 0) or 0)
        co = int(getattr(usage, "output_tokens", 0) or 0)
        cr = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        cc = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
        self.t_in += ci; self.t_out += co; self.c_read += cr; self.c_create += cc
        self._push({"agent": agent, "status": "done", "in": ci, "out": co,
                    "cache_read": cr, "cache_creation": cc, "ms": round(ms)})

    def offline(self, agent: str, ms: float) -> None:
        self._push({"agent": agent, "status": "done", "in": 0, "out": 0,
                    "cache_read": 0, "cache_creation": 0, "ms": round(ms), "note": "离线规则"})

    def hit(self, agent: str, ms: float) -> None:
        self.result_hits += 1
        self._push({"agent": agent, "status": "cache", "ms": round(ms),
                    "note": "结果缓存命中 · 0 token"})

    def error(self, agent: str, msg: str) -> None:
        self._push({"agent": agent, "status": "error", "note": str(msg)[:160]})


# =========================================================
# 异步客户端 + tool-use 结构化调用（含双层缓存）
# =========================================================

def _aclient():
    import anthropic
    kwargs = {"api_key": settings.anthropic_api_key}
    if settings.anthropic_base_url:
        kwargs["base_url"] = settings.anthropic_base_url
    return anthropic.AsyncAnthropic(**kwargs)


async def _structured_async(client, model: str, system_text: str, user_text: str,
                            output_model, max_tokens: int, *, agent: str,
                            ledger: Ledger, cache_payload: str, use_cache: bool = True):
    """tool-use 拿结构化输出。先查结果缓存(0 token)，未命中再调用并把静态前缀打 cache_control。"""
    ledger.result_total += 1
    key = make_key(model, SCHEMA_VERSION, agent, cache_payload)
    t0 = perf_counter()

    if use_cache:
        cached = cache.get(key)
        if cached is not None:
            obj = output_model.model_validate(cached)
            ledger.hit(agent, (perf_counter() - t0) * 1000)
            return obj

    tool = {
        "name": "emit_result",
        "description": f"输出结构化结果（{output_model.__name__}）",
        "input_schema": output_model.model_json_schema(),
    }
    # 静态前缀打 cache_control → 跨章命中 prompt 缓存（cache_read_input_tokens）
    system_blocks = [{"type": "text", "text": system_text,
                      "cache_control": {"type": "ephemeral"}}]
    common = dict(model=model, max_tokens=max_tokens, tools=[tool],
                  tool_choice={"type": "tool", "name": "emit_result"},
                  messages=[{"role": "user", "content": user_text}])
    try:
        resp = await client.messages.create(system=system_blocks, **common)
    except Exception:
        # 中转站若不接受 cache_control，退回纯文本 system 再试一次
        resp = await client.messages.create(system=system_text, **common)

    ms = (perf_counter() - t0) * 1000
    data = None
    for b in resp.content:
        if getattr(b, "type", None) == "tool_use":
            data = b.input
            break
    if data is None:
        raise RuntimeError("模型未返回 tool_use 结构化结果")
    obj = output_model.model_validate(data)
    cache.put(key, data)
    ledger.done(agent, resp.usage, ms)
    return obj


# =========================================================
# 各 Agent
# =========================================================

async def _story_agent(client, model, full_text, ledger, offline) -> StoryMeta:
    agent = "故事Agent"
    ledger.start(agent, "提炼 logline/genre/tone")
    t0 = perf_counter()
    if offline:
        ledger.offline(agent, (perf_counter() - t0) * 1000)
        return StoryMeta()
    prompt = ("下面是一篇小说。请用一句话 logline（主角+核心困境+悬念）概括故事，"
              "并判断 genre 与 tone。\n\n小说全文：\n" + full_text[:12000])
    try:
        return await _structured_async(
            client, model, "你是资深剧本策划，擅长一句话提炼故事主线。", prompt,
            StoryMeta, 1000, agent=agent, ledger=ledger, cache_payload=full_text[:12000])
    except Exception as e:
        ledger.error(agent, str(e))
        return StoryMeta()


async def _character_agent(client, model, full_text, ledger, offline) -> List[Character]:
    agent = "人物Agent"
    ledger.start(agent, "抽取全局人物表")
    t0 = perf_counter()
    if offline:
        chars = await asyncio.to_thread(_extract_characters_offline, full_text)
        ledger.offline(agent, (perf_counter() - t0) * 1000)
        return chars
    prompt = ("下面是一篇小说。请抽取主要人物，生成全局人物表。"
              "为每个角色分配唯一 id（如 char_01），给出 name、一句话 description、"
              "别名 aliases、role（主角/反派/配角）、性别、人物弧光 arc。\n\n"
              "小说全文：\n" + full_text[:12000])
    try:
        cl = await _structured_async(
            client, model, "你是专业编剧助手，擅长从小说中梳理人物。", prompt,
            CharacterList, 4000, agent=agent, ledger=ledger, cache_payload=full_text[:12000])
        return cl.characters if cl else []
    except Exception as e:
        ledger.error(agent, str(e))
        return await asyncio.to_thread(_extract_characters_offline, full_text)


def _char_hint(characters: List[Character]) -> str:
    return "；".join(f"{c.name}({c.description})" for c in characters) or "（无）"


async def _chapter_agent(client, model, idx, title, body, characters, ledger, offline,
                         hint: str = "") -> List[Scene]:
    agent = f"分场Agent·{title[:8]}"
    ledger.start(agent, "本章 → 结构化场次")
    t0 = perf_counter()
    if offline:
        scenes = await asyncio.to_thread(_convert_chapter_offline, body, characters)
        ledger.offline(agent, (perf_counter() - t0) * 1000)
        return scenes
    char_ctx = _char_hint(characters)
    # 静态前缀（RULES + 人物表）放 system → 跨章 prompt 缓存命中
    system_text = (f"{RULES}\n\n已知人物表（对白/旁白的 character 必须用这些名字）：{char_ctx}")
    user_text = ("请把下面这一章小说转换为结构化剧本：按时间/地点切分为若干场，"
                 "每场给出 heading（含 day_night）、synopsis、beat、breakdown 与有序 elements。\n")
    if hint:
        user_text += f"\n【上一轮校验发现的问题，请务必修正】：{hint}\n"
    user_text += f"\n本章正文：\n{body}"
    try:
        sl = await _structured_async(
            client, model, system_text, user_text, SceneList, 16000,
            agent=agent, ledger=ledger,
            cache_payload=f"{char_ctx}||{hint}||{body}", use_cache=not hint)
        return sl.scenes if sl else []
    except Exception as e:
        ledger.error(agent, str(e))
        return await asyncio.to_thread(_convert_chapter_offline, body, characters)


# =========================================================
# 装配 + Critic
# =========================================================

def _assemble(chapters, chapter_scenes: Dict[int, List[Scene]], characters, story,
              title, original_work, author):
    name_idx = _name_index(characters)
    scenes_out: List[dict] = []
    scene_chapter: List[int] = []
    n = 0
    for idx, (chap_title, _body) in enumerate(chapters):
        for sc in chapter_scenes.get(idx, []):
            d = sc.model_dump()
            _enrich_scene(d, chap_title, name_idx)
            n += 1
            scenes_out.append(_compact({"scene_number": n, **d}))
            scene_chapter.append(idx)

    meta = {
        "title": title, "original_work": original_work, "author": author,
        "script_type": "film", "schema_version": SCHEMA_VERSION, "language": "zh",
        "source_chapters": [t for t, _ in chapters], "generated_by": "ai-draft",
    }
    if story.logline:
        meta["logline"] = story.logline
    if story.genre:
        meta["genre"] = story.genre
    if story.tone:
        meta["tone"] = story.tone

    doc = {
        "meta": meta,
        "characters": [_compact(c.model_dump()) for c in characters],
        "scenes": scenes_out,
    }
    return doc, scene_chapter


def _offending_chapters(problems: List[str], scene_chapter: List[int]) -> List[int]:
    """从 '第 N 场...' 的问题里反查涉及哪些章（用于 Critic 定向重跑）。"""
    idxs = set()
    for p in problems:
        m = re.search(r"第\s*(\d+)\s*场", p)
        if m:
            i = int(m.group(1)) - 1
            if 0 <= i < len(scene_chapter):
                idxs.add(scene_chapter[i])
    return sorted(idxs)


# =========================================================
# 编排主流程
# =========================================================

async def orchestrate(text: str, title: str = "未命名剧本", original_work: str = "",
                      author: str = "", use_ai: bool = True, model: Optional[str] = None,
                      emit: EmitCb = None, concurrency: int = DEFAULT_CONCURRENCY) -> dict:
    wall0 = perf_counter()
    ledger = Ledger(emit)
    offline = _is_offline(use_ai)
    model = model or settings.script_model
    chapters = split_chapters(text)
    client = None if offline else _aclient()

    ledger.start("编排器", f"规划 {len(chapters)} 章 · {'离线' if offline else model}")

    # 1) 故事元信息 + 人物表（并发）
    story, characters = await asyncio.gather(
        _story_agent(client, model, text, ledger, offline),
        _character_agent(client, model, text, ledger, offline),
    )

    # 2) 逐章并发转换（信号量限流）
    sem = asyncio.Semaphore(max(1, concurrency))

    async def run_chapter(idx, title_, body):
        async with sem:
            scenes = await _chapter_agent(client, model, idx, title_, body, characters,
                                          ledger, offline)
        return idx, scenes

    pairs = await asyncio.gather(*[
        run_chapter(idx, t, b) for idx, (t, b) in enumerate(chapters)
    ])
    chapter_scenes: Dict[int, List[Scene]] = {idx: sc for idx, sc in pairs}

    # 3) Critic 回环：装配→校验→定向重跑出问题的章（有界）
    rounds = 0
    doc, scene_chapter = _assemble(chapters, chapter_scenes, characters, story,
                                   title, original_work, author)
    problems = validate_screenplay(doc)
    while problems and not offline and rounds < MAX_CRITIC_ROUNDS:
        rounds += 1
        bad = _offending_chapters(problems, scene_chapter)
        ledger.start("Critic", f"第{rounds}轮 · {len(problems)}个问题 · 重跑{len(bad)}章")
        hint = "；".join(problems[:6])
        fixes = await asyncio.gather(*[
            _chapter_agent(client, model, idx, chapters[idx][0], chapters[idx][1],
                           characters, ledger, offline, hint=hint)
            for idx in bad
        ])
        for idx, scenes in zip(bad, fixes):
            chapter_scenes[idx] = scenes
        doc, scene_chapter = _assemble(chapters, chapter_scenes, characters, story,
                                       title, original_work, author)
        problems = validate_screenplay(doc)

    if client is not None:
        await client.close()

    # 4) 统计 + token 账本
    scenes_out = doc["scenes"]
    wall_ms = round((perf_counter() - wall0) * 1000)
    est_total = sum(s.get("est_duration_sec", 0) for s in scenes_out)
    hit_rate = (ledger.result_hits / ledger.result_total) if ledger.result_total else 0.0
    stats = {
        "engine": "agents:offline" if offline else f"agents:{model}",
        "model": None if offline else model,
        "chapters": len(chapters),
        "characters": len(characters),
        "scenes": len(scenes_out),
        "dialogues": sum(1 for s in scenes_out for el in s["elements"] if el["type"] == "dialogue"),
        "voiceovers": sum(1 for s in scenes_out for el in s["elements"] if el["type"] == "voiceover"),
        "est_total_sec": est_total,
        "valid": len(problems) == 0,
        "problems": problems,
        "rounds": rounds,
        "tokens": {"in": ledger.t_in, "out": ledger.t_out,
                   "cache_read": ledger.c_read, "cache_creation": ledger.c_create},
        "cache": {"result_hits": ledger.result_hits, "result_total": ledger.result_total,
                  "hit_rate": round(hit_rate, 3), "prompt_cache_read_tokens": ledger.c_read},
        "timing": {"wall_ms": wall_ms, "agent_count": ledger.seq},
        # 兼容旧字段
        "in_tokens": ledger.t_in, "out_tokens": ledger.t_out,
    }
    return {"screenplay": doc, "stats": stats, "events": ledger.events}


def run_agents(text: str, title: str = "未命名剧本", original_work: str = "",
               author: str = "", use_ai: bool = True, model: Optional[str] = None,
               concurrency: int = DEFAULT_CONCURRENCY) -> dict:
    """同步包装：内部跑异步编排，返回 {screenplay, stats, events}。"""
    return asyncio.run(orchestrate(
        text, title=title, original_work=original_work, author=author,
        use_ai=use_ai, model=model, concurrency=concurrency))
