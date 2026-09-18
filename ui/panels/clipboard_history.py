"""剪贴板历史：监听系统剪贴板、可搜索、可固定、可智能识别表达式。"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QApplication, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QVBoxLayout, QHBoxLayout,
    QAbstractItemView, QCheckBox,
)

from core import clipboard_monitor
from .base import CalcPanel


class ClipboardHistoryPanel(CalcPanel):
    module_key = "clipboard_history"

    MAX = 200

    expr_detected = Signal(str)

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)
        self._items: list = []

        # ---------------- 搜索 ----------------
        self.search = QLineEdit()
        self.search.setPlaceholderText(
            i18n.t("search", "搜索"))
        self.search.textChanged.connect(self._refresh)

        # ---------------- 列表 ----------------
        self.list = QListWidget()
        self.list.setSelectionMode(
            QAbstractItemView.SingleSelection)
        self.list.itemDoubleClicked.connect(
            lambda _: self._copy_current())

        # ---------------- 按钮 ----------------
        b_copy = QPushButton(i18n.t("copy", "复制"))
        b_pin = QPushButton(i18n.t("pin", "固定"))
        b_clear = QPushButton(i18n.t("clear", "清空"))
        b_copy.clicked.connect(self._copy_current)
        b_pin.clicked.connect(self._toggle_pin)
        b_clear.clicked.connect(self._clear)

        # ---------------- 智能识别开关 ----------------
        self.smart_detect = QCheckBox(
            i18n.t("clipboard_smart_detect",
                   "智能识别表达式"))
        self.smart_detect.setChecked(
            bool(settings.get("clipboard_smart_detect",
                              False)))
        self.smart_detect.stateChanged.connect(
            self._on_smart_toggle)

        self.smart_toast = QCheckBox(
            i18n.t("clipboard_smart_toast",
                   "识别后弹提示"))
        self.smart_toast.setChecked(
            bool(settings.get("clipboard_smart_toast", True)))
        self.smart_toast.stateChanged.connect(
            lambda _: settings.set(
                "clipboard_smart_toast",
                self.smart_toast.isChecked()))

        row = QHBoxLayout()
        for b in (b_copy, b_pin, b_clear):
            row.addWidget(b)
        row.addStretch(1)

        smart_row = QHBoxLayout()
        smart_row.addWidget(self.smart_detect)
        smart_row.addWidget(self.smart_toast)
        smart_row.addStretch(1)

        main = QVBoxLayout(self)
        main.addWidget(self.search)
        main.addLayout(smart_row)
        main.addWidget(self.list, 1)
        main.addLayout(row)

        # ---------------- 内部信号 → bus 转发 ----------------
        self.expr_detected.connect(self._forward_to_bus)

        # ---------------- 剪贴板监听 ----------------
        self._monitor = clipboard_monitor.ClipboardMonitor(self)

        cb = QApplication.clipboard()
        cb.dataChanged.connect(self._on_clipboard)
        self._last_text = ""
        self._refresh()

        if self.smart_detect.isChecked():
            QTimer.singleShot(0, self._start_monitor)

    # ==================================================================

    def _forward_to_bus(self, text):
        try:
            from ui.signals import bus
            bus().clipboard_expr.emit(str(text))
        except Exception:
            pass

    def _on_smart_toggle(self, state):
        try:
            self.settings.set(
                "clipboard_smart_detect", bool(state))
        except Exception:
            pass
        if state:
            self._start_monitor()
        else:
            self._stop_monitor()

    def _start_monitor(self):
        try:
            self._monitor.start(self._on_expr_detected)
        except Exception:
            pass

    def _stop_monitor(self):
        try:
            self._monitor.stop()
        except Exception:
            pass

    def _on_expr_detected(self, text):
        if not self.smart_detect.isChecked():
            return
        try:
            self.expr_detected.emit(text)
        except Exception:
            pass

    def closeEvent(self, e):
        try:
            self._stop_monitor()
        except Exception:
            pass
        super().closeEvent(e)

    # ==================================================================

    def _on_clipboard(self):
        try:
            t = QApplication.clipboard().text()
        except Exception:
            return
        if not t or t == self._last_text:
            return
        self._last_text = t
        self._items.insert(0, {"text": t, "pinned": False})
        if len(self._items) > self.MAX:
            keep = [x for x in self._items if x["pinned"]]
            others = [x for x in self._items
                      if not x["pinned"]]
            others = others[: self.MAX - len(keep)]
            self._items = keep + others
        self._refresh()

    def _refresh(self):
        q = self.search.text().strip().lower()
        self.list.clear()
        for i, item in enumerate(self._items):
            text = item["text"]
            if q and q not in text.lower():
                continue
            star = "📌 " if item["pinned"] else ""
            preview = text.replace("\n", " ⏎ ")[:120]
            li = QListWidgetItem(f"{star}{preview}")
            li.setData(Qt.UserRole, i)
            self.list.addItem(li)

    def _current_index(self):
        it = self.list.currentItem()
        return it.data(Qt.UserRole) if it else None

    def _copy_current(self):
        i = self._current_index()
        if i is None:
            return
        QApplication.clipboard().setText(
            self._items[i]["text"])
        self._last_text = self._items[i]["text"]

    def _toggle_pin(self):
        i = self._current_index()
        if i is None:
            return
        self._items[i]["pinned"] = not self._items[i]["pinned"]
        self._refresh()

    def _clear(self):
        self._items = [x for x in self._items if x["pinned"]]
        self._refresh()


__all__ = ["ClipboardHistoryPanel"]