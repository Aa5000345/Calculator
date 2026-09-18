"""数字系统转换面板：阿拉伯 ↔ 罗马 / 中文 / 英文 / 摩尔斯。

变更历史：
- 第 6.5 轮：新增
- 第 13 轮：InputHistoryButton
"""
from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView,
)

from core import number_systems as ns
from core.errors import InputError
from core.logger import log_exc
from ui.shortcuts import install_panel_shortcuts
from ._common import ResultView, InlinePreviewBar
from .base import CalcPanel


class NumberSystemsPanel(CalcPanel):
    module_key = "number_systems"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)
        self._calc_start = None

        # ---------------- 输入区 ----------------
        self.value = QLineEdit("2024")
        self.primary_input = self.value
        self.value.textChanged.connect(
            lambda t: settings.set_draft("ns_value", t))
        self.value.returnPressed.connect(self.calc)
        draft = settings.get_draft("ns_value", "")
        if draft:
            self.value.setText(draft)

        self.from_sys = QComboBox()
        self.to_sys = QComboBox()
        for s in ns.list_systems():
            label = i18n.t(f"ns_{s['key']}", s["label"])
            self.from_sys.addItem(label, s["key"])
            self.to_sys.addItem(label, s["key"])
        self.from_sys.setCurrentIndex(
            self.from_sys.findData("arabic"))
        self.to_sys.setCurrentIndex(
            self.to_sys.findData("roman"))

        self.from_sys.currentIndexChanged.connect(
            lambda _: self.preview.refresh(self.value.text()))
        self.to_sys.currentIndexChanged.connect(
            lambda _: self.preview.refresh(self.value.text()))

        # ---------------- 按钮 ----------------
        self.calc_btn = QPushButton(i18n.t("calc", "转换"))
        self.calc_btn.setMinimumHeight(32)
        self.calc_btn.clicked.connect(self.calc)

        self.swap_btn = QPushButton("⇄")
        self.swap_btn.setFixedWidth(36)
        self.swap_btn.setToolTip(
            i18n.t("ns_swap", "交换源/目标系统"))
        self.swap_btn.clicked.connect(self._swap)

        # ---------------- 实时预览 ----------------
        self.preview = InlinePreviewBar(calc_fn=self._preview)
        self.preview.attach(
            self.value, enabled_getter=lambda: True)

        # ---------------- 结果 ----------------
        self.result = ResultView(i18n)

        # ---------------- 对照表 ----------------
        self.ref_table = QTableWidget(0, 6)
        self.ref_table.setHorizontalHeaderLabels([
            i18n.t("ns_arabic", "阿拉伯"),
            i18n.t("ns_roman", "罗马"),
            i18n.t("ns_chinese", "中文"),
            i18n.t("ns_chinese_formal", "大写"),
            i18n.t("ns_english", "英文"),
            i18n.t("ns_morse", "摩尔斯"),
        ])
        self.ref_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self.ref_table.verticalHeader().setVisible(False)
        self.ref_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers)
        self.ref_table.setSelectionBehavior(
            QAbstractItemView.SelectRows)
        self.ref_table.setMaximumHeight(240)
        self._fill_ref_table()

        # ---------------- 布局 ----------------
        top = QHBoxLayout()
        top.addWidget(QLabel(
            i18n.t("ns_input", "输入")))
        top.addWidget(self.value, 1)

        # 输入历史按钮（第 13 轮）
        try:
            from ui.widgets.input_history_widget import (
                InputHistoryButton,
            )
            self.history_btn = InputHistoryButton(
                settings, i18n, "number_systems.value", self)
            self.history_btn.attach(self.value)
            top.addWidget(self.history_btn)
        except Exception:
            self.history_btn = None

        top.addWidget(self.make_kb_button())

        sys_row = QHBoxLayout()
        sys_row.addWidget(QLabel(
            i18n.t("ns_from", "源系统")))
        sys_row.addWidget(self.from_sys, 1)
        sys_row.addWidget(self.swap_btn)
        sys_row.addWidget(QLabel(
            i18n.t("ns_to", "目标系统")))
        sys_row.addWidget(self.to_sys, 1)

        main = QVBoxLayout(self)
        main.addLayout(top)
        main.addLayout(sys_row)
        main.addWidget(self.preview)
        main.addWidget(self.calc_btn)
        main.addWidget(QLabel(i18n.t("result", "结果")))
        main.addWidget(self.result, 2)
        main.addWidget(QLabel(
            i18n.t("ns_ref_table", "对照表")))
        main.addWidget(self.ref_table, 1)

        install_panel_shortcuts(
            self,
            on_calc=self.calc,
            on_cancel=self.cancel_current,
            on_clear=self._clear,
            on_undo=self.undo,
            expr_widget=self.value,
            history_getter=self._history_exprs,
        )

        sc_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        sc_undo.setContext(Qt.WidgetWithChildrenShortcut)
        sc_undo.activated.connect(self.undo)
        self._undo_sc = sc_undo

    # ==================================================================

    def _swap(self):
        try:
            i = self.from_sys.currentIndex()
            j = self.to_sys.currentIndex()
            self.from_sys.setCurrentIndex(j)
            self.to_sys.setCurrentIndex(i)
        except Exception:
            pass

    def _preview(self, text):
        s = (text or "").strip()
        if not s:
            return None
        try:
            return ns.convert(
                s,
                self.from_sys.currentData(),
                self.to_sys.currentData())
        except Exception:
            return None

    def _clear(self):
        try:
            self.push_undo()
            self.value.clear()
            self.result.show_result("", "")
        except Exception:
            pass

    def _history_exprs(self):
        try:
            rows = self.history.list(
                module="number_systems", limit=50,
                order="id DESC")
            return [r["expr"] for r in rows if r.get("expr")]
        except Exception:
            return []

    def calc(self):
        s = self.value.text().strip()
        if not s:
            self.result.show_error(
                InputError("输入为空",
                           friendly_key="err_empty_expr"))
            return
        self.push_undo()
        self._calc_start = time.time()
        try:
            out = ns.convert(
                s,
                self.from_sys.currentData(),
                self.to_sys.currentData())
            elapsed = time.time() - self._calc_start
            self.result.show_result(
                str(out), "", elapsed=elapsed)
            self.add_history(
                f"{s} ({self.from_sys.currentText()} → "
                f"{self.to_sys.currentText()})",
                str(out),
                module="number_systems")
        except Exception as e:
            self.result.show_error(e, retry_cb=self.calc)

    def _fill_ref_table(self):
        self.ref_table.setRowCount(0)
        for n in range(1, 21):
            r = self.ref_table.rowCount()
            self.ref_table.insertRow(r)
            try:
                vals = [
                    str(n),
                    ns.to_roman(n),
                    ns.to_chinese(n),
                    ns.to_chinese(n, formal=True),
                    ns.to_english(n),
                    ns.to_morse(n),
                ]
            except Exception:
                vals = [str(n), "", "", "", "", ""]
            for c, v in enumerate(vals):
                self.ref_table.setItem(
                    r, c, QTableWidgetItem(v))


__all__ = ["NumberSystemsPanel"]