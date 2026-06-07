"""剧本数据结构（pydantic 模型）。

对应文档《06_剧本YAML_Schema定义与产业化设计》。这些模型同时承担两个职责：
1. 作为 Claude 结构化输出（messages.parse）的 output_format，强约束 LLM 产出；
2. 作为校验层，保证最终导出的 YAML 合法。

v1.0 起按影视/短剧工业流程分三层丰富（全部可选、可降级）：
- 创作层（编剧）：logline/genre、act/beat、人物 role/arc、对白 extension。
- 制片层（统筹）：heading.day_night、scene.breakdown 分解表、est_duration_sec 时长。
- 微短剧层（操盘）：episode/hook/cliffhanger/pay_point/highlights。
离线引擎只填能确定性推导的字段，其余留空；AI 引擎尽量补全。
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
    description: str = Field(default="", description="一句话人物简介")
    aliases: List[str] = Field(
        default_factory=list, description="别名/外号，用于跨章消歧，如 [小林, 林记者]"
    )
    role: Optional[Literal["protagonist", "antagonist", "supporting", "minor"]] = Field(
        default=None, description="叙事角色：主角/反派/配角/龙套，便于选角与重点把控"
    )
    gender: Optional[str] = Field(default=None, description="性别，供选角参考，可留空")
    age: Optional[str] = Field(default=None, description="年龄/年龄段，供选角参考，可留空")
    arc: Optional[str] = Field(default=None, description="人物弧光：一句话概括其转变，可留空")


class CharacterList(BaseModel):
    characters: List[Character]


class StoryMeta(BaseModel):
    """故事级元信息（AI 通读全文后产出，帮助作者快速把握主线与定位）。"""
    logline: str = Field(default="", description="一句话故事（主角+困境+悬念）")
    genre: str = Field(default="", description="类型，如 都市/悬疑/言情/古装")
    tone: str = Field(default="", description="基调，如 写实克制/热血爽感/暗黑悬疑")


class Heading(BaseModel):
    """场头（行业 Slug Line）。"""
    int_ext: Literal["INT", "EXT", "INT/EXT"] = Field(description="内景INT/外景EXT")
    location: str = Field(description="地点")
    time: str = Field(description="时间，自由文本，如 白天/夜晚/黄昏/第二天清晨/雨夜")
    day_night: Optional[Literal["DAY", "NIGHT", "DAWN", "DUSK"]] = Field(
        default=None, description="归一化的日/夜，供制片排期与灯光统筹；由 time 推导"
    )


class SourceRef(BaseModel):
    """溯源：本场对应原文位置，支撑「原文↔剧本对照」与情节保留率度量。"""
    chapter: str = Field(default="", description="对应原著章节标题")
    excerpt: str = Field(default="", description="对应原文起始片段")


class Breakdown(BaseModel):
    """场景制片分解表（Script Breakdown）——一份剧本直接产出通告单的基础数据。

    cast 由程序确定性计算（场内出现的角色）；其余元素由 AI 尽力抽取，离线留空。
    """
    cast: List[str] = Field(default_factory=list, description="本场出场（有台词/有动作）的角色")
    extras: List[str] = Field(default_factory=list, description="群演/背景人物")
    props: List[str] = Field(default_factory=list, description="关键道具")
    wardrobe: List[str] = Field(default_factory=list, description="服装造型")
    vehicles: List[str] = Field(default_factory=list, description="交通工具")
    sfx: List[str] = Field(default_factory=list, description="特殊效果/特技/氛围（雨、雪、爆破等）")


class SceneElement(BaseModel):
    """场内的一个有序元素。顺序即叙事节奏，必须保持原始先后。"""
    type: Literal["action", "dialogue", "voiceover", "transition", "shot", "subheading"] = Field(
        description=(
            "action=动作描述; dialogue=对白; voiceover=旁白/心理独白(画外音); "
            "transition=转场; shot=镜头/景别提示(可选); subheading=场内次场头(时间推移等)"
        )
    )
    text: str = Field(description="该元素的文本内容")
    character: Optional[str] = Field(
        default=None, description="dialogue/voiceover 的说话人；其他类型留空"
    )
    parenthetical: Optional[str] = Field(
        default=None, description="表演提示（怎么说），如 冷冷地；可留空"
    )
    extension: Optional[Literal[
        "V.O.", "O.S.", "O.C.", "CONT'D", "INTO PHONE", "FILTERED", "SUBTITLE"
    ]] = Field(
        default=None,
        description="对白声音处理：V.O.画外音/O.S.画外/CONT'D接续/INTO PHONE电话/FILTERED滤音；可留空",
    )


class Scene(BaseModel):
    """一场戏（一个连续的时间+地点）。"""
    heading: Heading
    synopsis: str = Field(description="本场一句话梗概，便于作者快速浏览/编辑")
    elements: List[SceneElement] = Field(description="有序的剧本元素列表")
    # ---- 创作层（结构）----
    act: Optional[int] = Field(default=None, description="所属幕：1/2/3（三幕结构），可留空")
    beat: Optional[str] = Field(
        default=None,
        description="叙事节拍，如 setup/inciting_incident/turning_point/midpoint/climax/resolution",
    )
    # ---- 制片层 ----
    breakdown: Optional[Breakdown] = Field(default=None, description="制片分解表")
    est_duration_sec: Optional[int] = Field(
        default=None, description="预估时长(秒)，用于时长体检；由程序按元素体量估算"
    )
    source_ref: Optional[SourceRef] = Field(default=None, description="原文溯源")
    # ---- 微短剧层（script_type=short_drama 时有意义）----
    episode: Optional[int] = Field(default=None, description="集号（微短剧分集）")
    hook: Optional[str] = Field(default=None, description="开场钩子（黄金3秒）")
    cliffhanger: Optional[str] = Field(default=None, description="集尾扣子/悬念")
    pay_point: Optional[bool] = Field(default=None, description="是否付费卡点")
    highlights: Optional[List[str]] = Field(
        default=None, description="爽点/反转/名场面标签，如 [反转, 打脸]"
    )


class SceneList(BaseModel):
    """单章转换的产出。"""
    scenes: List[Scene]


# ---- 最终装配 / 校验 ----

VALID_ELEMENT_TYPES = {"action", "dialogue", "voiceover", "transition", "shot", "subheading"}
VALID_DAY_NIGHT = {"DAY", "NIGHT", "DAWN", "DUSK"}


def validate_screenplay(doc: dict) -> List[str]:
    """对装配好的剧本 dict 做一致性校验，返回问题列表（空=合法）。

    设计原则：核心约束严格（场号/人物归属/元素类型），专业增强字段宽容
    （存在即校验取值，不强制存在），保证离线产出与 AI 产出都能通过。
    """
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

        # 专业增强字段：存在才校验取值（不强制）
        dn = (s.get("heading") or {}).get("day_night")
        if dn is not None and dn not in VALID_DAY_NIGHT:
            problems.append(f"第 {no} 场 day_night 非法：{dn}")
        ep = s.get("episode")
        if ep is not None and (not isinstance(ep, int) or ep < 1):
            problems.append(f"第 {no} 场 episode 非法：{ep}")

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
    return problems
