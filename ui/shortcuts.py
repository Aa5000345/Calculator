"""全局快捷键安装（支持用户自定义 + 元数据驱动）。

变更历史：
- 第 1 轮：初版
- 第 4 轮：从 core.shortcut_config 读取键位
- 第 13 轮：加 snapshot_save / snapshot_timeline
- 第 18 轮：
  - 改为遍历 core.shortcut_meta 自动安装
  - 支持双键序列（如 "Ctrl+K Z"）
  - 按 scope 分组安装（global / panel / widget）

主窗口级（scope=global）：由 shortcut_meta 定义
面板级（scope=panel）：由 install_panel_shortcuts 安装
输入框级（scope=widget）：由 _install_history_recall 安装
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut

from core import shortcut_config as sc_cfg
from core import shortcut_meta as sc_meta


# ===========================================================================
# 主窗口级快捷键
# ===========================================================================

# command_id → MainWindow 方法名
_GLOBAL_HANDLERS = {
    "global.settings": "_open_settings_via_shortcut",
    "global.shortcuts_help": "_show_shortcuts",
    "global.quit": "_quit_app",
    "global.command_palette": "open_command_palette",
    "global.toggle_keyboard": "toggle_keyboard",
    "global.handwriting": "open_handwriting",
    "global.ocr": "open_ocr_input",
    "global.glyph_panel": "_open_glyph_panel_via_shortcut",
    "global.toggle_sidebar": "toggle_sidebar",
    "global.open_in_split": "open_current_in_split",
    "global.close_split": "close_split",
    "global.focus_mode": "toggle_focus_mode",
    "global.toggle_tray": "_toggle_tray",
    "global.new_window": "_new_window_via_shortcut",
    "global.snapshot_save": "_save_snapshot_via_shortcut",
    "global.snapshot_timeline": "_open_snapshot_dialog_via_shortcut",
    "global.check_update": "_check_update",
    "global.export_session": "_export_session_via_shortcut",
    "global.import_session": "import_session",
}


def install_main_window_shortcuts(window):
    """安装主窗口级快捷键（从 shortcut_meta + shortcut_config 读取）。"""
    # 清空旧的（reload 时）
    for sc in getattr(window, "_main_shortcuts", []) or []:
        try:
            sc.setEnabled(False)
            sc.deleteLater()
        except Exception:
            pass
    window._main_shortcuts = []

    # 遍历元数据里的所有 global 作用域命令
    for m in sc_meta.all_metas():
        if m.scope != "global":
            continue
        key = sc_cfg.get(m.command_id)
        if not key:
            continue

        # 模块切换（nav.module_N）特殊处理
        if m.command_id.startswith("nav.module_"):
            try:
                n = int(m.command_id.rsplit("_", 1)[1])
            except Exception:
                continue
            _add_shortcut(
                window, key,
                lambda w=window, idx=n - 1:
                _switch_visible_index(w, idx))
            continue

        # 常规命令：查 handler 名
        handler_name = _GLOBAL_HANDLERS.get(m.command_id)
        if not handler_name:
            continue
        handler = getattr(window, handler_name, None)
        if not callable(handler):
            continue
        _add_shortcut(window, key, handler)

    # 兼容：硬编码的 Ctrl+1..9 已通过 nav.module_N 覆盖
    # 若用户把 nav.module_1 清空，会自然不安装


def reload_main_window_shortcuts(window):
    """重新安装（用于快捷键自定义后刷新）。"""
    install_main_window_shortcuts(window)


def _add_shortcut(window, seq_text: str, callback,
                  context=Qt.ApplicationShortcut):
    """安装一个 QShortcut 并记录下来。"""
    if not seq_text or not callable(callback):
        return None
    try:
        sc = QShortcut(QKeySequence(seq_text), window)
        sc.setContext(context)
        sc.activated.connect(callback)
        window._main_shortcuts.append(sc)
        return sc
    except Exception:
        return None


def _switch_visible_index(window, idx):
    try:
        keys = window._visible_keys_in_order()
        if 0 <= idx < len(keys):
            window.switch_to_key(keys[idx])
    except Exception:
        pass


# ===========================================================================
# 面板级快捷键
# ===========================================================================

def install_panel_shortcuts(panel, *,
                            on_calc=None, on_cancel=None,
                            on_clear=None, on_undo=None,
                            expr_widget=None, history_getter=None):
    """给面板安装通用快捷键（从 shortcut_meta + shortcut_config 读取）。

    会覆盖 scope=panel 的：
        panel.calc / panel.cancel / panel.clear / panel.undo
    以及 scope=widget 的：
        panel.history_up / panel.history_down
    """
    shortcuts = []

    def _add(seq_text, cb, context=Qt.WidgetWithChildrenShortcut):
        if not seq_text or cb is None:
            return
        try:
            sc = QShortcut(QKeySequence(seq_text), panel)
            sc.setContext(context)
            sc.activated.connect(cb)
            shortcuts.append(sc)
        except Exception:
            pass

    # panel.calc
    if on_calc is not None:
        _add(sc_cfg.get("panel.calc"), on_calc)
    # panel.cancel
    if on_cancel is not None:
        _add(sc_cfg.get("panel.cancel"), on_cancel,
             context=Qt.WidgetWithChildrenShortcut)
    # panel.clear
    if on_clear is not None:
        _add(sc_cfg.get("panel.clear"), on_clear)
    # panel.undo
    if on_undo is not None:
        _add(sc_cfg.get("panel.undo"), on_undo)

    # 历史召回（widget scope）
    if expr_widget is not None and history_getter is not None:
        _install_history_recall(
            panel, expr_widget, history_getter, shortcuts)

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
            if direction < 0:      # Up
                if state["index"] == -1:
                    state["index"] = 0
                else:
                    state["index"] = min(
                        state["index"] + 1, len(items) - 1)
            else:                  # Down
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

    up_key = sc_cfg.get("panel.history_up") or "Up"
    down_key = sc_cfg.get("panel.history_down") or "Down"

    up = QShortcut(QKeySequence(up_key), widget)
    up.setContext(Qt.WidgetShortcut)
    up.activated.connect(lambda: _recall(-1))
    shortcuts.append(up)

    down = QShortcut(QKeySequence(down_key), widget)
    down.setContext(Qt.WidgetShortcut)
    down.activated.connect(lambda: _recall(1))
    shortcuts.append(down)


__all__ = [
    "install_main_window_shortcuts",
    "reload_main_window_shortcuts",
    "install_panel_shortcuts",
]