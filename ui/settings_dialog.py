"""模块可见性 / 排序对话框。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)


class ModuleVisibilityDialog(QDialog):
    """一个对话框完成模块显隐 + 拖拽排序。

    使用：
        dlg = ModuleVisibilityDialog(i18n, current_order, default_order,
                                     titles, visible_getter, parent)
        if dlg.exec() == QDialog.Accepted:
            order, vis = dlg.result_state()
    """

    def __init__(self, i18n, current_order, default_order,
                 titles, visible_getter, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self._default_order = list(default_order)
        self.setWindowTitle(i18n.t("module_visibility", "Module visibility"))
        self.resize(460, 520)

        self.list = QListWidget()
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.setDefaultDropAction(Qt.MoveAction)
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.setAlternatingRowColors(True)

        for key in current_order:
            item = QListWidgetItem(titles.get(key, key))
            item.setData(Qt.UserRole, key)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(
                Qt.Checked if visible_getter(key) else Qt.Unchecked)
            self.list.addItem(item)

        btn_all = QPushButton(i18n.t("select_all", "Select all"))
        btn_none = QPushButton(i18n.t("select_none", "Select none"))
        btn_reset = QPushButton(i18n.t("reset_order", "Reset order"))
        btn_all.clicked.connect(lambda: self._set_all(Qt.Checked))
        btn_none.clicked.connect(lambda: self._set_all(Qt.Unchecked))
        btn_reset.clicked.connect(self._reset_order)

        hint = QLabel(i18n.t(
            "module_visibility_hint",
            "勾选显示，拖拽调整顺序；点击 OK 生效。"))

        top = QHBoxLayout()
        top.addWidget(btn_all)
        top.addWidget(btn_none)
        top.addWidget(btn_reset)
        top.addStretch(1)

        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(hint)
        lay.addLayout(top)
        lay.addWidget(self.list, 1)
        lay.addWidget(box)

    # ---------------- 操作 ----------------

    def _set_all(self, state):
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(state)

    def _reset_order(self):
        # 保存现有勾选状态
        state_by_key = {}
        for i in range(self.list.count()):
            it = self.list.item(i)
            state_by_key[it.data(Qt.UserRole)] = it.checkState()

        # 以 default_order 顺序重排；default 中没有的键放到末尾
        order = [k for k in self._default_order if k in state_by_key]
        order += [k for k in state_by_key if k not in order]

        self.list.clear()
        for key in order:
            item = QListWidgetItem(key)
            item.setData(Qt.UserRole, key)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(state_by_key.get(key, Qt.Checked))
            self.list.addItem(item)

    def result_state(self):
        """返回 ``(order, visibility_map)``。"""
        order = []
        vis = {}
        for i in range(self.list.count()):
            it = self.list.item(i)
            key = it.data(Qt.UserRole)
            order.append(key)
            vis[key] = it.checkState() == Qt.Checked
        return order, vis