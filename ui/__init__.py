"""UI 包：Qt 界面层。

合并后的新布局：

    ui.main_window    主窗口
    ui.shell          Qt 运行期辅助：信号总线 / 状态栏 / 分屏 / Toast / 托盘
    ui.shortcuts      全局与面板快捷键安装
    ui.dialogs        各类对话框：命令面板 / 快捷键速查 / 模块可见性 /
                      主题编辑器 / LaTeX 渲染组件
    ui.panels/        面板
    ui.widgets/       自定义组件

设计原则：
- ui/ 依赖 core/ 和 PySide6
- 面板之间通过 ui.shell.bus() 通信，不直接互相 import
- 本 __init__ 不做子模块导入，避免导入期实例化 Qt 对象
"""
from __future__ import annotations

__all__: list = []