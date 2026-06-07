"""Agent 结果缓存（语义级）。

key = sha256(model | schema_version | agent | 输入文本) -> 结构化结果 dict。
命中即 0 token、毫秒级返回。内存 + 磁盘(backend/.cache/agents.json)持久化，跨重启有效。

注意：这是「结果缓存」；另一层「Prompt 缓存」由 orchestrator 在调用时给静态前缀打
cache_control 实现，体现为 usage.cache_read_input_tokens，与本模块互补。
"""
from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Optional

_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
_CACHE_FILE = _CACHE_DIR / "agents.json"
_lock = threading.Lock()


def make_key(model: str, schema_version: str, agent: str, payload: str) -> str:
    h = hashlib.sha256()
    h.update(f"{model}\x1f{schema_version}\x1f{agent}\x1f{payload}".encode("utf-8"))
    return h.hexdigest()


class ResultCache:
    def __init__(self) -> None:
        self._mem: dict = {}
        self._load()

    def _load(self) -> None:
        try:
            if _CACHE_FILE.exists():
                self._mem = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            self._mem = {}

    def get(self, key: str) -> Optional[dict]:
        return self._mem.get(key)

    def put(self, key: str, value: dict) -> None:
        with _lock:
            self._mem[key] = value
            try:
                _CACHE_DIR.mkdir(parents=True, exist_ok=True)
                _CACHE_FILE.write_text(
                    json.dumps(self._mem, ensure_ascii=False), encoding="utf-8"
                )
            except Exception:
                pass  # 缓存写盘失败不影响主流程

    def stats(self) -> dict:
        return {"entries": len(self._mem)}


cache = ResultCache()
