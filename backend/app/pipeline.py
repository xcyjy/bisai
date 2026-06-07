"""转换流水线：把整篇小说装配成完整剧本 dict。

流程：分章 -> 全局人物抽取 -> 逐章转换 -> 装配 + 编号 -> 校验。
支持 use_ai（AI 精修 vs 离线规则）与 progress 回调（用于异步任务进度）。
"""
from __future__ import annotations

from typing import Callable, Optional

from .chapters import split_chapters
from .converter import convert_chapter, engine_mode, extract_characters
from .schema import validate_screenplay

ProgressCb = Optional[Callable[[int, int], None]]


def convert_novel(
    text: str,
    title: str = "未命名剧本",
    original_work: str = "",
    author: str = "",
    use_ai: bool = False,
    progress: ProgressCb = None,
) -> dict:
    """返回完整剧本 dict（含 meta / characters / scenes）+ 统计 + 校验结果。

    progress(done, total)：每完成一章回调一次，便于异步任务上报进度。
    stats 中含 token 用量（in_tokens/out_tokens），离线时为 0。
    """
    chapters = split_chapters(text)
    chapter_titles = [t for t, _ in chapters]
    total = len(chapters)
    usage = {"in_tokens": 0, "out_tokens": 0}

    if progress:
        progress(0, total)

    # 1) 全局人物表
    characters = extract_characters(text, use_ai=use_ai, usage=usage)

    # 2) 逐章转换
    all_scenes = []
    for i, (_title, body) in enumerate(chapters, start=1):
        all_scenes.extend(convert_chapter(body, characters, use_ai=use_ai, usage=usage))
        if progress:
            progress(i, total)

    # 3) 装配 + 连续编号
    scenes_out = []
    for i, scene in enumerate(all_scenes, start=1):
        s = scene.model_dump()
        for el in s["elements"]:
            if el.get("character") is None:
                el.pop("character", None)
            if el.get("parenthetical") is None:
                el.pop("parenthetical", None)
        scenes_out.append({"scene_number": i, **s})

    doc = {
        "meta": {
            "title": title,
            "original_work": original_work,
            "author": author,
            "script_type": "film",
            "language": "zh",
            "source_chapters": chapter_titles,
            "generated_by": "ai-draft",
        },
        "characters": [
            {"id": c.id, "name": c.name, "aliases": [], "description": c.description}
            for c in characters
        ],
        "scenes": scenes_out,
    }

    problems = validate_screenplay(doc)
    stats = {
        "engine": engine_mode(use_ai),
        "chapters": len(chapters),
        "characters": len(characters),
        "scenes": len(scenes_out),
        "dialogues": sum(
            1 for s in scenes_out for el in s["elements"] if el["type"] == "dialogue"
        ),
        "voiceovers": sum(
            1 for s in scenes_out for el in s["elements"] if el["type"] == "voiceover"
        ),
        "valid": len(problems) == 0,
        "problems": problems,
        "in_tokens": usage["in_tokens"],
        "out_tokens": usage["out_tokens"],
    }
    return {"screenplay": doc, "stats": stats}
