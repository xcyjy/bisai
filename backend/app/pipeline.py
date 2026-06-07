"""转换流水线：把整篇小说装配成完整剧本 dict。

流程：分章 -> 故事元信息 + 全局人物抽取 -> 逐章转换 -> 专业字段装配 + 编号 -> [短剧:拆集] -> 校验。
支持影视 / 短剧双路：默认产出通用影视剧本；当 script_type="short_drama" 时，
转换后按口播时长自动拆集（每集带钩子/扣子/时长），产出分集短剧结构。
支持 use_ai（AI 精修 vs 离线规则）与 progress 回调（用于异步任务进度）。

「专业字段装配」在装配期对每一场确定性地补全可计算的产业化字段：
- source_ref：本场来自哪一章（章索引可靠，不依赖模型）。
- breakdown.cast：本场出场角色（扫描元素中出现的人名/别名）。
- est_duration_sec：按元素体量估算时长（时长体检的基础）。
- heading.day_night：缺失时由 time 文本兜底归一化。
这些字段无论在线/离线都能产出，是「结构化剧本 > 裸调大模型」的差异化所在。
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from .chapters import split_chapters
from .converter import (
    convert_chapter,
    derive_day_night,
    engine_mode,
    extract_characters,
    extract_story_meta,
)
from .episodes import split_into_episodes
from .schema import Character, validate_screenplay

ProgressCb = Optional[Callable[[int, int], None]]

# 时长估算系数（粗略，仅供时长体检参考）：
# 对白/旁白按朗读语速 ~5 字/秒；动作按视觉节奏 ~12 字/秒 + 1 秒起拍；转场固定 1 秒。
_SPEAK_CPS = 5.0
_ACTION_CPS = 12.0


def _name_index(characters: List[Character]) -> Dict[str, str]:
    """别名/本名 -> 本名 的映射，用于把场内出现的称呼归一到角色本名。"""
    idx: Dict[str, str] = {}
    for c in characters:
        idx[c.name] = c.name
        for a in c.aliases or []:
            idx[a] = c.name
    return idx


def _scene_cast(elements: List[dict], name_idx: Dict[str, str]) -> List[str]:
    """确定性统计本场出场角色：对白/旁白说话人 + 动作文本中点到的人名。保持出现顺序去重。"""
    seen: List[str] = []

    def add(name: Optional[str]):
        if name and name in seen:
            return
        if name:
            seen.append(name)

    for el in elements:
        ch = el.get("character")
        if ch:
            add(name_idx.get(ch, ch))
        text = el.get("text", "")
        for alias, canonical in name_idx.items():
            if alias and alias in text:
                add(canonical)
    return seen


def _estimate_seconds(elements: List[dict]) -> int:
    sec = 0.0
    for el in elements:
        t = len(el.get("text", "") or "")
        typ = el.get("type")
        if typ in ("dialogue", "voiceover"):
            sec += t / _SPEAK_CPS
        elif typ == "transition":
            sec += 1.0
        else:  # action / shot / subheading
            sec += t / _ACTION_CPS + 1.0
    return max(3, round(sec))


def _compact(value):
    """递归剔除 None 与空容器/空串，得到干净的 YAML（不输出一堆 null/[]）。"""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            cv = _compact(v)
            if cv is None or cv == [] or cv == {} or cv == "":
                continue
            out[k] = cv
        return out
    if isinstance(value, list):
        return [_compact(v) for v in value]
    return value


def _enrich_scene(scene: dict, chapter_title: str, name_idx: Dict[str, str]) -> dict:
    """装配期补全确定性专业字段（不覆盖模型已给出的更优内容）。"""
    elements = scene.get("elements", [])

    # 1) 溯源：章节可靠由流水线给出；excerpt 缺失则取首个动作/文本片段兜底
    src = scene.get("source_ref") or {}
    src["chapter"] = chapter_title
    if not src.get("excerpt"):
        first_text = next((el.get("text", "") for el in elements if el.get("text")), "")
        src["excerpt"] = first_text[:50]
    scene["source_ref"] = src

    # 2) 制片分解：cast 确定性计算并与模型给出的 breakdown 合并
    bd = scene.get("breakdown") or {}
    bd["cast"] = _scene_cast(elements, name_idx)
    scene["breakdown"] = bd

    # 3) 时长体检
    scene["est_duration_sec"] = _estimate_seconds(elements)

    # 4) day_night 兜底
    heading = scene.get("heading") or {}
    if not heading.get("day_night"):
        dn = derive_day_night(heading.get("time", ""))
        if dn:
            heading["day_night"] = dn
    scene["heading"] = heading
    return scene


def convert_novel(
    text: str,
    title: str = "未命名剧本",
    original_work: str = "",
    author: str = "",
    use_ai: bool = False,
    progress: ProgressCb = None,
    script_type: str = "film",
    target_minutes: float = 2.5,
) -> dict:
    """返回完整剧本 dict（含 meta / characters / scenes）+ 统计 + 校验结果。

    支持影视 / 短剧双路：script_type（film | tv | short_drama）决定剧本类型。
    当 script_type="short_drama" 时，转换后按口播时长自动拆集
    （doc["episodes"]，每集带钩子/扣子/时长）；影视模式不自动拆集，
    如需分集可调 /api/projects/{id}/episodes。
    progress(done, total)：每完成一章回调一次，便于异步任务上报进度。
    target_minutes：短剧单集目标时长（分钟），用于自动拆集。
    stats 中含 token 用量（in_tokens/out_tokens），离线时为 0。
    """
    chapters = split_chapters(text)
    chapter_titles = [t for t, _ in chapters]
    total = len(chapters)
    usage = {"in_tokens": 0, "out_tokens": 0}

    if progress:
        progress(0, total)

    # 1) 故事元信息 + 全局人物表
    story = extract_story_meta(text, use_ai=use_ai, usage=usage)
    characters = extract_characters(text, use_ai=use_ai, usage=usage)
    name_idx = _name_index(characters)

    # 2) 逐章转换，并记住每一场来自哪一章
    enriched_scenes: List[dict] = []
    for i, (chap_title, body) in enumerate(chapters, start=1):
        for scene in convert_chapter(body, characters, use_ai=use_ai, usage=usage):
            d = scene.model_dump()
            _enrich_scene(d, chap_title, name_idx)
            enriched_scenes.append(d)
        if progress:
            progress(i, total)

    # 3) 连续编号 + 清理空字段
    scenes_out: List[dict] = []
    for i, scene in enumerate(enriched_scenes, start=1):
        scenes_out.append(_compact({"scene_number": i, **scene}))

    meta = {
        "title": title,
        "original_work": original_work,
        "author": author,
        "script_type": script_type,
        "schema_version": "1.0",
        "language": "zh",
        "source_chapters": chapter_titles,
        "generated_by": "ai-draft",
    }
    # 故事级元信息（AI 才有，离线留空则不写入，保持 meta 干净）
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

    # 4) 短剧模式：转换即按口播时长自动拆集（每集带钩子/扣子/时长）；影视模式不拆。
    if script_type == "short_drama":
        doc["episodes"] = split_into_episodes(doc, target_minutes=target_minutes)

    problems = validate_screenplay(doc)
    est_total = sum(s.get("est_duration_sec", 0) for s in scenes_out)
    stats = {
        "engine": engine_mode(use_ai),
        "chapters": len(chapters),
        "characters": len(characters),
        "scenes": len(scenes_out),
        "episodes": len(doc.get("episodes", [])),
        "dialogues": sum(
            1 for s in scenes_out for el in s["elements"] if el["type"] == "dialogue"
        ),
        "voiceovers": sum(
            1 for s in scenes_out for el in s["elements"] if el["type"] == "voiceover"
        ),
        "est_total_sec": est_total,
        "valid": len(problems) == 0,
        "problems": problems,
        "in_tokens": usage["in_tokens"],
        "out_tokens": usage["out_tokens"],
    }
    return {"screenplay": doc, "stats": stats}
