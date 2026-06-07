"""计费：大模型 token -> 美元成本。用于内部审计与定价参考。

价格为官方公开价（每 1M token，单位美元），核对自 Claude 平台文档。
仅作内部成本记录；对用户始终按"1 次 AI 转换 = 1 积分"计量。
"""
from __future__ import annotations

# model_id -> (输入价 $/1M, 输出价 $/1M)
PRICES = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}


def cost_usd(model: str, in_tokens: int, out_tokens: int) -> float:
    """根据 token 用量折算美元成本（未知模型按 Opus 价兜底）。"""
    pin, pout = PRICES.get(model, PRICES["claude-opus-4-8"])
    return round(in_tokens / 1_000_000 * pin + out_tokens / 1_000_000 * pout, 6)
