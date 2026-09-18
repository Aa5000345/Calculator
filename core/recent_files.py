"""最近打开的文件：记录、去重、上限、持久化。

用途：
- .mcsession / .mcnb / .ipynb / .csv / .mcenc 等
- 菜单「文件 → 最近打开」子菜单
- 欢迎页的「最近」列表

设计：
- 存储到 ~/.multicalc/recent_files.json
- 最多保留 20 条
- 自动去重（路径规范化后比较）
- 支持按 kind 过滤

对外接口：
    add(path, kind="", label="") -> bool
    list_all(limit) -> list[dict]
    list_by_kind(kind, limit) -> list[dict]
    remove(path) -> bool
    clear() -> int
    exists(path) -> bool
    kinds() -> list[str]
"""
from __future__ import annotations

import datetime
import json
import os
import threading
from dataclasses import dataclass, field
from typing import Optional

from core.logger import log_warn


_MAX_ITEMS = 20


_LOCK = threading.RLock()
_CACHE: Optional[list] = None


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class RecentItem:
    path: str
    kind: str = ""             # session / notebook / csv / enc / image / ...
    label: str = ""            # 显示名（默认用文件名）
    opened_at: str = ""        # ISO 时间戳
    exists: bool = True        # 当前文件是否存在

    def display(self) -> str:
        return self.label or os.path.basename(self.path) or self.path

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "kind": self.kind,
            "label": self.label,
            "opened_at": self.opened_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RecentItem":
        return cls(
            path=str(d.get("path") or ""),
            kind=str(d.get("kind") or ""),
            label=str(d.get("label") or ""),
            opened_at=str(d.get("opened_at") or ""),
        )


# ---------------------------------------------------------------------------
# 存储
# ---------------------------------------------------------------------------

def _path() -> str:
    return os.path.join(
        os.path.expanduser("~"),
        ".multicalc", "recent_files.json")


def _load() -> list:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    try:
        with open(_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            _CACHE = [
                RecentItem.from_dict(x)
                for x in data if isinstance(x, dict)
            ]
        else:
            _CACHE = []
    except Exception:
        _CACHE = []
    return _CACHE


def _save(items: list):
    global _CACHE
    try:
        os.makedirs(os.path.dirname(_path()), exist_ok=True)
        with open(_path(), "w", encoding="utf-8") as f:
            json.dump([x.to_dict() for x in items],
                      f, ensure_ascii=False, indent=2)
        _CACHE = items
    except Exception as e:
        log_warn(f"save recent_files failed: {e}",
                 module="recent_files")


def _norm(path: str) -> str:
    try:
        return os.path.normcase(os.path.abspath(str(path)))
    except Exception:
        return str(path)


# ---------------------------------------------------------------------------
# 公开接口
# ---------------------------------------------------------------------------

def add(path: str, kind: str = "",
        label: str = "") -> bool:
    """添加 / 更新一条最近打开记录。

    Args:
        path: 文件路径
        kind: 分类（session / notebook / csv / enc / image ...）
        label: 显示名（默认用文件名）

    Returns:
        True 成功
    """
    p = str(path or "").strip()
    if not p:
        return False

    norm = _norm(p)
    with _LOCK:
        items = list(_load())
        # 移除同路径的旧记录
        items = [x for x in items if _norm(x.path) != norm]

        item = RecentItem(
            path=p,
            kind=str(kind or _guess_kind(p)),
            label=str(label or os.path.basename(p)),
            opened_at=datetime.datetime.now().isoformat(
                timespec="seconds"),
            exists=os.path.exists(p),
        )
        items.insert(0, item)

        # 截断
        if len(items) > _MAX_ITEMS:
            items = items[:_MAX_ITEMS]

        _save(items)
    return True


def _guess_kind(path: str) -> str:
    ext = os.path.splitext(str(path))[1].lower()
    return {
        ".mcsession": "session",
        ".mcnb": "notebook",
        ".ipynb": "notebook",
        ".csv": "csv",
        ".json": "json",
        ".mcenc": "enc",
        ".png": "image",
        ".jpg": "image",
        ".jpeg": "image",
        ".bmp": "image",
        ".gif": "image",
        ".webp": "image",
    }.get(ext, "other")


def list_all(limit: int = _MAX_ITEMS) -> list:
    """列出全部（按时间倒序）。"""
    with _LOCK:
        items = list(_load())
    for it in items:
        it.exists = os.path.exists(it.path)
    return items[:int(limit)]


def list_by_kind(kind: str, limit: int = _MAX_ITEMS) -> list:
    k = str(kind or "").lower()
    with _LOCK:
        items = [x for x in _load()
                 if x.kind.lower() == k]
    for it in items:
        it.exists = os.path.exists(it.path)
    return items[:int(limit)]


def list_existing(limit: int = _MAX_ITEMS) -> list:
    """只返回仍存在的文件。"""
    out = []
    for it in list_all(limit * 2):
        if it.exists:
            out.append(it)
            if len(out) >= limit:
                break
    return out


def remove(path: str) -> bool:
    p = str(path or "").strip()
    if not p:
        return False
    norm = _norm(p)
    with _LOCK:
        items = list(_load())
        new_items = [x for x in items
                     if _norm(x.path) != norm]
        if len(new_items) == len(items):
            return False
        _save(new_items)
    return True


def clear() -> int:
    """清空所有记录，返回删除数量。"""
    with _LOCK:
        n = len(_load())
        _save([])
    return n


def exists(path: str) -> bool:
    p = str(path or "").strip()
    if not p:
        return False
    norm = _norm(p)
    with _LOCK:
        return any(_norm(x.path) == norm
                   for x in _load())


def kinds() -> list:
    with _LOCK:
        ks = {x.kind for x in _load() if x.kind}
    return sorted(ks)


__all__ = [
    "RecentItem",
    "add",
    "list_all",
    "list_by_kind",
    "list_existing",
    "remove",
    "clear",
    "exists",
    "kinds",
]