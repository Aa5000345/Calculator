"""示例插件：演示 plugin_api 的各种注册方式。

启用方式：
1. 把 plugin.json 的 "enabled" 改为 true
2. 重启应用
3. 命令面板（Ctrl+K）里搜 "Hello" 或 "示例"
4. 菜单 → 工具 → 「示例：显示消息」
5. 侧边栏 → 「工具」组 → 「示例面板」
"""
from __future__ import annotations

from core.plugin_api import (
    PanelPlugin,
    plugin_metadata,
    register_command,
    register_menu,
    register_panel,
    register_theme,
)


# ===========================================================================
# 面板
# ===========================================================================

@register_panel
class ExamplePanel(PanelPlugin):
    key = "example_panel"
    group = "工具"
    title_key = "example_panel"
    title_default = "示例面板"
    keywords = ("example", "demo", "示例", "插件")
    priority = 200

    def create_widget(self, ctx):
        from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabel(
            "👋 这是由插件注册的面板。\n\n"
            "如果你能看到这段文字，说明插件加载成功。"))
        v.addStretch(1)
        return w


# ===========================================================================
# 命令
# ===========================================================================

@register_command("example_hello", "Hello from plugin",
                  group="plugin",
                  keywords=("example", "hello", "示例"))
def _cmd_hello(ctx):
    try:
        from PySide6.QtWidgets import QMessageBox
        win = None
        try:
            win = ctx.get("main_window") if ctx else None
        except Exception:
            pass
        QMessageBox.information(
            win, "Example Plugin",
            "你好！这是示例插件注册的命令。")
    except Exception:
        print("Hello from example plugin")


@register_command("example_system_info",
                  "Show system info",
                  group="plugin",
                  keywords=("system", "info", "系统"))
def _cmd_system_info(ctx):
    import platform
    import sys
    info = (
        f"Python: {sys.version.split()[0]}\n"
        f"Platform: {platform.platform()}\n"
        f"Machine: {platform.machine()}")
    try:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(None, "System Info", info)
    except Exception:
        print(info)


# ===========================================================================
# 菜单项
# ===========================================================================

@register_menu("工具/示例：显示消息", "示例：显示消息")
def _menu_show_msg(ctx):
    try:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            None, "Example Plugin",
            "这是插件注册的菜单项。")
    except Exception:
        pass


# ===========================================================================
# 主题
# ===========================================================================

register_theme(
    name="example_theme",
    label="Example Theme",
    palette={
        "bg": "#1a1b26",
        "fg": "#c0caf5",
        "panel": "#24283b",
        "accent": "#7aa2f7",
        "border": "#414868",
        "hover": "#3b4261",
    })


# ===========================================================================
# 入口
# ===========================================================================

@plugin_metadata(
    name="Example Command",
    version="1.0.0",
    description="演示 plugin_api 的各种注册方式",
    author="MultiCalc",
)
def register(app_context):
    """插件入口（可选）。

    如果插件只用装饰器注册，可以省略此函数。
    如果需要动态注册（依赖运行时状态），在此处执行。

    Args:
        app_context: 包含 settings / i18n / history / main_window
    """
    print("[example_command] registered with app_context:",
          list((app_context or {}).keys()))