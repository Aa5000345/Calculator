"""片段管理器：常用表达式/公式收藏。

存储到 ~/.multicalc/snippets.json。
"""
from __future__ import annotations

import json
import os
import threading
import time

_LOCK = threading.RLock()


def _path():
    return os.path.join(os.path.expanduser("~"),
                        ".multicalc", "snippets.json")


def load() -> list[dict]:
    with _LOCK:
        if not os.path.exists(_path()):
            return []
        try:
            with open(_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []


def _save(items):
    try:
        os.makedirs(os.path.dirname(_path()), exist_ok=True)
        with open(_path(), "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def add(name, expr, tags=None):
    with _LOCK:
        items = load()
        items.append({
            "name": str(name),
            "expr": str(expr),
            "tags": list(tags or []),
            "created": time.time(),
        })
        _save(items)


def update(idx, name, expr, tags=None):
    with _LOCK:
        items = load()
        if 0 <= idx < len(items):
            items[idx] = {
                **items[idx],
                "name": str(name),
                "expr": str(expr),
                "tags": list(tags or []),
            }
            _save(items)


def remove(idx):
    with _LOCK:
        items = load()
        if 0 <= idx < len(items):
            items.pop(idx)
            _save(items)


def clear():
    with _LOCK:
        _save([])