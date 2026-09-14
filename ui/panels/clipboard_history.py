"""剪贴板历史：监听系统剪贴板、可搜索、可固定。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QHBoxLayout, QAbstractItemView,
)

from .base import CalcPanel


class ClipboardHistoryPanel(CalcPanel):
    module_key = "clipboard_history"

    MAX = 200

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)
        self._items: list[dict] = []

        self.search = QLineEdit()
        self.search.setPlaceholderText(i18n.t("search", "搜索"))
        self.search.textChanged.connect(self._refresh)

        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.itemDoubleClicked.connect(lambda _: self._copy_current())

        b_copy = QPushButton(i18n.t("copy", "复制"))
        b_pin = QPushButton(i18n.t("pin", "固定"))
        b_clear = QPushButton(i18n.t("clear", "清空"))
        b_copy.clicked.connect(self._copy_current)
        b_pin.clicked.connect(self._toggle_pin)
        b_clear.clicked.connect(self._clear)

        row = QHBoxLayout()
        for b in (b_copy, b_pin, b_clear):
            row.addWidget(b)
        row.addStretch(1)

        main = QVBoxLayout(self)
        main.addWidget(self.search)
        main.addWidget(self.list, 1)
        main.addLayout(row)

        cb = QApplication.clipboard()
        cb.dataChanged.connect(self._on_clipboard)
        self._last_text = ""
        self._refresh()

    def _on_clipboard(self):
        try:
            t = QApplication.clipboard().text()
        except Exception:
            return
        if not t or t == self._last_text:
            return
        self._last_text = t
        self._items.insert(0, {"text": t, "pinned": False})
        # 保留最多 MAX 条，固定项不丢
        if len(self._items) > self.MAX:
            keep = [x for x in self._items if x["pinned"]]
            others = [x for x in self._items if not x["pinned"]]
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
        QApplication.clipboard().setText(self._items[i]["text"])
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