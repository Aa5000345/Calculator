"""自定义 widget 集合（合并后）。

     ui.widgets.input      焦点 / 键按钮 / 输入历史 /
                           建议气泡 / 差异徽章 / 空状态
     ui.widgets.keyboard   键盘布局 DSL + 浮动计算器键盘
     ui.widgets.tools      手写 / OCR / 绘图动画
     ui.widgets.dialogs    快照 / 更新 / 插件 / 导览 /
                           欢迎页 / 快捷键编辑器

向后兼容别名：
    COMPACT_LAYOUT = keyboard.LAYOUT_BASIC
    SCI_LAYOUT     = keyboard.LAYOUT_SCIENTIFIC
"""
from __future__ import annotations

# ---- input ----
from .input import (
    FocusTracker,
    KeyButton,
    InputHistoryButton,
    SuggestionBubble,
    DiffBadge,
    EmptyState,
)

# ---- keyboard ----
from .keyboard import (
    Key,
    Layout,
    get_layout,
    get_layout_name,
    all_module_keys,
    LAYOUT_BASIC,
    LAYOUT_SCIENTIFIC,
    LAYOUT_DEFAULT,
    LAYOUT_MATRIX,
    LAYOUT_PLOT,
    LAYOUT_PLOT3D,
    LAYOUT_FINANCE,
    LAYOUT_DATE,
    LAYOUT_UNIT,
    LAYOUT_CURRENCY,
    LAYOUT_BASE,
    LAYOUT_BITS,
    LAYOUT_CRYPTO,
    LAYOUT_LATEX,
    LAYOUT_SCRIPT,
    CalcKeyboard,
)

# 向后兼容别名
COMPACT_LAYOUT = LAYOUT_BASIC
SCI_LAYOUT = LAYOUT_SCIENTIFIC

# ---- tools（延迟导入，避免顶层 import torch） ----
try:
    from .tools import HandwritingDialog, OCRInputDialog
except Exception:
    HandwritingDialog = None
    OCRInputDialog = None

# ---- dialogs（延迟导入） ----
try:
    from .dialogs import (
        SnapshotDialog,
        UpdateDialog,
        PluginManagerDialog,
        QuickTour,
        WelcomeWidget,
        ShortcutEditor,
    )
except Exception:
    SnapshotDialog = None
    UpdateDialog = None
    PluginManagerDialog = None
    QuickTour = None
    WelcomeWidget = None
    ShortcutEditor = None


__all__ = [
    # input
    "FocusTracker", "KeyButton", "InputHistoryButton",
    "SuggestionBubble", "DiffBadge", "EmptyState",
    # keyboard
    "Key", "Layout",
    "get_layout", "get_layout_name", "all_module_keys",
    "LAYOUT_BASIC", "LAYOUT_SCIENTIFIC", "LAYOUT_DEFAULT",
    "LAYOUT_MATRIX", "LAYOUT_PLOT", "LAYOUT_PLOT3D",
    "LAYOUT_FINANCE", "LAYOUT_DATE", "LAYOUT_UNIT",
    "LAYOUT_CURRENCY", "LAYOUT_BASE", "LAYOUT_BITS",
    "LAYOUT_CRYPTO", "LAYOUT_LATEX", "LAYOUT_SCRIPT",
    "COMPACT_LAYOUT", "SCI_LAYOUT",
    "CalcKeyboard",
    # tools
    "HandwritingDialog", "OCRInputDialog",
    # dialogs
    "SnapshotDialog", "UpdateDialog", "PluginManagerDialog",
    "QuickTour", "WelcomeWidget", "ShortcutEditor",
]