"""贝叶斯 / MCMC / 蒙特卡洛 Tab。

被 ui/panels/probability.py 作为 Tab 使用：
    from ui.widgets.bayesian_tab import BayesianTab
    tabs.addTab(BayesianTab(settings, i18n, history),
                i18n.t("prob_bayes", "贝叶斯"))
"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from core import bayesian as bayes
from core import mcmc as mcmc_mod
from core import monte_carlo as mc
from core.logger import log_exc


class _Worker(QThread):
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
    """贝叶斯 / MCMC / 蒙特卡洛。"""

    def __init__(self, settings, i18n, history, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n
        self.history = history
        self._worker: _Worker | None = None

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
            r = bayes.beta_binomial(
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
            r = bayes.normal_normal(
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
            import re
            counts = [int(x) for x in
                      re.split(r"[\s,;]+", self.gp_counts.text())
                      if x]
            r = bayes.gamma_poisson(
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
        self.mc_kind.currentIndexChanged.connect(self._update_mcmc_hint)

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
            "bimodal": "log p(θ) = log(exp(-(θ-2)²/2) + exp(-(θ+2)²/2))",
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
            # 2D 相关正态，ρ=0.7
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

        self._worker = _Worker(
            mcmc_mod.metropolis_hastings,
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
            # 1D 时计算分位数
            trace = r.get("trace") or []
            if trace and r.get("n_dim") == 1:
                import numpy as np
                arr = np.asarray([t[0] for t in trace])
                summary["quantiles"] = {
                    "5%": float(np.quantile(arr, 0.05)),
                    "25%": float(np.quantile(arr, 0.25)),
                    "50%": float(np.quantile(arr, 0.5)),
                    "75%": float(np.quantile(arr, 0.75)),
                    "95%": float(np.quantile(arr, 0.95)),
                }
                summary["autocorr_lag1"] = float(
                    mcmc_mod.autocorrelation(arr.tolist(), 1)[1]
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
                r = mc.estimate_pi(self.mc2_n.value())
            else:
                # 构造 f(x)
                from core import engine
                expr = self.mc2_expr.text().strip()
                a = float(self.mc2_a.text())
                b = float(self.mc2_b.text())

                def f(x):
                    return float(engine.sci_eval(
                        expr.replace("x", f"({x})")))
                r = mc.integrate_1d(f, a, b, self.mc2_n.value())
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
                    self.history.add("probability-bayes", "op",
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