"""脚本 / 批量计算面板：多行表达式顺序执行。

- 每行一个表达式；# 开头或行尾 " #" 为注释
- 复用 core.symbols 变量，支持 x = 5 / f(x) = x^2 等
- 结果表格可导出 CSV
"""
from __future__ import annotations

import csv

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QMessageBox, QSplitter, QWidget,
)

from core import engine
from core.logger import log_exc
from ._common import friendly_error
from .base import CalcPanel


class ScriptPanel(CalcPanel):
    module_key = "script"

    SAMPLE = (
        "# 每行一个表达式；# 开头或行尾 ' #' 为注释\n"
        "a = 3\n"
        "b = 4\n"
        "sqrt(a^2 + b^2)\n"
        "\n"
        "100 的 15%  # 支持百分比语法吗？ → 脚本中暂不支持，用 100 * 15 / 100\n"
        "100 * 15 / 100\n"
        "sin(pi / 6)\n"
        "factorial(5)\n"
    )

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText(self.SAMPLE)
        self.editor.setPlainText(self.SAMPLE)

        self.run_btn = QPushButton(i18n.t("script_run", "运行全部"))
        self.run_btn.clicked.connect(self.run_script)

        self.clear_btn = QPushButton(i18n.t("clear", "清空"))
        self.clear_btn.clicked.connect(self._clear)

        self.export_btn = QPushButton(
            i18n.t("script_export_csv", "导出结果 CSV"))
        self.export_btn.clicked.connect(self._export_csv)

        self.result_table = QTableWidget(0, 3)
        self.result_table.setHorizontalHeaderLabels([
            i18n.t("script_line", "行"),
            i18n.t("script_expr", "表达式"),
            i18n.t("result", "结果"),
        ])
        hdr = self.result_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        self.result_table.setSelectionBehavior(QTableWidget.SelectRows)

        self.status = QLabel("")
        self.status.setStyleSheet("color: #888;")

        row = QHBoxLayout()
        for b in (self.run_btn, self.clear_btn, self.export_btn):
            row.addWidget(b)
        row.addStretch(1)

        top = QWidget()
        tv = QVBoxLayout(top)
        tv.setContentsMargins(0, 0, 0, 0)
        tv.addWidget(QLabel(i18n.t("script_source", "脚本源码")))
        tv.addWidget(self.editor, 1)

        bottom = QWidget()
        bv = QVBoxLayout(bottom)
        bv.setContentsMargins(0, 0, 0, 0)
        bv.addWidget(QLabel(i18n.t("script_results", "结果")))
        bv.addWidget(self.result_table, 1)

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(top)
        splitter.addWidget(bottom)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        main = QVBoxLayout(self)
        main.addWidget(splitter, 1)
        main.addLayout(row)
        main.addWidget(self.status)

    # ------------------------------------------------------------------

    def _angle_mode(self) -> str:
        try:
            return self.settings.get("angle_mode", "RAD") or "RAD"
        except Exception:
            return "RAD"

    def run_script(self):
        self.result_table.setRowCount(0)
        text = self.editor.toPlainText()
        angle = self._angle_mode()

        n_ok = 0
        n_err = 0
        for lineno, line in enumerate(text.splitlines(), 1):
            raw = line.rstrip()
            s = raw.strip()
            if not s or s.startswith("#"):
                continue
            # 行尾注释（用 " #" 分隔，避免与 # 用于其它语法冲突）
            if " #" in s:
                s = s.split(" #", 1)[0].strip()
                if not s:
                    continue
            try:
                r = engine.sci_eval(s, angle)
                try:
                    out = engine.format_result(r, "text")
                except Exception:
                    out = str(r)
                self._add_row(lineno, s, out)
                n_ok += 1
            except Exception as e:
                msg = friendly_error(self.i18n, e, "script")
                self._add_row(lineno, s, f"⚠ {msg}")
                n_err += 1

        tmpl = self.i18n.t(
            "script_done", "完成：成功 {ok}，失败 {err}")
        try:
            self.status.setText(tmpl.format(ok=n_ok, err=n_err))
        except Exception:
            self.status.setText(f"完成：成功 {n_ok}，失败 {n_err}")

        try:
            self.add_history(
                f"script:{n_ok}lines",
                f"ok={n_ok} err={n_err}", module="script")
        except Exception:
            pass

    def _add_row(self, lineno, expr, result):
        r = self.result_table.rowCount()
        self.result_table.insertRow(r)
        self.result_table.setItem(r, 0, QTableWidgetItem(str(lineno)))
        self.result_table.setItem(r, 1, QTableWidgetItem(expr))
        self.result_table.setItem(r, 2, QTableWidgetItem(result))

    def _clear(self):
        self.result_table.setRowCount(0)
        self.status.setText("")

    def _export_csv(self):
        if self.result_table.rowCount() == 0:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "script_results.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["line", "expr", "result"])
                for r in range(self.result_table.rowCount()):
                    row = []
                    for c in range(3):
                        it = self.result_table.item(r, c)
                        row.append(it.text() if it else "")
                    w.writerow(row)
            self.status.setText(path)
        except Exception as e:
            log_exc(e, module="ScriptPanel._export_csv")
            QMessageBox.warning(self, "Error", str(e))