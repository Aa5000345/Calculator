"""设置管理：默认值 + 用户覆盖 + 热重载 + 导入导出 + 草稿（带防抖写盘）
+ 主题文件扫描（config/themes/*.json）。

修复历史：
- update() 逐 key 通知监听器（原为 notify(None)，导致 language 热切换失效）
- save()/export_to() 不再写入 _drafts（避免与 draft.json 重复）
- 增加线程锁，避免后台 Worker 与 UI 并发修改
- reload_if_changed() 忽略 _drafts 差异
- set_draft() 使用 300ms 防抖，避免每次按键都写盘
- 提供 flush() 供应用退出时强制冲刷草稿
- palette() 支持从 config/themes/*.json 读取主题
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
        self._load_theme_files()

        self._listeners: list = []

    # ==================================================================
    # 读写
    # ==================================================================

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
        # 主题文件可能变化，重新扫描
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
            self._load_theme_files()
            self.save()
        if notify:
            self._notify(None)

    # ==================================================================
    # 导入 / 导出
    # ==================================================================

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
        self._load_theme_files()
        self.save()
        self._notify(None)

    # ==================================================================
    # 草稿（防抖）
    # ==================================================================

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

    # ==================================================================
    # 监听器
    # ==================================================================

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

    # ==================================================================
    # 主题文件扫描
    # ==================================================================

    def _load_theme_files(self):
        """扫描 config/themes/*.json，作为可选主题加载到 self.data['_themes']。

        default_path 一般位于 <base>/config/default_settings.json，
        因此主题目录位于 <base>/config/themes/。
        """
        themes_dir = os.path.join(
            os.path.dirname(self.default_path), "themes")
        out = {}
        if os.path.isdir(themes_dir):
            for fn in sorted(os.listdir(themes_dir)):
                if not fn.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(themes_dir, fn),
                              "r", encoding="utf-8") as f:
                        info = json.load(f)
                    name = info.get("name") or os.path.splitext(fn)[0]
                    pal = info.get("palette") or {}
                    if name and isinstance(pal, dict):
                        out[name] = {
                            "label": info.get("label", name),
                            "palette": pal,
                        }
                except Exception:
                    pass
        self.data["_themes"] = out

    def themes(self):
        """返回 {name: {"label": ..., "palette": {...}}}。

        合并 default_settings.json 里的 palette 与 config/themes/*.json。
        """
        result = {}
        for name, pal in (self.default.get("palette") or {}).items():
            result[name] = {"label": name, "palette": pal}
        for name, info in (self.data.get("_themes") or {}).items():
            result[name] = info
        return result

    def save_theme(self, name, label, palette):
        """保存主题到 config/themes/{name}.json。返回路径或 None。"""
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

    def delete_theme(self, name):
        """删除 config/themes/{name}.json。"""
        themes_dir = os.path.join(
            os.path.dirname(self.default_path), "themes")
        try:
            path = os.path.join(themes_dir, f"{name}.json")
            if os.path.exists(path):
                os.remove(path)
            self._load_theme_files()
        except Exception:
            pass

    # ==================================================================
    # 配色 / 汇率 / 模块
    # ==================================================================

    def palette(self, theme_override=None):
        """返回当前主题的调色板字典。

        优先级：
        1. 用户在 settings.json 的 palette 字段中自定义的
        2. config/themes/*.json 中的主题
        3. default_settings.json 中的 dark 兜底
        """
        theme = theme_override or self.get("theme", "dark")
        if theme == "system":
            theme = "dark"

        # 1) 用户自定义 palette
        pal = self.get("palette", {}) or {}
        if theme in pal:
            return pal[theme]

        # 2) 主题文件
        themes = self.data.get("_themes") or {}
        if theme in themes:
            return themes[theme]["palette"]

        # 3) 兜底
        return pal.get("dark", {
            "bg": "#1e1e1e", "fg": "#ffffff", "panel": "#2d2d30",
            "accent": "#007acc", "border": "#3f3f46", "hover": "#3a3d41"})

    def set_palette_color(self, key, color):
        """为当前主题设置单个调色板颜色（写入用户 palette 字段）。"""
        theme = self.get("theme", "dark")
        if theme == "system":
            theme = "dark"
        pal = dict(self.get("palette", {}) or {})
        # 若当前主题来自主题文件（不在 pal 中），需要以文件主题为基底
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