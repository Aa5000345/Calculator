"""设置管理：默认值 + 用户覆盖 + 热重载 + 导入导出 + 草稿（带防抖写盘）。

修复：
- update() 逐 key 通知监听器（原为 notify(None)，导致 language 热切换失效）
- save()/export_to() 不再写入 _drafts（避免与 draft.json 重复）
- 增加线程锁，避免后台 Worker 与 UI 并发修改
- reload_if_changed() 忽略 _drafts 差异
- set_draft() 使用 300ms 防抖，避免每次按键都写盘
- 提供 flush() 供应用退出时强制冲刷草稿
"""
from __future__ import annotations

import copy
import json
import os
import threading


_DRAFT_DEBOUNCE_SEC = 0.3


class Settings:
    def __init__(self, default_path):
        self.default_path = default_path
        self.user_dir = os.path.join(os.path.expanduser("~"), ".multicalc")
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

        self._listeners = []

    # ---------------- 读写 ----------------

    def _load_user(self):
        if not os.path.exists(self.user_path):
            return
        try:
            with open(self.user_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data.pop("_drafts", None)  # 兼容旧文件
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
        current = {k: v for k, v in self.data.items() if k != "_drafts"}
        if disk == current:
            return False
        merged = copy.deepcopy(self.default)
        merged.update(disk)
        if "_drafts" in self.data:
            merged["_drafts"] = self.data["_drafts"]
        self.data = merged
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
        """批量更新：逐 key 触发监听器，避免 language 热切换失效。"""
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
            clean = {k: v for k, v in self.data.items() if k != "_drafts"}
            with open(self.user_path, "w", encoding="utf-8") as f:
                json.dump(clean, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def reset(self, notify=True):
        with self._lock:
            self.data = copy.deepcopy(self.default)
            self.save()
        if notify:
            self._notify(None)

    # ---------------- 导入 / 导出 ----------------

    def export_to(self, path):
        clean = {k: v for k, v in self.data.items() if k != "_drafts"}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False, indent=2)

    def import_from(self, path):
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
        self.save()
        self._notify(None)

    # ---------------- 草稿（防抖） ----------------

    def _load_drafts(self):
        if not os.path.exists(self.draft_path):
            return
        try:
            with open(self.draft_path, "r", encoding="utf-8") as f:
                self.data["_drafts"] = json.load(f)
        except Exception:
            pass

    def set_draft(self, key, value):
        """写入草稿（内存），延迟 300ms 批量写盘。"""
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
                with open(self.draft_path, "w", encoding="utf-8") as f:
                    json.dump(drafts, f, ensure_ascii=False, indent=2)
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

    # ---------------- 配色 / 汇率 / 模块 ----------------

    def palette(self, theme_override=None):
        theme = theme_override or self.get("theme", "dark")
        if theme == "system":
            theme = "dark"
        pal = self.get("palette", {}) or {}
        return pal.get(theme, pal.get("dark", {
            "bg": "#1e1e1e", "fg": "#ffffff", "panel": "#2d2d30",
            "accent": "#007acc", "border": "#3f3f46", "hover": "#3a3d41"}))

    def set_palette_color(self, key, color):
        theme = self.get("theme", "dark")
        pal = dict(self.get("palette", {}))
        theme_pal = dict(pal.get(theme, {}))
        theme_pal[key] = color
        pal[theme] = theme_pal
        self.set("palette", pal)

    def get_manual_rate(self, pair):
        rates = self.get("manual_rates", {}) or {}
        return rates.get(pair)

    def set_manual_rate(self, pair, rate):
        rates = dict(self.get("manual_rates", {}) or {})
        rates[pair] = float(rate)
        self.set("manual_rates", rates)

    def is_module_visible(self, key):
        vm = self.get("visible_modules", {}) or {}
        return vm.get(key, True)

    def set_module_visible(self, key, visible):
        vm = dict(self.get("visible_modules", {}) or {})
        vm[key] = bool(visible)
        self.set("visible_modules", vm)