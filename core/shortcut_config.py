"""快捷键配置：用户自定义键位（最终版）。

存储：~/.multicalc/shortcuts.json
格式：{"<command_id>": "<key sequence>"}

设计：
- 默认值从 core.shortcut_meta 动态生成
- 用户覆盖与默认值分离：只在文件中存"与默认不同的键"
- 向后兼容模块级 DEFAULTS / LABELS（通过 __getattr__ 动态生成）

修复记录：
- 第 20 轮：set() / reset() 中的 `global _CACHE` 提到函数体首行，
          避免 SyntaxError（name assigned before global declaration）
"""
from __future__ import annotations

import json
import os
import threading

from core import shortcut_meta as sc_meta


_LOCK = threading.RLock()
_CACHE: dict | None = None


def _path() -> str:
    return os.path.join(
        os.path.expanduser("~"),
        ".multicalc", "shortcuts.json")


# ---------------------------------------------------------------------------
# 动态生成默认值与标签
# ---------------------------------------------------------------------------

def _defaults() -> dict:
    out = {}
    for m in sc_meta.all_metas():
        out[m.command_id] = m.default
    return out


def _labels() -> dict:
    out = {}
    for m in sc_meta.all_metas():
        out[m.command_id] = m.label
    return out


def __getattr__(name: str):
    if name == "DEFAULTS":
        return _defaults()
    if name == "LABELS":
        return _labels()
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}")


# ---------------------------------------------------------------------------
# 加载 / 保存
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 公开接口
# ---------------------------------------------------------------------------

def get(command_id: str, default: str | None = None) -> str:
    """取某个命令的快捷键；用户未覆盖则返回默认。"""
    with _LOCK:
        data = _load()
    if command_id in data:
        return str(data[command_id])
    if default is not None:
        return default
    m = sc_meta.get_meta(command_id)
    return m.default if m else ""


def get_all() -> dict:
    """返回 {command_id: key} 合并后的完整表。"""
    out = _defaults()
    with _LOCK:
        data = _load()
    out.update(data)
    return out


def set(command_id: str, key: str):
    """设置某个命令的快捷键；key 为空则删除（回退默认）。"""
    global _CACHE
    with _LOCK:
        data = dict(_load())
        if key:
            data[command_id] = str(key)
        else:
            data.pop(command_id, None)
        _save(data)
        _CACHE = data


def reset(command_id: str | None = None):
    """重置某个命令或全部命令。"""
    global _CACHE
    with _LOCK:
        if command_id is None:
            _save({})
            _CACHE = {}
            return
        data = dict(_load())
        data.pop(command_id, None)
        _save(data)
        _CACHE = data


def conflicts() -> list:
    """检测冲突：返回 [(key, [command_id, ...]), ...]。"""
    all_keys = get_all()
    by_key: dict = {}
    for cmd, key in all_keys.items():
        if not key:
            continue
        by_key.setdefault(key, []).append(cmd)
    return [(k, v) for k, v in by_key.items() if len(v) > 1]


def label(command_id: str) -> str:
    m = sc_meta.get_meta(command_id)
    return m.label if m else command_id


def defaults() -> dict:
    return _defaults()


def labels() -> dict:
    return _labels()


__all__ = [
    "get",
    "get_all",
    "set",
    "reset",
    "conflicts",
    "label",
    "defaults",
    "labels",
]