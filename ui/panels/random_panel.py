"""随机数面板。

变更历史：
- 第 23a 轮：修复 _build_* 方法中误用裸 i18n 的问题
"""
from __future__ import annotations

import json
import re

from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QFormLayout, QComboBox, QSpinBox, QCheckBox,
    QTabWidget, QWidget,
)

from core import random_ext as rand_mod
from ._common import friendly_error
from .base import CalcPanel


class RandomPanel(CalcPanel):
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
            QLabel(self.i18n.t("seed", "Seed")),
            self.seed)
        self.d_form.addRow(
            QLabel(self.i18n.t("count", "Count")),
            self.d_n)
        self._d_rows = {}
        self._add_d_row("uniform_lo", QLabel("low"), self.p_low)
        self._add_d_row("uniform_hi", QLabel("high"), self.p_high)
        self._add_d_row("normal_mu", QLabel("μ"), self.p_mu)
        self._add_d_row("normal_sigma", QLabel("σ"), self.p_sigma)
        self._add_d_row("exp_lambda", QLabel("λ"), self.p_lambda)
        self._add_d_row("int_lo", QLabel("int low"), self.p_i_low)
        self._add_d_row("int_hi", QLabel("int high"), self.p_i_high)
        self._add_d_row("choice_pool", QLabel("候选池"), self.p_pool)

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
            r = rand_mod.distribution_sample(
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
        self.sh_items = QPlainTextEdit("1,2,3,4,5,6,7,8,9,10")
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
            r = rand_mod.shuffle_list(
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
            r = rand_mod.sample_from_list(
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
            r = rand_mod.uuid_list(
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
                out.append(rand_mod.password_gen(
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


__all__ = ["RandomPanel"]