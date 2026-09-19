"""用户数据持久化：使用统计 / 输入历史 / 最近文件 / 快照 / 片段。

合并自：core/usage_stats.py + core/input_history.py
        + core/recent_files.py + core/snapshot.py + core/snippets.py

命名约定（合并后）：
    usage_*      使用频率统计（~/.multicalc/usage.json）
    input_*      输入框版本历史（~/.multicalc/input_history.json）
    recent_*     最近打开（~/.multicalc/recent_files.json）
    snippet_*    片段（~/.multicalc/snippets.json）
    Snapshot*    会话快照（~/.multicalc/snapshots/）
"""
from __future__ import annotations

import datetime
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from core.base import InputError, log_info, log_warn

__all__ = [
    # 使用统计
    "usage_bump", "usage_score", "usage_all_scores", "usage_clear",
    # 输入历史
    "input_record", "input_list_versions", "input_get_version",
    "input_clear", "input_clear_all", "input_list_keys",
    "input_latest",
    # 最近文件
    "RecentItem",
    "recent_add", "recent_list_all", "recent_list_by_kind",
    "recent_list_existing", "recent_remove", "recent_clear",
    "recent_exists", "recent_kinds",
    # 快照
    "SnapshotMeta", "Snapshot", "SnapshotManager", "get_snapshot_manager",
    # 片段
    "snippet_load", "snippet_add", "snippet_update",
    "snippet_remove", "snippet_clear",
]


# ===========================================================================
# 通用辅助
# ===========================================================================

def _home_json_path(filename: str) -> str:
    return os.path.join(os.path.expanduser("~"),
                        ".multicalc", filename)


def _read_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path: str, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


# ===========================================================================
# 使用频率统计
# ===========================================================================

_USAGE_LOCK = threading.RLock()
_USAGE_CACHE: Optional[dict] = None


def _usage_path() -> str:
    return _home_json_path("usage.json")


def _usage_load() -> dict:
    global _USAGE_CACHE
    if _USAGE_CACHE is not None:
        return _USAGE_CACHE
    data = _read_json(_usage_path(), {})
    _USAGE_CACHE = data if isinstance(data, dict) else {}
    return _USAGE_CACHE


def _usage_save(data: dict):
    _write_json(_usage_path(), data)


def usage_bump(command_id: str, weight: int = 1):
    """记录一次使用。weight 可用于加权。"""
    cid = str(command_id or "").strip()
    if not cid:
        return
    with _USAGE_LOCK:
        data = _usage_load()
        rec = data.setdefault(cid, {"count": 0, "last": 0})
        rec["count"] = int(rec.get("count", 0)) + int(weight)
        rec["last"] = time.time()
        _usage_save(data)


def usage_score(command_id: str) -> float:
    """返回命令的推荐分（越高越靠前）。

    简单模型：主要看 count；14 天半衰期加权。
    """
    cid = str(command_id or "").strip()
    if not cid:
        return 0.0
    with _USAGE_LOCK:
        data = _usage_load()
    rec = data.get(cid)
    if not rec:
        return 0.0
    count = float(rec.get("count", 0))
    last = float(rec.get("last", 0))
    if count <= 0:
        return 0.0
    age_days = max(0.0, (time.time() - last) / 86400.0)
    recency = 0.5 ** (age_days / 14.0)
    return count * (0.6 + 0.4 * recency)


def usage_all_scores() -> dict:
    with _USAGE_LOCK:
        data = _usage_load()
    return {k: usage_score(k) for k in data}


def usage_clear():
    global _USAGE_CACHE
    with _USAGE_LOCK:
        _USAGE_CACHE = {}
        try:
            if os.path.exists(_usage_path()):
                os.remove(_usage_path())
        except Exception:
            pass


# ===========================================================================
# 输入框版本历史
# ===========================================================================

_INPUT_LOCK = threading.RLock()
_INPUT_CACHE: Optional[dict] = None

_INPUT_MAX_VERSIONS = 50
_INPUT_MAX_KEYS = 100


def _input_path() -> str:
    return _home_json_path("input_history.json")


def _input_load() -> dict:
    global _INPUT_CACHE
    if _INPUT_CACHE is not None:
        return _INPUT_CACHE
    data = _read_json(_input_path(), {})
    _INPUT_CACHE = data if isinstance(data, dict) else {}
    return _INPUT_CACHE


def _input_save(data: dict):
    global _INPUT_CACHE
    if _write_json(_input_path(), data):
        _INPUT_CACHE = data


def input_record(key: str, text: str):
    """记录一个版本。与上一个版本相同则跳过。"""
    k = str(key or "").strip()
    if not k:
        return
    with _INPUT_LOCK:
        data = dict(_input_load())
        versions = list(data.get(k) or [])
        t = str(text or "")

        if versions and versions[-1].get("text") == t:
            return

        versions.append({
            "text": t,
            "time": datetime.datetime.now().isoformat(
                timespec="seconds"),
        })
        if len(versions) > _INPUT_MAX_VERSIONS:
            versions = versions[-_INPUT_MAX_VERSIONS:]
        data[k] = versions

        if len(data) > _INPUT_MAX_KEYS:
            def _latest_ts(v):
                return v[-1].get("time", "") if v else ""
            keys = sorted(
                data.keys(),
                key=lambda kk: _latest_ts(data.get(kk) or []),
                reverse=True)
            data = {k2: data[k2] for k2 in keys[:_INPUT_MAX_KEYS]}

        _input_save(data)


def input_list_versions(key: str) -> list:
    """列出某个 key 的所有版本（倒序，最新在前）。"""
    k = str(key or "").strip()
    if not k:
        return []
    with _INPUT_LOCK:
        data = _input_load()
        versions = list(data.get(k) or [])
    return list(reversed(versions))


def input_get_version(key: str, index: int) -> str:
    """按索引取版本（0 = 最新）。"""
    versions = input_list_versions(key)
    if 0 <= index < len(versions):
        return str(versions[index].get("text") or "")
    return ""


def input_clear(key: str):
    k = str(key or "").strip()
    if not k:
        return
    with _INPUT_LOCK:
        data = dict(_input_load())
        data.pop(k, None)
        _input_save(data)


def input_clear_all():
    with _INPUT_LOCK:
        _input_save({})


def input_list_keys() -> list:
    with _INPUT_LOCK:
        return sorted(_input_load().keys())


def input_latest(key: str) -> str:
    versions = input_list_versions(key)
    if versions:
        return str(versions[0].get("text") or "")
    return ""


# ===========================================================================
# 最近打开
# ===========================================================================

_RECENT_LOCK = threading.RLock()
_RECENT_CACHE: Optional[list] = None
_RECENT_MAX_ITEMS = 20


@dataclass
class RecentItem:
    path: str
    kind: str = ""
    label: str = ""
    opened_at: str = ""
    exists: bool = True

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


def _recent_path() -> str:
    return _home_json_path("recent_files.json")


def _recent_load() -> list:
    global _RECENT_CACHE
    if _RECENT_CACHE is not None:
        return _RECENT_CACHE
    data = _read_json(_recent_path(), [])
    if isinstance(data, list):
        _RECENT_CACHE = [RecentItem.from_dict(x)
                         for x in data if isinstance(x, dict)]
    else:
        _RECENT_CACHE = []
    return _RECENT_CACHE


def _recent_save(items: list):
    global _RECENT_CACHE
    if _write_json(_recent_path(),
                   [x.to_dict() for x in items]):
        _RECENT_CACHE = items


def _recent_norm(path: str) -> str:
    try:
        return os.path.normcase(os.path.abspath(str(path)))
    except Exception:
        return str(path)


def _guess_kind(path: str) -> str:
    ext = os.path.splitext(str(path))[1].lower()
    return {
        ".mcsession": "session",
        ".mcnb": "notebook",
        ".ipynb": "notebook",
        ".csv": "csv",
        ".json": "json",
        ".mcenc": "enc",
        ".png": "image", ".jpg": "image", ".jpeg": "image",
        ".bmp": "image", ".gif": "image", ".webp": "image",
    }.get(ext, "other")


def recent_add(path: str, kind: str = "", label: str = "") -> bool:
    p = str(path or "").strip()
    if not p:
        return False
    norm = _recent_norm(p)
    with _RECENT_LOCK:
        items = list(_recent_load())
        items = [x for x in items if _recent_norm(x.path) != norm]

        item = RecentItem(
            path=p,
            kind=str(kind or _guess_kind(p)),
            label=str(label or os.path.basename(p)),
            opened_at=datetime.datetime.now().isoformat(
                timespec="seconds"),
            exists=os.path.exists(p),
        )
        items.insert(0, item)
        if len(items) > _RECENT_MAX_ITEMS:
            items = items[:_RECENT_MAX_ITEMS]
        _recent_save(items)
    return True


def recent_list_all(limit: int = _RECENT_MAX_ITEMS) -> list:
    with _RECENT_LOCK:
        items = list(_recent_load())
    for it in items:
        it.exists = os.path.exists(it.path)
    return items[:int(limit)]


def recent_list_by_kind(kind: str,
                        limit: int = _RECENT_MAX_ITEMS) -> list:
    k = str(kind or "").lower()
    with _RECENT_LOCK:
        items = [x for x in _recent_load()
                 if x.kind.lower() == k]
    for it in items:
        it.exists = os.path.exists(it.path)
    return items[:int(limit)]


def recent_list_existing(limit: int = _RECENT_MAX_ITEMS) -> list:
    out = []
    for it in recent_list_all(limit * 2):
        if it.exists:
            out.append(it)
            if len(out) >= limit:
                break
    return out


def recent_remove(path: str) -> bool:
    p = str(path or "").strip()
    if not p:
        return False
    norm = _recent_norm(p)
    with _RECENT_LOCK:
        items = list(_recent_load())
        new_items = [x for x in items
                     if _recent_norm(x.path) != norm]
        if len(new_items) == len(items):
            return False
        _recent_save(new_items)
    return True


def recent_clear() -> int:
    with _RECENT_LOCK:
        n = len(_recent_load())
        _recent_save([])
    return n


def recent_exists(path: str) -> bool:
    p = str(path or "").strip()
    if not p:
        return False
    norm = _recent_norm(p)
    with _RECENT_LOCK:
        return any(_recent_norm(x.path) == norm
                   for x in _recent_load())


def recent_kinds() -> list:
    with _RECENT_LOCK:
        ks = {x.kind for x in _recent_load() if x.kind}
    return sorted(ks)


# ===========================================================================
# 会话快照
# ===========================================================================

_SNAPSHOT_MAX = 100
_SNAPSHOT_INDEX = "index.json"


@dataclass
class SnapshotMeta:
    id: str
    title: str
    created: str
    note: str = ""
    size: int = 0
    entries: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "created": self.created,
            "note": self.note,
            "size": self.size,
            "entries": self.entries,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SnapshotMeta":
        return cls(
            id=str(d.get("id") or ""),
            title=str(d.get("title") or ""),
            created=str(d.get("created") or ""),
            note=str(d.get("note") or ""),
            size=int(d.get("size") or 0),
            entries=int(d.get("entries") or 0),
        )


@dataclass
class Snapshot:
    meta: SnapshotMeta
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"meta": self.meta.to_dict(), "data": self.data}

    @classmethod
    def from_dict(cls, d: dict) -> "Snapshot":
        return cls(
            meta=SnapshotMeta.from_dict(d.get("meta") or {}),
            data=dict(d.get("data") or {}),
        )


class SnapshotManager:
    """快照管理器。存储目录默认 ~/.multicalc/snapshots。"""

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir is None:
            base_dir = os.path.join(
                os.path.expanduser("~"),
                ".multicalc", "snapshots")
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        self._lock = threading.RLock()

    # ---------------- 内部 ----------------

    def _path(self, sid: str) -> str:
        return os.path.join(self.base_dir, f"{sid}.json")

    def _index_path(self) -> str:
        return os.path.join(self.base_dir, _SNAPSHOT_INDEX)

    def _load_index(self) -> list:
        data = _read_json(self._index_path(), [])
        if isinstance(data, list):
            return [SnapshotMeta.from_dict(x)
                    for x in data if isinstance(x, dict)]
        return []

    def _save_index(self, metas: list):
        _write_json(self._index_path(),
                    [m.to_dict() for m in metas])

    # ---------------- 公开 ----------------

    def create(self, title: str = "",
               context: Optional[dict] = None,
               note: str = "") -> Snapshot:
        with self._lock:
            sid = (datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                   + "_" + uuid.uuid4().hex[:6])
            title = title.strip() or self.auto_label()
            ctx = context or {}

            data = {
                "settings_diff": self._extract_settings_diff(
                    ctx.get("settings")),
                "symbols": ctx.get("symbols") or {},
                "snippets": ctx.get("snippets") or [],
                "drafts": ctx.get("drafts") or {},
                "panel_states": ctx.get("panel_states") or {},
                "history_ids": ctx.get("history_ids") or [],
            }

            entries = (len(data["symbols"])
                       + len(data["snippets"])
                       + len(data["drafts"])
                       + len(data["panel_states"]))

            meta = SnapshotMeta(
                id=sid, title=title,
                created=datetime.datetime.now().isoformat(
                    timespec="seconds"),
                note=str(note or ""), entries=entries)

            snapshot = Snapshot(meta=meta, data=data)
            if not _write_json(self._path(sid),
                               snapshot.to_dict()):
                raise InputError("保存快照失败")
            try:
                meta.size = os.path.getsize(self._path(sid))
            except Exception:
                pass

            metas = self._load_index()
            metas.append(meta)
            self._trim(metas)
            self._save_index(metas)

            log_info(f"snapshot created: {sid} ({title})",
                     module="snapshot")
            return snapshot

    def _extract_settings_diff(self, settings) -> dict:
        if settings is None:
            return {}
        try:
            data = dict(getattr(settings, "data", {}) or {})
            default = dict(getattr(settings, "default", {}) or {})
            diff = {}
            for k, v in data.items():
                if k in ("_drafts", "_themes"):
                    continue
                if k not in default or default[k] != v:
                    diff[k] = v
            return diff
        except Exception as e:
            log_warn(f"extract settings diff failed: {e}",
                     module="snapshot")
            return {}

    def _trim(self, metas: list):
        while len(metas) > _SNAPSHOT_MAX:
            oldest = metas.pop(0)
            try:
                p = self._path(oldest.id)
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass

    def list(self) -> list:
        with self._lock:
            metas = self._load_index()
            metas.sort(key=lambda m: m.created, reverse=True)
            return metas

    def get(self, sid: str) -> Optional[Snapshot]:
        p = self._path(sid)
        if not os.path.exists(p):
            return None
        data = _read_json(p, None)
        if data is None:
            return None
        try:
            return Snapshot.from_dict(data)
        except Exception as e:
            log_warn(f"load snapshot {sid} failed: {e}",
                     module="snapshot")
            return None

    def delete(self, sid: str) -> bool:
        with self._lock:
            p = self._path(sid)
            deleted = False
            if os.path.exists(p):
                try:
                    os.remove(p)
                    deleted = True
                except Exception:
                    return False
            metas = [m for m in self._load_index() if m.id != sid]
            self._save_index(metas)
            return deleted

    def rename(self, sid: str, new_title: str) -> bool:
        with self._lock:
            metas = self._load_index()
            changed = False
            for m in metas:
                if m.id == sid:
                    m.title = (str(new_title or "").strip()
                               or m.title)
                    changed = True
                    break
            if not changed:
                return False
            self._save_index(metas)
            snap = self.get(sid)
            if snap is not None:
                snap.meta.title = new_title
                _write_json(self._path(sid), snap.to_dict())
            return True

    def clear_all(self) -> int:
        with self._lock:
            metas = self._load_index()
            n = len(metas)
            for m in metas:
                try:
                    p = self._path(m.id)
                    if os.path.exists(p):
                        os.remove(p)
                except Exception:
                    pass
            self._save_index([])
            return n

    def restore(self, sid: str) -> dict:
        snap = self.get(sid)
        if snap is None:
            raise InputError(f"快照不存在：{sid}")
        return {
            "settings_diff": snap.data.get("settings_diff") or {},
            "symbols": snap.data.get("symbols") or {},
            "snippets": snap.data.get("snippets") or [],
            "drafts": snap.data.get("drafts") or {},
            "panel_states": snap.data.get("panel_states") or {},
            "history_ids": snap.data.get("history_ids") or [],
        }

    def diff(self, id_a: str, id_b: str) -> dict:
        a = self.get(id_a)
        b = self.get(id_b)
        if a is None or b is None:
            raise InputError("快照不存在")
        return {
            "settings": self._diff_dict(
                a.data.get("settings_diff") or {},
                b.data.get("settings_diff") or {}),
            "symbols": self._diff_dict(
                a.data.get("symbols") or {},
                b.data.get("symbols") or {}),
            "drafts": self._diff_dict(
                a.data.get("drafts") or {},
                b.data.get("drafts") or {}),
            "snippets_count": (
                len(a.data.get("snippets") or []),
                len(b.data.get("snippets") or [])),
            "panel_states": self._diff_dict(
                a.data.get("panel_states") or {},
                b.data.get("panel_states") or {}),
        }

    @staticmethod
    def _diff_dict(a: dict, b: dict) -> dict:
        a_keys = set(a.keys())
        b_keys = set(b.keys())
        added = {k: b[k] for k in b_keys - a_keys}
        removed = {k: a[k] for k in a_keys - b_keys}
        changed = {}
        for k in a_keys & b_keys:
            if a[k] != b[k]:
                changed[k] = {"from": a[k], "to": b[k]}
        return {"added": added, "removed": removed,
                "changed": changed}

    @staticmethod
    def auto_label() -> str:
        now = datetime.datetime.now()
        return f"快照 {now.strftime('%m-%d %H:%M:%S')}"


_SNAPSHOT_MANAGER: Optional[SnapshotManager] = None
_SNAPSHOT_MANAGER_LOCK = threading.RLock()


def get_snapshot_manager() -> SnapshotManager:
    global _SNAPSHOT_MANAGER
    with _SNAPSHOT_MANAGER_LOCK:
        if _SNAPSHOT_MANAGER is None:
            _SNAPSHOT_MANAGER = SnapshotManager()
        return _SNAPSHOT_MANAGER


# ===========================================================================
# 片段
# ===========================================================================

_SNIPPET_LOCK = threading.RLock()


def _snippet_path() -> str:
    return _home_json_path("snippets.json")


def snippet_load() -> list:
    with _SNIPPET_LOCK:
        data = _read_json(_snippet_path(), [])
        return data if isinstance(data, list) else []


def _snippet_save(items: list):
    _write_json(_snippet_path(), items)


def snippet_add(name, expr, tags=None):
    with _SNIPPET_LOCK:
        items = snippet_load()
        items.append({
            "name": str(name),
            "expr": str(expr),
            "tags": list(tags or []),
            "created": time.time(),
        })
        _snippet_save(items)


def snippet_update(idx, name, expr, tags=None):
    with _SNIPPET_LOCK:
        items = snippet_load()
        if 0 <= idx < len(items):
            items[idx] = {
                **items[idx],
                "name": str(name),
                "expr": str(expr),
                "tags": list(tags or []),
            }
            _snippet_save(items)


def snippet_remove(idx):
    with _SNIPPET_LOCK:
        items = snippet_load()
        if 0 <= idx < len(items):
            items.pop(idx)
            _snippet_save(items)


def snippet_clear():
    with _SNIPPET_LOCK:
        _snippet_save([])