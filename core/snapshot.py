"""会话快照 / 时间机器：保存与恢复整个应用状态。

设计：
- 快照包含：settings 差异、symbols、snippets、drafts、面板状态
- 存储到 ~/.multicalc/snapshots/<id>.json（每个快照一个文件）
- 索引文件 ~/.multicalc/snapshots/index.json 记录元数据
- 最多保留 100 个快照（超过时自动删除最旧的）
- 支持 diff：比较两个快照的差异

对外接口：
    SnapshotManager:
        create(title, context, note) -> Snapshot
        list() -> list[SnapshotMeta]
        restore(snapshot_id) -> dict
        delete(snapshot_id) -> bool
        get(snapshot_id) -> Snapshot
        diff(id_a, id_b) -> dict
        rename(snapshot_id, new_title) -> bool
        auto_label() -> str
"""
from __future__ import annotations

import datetime
import json
import os
import threading
import uuid
from dataclasses import dataclass, field
from typing import Optional

from core.errors import InputError
from core.logger import log_info, log_warn


_MAX_SNAPSHOTS = 100
_INDEX_FILE = "index.json"


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

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
        return {
            "meta": self.meta.to_dict(),
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Snapshot":
        return cls(
            meta=SnapshotMeta.from_dict(d.get("meta") or {}),
            data=dict(d.get("data") or {}),
        )


# ---------------------------------------------------------------------------
# 管理器
# ---------------------------------------------------------------------------

class SnapshotManager:
    """快照管理器。

    Args:
        base_dir: 存储目录（默认 ~/.multicalc/snapshots）
    """

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
        return os.path.join(self.base_dir, _INDEX_FILE)

    def _load_index(self) -> list:
        try:
            with open(self._index_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [SnapshotMeta.from_dict(x) for x in data
                        if isinstance(x, dict)]
        except Exception:
            pass
        return []

    def _save_index(self, metas: list):
        try:
            with open(self._index_path(), "w", encoding="utf-8") as f:
                json.dump([m.to_dict() for m in metas],
                          f, ensure_ascii=False, indent=2)
        except Exception as e:
            log_warn(f"save snapshot index failed: {e}",
                     module="snapshot")

    # ---------------- 公开接口 ----------------

    def create(self, title: str = "",
               context: Optional[dict] = None,
               note: str = "") -> Snapshot:
        """创建快照。

        Args:
            title: 标题（留空则自动生成）
            context: 应用状态字典，包含：
                - settings: Settings 实例（可选）
                - symbols: 变量 dict
                - snippets: 片段 list
                - drafts: 草稿 dict
                - panel_states: 面板状态 dict
                - history_ids: 历史记录 id 列表（可选）
            note: 备注

        Returns:
            Snapshot
        """
        with self._lock:
            sid = datetime.datetime.now().strftime(
                "%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:6]
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

            entries = (
                len(data["symbols"])
                + len(data["snippets"])
                + len(data["drafts"])
                + len(data["panel_states"])
            )

            meta = SnapshotMeta(
                id=sid,
                title=title,
                created=datetime.datetime.now().isoformat(
                    timespec="seconds"),
                note=str(note or ""),
                entries=entries,
            )

            # 写文件
            snapshot = Snapshot(meta=meta, data=data)
            try:
                with open(self._path(sid), "w",
                          encoding="utf-8") as f:
                    json.dump(snapshot.to_dict(), f,
                              ensure_ascii=False, indent=2)
                meta.size = os.path.getsize(self._path(sid))
            except Exception as e:
                raise InputError(f"保存快照失败：{e}")

            # 更新索引
            metas = self._load_index()
            metas.append(meta)
            self._trim(metas)
            self._save_index(metas)

            log_info(f"snapshot created: {sid} ({title})",
                     module="snapshot")
            return snapshot

    def _extract_settings_diff(self, settings) -> dict:
        """从 Settings 实例提取非默认值。"""
        if settings is None:
            return {}
        try:
            data = dict(getattr(settings, "data", {}) or {})
            default = dict(getattr(settings, "default", {}) or {})
            # 只保留和默认不同的键
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
        """超过上限时删除最旧的。"""
        while len(metas) > _MAX_SNAPSHOTS:
            oldest = metas.pop(0)
            try:
                p = self._path(oldest.id)
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass

    def list(self) -> list:
        """列出所有快照（按时间倒序）。"""
        with self._lock:
            metas = self._load_index()
            metas.sort(key=lambda m: m.created, reverse=True)
            return metas

    def get(self, sid: str) -> Optional[Snapshot]:
        """读取单个快照。"""
        p = self._path(sid)
        if not os.path.exists(p):
            return None
        try:
            with open(p, "r", encoding="utf-8") as f:
                return Snapshot.from_dict(json.load(f))
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
                    m.title = str(new_title or "").strip() \
                        or m.title
                    changed = True
                    break
            if not changed:
                return False
            self._save_index(metas)
            # 同步到快照文件
            snap = self.get(sid)
            if snap is not None:
                snap.meta.title = new_title
                try:
                    with open(self._path(sid), "w",
                              encoding="utf-8") as f:
                        json.dump(snap.to_dict(), f,
                                  ensure_ascii=False, indent=2)
                except Exception:
                    pass
            return True

    def clear_all(self) -> int:
        """清空所有快照，返回删除数量。"""
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

    # ---------------- 恢复 ----------------

    def restore(self, sid: str) -> dict:
        """恢复快照，返回应用状态字典。

        调用方负责把返回的 dict 应用到 Settings / symbols 等。
        """
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

    # ---------------- Diff ----------------

    def diff(self, id_a: str, id_b: str) -> dict:
        """比较两个快照。"""
        a = self.get(id_a)
        b = self.get(id_b)
        if a is None or b is None:
            raise InputError("快照不存在")

        out = {
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
                len(b.data.get("snippets") or []),
            ),
            "panel_states": self._diff_dict(
                a.data.get("panel_states") or {},
                b.data.get("panel_states") or {}),
        }
        return out

    @staticmethod
    def _diff_dict(a: dict, b: dict) -> dict:
        """比较两个 dict，返回 {added, removed, changed}。"""
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

    # ---------------- 自动标签 ----------------

    @staticmethod
    def auto_label() -> str:
        now = datetime.datetime.now()
        return f"快照 {now.strftime('%m-%d %H:%M:%S')}"


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_MANAGER: Optional[SnapshotManager] = None


def get_manager() -> SnapshotManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = SnapshotManager()
    return _MANAGER


__all__ = [
    "SnapshotMeta",
    "Snapshot",
    "SnapshotManager",
    "get_manager",
]