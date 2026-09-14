"""全局快捷键安装。

主窗口级：
    Ctrl+1..9    切换第 N 个可见模块
    Ctrl+,       打开设置面板
    Ctrl+Shift+L 切换侧边栏

面板级：
    Ctrl+Enter   计算
    Esc          取消运行中的任务
    Ctrl+L       清空输入
    Up / Down    历史表达式召回
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut


def install_main_window_shortcuts(window):
    # Ctrl+1..Ctrl+9 切换可见模块
    for i in range(1, 10):
        sc = QShortcut(QKeySequence(f"Ctrl+{i}"), window)
        sc.setContext(Qt.ApplicationShortcut)
        sc.activated.connect(
            lambda idx=i - 1: _switch_visible_index(window, idx))

    # Ctrl+, 打开设置
    sc = QShortcut(QKeySequence("Ctrl+,"), window)
    sc.setContext(Qt.ApplicationShortcut)
    sc.activated.connect(lambda: _switch_by_key(window, "settings"))

    # Ctrl+Shift+L 切换侧边栏
    sc = QShortcut(QKeySequence("Ctrl+Shift+L"), window)
    sc.setContext(Qt.ApplicationShortcut)
    sc.activated.connect(window.toggle_sidebar)


def _switch_visible_index(window, idx):
    try:
        keys = window._visible_keys_in_order()
        if 0 <= idx < len(keys):
            window.switch_to_key(keys[idx])
    except Exception:
        pass


def _switch_by_key(window, key):
    try:
        window.switch_to_key(key)
    except Exception:
        pass


def install_panel_shortcuts(panel, *,
                            on_calc=None, on_cancel=None,
                            on_clear=None, expr_widget=None,
                            history_getter=None):
    """给面板安装通用快捷键。

    参数
    ----
    panel        : QWidget
    on_calc      : callable | None
    on_cancel    : callable | None
    on_clear     : callable | None
    expr_widget  : QLineEdit | QPlainTextEdit | None 用于 Up/Down 历史召回
    history_getter : callable() -> list[str]  历史表达式列表
    """
    shortcuts = []

    if on_calc is not None and expr_widget is not None:
        sc = QShortcut(QKeySequence("Ctrl+Return"), panel)
        sc.activated.connect(on_calc)
        shortcuts.append(sc)

    if on_cancel is not None:
        sc = QShortcut(QKeySequence(Qt.Key_Escape), panel)
        sc.activated.connect(on_cancel)
        shortcuts.append(sc)

    if on_clear is not None:
        sc = QShortcut(QKeySequence("Ctrl+L"), panel)
        sc.activated.connect(on_clear)
        shortcuts.append(sc)

    if expr_widget is not None and history_getter is not None:
        _install_history_recall(panel, expr_widget, history_getter,
                                shortcuts)

    panel._panel_shortcuts = shortcuts


def _install_history_recall(panel, widget, history_getter, shortcuts):
    """Up / Down 在输入框中循环召回历史。"""
    try:
        from PySide6.QtWidgets import QLineEdit, QPlainTextEdit
    except Exception:
        return

    state = {"index": -1}

    def _set_text(t):
        if isinstance(widget, QLineEdit):
            widget.setText(t)
            widget.setCursorPosition(len(t))
        elif isinstance(widget, QPlainTextEdit):
            widget.setPlainText(t)

    def _recall(direction):
        try:
            items = list(history_getter() or [])
            if not items:
                return
            if direction < 0:  # Up
                if state["index"] == -1:
                    state["index"] = 0
                else:
                    state["index"] = min(state["index"] + 1, len(items) - 1)
            else:  # Down
                if state["index"] == -1:
                    return
                state["index"] -= 1
                if state["index"] < 0:
                    state["index"] = -1
                    _set_text("")
                    return
            _set_text(items[state["index"]])
        except Exception:
            pass

    up = QShortcut(QKeySequence("Up"), widget)
    up.setContext(Qt.WidgetShortcut)
    up.activated.connect(lambda: _recall(-1))
    shortcuts.append(up)

    down = QShortcut(QKeySequence("Down"), widget)
    down.setContext(Qt.WidgetShortcut)
    down.activated.connect(lambda: _recall(1))
    shortcuts.append(down)