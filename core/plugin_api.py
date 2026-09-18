"""插件 API：定义插件可以实现的接口。

插件通过**装饰器**或**继承基类**的方式，向运行时注册扩展点。

支持的扩展点：
    PanelPlugin     —— 注册新面板
    CommandPlugin   —— 注册命令面板命令
    ThemePlugin     —— 注册主题
    RatePlugin      —— 注册汇率源（包装 core.rates.RateSource）
    MenuPlugin      —— 向主菜单添加项
    StatusPlugin    —— 向状态栏添加小组件

用法示例：

    from core.plugin_api import (
        PanelPlugin, CommandPlugin, register_panel, register_command,
    )

    # 方式 1：继承 + 装饰器
    @register_panel
    class MyPanel(PanelPlugin):
        key = "my_panel"
        group = "工具"
        title_key = "my_panel"
        title_default = "My Panel"
        keywords = ("demo", "示例")

        def create_widget(self, ctx):
            from PySide6.QtWidgets import QLabel
            return QLabel("Hello from plugin!")

    # 方式 2：直接用装饰器注册函数
    @register_command("mycmd", "My Command", group="plugin")
    def my_command(ctx):
        print("Command executed")

    # 方式 3：通过 register_theme 注册主题
    register_theme(
        name="my_theme",
        label="My Theme",
        palette={
            "bg": "#1e1e2e", "fg": "#cdd6f4",
            "panel": "#313244", "accent": "#cba6f7",
            "border": "#45475a", "hover": "#45475a",
        })
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# ===========================================================================
# 基类
# ===========================================================================

class PanelPlugin:
    """面板插件基类。

    子类必须定义：
        key             —— 面板唯一 ID（如 "my_panel"）
        title_default   —— 面板标题（i18n 缺失时的默认值）

    子类可选定义：
        group           —— 分组名（默认"插件"）
        title_key       —— i18n key（默认 = key）
        keywords        —— 搜索关键词
        priority        —— 排序优先级（小者靠前，默认 100）

    子类必须实现：
        create_widget(ctx) -> QWidget
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
    """命令插件基类。

    子类必须定义：
        command_id      —— 命令唯一 ID
        title_default   —— 命令标题
        run(ctx)        —— 执行函数
    """
    command_id: str = ""
    title_default: str = ""
    title_key: str = ""
    group: str = "plugin"
    keywords: tuple = ()

    def run(self, ctx) -> Any:
        raise NotImplementedError


class MenuPlugin:
    """菜单项插件基类。

    子类必须定义：
        menu_path       —— 菜单路径，如 "工具/我的插件"
        run(ctx)        —— 点击时执行
    """
    menu_path: str = ""
    title_default: str = ""
    title_key: str = ""

    def run(self, ctx) -> Any:
        raise NotImplementedError


@dataclass
class ThemeDef:
    """主题定义。"""
    name: str
    label: str
    palette: dict = field(default_factory=dict)


@dataclass
class RateSourceDef:
    """汇率源定义（包装已有 RateSource）。"""
    source: Any = None        # RateSource 实例


# ===========================================================================
# 装饰器 / 注册函数
# ===========================================================================

def register_panel(cls_or_instance=None):
    """注册面板插件。

    用法：
        @register_panel
        class MyPanel(PanelPlugin):
            ...

    或：
        register_panel(MyPanel)
    """
    from core.plugin_registry import get_registry

    def _do(cls):
        try:
            reg = get_registry()
            reg.add_panel(cls)
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
    """注册命令。

    用法：
        @register_command("mycmd", "My Command")
        def my_command(ctx):
            ...
    """
    from core.plugin_registry import get_registry

    def _do(fn):
        try:
            reg = get_registry()
            reg.add_command(
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
    """注册菜单项。

    用法：
        @register_menu("工具/我的工具", "打开我的工具")
        def _open(ctx):
            ...
    """
    from core.plugin_registry import get_registry

    def _do(fn):
        try:
            reg = get_registry()
            reg.add_menu(
                menu_path=menu_path,
                title_default=title_default or menu_path,
                title_key=title_key or menu_path,
                fn=fn,
            )
        except Exception:
            pass
        return fn

    return _do


def register_theme(name: str, label: str, palette: dict):
    """注册主题。"""
    from core.plugin_registry import get_registry
    try:
        reg = get_registry()
        reg.add_theme(ThemeDef(name=name, label=label,
                               palette=dict(palette or {})))
        return True
    except Exception:
        return False


def register_rate_source(source):
    """注册汇率源（RateSource 实例）。"""
    from core.plugin_registry import get_registry
    try:
        reg = get_registry()
        reg.add_rate_source(source)
        return True
    except Exception:
        return False


def register_status_widget(factory: Callable,
                           position: str = "right"):
    """注册状态栏小组件。

    Args:
        factory: ``fn(ctx) -> QWidget``
        position: ``"left"`` / ``"right"``
    """
    from core.plugin_registry import get_registry
    try:
        reg = get_registry()
        reg.add_status_widget(factory, position)
        return True
    except Exception:
        return False


# ===========================================================================
# 工具
# ===========================================================================

def plugin_metadata(name: str = "",
                    version: str = "",
                    description: str = "",
                    author: str = ""):
    """装饰器：给插件的 register() 函数附加元数据。

    用法：
        @plugin_metadata("My Plugin", "1.0", "一句话", "作者")
        def register(app_context):
            ...
    """
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


__all__ = [
    "PanelPlugin",
    "CommandPlugin",
    "MenuPlugin",
    "ThemeDef",
    "RateSourceDef",
    "register_panel",
    "register_command",
    "register_menu",
    "register_theme",
    "register_rate_source",
    "register_status_widget",
    "plugin_metadata",
]