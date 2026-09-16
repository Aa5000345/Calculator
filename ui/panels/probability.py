"""概率分布 / 假设检验 / 回归面板：新增 PDF/CDF/直方图绘图。"""
from __future__ import annotations

import json
import re

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QFormLayout, QComboBox, QTabWidget, QWidget,
)

from core import probability as prob
from core.logger import log_exc
from ._common import ResultView
from .base import CalcPanel
from ._common import ResultView, InlinePreviewBar


class ProbabilityPanel(CalcPanel):
    module_key = "probability"

    INT_KEYS = {"df", "dfn", "dfd", "n"}

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)
        self._last_sample = None
        self._fg = "#ffffff"
        self._bg = "#1e1e1e"
        self._panel = "#2d2d30"

        self.dist = QComboBox()
        for k in prob.DISTS.keys():
            self.dist.addItem(k, k)
        self.params = QLineEdit('{"loc":0,"scale":1}')
        self.x = QLineEdit("0")
        self.p = QLineEdit("0.95")
        self.n = QLineEdit("1000")
        self._dist_preview = InlinePreviewBar(calc_fn=self._preview_pdf)
        self._dist_preview.attach(self.x, enabled_getter=lambda: True)
        self.dist.currentIndexChanged.connect(
            lambda _: self._dist_preview.refresh(self.x.text()))
        self.params.editingFinished.connect(
            lambda: self._dist_preview.refresh(self.x.text()))

        self.plot_range = QLineEdit("-4, 4")
        self.plot_points = QLineEdit("300")

        self.data1 = QPlainTextEdit("1 2 3 4 5"); self.data1.setFixedHeight(56)
        self.data2 = QPlainTextEdit("2 3 4 5 6"); self.data2.setFixedHeight(56)
        self.mu0 = QLineEdit("0"); self.alpha = QLineEdit("0.05")
        self.test_kind = QComboBox()
        for k in ("ttest_1samp", "ttest_ind", "ttest_paired", "chi2", "anova"):
            self.test_kind.addItem(k, k)

        self.fit_data = QPlainTextEdit("2.1 1.9 2.3 2.0 1.8 2.2 2.1 2.0")
        self.fit_data.setFixedHeight(56)
        self.ci_data = QPlainTextEdit("2.1 1.9 2.3 2.0 1.8 2.2 2.1 2.0")
        self.ci_data.setFixedHeight(56)
        self.ci_sigma = QLineEdit("")

        self.mr_X = QPlainTextEdit("1 2\n2 1\n3 4\n4 3\n5 6")
        self.mr_X.setFixedHeight(80)
        self.mr_y = QPlainTextEdit("3 5 8 9 12"); self.mr_y.setFixedHeight(56)
        self.chi_table = QPlainTextEdit("10 20 30\n20 15 25")
        self.chi_table.setFixedHeight(70)

        self.figure = Figure(figsize=(6, 3.5))
        self.canvas = FigureCanvas(self.figure)

        self.result = ResultView(i18n)

        b_pdf = QPushButton("PDF / PMF"); b_pdf.clicked.connect(self.do_pdf)
        b_cdf = QPushButton("CDF"); b_cdf.clicked.connect(self.do_cdf)
        b_q = QPushButton("Quantile"); b_q.clicked.connect(self.do_q)
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

        b_plot_pdf = QPushButton(i18n.t("plot_pdf", "绘制 PDF"))
        b_plot_cdf = QPushButton(i18n.t("plot_cdf", "绘制 CDF"))
        b_plot_hist = QPushButton(i18n.t("plot_hist", "样本直方图"))
        b_plot_pdf.clicked.connect(self.plot_pdf)
        b_plot_cdf.clicked.connect(self.plot_cdf)
        b_plot_hist.clicked.connect(self.plot_hist)

        tabs = QTabWidget()

        w1 = QWidget(); f1 = QFormLayout(w1)
        f1.addRow(QLabel(i18n.t("prob_dist", "分布")), self.dist)
        f1.addRow(QLabel(i18n.t("prob_params", "参数 JSON")), self.params)
        f1.addRow(QLabel("x"), self.x)
        f1.addRow(QLabel(""), self._dist_preview)   # ← 预览条
        f1.addRow(QLabel("p"), self.p)
        f1.addRow(QLabel("n"), self.n)
        f1.addRow(QLabel(i18n.t("plot_range", "绘图范围")), self.plot_range)
        f1.addRow(QLabel(i18n.t("plot_points", "绘图点数")), self.plot_points)
        row = QHBoxLayout()
        for b in (b_pdf, b_cdf, b_q, b_s): row.addWidget(b)
        f1.addRow(row)
        row2 = QHBoxLayout()
        for b in (b_plot_pdf, b_plot_cdf, b_plot_hist): row2.addWidget(b)
        f1.addRow(row2)
        tabs.addTab(w1, i18n.t("prob", "分布"))

        w2 = QWidget(); f2 = QFormLayout(w2)
        f2.addRow(QLabel(i18n.t("prob_test_kind", "检验类型")), self.test_kind)
        f2.addRow(QLabel("data1"), self.data1)
        f2.addRow(QLabel("data2"), self.data2)
        f2.addRow(QLabel("μ₀"), self.mu0)
        f2.addRow(QLabel("α"), self.alpha)
        f2.addRow(QLabel("2D table (chi2)"), self.chi_table)
        f2.addRow(b_t)
        tabs.addTab(w2, i18n.t("prob_test", "检验"))

        w3 = QWidget(); f3 = QFormLayout(w3)
        f3.addRow(QLabel("X data"), self.data1)
        f3.addRow(QLabel("Y data"), self.data2)
        f3.addRow(b_r)
        f3.addRow(QLabel("X matrix (multi)"), self.mr_X)
        f3.addRow(QLabel("y (multi)"), self.mr_y)
        f3.addRow(b_mr)
        tabs.addTab(w3, i18n.t("prob_regress", "回归"))

        w4 = QWidget(); f4 = QFormLayout(w4)
        f4.addRow(QLabel("Data"), self.fit_data)
        f4.addRow(b_fit)
        f4.addRow(QLabel("Data"), self.ci_data)
        f4.addRow(QLabel("σ (optional)"), self.ci_sigma)
        f4.addRow(b_ci)
        tabs.addTab(w4, i18n.t("fit_ci", "拟合 / 区间"))

        w5 = QWidget(); v5 = QVBoxLayout(w5)
        v5.addWidget(self.canvas, 1)
        tabs.addTab(w5, i18n.t("chart", "图表"))

        main = QVBoxLayout(self)
        main.addWidget(tabs, 2)
        main.addWidget(self.result, 1)

    # ------------------------------------------------------------------
    # 参数 / 工具
    # ------------------------------------------------------------------

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
        s = json.dumps(obj, ensure_ascii=False, indent=2, default=str)
        self.result.show_result(s, "")
        self.add_history(self.dist.currentData(), s, module=tag)

    def _nums(self, w):
        return [float(x) for x in re.split(r"[\s,;]+", w.toPlainText()) if x]

    @staticmethod
    def _nums_line(line):
        return [float(x) for x in re.split(r"[\s,;]+", line) if x]

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

    # ------------------------------------------------------------------
    # 计算
    # ------------------------------------------------------------------


    def _preview_pdf(self, _text):
        """x 变化时实时预览 PDF / PMF 值。"""
        try:
            name = self.dist.currentData()
            params = self._params()
            xv = float(self.x.text())
            v = prob.pdf_or_pmf(name, xv, params)
            # 展示用：保留 4 位有效数字
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
            v = prob.pdf_or_pmf(self.dist.currentData(),
                                float(self.x.text()), self._params())
            self._show({"pdf_or_pmf": v})
        except Exception as e:
            self.result.show_error(e)

    def do_cdf(self):
        try:
            v = prob.cdf(self.dist.currentData(),
                         float(self.x.text()), self._params())
            self._show({"cdf": v})
        except Exception as e:
            self.result.show_error(e)

    def do_q(self):
        try:
            v = prob.quantile(self.dist.currentData(),
                              float(self.p.text()), self._params())
            self._show({"quantile": v})
        except Exception as e:
            self.result.show_error(e)

    def do_sample(self):
        try:
            v = prob.sample(self.dist.currentData(),
                            self._params(), int(self.n.text()))
            self._last_sample = v
            self._show({"sample": v})
        except Exception as e:
            self.result.show_error(e)

    def do_test(self):
        try:
            k = self.test_kind.currentData()
            if k == "ttest_1samp":
                r = prob.ttest_1samp(self._nums(self.data1),
                                     float(self.mu0.text()),
                                     float(self.alpha.text()))
            elif k == "ttest_ind":
                r = prob.ttest_ind(self._nums(self.data1),
                                   self._nums(self.data2),
                                   float(self.alpha.text()))
            elif k == "ttest_paired":
                a = self._nums(self.data1); b = self._nums(self.data2)
                from scipy import stats as st
                t, p = st.ttest_rel(a, b)
                r = {"t": float(t), "p": float(p),
                     "reject_H0": bool(p < float(self.alpha.text()))}
            elif k == "chi2":
                r = prob.chi2_independence(
                    [self._nums_line(ln) for ln in
                     self.chi_table.toPlainText().splitlines() if ln.strip()])
            elif k == "anova":
                r = prob.anova_oneway(self._nums(self.data1),
                                      self._nums(self.data2))
            else:
                return
            self._show(r, tag="prob-test")
        except Exception as e:
            self.result.show_error(e)

    def do_regress(self):
        try:
            r = prob.linear_regression(self._nums(self.data1),
                                       self._nums(self.data2))
            self._show(r, tag="prob-regress")
        except Exception as e:
            self.result.show_error(e)

    def do_fit(self):
        try:
            data = self._nums(self.fit_data)
            r = prob.fit_distribution(self.dist.currentData(), data)
            self._show(r, tag="prob-fit")
        except Exception as e:
            self.result.show_error(e)

    def do_ci(self):
        try:
            data = self._nums(self.ci_data)
            sigma = self.ci_sigma.text().strip()
            r = prob.confidence_interval_mean(
                data, float(self.alpha.text()),
                float(sigma) if sigma else None)
            self._show(r, tag="prob-ci")
        except Exception as e:
            self.result.show_error(e)

    def do_multi_reg(self):
        try:
            X = []
            for line in self.mr_X.toPlainText().splitlines():
                if line.strip():
                    X.append([float(x) for x in
                              re.split(r"[\s,;]+", line.strip()) if x])
            y = [float(x) for x in
                 re.split(r"[\s,;]+", self.mr_y.toPlainText()) if x]
            r = prob.multiple_regression(X, y)
            self._show(r, tag="prob-mr")
        except Exception as e:
            self.result.show_error(e)

    # ------------------------------------------------------------------
    # 绘图
    # ------------------------------------------------------------------

    def plot_pdf(self):
        try:
            name = self.dist.currentData()
            params = self._params()
            lo, hi = self._plot_range_vals()
            n = int(self.plot_points.text() or "300")
            fn = prob.DISTS[name][0]
            kw = self._build_kw(params)

            if name in ("binom", "poisson", "geom"):
                xi = np.arange(int(np.ceil(lo)), int(np.floor(hi)) + 1)
                ys = fn.pmf(xi, **kw)
                ax = self._prep_axes()
                ax.bar(xi, ys, color="#007acc", alpha=0.85)
                ax.set_ylabel("PMF", color=self._fg)
            else:
                xs = np.linspace(lo, hi, n)
                ys = fn.pdf(xs, **kw)
                ax = self._prep_axes()
                ax.plot(xs, ys, color="#007acc", linewidth=1.6)
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
            fn = prob.DISTS[name][0]
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