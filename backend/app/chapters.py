"""分章模块：把整篇小说切成章节。"""
from __future__ import annotations

import re
from typing import List, Tuple

# 匹配常见章节标题：第一章 / 第1章 / 第十二回 / Chapter 3 / 卷一
_CHAPTER_PATTERNS = [
    re.compile(r"^\s*第\s*[0-9零一二三四五六七八九十百千]+\s*[章回节]\b.*$"),
    re.compile(r"^\s*Chapter\s+\d+.*$", re.IGNORECASE),
    re.compile(r"^\s*CHAPTER\s+[IVXLC]+.*$"),
]


def _is_chapter_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 40:
        return False
    return any(p.match(stripped) for p in _CHAPTER_PATTERNS)


def split_chapters(text: str) -> List[Tuple[str, str]]:
    """切分章节。

    返回 [(章节标题, 章节正文), ...]。
    若识别不到章节标题，则整篇作为单章返回（标题为「正文」）。
    """
    lines = text.splitlines()
    chapters: List[Tuple[str, List[str]]] = []
    current_title = None
    current_body: List[str] = []

    for line in lines:
        if _is_chapter_heading(line):
            if current_title is not None or current_body:
                chapters.append((current_title or "正文", current_body))
            current_title = line.strip()
            current_body = []
        else:
            current_body.append(line)

    if current_title is not None or current_body:
        chapters.append((current_title or "正文", current_body))

    # 清理空白章节，正文拼回字符串
    result: List[Tuple[str, str]] = []
    for title, body in chapters:
        body_text = "\n".join(body).strip()
        if body_text:
            result.append((title, body_text))

    if not result:
        result = [("正文", text.strip())]
    return result


def paragraphs(chapter_text: str) -> List[str]:
    """把章节正文拆成段落（按空行或换行）。"""
    raw = re.split(r"\n\s*\n|\n", chapter_text)
    return [p.strip() for p in raw if p.strip()]
