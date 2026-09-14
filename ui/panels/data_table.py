"""数据表编辑器面板：可编辑表头、公式列、导入/导出 CSV/JSON。"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QMenu, QInputDialog,
)

from core import data_table as dt_mod
from core.errors import InputError
from core.logger import log_exc
from ._common import ResultView
from .base import CalcPanel


class DataTablePanel(CalcPanel):
    module_key = "data_table"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)
        self._formulas = {}  # col_idx -> 公式文本

        # ---------------- 表格 ----------------
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["A", "B", "C", "D"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.horizontalHeader().customContextMenuRequested.connect(
            self._header_context_menu)

        for _ in range(5):
            self._append_row()

        # ---------------- 工具栏 ----------------
        b_add = QPushButton(i18n.t("add_row", "添加行"))
        b_del = QPushButton(i18n.t("delete_row", "删除行"))
        b_col = QPushButton(i18n.t("add_col", "添加列"))
        b_delcol = QPushButton(i18n.t("delete_col", "删除列"))
        b_import = QPushButton(i18n.t("import_csv", "导入 CSV"))
        b_export = QPushButton(i18n.t("export_csv", "导出 CSV"))
        b_json = QPushButton(i18n.t("export_json", "导出 JSON"))
        b_calc = QPushButton(i18n.t("recalc", "重算公式"))

        b_add.clicked.connect(self._append_row)
        b_del.clicked.connect(self._delete_rows)
        b_col.clicked.connect(self._append_col)
        b_delcol.clicked.connect(self._delete_cols)
        b_import.clicked.connect(self._import_csv)
        b_export.clicked.connect(self._export_csv)
        b_json.clicked.connect(self._export_json)
        b_calc.clicked.connect(self._recalc_all)

        row = QHBoxLayout()
        for b in (b_add, b_del, b_col, b_delcol, b_calc,
                  b_import, b_export, b_json):
            row.addWidget(b)
        row.addStretch(1)

        # ---------------- 公式行 ----------------
        form_row = QHBoxLayout()
        form_row.addWidget(QLabel(i18n.t("formula_col", "公式列")))
        self.formula_col = QComboBox()
        self.formula_col.currentIndexChanged.connect(
            self._on_formula_col_changed)
        form_row.addWidget(self.formula_col)
        form_row.addWidget(QLabel(i18n.t("formula", "公式")))
        self.formula_input = QLineEdit()
        self.formula_input.setPlaceholderText("=[A] + [B]")
        self.formula_input.editingFinished.connect(self._save_formula)
        form_row.addWidget(self.formula_input, 1)

        # ---------------- 结果 ----------------
        self.result = ResultView(i18n)

        main = QVBoxLayout(self)
        main.addLayout(row)
        main.addLayout(form_row)
        main.addWidget(self.table, 3)
        main.addWidget(self.result, 1)

        self._refresh_formula_combo()

    # ------------------------------------------------------------------
    # 列管理
    # ------------------------------------------------------------------

    def _col_letter(self, idx):
        s = ""
        idx += 1
        while idx:
            idx, r = divmod(idx - 1, 26)
            s = chr(ord("A") + r) + s
        return s

    def _col_name(self, idx):
        it = self.table.horizontalHeaderItem(idx)
        return it.text() if it else f"Col {idx + 1}"

    def _refresh_formula_combo(self):
        cur = self.formula_col.currentData()
        self.formula_col.blockSignals(True)
        self.formula_col.clear()
        self.formula_col.addItem("—", -1)
        for j in range(self.table.columnCount()):
            self.formula_col.addItem(self._col_name(j), j)
        self.formula_col.blockSignals(False)
        if isinstance(cur, int) and 0 <= cur < self.formula_col.count():
            self.formula_col.setCurrentIndex(self.formula_col.findData(cur))

    def _on_formula_col_changed(self):
        c = self.formula_col.currentData()
        if c is None or c < 0:
            self.formula_input.setText("")
            return
        self.formula_input.setText(self._formulas.get(c, ""))

    def _save_formula(self):
        c = self.formula_col.currentData()
        if c is None or c < 0:
            return
        text = self.formula_input.text().strip()
        if text:
            self._formulas[c] = text
        else:
            self._formulas.pop(c, None)
        self._recalc_all()

    def _append_col(self):
        n = self.table.columnCount()
        self.table.insertColumn(n)
        self.table.setHorizontalHeaderItem(
            n, QTableWidgetItem(self._col_letter(n)))
        self._refresh_formula_combo()

    def _delete_cols(self):
        cols = sorted({i.column() for i in self.table.selectedIndexes()},
                      reverse=True)
        if not cols and self.table.columnCount():
            cols = [self.table.columnCount() - 1]
        for c in cols:
            self.table.removeColumn(c)
            new_f = {}
            for k, v in self._formulas.items():
                if k < c:
                    new_f[k] = v
                elif k > c:
                    new_f[k - 1] = v
            self._formulas = new_f
        self._refresh_formula_combo()

    # ------------------------------------------------------------------
    # 行管理
    # ------------------------------------------------------------------

    def _append_row(self):
        r = self.table.rowCount()
        self.table.insertRow(r)
        for c in range(self.table.columnCount()):
            self.table.setItem(r, c, QTableWidgetItem(""))

    def _delete_rows(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()},
                      reverse=True)
        if not rows and self.table.rowCount():
            rows = [self.table.rowCount() - 1]
        for r in rows:
            self.table.removeRow(r)

    # ------------------------------------------------------------------
    # 公式求值
    # ------------------------------------------------------------------

    def _to_data_table(self):
        dt = dt_mod.DataTable()
        cols = [self._col_name(c) for c in range(self.table.columnCount())]
        dt.set_columns(cols)
        for r in range(self.table.rowCount()):
            row = []
            for c in range(self.table.columnCount()):
                it = self.table.item(r, c)
                row.append(it.text() if it else "")
            dt.add_row(row)
        for c, f in self._formulas.items():
            if 0 <= c < len(cols):
                dt.set_formula(cols[c], f)
        return dt

    def _recalc_all(self):
        try:
            dt = self._to_data_table()
            dt.recalc_all()
            for r in range(self.table.rowCount()):
                for c in range(self.table.columnCount()):
                    v = dt.get_cell(r, c)
                    self.table.setItem(r, c, QTableWidgetItem(v))
            self.result.show_result(
                f"✓ {self.i18n.t('recalc_done', '重算完成')}", "")
        except Exception as e:
            self.result.show_error(e)

    # ------------------------------------------------------------------
    # 表头右键菜单
    # ------------------------------------------------------------------

    def _header_context_menu(self, pos):
        idx = self.table.horizontalHeader().logicalIndexAt(pos)
        if idx < 0:
            return
        menu = QMenu(self)
        a_rename = menu.addAction(self.i18n.t("rename_col", "重命名"))
        a_setform = menu.addAction(self.i18n.t("set_formula", "设为公式列…"))
        a_clearform = menu.addAction(self.i18n.t("clear_formula", "清除公式"))
        chosen = menu.exec(self.table.horizontalHeader().mapToGlobal(pos))
        if chosen is a_rename:
            cur = self._col_name(idx)
            text, ok = QInputDialog.getText(
                self, self.i18n.t("rename_col", "重命名"),
                self.i18n.t("new_name", "新名称："), text=cur)
            if ok and text:
                self.table.setHorizontalHeaderItem(
                    idx, QTableWidgetItem(text))
                self._refresh_formula_combo()
        elif chosen is a_setform:
            target = self.formula_col.findData(idx)
            if target >= 0:
                self.formula_col.setCurrentIndex(target)
            self.formula_input.setFocus()
        elif chosen is a_clearform:
            self._formulas.pop(idx, None)
            self._recalc_all()

    # ------------------------------------------------------------------
    # 导入 / 导出
    # ------------------------------------------------------------------

    def _import_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import CSV", "", "CSV (*.csv);;Text (*.txt)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                text = f.read()
            dt = dt_mod.DataTable()
            dt.from_csv(text)
            self._load_from_data_table(dt)
            self.result.show_result(
                f"✓ {self.i18n.t('imported', '已导入')} "
                f"{len(dt.rows)}×{len(dt.columns)}", "")
        except Exception as e:
            self.result.show_error(e)

    def _load_from_data_table(self, dt: dt_mod.DataTable):
        self._formulas = {}
        self.table.setColumnCount(len(dt.columns))
        self.table.setHorizontalHeaderLabels(dt.columns)
        self.table.setRowCount(0)
        for row in dt.rows:
            self._append_row()
            r = self.table.rowCount() - 1
            for c, v in enumerate(row):
                if c < self.table.columnCount():
                    self.table.setItem(r, c, QTableWidgetItem(str(v)))
        self._refresh_formula_combo()

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "table.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            dt = self._to_data_table()
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                f.write(dt.to_csv())
            self.result.show_result(f"✓ {path}", "")
        except Exception as e:
            self.result.show_error(e)

    def _export_json(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export JSON", "table.json", "JSON (*.json)")
        if not path:
            return
        try:
            dt = self._to_data_table()
            with open(path, "w", encoding="utf-8") as f:
                f.write(dt.to_json())
            self.result.show_result(f"✓ {path}", "")
        except Exception as e:
            self.result.show_error(e)