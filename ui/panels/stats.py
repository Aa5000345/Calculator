"""统计面板。"""
from __future__ import annotations

import json
import re

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QComboBox, QTableWidget, QTableWidgetItem, QTabWidget,
    QWidget, QFileDialog, QMessageBox,
)

from core import engine
from core.errors import InputError
from core.logger import log_exc
from ._common import friendly_error
from .base import CalcPanel


class StatsPanel(CalcPanel):
    module_key = "stats"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        self.data = QPlainTextEdit("1 2 3 4 5 6 7 8 9 10")
        self.data.setFixedHeight(70)
        b_import = QPushButton(i18n.t("import_csv", "Import CSV"))
        b_import.clicked.connect(self._import_csv)

        self.desc_result = QPlainTextEdit()
        self.desc_result.setReadOnly(True)

        self.test_data1 = QPlainTextEdit("1 2 3 4 5"); self.test_data1.setFixedHeight(60)
        self.test_data2 = QPlainTextEdit("2 3 4 5 6"); self.test_data2.setFixedHeight(60)
        self.test_mu0 = QLineEdit("0")
        self.test_alpha = QLineEdit("0.05")
        self.test_kind = QComboBox()
        for k, label in [("ttest_1samp", "单样本 t 检验"),
                         ("ttest_ind", "独立样本 t 检验"),
                         ("ttest_paired", "配对 t 检验"),
                         ("normality", "正态性检验 (Shapiro)")]:
            self.test_kind.addItem(label, k)
        b_test = QPushButton(i18n.t("run_test", "Run test"))
        b_test.clicked.connect(self._run_test)
        self.test_result = QPlainTextEdit()
        self.test_result.setReadOnly(True)

        self.corr_input = QPlainTextEdit(
            "# 每行一个变量: 名称: 值1 值2 ...\n"
            "x: 1 2 3 4 5\ny: 2 4 6 8 10\nz: 1 1 2 3 5")
        self.corr_input.setFixedHeight(90)
        b_corr = QPushButton(i18n.t("corr_matrix", "Correlation matrix"))
        b_corr.clicked.connect(self._run_corr)
        self.corr_table = QTableWidget(0, 0)
        self.corr_table.setFixedHeight(160)

        self.reg_x = QPlainTextEdit("1 2 3 4 5 6 7 8 9 10"); self.reg_x.setFixedHeight(60)
        self.reg_y = QPlainTextEdit("2.1 4.0 6.2 8.1 10.0 12.1 14.0 16.2 18.0 20.1")
        self.reg_y.setFixedHeight(60)
        b_reg = QPushButton(i18n.t("run_regression", "Run regression"))
        b_reg.clicked.connect(self._run_regression)
        self.reg_result = QPlainTextEdit()
        self.reg_result.setReadOnly(True)

        self.figure = Figure(figsize=(6, 4))
        self.canvas = FigureCanvas(self.figure)
        self._fg = "#ffffff"; self._bg = "#1e1e1e"; self._panel = "#2d2d30"
        self.plot_kind = QComboBox()
        self.plot_kind.addItems(["hist", "box", "scatter"])
        b_plot = QPushButton(i18n.t("draw", "Plot"))
        b_plot.clicked.connect(self._plot)

        plot_row = QHBoxLayout()
        plot_row.addWidget(self.plot_kind)
        plot_row.addWidget(b_plot)
        plot_row.addStretch(1)

        tabs = QTabWidget()
        w1 = QWidget(); v1 = QVBoxLayout(w1)
        v1.addWidget(QLabel(i18n.t("data")))
        v1.addWidget(self.data)
        v1.addWidget(b_import)
        b_desc = QPushButton(i18n.t("calc"))
        b_desc.clicked.connect(self.calc)
        v1.addWidget(b_desc)
        v1.addWidget(self.desc_result, 1)
        tabs.addTab(w1, i18n.t("describe", "Describe"))

        w2 = QWidget(); v2 = QVBoxLayout(w2)
        v2.addWidget(QLabel("data1")); v2.addWidget(self.test_data1)
        v2.addWidget(QLabel("data2 (ind/paired)")); v2.addWidget(self.test_data2)
        row = QHBoxLayout()
        row.addWidget(QLabel("μ₀")); row.addWidget(self.test_mu0)
        row.addWidget(QLabel("α")); row.addWidget(self.test_alpha)
        row.addStretch(1)
        v2.addLayout(row); v2.addWidget(self.test_kind)
        v2.addWidget(b_test); v2.addWidget(self.test_result, 1)
        tabs.addTab(w2, i18n.t("test", "Test"))

        w3 = QWidget(); v3 = QVBoxLayout(w3)
        v3.addWidget(QLabel(i18n.t("corr_input", "每行 '变量名: 值1 值2 ...'")))
        v3.addWidget(self.corr_input)
        v3.addWidget(b_corr)
        v3.addWidget(self.corr_table)
        v3.addStretch(1)
        tabs.addTab(w3, i18n.t("correlation", "Correlation"))

        w4 = QWidget(); v4 = QVBoxLayout(w4)
        v4.addWidget(QLabel("X")); v4.addWidget(self.reg_x)
        v4.addWidget(QLabel("Y")); v4.addWidget(self.reg_y)
        v4.addWidget(b_reg); v4.addWidget(self.reg_result, 1)
        tabs.addTab(w4, i18n.t("regression", "Regression"))

        w5 = QWidget(); v5 = QVBoxLayout(w5)
        v5.addLayout(plot_row); v5.addWidget(self.canvas, 1)
        tabs.addTab(w5, i18n.t("chart", "Chart"))

        main = QVBoxLayout(self)
        main.addWidget(tabs)

    def calc(self):
        try:
            raw = self.data.toPlainText().strip()
            if not raw:
                self.desc_result.setPlainText(
                    self.i18n.t("err_stats_empty", "Stats: empty data"))
                return
            r = engine.stats_calc(raw)
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.desc_result.setPlainText(s)
            self.add_history(raw, s, module="stats")
        except Exception as e:
            self.desc_result.setPlainText(friendly_error(self.i18n, e, "stats"))

    def _run_test(self):
        k = self.test_kind.currentData()
        try:
            if k == "ttest_1samp":
                r = engine.stats_ttest_1samp(
                    self.test_data1.toPlainText(),
                    float(self.test_mu0.text()), float(self.test_alpha.text()))
            elif k == "ttest_ind":
                r = engine.stats_ttest_ind(
                    self.test_data1.toPlainText(), self.test_data2.toPlainText(),
                    float(self.test_alpha.text()))
            elif k == "ttest_paired":
                r = engine.stats_ttest_paired(
                    self.test_data1.toPlainText(), self.test_data2.toPlainText(),
                    float(self.test_alpha.text()))
            elif k == "normality":
                r = engine.stats_normality(self.test_data1.toPlainText())
            else:
                return
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.test_result.setPlainText(s)
            self.add_history(k, s, module="stats-test")
        except Exception as e:
            self.test_result.setPlainText(friendly_error(self.i18n, e, "stats"))

    def _parse_corr_input(self):
        cols = {}
        for line in self.corr_input.toPlainText().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            name, _, vals = line.partition(":")
            name = name.strip()
            nums = [float(x) for x in vals.split() if x]
            if name and nums:
                cols[name] = nums
        return cols

    def _run_corr(self):
        try:
            cols = self._parse_corr_input()
            if len(cols) < 2:
                raise InputError("至少需要两个变量", friendly_key="err_input")
            r = engine.stats_correlation(cols)
            names = r["names"]; mat = r["matrix"]
            self.corr_table.setRowCount(len(names))
            self.corr_table.setColumnCount(len(names))
            self.corr_table.setHorizontalHeaderLabels(names)
            self.corr_table.setVerticalHeaderLabels(names)
            for i in range(len(names)):
                for j in range(len(names)):
                    self.corr_table.setItem(
                        i, j, QTableWidgetItem(f"{mat[i][j]:.4f}"))
            self.add_history(",".join(names), json.dumps(mat),
                             module="stats-corr")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _run_regression(self):
        try:
            r = engine.stats_regression_full(
                self.reg_x.toPlainText(), self.reg_y.toPlainText())
            show = {k: v for k, v in r.items()
                    if k not in ("predictions", "residuals")}
            s = json.dumps(show, ensure_ascii=False, indent=2)
            self.reg_result.setPlainText(s)
            self.add_history("reg", s, module="stats-reg")
            self._plot_regression(r)
        except Exception as e:
            self.reg_result.setPlainText(friendly_error(self.i18n, e, "stats"))

    def _plot_regression(self, r):
        try:
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            ax.set_facecolor(self._panel)
            self.figure.patch.set_facecolor(self._bg)
            ax.tick_params(colors=self._fg)
            for sp in ax.spines.values():
                sp.set_color(self._fg)
            ys = [float(x) for x in self.reg_y.toPlainText().split()]
            xs = [float(x) for x in self.reg_x.toPlainText().split()]
            ax.scatter(xs, ys, c="#007acc", s=20, label="data")
            ax.plot(xs, r["predictions"], c="#ff7f0e", linewidth=1.4, label="fit")
            leg = ax.legend(facecolor=self._panel, edgecolor=self._fg, fontsize=8)
            for t in leg.get_texts():
                t.set_color(self._fg)
            ax.grid(True, color="#666", alpha=0.4, linewidth=0.6)
            try:
                self.figure.tight_layout()
            except Exception:
                pass
            self.canvas.draw()
        except Exception as e:
            log_exc(e, module="StatsPanel._plot_regression")

    def _plot(self):
        try:
            kind = self.plot_kind.currentText()
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            ax.set_facecolor(self._panel)
            self.figure.patch.set_facecolor(self._bg)
            ax.tick_params(colors=self._fg)
            for sp in ax.spines.values():
                sp.set_color(self._fg)
            data = [float(x) for x in self.data.toPlainText().split() if x]

            if kind == "hist":
                ax.hist(data, bins=15, color="#007acc", edgecolor="#ffffff")
            elif kind == "box":
                ax.boxplot(data)
            elif kind == "scatter":
                xs = [float(x) for x in self.reg_x.toPlainText().split() if x]
                ys = [float(x) for x in self.reg_y.toPlainText().split() if x]
                ax.scatter(xs, ys, c="#007acc", s=20)
            ax.grid(True, color="#666", alpha=0.4, linewidth=0.6)
            try:
                self.figure.tight_layout()
            except Exception:
                pass
            self.canvas.draw()
        except Exception as e:
            log_exc(e, module="StatsPanel._plot")

    def _import_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import CSV", "", "CSV (*.csv);;Text (*.txt)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                text = f.read()
            nums = re.findall(r"-?\d+\.?\d*(?:[eE][-+]?\d+)?", text)
            self.data.setPlainText(" ".join(nums))
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def set_theme_colors(self, fg, bg, panel):
        self._fg, self._bg, self._panel = fg, bg, panel
        try:
            self._plot()
        except Exception:
            pass