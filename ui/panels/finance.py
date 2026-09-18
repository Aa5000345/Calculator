"""财务面板：贷款 / 复利 / NPV-IRR / 等额本金 / TVM / 折旧 /
债券 / 期权 / 个税 / XIRR。

变更历史：
- 第 1 轮：
  - bond_ytm 不再用面值当市场价，新增 Market Price 输入框
  - 去掉文件头尾重复的 friendly_error import
"""
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
from ._common import friendly_error, InlinePreviewBar
from .base import CalcPanel


class FinancePanel(CalcPanel):
    module_key = "finance"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["期", "还款", "本金", "利息", "余额"])
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self.table.setFixedHeight(180)

        tabs = QTabWidget()
        tabs.addTab(self._build_loan_tab(),
                    i18n.t("loan", "Loan"))
        tabs.addTab(self._build_compound_tab(),
                    i18n.t("compound_calc", "Compound"))
        tabs.addTab(self._build_npv_tab(), "NPV / IRR")
        tabs.addTab(self._build_compare_tab(),
                    i18n.t("compare_plans", "Compare"))
        tabs.addTab(self._build_tvm_tab(), "TVM")
        tabs.addTab(self._build_depr_tab(),
                    i18n.t("depreciation", "Depreciation"))
        tabs.addTab(self._build_bond_tab(),
                    i18n.t("bond", "债券"))
        tabs.addTab(self._build_option_tab(),
                    i18n.t("option", "期权"))
        tabs.addTab(self._build_tax_tab(),
                    i18n.t("tax", "个税"))
        tabs.addTab(self._build_xirr_tab(), "XIRR")

        main = QVBoxLayout(self)
        main.addWidget(tabs)
        main.addWidget(self.table)
        main.addWidget(self.result, 1)

    # ==================================================================
    # 贷款
    # ==================================================================

    def _build_loan_tab(self):
        self.p = QLineEdit("100000")
        self.primary_input = self.p
        self.rate = QLineEdit("4.9")
        self.years = QLineEdit("30")
        self.loan_kind = QComboBox()
        self.loan_kind.addItem(
            self.i18n.t("equal_payment", "等额本息"),
            "equal_payment")
        self.loan_kind.addItem(
            self.i18n.t("equal_principal", "等额本金"),
            "equal_principal")
        b = QPushButton(self.i18n.t("calc"))
        b.clicked.connect(self.loan)

        self._loan_preview = InlinePreviewBar(
            calc_fn=self._preview_loan)
        self._loan_preview.attach(
            self.p, enabled_getter=lambda: True)
        self.rate.textChanged.connect(
            lambda _t: self._loan_preview.refresh(
                self.p.text()))
        self.years.textChanged.connect(
            lambda _t: self._loan_preview.refresh(
                self.p.text()))
        self.loan_kind.currentIndexChanged.connect(
            lambda _: self._loan_preview.refresh(
                self.p.text()))

        w = QWidget()
        form = QFormLayout(w)
        form.addRow(QLabel(self.i18n.t("principal")), self.p)
        form.addRow(QLabel(""), self._loan_preview)
        form.addRow(QLabel(self.i18n.t("annual_rate")),
                    self.rate)
        form.addRow(QLabel(self.i18n.t("years")), self.years)
        form.addRow(QLabel(self.i18n.t("loan_kind", "类型")),
                    self.loan_kind)
        form.addRow(b)
        return w

    def _preview_loan(self, _text):
        try:
            p = float(self.p.text())
            r_year = float(self.rate.text())
            n = int(float(self.years.text()) * 12)
            if p <= 0 or n <= 0 or r_year < 0:
                return None
            r = r_year / 100.0 / 12.0
            kind = self.loan_kind.currentData()
            if kind == "equal_principal":
                first = p / n + p * r
                last = p / n + (p / n) * r
                return (f"首月 ≈ {first:,.2f} / "
                        f"末月 ≈ {last:,.2f}")
            if r == 0:
                m = p / n
            else:
                m = (p * r * (1 + r) ** n
                     / ((1 + r) ** n - 1))
            return f"月供 ≈ {m:,.2f}"
        except Exception:
            return None

    def loan(self):
        try:
            info = fin.loan_schedule(
                float(self.p.text()),
                float(self.rate.text()),
                float(self.years.text()),
                self.loan_kind.currentData())
            sched = info.pop("schedule")
            s = json.dumps(info, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self._fill_schedule(sched)
            self.add_history(
                f"{self.p.text()},{self.rate.text()},"
                f"{self.years.text()}",
                s, module="finance-loan")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "finance"))

    def _fill_schedule(self, schedule, limit=360):
        self.table.setRowCount(0)
        for row in schedule[:limit]:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(
                r, 0, QTableWidgetItem(str(row["period"])))
            self.table.setItem(
                r, 1, QTableWidgetItem(str(row["payment"])))
            self.table.setItem(
                r, 2, QTableWidgetItem(str(row["principal"])))
            self.table.setItem(
                r, 3, QTableWidgetItem(str(row["interest"])))
            self.table.setItem(
                r, 4, QTableWidgetItem(str(row["remaining"])))

    # ==================================================================
    # 复利
    # ==================================================================

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
        form.addRow(QLabel(self.i18n.t("annual_rate")),
                    self.rate2)
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
                f"{self.p2.text()},{self.rate2.text()},"
                f"{self.years2.text()}",
                r, module="finance-compound")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "finance"))

    # ==================================================================
    # NPV / IRR
    # ==================================================================

    def _build_npv_tab(self):
        self.cashflows = QLineEdit("-1000,300,400,500,300")
        self.disc = QLineEdit("8")
        b_npv = QPushButton("NPV")
        b_npv.clicked.connect(self.do_npv)
        b_irr = QPushButton("IRR")
        b_irr.clicked.connect(self.do_irr)

        w = QWidget()
        form = QFormLayout(w)
        form.addRow(QLabel(self.i18n.t("cashflows")),
                    self.cashflows)
        form.addRow(QLabel(self.i18n.t("discount_rate")),
                    self.disc)
        row = QHBoxLayout()
        row.addWidget(b_npv)
        row.addWidget(b_irr)
        form.addRow(row)
        return w

    def _parse_cf(self):
        return [float(x) for x in
                re.split(r"[\s,;]+", self.cashflows.text())
                if x]

    def do_npv(self):
        try:
            r = fin.npv(float(self.disc.text()),
                        self._parse_cf())
            s = json.dumps({"NPV": r}, ensure_ascii=False,
                           indent=2)
            self.result.setPlainText(s)
            self.add_history(self.cashflows.text(), s,
                             module="finance-npv")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "finance"))

    def do_irr(self):
        try:
            roots = fin.irr_all(self._parse_cf())
            if not roots:
                self.result.setPlainText(
                    self.i18n.t("no_solution", "No solution"))
                return
            note = (self.i18n.t(
                "irr_multiple", "Multiple IRRs detected")
                if len(roots) > 1 else "")
            s = json.dumps({"IRR(%)": roots, "note": note},
                           ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history(self.cashflows.text(), s,
                             module="finance-irr")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "finance"))

    # ==================================================================
    # 对比
    # ==================================================================

    def _build_compare_tab(self):
        self.cmp_p = QLineEdit("100000")
        self.cmp_rate = QLineEdit("4.9")
        self.cmp_years = QLineEdit("30")
        b = QPushButton(
            self.i18n.t("compare_plans", "Compare"))
        b.clicked.connect(self.compare)

        w = QWidget()
        form = QFormLayout(w)
        form.addRow(QLabel(self.i18n.t("principal")),
                    self.cmp_p)
        form.addRow(QLabel(self.i18n.t("annual_rate")),
                    self.cmp_rate)
        form.addRow(QLabel(self.i18n.t("years")),
                    self.cmp_years)
        form.addRow(b)
        return w

    def compare(self):
        try:
            r = fin.compare_plans(
                float(self.cmp_p.text()),
                float(self.cmp_rate.text()),
                float(self.cmp_years.text()))
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history("compare", s,
                             module="finance-compare")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "finance"))

    # ==================================================================
    # TVM
    # ==================================================================

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
                rate=_maybe(self.tvm_rate),
                nper=_maybe(self.tvm_nper),
                pmt=_maybe(self.tvm_pmt),
                kind=self.tvm_kind.currentData())
            s = json.dumps({"result": r},
                           ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history("tvm", s, module="finance-tvm")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "finance"))

    # ==================================================================
    # 折旧
    # ==================================================================

    def _build_depr_tab(self):
        self.d_cost = QLineEdit("100000")
        self.d_salvage = QLineEdit("10000")
        self.d_life = QLineEdit("5")
        self.d_method = QComboBox()
        for k, lbl in [("straight", "直线法"),
                       ("sum_of_years", "年数总和法"),
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
                float(self.d_cost.text()),
                float(self.d_salvage.text()),
                int(self.d_life.text()),
                self.d_method.currentData(),
                float(self.d_factor.text()),
                int(year) if year else None)
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            sched = r.get("schedule", [])
            self.table.setRowCount(0)
            for row in sched:
                i = self.table.rowCount()
                self.table.insertRow(i)
                self.table.setItem(
                    i, 0,
                    QTableWidgetItem(str(row["year"])))
                self.table.setItem(
                    i, 1,
                    QTableWidgetItem(
                        str(row["depreciation"])))
                self.table.setItem(
                    i, 2,
                    QTableWidgetItem(
                        str(row["book_value"])))
            self.add_history("depr", s,
                             module="finance-depr")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "finance"))

    # ==================================================================
    # 债券（第 1 轮修复）
    # ==================================================================

    def _build_bond_tab(self):
        self.b_face = QLineEdit("1000")
        self.b_coupon = QLineEdit("5")
        self.b_years = QLineEdit("10")
        self.b_ytm = QLineEdit("4")
        # 第 1 轮新增：市场价输入框
        self.b_price = QLineEdit("1080")
        self.b_freq = QLineEdit("2")
        b1 = QPushButton(self.i18n.t("calc", "计算价格"))
        b2 = QPushButton(
            self.i18n.t("calc_ytm", "由价格求 YTM"))
        b1.clicked.connect(self.bond_price)
        b2.clicked.connect(self.bond_ytm)

        w = QWidget()
        f = QFormLayout(w)
        f.addRow(QLabel("Face"), self.b_face)
        f.addRow(QLabel("Coupon %"), self.b_coupon)
        f.addRow(QLabel("Years"), self.b_years)
        f.addRow(QLabel("YTM %"), self.b_ytm)
        f.addRow(QLabel("Market Price"), self.b_price)
        f.addRow(QLabel("Freq"), self.b_freq)
        r = QHBoxLayout()
        r.addWidget(b1)
        r.addWidget(b2)
        f.addRow(r)
        return w

    def bond_price(self):
        try:
            from core import bonds
            r = bonds.bond_price(
                self.b_face.text(), self.b_coupon.text(),
                self.b_years.text(), self.b_ytm.text(),
                int(self.b_freq.text() or "1"))
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history("bond-price", s,
                             module="finance-bond")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "finance"))

    def bond_ytm(self):
        """由市场价格反求 YTM。

        修复：不再用面值当价格；改用 b_price 输入框。
        """
        try:
            from core import bonds
            price_text = self.b_price.text().strip()
            if not price_text:
                self.result.setPlainText(
                    "请填写 Market Price 输入框")
                return
            r = bonds.bond_ytm(
                self.b_face.text(), self.b_coupon.text(),
                self.b_years.text(), price_text,
                int(self.b_freq.text() or "1"))
            self.result.setPlainText(f"YTM = {r:.4f}%")
            self.add_history(
                f"ytm:{price_text}", f"{r:.4f}%",
                module="finance-bond")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "finance"))

    # ==================================================================
    # 期权
    # ==================================================================

    def _build_option_tab(self):
        self.o_s = QLineEdit("100")
        self.o_k = QLineEdit("100")
        self.o_t = QLineEdit("1")
        self.o_r = QLineEdit("5")
        self.o_sigma = QLineEdit("20")
        self.o_kind = QComboBox()
        self.o_kind.addItem("call", "call")
        self.o_kind.addItem("put", "put")
        b = QPushButton(self.i18n.t("calc", "计算"))
        b.clicked.connect(self.option_calc)

        w = QWidget()
        f = QFormLayout(w)
        f.addRow(QLabel("Spot"), self.o_s)
        f.addRow(QLabel("Strike"), self.o_k)
        f.addRow(QLabel("T (years)"), self.o_t)
        f.addRow(QLabel("r %"), self.o_r)
        f.addRow(QLabel("sigma %"), self.o_sigma)
        f.addRow(QLabel("Kind"), self.o_kind)
        f.addRow(b)
        return w

    def option_calc(self):
        try:
            from core import options
            r = options.black_scholes(
                self.o_s.text(), self.o_k.text(),
                self.o_t.text(), self.o_r.text(),
                self.o_sigma.text(),
                self.o_kind.currentData())
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history("bs", s,
                             module="finance-option")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "finance"))

    # ==================================================================
    # 个税
    # ==================================================================

    def _build_tax_tab(self):
        self.t_country = QComboBox()
        self.t_country.addItem("中国", "CN")
        self.t_country.addItem("美国 (单身)", "US-single")
        self.t_country.addItem("美国 (已婚)", "US-married")
        self.t_salary = QLineEdit("20000")
        self.t_si = QLineEdit("3000")
        self.t_sd = QLineEdit("1000")
        self.t_months = QLineEdit("1")
        b = QPushButton(self.i18n.t("calc", "计算"))
        b.clicked.connect(self.tax_calc)

        w = QWidget()
        f = QFormLayout(w)
        f.addRow(QLabel("Country"), self.t_country)
        f.addRow(QLabel("月薪 / 年薪"), self.t_salary)
        f.addRow(QLabel("三险一金 / 扣除"), self.t_si)
        f.addRow(QLabel("专项附加 / 已工作月"), self.t_sd)
        f.addRow(QLabel("月数"), self.t_months)
        f.addRow(b)
        return w

    def tax_calc(self):
        try:
            from core import tax
            c = self.t_country.currentData()
            if c == "CN":
                r = tax.cn_income_tax(
                    self.t_salary.text(), self.t_si.text(),
                    self.t_sd.text(),
                    int(self.t_months.text() or "1"))
            else:
                r = tax.us_federal_tax(
                    self.t_salary.text(),
                    filing=("married"
                            if "married" in c else "single"))
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history(c, s, module="finance-tax")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "finance"))

    # ==================================================================
    # XIRR
    # ==================================================================

    def _build_xirr_tab(self):
        self.x_cfs = QLineEdit("-1000, 200, 300, 500, 400")
        self.x_dates = QLineEdit(
            "2024-01-01, 2024-06-01, 2024-12-01, "
            "2025-06-01, 2025-12-01")
        b = QPushButton("XIRR")
        b.clicked.connect(self.xirr_calc)

        w = QWidget()
        f = QFormLayout(w)
        f.addRow(QLabel("Cashflows"), self.x_cfs)
        f.addRow(QLabel("Dates (ISO)"), self.x_dates)
        f.addRow(b)
        return w

    def xirr_calc(self):
        try:
            cfs = [float(x)
                   for x in self.x_cfs.text().split(",")]
            dates = [d.strip()
                     for d in self.x_dates.text().split(",")]
            r = fin.xirr(cfs, dates)
            self.result.setPlainText(f"XIRR = {r:.4f}%")
            self.add_history("xirr", f"{r:.4f}%",
                             module="finance-xirr")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "finance"))


__all__ = ["FinancePanel"]