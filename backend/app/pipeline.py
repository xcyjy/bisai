"""转换流水线：把整篇小说装配成完整剧本 dict。

流程：分章 -> 全局人物抽取 -> 逐章转换 -> 装配 + 编号 -> 校验。
"""
from __future__ import annotations

from typing import Optional

from .chapters import split_chapters
from .converter import convert_chapter, engine_mode, extract_characters
from .schema import validate_screenplay


def convert_novel(
    text: str,
    title: str = "未命名剧本",
    original_work: str = "",
    author: str = "",
) -> dict:
    """返回完整剧本 dict（含 meta / characters / scenes）+ 统计 + 校验结果。"""
    chapters = split_chapters(text)
    chapter_titles = [t for t, _ in chapters]

    # 1) 全局人物表
    characters = extract_characters(text)

    # 2) 逐章转换
    all_scenes = []
    for _title, body in chapters:
        all_scenes.extend(convert_chapter(body, characters))

    # 3) 装配 + 连续编号
    scenes_out = []
    for i, scene in enumerate(all_scenes, start=1):
        s = scene.model_dump()
        # 清理 None 字段，YAML 更干净
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
        "engine": engine_mode(),
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
    }
    return {"screenplay": doc, "stats": stats}
