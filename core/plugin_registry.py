"""插件运行时注册表：管理面板 / 命令 / 主题 / 汇率源 / 菜单项。

设计：
- 全局单例
- 线程安全（RLock）
- 支持注册、枚举、查询来源
- 提供 snapshot() 便于 UI 展示

对外接口：
    get_registry() -> PluginRegistry
    registry.panels() -> list
    registry.commands() -> list
    registry.themes() -> list
    registry.rate_sources() -> list
    registry.menus() -> list
    registry.status_widgets() -> list
    registry.clear_all()
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# ---------------------------------------------------------------------------
# 记录
# ---------------------------------------------------------------------------

@dataclass
class PanelRecord:
    cls: Any                     # PanelPlugin 子类
    source: str = ""             # 来源插件名
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
    theme: Any                   # ThemeDef
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


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------

class PluginRegistry:
    """插件运行时注册表。

    由 get_registry() 返回单例。
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._panels: list[PanelRecord] = []
        self._commands: list[CommandRecord] = []
        self._menus: list[MenuRecord] = []
        self._themes: list[ThemeRecord] = []
        self._rates: list[RateSourceRecord] = []
        self._status: list[StatusWidgetRecord] = []

        # 当前正在加载的插件名（用于标记 source）
        self._current_source = ""

    # ==================================================================
    # 上下文管理：标记来源
    # ==================================================================

    def set_source(self, name: str):
        self._current_source = str(name or "")

    def current_source(self) -> str:
        return self._current_source

    # ==================================================================
    # 注册
    # ==================================================================

    def add_panel(self, cls) -> bool:
        if cls is None:
            return False
        key = getattr(cls, "key", "")
        if not key:
            return False
        with self._lock:
            # 去重：同 key 覆盖
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

    # ==================================================================
    # 枚举
    # ==================================================================

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

    # ==================================================================
    # 按来源查询 / 启停
    # ==================================================================

    def records_by_source(self, source: str) -> dict:
        """返回某个插件注册的所有内容。"""
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
        """启用 / 禁用某个插件注册的所有内容。"""
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
        """移除某个插件的所有注册（用于卸载）。"""
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

    # ==================================================================
    # 清空
    # ==================================================================

    def clear_all(self):
        with self._lock:
            self._panels.clear()
            self._commands.clear()
            self._menus.clear()
            self._themes.clear()
            self._rates.clear()
            self._status.clear()

    # ==================================================================
    # 快照
    # ==================================================================

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


# ---------------------------------------------------------------------------
# 单例
# ---------------------------------------------------------------------------

_REGISTRY: Optional[PluginRegistry] = None
_LOCK = threading.RLock()


def get_registry() -> PluginRegistry:
    global _REGISTRY
    with _LOCK:
        if _REGISTRY is None:
            _REGISTRY = PluginRegistry()
        return _REGISTRY


__all__ = [
    "PanelRecord",
    "CommandRecord",
    "MenuRecord",
    "ThemeRecord",
    "RateSourceRecord",
    "StatusWidgetRecord",
    "PluginRegistry",
    "get_registry",
]