"""命令面板（Ctrl+K）：模糊搜索并执行动作。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QLabel,
)

from core.logger import log_exc


def _fuzzy_score(query: str, target: str) -> int:
    """简单子序列匹配打分；越高越匹配。"""
    q = query.lower()
    t = target.lower()
    if not q:
        return 1
    if q in t:
        return 1000 - t.index(q)
    i = 0
    for ch in t:
        if i < len(q) and ch == q[i]:
            i += 1
    if i == len(q):
        return 500 - len(t)
    return 0


class CommandPalette(QDialog):
    def __init__(self, i18n, commands, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self._commands = list(commands)
        self._filtered = list(commands)

        self.setWindowTitle(i18n.t("command_palette", "Command palette"))
        self.setWindowFlag(Qt.FramelessWindowHint, False)
        self.resize(520, 380)

        self.search = QLineEdit()
        self.search.setPlaceholderText(
            i18n.t("type_to_search", "Type to search…"))
        self.search.textChanged.connect(self._on_change)
        self.search.returnPressed.connect(self._run_current)

        self.list = QListWidget()
        self.list.itemActivated.connect(lambda _: self._run_current())
        self.list.itemClicked.connect(lambda _: self._run_current())

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(i18n.t("command_palette", "Command palette")))
        lay.addWidget(self.search)
        lay.addWidget(self.list, 1)

        self._refresh()

    def _on_change(self, text):
        text = text.strip()
        scored = []
        for title, cb in self._commands:
            s = _fuzzy_score(text, title)
            if s > 0:
                scored.append((s, title, cb))
        scored.sort(key=lambda x: -x[0])
        self._filtered = [(t, cb) for _, t, cb in scored]
        self._refresh()

    def _refresh(self):
        self.list.clear()
        for title, _ in self._filtered[:200]:
            self.list.addItem(QListWidgetItem(title))
        if self.list.count():
            self.list.setCurrentRow(0)

    def _run_current(self):
        row = self.list.currentRow()
        if 0 <= row < len(self._filtered):
            _, cb = self._filtered[row]
            self.accept()
            try:
                cb()
            except Exception as e:
                log_exc(e, module="CommandPalette.run")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
            return
        if event.key() in (Qt.Key_Down, Qt.Key_Up):
            self.list.setFocus()
            self.list.keyPressEvent(event)
            return
        super().keyPressEvent(event)

    @staticmethod
    def shortcut():
        return QKeySequence("Ctrl+K")