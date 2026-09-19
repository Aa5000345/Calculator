"""统计 / 概率 / 随机 / 数据表 / 数据运算面板。

合并自：ui/panels/stats.py + ui/panels/probability.py
        + ui/panels/random_panel.py + ui/panels/data_table.py
        + ui/panels/data_ops_panel.py

对外接口（类名保持不变，老 registry.py 无需改动）：
    StatsPanel
    ProbabilityPanel
    RandomPanel
    DataTablePanel
    DataOpsPanel

依赖（合并后）：
    core.base          —— InputError / log_exc
    core.engine        —— stats_calc（StatsPanel 内部直接使用）
    core.probability   —— 分布 / 检验 / 回归 / 随机 / 拟合
    core.data          —— DataTable / AGG_OPS / FILTER_OPS /
                          aggregate / sort_rows / filter_rows /
                          analyze_rows / column_values /
                          to_stats_text
    ui.shell           —— bus
    ui.panels.base     —— CalcPanel
    ui.panels._common  —— ResultView / InlinePreviewBar /
                          friendly_error

修复记录（本轮）：
- StatsPanel：`from core import probability as prob` → 别名统一为
  `prob_mod`，避免与其他面板内的 `prob` 撞名。
- ProbabilityPanel：`from ui.widgets.bayesian_tab import BayesianTab`
  **保持原样**（该 widget 将在第 12 轮合并；本轮延迟导入已由
  try/except 兜住）。
- RandomPanel：`from core import random_ext as rand_mod` → 统一走
  `prob_mod`（random_ext 已合并进 core.probability）。
- DataTablePanel / DataOpsPanel：`dt_mod` / `dop` → 统一 `data_mod`。
"""
from __future__ import annotations

import json
import re
import time

import numpy as np
from matplotlib.backends.backend_qtagg import (
    FigureCanvasQTAgg as FigureCanvas,
)
from matplotlib.figure import Figure

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFileDialog,
    QFormLayout, QHeaderView, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QMenu, QMessageBox, QPlainTextEdit,
    QPushButton, QSpinBox, QStackedWidget, QTabWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    QDoubleSpinBox,QProgressBar
)

from core import data as data_mod
from core import probability as prob_mod
from core.base import InputError, log_exc
from ui.shell import bus
from ._common import (
    ResultView,
    InlinePreviewBar,
    friendly_error,
)
from .base import CalcPanel


__all__ = [
    "StatsPanel",
    "ProbabilityPanel",
    "RandomPanel",
    "DataTablePanel",
    "DataOpsPanel",
]


def _parse_floats(text: str) -> list:
    """把一段文本（空格/逗号/分号分隔）解析为 float 列表。"""
    return [float(x)
            for x in re.split(r"[\s,;]+", str(text)) if x]


# ===========================================================================
# 统计
# ===========================================================================

class StatsPanel(CalcPanel):
    """统计面板：描述统计 / 假设检验 / 相关 / 回归 / 绘图。"""

    module_key = "stats"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        # ---------------- 描述统计 ----------------
        self.data = QPlainTextEdit(
            "1 2 3 4 5 6 7 8 9 10")
        self.data.setFixedHeight(70)
        self.primary_input = self.data
        b_import = QPushButton(
            i18n.t("import_csv", "Import CSV"))
        b_import.clicked.connect(self._import_csv)

        self.desc_result = QPlainTextEdit()
        self.desc_result.setReadOnly(True)

        # ---------------- 假设检验 ----------------
        self.test_data1 = QPlainTextEdit("1 2 3 4 5")
        self.test_data1.setFixedHeight(60)
        self.test_data2 = QPlainTextEdit("2 3 4 5 6")
        self.test_data2.setFixedHeight(60)
        self.test_mu0 = QLineEdit("0")
        self.test_alpha = QLineEdit("0.05")
        self.test_kind = QComboBox()
        for k, label in [
                ("ttest_1samp", "单样本 t 检验"),
                ("ttest_ind", "独立样本 t 检验"),
                ("ttest_paired", "配对 t 检验"),
                ("normality", "正态性检验 (Shapiro)"),
                ("anova", "单因素方差分析")]:
            self.test_kind.addItem(label, k)
        b_test = QPushButton(i18n.t("run_test", "Run test"))
        b_test.clicked.connect(self._run_test)
        self.test_result = QPlainTextEdit()
        self.test_result.setReadOnly(True)

        # ---------------- 相关 ----------------
        self.corr_input = QPlainTextEdit(
            "# 每行一个变量: 名称: 值1 值2 ...\n"
            "x: 1 2 3 4 5\ny: 2 4 6 8 10\nz: 1 1 2 3 5")
        self.corr_input.setFixedHeight(90)
        b_corr = QPushButton(
            i18n.t("corr_matrix", "Correlation matrix"))
        b_corr.clicked.connect(self._run_corr)
        self.corr_table = QTableWidget(0, 0)
        self.corr_table.setFixedHeight(160)

        # ---------------- 回归 ----------------
        self.reg_x = QPlainTextEdit(
            "1 2 3 4 5 6 7 8 9 10")
        self.reg_x.setFixedHeight(60)
        self.reg_y = QPlainTextEdit(
            "2.1 4.0 6.2 8.1 10.0 12.1 14.0 16.2 18.0 20.1")
        self.reg_y.setFixedHeight(60)
        b_reg = QPushButton(
            i18n.t("run_regression", "Run regression"))
        b_reg.clicked.connect(self._run_regression)
        self.reg_result = QPlainTextEdit()
        self.reg_result.setReadOnly(True)

        # ---------------- 绘图 ----------------
        self.figure = Figure(figsize=(6, 4))
        self.canvas = FigureCanvas(self.figure)
        self._fg = "#ffffff"
        self._bg = "#1e1e1e"
        self._panel = "#2d2d30"
        self.plot_kind = QComboBox()
        self.plot_kind.addItems(["hist", "box", "scatter"])
        b_plot = QPushButton(i18n.t("draw", "Plot"))
        b_plot.clicked.connect(self._plot)

        plot_row = QHBoxLayout()
        plot_row.addWidget(self.plot_kind)
        plot_row.addWidget(b_plot)
        plot_row.addStretch(1)

        # ---------------- 布局 ----------------
        tabs = QTabWidget()

        w1 = QWidget()
        v1 = QVBoxLayout(w1)
        v1.addWidget(QLabel(i18n.t("data")))
        v1.addWidget(self.data)
        v1.addWidget(b_import)
        b_desc = QPushButton(i18n.t("calc"))
        b_desc.clicked.connect(self.calc)
        b_send_ops = QPushButton(
            i18n.t("send_to_data_ops", "发送到数据运算"))
        b_send_ops.clicked.connect(self._send_to_data_ops)
        row1 = QHBoxLayout()
        row1.addWidget(b_desc)
        row1.addWidget(b_send_ops)
        row1.addStretch(1)
        v1.addLayout(row1)
        v1.addWidget(self.desc_result, 1)
        tabs.addTab(w1, i18n.t("describe", "Describe"))

        w2 = QWidget()
        v2 = QVBoxLayout(w2)
        v2.addWidget(QLabel("data1"))
        v2.addWidget(self.test_data1)
        v2.addWidget(QLabel("data2 (ind/paired/anova-2)"))
        v2.addWidget(self.test_data2)
        row = QHBoxLayout()
        row.addWidget(QLabel("μ₀"))
        row.addWidget(self.test_mu0)
        row.addWidget(QLabel("α"))
        row.addWidget(self.test_alpha)
        row.addStretch(1)
        v2.addLayout(row)
        v2.addWidget(self.test_kind)
        v2.addWidget(b_test)
        v2.addWidget(self.test_result, 1)
        tabs.addTab(w2, i18n.t("test", "Test"))

        w3 = QWidget()
        v3 = QVBoxLayout(w3)
        v3.addWidget(QLabel(i18n.t(
            "corr_input", "每行 '变量名: 值1 值2 ...'")))
        v3.addWidget(self.corr_input)
        v3.addWidget(b_corr)
        v3.addWidget(self.corr_table)
        v3.addStretch(1)
        tabs.addTab(w3, i18n.t("correlation", "Correlation"))

        w4 = QWidget()
        v4 = QVBoxLayout(w4)
        v4.addWidget(QLabel("X"))
        v4.addWidget(self.reg_x)
        v4.addWidget(QLabel("Y"))
        v4.addWidget(self.reg_y)
        v4.addWidget(b_reg)
        v4.addWidget(self.reg_result, 1)
        tabs.addTab(w4, i18n.t("regression", "Regression"))

        w5 = QWidget()
        v5 = QVBoxLayout(w5)
        v5.addLayout(plot_row)
        v5.addWidget(self.canvas, 1)
        tabs.addTab(w5, i18n.t("chart", "Chart"))

        main = QVBoxLayout(self)
        main.addWidget(tabs)

    # ==================================================================
    # 描述统计
    # ==================================================================

    def calc(self):
        try:
            raw = self.data.toPlainText().strip()
            if not raw:
                self.desc_result.setPlainText(
                    self.i18n.t("err_stats_empty",
                                "Stats: empty data"))
                return
            from core import engine
            r = engine.stats_calc(raw)
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.desc_result.setPlainText(s)
            self.add_history(raw, s, module="stats")
        except Exception as e:
            self.desc_result.setPlainText(
                friendly_error(self.i18n, e, "stats"))

    def _send_to_data_ops(self):
        """把当前数据发送到数据运算面板。"""
        try:
            text = self.data.toPlainText().strip()
            if not text:
                return
            nums = _parse_floats(text)
            lines = ["value"]
            for n in nums:
                lines.append(f"{n:g}")
            csv_text = "\n".join(lines)
            bus().send_to_data_ops.emit(csv_text)
            try:
                from ui.shell import toast
                toast(self.window(),
                      self.i18n.t("sent_to_data_ops",
                                  "已发送到数据运算面板"),
                      level="success")
            except Exception:
                pass
        except Exception as e:
            log_exc(e, module="StatsPanel._send_to_data_ops")

    # ==================================================================
    # 假设检验
    # ==================================================================

    def _run_test(self):
        k = self.test_kind.currentData()
        alpha = float(self.test_alpha.text() or "0.05")
        try:
            if k == "ttest_1samp":
                data = _parse_floats(
                    self.test_data1.toPlainText())
                mu0 = float(self.test_mu0.text() or "0")
                r = prob_mod.ttest_1samp(data, mu0, alpha)
            elif k == "ttest_ind":
                a = _parse_floats(
                    self.test_data1.toPlainText())
                b = _parse_floats(
                    self.test_data2.toPlainText())
                r = prob_mod.ttest_ind(a, b, alpha)
            elif k == "ttest_paired":
                from scipy import stats as st
                a = _parse_floats(
                    self.test_data1.toPlainText())
                b = _parse_floats(
                    self.test_data2.toPlainText())
                t, p = st.ttest_rel(a, b)
                r = {"t": float(t), "p": float(p),
                     "reject_H0": bool(p < alpha)}
            elif k == "normality":
                from scipy import stats as st
                data = _parse_floats(
                    self.test_data1.toPlainText())
                if len(data) < 3:
                    raise InputError(
                        "Shapiro 检验至少需要 3 个数据点",
                        friendly_key="err_input")
                w, p = st.shapiro(data)
                r = {"statistic": float(w), "p": float(p),
                     "normal_95": bool(p >= 0.05)}
            elif k == "anova":
                a = _parse_floats(
                    self.test_data1.toPlainText())
                b = _parse_floats(
                    self.test_data2.toPlainText())
                r = prob_mod.anova_oneway(a, b, alpha=alpha)
            else:
                return
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.test_result.setPlainText(s)
            self.add_history(k, s, module="stats-test")
        except Exception as e:
            self.test_result.setPlainText(
                friendly_error(self.i18n, e, "stats"))

    # ==================================================================
    # 相关
    # ==================================================================

    def _parse_corr_input(self):
        cols = {}
        for line in self.corr_input.toPlainText().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            name, _, vals = line.partition(":")
            name = name.strip()
            nums = _parse_floats(vals)
            if name and nums:
                cols[name] = nums
        return cols

    def _run_corr(self):
        try:
            cols = self._parse_corr_input()
            if len(cols) < 2:
                raise InputError("至少需要两个变量",
                                 friendly_key="err_input")
            names = list(cols.keys())
            arr = np.array([cols[n] for n in names], dtype=float)
            if len({len(v) for v in cols.values()}) != 1:
                raise InputError("各变量长度需一致",
                                 friendly_key="err_input")
            mat = np.corrcoef(arr)
            self.corr_table.setRowCount(len(names))
            self.corr_table.setColumnCount(len(names))
            self.corr_table.setHorizontalHeaderLabels(names)
            self.corr_table.setVerticalHeaderLabels(names)
            for i in range(len(names)):
                for j in range(len(names)):
                    self.corr_table.setItem(
                        i, j,
                        QTableWidgetItem(f"{mat[i][j]:.4f}"))
            self.add_history(
                ",".join(names), json.dumps(mat.tolist()),
                module="stats-corr")
        except Exception as e:
            QMessageBox.warning(
                self, "Error",
                friendly_error(self.i18n, e, "stats"))

    # ==================================================================
    # 回归
    # ==================================================================

    def _run_regression(self):
        try:
            xs = _parse_floats(self.reg_x.toPlainText())
            ys = _parse_floats(self.reg_y.toPlainText())
            r = prob_mod.linear_regression(xs, ys)
            slope = r["slope"]
            inter = r["intercept"]
            r["predictions"] = [slope * x + inter for x in xs]
            r["residuals"] = [y - p for y, p in
                              zip(ys, r["predictions"])]
            show = {k: v for k, v in r.items()
                    if k not in ("predictions", "residuals")}
            s = json.dumps(show, ensure_ascii=False, indent=2)
            self.reg_result.setPlainText(s)
            self.add_history("reg", s, module="stats-reg")
            self._plot_regression(r)
        except Exception as e:
            self.reg_result.setPlainText(
                friendly_error(self.i18n, e, "stats"))

    def _plot_regression(self, r):
        try:
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            ax.set_facecolor(self._panel)
            self.figure.patch.set_facecolor(self._bg)
            ax.tick_params(colors=self._fg)
            for sp in ax.spines.values():
                sp.set_color(self._fg)
            ys = _parse_floats(self.reg_y.toPlainText())
            xs = _parse_floats(self.reg_x.toPlainText())
            ax.scatter(xs, ys, c="#007acc", s=20,
                       label="data")
            ax.plot(xs, r["predictions"], c="#ff7f0e",
                    linewidth=1.4, label="fit")
            leg = ax.legend(facecolor=self._panel,
                            edgecolor=self._fg, fontsize=8)
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

    # ==================================================================
    # 绘图
    # ==================================================================

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
            data = _parse_floats(self.data.toPlainText())

            if kind == "hist":
                ax.hist(data, bins=15, color="#007acc",
                        edgecolor="#ffffff")
            elif kind == "box":
                ax.boxplot(data)
            elif kind == "scatter":
                xs = _parse_floats(self.reg_x.toPlainText())
                ys = _parse_floats(self.reg_y.toPlainText())
                ax.scatter(xs, ys, c="#007acc", s=20)
            ax.grid(True, color="#666", alpha=0.4, linewidth=0.6)
            try:
                self.figure.tight_layout()
            except Exception:
                pass
            self.canvas.draw()
        except Exception as e:
            log_exc(e, module="StatsPanel._plot")

    # ==================================================================
    # 导入
    # ==================================================================

    def _import_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import CSV", "",
            "CSV (*.csv);;Text (*.txt)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                text = f.read()
            nums = re.findall(
                r"-?\d+\.?\d*(?:[eE][-+]?\d+)?", text)
            self.data.setPlainText(" ".join(nums))
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def set_theme_colors(self, fg, bg, panel):
        self._fg, self._bg, self._panel = fg, bg, panel
        try:
            self._plot()
        except Exception:
            pass


# ===========================================================================
# 概率
# ===========================================================================

class ProbabilityPanel(CalcPanel):
    """概率分布 / 假设检验 / 回归 / 拟合 / 贝叶斯面板。"""

    module_key = "probability"

    INT_KEYS = {"df", "dfn", "dfd", "n"}

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)
        self._last_sample = None
        self._fg = "#ffffff"
        self._bg = "#1e1e1e"
        self._panel = "#2d2d30"

        # ---------------- 分布参数 ----------------
        self.dist = QComboBox()
        for k in prob_mod.DISTS.keys():
            self.dist.addItem(k, k)
        self.params = QLineEdit('{"loc":0,"scale":1}')
        self.x = QLineEdit("0")
        self.p = QLineEdit("0.95")
        self.n = QLineEdit("1000")

        self._dist_preview = InlinePreviewBar(
            calc_fn=self._preview_pdf)
        self._dist_preview.attach(
            self.x, enabled_getter=lambda: True)
        self.dist.currentIndexChanged.connect(
            lambda _: self._dist_preview.refresh(self.x.text()))
        self.params.editingFinished.connect(
            lambda: self._dist_preview.refresh(self.x.text()))

        self.plot_range = QLineEdit("-4, 4")
        self.plot_points = QLineEdit("300")

        # ---------------- 检验数据 ----------------
        self.data1 = QPlainTextEdit("1 2 3 4 5")
        self.data1.setFixedHeight(56)
        self.data2 = QPlainTextEdit("2 3 4 5 6")
        self.data2.setFixedHeight(56)
        self.mu0 = QLineEdit("0")
        self.alpha = QLineEdit("0.05")
        self.test_kind = QComboBox()
        for k in ("ttest_1samp", "ttest_ind", "ttest_paired",
                  "chi2", "anova"):
            self.test_kind.addItem(k, k)

        # ---------------- 拟合 / CI ----------------
        self.fit_data = QPlainTextEdit(
            "2.1 1.9 2.3 2.0 1.8 2.2 2.1 2.0")
        self.fit_data.setFixedHeight(56)
        self.ci_data = QPlainTextEdit(
            "2.1 1.9 2.3 2.0 1.8 2.2 2.1 2.0")
        self.ci_data.setFixedHeight(56)
        self.ci_sigma = QLineEdit("")

        # ---------------- 多元回归 ----------------
        self.mr_X = QPlainTextEdit(
            "1 2\n2 1\n3 4\n4 3\n5 6")
        self.mr_X.setFixedHeight(80)
        self.mr_y = QPlainTextEdit("3 5 8 9 12")
        self.mr_y.setFixedHeight(56)
        self.chi_table = QPlainTextEdit(
            "10 20 30\n20 15 25")
        self.chi_table.setFixedHeight(70)

        # ---------------- 绘图 ----------------
        self.figure = Figure(figsize=(6, 3.5))
        self.canvas = FigureCanvas(self.figure)

        self.result = ResultView(i18n)

        # ---------------- 按钮 ----------------
        b_pdf = QPushButton("PDF / PMF")
        b_pdf.clicked.connect(self.do_pdf)
        b_cdf = QPushButton("CDF")
        b_cdf.clicked.connect(self.do_cdf)
        b_q = QPushButton("Quantile")
        b_q.clicked.connect(self.do_q)
        b_s = QPushButton(i18n.t("prob_sample_btn", "抽样"))
        b_s.clicked.connect(self.do_sample)
        b_t = QPushButton(i18n.t("prob_test", "运行检验"))
        b_t.clicked.connect(self.do_test)
        b_r = QPushButton(i18n.t("prob_regress", "简单回归"))
        b_r.clicked.connect(self.do_regress)
        b_fit = QPushButton(i18n.t("fit", "拟合分布"))
        b_fit.clicked.connect(self.do_fit)
        b_ci = QPushButton(i18n.t("ci", "置信区间"))
        b_ci.clicked.connect(self.do_ci)
        b_mr = QPushButton(i18n.t("multi_reg", "多元回归"))
        b_mr.clicked.connect(self.do_multi_reg)

        b_plot_pdf = QPushButton(
            i18n.t("plot_pdf", "绘制 PDF"))
        b_plot_cdf = QPushButton(
            i18n.t("plot_cdf", "绘制 CDF"))
        b_plot_hist = QPushButton(
            i18n.t("plot_hist", "样本直方图"))
        b_plot_pdf.clicked.connect(self.plot_pdf)
        b_plot_cdf.clicked.connect(self.plot_cdf)
        b_plot_hist.clicked.connect(self.plot_hist)

        # ---------------- Tab ----------------
        tabs = QTabWidget()

        w1 = QWidget()
        f1 = QFormLayout(w1)
        f1.addRow(QLabel(i18n.t("prob_dist", "分布")),
                  self.dist)
        f1.addRow(QLabel(i18n.t("prob_params", "参数 JSON")),
                  self.params)
        f1.addRow(QLabel("x"), self.x)
        f1.addRow(QLabel(""), self._dist_preview)
        f1.addRow(QLabel("p"), self.p)
        f1.addRow(QLabel("n"), self.n)
        f1.addRow(QLabel(i18n.t("plot_range", "绘图范围")),
                  self.plot_range)
        f1.addRow(QLabel(i18n.t("plot_points", "绘图点数")),
                  self.plot_points)
        row = QHBoxLayout()
        for b in (b_pdf, b_cdf, b_q, b_s):
            row.addWidget(b)
        f1.addRow(row)
        row2 = QHBoxLayout()
        for b in (b_plot_pdf, b_plot_cdf, b_plot_hist):
            row2.addWidget(b)
        f1.addRow(row2)
        tabs.addTab(w1, i18n.t("prob", "分布"))

        w2 = QWidget()
        f2 = QFormLayout(w2)
        f2.addRow(QLabel(i18n.t("prob_test_kind", "检验类型")),
                  self.test_kind)
        f2.addRow(QLabel("data1"), self.data1)
        f2.addRow(QLabel("data2"), self.data2)
        f2.addRow(QLabel("μ₀"), self.mu0)
        f2.addRow(QLabel("α"), self.alpha)
        f2.addRow(QLabel("2D table (chi2)"), self.chi_table)
        f2.addRow(b_t)
        tabs.addTab(w2, i18n.t("prob_test", "检验"))

        w3 = QWidget()
        f3 = QFormLayout(w3)
        f3.addRow(QLabel("X data"), self.data1)
        f3.addRow(QLabel("Y data"), self.data2)
        f3.addRow(b_r)
        f3.addRow(QLabel("X matrix (multi)"), self.mr_X)
        f3.addRow(QLabel("y (multi)"), self.mr_y)
        f3.addRow(b_mr)
        tabs.addTab(w3, i18n.t("prob_regress", "回归"))

        w4 = QWidget()
        f4 = QFormLayout(w4)
        f4.addRow(QLabel("Data"), self.fit_data)
        f4.addRow(b_fit)
        f4.addRow(QLabel("Data"), self.ci_data)
        f4.addRow(QLabel("σ (optional)"), self.ci_sigma)
        f4.addRow(b_ci)
        tabs.addTab(w4, i18n.t("fit_ci", "拟合 / 区间"))

        w5 = QWidget()
        v5 = QVBoxLayout(w5)
        v5.addWidget(self.canvas, 1)
        tabs.addTab(w5, i18n.t("chart", "图表"))

        # 贝叶斯 Tab（延迟导入；widget 将在第 12 轮合并）
        tabs.addTab(
            BayesianTab(settings, i18n, history, self),
            i18n.t("prob_bayes", "贝叶斯"))

        main = QVBoxLayout(self)
        main.addWidget(tabs, 2)
        main.addWidget(self.result, 1)

    # ==================================================================
    # 参数 / 工具
    # ==================================================================

    def _params(self):
        s = self.params.text().strip() or "{}"
        return json.loads(s)

    def _build_kw(self, params):
        kw = {}
        for k, v in params.items():
            if v in (None, ""):
                continue
            if k in self.INT_KEYS:
                kw[k] = int(round(float(v)))
            else:
                kw[k] = float(v)
        return kw

    def _show(self, obj, tag="prob"):
        s = json.dumps(obj, ensure_ascii=False,
                       indent=2, default=str)
        self.result.show_result(s, "")
        self.add_history(
            self.dist.currentData(), s, module=tag)

    def _nums(self, w):
        return [float(x)
                for x in re.split(r"[\s,;]+", w.toPlainText())
                if x]

    @staticmethod
    def _nums_line(line):
        return [float(x)
                for x in re.split(r"[\s,;]+", line) if x]

    def _prep_axes(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(self._panel)
        self.figure.patch.set_facecolor(self._bg)
        ax.tick_params(colors=self._fg)
        for sp in ax.spines.values():
            sp.set_color(self._fg)
        ax.grid(True, color="#666", alpha=0.4, linewidth=0.6)
        return ax

    def _plot_range_vals(self):
        s = (self.plot_range.text() or "").strip() or "-4, 4"
        parts = re.split(r"[,;\s]+", s)
        lo, hi = -4.0, 4.0
        if len(parts) >= 2:
            try:
                lo, hi = float(parts[0]), float(parts[1])
            except ValueError:
                pass
        return lo, hi

    # ==================================================================
    # 分布
    # ==================================================================

    def _preview_pdf(self, _text):
        """x 变化时实时预览 PDF / PMF 值。"""
        try:
            name = self.dist.currentData()
            params = self._params()
            xv = float(self.x.text())
            v = prob_mod.pdf_or_pmf(name, xv, params)
            try:
                disp = f"{v:.4g}"
            except Exception:
                disp = str(v)
            is_discrete = name in ("binom", "poisson", "geom")
            tag = "PMF" if is_discrete else "PDF"
            return f"{tag}({name}, x={xv:g}) = {disp}"
        except Exception:
            return None

    def do_pdf(self):
        try:
            v = prob_mod.pdf_or_pmf(
                self.dist.currentData(),
                float(self.x.text()), self._params())
            self._show({"pdf_or_pmf": v})
        except Exception as e:
            self.result.show_error(e)

    def do_cdf(self):
        try:
            v = prob_mod.cdf(
                self.dist.currentData(),
                float(self.x.text()), self._params())
            self._show({"cdf": v})
        except Exception as e:
            self.result.show_error(e)

    def do_q(self):
        try:
            v = prob_mod.quantile(
                self.dist.currentData(),
                float(self.p.text()), self._params())
            self._show({"quantile": v})
        except Exception as e:
            self.result.show_error(e)

    def do_sample(self):
        try:
            v = prob_mod.sample(
                self.dist.currentData(),
                self._params(), int(self.n.text()))
            self._last_sample = v
            self._show({"sample": v})
        except Exception as e:
            self.result.show_error(e)

    # ==================================================================
    # 检验
    # ==================================================================

    def do_test(self):
        try:
            k = self.test_kind.currentData()
            if k == "ttest_1samp":
                r = prob_mod.ttest_1samp(
                    self._nums(self.data1),
                    float(self.mu0.text()),
                    float(self.alpha.text()))
            elif k == "ttest_ind":
                r = prob_mod.ttest_ind(
                    self._nums(self.data1),
                    self._nums(self.data2),
                    float(self.alpha.text()))
            elif k == "ttest_paired":
                a = self._nums(self.data1)
                b = self._nums(self.data2)
                from scipy import stats as st
                t, p = st.ttest_rel(a, b)
                r = {"t": float(t), "p": float(p),
                     "reject_H0": bool(
                         p < float(self.alpha.text()))}
            elif k == "chi2":
                r = prob_mod.chi2_independence([
                    self._nums_line(ln)
                    for ln in self.chi_table.toPlainText()
                    .splitlines() if ln.strip()])
            elif k == "anova":
                r = prob_mod.anova_oneway(
                    self._nums(self.data1),
                    self._nums(self.data2))
            else:
                return
            self._show(r, tag="prob-test")
        except Exception as e:
            self.result.show_error(e)

    def do_regress(self):
        try:
            r = prob_mod.linear_regression(
                self._nums(self.data1),
                self._nums(self.data2))
            self._show(r, tag="prob-regress")
        except Exception as e:
            self.result.show_error(e)

    def do_fit(self):
        try:
            data = self._nums(self.fit_data)
            r = prob_mod.fit_distribution(
                self.dist.currentData(), data)
            self._show(r, tag="prob-fit")
        except Exception as e:
            self.result.show_error(e)

    def do_ci(self):
        try:
            data = self._nums(self.ci_data)
            sigma = self.ci_sigma.text().strip()
            r = prob_mod.confidence_interval_mean(
                data, float(self.alpha.text()),
                float(sigma) if sigma else None)
            self._show(r, tag="prob-ci")
        except Exception as e:
            self.result.show_error(e)

    def do_multi_reg(self):
        try:
            X = []
            for line in (self.mr_X.toPlainText()
                         .splitlines()):
                if line.strip():
                    X.append([
                        float(x)
                        for x in re.split(
                            r"[\s,;]+", line.strip())
                        if x])
            y = [float(x)
                 for x in re.split(
                     r"[\s,;]+", self.mr_y.toPlainText())
                 if x]
            r = prob_mod.multiple_regression(X, y)
            self._show(r, tag="prob-mr")
        except Exception as e:
            self.result.show_error(e)

    # ==================================================================
    # 绘图
    # ==================================================================

    def plot_pdf(self):
        try:
            name = self.dist.currentData()
            params = self._params()
            lo, hi = self._plot_range_vals()
            n = int(self.plot_points.text() or "300")
            fn = prob_mod.DISTS[name][0]
            kw = self._build_kw(params)

            if name in ("binom", "poisson", "geom"):
                xi = np.arange(int(np.ceil(lo)),
                               int(np.floor(hi)) + 1)
                ys = fn.pmf(xi, **kw)
                ax = self._prep_axes()
                ax.bar(xi, ys, color="#007acc", alpha=0.85)
                ax.set_ylabel("PMF", color=self._fg)
            else:
                xs = np.linspace(lo, hi, n)
                ys = fn.pdf(xs, **kw)
                ax = self._prep_axes()
                ax.plot(xs, ys, color="#007acc",
                        linewidth=1.6)
                ax.set_ylabel("PDF", color=self._fg)

            ax.set_xlabel("x", color=self._fg)
            try:
                self.figure.tight_layout()
            except Exception:
                pass
            self.canvas.draw()
        except Exception as e:
            self.result.show_error(e)

    def plot_cdf(self):
        try:
            name = self.dist.currentData()
            params = self._params()
            lo, hi = self._plot_range_vals()
            n = int(self.plot_points.text() or "300")
            xs = np.linspace(lo, hi, n)
            fn = prob_mod.DISTS[name][0]
            kw = self._build_kw(params)
            ys = fn.cdf(xs, **kw)
            ax = self._prep_axes()
            ax.plot(xs, ys, color="#ff7f0e", linewidth=1.6)
            ax.set_xlabel("x", color=self._fg)
            ax.set_ylabel("CDF", color=self._fg)
            try:
                self.figure.tight_layout()
            except Exception:
                pass
            self.canvas.draw()
        except Exception as e:
            self.result.show_error(e)

    def plot_hist(self):
        try:
            data = self._last_sample
            if not data:
                self.do_sample()
                data = self._last_sample
            if not data:
                return
            ax = self._prep_axes()
            ax.hist(data, bins=30, color="#2ca02c",
                    edgecolor="#ffffff", alpha=0.85)
            ax.set_xlabel("value", color=self._fg)
            ax.set_ylabel("count", color=self._fg)
            try:
                self.figure.tight_layout()
            except Exception:
                pass
            self.canvas.draw()
        except Exception as e:
            self.result.show_error(e)

    def set_theme_colors(self, fg, bg, panel):
        self._fg, self._bg, self._panel = fg, bg, panel


# ===========================================================================
# 随机数
# ===========================================================================

class RandomPanel(CalcPanel):
    """随机数面板：分布 / 洗牌 / UUID / 密码。"""

    module_key = "random"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)

        tabs = QTabWidget()
        tabs.addTab(self._build_dist_tab(),
                    i18n.t("distribution", "Distribution"))
        tabs.addTab(self._build_shuffle_tab(),
                    i18n.t("shuffle", "Shuffle / Sample"))
        tabs.addTab(self._build_uuid_tab(), "UUID")
        tabs.addTab(self._build_pw_tab(),
                    i18n.t("password", "Password"))

        main = QVBoxLayout(self)
        main.addWidget(tabs)
        main.addWidget(QLabel(i18n.t("result")))
        main.addWidget(self.result, 1)

    # ==================================================================
    # 分布
    # ==================================================================

    def _build_dist_tab(self):
        self.dist_kind = QComboBox()
        for k in ("uniform", "normal", "exponential",
                  "int", "choice"):
            self.dist_kind.addItem(k, k)
        self.dist_kind.currentIndexChanged.connect(
            self._update_dist_params)
        self.seed = QLineEdit("")
        self.seed.setPlaceholderText("(留空=随机)")
        self.d_n = QLineEdit("10")
        self.p_low = QLineEdit("0")
        self.p_high = QLineEdit("1")
        self.p_mu = QLineEdit("0")
        self.p_sigma = QLineEdit("1")
        self.p_lambda = QLineEdit("1")
        self.p_i_low = QLineEdit("1")
        self.p_i_high = QLineEdit("100")
        self.p_pool = QLineEdit("A,B,C,D,E")

        self.d_form = QFormLayout()
        self.d_form.addRow(
            QLabel(self.i18n.t("kind", "Kind")),
            self.dist_kind)
        self.d_form.addRow(
            QLabel(self.i18n.t("seed", "Seed")), self.seed)
        self.d_form.addRow(
            QLabel(self.i18n.t("count", "Count")), self.d_n)
        self._d_rows = {}
        self._add_d_row("uniform_lo", QLabel("low"),
                        self.p_low)
        self._add_d_row("uniform_hi", QLabel("high"),
                        self.p_high)
        self._add_d_row("normal_mu", QLabel("μ"), self.p_mu)
        self._add_d_row("normal_sigma", QLabel("σ"),
                        self.p_sigma)
        self._add_d_row("exp_lambda", QLabel("λ"),
                        self.p_lambda)
        self._add_d_row("int_lo", QLabel("int low"),
                        self.p_i_low)
        self._add_d_row("int_hi", QLabel("int high"),
                        self.p_i_high)
        self._add_d_row("choice_pool", QLabel("候选池"),
                        self.p_pool)

        b_gen = QPushButton(self.i18n.t("generate"))
        b_gen.clicked.connect(self._gen_dist)

        w = QWidget()
        v = QVBoxLayout(w)
        v.addLayout(self.d_form)
        v.addWidget(b_gen)
        v.addStretch(1)
        self._update_dist_params()
        return w

    def _add_d_row(self, name, label, widget):
        self.d_form.addRow(label, widget)
        self._d_rows[name] = (label, widget,
                              self.d_form.rowCount() - 1)

    def _update_dist_params(self, *_):
        kind = self.dist_kind.currentData()
        needed = {
            "uniform": {"uniform_lo", "uniform_hi"},
            "normal": {"normal_mu", "normal_sigma"},
            "exponential": {"exp_lambda"},
            "int": {"int_lo", "int_hi"},
            "choice": {"choice_pool"},
        }.get(kind, set())
        for name, (label, widget, row) in self._d_rows.items():
            vis = name in needed
            try:
                self.d_form.setRowVisible(row, vis)
            except Exception:
                label.setVisible(vis)
                widget.setVisible(vis)

    def _gen_dist(self):
        try:
            kind = self.dist_kind.currentData()
            params = {
                "low": self.p_low.text(),
                "high": self.p_high.text(),
                "mu": self.p_mu.text(),
                "sigma": self.p_sigma.text(),
                "lambda": self.p_lambda.text(),
            }
            if kind == "int":
                params = {"low": int(self.p_i_low.text()),
                          "high": int(self.p_i_high.text())}
            elif kind == "choice":
                pool = [x.strip()
                        for x in self.p_pool.text().split(",")
                        if x.strip()]
                params = {"pool": pool}
            r = prob_mod.distribution_sample(
                kind, int(self.d_n.text()), params,
                self.seed.text() or None)
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history(
                f"{kind} n={self.d_n.text()}", s[:500],
                module="random")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "random"))

    # ==================================================================
    # 洗牌 / 抽样
    # ==================================================================

    def _build_shuffle_tab(self):
        self.sh_items = QPlainTextEdit(
            "1,2,3,4,5,6,7,8,9,10")
        self.sh_items.setFixedHeight(80)
        self.sh_seed = QLineEdit("")
        self.sh_k = QLineEdit("3")
        self.sh_replace = QCheckBox(
            self.i18n.t("with_replacement", "有放回"))
        b_sh = QPushButton(self.i18n.t("shuffle", "Shuffle"))
        b_sa = QPushButton(self.i18n.t("sample", "Sample"))
        b_sh.clicked.connect(self._do_shuffle)
        b_sa.clicked.connect(self._do_sample)

        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabel(self.i18n.t(
            "items", "Items (comma/space sep)")))
        v.addWidget(self.sh_items)
        v.addWidget(QLabel(self.i18n.t("seed", "Seed")))
        v.addWidget(self.sh_seed)
        v.addWidget(QLabel(self.i18n.t("count", "Count")))
        v.addWidget(self.sh_k)
        v.addWidget(self.sh_replace)
        row = QHBoxLayout()
        row.addWidget(b_sh)
        row.addWidget(b_sa)
        v.addLayout(row)
        v.addStretch(1)
        return w

    def _items(self):
        return [x.strip() for x in re.split(
            r"[\s,;]+", self.sh_items.toPlainText())
            if x.strip()]

    def _do_shuffle(self):
        try:
            r = prob_mod.shuffle_list(
                self._items(), self.sh_seed.text() or None)
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history(
                f"n={len(r)}", s[:500],
                module="random-shuffle")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "random"))

    def _do_sample(self):
        try:
            r = prob_mod.sample_from_list(
                self._items(), int(self.sh_k.text()),
                self.sh_replace.isChecked(),
                self.sh_seed.text() or None)
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history(
                f"k={self.sh_k.text()}", s[:500],
                module="random-sample")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "random"))

    # ==================================================================
    # UUID
    # ==================================================================

    def _build_uuid_tab(self):
        self.uuid_n = QLineEdit("5")
        self.uuid_ver = QComboBox()
        for v in (1, 3, 4, 5):
            self.uuid_ver.addItem(f"v{v}", v)
        self.uuid_ver.setCurrentIndex(2)
        b = QPushButton(self.i18n.t("generate"))
        b.clicked.connect(self._do_uuid)

        w = QWidget()
        f = QFormLayout(w)
        f.addRow(QLabel(self.i18n.t("count", "Count")),
                 self.uuid_n)
        f.addRow(QLabel("Version"), self.uuid_ver)
        f.addRow(b)
        return w

    def _do_uuid(self):
        try:
            r = prob_mod.uuid_list(
                int(self.uuid_n.text()),
                self.uuid_ver.currentData())
            s = "\n".join(r)
            self.result.setPlainText(s)
            self.add_history(
                f"n={self.uuid_n.text()}", s[:500],
                module="random-uuid")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "random"))

    # ==================================================================
    # 密码
    # ==================================================================

    def _build_pw_tab(self):
        self.pw_len = QSpinBox()
        self.pw_len.setRange(4, 128)
        self.pw_len.setValue(16)
        self.pw_upper = QCheckBox("A-Z")
        self.pw_upper.setChecked(True)
        self.pw_lower = QCheckBox("a-z")
        self.pw_lower.setChecked(True)
        self.pw_digit = QCheckBox("0-9")
        self.pw_digit.setChecked(True)
        self.pw_sym = QCheckBox("!@#$")
        self.pw_noamb = QCheckBox(
            self.i18n.t("no_ambiguous", "排除易混字符"))
        self.pw_n = QLineEdit("1")
        b = QPushButton(self.i18n.t("generate"))
        b.clicked.connect(self._do_pw)

        w = QWidget()
        f = QFormLayout(w)
        f.addRow(QLabel(self.i18n.t("length", "Length")),
                 self.pw_len)
        f.addRow(QLabel(self.i18n.t("count", "Count")),
                 self.pw_n)
        f.addRow(QLabel(""), self.pw_upper)
        f.addRow(QLabel(""), self.pw_lower)
        f.addRow(QLabel(""), self.pw_digit)
        f.addRow(QLabel(""), self.pw_sym)
        f.addRow(QLabel(""), self.pw_noamb)
        f.addRow(b)
        return w

    def _do_pw(self):
        try:
            out = []
            for _ in range(max(1, int(self.pw_n.text()))):
                out.append(prob_mod.password_gen(
                    self.pw_len.value(),
                    self.pw_upper.isChecked(),
                    self.pw_lower.isChecked(),
                    self.pw_digit.isChecked(),
                    self.pw_sym.isChecked(),
                    self.pw_noamb.isChecked()))
            self.result.setPlainText("\n".join(out))
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "random"))


# ===========================================================================
# 数据表
# ===========================================================================

class DataTablePanel(CalcPanel):
    """数据表编辑器面板：可编辑表头、公式列、导入/导出 CSV/JSON。"""

    module_key = "data_table"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)
        self._formulas = {}
        self._suppress_item_changed = False

        # ---------------- 表格 ----------------
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["A", "B", "C", "D"])
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self.table.horizontalHeader().setContextMenuPolicy(
            Qt.CustomContextMenu)
        self.table.horizontalHeader().customContextMenuRequested\
            .connect(self._header_context_menu)

        self._recalc_timer = QTimer(self)
        self._recalc_timer.setSingleShot(True)
        self._recalc_timer.setInterval(350)
        self._recalc_timer.timeout.connect(self._auto_recalc)
        self.table.itemChanged.connect(self._on_cell_changed)

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
        b_send = QPushButton(
            i18n.t("send_to_data_ops", "发送到数据运算"))

        b_add.clicked.connect(self._append_row)
        b_del.clicked.connect(self._delete_rows)
        b_col.clicked.connect(self._append_col)
        b_delcol.clicked.connect(self._delete_cols)
        b_import.clicked.connect(self._import_csv)
        b_export.clicked.connect(self._export_csv)
        b_json.clicked.connect(self._export_json)
        b_calc.clicked.connect(self._recalc_all)
        b_send.clicked.connect(self._send_to_data_ops)

        row = QHBoxLayout()
        for b in (b_add, b_del, b_col, b_delcol, b_calc,
                  b_import, b_export, b_json, b_send):
            row.addWidget(b)
        row.addStretch(1)

        # ---------------- 公式行 ----------------
        form_row = QHBoxLayout()
        form_row.addWidget(QLabel(
            i18n.t("formula_col", "公式列")))
        self.formula_col = QComboBox()
        self.formula_col.currentIndexChanged.connect(
            self._on_formula_col_changed)
        form_row.addWidget(self.formula_col)
        form_row.addWidget(QLabel(
            i18n.t("formula", "公式")))
        self.formula_input = QLineEdit()
        self.formula_input.setPlaceholderText("=[A] + [B]")
        self.formula_input.editingFinished.connect(
            self._save_formula)
        form_row.addWidget(self.formula_input, 1)

        self.result = ResultView(i18n)

        # ---------------- 主布局 ----------------
        main = QVBoxLayout(self)
        main.addLayout(row)
        main.addLayout(form_row)
        main.addWidget(self.table, 3)
        main.addWidget(self.result, 1)

        self._refresh_formula_combo()

    # ==================================================================
    # 单元格变更
    # ==================================================================

    def _on_cell_changed(self, _item):
        if self._suppress_item_changed:
            return
        if not self._formulas:
            return
        self._recalc_timer.start()

    def _auto_recalc(self):
        try:
            self._recalc_all(silent=True)
        except Exception as e:
            log_exc(e, module="DataTablePanel._auto_recalc")

    # ==================================================================
    # 列管理
    # ==================================================================

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
        if (isinstance(cur, int)
                and 0 <= cur < self.formula_col.count()):
            self.formula_col.setCurrentIndex(
                self.formula_col.findData(cur))

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
        cols = sorted(
            {i.column()
             for i in self.table.selectedIndexes()},
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

    # ==================================================================
    # 行管理
    # ==================================================================

    def _append_row(self):
        self._suppress_item_changed = True
        try:
            r = self.table.rowCount()
            self.table.insertRow(r)
            for c in range(self.table.columnCount()):
                self.table.setItem(
                    r, c, QTableWidgetItem(""))
        finally:
            self._suppress_item_changed = False

    def _delete_rows(self):
        rows = sorted(
            {i.row() for i in self.table.selectedIndexes()},
            reverse=True)
        if not rows and self.table.rowCount():
            rows = [self.table.rowCount() - 1]
        for r in rows:
            self.table.removeRow(r)

    # ==================================================================
    # 数据转换
    # ==================================================================

    def _to_data_table(self):
        dt = data_mod.DataTable()
        cols = [self._col_name(c)
                for c in range(self.table.columnCount())]
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

    def _recalc_all(self, silent=False):
        self._suppress_item_changed = True
        try:
            dt = self._to_data_table()
            dt.recalc_all()
            for r in range(self.table.rowCount()):
                for c in range(self.table.columnCount()):
                    v = dt.get_cell(r, c)
                    it = self.table.item(r, c)
                    if it is None:
                        self.table.setItem(
                            r, c, QTableWidgetItem(v))
                    elif it.text() != v:
                        it.setText(v)
            if not silent:
                self.result.show_result(
                    f"✓ {self.i18n.t('recalc_done', '重算完成')}",
                    "")
        except Exception as e:
            if not silent:
                self.result.show_error(e)
        finally:
            self._suppress_item_changed = False

    # ==================================================================
    # 表头右键
    # ==================================================================

    def _header_context_menu(self, pos):
        idx = self.table.horizontalHeader().logicalIndexAt(pos)
        if idx < 0:
            return
        menu = QMenu(self)
        a_rename = menu.addAction(
            self.i18n.t("rename_col", "重命名"))
        a_setform = menu.addAction(
            self.i18n.t("set_formula", "设为公式列…"))
        a_clearform = menu.addAction(
            self.i18n.t("clear_formula", "清除公式"))
        chosen = menu.exec(
            self.table.horizontalHeader().mapToGlobal(pos))
        if chosen is a_rename:
            cur = self._col_name(idx)
            text, ok = QInputDialog.getText(
                self,
                self.i18n.t("rename_col", "重命名"),
                self.i18n.t("new_name", "新名称："),
                text=cur)
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

    # ==================================================================
    # 导入 / 导出
    # ==================================================================

    def _import_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import CSV", "",
            "CSV (*.csv);;Text (*.txt)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                text = f.read()
            dt = data_mod.DataTable()
            dt.from_csv(text)
            self._load_from_data_table(dt)
            self.result.show_result(
                f"✓ {self.i18n.t('imported', '已导入')} "
                f"{len(dt.rows)}×{len(dt.columns)}", "")
        except Exception as e:
            self.result.show_error(e)

    def _load_from_data_table(self, dt):
        self._formulas = {}
        self._suppress_item_changed = True
        try:
            self.table.setColumnCount(len(dt.columns))
            self.table.setHorizontalHeaderLabels(dt.columns)
            self.table.setRowCount(0)
            for row in dt.rows:
                r = self.table.rowCount()
                self.table.insertRow(r)
                for c in range(self.table.columnCount()):
                    v = row[c] if c < len(row) else ""
                    self.table.setItem(
                        r, c, QTableWidgetItem(str(v)))
        finally:
            self._suppress_item_changed = False
        self._refresh_formula_combo()

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "table.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            dt = self._to_data_table()
            with open(path, "w", encoding="utf-8-sig",
                      newline="") as f:
                f.write(dt.to_csv())
            self.result.show_result(f"✓ {path}", "")
        except Exception as e:
            self.result.show_error(e)

    def _export_json(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export JSON", "table.json",
            "JSON (*.json)")
        if not path:
            return
        try:
            dt = self._to_data_table()
            with open(path, "w", encoding="utf-8") as f:
                f.write(dt.to_json())
            self.result.show_result(f"✓ {path}", "")
        except Exception as e:
            self.result.show_error(e)

    # ==================================================================
    # 发送到数据运算
    # ==================================================================

    def _send_to_data_ops(self):
        """把当前表格发送到数据运算面板（CSV 文本）。"""
        try:
            dt = self._to_data_table()
            csv_text = dt.to_csv()
            bus().send_to_data_ops.emit(csv_text)
            try:
                from ui.shell import toast
                toast(self.window(),
                      self.i18n.t("sent_to_data_ops",
                                  "已发送到数据运算面板"),
                      level="success")
            except Exception:
                pass
        except Exception as e:
            log_exc(e, module="DataTablePanel._send_to_data_ops")


# ===========================================================================
# 数据运算
# ===========================================================================

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
    """数据运算面板：列聚合 / 排序 / 筛选 / 分析。"""

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
                headers.append(
                    it.text() if it else f"Col{c + 1}")

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
        for k, label in data_mod.AGG_OPS.items():
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
            vals = data_mod.column_values(
                self._rows, self._headers, name)
            r = data_mod.aggregate(vals, op)
            label = data_mod.AGG_OPS.get(op, op)
            self.result.show_result(
                f"{label}([{name}]) = {r:g}", "")
            self.add_history(
                f"{op}([{name}])", f"{r:g}",
                module="data-ops")
        except Exception as e:
            self.result.show_error(
                e, retry_cb=self._do_aggregate)

    def _send_to_stats(self):
        try:
            name = self.agg_col.currentData()
            if name is None:
                return
            vals = data_mod.column_values(
                self._rows, self._headers, name)
            text = data_mod.to_stats_text(vals)
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
            self._rows = data_mod.sort_rows(
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
        for k in data_mod.FILTER_OPS:
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
            self._rows = data_mod.filter_rows(
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
            self.i18n.t("data_ops_analyze_all",
                        "分析所有列"))
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
            r = data_mod.analyze_rows(
                self._rows, self._headers)
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
            r = data_mod.analyze_rows(
                self._rows, self._headers)
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

# ===========================================================================
# 贝叶斯 / MCMC / 蒙特卡洛
# ===========================================================================

class _BayesWorker(QThread):
    """MCMC / MC 后台执行。"""

    done = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            def _prog(done, total):
                self.progress.emit(int(done), int(total))

            def _cancel():
                return self._cancelled

            self._kwargs.setdefault("progress_cb", _prog)
            self._kwargs.setdefault("cancelled", _cancel)
            r = self._fn(*self._args, **self._kwargs)
            if not self._cancelled:
                self.done.emit(r)
        except Exception as e:  # noqa: BLE001
            if not self._cancelled:
                self.failed.emit(str(e))


class BayesianTab(QWidget):
    """贝叶斯 / MCMC / 蒙特卡洛 Tab。"""

    def __init__(self, settings, i18n, history, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n
        self.history = history
        self._worker: _BayesWorker | None = None

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_beta_binom(), "Beta-Binomial")
        self.tabs.addTab(self._build_normal_normal(), "Normal-Normal")
        self.tabs.addTab(self._build_gamma_poisson(), "Gamma-Poisson")
        self.tabs.addTab(self._build_mcmc(), "MCMC")
        self.tabs.addTab(self._build_monte_carlo(), "Monte Carlo")

        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)
        self.result.setMaximumHeight(220)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)

        self.status = QLabel("")
        self.status.setStyleSheet("color: #888;")

        main = QVBoxLayout(self)
        main.addWidget(self.tabs, 1)
        main.addWidget(self.progress)
        main.addWidget(QLabel(self.i18n.t("result", "结果")))
        main.addWidget(self.result)
        main.addWidget(self.status)

    # ==================================================================
    # Beta-Binomial
    # ==================================================================

    def _build_beta_binom(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.bb_alpha = QDoubleSpinBox()
        self.bb_alpha.setRange(0.001, 1e9)
        self.bb_alpha.setValue(1.0)
        self.bb_beta = QDoubleSpinBox()
        self.bb_beta.setRange(0.001, 1e9)
        self.bb_beta.setValue(1.0)
        self.bb_succ = QSpinBox()
        self.bb_succ.setRange(0, 10 ** 9)
        self.bb_succ.setValue(7)
        self.bb_fail = QSpinBox()
        self.bb_fail.setRange(0, 10 ** 9)
        self.bb_fail.setValue(3)
        b = QPushButton("计算后验")
        b.clicked.connect(self._do_beta_binom)

        f = QFormLayout()
        f.addRow(QLabel("α (先验)"), self.bb_alpha)
        f.addRow(QLabel("β (先验)"), self.bb_beta)
        f.addRow(QLabel("成功数"), self.bb_succ)
        f.addRow(QLabel("失败数"), self.bb_fail)
        f.addRow(b)
        v.addLayout(f)
        v.addStretch(1)
        return w

    def _do_beta_binom(self):
        try:
            r = prob_mod.beta_binomial(
                self.bb_alpha.value(), self.bb_beta.value(),
                self.bb_succ.value(), self.bb_fail.value())
            self._show(r)
        except Exception as e:
            self._show_err(e)

    # ==================================================================
    # Normal-Normal
    # ==================================================================

    def _build_normal_normal(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.nn_mu0 = QDoubleSpinBox()
        self.nn_mu0.setRange(-1e9, 1e9)
        self.nn_mu0.setValue(0.0)
        self.nn_s0 = QDoubleSpinBox()
        self.nn_s0.setRange(0.001, 1e9)
        self.nn_s0.setValue(1.0)
        self.nn_xbar = QDoubleSpinBox()
        self.nn_xbar.setRange(-1e9, 1e9)
        self.nn_xbar.setValue(0.5)
        self.nn_sigma = QDoubleSpinBox()
        self.nn_sigma.setRange(0.001, 1e9)
        self.nn_sigma.setValue(1.0)
        self.nn_n = QSpinBox()
        self.nn_n.setRange(1, 10 ** 9)
        self.nn_n.setValue(20)
        b = QPushButton("计算后验")
        b.clicked.connect(self._do_normal_normal)

        f = QFormLayout()
        f.addRow(QLabel("μ₀"), self.nn_mu0)
        f.addRow(QLabel("σ₀"), self.nn_s0)
        f.addRow(QLabel("样本均值 x̄"), self.nn_xbar)
        f.addRow(QLabel("观测 σ"), self.nn_sigma)
        f.addRow(QLabel("样本量 n"), self.nn_n)
        f.addRow(b)
        v.addLayout(f)
        v.addStretch(1)
        return w

    def _do_normal_normal(self):
        try:
            r = prob_mod.normal_normal(
                self.nn_mu0.value(), self.nn_s0.value(),
                self.nn_xbar.value(), self.nn_sigma.value(),
                self.nn_n.value())
            self._show(r)
        except Exception as e:
            self._show_err(e)

    # ==================================================================
    # Gamma-Poisson
    # ==================================================================

    def _build_gamma_poisson(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.gp_alpha = QDoubleSpinBox()
        self.gp_alpha.setRange(0.001, 1e9)
        self.gp_alpha.setValue(2.0)
        self.gp_beta = QDoubleSpinBox()
        self.gp_beta.setRange(0.001, 1e9)
        self.gp_beta.setValue(1.0)
        self.gp_counts = QLineEdit("3, 5, 4, 6, 2, 7")
        b = QPushButton("计算后验")
        b.clicked.connect(self._do_gamma_poisson)

        f = QFormLayout()
        f.addRow(QLabel("α (先验 shape)"), self.gp_alpha)
        f.addRow(QLabel("β (先验 rate)"), self.gp_beta)
        f.addRow(QLabel("计数（逗号分隔）"), self.gp_counts)
        f.addRow(b)
        v.addLayout(f)
        v.addStretch(1)
        return w

    def _do_gamma_poisson(self):
        try:
            counts = [int(x) for x in
                      re.split(r"[\s,;]+", self.gp_counts.text())
                      if x]
            r = prob_mod.gamma_poisson(
                self.gp_alpha.value(), self.gp_beta.value(), counts)
            self._show(r)
        except Exception as e:
            self._show_err(e)

    # ==================================================================
    # MCMC
    # ==================================================================

    def _build_mcmc(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.mc_kind = QComboBox()
        self.mc_kind.addItem("1D 正态后验", "normal")
        self.mc_kind.addItem("1D 双峰（两个正态混合）", "bimodal")
        self.mc_kind.addItem("2D 相关正态", "2d_normal")
        self.mc_kind.currentIndexChanged.connect(
            self._update_mcmc_hint)

        self.mc_n = QSpinBox()
        self.mc_n.setRange(100, 1_000_000)
        self.mc_n.setValue(20000)
        self.mc_burn = QSpinBox()
        self.mc_burn.setRange(0, 1_000_000)
        self.mc_burn.setValue(2000)
        self.mc_scale = QDoubleSpinBox()
        self.mc_scale.setRange(0.001, 100.0)
        self.mc_scale.setValue(0.5)
        self.mc_seed = QSpinBox()
        self.mc_seed.setRange(-1, 2 ** 31 - 1)
        self.mc_seed.setValue(-1)

        self.mc_hint = QLabel("")
        self.mc_hint.setStyleSheet("color:#888;")

        b_run = QPushButton("采样")
        b_run.clicked.connect(self._do_mcmc)
        b_stop = QPushButton("取消")
        b_stop.setEnabled(False)
        b_stop.clicked.connect(self._cancel)
        self._mcmc_stop = b_stop

        f = QFormLayout()
        f.addRow(QLabel("目标分布"), self.mc_kind)
        f.addRow(QLabel(""), self.mc_hint)
        f.addRow(QLabel("采样数"), self.mc_n)
        f.addRow(QLabel("Burn-in"), self.mc_burn)
        f.addRow(QLabel("Proposal σ"), self.mc_scale)
        f.addRow(QLabel("Seed（-1 随机）"), self.mc_seed)
        row = QHBoxLayout()
        row.addWidget(b_run)
        row.addWidget(b_stop)
        f.addRow(row)
        v.addLayout(f)
        v.addStretch(1)
        self._update_mcmc_hint()
        return w

    def _update_mcmc_hint(self):
        k = self.mc_kind.currentData()
        hints = {
            "normal": "log p(θ) = -0.5*θ²（标准正态）",
            "bimodal": ("log p(θ) = log(exp(-(θ-2)²/2) + "
                        "exp(-(θ+2)²/2))"),
            "2d_normal": "2 维相关正态，ρ=0.7",
        }
        self.mc_hint.setText(hints.get(k, ""))

    def _build_log_posterior(self, kind: str):
        import math

        if kind == "normal":
            def lp(theta):
                x = theta[0]
                return -0.5 * x * x
            return lp
        if kind == "bimodal":
            def lp(theta):
                x = theta[0]
                a = math.exp(-0.5 * (x - 2) ** 2)
                b = math.exp(-0.5 * (x + 2) ** 2)
                return math.log(a + b + 1e-300)
            return lp
        if kind == "2d_normal":
            def lp(theta):
                x, y = theta[0], theta[1]
                rho = 0.7
                det = 1 - rho * rho
                z = (x * x - 2 * rho * x * y + y * y) / det
                return -0.5 * z
            return lp
        raise ValueError(f"未知目标分布：{kind}")

    def _do_mcmc(self):
        kind = self.mc_kind.currentData()
        try:
            lp = self._build_log_posterior(kind)
        except Exception as e:
            self._show_err(e)
            return

        if kind == "2d_normal":
            init = [0.0, 0.0]
        else:
            init = [0.0]

        seed = self.mc_seed.value()
        if seed < 0:
            seed = None

        self._set_busy(True)
        self._mcmc_stop.setEnabled(True)
        self.status.setText("MCMC 采样中…")

        self._worker = _BayesWorker(
            prob_mod.metropolis_hastings,
            lp, init,
            n_samples=self.mc_n.value(),
            burn_in=self.mc_burn.value(),
            proposal_scale=self.mc_scale.value(),
            seed=seed,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_mcmc_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_mcmc_done(self, r: dict):
        try:
            summary = {
                "n_samples": r.get("n_samples"),
                "n_dim": r.get("n_dim"),
                "burn_in": r.get("burn_in"),
                "mean": r.get("mean"),
                "std": r.get("std"),
                "ess": r.get("ess"),
                "acceptance_rate": r.get("acceptance_rate"),
                "map_estimate": r.get("map_estimate"),
            }
            trace = r.get("trace") or []
            if trace and r.get("n_dim") == 1:
                arr = np.asarray([t[0] for t in trace])
                summary["quantiles"] = {
                    "5%": float(np.quantile(arr, 0.05)),
                    "25%": float(np.quantile(arr, 0.25)),
                    "50%": float(np.quantile(arr, 0.5)),
                    "75%": float(np.quantile(arr, 0.75)),
                    "95%": float(np.quantile(arr, 0.95)),
                }
                summary["autocorr_lag1"] = float(
                    prob_mod.autocorrelation(
                        arr.tolist(), 1)[1]
                    if len(arr) > 1 else 0.0)
            self._show(summary)
        except Exception as e:
            log_exc(e, module="BayesianTab._on_mcmc_done")

    # ==================================================================
    # Monte Carlo
    # ==================================================================

    def _build_monte_carlo(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.mc2_kind = QComboBox()
        self.mc2_kind.addItem("估算 π", "pi")
        self.mc2_kind.addItem("1D 积分", "integrate")
        self.mc2_kind.currentIndexChanged.connect(
            self._update_mc2_visible)

        self.mc2_expr = QLineEdit("exp(-x^2)")
        self.mc2_a = QLineEdit("-1")
        self.mc2_b = QLineEdit("1")
        self.mc2_n = QSpinBox()
        self.mc2_n.setRange(100, 10 ** 8)
        self.mc2_n.setValue(1_000_000)

        self._expr_row = QWidget()
        ef = QFormLayout(self._expr_row)
        ef.setContentsMargins(0, 0, 0, 0)
        ef.addRow(QLabel("f(x)"), self.mc2_expr)
        ef.addRow(QLabel("a"), self.mc2_a)
        ef.addRow(QLabel("b"), self.mc2_b)

        b_run = QPushButton("运行")
        b_run.clicked.connect(self._do_mc2)

        f = QFormLayout()
        f.addRow(QLabel("类型"), self.mc2_kind)
        f.addRow(self._expr_row)
        f.addRow(QLabel("采样数"), self.mc2_n)
        f.addRow(b_run)
        v.addLayout(f)
        v.addStretch(1)
        self._update_mc2_visible()
        return w

    def _update_mc2_visible(self):
        k = self.mc2_kind.currentData()
        self._expr_row.setVisible(k == "integrate")

    def _do_mc2(self):
        k = self.mc2_kind.currentData()
        try:
            if k == "pi":
                r = prob_mod.estimate_pi(self.mc2_n.value())
            else:
                from core import engine
                expr = self.mc2_expr.text().strip()
                a = float(self.mc2_a.text())
                b = float(self.mc2_b.text())

                def f(x):
                    return float(engine.sci_eval(
                        expr.replace("x", f"({x})")))
                r = prob_mod.integrate_1d(
                    f, a, b, self.mc2_n.value())
            self._show(r)
        except Exception as e:
            self._show_err(e)

    # ==================================================================
    # 通用
    # ==================================================================

    def _show(self, r):
        try:
            if isinstance(r, dict):
                text = json.dumps(r, ensure_ascii=False,
                                  indent=2, default=str)
            else:
                text = str(r)
            self.result.setPlainText(text)
            if self.history is not None:
                try:
                    self.history.add(
                        "probability-bayes", "op",
                        text[:500])
                except Exception:
                    pass
            self.status.setText("✓ 完成")
        except Exception as e:
            log_exc(e, module="BayesianTab._show")

    def _show_err(self, e):
        self.result.setPlainText(f"✗ {e}")
        self.status.setText(f"✗ {e}")

    def _set_busy(self, busy: bool):
        self.progress.setVisible(busy)
        if busy:
            self.progress.setValue(0)

    def _on_progress(self, done: int, total: int):
        if total > 0:
            pct = min(100, int(done / total * 100))
            self.progress.setValue(pct)

    def _on_failed(self, msg: str):
        self._show_err(msg)

    def _on_finished(self):
        self._set_busy(False)
        try:
            self._mcmc_stop.setEnabled(False)
        except Exception:
            pass
        self._worker = None

    def _cancel(self):
        if self._worker is not None:
            self._worker.cancel()

    def closeEvent(self, e):
        try:
            if self._worker is not None and self._worker.isRunning():
                self._worker.cancel()
                self._worker.wait(2000)
        except Exception:
            pass
        super().closeEvent(e)


__all__ = [
    "StatsPanel",
    "ProbabilityPanel",
    "BayesianTab",
    "RandomPanel",
    "DataTablePanel",
    "DataOpsPanel",
]