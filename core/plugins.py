"""插件系统：API + 运行时注册表 + 加载器。

合并自：core/plugin_api.py + core/plugin_registry.py + core/plugins.py

对外接口：
    # 扩展点基类
    PanelPlugin, CommandPlugin, MenuPlugin,
    ThemeDef, RateSourceDef
    # 装饰器 / 注册函数
    register_panel, register_command, register_menu,
    register_theme, register_rate_source,
    register_status_widget, plugin_metadata
    # 注册表
    PluginRegistry, get_registry
    # 加载器
    PluginInfo, discover, load_plugin, load_all, unload_plugin
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from core.base import log_info, log_warn

__all__ = [
    # 基类
    "PanelPlugin", "CommandPlugin", "MenuPlugin",
    "ThemeDef", "RateSourceDef",
    # 装饰器
    "register_panel", "register_command", "register_menu",
    "register_theme", "register_rate_source",
    "register_status_widget", "plugin_metadata",
    # 注册表
    "PluginRegistry", "get_registry",
    # 加载器
    "PluginInfo", "discover", "load_plugin", "load_all",
    "unload_plugin",
]


# ===========================================================================
# 扩展点基类
# ===========================================================================

class PanelPlugin:
    """面板插件基类。

    子类必须定义 key / title_default；实现 create_widget(ctx)。
    """
    key: str = ""
    group: str = "插件"
    title_key: str = ""
    title_default: str = ""
    keywords: tuple = ()
    priority: int = 100

    def create_widget(self, ctx) -> Any:
        raise NotImplementedError


class CommandPlugin:
    command_id: str = ""
    title_default: str = ""
    title_key: str = ""
    group: str = "plugin"
    keywords: tuple = ()

    def run(self, ctx) -> Any:
        raise NotImplementedError


class MenuPlugin:
    menu_path: str = ""
    title_default: str = ""
    title_key: str = ""

    def run(self, ctx) -> Any:
        raise NotImplementedError


@dataclass
class ThemeDef:
    name: str
    label: str
    palette: dict = field(default_factory=dict)


@dataclass
class RateSourceDef:
    source: Any = None


# ===========================================================================
# 装饰器 / 注册函数
# ===========================================================================

def register_panel(cls_or_instance=None):
    """注册面板插件。可用于装饰器，也可直接调用。"""
    def _do(cls):
        try:
            get_registry().add_panel(cls)
        except Exception:
            pass
        return cls

    if cls_or_instance is None:
        return _do
    return _do(cls_or_instance)


def register_command(command_id: str,
                     title_default: str = "",
                     group: str = "plugin",
                     title_key: str = "",
                     keywords: tuple = ()):
    """注册命令。"""
    def _do(fn):
        try:
            get_registry().add_command(
                command_id=command_id,
                title_default=title_default or command_id,
                title_key=title_key or command_id,
                group=group,
                keywords=keywords,
                fn=fn,
            )
        except Exception:
            pass
        return fn
    return _do


def register_menu(menu_path: str,
                  title_default: str = "",
                  title_key: str = ""):
    """注册菜单项。"""
    def _do(fn):
        try:
            get_registry().add_menu(
                menu_path=menu_path,
                title_default=title_default or menu_path,
                title_key=title_key or menu_path,
                fn=fn,
            )
        except Exception:
            pass
        return fn
    return _do


def register_theme(name: str, label: str, palette: dict) -> bool:
    try:
        get_registry().add_theme(
            ThemeDef(name=name, label=label,
                     palette=dict(palette or {})))
        return True
    except Exception:
        return False


def register_rate_source(source) -> bool:
    try:
        get_registry().add_rate_source(source)
        return True
    except Exception:
        return False


def register_status_widget(factory: Callable,
                           position: str = "right") -> bool:
    try:
        get_registry().add_status_widget(factory, position)
        return True
    except Exception:
        return False


def plugin_metadata(name: str = "",
                    version: str = "",
                    description: str = "",
                    author: str = ""):
    """给插件的 register() 函数附加元数据。"""
    def _do(fn):
        try:
            setattr(fn, "_plugin_meta", {
                "name": name, "version": version,
                "description": description, "author": author,
            })
        except Exception:
            pass
        return fn
    return _do


# ===========================================================================
# 注册表记录
# ===========================================================================

@dataclass
class PanelRecord:
    cls: Any
    source: str = ""
    enabled: bool = True


@dataclass
class CommandRecord:
    command_id: str
    title_default: str
    title_key: str
    group: str
    keywords: tuple
    fn: Callable
    source: str = ""
    enabled: bool = True

    def display_title(self, i18n=None) -> str:
        if i18n is not None and self.title_key:
            try:
                t = i18n.t(self.title_key, None)
                if t and t != self.title_key:
                    return t
            except Exception:
                pass
        return self.title_default


@dataclass
class MenuRecord:
    menu_path: str
    title_default: str
    title_key: str
    fn: Callable
    source: str = ""
    enabled: bool = True

    def display_title(self, i18n=None) -> str:
        if i18n is not None and self.title_key:
            try:
                t = i18n.t(self.title_key, None)
                if t and t != self.title_key:
                    return t
            except Exception:
                pass
        return self.title_default


@dataclass
class ThemeRecord:
    theme: Any
    source: str = ""
    enabled: bool = True


@dataclass
class RateSourceRecord:
    source_obj: Any
    source: str = ""
    enabled: bool = True


@dataclass
class StatusWidgetRecord:
    factory: Callable
    position: str = "right"
    source: str = ""
    enabled: bool = True


# ===========================================================================
# 注册表
# ===========================================================================

class PluginRegistry:
    """插件运行时注册表。"""

    def __init__(self):
        self._lock = threading.RLock()
        self._panels: list = []
        self._commands: list = []
        self._menus: list = []
        self._themes: list = []
        self._rates: list = []
        self._status: list = []
        self._current_source = ""

    # ---------------- 上下文：标记来源 ----------------

    def set_source(self, name: str):
        self._current_source = str(name or "")

    def current_source(self) -> str:
        return self._current_source

    # ---------------- 注册 ----------------

    def add_panel(self, cls) -> bool:
        if cls is None:
            return False
        key = getattr(cls, "key", "")
        if not key:
            return False
        with self._lock:
            self._panels = [
                p for p in self._panels
                if getattr(p.cls, "key", "") != key]
            self._panels.append(PanelRecord(
                cls=cls, source=self._current_source))
        return True

    def add_command(self, command_id: str,
                    title_default: str,
                    title_key: str,
                    group: str,
                    keywords: tuple,
                    fn: Callable) -> bool:
        if not command_id or fn is None:
            return False
        with self._lock:
            self._commands = [
                c for c in self._commands
                if c.command_id != command_id]
            self._commands.append(CommandRecord(
                command_id=command_id,
                title_default=title_default,
                title_key=title_key,
                group=group,
                keywords=tuple(keywords or ()),
                fn=fn,
                source=self._current_source,
            ))
        return True

    def add_menu(self, menu_path: str,
                 title_default: str,
                 title_key: str,
                 fn: Callable) -> bool:
        if not menu_path or fn is None:
            return False
        with self._lock:
            self._menus.append(MenuRecord(
                menu_path=menu_path,
                title_default=title_default,
                title_key=title_key,
                fn=fn,
                source=self._current_source,
            ))
        return True

    def add_theme(self, theme) -> bool:
        name = getattr(theme, "name", "")
        if not name:
            return False
        with self._lock:
            self._themes = [
                t for t in self._themes
                if getattr(t.theme, "name", "") != name]
            self._themes.append(ThemeRecord(
                theme=theme, source=self._current_source))
        return True

    def add_rate_source(self, source) -> bool:
        if source is None:
            return False
        with self._lock:
            self._rates.append(RateSourceRecord(
                source_obj=source,
                source=self._current_source))
        return True

    def add_status_widget(self, factory: Callable,
                          position: str = "right") -> bool:
        if factory is None:
            return False
        pos = "left" if str(position).lower() == "left" else "right"
        with self._lock:
            self._status.append(StatusWidgetRecord(
                factory=factory, position=pos,
                source=self._current_source))
        return True

    # ---------------- 枚举 ----------------

    def panels(self) -> list:
        with self._lock:
            return [p for p in self._panels if p.enabled]

    def commands(self) -> list:
        with self._lock:
            return [c for c in self._commands if c.enabled]

    def menus(self) -> list:
        with self._lock:
            return [m for m in self._menus if m.enabled]

    def themes(self) -> list:
        with self._lock:
            return [t for t in self._themes if t.enabled]

    def rate_sources(self) -> list:
        with self._lock:
            return [r for r in self._rates if r.enabled]

    def status_widgets(self, position: Optional[str] = None) -> list:
        with self._lock:
            items = [s for s in self._status if s.enabled]
        if position:
            pos = str(position).lower()
            items = [s for s in items if s.position == pos]
        return items

    # ---------------- 按来源查询 / 启停 ----------------

    def records_by_source(self, source: str) -> dict:
        s = str(source or "")
        with self._lock:
            return {
                "panels": [p for p in self._panels
                           if p.source == s],
                "commands": [c for c in self._commands
                             if c.source == s],
                "menus": [m for m in self._menus
                          if m.source == s],
                "themes": [t for t in self._themes
                           if t.source == s],
                "rates": [r for r in self._rates
                          if r.source == s],
                "status": [w for w in self._status
                           if w.source == s],
            }

    def set_enabled(self, source: str, enabled: bool):
        s = str(source or "")
        v = bool(enabled)
        with self._lock:
            for lst in (self._panels, self._commands,
                        self._menus, self._themes,
                        self._rates, self._status):
                for r in lst:
                    if r.source == s:
                        r.enabled = v

    def remove_source(self, source: str):
        s = str(source or "")
        with self._lock:
            self._panels = [p for p in self._panels
                            if p.source != s]
            self._commands = [c for c in self._commands
                              if c.source != s]
            self._menus = [m for m in self._menus
                           if m.source != s]
            self._themes = [t for t in self._themes
                            if t.source != s]
            self._rates = [r for r in self._rates
                           if r.source != s]
            self._status = [w for w in self._status
                            if w.source != s]

    def clear_all(self):
        with self._lock:
            self._panels.clear()
            self._commands.clear()
            self._menus.clear()
            self._themes.clear()
            self._rates.clear()
            self._status.clear()

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "panels": [
                    {"key": getattr(p.cls, "key", ""),
                     "group": getattr(p.cls, "group", ""),
                     "source": p.source, "enabled": p.enabled}
                    for p in self._panels
                ],
                "commands": [
                    {"id": c.command_id, "group": c.group,
                     "source": c.source, "enabled": c.enabled}
                    for c in self._commands
                ],
                "menus": [
                    {"path": m.menu_path, "source": m.source,
                     "enabled": m.enabled}
                    for m in self._menus
                ],
                "themes": [
                    {"name": getattr(t.theme, "name", ""),
                     "source": t.source, "enabled": t.enabled}
                    for t in self._themes
                ],
                "rates": [
                    {"name": getattr(r.source_obj, "name", ""),
                     "source": r.source, "enabled": r.enabled}
                    for r in self._rates
                ],
                "status": [
                    {"position": w.position, "source": w.source,
                     "enabled": w.enabled}
                    for w in self._status
                ],
            }


_PLUGIN_REGISTRY: Optional[PluginRegistry] = None
_REGISTRY_LOCK = threading.RLock()


def get_registry() -> PluginRegistry:
    global _PLUGIN_REGISTRY
    with _REGISTRY_LOCK:
        if _PLUGIN_REGISTRY is None:
            _PLUGIN_REGISTRY = PluginRegistry()
        return _PLUGIN_REGISTRY


# ===========================================================================
# 加载器
# ===========================================================================

class PluginInfo:
    def __init__(self, path, name, version="", description="",
                 author="", enabled=True):
        self.path = path
        self.name = name
        self.version = version
        self.description = description
        self.author = author
        self.enabled = enabled

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "enabled": self.enabled,
            "path": self.path,
        }

    def __repr__(self):
        return (f"<PluginInfo name={self.name!r} "
                f"v{self.version} enabled={self.enabled}>")


def discover(plugin_root: str) -> list:
    """扫描 plugin_root 下每个子目录。"""
    if not os.path.isdir(plugin_root):
        return []
    out = []
    for entry in sorted(os.listdir(plugin_root)):
        sub = os.path.join(plugin_root, entry)
        if not os.path.isdir(sub):
            continue
        info = _read_meta(sub, entry)
        if info:
            out.append(info)
    return out


def _read_meta(sub, fallback_name):
    meta_path = os.path.join(sub, "plugin.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                d = json.load(f)
            return PluginInfo(
                path=sub,
                name=d.get("name") or fallback_name,
                version=d.get("version", ""),
                description=d.get("description", ""),
                author=d.get("author", ""),
                enabled=bool(d.get("enabled", True)),
            )
        except Exception as e:  # noqa: BLE001
            log_warn(
                f"plugin.json 读取失败 {meta_path}: {e}",
                module="plugins")

    init_py = os.path.join(sub, "__init__.py")
    if os.path.exists(init_py):
        return PluginInfo(path=sub, name=fallback_name)
    return None


def load_plugin(info: PluginInfo, app_context=None) -> bool:
    """把插件作为模块加载；失败只记录日志。

    加载前调用 registry.set_source(info.name)，
    这样插件内通过装饰器注册的扩展点都会被标记来源。
    """
    if not info.enabled:
        return False
    init_py = os.path.join(info.path, "__init__.py")
    if not os.path.exists(init_py):
        return False

    try:
        mod_name = f"multicalc_plugin_{os.path.basename(info.path)}"
        spec = importlib.util.spec_from_file_location(
            mod_name, init_py,
            submodule_search_locations=[info.path])
        if spec is None or spec.loader is None:
            return False

        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod

        try:
            get_registry().set_source(info.name)
        except Exception:
            pass

        spec.loader.exec_module(mod)

        fn = getattr(mod, "register", None)
        if callable(fn):
            try:
                fn(app_context)
            except Exception as e:  # noqa: BLE001
                log_warn(
                    f"plugin register failed {info.name}: {e}",
                    module="plugins")

        log_info(f"plugin loaded: {info.name}",
                 module="plugins")
        return True

    except Exception as e:  # noqa: BLE001
        log_warn(f"plugin load failed {info.name}: {e}",
                 module="plugins")
        return False
    finally:
        try:
            get_registry().set_source("")
        except Exception:
            pass


def load_all(plugin_root: str, app_context=None) -> dict:
    """加载 plugin_root 下所有已启用的插件。"""
    infos = discover(plugin_root)
    result = {
        "root": plugin_root,
        "total": len(infos),
        "enabled": 0,
        "loaded": 0,
        "failed": 0,
        "details": [],
    }

    for info in infos:
        detail = {
            "name": info.name,
            "path": info.path,
            "enabled": bool(info.enabled),
            "ok": False,
            "error": "",
        }
        if not info.enabled:
            detail["error"] = "disabled"
            result["details"].append(detail)
            continue

        result["enabled"] += 1
        try:
            ok = load_plugin(info, app_context)
        except Exception as e:  # noqa: BLE001
            ok = False
            detail["error"] = str(e)

        detail["ok"] = bool(ok)
        if ok:
            result["loaded"] += 1
        else:
            result["failed"] += 1
            if not detail["error"]:
                detail["error"] = "load failed"
        result["details"].append(detail)

    log_info(
        f"plugins loaded: {result['loaded']}/{result['enabled']} "
        f"(total {result['total']})",
        module="plugins")
    return result


def unload_plugin(info: PluginInfo) -> bool:
    """从运行时注册表移除某插件的所有注册。"""
    try:
        get_registry().remove_source(info.name)
        log_info(f"plugin unloaded: {info.name}",
                 module="plugins")
        return True
    except Exception as e:  # noqa: BLE001
        log_warn(f"plugin unload failed {info.name}: {e}",
                 module="plugins")
        return False