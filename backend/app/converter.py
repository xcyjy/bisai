"""转换核心：小说章节 -> 结构化场景。

两条路径：
- 在线（有 ANTHROPIC_API_KEY）：调用 Claude，用结构化输出强约束产出剧本元素；
- 离线（无 key / FORCE_OFFLINE）：纯规则引擎，保证 demo 在任何环境都能跑通。
"""
from __future__ import annotations

import re
from typing import List, Optional

from .chapters import paragraphs
from .core.config import settings
from .schema import (
    Character,
    CharacterList,
    Heading,
    Scene,
    SceneElement,
    SceneList,
    StoryMeta,
)


def _model() -> str:
    return settings.script_model

# ---- 转换铁律（注入到 Prompt，也是离线规则的设计依据）----
RULES = """你是一位专业编剧，正在把小说改编成剧本初稿。严格遵守以下铁律：
1. Show, don't tell：剧本只能呈现“看得见的动作 + 听得到的声音”。
2. 心理描写（他想/他明白/他没想到/内心独白）→ 转成 voiceover（画外音），归到对应角色，绝不能当作 action。
3. 对白 → dialogue，必须标明 character（说话人）；“怎么说”的提示放进 parenthetical。
   若对白是电话另一头/画外/旁人听不到，用 extension 标注（INTO PHONE / O.S. / V.O.）。
4. 环境/动作描写 → action。
5. 时间或地点发生变化 → 切分为新的一场（scene）。
6. 忠于原文：不要臆造原文没有的情节；可适当精简冗长的环境描写。
7. elements 必须保持原文的先后顺序（顺序=叙事节奏）。

【专业增强字段，尽力填写，无法判断就留空，绝不臆造】
- heading.day_night：把 time 归一化为 DAY/NIGHT/DAWN/DUSK，供制片排期。
- scene.beat：该场叙事节拍（setup/inciting_incident/turning_point/midpoint/climax/resolution）。
- scene.breakdown：制片分解——props(关键道具)/wardrobe(服装)/vehicles(交通工具)/sfx(雨雪爆破等氛围特效)/extras(群演)。
  （cast 由程序自动统计，你不必填。）
"""

# 日/夜归一化提示词（离线与 AI 缺失时的确定性兜底）。先匹配更具体的，再匹配宽泛的。
_DAY_NIGHT_CUES = [
    ("DAWN", ["黎明", "拂晓", "破晓", "天刚亮", "凌晨"]),
    ("DUSK", ["黄昏", "傍晚", "日暮", "暮色", "夕阳", "薄暮"]),
    ("NIGHT", ["夜", "晚", "深夜", "午夜", "子夜", "星", "月"]),
    ("DAY", ["清晨", "早晨", "上午", "中午", "正午", "下午", "白天", "晌午", "日间"]),
]


def derive_day_night(time_text: str) -> Optional[str]:
    """把自由文本时间归一化为 DAY/NIGHT/DAWN/DUSK，无法判断返回 None。"""
    if not time_text:
        return None
    for label, cues in _DAY_NIGHT_CUES:
        if any(cue in time_text for cue in cues):
            return label
    return None

# 心理活动 / 议论的提示词（离线规则用）
_PSYCH_CUES = ["想", "心里", "心想", "觉得", "没想到", "明白", "意识到", "仿佛",
               "似乎", "记得", "回忆", "暗自", "默默", "知道", "感到", "希望", "后悔"]
# 时间/地点切换的提示词（离线规则用）
_TIME_CUES = ["第二天", "次日", "傍晚", "黄昏", "清晨", "夜里", "深夜", "翌日",
              "几天后", "一周后", "与此同时", "另一边", "回到", "三天后", "多年后", "片刻后"]
# 引号
_QUOTE_RE = re.compile(r"[“\"「](.+?)[”\"」]")


def _is_offline(use_ai: bool) -> bool:
    """是否走离线规则引擎。use_ai=False 强制离线；use_ai=True 但未配置 key 也回落离线。"""
    if not use_ai:
        return True
    return not settings.ai_available


# =========================================================
# 在线路径（Claude）
# =========================================================

def _client():
    import anthropic
    kwargs = {"api_key": settings.anthropic_api_key}
    if settings.anthropic_base_url:
        kwargs["base_url"] = settings.anthropic_base_url  # 兼容中转站
    return anthropic.Anthropic(**kwargs)


def _track(usage: Optional[dict], resp) -> None:
    """累加一次调用的 token 用量到 usage 累加器。"""
    if usage is None:
        return
    u = getattr(resp, "usage", None)
    if u is not None:
        usage["in_tokens"] = usage.get("in_tokens", 0) + getattr(u, "input_tokens", 0)
        usage["out_tokens"] = usage.get("out_tokens", 0) + getattr(u, "output_tokens", 0)


def _structured(client, system: str, prompt: str, output_model, max_tokens: int,
                usage: Optional[dict] = None):
    """用 tool-use（函数调用）拿结构化输出，并用 pydantic 校验。

    为什么不用 messages.parse(output_format=...)：那依赖 Anthropic 结构化输出 beta，
    很多中转站不支持（会把 JSON 包在 ```代码块里返回导致解析失败）。tool-use 是 GA 能力，
    中转站普遍支持，强制 tool_choice 后能稳定拿到干净 JSON。
    """
    tool = {
        "name": "emit_result",
        "description": f"输出结构化结果（{output_model.__name__}）",
        "input_schema": output_model.model_json_schema(),
    }
    resp = client.messages.create(
        model=_model(),
        max_tokens=max_tokens,
        system=system,
        tools=[tool],
        tool_choice={"type": "tool", "name": "emit_result"},
        messages=[{"role": "user", "content": prompt}],
    )
    _track(usage, resp)
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use":
            return output_model.model_validate(block.input)
    return None


def _extract_characters_online(full_text: str, usage: Optional[dict] = None) -> List[Character]:
    client = _client()
    prompt = (
        "下面是一篇小说。请抽取主要人物，生成全局人物表。"
        "为每个角色分配唯一 id（如 char_01），给出 name 和一句话 description。\n\n"
        f"小说全文：\n{full_text[:12000]}"
    )
    out = _structured(
        client,
        system="你是专业编剧助手，擅长从小说中梳理人物。",
        prompt=prompt,
        output_model=CharacterList,
        max_tokens=4000,
        usage=usage,
    )
    return out.characters if out else []


def _extract_story_meta_online(full_text: str, usage: Optional[dict] = None) -> StoryMeta:
    client = _client()
    prompt = (
        "下面是一篇小说。请用一句话 logline（主角+核心困境+悬念）概括故事，"
        "并判断其 genre（类型，如 都市/悬疑/言情/古装）与 tone（基调）。\n\n"
        f"小说全文：\n{full_text[:12000]}"
    )
    out = _structured(
        client,
        system="你是资深剧本策划，擅长一句话提炼故事主线。",
        prompt=prompt,
        output_model=StoryMeta,
        max_tokens=1000,
        usage=usage,
    )
    return out or StoryMeta()


def _convert_chapter_online(
    chapter_text: str, characters: List[Character], usage: Optional[dict] = None
) -> List[Scene]:
    client = _client()
    char_hint = "；".join(f"{c.name}({c.description})" for c in characters) or "（无）"
    prompt = (
        f"{RULES}\n\n"
        f"已知人物表（对白/旁白的 character 必须使用这些名字）：{char_hint}\n\n"
        "请把下面这一章小说转换为结构化剧本。按时间/地点切分为若干场，"
        "每场给出 heading、synopsis 和有序的 elements。\n\n"
        f"本章正文：\n{chapter_text}"
    )
    out = _structured(
        client,
        system="你是专业编剧，把小说改编成规范的剧本初稿。",
        prompt=prompt,
        output_model=SceneList,
        max_tokens=16000,
        usage=usage,
    )
    return out.scenes if out else []


# =========================================================
# 离线路径（规则引擎）
# =========================================================

# 常见的“非人名”词（副词/虚词/常见双字词），用于过滤误抽
_NAME_STOP = {
    "轻声", "低声", "大声", "冷冷", "淡淡", "喃喃", "默默", "缓缓", "轻轻", "连忙",
    "急忙", "笑着", "接着", "继续", "小声", "什么", "自己", "他们", "我们", "你们",
    "起来", "没有", "知道", "时候", "现在", "已经", "可是", "但是", "然后", "这样",
    "那样", "如果", "于是", "忽然", "终于", "一个", "那把", "这座", "声音",
}
# 跟在人名后、能较可靠指示“这是个人”的动词
_PERSON_VERBS = ("说道", "说", "道", "问道", "问", "答道", "喊道", "笑道", "叹道",
                 "走", "站", "坐", "推开", "提着", "撑着", "攥", "拆开", "点点头",
                 "抬起头", "回过头")


def _extract_characters_offline(full_text: str) -> List[Character]:
    """启发式抽取人物名：

    1) 统计全文 2 字汉字组合的出现频次（主角名通常高频复现）；
    2) 仅保留“至少出现一次在人物动词之前”的组合（偏向人名，排除普通词）；
    3) 过滤停用词，按频次取前若干。
    """
    from collections import Counter

    # 全文 2 字滑窗频次
    bigrams: Counter = Counter()
    for run in re.findall(r"[一-龥]+", full_text):
        for i in range(len(run) - 1):
            bigrams[run[i:i + 2]] += 1

    # 出现在人物动词前的 2 字组合（定长 2，避免贪婪多吞一个字）
    verb_alt = "|".join(_PERSON_VERBS)
    near_verb = set(re.findall(rf"([一-龥]{{2}})(?:{verb_alt})", full_text))

    def pick(min_count: int):
        cands = [
            (name, cnt) for name, cnt in bigrams.items()
            if cnt >= min_count and name not in _NAME_STOP and name in near_verb
        ]
        cands.sort(key=lambda kv: -kv[1])
        return cands

    ranked = pick(3) or pick(2) or pick(1)
    chars: List[Character] = []
    for i, (name, _) in enumerate(ranked[:8], start=1):
        chars.append(Character(id=f"char_{i:02d}", name=name, description="（自动识别，待人工补充）"))
    return chars


# 用一个可变容器在逐段处理中记忆“上一个说话人”，实现对白交替
_last_speaker = {"name": None}


def _guess_speaker(text: str, characters: List[Character]) -> Optional[str]:
    # 1) 段落里直接出现的角色名优先
    for c in characters:
        if c.name in text:
            _last_speaker["name"] = c.name
            return c.name
    # 2) 否则在两个主要角色间交替（对话往往你一言我一语）
    if len(characters) >= 2:
        last = _last_speaker["name"]
        nxt = characters[1].name if last == characters[0].name else characters[0].name
        _last_speaker["name"] = nxt
        return nxt
    if characters:
        return characters[0].name
    return "（待定）"


def _convert_chapter_offline(chapter_text: str, characters: List[Character]) -> List[Scene]:
    paras = paragraphs(chapter_text)
    scenes: List[Scene] = []
    current_elements: List[SceneElement] = []
    time_label = "白天"

    def flush(time_lbl: str):
        if current_elements:
            scenes.append(Scene(
                heading=Heading(
                    int_ext="INT", location="待定地点", time=time_lbl,
                    day_night=derive_day_night(time_lbl),
                ),
                synopsis="（自动生成，建议人工补充梗概）",
                elements=list(current_elements),
            ))
            current_elements.clear()

    for para in paras:
        # 时间/地点切换 -> 新场
        if any(cue in para[:8] for cue in _TIME_CUES) and current_elements:
            new_time = next((cue for cue in _TIME_CUES if cue in para[:8]), time_label)
            flush(time_label)
            time_label = new_time

        quote = _QUOTE_RE.search(para)
        if quote:
            speaker = _guess_speaker(para, characters)
            current_elements.append(SceneElement(
                type="dialogue", character=speaker, text=quote.group(1)
            ))
        elif any(cue in para for cue in _PSYCH_CUES):
            speaker = _guess_speaker(para, characters)
            current_elements.append(SceneElement(
                type="voiceover", character=speaker, text=para
            ))
        else:
            current_elements.append(SceneElement(type="action", text=para))

    flush(time_label)
    if not scenes:
        scenes.append(Scene(
            heading=Heading(int_ext="INT", location="待定地点", time="白天"),
            synopsis="（空章节）",
            elements=[SceneElement(type="action", text=chapter_text[:200])],
        ))
    return scenes


# =========================================================
# 对外统一接口
# =========================================================

def extract_characters(
    full_text: str, use_ai: bool = False, usage: Optional[dict] = None
) -> List[Character]:
    if _is_offline(use_ai):
        return _extract_characters_offline(full_text)
    try:
        return _extract_characters_online(full_text, usage)
    except Exception:
        return _extract_characters_offline(full_text)


def extract_story_meta(
    full_text: str, use_ai: bool = False, usage: Optional[dict] = None
) -> StoryMeta:
    """抽取故事级元信息（logline/genre/tone）。离线无法可靠生成，返回空。"""
    if _is_offline(use_ai):
        return StoryMeta()
    try:
        return _extract_story_meta_online(full_text, usage)
    except Exception:
        return StoryMeta()


def convert_chapter(
    chapter_text: str,
    characters: List[Character],
    use_ai: bool = False,
    usage: Optional[dict] = None,
) -> List[Scene]:
    if _is_offline(use_ai):
        return _convert_chapter_offline(chapter_text, characters)
    try:
        return _convert_chapter_online(chapter_text, characters, usage)
    except Exception:
        # 在线失败兜底为离线，保证不中断
        return _convert_chapter_offline(chapter_text, characters)


def engine_mode(use_ai: bool = False) -> str:
    return "offline-rules" if _is_offline(use_ai) else f"claude:{_model()}"
