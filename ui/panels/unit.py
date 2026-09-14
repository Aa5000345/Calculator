"""单位换算面板：接收来自其他面板的"发送到单位面板"。"""
from __future__ import annotations

import re

from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QGridLayout, QComboBox, QWidget, QTableWidget,
    QTableWidgetItem, QHeaderView,
)

from core import engine
from core import units as unit_mod
from core.logger import log_exc
from ui.signals import bus
from ._common import _clear_layout, friendly_error
from .base import CalcPanel


class UnitPanel(CalcPanel):
    module_key = "unit"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        self.category = QComboBox()
        for key in unit_mod.categories():
            label = unit_mod.get_category(key)["label"]
            self.category.addItem(label, key)
        last_cat = settings.get("unit_category", "length")
        idx = self.category.findData(last_cat)
        if idx >= 0:
            self.category.setCurrentIndex(idx)
        self.category.currentIndexChanged.connect(self._on_category_changed)

        self.value = QLineEdit("1")
        self.from_u = QComboBox()
        self.to_u = QComboBox()
        for c in (self.from_u, self.to_u):
            c.setEditable(True)

        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)

        self.quick_box = QWidget()
        self.quick_row = QHBoxLayout(self.quick_box)
        self.quick_row.setContentsMargins(0, 0, 0, 0)

        self.batch_targets = QLineEdit()
        self.batch_table = QTableWidget(0, 2)
        self.batch_table.setHorizontalHeaderLabels(
            [i18n.t("unit", "Unit"), i18n.t("value", "Value")])
        self.batch_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self.batch_table.setFixedHeight(180)

        btn = QPushButton(i18n.t("convert"))
        btn.clicked.connect(self.convert)
        btn_batch = QPushButton(i18n.t("batch_convert", "Batch"))
        btn_batch.clicked.connect(self.convert_batch)

        form = QGridLayout()
        form.addWidget(QLabel(i18n.t("category", "Category")), 0, 0)
        form.addWidget(self.category, 0, 1)
        form.addWidget(QLabel(i18n.t("value")), 1, 0)
        form.addWidget(self.value, 1, 1)
        form.addWidget(QLabel(i18n.t("from")), 2, 0)
        form.addWidget(self.from_u, 2, 1)
        form.addWidget(QLabel(i18n.t("to")), 3, 0)
        form.addWidget(self.to_u, 3, 1)
        form.addWidget(QLabel(i18n.t("targets", "Targets")), 4, 0)
        form.addWidget(self.batch_targets, 4, 1)

        main = QVBoxLayout(self)
        main.addLayout(form)
        main.addWidget(QLabel(i18n.t("quick", "Quick convert")))
        main.addWidget(self.quick_box)
        main.addWidget(btn)
        main.addWidget(QLabel(i18n.t("batch_table", "Batch table")))
        main.addWidget(self.batch_table)
        main.addWidget(btn_batch)
        main.addWidget(QLabel(i18n.t("result")))
        main.addWidget(self.result, 1)

        self._on_category_changed()

        # 订阅跨面板信号
        bus().send_to_unit.connect(self.receive_text)

    # ---------------- 类别 ----------------

    def _on_category_changed(self):
        cat_key = self.category.currentData()
        self.settings.set("unit_category", cat_key)
        cat = unit_mod.get_category(cat_key)
        if not cat:
            return
        units = cat["units"]

        for combo, default_idx in ((self.from_u, 0), (self.to_u, 1)):
            combo.blockSignals(True)
            combo.clear()
            for label, pint in units:
                combo.addItem(label, pint)
            if default_idx < combo.count():
                combo.setCurrentIndex(default_idx)
            combo.blockSignals(False)

        self._rebuild_quick_buttons(units)

        if not self.batch_targets.text().strip():
            labels = [u[0] for u in units[:6]]
            self.batch_targets.setText(",".join(labels))

    def _rebuild_quick_buttons(self, units):
        _clear_layout(self.quick_row)
        for label, pint in units[:8]:
            b = QPushButton(label)
            b.setFixedHeight(26)
            b.clicked.connect(lambda _, p=pint: self._quick_convert(p))
            self.quick_row.addWidget(b)
        self.quick_row.addStretch(1)

    def _quick_convert(self, to_pint):
        try:
            idx = self.to_u.findData(to_pint)
            if idx >= 0:
                self.to_u.setCurrentIndex(idx)
            self.convert()
        except Exception as e:
            log_exc(e, module="UnitPanel._quick_convert")

    # ---------------- 换算 ----------------

    def convert(self):
        try:
            v = float(self.value.text())
            fu = self.from_u.currentData()
            tu = self.to_u.currentData()
            r = engine.unit_convert(v, fu, tu)
            self.result.setPlainText(f"{v} {fu} = {r} {tu}")
            self.add_history(f"{v} {fu} -> {tu}", r, module="unit")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "unit"))

    def convert_batch(self):
        try:
            v = float(self.value.text())
            fu = self.from_u.currentData()
            targets = [t.strip()
                       for t in self.batch_targets.text().split(",")
                       if t.strip()]
            self.batch_table.setRowCount(0)
            for t in targets:
                idx = self.to_u.findData(t)
                if idx < 0:
                    continue
                tu = self.to_u.itemData(idx)
                try:
                    r = engine.unit_convert(v, fu, tu)
                except Exception:
                    r = "—"
                row = self.batch_table.rowCount()
                self.batch_table.insertRow(row)
                self.batch_table.setItem(
                    row, 0, QTableWidgetItem(self.to_u.itemText(idx)))
                self.batch_table.setItem(row, 1, QTableWidgetItem(str(r)))
            self.add_history(
                f"{v} {fu} -> {targets}",
                f"{self.batch_table.rowCount()} rows",
                module="unit-batch")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "unit"))

    # ---------------- 跨面板接收 ----------------

    def receive_text(self, text: str):
        """接收 "1.5 km" / "1.5 kilometer" 之类的文本。"""
        try:
            s = str(text).strip()
            # 忽略多行的（例如错误卡片），只处理单行"数字 + 单位"模式
            if "\n" in s:
                return
            m = re.match(
                r"^\s*(-?\d+\.?\d*(?:[eE][-+]?\d+)?)\s+([A-Za-z°μµ/²³·]+.*?)\s*$",
                s)
            if not m:
                return
            value_str = m.group(1)
            unit_str = m.group(2).strip()
            self.value.setText(value_str)
            # 优先精确匹配；找不到则跳过
            idx = self.from_u.findData(unit_str)
            if idx < 0:
                for i in range(self.from_u.count()):
                    if str(self.from_u.itemData(i)) == unit_str:
                        idx = i
                        break
            if idx >= 0:
                self.from_u.setCurrentIndex(idx)
            else:
                # 可编辑：直接填入
                self.from_u.setEditText(unit_str)
            self.convert()
        except Exception as e:
            log_exc(e, module="UnitPanel.receive_text")