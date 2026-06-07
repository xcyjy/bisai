"""剧本数据结构（pydantic 模型）。

对应文档《02_YAML_Schema设计文档》。这些模型同时承担两个职责：
1. 作为 Claude 结构化输出（messages.parse）的 output_format，强约束 LLM 产出；
2. 作为校验层，保证最终导出的 YAML 合法。
"""
from __future__ import annotations

from typing import List, Optional
from typing_extensions import Literal

from pydantic import BaseModel, Field


# ---- LLM 抽取/转换阶段使用的结构（与 Claude structured output 对齐）----

class Character(BaseModel):
    """全局人物表中的一个角色。"""
    id: str = Field(description="全局唯一ID，如 char_01")
    name: str = Field(description="角色名")
    description: str = Field(description="一句话人物简介")


class CharacterList(BaseModel):
    characters: List[Character]


class Heading(BaseModel):
    """场头（行业 Slug Line）。"""
    int_ext: Literal["INT", "EXT", "INT/EXT"] = Field(description="内景INT/外景EXT")
    location: str = Field(description="地点")
    time: str = Field(description="时间，如 白天/夜晚/黄昏/第二天清晨")


class SceneElement(BaseModel):
    """场内的一个有序元素。顺序即叙事节奏，必须保持原始先后。"""
    type: Literal["action", "dialogue", "voiceover", "transition"] = Field(
        description="action=动作描述; dialogue=对白; voiceover=旁白/心理独白; transition=转场"
    )
    text: str = Field(description="该元素的文本内容")
    character: Optional[str] = Field(
        default=None, description="dialogue/voiceover 的说话人；其他类型留空"
    )
    parenthetical: Optional[str] = Field(
        default=None, description="表演提示（怎么说），如 冷冷地；可留空"
    )


class Scene(BaseModel):
    """一场戏（一个连续的时间+地点）。"""
    heading: Heading
    synopsis: str = Field(description="本场一句话梗概，便于作者快速浏览/编辑")
    elements: List[SceneElement] = Field(description="有序的剧本元素列表")


class SceneList(BaseModel):
    """单章转换的产出。"""
    scenes: List[Scene]


class Episode(BaseModel):
    """短剧的一集（由若干连续场打包而成）。

    短剧是本工具的核心产物：剧本转换完成后按口播时长贪心拆集，
    每集必须自带开场钩子（hook）与集尾扣子（cliffhanger）。
    """
    episode_number: int = Field(description="集号，从 1 递增")
    title: str = Field(description="本集标题（取自首场梗概）")
    scene_numbers: List[int] = Field(description="本集包含的场号（引用 scenes）")
    hook: str = Field(default="", description="开场钩子：前几秒抓人的台词/梗概")
    cliffhanger: str = Field(default="", description="集尾扣子：逼着观众看下一集的悬念")
    est_seconds: int = Field(default=0, description="预估时长（秒），按口播字数估算")
    duration_text: str = Field(default="", description="时长的可读文本，如 2分30秒")


# ---- 最终装配 / 校验 ----

VALID_ELEMENT_TYPES = {"action", "dialogue", "voiceover", "transition"}


def validate_screenplay(doc: dict) -> List[str]:
    """对装配好的剧本 dict 做一致性校验，返回问题列表（空=合法）。"""
    problems: List[str] = []
    scenes = doc.get("scenes", [])

    # 人物名集合（含别名），用于校验对白归属
    known_names = set()
    for c in doc.get("characters", []):
        known_names.add(c.get("name"))
        for a in c.get("aliases", []) or []:
            known_names.add(a)

    expected_no = 1
    for s in scenes:
        no = s.get("scene_number")
        if no != expected_no:
            problems.append(f"场号不连续：期望 {expected_no}，实际 {no}")
        expected_no += 1

        elements = s.get("elements", [])
        if not elements:
            problems.append(f"第 {no} 场为空场（无任何元素）")

        for el in elements:
            t = el.get("type")
            if t not in VALID_ELEMENT_TYPES:
                problems.append(f"第 {no} 场存在非法元素类型：{t}")
            if t in ("dialogue", "voiceover"):
                ch = el.get("character")
                if not ch:
                    problems.append(f"第 {no} 场的 {t} 缺少说话人")
                elif known_names and ch not in known_names:
                    problems.append(f"第 {no} 场说话人“{ch}”不在人物表中")

    # ---- 分集校验（短剧核心结构；仅在已拆集时执行）----
    # 这里只校验「结构完整性」——集号连续、场被完整且不重复地收录。
    # 钩子/扣子/时长是否达标属于内容健康度，由 episodes.py 以 warnings 形式给出，
    # 不在此判为硬错误（避免一集恰好收在动作镜头时被误判为无效）。
    episodes = doc.get("episodes", [])
    if episodes:
        all_scene_nos = [s.get("scene_number") for s in scenes]
        covered: List[int] = []
        exp_ep = 1
        for ep in episodes:
            en = ep.get("episode_number")
            if en != exp_ep:
                problems.append(f"集号不连续：期望 {exp_ep}，实际 {en}")
            exp_ep += 1
            sns = ep.get("scene_numbers") or []
            if not sns:
                problems.append(f"第 {en} 集没有任何场")
            covered.extend(sns)
        # 覆盖完整性：每个场恰好属于一集
        missing = [n for n in all_scene_nos if n not in covered]
        if missing:
            problems.append(f"以下场未被任何集收录：{missing}")
        if len(covered) != len(set(covered)):
            problems.append("存在被多集重复收录的场")
    return problems
