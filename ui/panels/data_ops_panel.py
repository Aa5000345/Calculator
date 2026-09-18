"""数据运算面板：列聚合、排序、筛选、分析。

和「数据表」面板配套：
- 数据表负责编辑
- 本面板负责运算

也可以独立使用：直接粘贴数据。
"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QComboBox, QTabWidget, QWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QFileDialog,
)

from core import data_ops as dop
from core.errors import InputError
from core.logger import log_exc
from ui.signals import bus
from ._common import ResultView
from .base import CalcPanel


def _parse_table(text: str) -> tuple:
    """把文本解析为 (rows, headers)。

    支持：
    - 第一行为表头（Tab / 逗号 / 空格分隔）
    - 无表头时自动生成 A, B, C ...
    """
    lines = [ln for ln in str(text).splitlines() if ln.strip()]
    if not lines:
        return [], []

    def _split(ln):
        if "\t" in ln:
            return [c.strip() for c in ln.split("\t")]
        if "," in ln:
            return [c.strip() for c in ln.split(",")]
        if ";" in ln:
            return [c.strip() for c in ln.split(";")]
        return ln.split()

    first = _split(lines[0])
    rest = [_split(ln) for ln in lines[1:]]

    def _looks_header(cells):
        non_numeric = 0
        for c in cells:
            try:
                float(c)
            except (TypeError, ValueError):
                non_numeric += 1
        return non_numeric >= len(cells) / 2

    if rest and _looks_header(first):
        headers = first
        rows = rest
    else:
        n = len(first)
        headers = [
            chr(ord("A") + i) if i < 26 else f"col{i}"
            for i in range(n)]
        rows = [first] + rest

    n = len(headers)
    rows = [(r + [""] * n)[:n] for r in rows]
    return rows, headers


class DataOpsPanel(CalcPanel):
    module_key = "data_ops"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        self._rows: list = []
        self._headers: list = []
        self._orig_rows = None

        # ---------------- 数据输入 ----------------
        self.data_input = QPlainTextEdit()
        self.primary_input = self.data_input
        self.data_input.setPlaceholderText(
            "第一行为表头（可选），每行一条记录\n"
            "A,B,C\n1,2,3\n4,5,6")
        self.data_input.setFixedHeight(120)

        b_parse = QPushButton(
            self.i18n.t("data_ops_parse", "解析数据"))
        b_parse.clicked.connect(self._parse)
        b_load_csv = QPushButton(
            self.i18n.t("data_ops_load_csv", "从 CSV 导入"))
        b_load_csv.clicked.connect(self._load_csv)
        b_from_table = QPushButton(
            self.i18n.t("data_ops_from_table",
                        "从数据表面板读取"))
        b_from_table.clicked.connect(self._from_data_table)

        # ---------------- 预览表 ----------------
        self.preview = QTableWidget(0, 0)
        self.preview.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self.preview.setEditTriggers(
            QAbstractItemView.NoEditTriggers)
        self.preview.setMaximumHeight(180)

        # ---------------- Tab ----------------
        self.tabs = QTabWidget()
        self.tabs.addTab(
            self._build_aggregate_tab(),
            self.i18n.t("data_ops_aggregate", "聚合"))
        self.tabs.addTab(
            self._build_sort_tab(),
            self.i18n.t("data_ops_sort", "排序"))
        self.tabs.addTab(
            self._build_filter_tab(),
            self.i18n.t("data_ops_filter", "筛选"))
        self.tabs.addTab(
            self._build_analyze_tab(),
            self.i18n.t("data_ops_analyze", "分析"))

        self.result = ResultView(i18n)

        # ---------------- 主布局 ----------------
        top = QHBoxLayout()
        top.addWidget(b_parse)
        top.addWidget(b_load_csv)
        top.addWidget(b_from_table)
        top.addStretch(1)
        top.addWidget(self.make_kb_button())

        main = QVBoxLayout(self)
        main.addWidget(QLabel(
            self.i18n.t("data_ops_input", "数据输入")))
        main.addWidget(self.data_input)
        main.addLayout(top)
        main.addWidget(QLabel(
            self.i18n.t("data_ops_preview", "预览")))
        main.addWidget(self.preview)
        main.addWidget(self.tabs, 1)
        main.addWidget(QLabel(
            self.i18n.t("result", "结果")))
        main.addWidget(self.result, 1)

        self._refresh_columns()

    # ==================================================================
    # 数据加载
    # ==================================================================

    def _parse(self):
        text = self.data_input.toPlainText()
        rows, headers = _parse_table(text)
        if not rows:
            self.result.show_error(
                InputError("没有可解析的数据"))
            return
        self._rows = rows
        self._headers = headers
        self._orig_rows = None
        self._render_preview()
        self._refresh_columns()
        self.result.show_result(
            f"✓ 解析完成：{len(rows)} 行 × {len(headers)} 列",
            "")

    def _load_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "导入 CSV", "",
            "CSV (*.csv);;Text (*.txt);;All Files (*)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                self.data_input.setPlainText(f.read())
            self._parse()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _from_data_table(self):
        """从「数据表」面板读数据。"""
        try:
            mw = self.window()
            panel = getattr(mw, "_panels", {}).get("data_table")
            if panel is None:
                QMessageBox.information(
                    self, "提示", "找不到数据表面板")
                return
            table = getattr(panel, "table", None)
            if table is None:
                return

            headers = []
            for c in range(table.columnCount()):
                it = table.horizontalHeaderItem(c)
                headers.append(it.text() if it else f"Col{c + 1}")

            lines = [",".join(headers)]
            for r in range(table.rowCount()):
                row = []
                for c in range(table.columnCount()):
                    it = table.item(r, c)
                    row.append(it.text() if it else "")
                lines.append(",".join(row))

            self.data_input.setPlainText("\n".join(lines))
            self._parse()
        except Exception as e:
            log_exc(e, module="DataOpsPanel._from_data_table")
            QMessageBox.warning(self, "Error", str(e))

    def _render_preview(self):
        self.preview.setRowCount(0)
        self.preview.setColumnCount(len(self._headers))
        self.preview.setHorizontalHeaderLabels(self._headers)
        for r, row in enumerate(self._rows):
            self.preview.insertRow(r)
            for c, v in enumerate(row):
                self.preview.setItem(
                    r, c, QTableWidgetItem(str(v)))

    # ==================================================================
    # 聚合 Tab
    # ==================================================================

    def _build_aggregate_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.agg_col = QComboBox()
        self.agg_op = QComboBox()
        for k, label in dop.AGG_OPS.items():
            self.agg_op.addItem(f"{label} ({k})", k)

        b_run = QPushButton(self.i18n.t("calc", "计算"))
        b_run.clicked.connect(self._do_aggregate)
        b_send = QPushButton(
            self.i18n.t("data_ops_send_stats",
                        "发送到统计面板"))
        b_send.clicked.connect(self._send_to_stats)

        row = QHBoxLayout()
        row.addWidget(QLabel(
            self.i18n.t("data_ops_col", "列")))
        row.addWidget(self.agg_col, 1)
        row.addWidget(QLabel(
            self.i18n.t("data_ops_op", "操作")))
        row.addWidget(self.agg_op, 1)
        row.addWidget(b_run)
        row.addWidget(b_send)
        v.addLayout(row)
        v.addStretch(1)
        return w

    def _do_aggregate(self):
        try:
            name = self.agg_col.currentData()
            if name is None:
                raise InputError("请先解析数据")
            op = self.agg_op.currentData()
            vals = dop.column_values(
                self._rows, self._headers, name)
            r = dop.aggregate(vals, op)
            label = dop.AGG_OPS.get(op, op)
            self.result.show_result(
                f"{label}([{name}]) = {r:g}", "")
            self.add_history(
                f"{op}([{name}])", f"{r:g}",
                module="data-ops")
        except Exception as e:
            self.result.show_error(e, retry_cb=self._do_aggregate)

    def _send_to_stats(self):
        try:
            name = self.agg_col.currentData()
            if name is None:
                return
            vals = dop.column_values(
                self._rows, self._headers, name)
            text = dop.to_stats_text(vals)
            bus().send_to_sci.emit(text)
            self.result.show_result(
                f"✓ 已发送 {name} 列到统计面板", "")
        except Exception as e:
            self.result.show_error(e)

    # ==================================================================
    # 排序 Tab
    # ==================================================================

    def _build_sort_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.sort_col = QComboBox()
        self.sort_desc = QComboBox()
        self.sort_desc.addItem(
            self.i18n.t("data_ops_ascending", "升序"), False)
        self.sort_desc.addItem(
            self.i18n.t("data_ops_descending", "降序"), True)

        b_run = QPushButton(
            self.i18n.t("data_ops_sort", "排序"))
        b_run.clicked.connect(self._do_sort)

        row = QHBoxLayout()
        row.addWidget(QLabel(
            self.i18n.t("data_ops_col", "列")))
        row.addWidget(self.sort_col, 1)
        row.addWidget(self.sort_desc)
        row.addWidget(b_run)
        v.addLayout(row)
        v.addStretch(1)
        return w

    def _do_sort(self):
        try:
            if not self._rows:
                raise InputError("请先解析数据")
            col = self.sort_col.currentData()
            desc = self.sort_desc.currentData()
            self._rows = dop.sort_rows(
                self._rows, self._headers, col, desc)
            self._render_preview()
            self.result.show_result(
                f"✓ 已按 [{col}] "
                f"{'降' if desc else '升'}序排列", "")
        except Exception as e:
            self.result.show_error(e)

    # ==================================================================
    # 筛选 Tab
    # ==================================================================

    def _build_filter_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.filter_col = QComboBox()
        self.filter_op = QComboBox()
        for k in dop.FILTER_OPS:
            self.filter_op.addItem(k, k)
        self.filter_value = QLineEdit("")

        b_run = QPushButton(
            self.i18n.t("data_ops_filter", "筛选"))
        b_run.clicked.connect(self._do_filter)
        b_reset = QPushButton(self.i18n.t("reset", "重置"))
        b_reset.clicked.connect(self._reset_filter)

        row = QHBoxLayout()
        row.addWidget(QLabel(
            self.i18n.t("data_ops_col", "列")))
        row.addWidget(self.filter_col, 1)
        row.addWidget(self.filter_op)
        row.addWidget(self.filter_value, 2)
        row.addWidget(b_run)
        row.addWidget(b_reset)
        v.addLayout(row)
        v.addStretch(1)
        return w

    def _do_filter(self):
        try:
            if not self._rows:
                raise InputError("请先解析数据")
            if self._orig_rows is None:
                self._orig_rows = list(self._rows)
            col = self.filter_col.currentData()
            op = self.filter_op.currentData()
            val = self.filter_value.text()
            self._rows = dop.filter_rows(
                self._orig_rows, self._headers, col, op, val)
            self._render_preview()
            self.result.show_result(
                f"✓ 筛选后 {len(self._rows)} 行", "")
        except Exception as e:
            self.result.show_error(e)

    def _reset_filter(self):
        if self._orig_rows is not None:
            self._rows = list(self._orig_rows)
            self._render_preview()
            self.result.show_result("✓ 已重置", "")

    # ==================================================================
    # 分析 Tab
    # ==================================================================

    def _build_analyze_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        b_all = QPushButton(
            self.i18n.t("data_ops_analyze_all", "分析所有列"))
        b_all.clicked.connect(self._do_analyze)
        b_export = QPushButton(
            self.i18n.t("data_ops_export_json", "导出 JSON"))
        b_export.clicked.connect(self._export_json)
        row = QHBoxLayout()
        row.addWidget(b_all)
        row.addWidget(b_export)
        row.addStretch(1)
        v.addLayout(row)
        v.addStretch(1)
        return w

    def _do_analyze(self):
        try:
            if not self._rows:
                raise InputError("请先解析数据")
            r = dop.analyze_rows(self._rows, self._headers)
            text = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.show_result(text, "")
            self.add_history(
                "analyze", text[:500], module="data-ops")
        except Exception as e:
            self.result.show_error(e)

    def _export_json(self):
        if not self._rows:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出分析 JSON", "analysis.json",
            "JSON (*.json)")
        if not path:
            return
        try:
            r = dop.analyze_rows(self._rows, self._headers)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(r, f, ensure_ascii=False, indent=2)
            self.result.show_result(f"✓ {path}", "")
        except Exception as e:
            self.result.show_error(e)

    # ==================================================================
    # 列下拉刷新
    # ==================================================================

    def _refresh_columns(self):
        for cb in (self.agg_col, self.sort_col,
                   self.filter_col):
            cb.blockSignals(True)
            cb.clear()
            for h in self._headers:
                cb.addItem(h, h)
            cb.blockSignals(False)


__all__ = ["DataOpsPanel"]