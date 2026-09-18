"""输入框版本历史：一个小按钮 + 下拉列表。

用法：
    hist = InputHistoryButton(settings, i18n, key="basic.expr",
                              parent=panel)
    hist.version_selected.connect(on_restore)
    layout.addWidget(hist)

    # 或在 attach 时自动记录
    hist.attach(line_edit)
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMenu, QPushButton, QVBoxLayout, QWidget,
)

from core import input_history as ih
from core.logger import log_exc


class InputHistoryButton(QPushButton):
    """输入框历史按钮（🕘）。

    - 单击：弹出下拉列表
    - 选择项：发出 version_selected 信号
    - 长按 / 右键：菜单（清空历史）
    """

    version_selected = Signal(str)

    def __init__(self, settings, i18n, key: str, parent=None):
        super().__init__("🕘", parent)
        self.settings = settings
        self.i18n = i18n
        self.key = str(key or "")
        self._target = None
        self._record_timer = QTimer(self)
        self._record_timer.setSingleShot(True)
        self._record_timer.setInterval(800)  # 800ms 防抖
        self._record_timer.timeout.connect(self._do_record)

        self.setFixedSize(26, 24)
        self.setToolTip(i18n.t(
            "input_history_tip", "查看历史版本"))
        self.setFocusPolicy(Qt.NoFocus)
        self.clicked.connect(self._show_menu)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context)

    # ==================================================================

    def attach(self, widget):
        """附着到输入框，自动记录变化。"""
        self._target = widget
        try:
            widget.textChanged.connect(self._on_text_changed)
        except AttributeError:
            try:
                widget.textChanged.connect(self._on_text_changed)
            except Exception:
                pass
        # 初始记录一次
        try:
            t = self._read_text()
            if t:
                ih.record(self.key, t)
        except Exception:
            pass

    def _on_text_changed(self, *_):
        self._record_timer.start()

    def _do_record(self):
        try:
            t = self._read_text()
            ih.record(self.key, t)
        except Exception:
            pass

    def _read_text(self) -> str:
        w = self._target
        if w is None:
            return ""
        try:
            if hasattr(w, "text"):
                return w.text()
            if hasattr(w, "toPlainText"):
                return w.toPlainText()
        except Exception:
            pass
        return ""

    def _write_text(self, text: str):
        w = self._target
        if w is None:
            return
        try:
            if hasattr(w, "setText"):
                w.setText(text)
                if hasattr(w, "setCursorPosition"):
                    w.setCursorPosition(len(text))
            elif hasattr(w, "setPlainText"):
                w.setPlainText(text)
        except Exception:
            pass

    # ==================================================================

    def _show_menu(self):
        try:
            versions = ih.list_versions(self.key)
        except Exception as e:
            log_exc(e, module="InputHistoryButton._show_menu")
            return

        if not versions:
            self.setToolTip(
                self.i18n.t("input_history_empty", "暂无历史"))
            return

        menu = QMenu(self)
        for i, v in enumerate(versions[:20]):
            text = str(v.get("text") or "")
            preview = text.replace("\n", " ⏎ ")
            if len(preview) > 60:
                preview = preview[:57] + "…"
            ts = str(v.get("time") or "")[-8:]  # HH:MM:SS
            act = menu.addAction(f"{ts}  {preview}")
            act.triggered.connect(
                lambda _=False, t=text: self._on_selected(t))

        menu.addSeparator()
        a_clear = menu.addAction(
            self.i18n.t("input_history_clear", "清空本输入框历史"))
        a_clear.triggered.connect(self._clear)

        menu.exec(self.mapToGlobal(self.rect().bottomLeft()))

    def _on_selected(self, text: str):
        self._write_text(text)
        try:
            self.version_selected.emit(text)
        except Exception:
            pass

    def _show_context(self, pos):
        menu = QMenu(self)
        a_clear = menu.addAction(
            self.i18n.t("input_history_clear", "清空本输入框历史"))
        a_clear.triggered.connect(self._clear)
        menu.exec(self.mapToGlobal(pos))

    def _clear(self):
        ih.clear(self.key)
        self.setToolTip(
            self.i18n.t("input_history_cleared", "历史已清空"))