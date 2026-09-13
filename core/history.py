"""历史记录：SQLite 存储 / 分页 / 标签 / 收藏 / 去重 / 导出。

兼容旧版 history.json：首次启动若检测到旧文件，自动迁移到 SQLite。
"""
from __future__ import annotations

import csv
import datetime
import json
import os
import sqlite3
import threading


_SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time TEXT NOT NULL,
    module TEXT NOT NULL,
    expr TEXT NOT NULL,
    result TEXT NOT NULL,
    favorite INTEGER NOT NULL DEFAULT 0,
    favorite_value TEXT,
    tags TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_history_module ON history(module);
CREATE INDEX IF NOT EXISTS idx_history_time ON history(time);
CREATE INDEX IF NOT EXISTS idx_history_fav ON history(favorite);
"""


class History:
    """SQLite 历史记录。

    - 自动去重：{module, expr, result} 完全相同且在 ``DEDUP_WINDOW``
      秒内重复出现时，仅刷新时间戳，不新增记录。
    - 自动裁剪：超过 ``MAX_ITEMS`` 时删除最早记录。
    - 线程安全：内部使用 RLock；连接 ``check_same_thread=False``。
    - ``items`` 属性保留为“全量只读快照”，供旧代码使用。
    """

    MAX_ITEMS = 5000
    DEDUP_WINDOW = 5  # seconds

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            d = os.path.join(os.path.expanduser("~"), ".multicalc")
            os.makedirs(d, exist_ok=True)
            db_path = os.path.join(d, "history.db")
        self.path = db_path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()
        self._migrate_legacy()

    # ---------------- 兼容旧文件 ----------------

    def _migrate_legacy(self):
        legacy = os.path.join(os.path.dirname(self.path), "history.json")
        if not os.path.exists(legacy):
            return
        with self._lock:
            try:
                cur = self._conn.execute("SELECT COUNT(*) FROM history")
                if cur.fetchone()[0] > 0:
                    return
            except Exception:
                return
            try:
                with open(legacy, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, list):
                    return
                for x in data:
                    self._conn.execute(
                        "INSERT INTO history "
                        "(time, module, expr, result, favorite, favorite_value, tags) "
                        "VALUES (?,?,?,?,?,?,?)",
                        (x.get("time", ""), x.get("module", ""),
                         x.get("expr", ""), x.get("result", ""),
                         1 if x.get("favorite") else 0,
                         x.get("favorite_value"), ""))
                self._conn.commit()
                try:
                    os.rename(legacy, legacy + ".bak")
                except Exception:
                    pass
            except Exception:
                pass

    # ---------------- 内部工具 ----------------

    @staticmethod
    def _row_to_dict(row) -> dict:
        tags_raw = row["tags"] or ""
        tags = [t for t in tags_raw.split(",") if t]
        return {
            "id": row["id"],
            "time": row["time"],
            "module": row["module"],
            "expr": row["expr"],
            "result": row["result"],
            "favorite": bool(row["favorite"]),
            "favorite_value": row["favorite_value"],
            "tags": tags,
        }

    def _build_filter(self, *, module=None, search=None,
                      favorites_only=False, tag=None,
                      has_favorite_value=False):
        clauses = []
        params: list = []
        if module:
            clauses.append("module = ?")
            params.append(module)
        if favorites_only:
            clauses.append("favorite = 1")
        if has_favorite_value:
            clauses.append("favorite_value IS NOT NULL AND favorite_value != ''")
        if tag:
            clauses.append("(',' || tags || ',') LIKE ?")
            params.append(f"%,{tag},%")
        if search:
            clauses.append("(expr LIKE ? OR result LIKE ? OR tags LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like, like])
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        return where, params

    # ---------------- 写入 ----------------

    def add(self, module, expr, result, tags=None) -> int:
        module = str(module)
        expr = str(expr)
        result = str(result)
        now = datetime.datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        cutoff = (now - datetime.timedelta(seconds=self.DEDUP_WINDOW)
                  ).strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            cur = self._conn.execute(
                "SELECT id FROM history WHERE module=? AND expr=? "
                "AND result=? AND time>=? ORDER BY id DESC LIMIT 1",
                (module, expr, result, cutoff))
            row = cur.fetchone()
            if row:
                self._conn.execute(
                    "UPDATE history SET time=? WHERE id=?", (now_str, row["id"]))
                self._conn.commit()
                return row["id"]
            tag_str = ",".join(tags) if tags else ""
            cur = self._conn.execute(
                "INSERT INTO history "
                "(time, module, expr, result, favorite, tags) "
                "VALUES (?,?,?,?,0,?)",
                (now_str, module, expr, result, tag_str))
            self._conn.commit()
            new_id = cur.lastrowid
            cur = self._conn.execute("SELECT COUNT(*) FROM history")
            total = cur.fetchone()[0]
            if total > self.MAX_ITEMS:
                excess = total - self.MAX_ITEMS
                self._conn.execute(
                    "DELETE FROM history WHERE id IN "
                    "(SELECT id FROM history ORDER BY id ASC LIMIT ?)",
                    (excess,))
                self._conn.commit()
            return new_id

    def remove(self, item_id):
        with self._lock:
            self._conn.execute("DELETE FROM history WHERE id=?", (int(item_id),))
            self._conn.commit()

    def clear(self):
        with self._lock:
            self._conn.execute("DELETE FROM history")
            self._conn.commit()

    def clear_module(self, module):
        with self._lock:
            self._conn.execute("DELETE FROM history WHERE module=?", (str(module),))
            self._conn.commit()

    def toggle_favorite(self, item_id) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "SELECT favorite FROM history WHERE id=?", (int(item_id),))
            row = cur.fetchone()
            if not row:
                return False
            new_val = 0 if row["favorite"] else 1
            self._conn.execute(
                "UPDATE history SET favorite=? WHERE id=?",
                (new_val, int(item_id)))
            self._conn.commit()
            return bool(new_val)

    def set_favorite(self, item_id, value: bool):
        with self._lock:
            self._conn.execute(
                "UPDATE history SET favorite=? WHERE id=?",
                (1 if value else 0, int(item_id)))
            self._conn.commit()

    def set_tags(self, item_id, tags):
        if tags is None:
            tag_str = ""
        elif isinstance(tags, str):
            tag_str = tags
        else:
            tag_str = ",".join(str(t).strip() for t in tags if str(t).strip())
        with self._lock:
            self._conn.execute(
                "UPDATE history SET tags=? WHERE id=?",
                (tag_str, int(item_id)))
            self._conn.commit()

    def set_favorite_value(self, item_id, value):
        with self._lock:
            self._conn.execute(
                "UPDATE history SET favorite_value=?, favorite=1 WHERE id=?",
                (str(value), int(item_id)))
            self._conn.commit()

    def get_favorite_value(self, item_id):
        with self._lock:
            cur = self._conn.execute(
                "SELECT favorite_value FROM history WHERE id=?", (int(item_id),))
            row = cur.fetchone()
            return row["favorite_value"] if row else None

    # ---------------- 读取 ----------------

    def get(self, item_id):
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM history WHERE id=?", (int(item_id),))
            row = cur.fetchone()
            return self._row_to_dict(row) if row else None

    def list(self, *, module=None, search=None, favorites_only=False,
             tag=None, has_favorite_value=False,
             offset=0, limit=200, order="id DESC"):
        where, params = self._build_filter(
            module=module, search=search, favorites_only=favorites_only,
            tag=tag, has_favorite_value=has_favorite_value)
        sql = f"SELECT * FROM history {where} ORDER BY {order} LIMIT ? OFFSET ?"
        with self._lock:
            cur = self._conn.execute(sql, params + [int(limit), int(offset)])
            return [self._row_to_dict(r) for r in cur.fetchall()]

    def count(self, *, module=None, search=None, favorites_only=False,
              tag=None, has_favorite_value=False) -> int:
        where, params = self._build_filter(
            module=module, search=search, favorites_only=favorites_only,
            tag=tag, has_favorite_value=has_favorite_value)
        with self._lock:
            cur = self._conn.execute(
                f"SELECT COUNT(*) FROM history {where}", params)
            return int(cur.fetchone()[0])

    def modules(self):
        with self._lock:
            cur = self._conn.execute(
                "SELECT DISTINCT module FROM history "
                "WHERE module != '' ORDER BY module")
            return [r["module"] for r in cur.fetchall()]

    def tags(self):
        with self._lock:
            cur = self._conn.execute(
                "SELECT tags FROM history WHERE tags != ''")
            seen = []
            for row in cur.fetchall():
                for t in (row["tags"] or "").split(","):
                    t = t.strip()
                    if t and t not in seen:
                        seen.append(t)
            return sorted(seen)

    def favorite_values(self):
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM history "
                "WHERE favorite_value IS NOT NULL AND favorite_value != '' "
                "ORDER BY id DESC")
            return [self._row_to_dict(r) for r in cur.fetchall()]

    @property
    def items(self):
        """全量快照（旧接口兼容；请优先使用 list()/count()）。"""
        return self.list(offset=0, limit=self.MAX_ITEMS * 2)

    # ---------------- 导出 ----------------

    def export_json(self, path):
        data = self.items
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def export_csv(self, path):
        # utf-8-sig 让 Excel 正确识别中文
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["time", "module", "expr", "result",
                        "favorite", "favorite_value", "tags"])
            for x in self.items:
                w.writerow([
                    x.get("time", ""), x.get("module", ""),
                    x.get("expr", ""), x.get("result", ""),
                    1 if x.get("favorite") else 0,
                    x.get("favorite_value") or "",
                    ",".join(x.get("tags") or []),
                ])

    # ---------------- 清理 ----------------

    def close(self):
        try:
            with self._lock:
                self._conn.close()
        except Exception:
            pass