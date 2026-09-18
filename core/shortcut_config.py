"""快捷键配置：用户自定义键位（最终版）。

变更历史：
- 第 4 轮：初版（硬编码 DEFAULTS / LABELS）
- 第 13 轮：加 snapshot_save / snapshot_timeline 默认键
- 第 18 轮：移除硬编码 DEFAULTS / LABELS，
            改为从 core.shortcut_meta 动态生成

存储：~/.multicalc/shortcuts.json
格式：{"<command_id>": "<key sequence>"}

设计：
- 用户覆盖与默认值分离：只在文件中存"与默认不同的键"
- 向后兼容模块级 DEFAULTS / LABELS（通过 __getattr__ 动态生成）
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
# 动态生成默认值与标签（替代旧的硬编码）
# ---------------------------------------------------------------------------

def _defaults() -> dict:
    """从 shortcut_meta 动态生成默认键位表。"""
    out = {}
    for m in sc_meta.all_metas():
        out[m.command_id] = m.default
    return out


def _labels() -> dict:
    """从 shortcut_meta 动态生成标签表。"""
    out = {}
    for m in sc_meta.all_metas():
        out[m.command_id] = m.label
    return out


def __getattr__(name: str):
    """模块级属性访问兜底：动态提供 DEFAULTS / LABELS。

    这样旧代码 `from core.shortcut_config import DEFAULTS` 仍然可用，
    但内容会随 shortcut_meta 更新而同步。
    """
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
    with _LOCK:
        data = dict(_load())
        if key:
            data[command_id] = str(key)
        else:
            data.pop(command_id, None)
        _save(data)
        global _CACHE
        _CACHE = data


def reset(command_id: str | None = None):
    """重置某个命令或全部命令。"""
    with _LOCK:
        if command_id is None:
            _save({})
            global _CACHE
            _CACHE = {}
            return
        data = dict(_load())
        data.pop(command_id, None)
        _save(data)
        global _CACHE
        _CACHE = data


def conflicts() -> list:
    """检测冲突：返回 [(key, [command_id, ...]), ...]。

    只检测"全局作用域"层面的简单冲突（同一 key 映射到多个命令）。
    更精细的作用域检测见 core.shortcut_scheme.detect_conflicts。
    """
    all_keys = get_all()
    by_key: dict = {}
    for cmd, key in all_keys.items():
        if not key:
            continue
        by_key.setdefault(key, []).append(cmd)
    return [(k, v) for k, v in by_key.items() if len(v) > 1]


def label(command_id: str) -> str:
    """取命令的中文标签。"""
    m = sc_meta.get_meta(command_id)
    return m.label if m else command_id


def defaults() -> dict:
    """公开的默认值快照（避免每次都通过 __getattr__）。"""
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