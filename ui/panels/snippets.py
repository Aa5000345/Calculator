"""片段管理器面板。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QInputDialog, QMessageBox,
    QAbstractItemView,
)

from core import snippets as snip_mod
from core.logger import log_exc
from .base import CalcPanel


class SnippetsPanel(CalcPanel):
    module_key = "snippets"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        self.search = QLineEdit()
        self.search.setPlaceholderText(i18n.t("search", "搜索"))
        self.search.textChanged.connect(self._reload)

        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.itemDoubleClicked.connect(lambda _: self._insert_current())

        b_add = QPushButton(i18n.t("add", "新增"))
        b_edit = QPushButton(i18n.t("edit", "编辑"))
        b_del = QPushButton(i18n.t("delete", "删除"))
        b_ins = QPushButton(i18n.t("insert", "插入"))

        b_add.clicked.connect(self._add)
        b_edit.clicked.connect(self._edit)
        b_del.clicked.connect(self._delete)
        b_ins.clicked.connect(self._insert_current)

        row = QHBoxLayout()
        for b in (b_add, b_edit, b_del, b_ins):
            row.addWidget(b)
        row.addStretch(1)

        main = QVBoxLayout(self)
        main.addWidget(self.search)
        main.addWidget(self.list, 1)
        main.addLayout(row)

        self._reload()

    def _reload(self):
        self.list.clear()
        q = self.search.text().strip().lower()
        self._items = snip_mod.load()
        for s in self._items:
            text = f"{s.get('name')}  →  {s.get('expr')}"
            tags = s.get("tags") or []
            if tags:
                text += "   #" + " #".join(tags)
            if q and q not in text.lower():
                continue
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, s)
            self.list.addItem(item)

    def _selected(self):
        it = self.list.currentItem()
        return it.data(Qt.UserRole) if it else None

    def _add(self):
        name, ok = QInputDialog.getText(
            self, self.i18n.t("add", "新增"), self.i18n.t("name", "名称"))
        if not ok or not name:
            return
        expr, ok = QInputDialog.getText(
            self, self.i18n.t("add", "新增"), self.i18n.t("expr", "表达式"))
        if not ok or not expr:
            return
        snip_mod.add(name, expr)
        self._reload()

    def _edit(self):
        cur = self._selected()
        if cur is None:
            return
        name, ok = QInputDialog.getText(
            self, self.i18n.t("edit", "编辑"), self.i18n.t("name", "名称"),
            text=cur.get("name", ""))
        if not ok:
            return
        expr, ok = QInputDialog.getText(
            self, self.i18n.t("edit", "编辑"), self.i18n.t("expr", "表达式"),
            text=cur.get("expr", ""))
        if not ok:
            return
        idx = self._items.index(cur)
        snip_mod.update(idx, name, expr, cur.get("tags"))
        self._reload()

    def _delete(self):
        cur = self._selected()
        if cur is None:
            return
        idx = self._items.index(cur)
        snip_mod.remove(idx)
        self._reload()

    def _insert_current(self):
        cur = self._selected()
        if cur is None:
            return
        expr = cur.get("expr", "")
        try:
            from ui.signals import bus
            # 复用 send_to_unit 机制：发送到 basic 面板
            # 这里改为剪贴板 + 提示
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(expr)
            QMessageBox.information(
                self, "OK",
                self.i18n.t("copied", "已复制到剪贴板") + f"\n{expr}")
        except Exception as e:
            log_exc(e, module="SnippetsPanel._insert_current")