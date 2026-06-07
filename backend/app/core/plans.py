"""套餐与积分包定义（商品目录）。

放在代码里便于本地直接跑；规模化后可迁移到 plans 表由后台配置。
1 次 AI 转换 = 1 积分；离线"快速版"不扣分。
"""
from __future__ import annotations

from typing import Dict, Optional

# SKU -> 商品定义
SKUS: Dict[str, dict] = {
    # ---- 会员套餐（按月） ----
    "pro_monthly": {
        "kind": "plan",
        "title": "Pro 会员（月）",
        "amount_cny": 39.0,
        "grant_plan": "pro",
        "grant_days": 30,
        "grant_credits": 30,   # 开通即到账 30 积分
        "desc": "AI 精修引擎 · 每月 30 次 · 作品不限量 · Word 导出",
    },
    # ---- 积分包（一次性，叠加） ----
    "pack_10": {
        "kind": "credits",
        "title": "积分包 · 10 次",
        "amount_cny": 19.0,
        "grant_plan": "",
        "grant_days": 0,
        "grant_credits": 10,
        "desc": "10 次 AI 转换，永久有效",
    },
    "pack_50": {
        "kind": "credits",
        "title": "积分包 · 50 次",
        "amount_cny": 79.0,
        "grant_plan": "",
        "grant_days": 0,
        "grant_credits": 50,
        "desc": "50 次 AI 转换，更划算",
    },
}


def get_sku(sku: str) -> Optional[dict]:
    return SKUS.get(sku)


def catalog() -> list[dict]:
    """对前端暴露的商品列表。"""
    return [{"sku": k, **v} for k, v in SKUS.items()]
