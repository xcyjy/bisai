"""拆集引擎：把整部剧本切成 N 集短剧，每集带 钩子 / 扣子 / 时长 / 体检。

这是面向短剧公司/编剧的"产能"核心能力——把短剧的行业铁律算法化：
- 每集控制在 2~3 分钟（按口播字数估时长）
- 开场有钩子（前几秒抓人）
- 集尾留扣子（逼着看下一集）
- 自动体检：缺钩子 / 缺扣子 / 超时长 / 无互动 一眼可见

规则引擎离线可跑（免费 / 确定性）；云端配置大模型后可在此基础上做 AI 精修。
"""
from __future__ import annotations

from typing import Dict, List

# 口播节奏：约 5 字/秒（≈300 字/分钟）；动作/旁白叙述按 ~12 字/秒
SPOKEN_CPS = 5.0
ACTION_CPS = 12.0
DEFAULT_TARGET_MIN = 2.5
MIN_SEC = 80      # 低于此判为"过短"
MAX_SEC = 200     # 高于此判为"超时长"


def _scene_metrics(scene: dict) -> dict:
    spoken = 0
    action = 0
    speakers = set()
    spoken_lines: List[str] = []
    for el in scene.get("elements", []):
        t = el.get("type")
        text = (el.get("text") or "").strip()
        if t in ("dialogue", "voiceover"):
            spoken += len(text)
            if text:
                spoken_lines.append(text)
            if el.get("character"):
                speakers.add(el["character"])
        else:
            action += len(text)
    seconds = spoken / SPOKEN_CPS + action / ACTION_CPS
    return {
        "seconds": seconds,
        "spoken": spoken,
        "speakers": speakers,
        "spoken_lines": spoken_lines,
        "first_spoken": spoken_lines[0] if spoken_lines else "",
        "last_spoken": spoken_lines[-1] if spoken_lines else "",
    }


def _fmt_dur(sec: float) -> str:
    sec = int(round(sec))
    m, s = divmod(sec, 60)
    return f"{m}分{s:02d}秒" if m else f"{s}秒"


def split_into_episodes(doc: dict, target_minutes: float = DEFAULT_TARGET_MIN) -> List[dict]:
    """把剧本 doc 的 scenes 贪心打包成若干集。"""
    scenes = doc.get("scenes", [])
    if not scenes:
        return []
    target = max(60.0, target_minutes * 60)

    # 贪心分组：累计时长达到目标即收一集（保证每集至少 1 场）
    groups: List[List[dict]] = []
    cur: List[dict] = []
    cur_sec = 0.0
    for sc in scenes:
        m = _scene_metrics(sc)
        cur.append(sc)
        cur_sec += m["seconds"]
        if cur_sec >= target:
            groups.append(cur)
            cur, cur_sec = [], 0.0
    if cur:
        # 末尾零头并入上一集（避免出现 10 秒的尾集）
        if groups and cur_sec < target * 0.5:
            groups[-1].extend(cur)
        else:
            groups.append(cur)

    episodes: List[dict] = []
    for i, grp in enumerate(groups, start=1):
        ms = [_scene_metrics(sc) for sc in grp]
        seconds = sum(m["seconds"] for m in ms)
        spoken = sum(m["spoken"] for m in ms)
        speakers = set().union(*(m["speakers"] for m in ms)) if ms else set()

        # 钩子：本集第一句台词；没有就用第一场梗概
        hook = next((m["first_spoken"] for m in ms if m["first_spoken"]), "")
        if not hook:
            hook = (grp[0].get("synopsis") or "").strip()
        # 扣子：本集最后一句台词
        cliff = ""
        for m in reversed(ms):
            if m["last_spoken"]:
                cliff = m["last_spoken"]
                break

        checks = {
            "has_hook": bool(hook),
            "has_cliffhanger": bool(cliff),
            "within_duration": MIN_SEC <= seconds <= MAX_SEC,
            "has_interaction": len(speakers) >= 2,
        }
        warnings = []
        if not checks["has_hook"]:
            warnings.append("开场缺钩子")
        if not checks["has_cliffhanger"]:
            warnings.append("集尾缺扣子")
        if seconds > MAX_SEC:
            warnings.append("时长偏长，建议拆分")
        elif seconds < MIN_SEC:
            warnings.append("时长偏短，建议合并")
        if not checks["has_interaction"]:
            warnings.append("缺人物互动/冲突")

        title = (grp[0].get("synopsis") or "").strip()
        if not title:
            loc = grp[0].get("heading", {}).get("location", "")
            title = loc or f"第{i}集"
        title = title[:14]

        episodes.append({
            "episode_number": i,
            "title": title,
            "scene_numbers": [sc.get("scene_number") for sc in grp],
            "hook": hook,
            "cliffhanger": cliff,
            "est_seconds": int(round(seconds)),
            "duration_text": _fmt_dur(seconds),
            "spoken_chars": spoken,
            "checks": checks,
            "warnings": warnings,
        })
    return episodes


def episodes_summary(episodes: List[dict]) -> Dict[str, int]:
    """整体体检概览。"""
    total = len(episodes)
    healthy = sum(1 for e in episodes if not e["warnings"])
    return {
        "count": total,
        "healthy": healthy,
        "needs_fix": total - healthy,
        "avg_seconds": int(round(sum(e["est_seconds"] for e in episodes) / total)) if total else 0,
    }
