"""全局状态：国际化 / 设置 / 历史 / 变量。

合并自：i18n.py + settings.py + history.py + symbols.py

依赖：core.base（log_warn）

对外接口：
    I18n        语言包 + 本地化
    Settings    默认值 + 用户覆盖 + 热重载 + 导入导出 + 主题扫描
    History     SQLite 历史记录
    # symbols（模块级函数）
    set_persist_path, match_assignment, get_all, get_raw, get_symbol,
    has, count, get_variables, get_functions, set_symbol,
    delete_symbol, clear_symbols, export_symbols, import_symbols
"""
from __future__ import annotations

import copy
import csv
import datetime
import json
import os
import re
import sqlite3
import threading

from core.base import log_warn

try:
    from babel.numbers import format_decimal, format_currency
    from babel.dates import format_date as babel_format_date
    _HAS_BABEL = True
except Exception:
    _HAS_BABEL = False


__all__ = [
    "I18n", "Settings", "History",
    "set_persist_path", "match_assignment",
    "get_all", "get_raw", "get_symbol",
    "has", "count", "get_variables", "get_functions",
    "set_symbol", "delete_symbol", "clear_symbols",
    "export_symbols", "import_symbols",
]


# ===========================================================================
# I18n
# ===========================================================================

class I18n:
    """语言包 + 数字/日期/货币本地化。"""

    def __init__(self, dir_path: str, lang: str = "zh_CN"):
        self.dir = dir_path
        self.lang = lang
        self.trans: dict = {}
        self.load(lang)

    def load(self, lang: str):
        path = os.path.join(self.dir, f"{lang}.json")
        if not os.path.exists(path):
            path = os.path.join(self.dir, "en_US.json")
            lang = "en_US"
        with open(path, "r", encoding="utf-8") as f:
            self.trans = json.load(f)
        self.lang = lang

    def t(self, key: str, default=None):
        return self.trans.get(
            key, default if default is not None else key)

    # ---------------- 本地化 ----------------

    def format_number(self, value, decimals=None) -> str:
        try:
            if _HAS_BABEL:
                if decimals is not None:
                    pattern = ("#,##0." + ("0" * decimals)
                               if decimals else "#,##0")
                    return format_decimal(
                        value, format=pattern, locale=self.lang)
                return format_decimal(value, locale=self.lang)
        except Exception:
            pass
        try:
            if decimals is None:
                return f"{value:,}"
            return f"{value:,.{decimals}f}"
        except Exception:
            return str(value)

    def format_currency(self, value, currency="USD") -> str:
        try:
            if _HAS_BABEL:
                return format_currency(
                    value, currency, locale=self.lang)
        except Exception:
            pass
        return f"{value:.2f} {currency}"

    def format_date(self, dt, fmt="medium") -> str:
        try:
            if _HAS_BABEL:
                if isinstance(dt, str):
                    dt = datetime.datetime.strptime(
                        dt, "%Y-%m-%d").date()
                return babel_format_date(
                    dt, format=fmt, locale=self.lang)
        except Exception:
            pass
        if isinstance(dt, (datetime.date, datetime.datetime)):
            return dt.strftime("%Y-%m-%d")
        return str(dt)


# ===========================================================================
# Settings
# ===========================================================================

_DRAFT_DEBOUNCE_SEC = 0.3


class Settings:
    """默认值 + 用户覆盖 + 热重载 + 导入导出 + 草稿（防抖写盘）+ 主题扫描。"""

    def __init__(self, default_path: str):
        self.default_path = default_path
        self.user_dir = os.path.join(
            os.path.expanduser("~"), ".multicalc")
        os.makedirs(self.user_dir, exist_ok=True)
        self.user_path = os.path.join(self.user_dir, "settings.json")
        self.draft_path = os.path.join(self.user_dir, "draft.json")

        with open(default_path, "r", encoding="utf-8") as f:
            self.default = json.load(f)

        self.data = copy.deepcopy(self.default)
        self._lock = threading.RLock()
        self._draft_timer: threading.Timer | None = None
        self._draft_dirty = False

        self._load_user()
        self._load_drafts()
        self._load_theme_files()

        self._listeners: list = []

    # ---------------- 读写 ----------------

    def _load_user(self):
        if not os.path.exists(self.user_path):
            return
        try:
            with open(self.user_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data.pop("_drafts", None)
                self.data.update(data)
        except Exception:
            pass

    def reload_if_changed(self) -> bool:
        try:
            with open(self.user_path, "r", encoding="utf-8") as f:
                disk = json.load(f)
        except Exception:
            return False
        if isinstance(disk, dict):
            disk.pop("_drafts", None)
        current = {k: v for k, v in self.data.items()
                   if k != "_drafts"}
        if disk == current:
            return False
        merged = copy.deepcopy(self.default)
        merged.update(disk)
        if "_drafts" in self.data:
            merged["_drafts"] = self.data["_drafts"]
        self.data = merged
        self._load_theme_files()
        return True

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value, notify=True):
        with self._lock:
            if self.data.get(key) == value:
                return
            self.data[key] = value
            self.save()
        if notify:
            self._notify(key)

    def update(self, mapping, notify=True):
        """批量更新：逐 key 触发监听器。"""
        changed_keys = []
        with self._lock:
            for k, v in mapping.items():
                if self.data.get(k) != v:
                    self.data[k] = v
                    changed_keys.append(k)
            if not changed_keys:
                return
            self.save()
        if notify:
            for k in changed_keys:
                self._notify(k)

    def save(self):
        try:
            clean = {k: v for k, v in self.data.items()
                     if k != "_drafts"}
            with open(self.user_path, "w",
                      encoding="utf-8") as f:
                json.dump(clean, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def reset(self, notify=True):
        with self._lock:
            self.data = copy.deepcopy(self.default)
            self._load_theme_files()
            self.save()
        if notify:
            self._notify(None)

    # ---------------- 导入 / 导出 ----------------

    def export_to(self, path: str):
        clean = {k: v for k, v in self.data.items()
                 if k != "_drafts"}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False, indent=2)

    def import_from(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("设置文件格式错误")
        data.pop("_drafts", None)
        merged = copy.deepcopy(self.default)
        merged.update(data)
        if "_drafts" in self.data:
            merged["_drafts"] = self.data["_drafts"]
        self.data = merged
        self._load_theme_files()
        self.save()
        self._notify(None)

    # ---------------- 草稿（防抖） ----------------

    def _load_drafts(self):
        if not os.path.exists(self.draft_path):
            return
        try:
            with open(self.draft_path, "r",
                      encoding="utf-8") as f:
                self.data["_drafts"] = json.load(f)
        except Exception:
            pass

    def set_draft(self, key, value):
        with self._lock:
            drafts = self.data.setdefault("_drafts", {})
            if drafts.get(key) == value:
                return
            drafts[key] = value
            self._draft_dirty = True
            if self._draft_timer is not None:
                try:
                    self._draft_timer.cancel()
                except Exception:
                    pass
            self._draft_timer = threading.Timer(
                _DRAFT_DEBOUNCE_SEC, self._flush_drafts_safe)
            self._draft_timer.daemon = True
            self._draft_timer.start()

    def _flush_drafts_safe(self):
        try:
            self._flush_drafts()
        except Exception:
            pass

    def _flush_drafts(self):
        with self._lock:
            if not self._draft_dirty:
                return
            drafts = self.data.get("_drafts", {}) or {}
            try:
                with open(self.draft_path, "w",
                          encoding="utf-8") as f:
                    json.dump(drafts, f,
                              ensure_ascii=False, indent=2)
                self._draft_dirty = False
            except Exception:
                pass

    def flush(self):
        """应用退出时调用：取消定时器并立即写盘。"""
        if self._draft_timer is not None:
            try:
                self._draft_timer.cancel()
            except Exception:
                pass
            self._draft_timer = None
        self._flush_drafts()

    def get_draft(self, key, default=""):
        return self.data.get("_drafts", {}).get(key, default)

    # ---------------- 监听器 ----------------

    def add_listener(self, fn):
        if fn not in self._listeners:
            self._listeners.append(fn)

    def remove_listener(self, fn):
        if fn in self._listeners:
            self._listeners.remove(fn)

    def _notify(self, key=None):
        for fn in list(self._listeners):
            try:
                fn(key)
            except Exception:
                pass

    # ---------------- 主题文件扫描 ----------------

    def _load_theme_files(self):
        themes_dir = os.path.join(
            os.path.dirname(self.default_path), "themes")
        out: dict = {}
        if os.path.isdir(themes_dir):
            for fn in sorted(os.listdir(themes_dir)):
                if not fn.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(themes_dir, fn),
                              "r", encoding="utf-8") as f:
                        info = json.load(f)
                    name = (info.get("name")
                            or os.path.splitext(fn)[0])
                    pal = info.get("palette") or {}
                    if name and isinstance(pal, dict):
                        out[name] = {
                            "label": info.get("label", name),
                            "palette": pal,
                        }
                except Exception:
                    pass
        self.data["_themes"] = out

    def themes(self) -> dict:
        result: dict = {}
        for name, pal in (self.default.get("palette") or {}).items():
            result[name] = {"label": name, "palette": pal}
        for name, info in (self.data.get("_themes") or {}).items():
            result[name] = info
        return result

    def save_theme(self, name, label, palette) -> str | None:
        themes_dir = os.path.join(
            os.path.dirname(self.default_path), "themes")
        try:
            os.makedirs(themes_dir, exist_ok=True)
            path = os.path.join(themes_dir, f"{name}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"name": name, "label": label,
                           "palette": palette}, f,
                          ensure_ascii=False, indent=2)
            self._load_theme_files()
            return path
        except Exception:
            return None

    def delete_theme(self, name: str):
        themes_dir = os.path.join(
            os.path.dirname(self.default_path), "themes")
        try:
            path = os.path.join(themes_dir, f"{name}.json")
            if os.path.exists(path):
                os.remove(path)
            self._load_theme_files()
        except Exception:
            pass

    # ---------------- 配色 / 汇率 / 模块 ----------------

    def palette(self, theme_override=None) -> dict:
        theme = theme_override or self.get("theme", "dark")
        if theme == "system":
            theme = "dark"

        pal = self.get("palette", {}) or {}
        if theme in pal:
            return pal[theme]

        themes = self.data.get("_themes") or {}
        if theme in themes:
            return themes[theme]["palette"]

        return pal.get("dark", {
            "bg": "#1e1e1e", "fg": "#ffffff",
            "panel": "#2d2d30", "accent": "#007acc",
            "border": "#3f3f46", "hover": "#3a3d41"})

    def set_palette_color(self, key, color):
        theme = self.get("theme", "dark")
        if theme == "system":
            theme = "dark"
        pal = dict(self.get("palette", {}) or {})
        base = pal.get(theme)
        if base is None:
            themes = self.data.get("_themes") or {}
            if theme in themes:
                base = dict(themes[theme]["palette"])
            else:
                base = dict(self.palette(theme))
        else:
            base = dict(base)
        base[key] = color
        pal[theme] = base
        self.set("palette", pal)

    def get_manual_rate(self, pair: str):
        return (self.get("manual_rates", {}) or {}).get(pair)

    def set_manual_rate(self, pair: str, rate):
        rates = dict(self.get("manual_rates", {}) or {})
        rates[pair] = float(rate)
        self.set("manual_rates", rates)

    def is_module_visible(self, key: str) -> bool:
        return (self.get("visible_modules", {}) or {}).get(key, True)

    def set_module_visible(self, key: str, visible: bool):
        vm = dict(self.get("visible_modules", {}) or {})
        vm[key] = bool(visible)
        self.set("visible_modules", vm)


# ===========================================================================
# History
# ===========================================================================

_HISTORY_SCHEMA = """
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

    - 5 秒内重复的 (module, expr, result) 只刷新时间戳
    - 超过 MAX_ITEMS 自动裁剪
    - 线程安全
    """

    MAX_ITEMS = 5000
    DEDUP_WINDOW = 5

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            d = os.path.join(os.path.expanduser("~"), ".multicalc")
            os.makedirs(d, exist_ok=True)
            db_path = os.path.join(d, "history.db")
        self.path = db_path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_HISTORY_SCHEMA)
            try:
                # 提升批量写性能
                self._conn.execute("PRAGMA synchronous=NORMAL")
            except Exception:
                pass
            self._conn.commit()
        self._migrate_legacy()

    # ---------------- 兼容旧文件 ----------------

    def _migrate_legacy(self):
        legacy = os.path.join(
            os.path.dirname(self.path), "history.json")
        if not os.path.exists(legacy):
            return
        with self._lock:
            try:
                cur = self._conn.execute(
                    "SELECT COUNT(*) FROM history")
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
                        "(time, module, expr, result, favorite, "
                        " favorite_value, tags) "
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

    # ---------------- 内部 ----------------

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
            clauses.append(
                "favorite_value IS NOT NULL AND "
                "favorite_value != ''")
        if tag:
            clauses.append("(',' || tags || ',') LIKE ?")
            params.append(f"%,{tag},%")
        if search:
            clauses.append(
                "(expr LIKE ? OR result LIKE ? OR tags LIKE ?)")
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
        cutoff = (now - datetime.timedelta(
            seconds=self.DEDUP_WINDOW)).strftime(
            "%Y-%m-%d %H:%M:%S")
        with self._lock:
            cur = self._conn.execute(
                "SELECT id FROM history WHERE module=? AND expr=? "
                "AND result=? AND time>=? ORDER BY id DESC LIMIT 1",
                (module, expr, result, cutoff))
            row = cur.fetchone()
            if row:
                self._conn.execute(
                    "UPDATE history SET time=? WHERE id=?",
                    (now_str, row["id"]))
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
            cur = self._conn.execute(
                "SELECT COUNT(*) FROM history")
            total = cur.fetchone()[0]
            if total > self.MAX_ITEMS:
                excess = total - self.MAX_ITEMS
                self._conn.execute(
                    "DELETE FROM history WHERE id IN "
                    "(SELECT id FROM history "
                    " ORDER BY id ASC LIMIT ?)", (excess,))
                self._conn.commit()
            return new_id

    def remove(self, item_id):
        with self._lock:
            self._conn.execute(
                "DELETE FROM history WHERE id=?", (int(item_id),))
            self._conn.commit()

    def clear(self):
        with self._lock:
            self._conn.execute("DELETE FROM history")
            self._conn.commit()

    def clear_module(self, module):
        with self._lock:
            self._conn.execute(
                "DELETE FROM history WHERE module=?", (str(module),))
            self._conn.commit()

    def toggle_favorite(self, item_id) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "SELECT favorite FROM history WHERE id=?",
                (int(item_id),))
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
            tag_str = ",".join(
                str(t).strip() for t in tags if str(t).strip())
        with self._lock:
            self._conn.execute(
                "UPDATE history SET tags=? WHERE id=?",
                (tag_str, int(item_id)))
            self._conn.commit()

    def set_favorite_value(self, item_id, value):
        with self._lock:
            self._conn.execute(
                "UPDATE history SET favorite_value=?, "
                "favorite=1 WHERE id=?",
                (str(value), int(item_id)))
            self._conn.commit()

    def get_favorite_value(self, item_id):
        with self._lock:
            cur = self._conn.execute(
                "SELECT favorite_value FROM history WHERE id=?",
                (int(item_id),))
            row = cur.fetchone()
            return row["favorite_value"] if row else None

    # ---------------- 读取 ----------------

    def get(self, item_id):
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM history WHERE id=?",
                (int(item_id),))
            row = cur.fetchone()
            return self._row_to_dict(row) if row else None

    def list(self, *, module=None, search=None,
             favorites_only=False, tag=None,
             has_favorite_value=False,
             offset=0, limit=200, order="id DESC"):
        where, params = self._build_filter(
            module=module, search=search,
            favorites_only=favorites_only, tag=tag,
            has_favorite_value=has_favorite_value)
        sql = (f"SELECT * FROM history {where} "
               f"ORDER BY {order} LIMIT ? OFFSET ?")
        with self._lock:
            cur = self._conn.execute(
                sql, params + [int(limit), int(offset)])
            return [self._row_to_dict(r) for r in cur.fetchall()]

    def count(self, *, module=None, search=None,
              favorites_only=False, tag=None,
              has_favorite_value=False) -> int:
        where, params = self._build_filter(
            module=module, search=search,
            favorites_only=favorites_only, tag=tag,
            has_favorite_value=has_favorite_value)
        with self._lock:
            cur = self._conn.execute(
                f"SELECT COUNT(*) FROM history {where}", params)
            return int(cur.fetchone()[0])

    def modules(self) -> list:
        with self._lock:
            cur = self._conn.execute(
                "SELECT DISTINCT module FROM history "
                "WHERE module != '' ORDER BY module")
            return [r["module"] for r in cur.fetchall()]

    def tags(self) -> list:
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

    def favorite_values(self) -> list:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM history WHERE favorite_value "
                "IS NOT NULL AND favorite_value != '' "
                "ORDER BY id DESC")
            return [self._row_to_dict(r) for r in cur.fetchall()]

    @property
    def items(self) -> list:
        """全量快照（旧接口兼容）。"""
        return self.list(offset=0, limit=self.MAX_ITEMS * 2)

    # ---------------- 导出 ----------------

    def export_json(self, path: str):
        data = self.items
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def export_csv(self, path: str):
        with open(path, "w", encoding="utf-8-sig",
                  newline="") as f:
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


# ===========================================================================
# Symbols（用户变量 / 函数）
# ===========================================================================

_SYMBOLS_LOCK = threading.RLock()
_SYMBOLS: dict = {}          # name -> sympy 对象
_RAW: dict = {}              # name -> 原始字符串
_PERSIST_PATH: str | None = None

_ASSIGN_RE = re.compile(
    r'^\s*([A-Za-z_]\w*)\s*(\([^)]*\))?\s*=(?!=)\s*(.+)$')


def set_persist_path(path: str):
    global _PERSIST_PATH
    _PERSIST_PATH = path
    _load_symbols()


def match_assignment(s: str):
    """如果是赋值语句，返回 (name, args_str_or_None, rhs)；否则 None。"""
    m = _ASSIGN_RE.match(s)
    if not m:
        return None
    return m.group(1), m.group(2), m.group(3)


def get_all() -> dict:
    with _SYMBOLS_LOCK:
        return dict(_SYMBOLS)


def get_raw() -> dict:
    with _SYMBOLS_LOCK:
        return dict(_RAW)


def get_symbol(name: str, default=None):
    with _SYMBOLS_LOCK:
        return _SYMBOLS.get(name, default)


def has(name: str) -> bool:
    with _SYMBOLS_LOCK:
        return name in _SYMBOLS


def count() -> int:
    with _SYMBOLS_LOCK:
        return len(_SYMBOLS)


def get_variables() -> dict:
    with _SYMBOLS_LOCK:
        return {k: v for k, v in _SYMBOLS.items()
                if not _is_function(v)}


def get_functions() -> dict:
    with _SYMBOLS_LOCK:
        return {k: v for k, v in _SYMBOLS.items()
                if _is_function(v)}


def _is_function(v) -> bool:
    try:
        import sympy as sp
        return isinstance(v, sp.Lambda)
    except Exception:
        return False


def set_symbol(name: str, value, raw: str | None = None):
    with _SYMBOLS_LOCK:
        _SYMBOLS[name] = value
        if raw is not None:
            _RAW[name] = raw
        else:
            try:
                _RAW[name] = str(value)
            except Exception:
                _RAW[name] = ""
    _save_symbols()


def delete_symbol(name: str) -> bool:
    with _SYMBOLS_LOCK:
        existed = name in _SYMBOLS
        _SYMBOLS.pop(name, None)
        _RAW.pop(name, None)
    if existed:
        _save_symbols()
    return existed


def clear_symbols():
    with _SYMBOLS_LOCK:
        _SYMBOLS.clear()
        _RAW.clear()
    _save_symbols()


def export_symbols(path: str) -> bool:
    try:
        with _SYMBOLS_LOCK:
            data = {
                "version": 1,
                "symbols": {
                    name: {
                        "raw": _RAW.get(name, ""),
                        "is_function": _is_function(
                            _SYMBOLS.get(name)),
                    }
                    for name in _SYMBOLS
                },
            }
        os.makedirs(
            os.path.dirname(os.path.abspath(path)) or ".",
            exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def import_symbols(path: str, merge: bool = True) -> dict:
    import sympy as sp

    result = {"imported": 0, "skipped": 0}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return result

    symbols = data.get("symbols") if isinstance(data, dict) else None
    if not isinstance(symbols, dict):
        return result

    if not merge:
        clear_symbols()

    for name, info in symbols.items():
        try:
            raw = (info.get("raw")
                   if isinstance(info, dict) else str(info))
            if not raw:
                result["skipped"] += 1
                continue
            val = sp.sympify(raw)
            set_symbol(name, val, raw)
            result["imported"] += 1
        except Exception:
            result["skipped"] += 1
    return result


# ---------------- 内部：加载 / 保存 ----------------

def _load_symbols():
    if not _PERSIST_PATH or not os.path.exists(_PERSIST_PATH):
        return
    try:
        import sympy as sp
        with open(_PERSIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        with _SYMBOLS_LOCK:
            if isinstance(data, dict):
                items = data.get("symbols", data)
                for name, info in items.items():
                    if isinstance(info, dict) and "raw" in info:
                        raw = str(info["raw"])
                    else:
                        raw = str(info)
                    if not raw:
                        continue
                    try:
                        _SYMBOLS[name] = sp.sympify(raw)
                        _RAW[name] = raw
                    except Exception:
                        pass
    except Exception:
        pass


def _save_symbols():
    if not _PERSIST_PATH:
        return
    try:
        with _SYMBOLS_LOCK:
            out = {
                "version": 1,
                "symbols": {
                    name: {"raw": raw}
                    for name, raw in _RAW.items()
                },
            }
        os.makedirs(os.path.dirname(_PERSIST_PATH),
                    exist_ok=True)
        with open(_PERSIST_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# 默认持久化路径
set_persist_path(os.path.join(
    os.path.expanduser("~"), ".multicalc", "symbols.json"))