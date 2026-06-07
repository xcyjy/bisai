"""可用模型列表：拉取中转站 /v1/models，白名单过滤出本项目能用的 Claude 系，并分档。

中转站实测仅 Anthropic 协议（/v1/messages）可用，故只暴露 claude-*；
按能力分三档（质量/均衡/经济）供前端下拉与「按任务路由模型」。
"""
from __future__ import annotations

import json
import urllib.request as _u
from typing import List

from .core.config import settings

# 模型 -> (展示名, 档位, 排序权重) 白名单。未列出的 claude-* 归入「其他」。
_TIER = {
    "claude-opus-4-8": ("Opus 4.8", "质量", 10),
    "claude-opus-4-7": ("Opus 4.7", "质量", 9),
    "claude-opus-4-6": ("Opus 4.6", "质量", 8),
    "claude-sonnet-4-6": ("Sonnet 4.6", "均衡", 6),
    "claude-haiku-4-5-20251001": ("Haiku 4.5", "经济", 4),
    "claude-haiku-4-5": ("Haiku 4.5", "经济", 4),
}
_TIER_DESC = {"质量": "分场最准，推荐成片", "均衡": "质量/成本平衡", "经济": "快而省，适合量产"}


def _fetch_relay_model_ids() -> List[str]:
    base = settings.anthropic_base_url.rstrip("/")
    req = _u.Request(
        f"{base}/v1/models",
        headers={"Authorization": f"Bearer {settings.anthropic_api_key}"},
    )
    opener = _u.build_opener(_u.ProxyHandler({}))
    with opener.open(req, timeout=15) as r:
        data = json.loads(r.read().decode("utf-8"))
    return [m.get("id", "") for m in data.get("data", [])]


def list_models() -> dict:
    """返回 {available, models:[{id,label,tier,desc}], note}。

    无 key/base_url 时 available=False（前端隐藏 AI/Agent 模型下拉）。
    """
    if not (settings.anthropic_api_key and settings.anthropic_base_url):
        return {"available": False, "models": [], "note": "未配置 AI 入口，仅离线引擎可用"}

    try:
        ids = _fetch_relay_model_ids()
    except Exception as e:  # 中转站不可达 → 回退到默认模型，AI 仍可用
        default = settings.script_model
        label, tier, _ = _TIER.get(default, (default, "质量", 5))
        return {
            "available": True,
            "models": [{"id": default, "label": label, "tier": tier,
                        "desc": _TIER_DESC.get(tier, "")}],
            "note": f"模型列表获取失败（{type(e).__name__}），已回退默认模型",
        }

    out = []
    for mid in ids:
        if mid in _TIER:
            label, tier, w = _TIER[mid]
        elif mid.startswith("claude-"):
            label, tier, w = mid, "其他", 1
        else:
            continue  # 非 Claude（如 gpt-*）此中转站走不通，剔除
        out.append({"id": mid, "label": label, "tier": tier,
                    "desc": _TIER_DESC.get(tier, ""), "_w": w})
    out.sort(key=lambda m: -m["_w"])
    for m in out:
        m.pop("_w", None)
    return {"available": True, "models": out, "note": ""}
