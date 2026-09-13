"""概率分布 / 假设检验 / 回归面板。"""
from __future__ import annotations

import json
import re

from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QFormLayout, QComboBox, QTabWidget, QWidget,
)

from core import probability as prob
from ._common import friendly_error
from .base import CalcPanel


class ProbabilityPanel(CalcPanel):
    module_key = "probability"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        self.dist = QComboBox()
        for k in prob.DISTS.keys():
            self.dist.addItem(k, k)
        self.params = QLineEdit('{"loc":0,"scale":1}')
        self.x = QLineEdit("0")
        self.p = QLineEdit("0.95")
        self.n = QLineEdit("1000")

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

        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)

        b_pdf = QPushButton("PDF / PMF"); b_pdf.clicked.connect(self.do_pdf)
        b_cdf = QPushButton("CDF"); b_cdf.clicked.connect(self.do_cdf)
        b_q = QPushButton("Quantile"); b_q.clicked.connect(self.do_q)
        b_s = QPushButton(i18n.t("prob_sample_btn", "Sample")); b_s.clicked.connect(self.do_sample)
        b_t = QPushButton(i18n.t("prob_test", "Run test")); b_t.clicked.connect(self.do_test)
        b_r = QPushButton(i18n.t("prob_regress", "Simple regression")); b_r.clicked.connect(self.do_regress)
        b_fit = QPushButton(i18n.t("fit", "Fit distribution")); b_fit.clicked.connect(self.do_fit)
        b_ci = QPushButton(i18n.t("ci", "Confidence interval")); b_ci.clicked.connect(self.do_ci)
        b_mr = QPushButton(i18n.t("multi_reg", "Multiple regression")); b_mr.clicked.connect(self.do_multi_reg)

        tabs = QTabWidget()

        w1 = QWidget(); f1 = QFormLayout(w1)
        f1.addRow(QLabel(i18n.t("prob_dist", "Distribution")), self.dist)
        f1.addRow(QLabel(i18n.t("prob_params", "Params JSON")), self.params)
        f1.addRow(QLabel("x"), self.x)
        f1.addRow(QLabel("p"), self.p)
        f1.addRow(QLabel("n"), self.n)
        row = QHBoxLayout()
        for b in (b_pdf, b_cdf, b_q, b_s): row.addWidget(b)
        f1.addRow(row)
        tabs.addTab(w1, i18n.t("prob", "Distribution"))

        w2 = QWidget(); f2 = QFormLayout(w2)
        f2.addRow(QLabel(i18n.t("prob_test_kind", "Test kind")), self.test_kind)
        f2.addRow(QLabel("data1"), self.data1)
        f2.addRow(QLabel("data2"), self.data2)
        f2.addRow(QLabel("μ₀"), self.mu0)
        f2.addRow(QLabel("α"), self.alpha)
        f2.addRow(QLabel("2D table (chi2 independence)"), self.chi_table)
        f2.addRow(b_t)
        tabs.addTab(w2, i18n.t("prob_test", "Test"))

        w3 = QWidget(); f3 = QFormLayout(w3)
        f3.addRow(QLabel("X data"), self.data1)
        f3.addRow(QLabel("Y data"), self.data2)
        f3.addRow(b_r)
        f3.addRow(QLabel("X matrix (multi)"), self.mr_X)
        f3.addRow(QLabel("y (multi)"), self.mr_y)
        f3.addRow(b_mr)
        tabs.addTab(w3, i18n.t("prob_regress", "Regression"))

        w4 = QWidget(); f4 = QFormLayout(w4)
        f4.addRow(QLabel("Data"), self.fit_data)
        f4.addRow(b_fit)
        f4.addRow(QLabel("Data"), self.ci_data)
        f4.addRow(QLabel("σ (optional)"), self.ci_sigma)
        f4.addRow(b_ci)
        tabs.addTab(w4, i18n.t("fit_ci", "Fit / CI"))

        main = QVBoxLayout(self)
        main.addWidget(tabs)
        main.addWidget(self.result, 1)

    def _params(self):
        s = self.params.text().strip() or "{}"
        return json.loads(s)

    def _show(self, obj, tag="prob"):
        s = json.dumps(obj, ensure_ascii=False, indent=2, default=str)
        self.result.setPlainText(s)
        self.add_history(self.dist.currentData(), s, module=tag)

    def do_pdf(self):
        try:
            v = prob.pdf_or_pmf(self.dist.currentData(),
                                float(self.x.text()), self._params())
            self._show({"pdf_or_pmf": v})
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "prob"))

    def do_cdf(self):
        try:
            v = prob.cdf(self.dist.currentData(),
                         float(self.x.text()), self._params())
            self._show({"cdf": v})
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "prob"))

    def do_q(self):
        try:
            v = prob.quantile(self.dist.currentData(),
                              float(self.p.text()), self._params())
            self._show({"quantile": v})
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "prob"))

    def do_sample(self):
        try:
            v = prob.sample(self.dist.currentData(),
                            self._params(), int(self.n.text()))
            self._show({"sample": v})
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "prob"))

    def _nums(self, w):
        return [float(x) for x in re.split(r"[\s,;]+", w.toPlainText()) if x]

    @staticmethod
    def _nums_line(line):
        return [float(x) for x in re.split(r"[\s,;]+", line) if x]

    def do_test(self):
        try:
            k = self.test_kind.currentData()
            if k == "ttest_1samp":
                r = prob.ttest_1samp(self._nums(self.data1),
                                     float(self.mu0.text()),
                                     float(self.alpha.text()))
            elif k == "ttest_ind":
                r = prob.ttest_ind(self._nums(self.data1), self._nums(self.data2),
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
                r = prob.anova_oneway(self._nums(self.data1), self._nums(self.data2))
            else:
                return
            self._show(r, tag="prob-test")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "prob"))

    def do_regress(self):
        try:
            r = prob.linear_regression(self._nums(self.data1),
                                       self._nums(self.data2))
            self._show(r, tag="prob-regress")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "prob"))

    def do_fit(self):
        try:
            data = self._nums(self.fit_data)
            r = prob.fit_distribution(self.dist.currentData(), data)
            self._show(r, tag="prob-fit")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "prob"))

    def do_ci(self):
        try:
            data = self._nums(self.ci_data)
            sigma = self.ci_sigma.text().strip()
            r = prob.confidence_interval_mean(
                data, float(self.alpha.text()),
                float(sigma) if sigma else None)
            self._show(r, tag="prob-ci")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "prob"))

    def do_multi_reg(self):
        try:
            X = []
            for line in self.mr_X.toPlainText().splitlines():
                if line.strip():
                    X.append([float(x) for x in
                              re.split(r"[\s,;]+", line.strip()) if x])
            y = [float(x) for x in re.split(r"[\s,;]+", self.mr_y.toPlainText()) if x]
            r = prob.multiple_regression(X, y)
            self._show(r, tag="prob-mr")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "prob"))