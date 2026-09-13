"""财务面板：贷款 / 复利 / NPV-IRR / 等额本金 / TVM / 折旧。"""
from __future__ import annotations

import json
import re

from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QFormLayout, QComboBox, QTabWidget, QWidget,
    QTableWidget, QTableWidgetItem, QHeaderView,
)

from core import engine
from core import finance as fin
from ._common import friendly_error
from .base import CalcPanel


class FinancePanel(CalcPanel):
    module_key = "finance"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["期", "还款", "本金", "利息", "余额"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setFixedHeight(180)

        tabs = QTabWidget()
        tabs.addTab(self._build_loan_tab(), i18n.t("loan", "Loan"))
        tabs.addTab(self._build_compound_tab(), i18n.t("compound_calc", "Compound"))
        tabs.addTab(self._build_npv_tab(), "NPV / IRR")
        tabs.addTab(self._build_compare_tab(), i18n.t("compare_plans", "Compare"))
        tabs.addTab(self._build_tvm_tab(), "TVM")
        tabs.addTab(self._build_depr_tab(), i18n.t("depreciation", "Depreciation"))

        main = QVBoxLayout(self)
        main.addWidget(tabs)
        main.addWidget(self.table)
        main.addWidget(self.result, 1)

    # ---------------- 贷款 ----------------

    def _build_loan_tab(self):
        self.p = QLineEdit("100000")
        self.rate = QLineEdit("4.9")
        self.years = QLineEdit("30")
        self.loan_kind = QComboBox()
        self.loan_kind.addItem(self.i18n.t("equal_payment", "等额本息"), "equal_payment")
        self.loan_kind.addItem(self.i18n.t("equal_principal", "等额本金"), "equal_principal")
        b = QPushButton(self.i18n.t("calc"))
        b.clicked.connect(self.loan)

        w = QWidget()
        form = QFormLayout(w)
        form.addRow(QLabel(self.i18n.t("principal")), self.p)
        form.addRow(QLabel(self.i18n.t("annual_rate")), self.rate)
        form.addRow(QLabel(self.i18n.t("years")), self.years)
        form.addRow(QLabel(self.i18n.t("loan_kind", "类型")), self.loan_kind)
        form.addRow(b)
        return w

    def loan(self):
        try:
            info = fin.loan_schedule(
                float(self.p.text()), float(self.rate.text()),
                float(self.years.text()), self.loan_kind.currentData())
            sched = info.pop("schedule")
            s = json.dumps(info, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self._fill_schedule(sched)
            self.add_history(
                f"{self.p.text()},{self.rate.text()},{self.years.text()}",
                s, module="finance-loan")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "finance"))

    def _fill_schedule(self, schedule, limit=360):
        self.table.setRowCount(0)
        for row in schedule[:limit]:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(row["period"])))
            self.table.setItem(r, 1, QTableWidgetItem(str(row["payment"])))
            self.table.setItem(r, 2, QTableWidgetItem(str(row["principal"])))
            self.table.setItem(r, 3, QTableWidgetItem(str(row["interest"])))
            self.table.setItem(r, 4, QTableWidgetItem(str(row["remaining"])))

    # ---------------- 复利 ----------------

    def _build_compound_tab(self):
        self.p2 = QLineEdit("10000")
        self.rate2 = QLineEdit("5")
        self.years2 = QLineEdit("10")
        self.times = QLineEdit("1")
        b = QPushButton(self.i18n.t("calc"))
        b.clicked.connect(self.compound)

        w = QWidget()
        form = QFormLayout(w)
        form.addRow(QLabel(self.i18n.t("principal")), self.p2)
        form.addRow(QLabel(self.i18n.t("annual_rate")), self.rate2)
        form.addRow(QLabel(self.i18n.t("years")), self.years2)
        form.addRow(QLabel(self.i18n.t("times")), self.times)
        form.addRow(b)
        return w

    def compound(self):
        try:
            r = engine.finance_compound(
                self.p2.text(), self.rate2.text(),
                self.years2.text(), self.times.text())
            self.result.setPlainText(str(r))
            self.add_history(
                f"{self.p2.text()},{self.rate2.text()},{self.years2.text()}",
                r, module="finance-compound")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "finance"))

    # ---------------- NPV / IRR ----------------

    def _build_npv_tab(self):
        self.cashflows = QLineEdit("-1000,300,400,500,300")
        self.disc = QLineEdit("8")
        b_npv = QPushButton("NPV"); b_npv.clicked.connect(self.do_npv)
        b_irr = QPushButton("IRR"); b_irr.clicked.connect(self.do_irr)

        w = QWidget()
        form = QFormLayout(w)
        form.addRow(QLabel(self.i18n.t("cashflows")), self.cashflows)
        form.addRow(QLabel(self.i18n.t("discount_rate")), self.disc)
        row = QHBoxLayout()
        row.addWidget(b_npv); row.addWidget(b_irr)
        form.addRow(row)
        return w

    def _parse_cf(self):
        return [float(x) for x in re.split(r"[\s,;]+", self.cashflows.text()) if x]

    def do_npv(self):
        try:
            r = fin.npv(float(self.disc.text()), self._parse_cf())
            s = json.dumps({"NPV": r}, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history(self.cashflows.text(), s, module="finance-npv")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "finance"))

    def do_irr(self):
        try:
            roots = fin.irr_all(self._parse_cf())
            if not roots:
                self.result.setPlainText(self.i18n.t("no_solution", "No solution"))
                return
            note = (self.i18n.t("irr_multiple", "Multiple IRRs detected")
                    if len(roots) > 1 else "")
            s = json.dumps({"IRR(%)": roots, "note": note},
                           ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history(self.cashflows.text(), s, module="finance-irr")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "finance"))

    # ---------------- 对比 ----------------

    def _build_compare_tab(self):
        self.cmp_p = QLineEdit("100000")
        self.cmp_rate = QLineEdit("4.9")
        self.cmp_years = QLineEdit("30")
        b = QPushButton(self.i18n.t("compare_plans", "Compare"))
        b.clicked.connect(self.compare)

        w = QWidget()
        form = QFormLayout(w)
        form.addRow(QLabel(self.i18n.t("principal")), self.cmp_p)
        form.addRow(QLabel(self.i18n.t("annual_rate")), self.cmp_rate)
        form.addRow(QLabel(self.i18n.t("years")), self.cmp_years)
        form.addRow(b)
        return w

    def compare(self):
        try:
            r = fin.compare_plans(
                float(self.cmp_p.text()), float(self.cmp_rate.text()),
                float(self.cmp_years.text()))
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history("compare", s, module="finance-compare")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "finance"))

    # ---------------- TVM ----------------

    def _build_tvm_tab(self):
        self.tvm_pv = QLineEdit("-100000")
        self.tvm_fv = QLineEdit("")
        self.tvm_rate = QLineEdit("5")
        self.tvm_nper = QLineEdit("10")
        self.tvm_pmt = QLineEdit("")
        self.tvm_kind = QComboBox()
        self.tvm_kind.addItem("期末", "end")
        self.tvm_kind.addItem("期初", "begin")
        b = QPushButton(self.i18n.t("calc"))
        b.clicked.connect(self.tvm_calc)

        w = QWidget()
        form = QFormLayout(w)
        form.addRow(QLabel("PV"), self.tvm_pv)
        form.addRow(QLabel("FV"), self.tvm_fv)
        form.addRow(QLabel("Rate %"), self.tvm_rate)
        form.addRow(QLabel("Nper"), self.tvm_nper)
        form.addRow(QLabel("PMT"), self.tvm_pmt)
        form.addRow(QLabel("Kind"), self.tvm_kind)
        form.addRow(b)
        return w

    def tvm_calc(self):
        def _maybe(x):
            s = x.text().strip()
            return float(s) if s else None
        try:
            r = fin.tvm(
                pv=_maybe(self.tvm_pv), fv=_maybe(self.tvm_fv),
                rate=_maybe(self.tvm_rate), nper=_maybe(self.tvm_nper),
                pmt=_maybe(self.tvm_pmt), kind=self.tvm_kind.currentData())
            s = json.dumps({"result": r}, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history("tvm", s, module="finance-tvm")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "finance"))

    # ---------------- 折旧 ----------------

    def _build_depr_tab(self):
        self.d_cost = QLineEdit("100000")
        self.d_salvage = QLineEdit("10000")
        self.d_life = QLineEdit("5")
        self.d_method = QComboBox()
        for k, lbl in [("straight", "直线法"), ("sum_of_years", "年数总和法"),
                       ("double_declining", "双倍余额递减法")]:
            self.d_method.addItem(lbl, k)
        self.d_factor = QLineEdit("2.0")
        self.d_year = QLineEdit("")
        b = QPushButton(self.i18n.t("calc"))
        b.clicked.connect(self.depr_calc)

        w = QWidget()
        form = QFormLayout(w)
        form.addRow(QLabel("Cost"), self.d_cost)
        form.addRow(QLabel("Salvage"), self.d_salvage)
        form.addRow(QLabel("Life (years)"), self.d_life)
        form.addRow(QLabel("Method"), self.d_method)
        form.addRow(QLabel("Factor"), self.d_factor)
        form.addRow(QLabel("Year"), self.d_year)
        form.addRow(b)
        return w

    def depr_calc(self):
        try:
            year = self.d_year.text().strip() or None
            r = fin.depreciation(
                float(self.d_cost.text()), float(self.d_salvage.text()),
                int(self.d_life.text()), self.d_method.currentData(),
                float(self.d_factor.text()),
                int(year) if year else None)
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            sched = r.get("schedule", [])
            self.table.setRowCount(0)
            for row in sched:
                i = self.table.rowCount()
                self.table.insertRow(i)
                self.table.setItem(i, 0, QTableWidgetItem(str(row["year"])))
                self.table.setItem(i, 1, QTableWidgetItem(str(row["depreciation"])))
                self.table.setItem(i, 2, QTableWidgetItem(str(row["book_value"])))
            self.add_history("depr", s, module="finance-depr")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "finance"))