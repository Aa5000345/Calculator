"""命令使用频率统计：为命令面板提供"越用越顺手"的排序依据。

存储到 ~/.multicalc/usage.json。
结构：{"<command_id>": {"count": N, "last": ts}}
"""
from __future__ import annotations

import json
import os
import threading
import time

_LOCK = threading.RLock()
_CACHE: dict | None = None


def _path() -> str:
    return os.path.join(os.path.expanduser("~"),
                        ".multicalc", "usage.json")


def _load() -> dict:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    try:
        with open(_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        _CACHE = data if isinstance(data, dict) else {}
    except Exception:
        _CACHE = {}
    return _CACHE


def _save(data: dict):
    try:
        os.makedirs(os.path.dirname(_path()), exist_ok=True)
        with open(_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def bump(command_id: str, weight: int = 1):
    """记录一次使用。weight 可用于加权（例如从历史复用比直接命令更重要）。"""
    cid = str(command_id or "").strip()
    if not cid:
        return
    with _LOCK:
        data = _load()
        rec = data.setdefault(cid, {"count": 0, "last": 0})
        rec["count"] = int(rec.get("count", 0)) + int(weight)
        rec["last"] = time.time()
        _save(data)


def score(command_id: str) -> float:
    """返回命令的推荐分（越高越靠前）。

    简单模型：
    - 主要看 count
    - 越近使用，加权越高（半衰期约 14 天）
    """
    cid = str(command_id or "").strip()
    if not cid:
        return 0.0
    with _LOCK:
        data = _load()
    rec = data.get(cid)
    if not rec:
        return 0.0
    count = float(rec.get("count", 0))
    last = float(rec.get("last", 0))
    if count <= 0:
        return 0.0
    age_days = max(0.0, (time.time() - last) / 86400.0)
    recency = 0.5 ** (age_days / 14.0)   # 14 天半衰
    return count * (0.6 + 0.4 * recency)


def all_scores() -> dict:
    with _LOCK:
        data = _load()
    out = {}
    for k in data:
        out[k] = score(k)
    return out


def clear():
    global _CACHE
    with _LOCK:
        _CACHE = {}
        try:
            if os.path.exists(_path()):
                os.remove(_path())
        except Exception:
            pass