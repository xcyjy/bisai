"""导出：把装配好的剧本 dict 序列化为 YAML。

注意：LLM 不直接产出 YAML（缩进敏感易错），而是产出结构化对象，
由这里统一用 PyYAML 序列化，兼顾稳定性与可读性。
"""
from __future__ import annotations

import yaml


class _OrderedDumper(yaml.SafeDumper):
    pass


def to_yaml(doc: dict) -> str:
    return yaml.dump(
        doc,
        Dumper=_OrderedDumper,
        allow_unicode=True,   # 保留中文，不转义成 \uXXXX
        sort_keys=False,      # 保持我们装配的字段顺序
        default_flow_style=False,
        width=80,
    )
