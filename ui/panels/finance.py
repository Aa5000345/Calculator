"""财务 / 日期面板。

合并自：ui/panels/finance.py + ui/panels/date.py

对外接口（类名保持不变，老 registry.py 无需改动）：
    FinancePanel
    DatePanel

依赖（合并后）：
    core.base     —— InputError / log_exc
    core.engine   —— finance_loan / finance_compound / format_result
    core.finance  —— 所有 NPV/IRR/XIRR/贷款/TVM/折旧/债券/期权/个税
    core.dates    —— 所有日期 / 农历 / 日出日落
    ui.panels.base       —— CalcPanel
    ui.panels._common    —— ResultView / InlinePreviewBar /
                            friendly_error

修复记录（本轮）：
- FinancePanel：`from core import finance as fin`
  → 统一别名 `fin_mod`，与 `core.finance` 模块名区分；
  同时移除 `from core import tax / bonds / options` 三处独立导入
  （已合并到 `core.finance`）。
- DatePanel：`from core import dates as dtmod`
  → `from core import dates as dt_mod`；`from core import lunar`
  / `from core import astro` 改为 `dt_mod.solar_to_lunar` /
  `dt_mod.sun_times`。
"""
from __future__ import annotations

import json
import re

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGridLayout,
    QHeaderView, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QTabWidget,
    QVBoxLayout, QWidget,
)

from core import engine
from core import finance as fin_mod
from core import dates as dt_mod
from ._common import (
    friendly_error,
    InlinePreviewBar,
)
from .base import CalcPanel


__all__ = ["FinancePanel", "DatePanel"]


# ===========================================================================
# 财务
# ===========================================================================

class FinancePanel(CalcPanel):
    """财务面板。

    贷款 / 复利 / NPV-IRR / 等额本金 / TVM / 折旧 / 债券 / 期权 /
    个税 / XIRR。
    """

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
            info = fin_mod.loan_schedule(
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
            r = fin_mod.npv(float(self.disc.text()),
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
            roots = fin_mod.irr_all(self._parse_cf())
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
            r = fin_mod.compare_plans(
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
            r = fin_mod.tvm(
                pv=_maybe(self.tvm_pv),
                fv=_maybe(self.tvm_fv),
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
            r = fin_mod.depreciation(
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
    # 债券
    # ==================================================================

    def _build_bond_tab(self):
        self.b_face = QLineEdit("1000")
        self.b_coupon = QLineEdit("5")
        self.b_years = QLineEdit("10")
        self.b_ytm = QLineEdit("4")
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
            r = fin_mod.bond_price(
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
        """由市场价格反求 YTM。"""
        try:
            price_text = self.b_price.text().strip()
            if not price_text:
                self.result.setPlainText(
                    "请填写 Market Price 输入框")
                return
            r = fin_mod.bond_ytm(
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
            r = fin_mod.black_scholes(
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
            c = self.t_country.currentData()
            if c == "CN":
                r = fin_mod.cn_income_tax(
                    self.t_salary.text(), self.t_si.text(),
                    self.t_sd.text(),
                    int(self.t_months.text() or "1"))
            else:
                r = fin_mod.us_federal_tax(
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
        self.x_cfs = QLineEdit(
            "-1000, 200, 300, 500, 400")
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
            r = fin_mod.xirr(cfs, dates)
            self.result.setPlainText(f"XIRR = {r:.4f}%")
            self.add_history("xirr", f"{r:.4f}%",
                             module="finance-xirr")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "finance"))


# ===========================================================================
# 日期
# ===========================================================================

class DatePanel(CalcPanel):
    """日期面板：日期差 / 加天数 / 倒计时 / 周信息 / 时区 /
    时间戳 / 年龄 / 农历 / 日出日落。"""

    module_key = "date"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        # ---------------- 主表单 ----------------
        self.d1 = QLineEdit("2024-01-01")
        self.d2 = QLineEdit("2024-12-31")
        self.days = QLineEdit("30")
        self.country = QLineEdit("CN")
        self.exclude_holidays = QCheckBox(
            i18n.t("exclude_holidays", "Exclude holidays"))
        self.exclude_holidays.setChecked(True)

        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)

        # ---------------- 时区 / 时间戳 ----------------
        self.tz_from = QLineEdit("Asia/Shanghai")
        self.tz_to = QLineEdit("UTC")
        self.dt_str = QLineEdit("2024-01-01 12:00:00")
        self.ts = QLineEdit("1700000000")
        self.birth = QLineEdit("1990-01-01")
        self.as_of = QLineEdit("")

        # ---------------- 按钮 ----------------
        b_diff = QPushButton(i18n.t("diff"))
        b_diff.clicked.connect(self.diff)
        b_add = QPushButton(i18n.t("date_add"))
        b_add.clicked.connect(self.add)
        b_count = QPushButton(
            i18n.t("countdown", "Countdown"))
        b_count.clicked.connect(self.countdown)
        b_week = QPushButton(
            i18n.t("week_info", "Week info"))
        b_week.clicked.connect(self.week_info)
        b_tz = QPushButton(
            i18n.t("tz_convert", "TZ convert"))
        b_tz.clicked.connect(self.tz_convert)
        b_ts2d = QPushButton(
            i18n.t("ts_to_date", "TS→Date"))
        b_ts2d.clicked.connect(self.ts_to_date)
        b_d2ts = QPushButton(
            i18n.t("date_to_ts", "Date→TS"))
        b_d2ts.clicked.connect(self.date_to_ts)
        b_age = QPushButton(i18n.t("age", "Age"))
        b_age.clicked.connect(self.age)
        b_hol = QPushButton(
            i18n.t("holidays", "Holidays"))
        b_hol.clicked.connect(self.holidays)

        # ---------------- 主表单布局 ----------------
        form = QGridLayout()
        form.addWidget(QLabel(i18n.t("date1")), 0, 0)
        form.addWidget(self.d1, 0, 1)
        form.addWidget(QLabel(i18n.t("date2")), 1, 0)
        form.addWidget(self.d2, 1, 1)
        form.addWidget(QLabel(i18n.t("days")), 2, 0)
        form.addWidget(self.days, 2, 1)
        form.addWidget(QLabel("Country"), 3, 0)
        form.addWidget(self.country, 3, 1)
        form.addWidget(self.exclude_holidays, 4, 1)
        form.addWidget(QLabel("From TZ"), 5, 0)
        form.addWidget(self.tz_from, 5, 1)
        form.addWidget(QLabel("To TZ"), 6, 0)
        form.addWidget(self.tz_to, 6, 1)
        form.addWidget(QLabel("Datetime"), 7, 0)
        form.addWidget(self.dt_str, 7, 1)
        form.addWidget(
            QLabel(i18n.t("timestamp", "Timestamp")), 8, 0)
        form.addWidget(self.ts, 8, 1)
        form.addWidget(
            QLabel(i18n.t("birthday", "Birthday")), 9, 0)
        form.addWidget(self.birth, 9, 1)
        form.addWidget(
            QLabel(i18n.t("as_of", "As of")), 10, 0)
        form.addWidget(self.as_of, 10, 1)

        row1 = QHBoxLayout()
        for b in (b_diff, b_add, b_count):
            row1.addWidget(b)
        row2 = QHBoxLayout()
        for b in (b_week, b_tz, b_age):
            row2.addWidget(b)
        row3 = QHBoxLayout()
        for b in (b_ts2d, b_d2ts, b_hol):
            row3.addWidget(b)

        # ---------------- Tab ----------------
        self._extra_tabs = QTabWidget()
        w_main = QWidget()
        vm = QVBoxLayout(w_main)
        vm.addLayout(form)
        vm.addLayout(row1)
        vm.addLayout(row2)
        vm.addLayout(row3)
        vm.addWidget(self.result, 1)
        self._extra_tabs.addTab(
            w_main, i18n.t("date_calc", "日期"))
        self._extra_tabs.addTab(
            self._build_lunar_tab(),
            i18n.t("lunar", "农历"))
        self._extra_tabs.addTab(
            self._build_sun_tab(),
            i18n.t("sun", "日出日落"))

        main = QVBoxLayout(self)
        main.addWidget(self._extra_tabs, 1)

    # ==================================================================
    # 日期差
    # ==================================================================

    def diff(self):
        try:
            info = dt_mod.date_diff_info(
                self.d1.text(), self.d2.text(),
                self.country.text() or "CN",
                self.exclude_holidays.isChecked())
            msg = [
                f"{self.i18n.t('days')}: {info['abs_days']}",
                f"diff(raw): {info['days']}",
                f"weeks: {info['weeks']}w "
                f"{info['remaining_days']}d",
                f"{self.i18n.t('workdays', 'Workdays')}: "
                f"{info['workdays']}",
                f"{self.i18n.t('holidays_in_range', 'Holidays')}"
                f": {info['holidays_in_range']}",
            ]
            if info["cross_year"]:
                msg.append(
                    f"[{self.i18n.t('cross_year_hint', 'Cross-year')}]")
            if info["leap_in_range"]:
                msg.append(
                    f"[{self.i18n.t('leap_year_hint', 'Leap year')}]")
            s = "\n".join(msg)
            self.result.setPlainText(s)
            self.add_history(
                f"{self.d1.text()} → {self.d2.text()}", s,
                module="date-diff")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "date"))

    def add(self):
        try:
            r = dt_mod.add_days(
                self.d1.text(), self.days.text())
            self.result.setPlainText(r)
            self.add_history(
                f"{self.d1.text()} + {self.days.text()}", r,
                module="date-add")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "date"))

    def countdown(self):
        try:
            r = dt_mod.countdown(
                self.d2.text(), self.d1.text())
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history(
                self.d2.text(), s,
                module="date-countdown")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "date"))

    def week_info(self):
        try:
            info = dt_mod.date_info(self.d1.text())
            wr = dt_mod.week_range(self.d1.text())
            info["week_start"] = wr["start"]
            info["week_end"] = wr["end"]
            s = json.dumps(info, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history(
                self.d1.text(), s, module="date-week")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "date"))

    def tz_convert(self):
        try:
            r = dt_mod.timezone_convert(
                self.dt_str.text(),
                self.tz_from.text() or "UTC",
                self.tz_to.text() or "UTC")
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history(
                f"{self.dt_str.text()} "
                f"{self.tz_from.text()}→{self.tz_to.text()}",
                s, module="date-tz")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "date"))

    def ts_to_date(self):
        try:
            r = dt_mod.from_timestamp(
                self.ts.text(),
                self.tz_from.text() or "UTC")
            self.result.setPlainText(r)
            self.add_history(
                self.ts.text(), r,
                module="date-ts2date")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "date"))

    def date_to_ts(self):
        try:
            r = dt_mod.to_timestamp(
                self.d1.text(),
                self.tz_from.text() or "UTC")
            self.result.setPlainText(str(r))
            self.add_history(
                self.d1.text(), r,
                module="date-date2ts")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "date"))

    def age(self):
        try:
            r = dt_mod.age_precise(
                self.birth.text(),
                self.as_of.text() or None)
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history(
                self.birth.text(), s, module="date-age")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "date"))

    def holidays(self):
        try:
            year = dt_mod.parse_date(
                self.d1.text()).year
            r = dt_mod.country_holidays(
                self.country.text() or "CN", year)
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history(
                f"{self.country.text()}:{year}", s,
                module="date-holidays")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "date"))

    # ==================================================================
    # 农历 Tab
    # ==================================================================

    def _build_lunar_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.lunar_date = QLineEdit("2024-01-01")
        b = QPushButton(self.i18n.t("calc", "转换"))
        b.clicked.connect(self.lunar_convert)
        v.addWidget(QLabel("公历 (YYYY-MM-DD)"))
        v.addWidget(self.lunar_date)
        v.addWidget(b)
        v.addStretch(1)
        return w

    def lunar_convert(self):
        try:
            r = dt_mod.solar_to_lunar(
                self.lunar_date.text())
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history("lunar", s,
                             module="date-lunar")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "date"))

    # ==================================================================
    # 日出日落 Tab
    # ==================================================================

    def _build_sun_tab(self):
        w = QWidget()
        f = QFormLayout(w)
        self.sun_date = QLineEdit("2024-06-21")
        self.sun_lat = QLineEdit("39.9")
        self.sun_lon = QLineEdit("116.4")
        self.sun_tz = QLineEdit("Asia/Shanghai")
        b = QPushButton(self.i18n.t("calc", "计算"))
        b.clicked.connect(self.sun_calc)
        f.addRow(QLabel("Date"), self.sun_date)
        f.addRow(QLabel("Latitude"), self.sun_lat)
        f.addRow(QLabel("Longitude"), self.sun_lon)
        f.addRow(QLabel("Timezone"), self.sun_tz)
        f.addRow(b)
        return w

    def sun_calc(self):
        try:
            r = dt_mod.sun_times(
                self.sun_date.text(),
                self.sun_lat.text(),
                self.sun_lon.text(),
                self.sun_tz.text() or "UTC")
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history("sun", s, module="date-sun")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "date"))