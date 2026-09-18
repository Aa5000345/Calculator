"""输入框版本控制：给每个输入框独立的版本历史。

设计：
- 按 key 隔离：`basic.expr` / `scientific.expr` 各自独立
- 每次文本变化（防抖）记录一个版本，去重
- 每个 key 最多保留 50 个版本
- 存储到 ~/.multicalc/input_history.json
- 支持：列出、回滚、删除某个版本、清空

对外接口：
    record(key, text)
    list_versions(key) -> list[dict]
    get_version(key, index) -> str
    clear(key)
    clear_all()
"""
from __future__ import annotations

import datetime
import json
import os
import threading

from core.logger import log_warn


_MAX_VERSIONS_PER_KEY = 50
_MAX_KEYS = 100


_LOCK = threading.RLock()
_CACHE: dict | None = None


def _path() -> str:
    return os.path.join(
        os.path.expanduser("~"),
        ".multicalc", "input_history.json")


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
    global _CACHE
    try:
        os.makedirs(os.path.dirname(_path()), exist_ok=True)
        with open(_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        _CACHE = data
    except Exception as e:
        log_warn(f"save input history failed: {e}",
                 module="input_history")


def record(key: str, text: str):
    """记录一个版本。

    与上一个版本相同则跳过；空字符串也记录（便于回滚到空）。
    """
    k = str(key or "").strip()
    if not k:
        return
    with _LOCK:
        data = dict(_load())

        versions = list(data.get(k) or [])
        t = str(text or "")

        # 去重：和最近一个版本相同则跳过
        if versions and versions[-1].get("text") == t:
            return

        versions.append({
            "text": t,
            "time": datetime.datetime.now().isoformat(
                timespec="seconds"),
        })

        # 截断
        if len(versions) > _MAX_VERSIONS_PER_KEY:
            versions = versions[-_MAX_VERSIONS_PER_KEY:]

        data[k] = versions

        # 键数量限制
        if len(data) > _MAX_KEYS:
            # 按最近使用排序，保留前 _MAX_KEYS
            def _latest_ts(v):
                if not v:
                    return ""
                return v[-1].get("time", "")
            keys = sorted(
                data.keys(),
                key=lambda kk: _latest_ts(data.get(kk) or []),
                reverse=True)
            data = {k2: data[k2] for k2 in keys[:_MAX_KEYS]}

        _save(data)


def list_versions(key: str) -> list:
    """列出某个 key 的所有版本（倒序，最新在前）。"""
    k = str(key or "").strip()
    if not k:
        return []
    with _LOCK:
        data = _load()
        versions = list(data.get(k) or [])
    return list(reversed(versions))


def get_version(key: str, index: int) -> str:
    """按索引取版本（0 = 最新）。"""
    versions = list_versions(key)
    if 0 <= index < len(versions):
        return str(versions[index].get("text") or "")
    return ""


def clear(key: str):
    """清空某个 key 的历史。"""
    k = str(key or "").strip()
    if not k:
        return
    with _LOCK:
        data = dict(_load())
        data.pop(k, None)
        _save(data)


def clear_all():
    with _LOCK:
        _save({})


def list_keys() -> list:
    """列出所有有历史的 key。"""
    with _LOCK:
        return sorted(_load().keys())


def latest_text(key: str) -> str:
    """取最近一次记录的文本。"""
    versions = list_versions(key)
    if versions:
        return str(versions[0].get("text") or "")
    return ""


__all__ = [
    "record",
    "list_versions",
    "get_version",
    "clear",
    "clear_all",
    "list_keys",
    "latest_text",
]