"""日期面板。"""
from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QGridLayout, QCheckBox,
)

from core import dates as dtmod
from ._common import friendly_error
from .base import CalcPanel
from PySide6.QtWidgets import QTabWidget


class DatePanel(CalcPanel):
    module_key = "date"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        self.d1 = QLineEdit("2024-01-01")
        self.d2 = QLineEdit("2024-12-31")
        self.days = QLineEdit("30")
        self.country = QLineEdit("CN")
        self.exclude_holidays = QCheckBox(
            self.i18n.t("exclude_holidays", "Exclude holidays"))
        self.exclude_holidays.setChecked(True)

        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)

        self.tz_from = QLineEdit("Asia/Shanghai")
        self.tz_to = QLineEdit("UTC")
        self.dt_str = QLineEdit("2024-01-01 12:00:00")
        self.ts = QLineEdit("1700000000")
        self.birth = QLineEdit("1990-01-01")
        self.as_of = QLineEdit("")

        b_diff = QPushButton(i18n.t("diff")); b_diff.clicked.connect(self.diff)
        b_add = QPushButton(i18n.t("add")); b_add.clicked.connect(self.add)
        b_count = QPushButton(i18n.t("countdown", "Countdown")); b_count.clicked.connect(self.countdown)
        b_week = QPushButton(i18n.t("week_info", "Week info")); b_week.clicked.connect(self.week_info)
        b_tz = QPushButton(i18n.t("tz_convert", "TZ convert")); b_tz.clicked.connect(self.tz_convert)
        b_ts2d = QPushButton(i18n.t("ts_to_date", "TS→Date")); b_ts2d.clicked.connect(self.ts_to_date)
        b_d2ts = QPushButton(i18n.t("date_to_ts", "Date→TS")); b_d2ts.clicked.connect(self.date_to_ts)
        b_age = QPushButton(i18n.t("age", "Age")); b_age.clicked.connect(self.age)
        b_hol = QPushButton(i18n.t("holidays", "Holidays")); b_hol.clicked.connect(self.holidays)

        form = QGridLayout()
        form.addWidget(QLabel(i18n.t("date1")), 0, 0); form.addWidget(self.d1, 0, 1)
        form.addWidget(QLabel(i18n.t("date2")), 1, 0); form.addWidget(self.d2, 1, 1)
        form.addWidget(QLabel(i18n.t("days")), 2, 0); form.addWidget(self.days, 2, 1)
        form.addWidget(QLabel("Country"), 3, 0); form.addWidget(self.country, 3, 1)
        form.addWidget(self.exclude_holidays, 4, 1)
        form.addWidget(QLabel("From TZ"), 5, 0); form.addWidget(self.tz_from, 5, 1)
        form.addWidget(QLabel("To TZ"), 6, 0); form.addWidget(self.tz_to, 6, 1)
        form.addWidget(QLabel("Datetime"), 7, 0); form.addWidget(self.dt_str, 7, 1)
        form.addWidget(QLabel(i18n.t("timestamp", "Timestamp")), 8, 0); form.addWidget(self.ts, 8, 1)
        form.addWidget(QLabel(i18n.t("birthday", "Birthday")), 9, 0); form.addWidget(self.birth, 9, 1)
        form.addWidget(QLabel(i18n.t("as_of", "As of")), 10, 0); form.addWidget(self.as_of, 10, 1)

        row1 = QHBoxLayout()
        for b in (b_diff, b_add, b_count): row1.addWidget(b)
        row2 = QHBoxLayout()
        for b in (b_week, b_tz, b_age): row2.addWidget(b)
        row3 = QHBoxLayout()
        for b in (b_ts2d, b_d2ts, b_hol): row3.addWidget(b)

        self._extra_tabs = QTabWidget()
        w_main = QWidget(); vm = QVBoxLayout(w_main)
        vm.addLayout(form)
        vm.addLayout(row1); vm.addLayout(row2); vm.addLayout(row3)
        vm.addWidget(self.result, 1)
        self._extra_tabs.addTab(w_main, i18n.t("date_calc", "日期"))
        self._extra_tabs.addTab(self._build_lunar_tab(), i18n.t("lunar", "农历"))
        self._extra_tabs.addTab(self._build_sun_tab(), i18n.t("sun", "日出日落"))

        main = QVBoxLayout(self)
        main.addWidget(self._extra_tabs, 1)

    def diff(self):
        try:
            info = dtmod.date_diff_info(
                self.d1.text(), self.d2.text(),
                self.country.text() or "CN",
                self.exclude_holidays.isChecked())
            msg = [
                f"{self.i18n.t('days')}: {info['abs_days']}",
                f"diff(raw): {info['days']}",
                f"weeks: {info['weeks']}w {info['remaining_days']}d",
                f"{self.i18n.t('workdays', 'Workdays')}: {info['workdays']}",
                f"{self.i18n.t('holidays_in_range', 'Holidays')}: "
                f"{info['holidays_in_range']}",
            ]
            if info["cross_year"]:
                msg.append(f"[{self.i18n.t('cross_year_hint', 'Cross-year')}]")
            if info["leap_in_range"]:
                msg.append(f"[{self.i18n.t('leap_year_hint', 'Leap year')}]")
            s = "\n".join(msg)
            self.result.setPlainText(s)
            self.add_history(f"{self.d1.text()} → {self.d2.text()}", s,
                             module="date-diff")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "date"))

    def add(self):
        try:
            r = dtmod.add_days(self.d1.text(), self.days.text())
            self.result.setPlainText(r)
            self.add_history(f"{self.d1.text()} + {self.days.text()}", r,
                             module="date-add")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "date"))

    def countdown(self):
        try:
            r = dtmod.countdown(self.d2.text(), self.d1.text())
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history(self.d2.text(), s, module="date-countdown")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "date"))

    def week_info(self):
        try:
            info = dtmod.date_info(self.d1.text())
            wr = dtmod.week_range(self.d1.text())
            info["week_start"] = wr["start"]; info["week_end"] = wr["end"]
            s = json.dumps(info, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history(self.d1.text(), s, module="date-week")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "date"))

    def tz_convert(self):
        try:
            r = dtmod.timezone_convert(
                self.dt_str.text(), self.tz_from.text() or "UTC",
                self.tz_to.text() or "UTC")
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history(
                f"{self.dt_str.text()} {self.tz_from.text()}→{self.tz_to.text()}",
                s, module="date-tz")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "date"))

    def ts_to_date(self):
        try:
            r = dtmod.from_timestamp(self.ts.text(), self.tz_from.text() or "UTC")
            self.result.setPlainText(r)
            self.add_history(self.ts.text(), r, module="date-ts2date")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "date"))

    def date_to_ts(self):
        try:
            r = dtmod.to_timestamp(self.d1.text(), self.tz_from.text() or "UTC")
            self.result.setPlainText(str(r))
            self.add_history(self.d1.text(), r, module="date-date2ts")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "date"))

    def age(self):
        try:
            r = dtmod.age_precise(self.birth.text(), self.as_of.text() or None)
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history(self.birth.text(), s, module="date-age")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "date"))

    def holidays(self):
        try:
            year = dtmod.parse_date(self.d1.text()).year
            r = dtmod.country_holidays(self.country.text() or "CN", year)
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history(f"{self.country.text()}:{year}", s,
                             module="date-holidays")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "date"))

    def _build_lunar_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
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
            from core import lunar
            r = lunar.solar_to_lunar(self.lunar_date.text())
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history("lunar", s, module="date-lunar")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "date"))

    def _build_sun_tab(self):
        w = QWidget(); f = QFormLayout(w)
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
            from core import astro
            r = astro.sun_times(
                self.sun_date.text(), self.sun_lat.text(),
                self.sun_lon.text(), self.sun_tz.text() or "UTC")
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history("sun", s, module="date-sun")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "date"))