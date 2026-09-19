"""单位换算 / 汇率 / 数字系统面板。

合并自：ui/panels/unit.py + ui/panels/currency.py
        + ui/panels/number_systems_panel.py

对外接口（类名保持不变，老 registry.py 无需改动）：
    UnitPanel
    CurrencyPanel
    NumberSystemsPanel

依赖（合并后）：
    core.base        —— InputError / NetworkError / log_exc
    core.engine      —— unit_convert / categories / get_category
    core.rates       —— RateSource / list_sources / load_offline /
                        ensure_fresh / convert / batch_convert /
                        init
    core.rates       —— 加密货币：list_coins / fetch_prices
    core.symbols_lib —— 数字系统：convert / list_systems /
                        to_roman / to_chinese / to_english / to_morse
    ui.shell         —— bus
    ui.shortcuts     —— install_panel_shortcuts
    ui.widgets.input —— InputHistoryButton（延迟）
    ui.panels.base   —— CalcPanel
    ui.panels._common —— ResultView / InlinePreviewBar /
                         friendly_error / _clear_layout
"""
from __future__ import annotations

import json
import re
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QGridLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from core import engine
from core import rates as rates_mod
from core import symbols_lib as ns
from core.base import InputError, NetworkError, log_exc
from ui.shortcuts import install_panel_shortcuts
from ui.shell import bus
from ._common import (
    _clear_layout,
    friendly_error,
    ResultView,
    InlinePreviewBar,
)
from .base import CalcPanel


__all__ = ["UnitPanel", "CurrencyPanel", "NumberSystemsPanel"]


# ===========================================================================
# 单位换算
# ===========================================================================

class UnitPanel(CalcPanel):
    """单位换算面板：接收来自其他面板的"发送到单位面板"。"""

    module_key = "unit"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        # ---------------- 类别 ----------------
        self.category = QComboBox()
        for key in engine.categories():
            label = engine.get_category(key)["label"]
            self.category.addItem(label, key)
        last_cat = settings.get("unit_category", "length")
        idx = self.category.findData(last_cat)
        if idx >= 0:
            self.category.setCurrentIndex(idx)
        self.category.currentIndexChanged.connect(
            self._on_category_changed)

        # ---------------- 输入 ----------------
        self.value = QLineEdit("1")
        self.primary_input = self.value
        self.from_u = QComboBox()
        self.to_u = QComboBox()
        for c in (self.from_u, self.to_u):
            c.setEditable(True)

        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)

        # ---------------- 快捷按钮 ----------------
        self.quick_box = QWidget()
        self.quick_row = QHBoxLayout(self.quick_box)
        self.quick_row.setContentsMargins(0, 0, 0, 0)

        # ---------------- 批量换算 ----------------
        self.batch_targets = QLineEdit()
        self.batch_table = QTableWidget(0, 2)
        self.batch_table.setHorizontalHeaderLabels(
            [i18n.t("unit", "Unit"), i18n.t("value", "Value")])
        self.batch_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self.batch_table.setFixedHeight(180)

        btn = QPushButton(i18n.t("convert"))
        btn.clicked.connect(self.convert)
        btn_batch = QPushButton(
            i18n.t("batch_convert", "Batch"))
        btn_batch.clicked.connect(self.convert_batch)

        form = QGridLayout()
        form.addWidget(QLabel(
            i18n.t("category", "Category")), 0, 0)
        form.addWidget(self.category, 0, 1)
        form.addWidget(QLabel(i18n.t("value")), 1, 0)
        form.addWidget(self.value, 1, 1)
        form.addWidget(QLabel(i18n.t("from")), 2, 0)
        form.addWidget(self.from_u, 2, 1)
        form.addWidget(QLabel(i18n.t("to")), 3, 0)
        form.addWidget(self.to_u, 3, 1)
        form.addWidget(QLabel(i18n.t("targets", "Targets")),
                       4, 0)
        form.addWidget(self.batch_targets, 4, 1)

        main = QVBoxLayout(self)
        main.addLayout(form)
        main.addWidget(QLabel(
            i18n.t("quick", "Quick convert")))
        main.addWidget(self.quick_box)
        main.addWidget(btn)
        main.addWidget(QLabel(
            i18n.t("batch_table", "Batch table")))
        main.addWidget(self.batch_table)
        main.addWidget(btn_batch)
        main.addWidget(QLabel(i18n.t("result")))
        main.addWidget(self.result, 1)

        self._on_category_changed()

        # 订阅跨面板信号
        bus().send_to_unit.connect(self.receive_text)

    # ==================================================================
    # 类别
    # ==================================================================

    def _on_category_changed(self):
        cat_key = self.category.currentData()
        self.settings.set("unit_category", cat_key)
        cat = engine.get_category(cat_key)
        if not cat:
            return
        units = cat["units"]

        for combo, default_idx in ((self.from_u, 0),
                                    (self.to_u, 1)):
            combo.blockSignals(True)
            combo.clear()
            for label, pint in units:
                combo.addItem(label, pint)
            if default_idx < combo.count():
                combo.setCurrentIndex(default_idx)
            combo.blockSignals(False)

        self._rebuild_quick_buttons(units)

        if not self.batch_targets.text().strip():
            labels = [u[0] for u in units[:6]]
            self.batch_targets.setText(",".join(labels))

    def _rebuild_quick_buttons(self, units):
        _clear_layout(self.quick_row)
        for label, pint in units[:8]:
            b = QPushButton(label)
            b.setFixedHeight(26)
            b.clicked.connect(
                lambda _, p=pint: self._quick_convert(p))
            self.quick_row.addWidget(b)
        self.quick_row.addStretch(1)

    def _quick_convert(self, to_pint):
        try:
            idx = self.to_u.findData(to_pint)
            if idx >= 0:
                self.to_u.setCurrentIndex(idx)
            self.convert()
        except Exception as e:
            log_exc(e, module="UnitPanel._quick_convert")

    # ==================================================================
    # 换算
    # ==================================================================

    def convert(self):
        try:
            v = float(self.value.text())
            fu = self.from_u.currentData()
            tu = self.to_u.currentData()
            r = engine.unit_convert(v, fu, tu)
            self.result.setPlainText(
                f"{v} {fu} = {r} {tu}")
            self.add_history(
                f"{v} {fu} -> {tu}", r, module="unit")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "unit"))

    def convert_batch(self):
        try:
            v = float(self.value.text())
            fu = self.from_u.currentData()
            targets = [
                t.strip()
                for t in self.batch_targets.text().split(",")
                if t.strip()]
            self.batch_table.setRowCount(0)
            for t in targets:
                idx = self.to_u.findData(t)
                if idx < 0:
                    continue
                tu = self.to_u.itemData(idx)
                try:
                    r = engine.unit_convert(v, fu, tu)
                except Exception:
                    r = "—"
                row = self.batch_table.rowCount()
                self.batch_table.insertRow(row)
                self.batch_table.setItem(
                    row, 0,
                    QTableWidgetItem(self.to_u.itemText(idx)))
                self.batch_table.setItem(
                    row, 1, QTableWidgetItem(str(r)))
            self.add_history(
                f"{v} {fu} -> {targets}",
                f"{self.batch_table.rowCount()} rows",
                module="unit-batch")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "unit"))

    # ==================================================================
    # 跨面板接收
    # ==================================================================

    def receive_text(self, text: str):
        """接收 "1.5 km" / "1.5 kilometer" 之类的文本。"""
        try:
            s = str(text).strip()
            if "\n" in s:
                return
            m = re.match(
                r"^\s*(-?\d+\.?\d*(?:[eE][-+]?\d+)?)"
                r"\s+([A-Za-z°μµ/²³·]+.*?)\s*$",
                s)
            if not m:
                return
            value_str = m.group(1)
            unit_str = m.group(2).strip()
            self.value.setText(value_str)
            idx = self.from_u.findData(unit_str)
            if idx < 0:
                for i in range(self.from_u.count()):
                    if str(self.from_u.itemData(i)) == unit_str:
                        idx = i
                        break
            if idx >= 0:
                self.from_u.setCurrentIndex(idx)
            else:
                self.from_u.setEditText(unit_str)
            self.convert()
        except Exception as e:
            log_exc(e, module="UnitPanel.receive_text")


# ===========================================================================
# 汇率换算
# ===========================================================================

class CurrencyPanel(CalcPanel):
    """汇率换算面板。

    多源 fallback / 缓存 / 离线回退 / 手动币对 / 加密货币。
    """

    module_key = "currency"

    AUTO_REFRESH_MS = 30 * 60 * 1000

    def __init__(self, base_path, settings, i18n, history):
        super().__init__(settings, i18n, history)
        self.base_path = base_path
        self._auto_worker = None

        try:
            self.rates_cache = rates_mod.load_offline(base_path)
        except Exception as e:
            log_exc(e, module="CurrencyPanel.init")
            self.rates_cache = {
                "rates": {}, "updated": 0, "source": "offline"}

        # ---------------- 输入 ----------------
        self.amount = QLineEdit("1")
        self.primary_input = self.amount
        self.from_c = QComboBox()
        self.from_c.setEditable(True)
        self.from_c.setInsertPolicy(QComboBox.NoInsert)
        self.to_c = QComboBox()
        self.to_c.setEditable(True)
        self.to_c.setInsertPolicy(QComboBox.NoInsert)
        self._populate_currencies()

        self.batch = QLineEdit("EUR,JPY,GBP,HKD")

        # ---------------- 汇率源 ----------------
        self.source = QComboBox()
        for s in rates_mod.list_sources():
            self.source.addItem(s.label, s.name)
        default_src = settings.get(
            "currency_source", "open.er-api.com")
        idx = self.source.findData(default_src)
        if idx >= 0:
            self.source.setCurrentIndex(idx)

        # ---------------- 手动汇率表 ----------------
        self.manual_table = QTableWidget(0, 3)
        self.manual_table.setHorizontalHeaderLabels(
            [i18n.t("from"), i18n.t("to"),
             i18n.t("rate", "Rate")])
        self.manual_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self.manual_table.setFixedHeight(140)
        self._load_manual_table()
        b_add_manual = QPushButton(i18n.t("add", "Add"))
        b_del_manual = QPushButton(i18n.t("delete", "Delete"))
        b_add_manual.clicked.connect(self._add_manual_row)
        b_del_manual.clicked.connect(self._del_manual_row)

        # ---------------- 加密货币 ----------------
        self.crypto_symbol = QComboBox()
        self.crypto_symbol.addItems(rates_mod.list_coins())
        self.crypto_label = QLabel("—")
        b_crypto = QPushButton(
            i18n.t("crypto_fetch", "Fetch crypto prices"))
        b_crypto.clicked.connect(self._fetch_crypto)

        # ---------------- 选项 ----------------
        self.offline = QCheckBox(i18n.t("use_offline"))
        self.offline.setChecked(True)
        self.auto_refresh = QCheckBox(
            i18n.t("auto_refresh", "Auto refresh"))
        self.auto_refresh.setChecked(
            bool(settings.get("currency_auto_refresh", False)))
        self.auto_refresh.stateChanged.connect(
            self._on_auto_refresh_toggled)

        # ---------------- 结果 ----------------
        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)
        self.status = QLabel("")
        self.status.setStyleSheet("color: #888;")

        # ---------------- 操作按钮 ----------------
        btn = QPushButton(i18n.t("convert"))
        btn.clicked.connect(self.convert)
        btn_batch = QPushButton(
            i18n.t("batch_convert", "Batch"))
        btn_batch.clicked.connect(self.convert_batch)
        btn_update = QPushButton(i18n.t("update_offline"))
        btn_update.clicked.connect(self.update_offline)

        # ---------------- 布局 ----------------
        form = QGridLayout()
        form.addWidget(QLabel(i18n.t("amount")), 0, 0)
        form.addWidget(self.amount, 0, 1)
        form.addWidget(QLabel(i18n.t("from")), 1, 0)
        form.addWidget(self.from_c, 1, 1)
        form.addWidget(QLabel(i18n.t("to")), 2, 0)
        form.addWidget(self.to_c, 2, 1)
        form.addWidget(
            QLabel(i18n.t("target_currencies", "Targets")),
            3, 0)
        form.addWidget(self.batch, 3, 1)
        form.addWidget(QLabel(i18n.t("source")), 4, 0)
        form.addWidget(self.source, 4, 1)
        form.addWidget(self.offline, 5, 1)
        form.addWidget(self.auto_refresh, 6, 1)

        manual_box = QVBoxLayout()
        manual_box.addWidget(QLabel(
            i18n.t("manual_rates", "Manual rates")))
        manual_box.addWidget(self.manual_table)
        mrow = QHBoxLayout()
        mrow.addWidget(b_add_manual)
        mrow.addWidget(b_del_manual)
        mrow.addStretch(1)
        manual_box.addLayout(mrow)

        crypto_row = QHBoxLayout()
        crypto_row.addWidget(QLabel(
            i18n.t("crypto", "Crypto")))
        crypto_row.addWidget(self.crypto_symbol)
        crypto_row.addWidget(b_crypto)
        crypto_box = QVBoxLayout()
        crypto_box.addLayout(crypto_row)
        crypto_box.addWidget(self.crypto_label)

        main = QVBoxLayout(self)
        main.addLayout(form)
        main.addLayout(manual_box)
        main.addLayout(crypto_box)
        for b in (btn, btn_batch, btn_update):
            main.addWidget(b)
        main.addWidget(self.status)
        main.addWidget(self.result, 1)

        # ---------------- 自动刷新 ----------------
        self._auto_timer = QTimer(self)
        self._auto_timer.setInterval(self.AUTO_REFRESH_MS)
        self._auto_timer.timeout.connect(
            lambda: self._refresh_async(force=True))
        if self.auto_refresh.isChecked():
            self._auto_timer.start()

        QTimer.singleShot(
            0, lambda: self._refresh_async(force=False))

    # ==================================================================
    # 币种填充
    # ==================================================================

    def _populate_currencies(self):
        try:
            codes = sorted(
                (self.rates_cache.get("rates") or {}).keys())
        except Exception:
            codes = []
        if not codes:
            codes = ["USD", "CNY", "EUR", "JPY",
                     "GBP", "HKD"]
        for c in (self.from_c, self.to_c):
            c.blockSignals(True)
            c.clear()
            c.addItems(codes)
            c.blockSignals(False)
        idx = self.from_c.findText("USD")
        if idx >= 0:
            self.from_c.setCurrentIndex(idx)
        idx = self.to_c.findText("CNY")
        if idx >= 0:
            self.to_c.setCurrentIndex(idx)

    # ==================================================================
    # 手动汇率表
    # ==================================================================

    def _load_manual_table(self):
        try:
            rates = self.settings.get("manual_rates", {}) or {}
            self.manual_table.setRowCount(0)
            for pair, rate in rates.items():
                if "->" not in pair:
                    continue
                a, b = pair.split("->", 1)
                r = self.manual_table.rowCount()
                self.manual_table.insertRow(r)
                self.manual_table.setItem(
                    r, 0, QTableWidgetItem(a))
                self.manual_table.setItem(
                    r, 1, QTableWidgetItem(b))
                self.manual_table.setItem(
                    r, 2, QTableWidgetItem(str(rate)))
        except Exception as e:
            log_exc(e, module="CurrencyPanel._load_manual_table")

    def _save_manual_table(self):
        try:
            out = {}
            for r in range(self.manual_table.rowCount()):
                a = (self.manual_table.item(r, 0)
                     or QTableWidgetItem()).text().strip().upper()
                b = (self.manual_table.item(r, 1)
                     or QTableWidgetItem()).text().strip().upper()
                v = (self.manual_table.item(r, 2)
                     or QTableWidgetItem()).text().strip()
                if not a or not b or not v:
                    continue
                try:
                    out[f"{a}->{b}"] = float(v)
                except ValueError:
                    continue
            self.settings.set("manual_rates", out)
        except Exception as e:
            log_exc(e, module="CurrencyPanel._save_manual_table")

    def _add_manual_row(self):
        r = self.manual_table.rowCount()
        self.manual_table.insertRow(r)
        self.manual_table.setItem(
            r, 0, QTableWidgetItem("USD"))
        self.manual_table.setItem(
            r, 1, QTableWidgetItem("CNY"))
        self.manual_table.setItem(
            r, 2, QTableWidgetItem("7.25"))
        self._save_manual_table()

    def _del_manual_row(self):
        rows = sorted(
            {i.row()
             for i in self.manual_table.selectedIndexes()},
            reverse=True)
        if not rows and self.manual_table.rowCount():
            rows = [self.manual_table.rowCount() - 1]
        for r in rows:
            self.manual_table.removeRow(r)
        self._save_manual_table()

    # ==================================================================
    # 自动刷新
    # ==================================================================

    def _on_auto_refresh_toggled(self, state):
        try:
            self.settings.set(
                "currency_auto_refresh", bool(state))
            if state:
                self._auto_timer.start()
            else:
                self._auto_timer.stop()
        except Exception as e:
            log_exc(e,
                    module="CurrencyPanel._on_auto_refresh_toggled")

    def _refresh_async(self, force=False):
        if (self._auto_worker is not None
                and self._auto_worker.isRunning()):
            return
        try:
            self._auto_worker = self.run(
                lambda: rates_mod.ensure_fresh(
                    self.base_path, force=force,
                    source=self.source.currentData()),
                cancel_btn=None, main_btn=None,
                on_done=self._on_rates_ready,
                on_fail=lambda e: log_exc(
                    e, module="CurrencyPanel.refresh"),
            )
        except Exception as e:
            log_exc(e, module="CurrencyPanel._refresh_async")

    def _on_rates_ready(self, data):
        try:
            if data:
                self.rates_cache = data
                self._populate_currencies()
            src = self.rates_cache.get("source", "?")
            upd = self.rates_cache.get("updated", 0)
            try:
                t = (time.strftime(
                    "%Y-%m-%d %H:%M",
                    time.localtime(float(upd))) if upd else "—")
            except Exception:
                t = "—"
            self.status.setText(
                f"source: {src}   updated: {t}")
        except Exception as e:
            log_exc(e, module="CurrencyPanel._on_rates_ready")

    # ==================================================================
    # 换算
    # ==================================================================

    def _lookup_manual(self, fc, tc):
        rates = self.settings.get("manual_rates", {}) or {}
        v = rates.get(f"{fc}->{tc}")
        if v is not None:
            return float(v), False
        v = rates.get(f"{tc}->{fc}")
        if v is not None:
            return float(v), True
        return None, False

    def _ensure_rates(self, on_ready):
        if self.offline.isChecked():
            on_ready(self.rates_cache)
        else:
            self.result.setPlainText(
                self.i18n.t("running", "Running…"))
            self.run(
                lambda: rates_mod.ensure_fresh(
                    self.base_path, force=True,
                    source=self.source.currentData()),
                cancel_btn=None, main_btn=None,
                on_done=on_ready,
                on_fail=lambda e: self.result.setPlainText(
                    friendly_error(self.i18n, e, "currency")),
            )

    def convert(self):
        try:
            fc = self.from_c.currentText().strip().upper()
            tc = self.to_c.currentText().strip().upper()
            amount = float(self.amount.text())
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "currency"))
            return

        def _do(data):
            try:
                self._on_rates_ready(data)
                rate, inverse = self._lookup_manual(fc, tc)
                if rate is not None:
                    r = (amount / rate if inverse
                         else amount * rate)
                else:
                    rates = (data or self.rates_cache).get(
                        "rates", {})
                    r = rates_mod.convert(
                        amount, fc, tc, rates)
                self.result.setPlainText(
                    f"{amount} {fc} = {r} {tc}")
                self.add_history(
                    f"{amount} {fc}->{tc}", r,
                    module="currency")
            except Exception as e:
                self.result.setPlainText(
                    friendly_error(self.i18n, e, "currency"))

        self._ensure_rates(_do)

    def convert_batch(self):
        try:
            fc = self.from_c.currentText().strip().upper()
            amount = float(self.amount.text())
            targets = [
                t.strip().upper()
                for t in self.batch.text().split(",")
                if t.strip()]
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "currency"))
            return

        def _do(data):
            try:
                self._on_rates_ready(data)
                rates = (data or self.rates_cache).get(
                    "rates", {})
                res = rates_mod.batch_convert(
                    amount, fc, targets, rates)
                lines = [f"{amount} {fc} ="] + [
                    f"  {v:.4f} {k}" for k, v in res.items()]
                s = "\n".join(lines)
                self.result.setPlainText(s)
                self.add_history(
                    f"{amount} {fc} -> {targets}", s,
                    module="currency-batch")
            except Exception as e:
                self.result.setPlainText(
                    friendly_error(self.i18n, e, "currency"))

        self._ensure_rates(_do)

    def update_offline(self):
        def _done(data):
            self._on_rates_ready(data)
            self.result.setPlainText(
                f"{self.i18n.t('update_offline')}: "
                f"{(data or {}).get('source', 'cache')}")
        self._ensure_rates(_done)

    # ==================================================================
    # 加密货币
    # ==================================================================

    def _fetch_crypto(self):
        self.crypto_label.setText(
            self.i18n.t("running", "Running…"))
        self.run(
            rates_mod.fetch_prices, "usd",
            cancel_btn=None, main_btn=None,
            on_done=self._on_crypto_ready,
            on_fail=lambda e: self.crypto_label.setText(
                friendly_error(self.i18n, e, "crypto")),
        )

    def _on_crypto_ready(self, prices):
        try:
            if not prices:
                self.crypto_label.setText("—")
                return
            sym = self.crypto_symbol.currentText()
            price = prices.get(sym)
            lines = [
                f"{sym}: ${price:,.2f}"
                if price is not None else f"{sym}: —"]
            for k in ("BTC", "ETH", "USDT", "BNB", "SOL"):
                if k in prices:
                    lines.append(
                        f"{k}: ${prices[k]:,.2f}")
            self.crypto_label.setText("  |  ".join(lines))
        except Exception as e:
            log_exc(e, module="CurrencyPanel._on_crypto_ready")


# ===========================================================================
# 数字系统转换
# ===========================================================================

class NumberSystemsPanel(CalcPanel):
    """数字系统转换面板：阿拉伯 ↔ 罗马 / 中文 / 英文 / 摩尔斯。"""

    module_key = "number_systems"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)
        self._calc_start = None

        # ---------------- 输入区 ----------------
        self.value = QLineEdit("2024")
        self.primary_input = self.value
        self.value.textChanged.connect(
            lambda t: settings.set_draft("ns_value", t))
        self.value.returnPressed.connect(self.calc)
        draft = settings.get_draft("ns_value", "")
        if draft:
            self.value.setText(draft)

        self.from_sys = QComboBox()
        self.to_sys = QComboBox()
        for s in ns.list_systems():
            label = i18n.t(f"ns_{s['key']}", s["label"])
            self.from_sys.addItem(label, s["key"])
            self.to_sys.addItem(label, s["key"])
        self.from_sys.setCurrentIndex(
            self.from_sys.findData("arabic"))
        self.to_sys.setCurrentIndex(
            self.to_sys.findData("roman"))

        self.from_sys.currentIndexChanged.connect(
            lambda _: self.preview.refresh(self.value.text()))
        self.to_sys.currentIndexChanged.connect(
            lambda _: self.preview.refresh(self.value.text()))

        # ---------------- 按钮 ----------------
        self.calc_btn = QPushButton(i18n.t("calc", "转换"))
        self.calc_btn.setMinimumHeight(32)
        self.calc_btn.clicked.connect(self.calc)

        self.swap_btn = QPushButton("⇄")
        self.swap_btn.setFixedWidth(36)
        self.swap_btn.setToolTip(
            i18n.t("ns_swap", "交换源/目标系统"))
        self.swap_btn.clicked.connect(self._swap)

        # ---------------- 实时预览 ----------------
        self.preview = InlinePreviewBar(calc_fn=self._preview)
        self.preview.attach(
            self.value, enabled_getter=lambda: True)

        # ---------------- 结果 ----------------
        self.result = ResultView(i18n)

        # ---------------- 对照表 ----------------
        self.ref_table = QTableWidget(0, 6)
        self.ref_table.setHorizontalHeaderLabels([
            i18n.t("ns_arabic", "阿拉伯"),
            i18n.t("ns_roman", "罗马"),
            i18n.t("ns_chinese", "中文"),
            i18n.t("ns_chinese_formal", "大写"),
            i18n.t("ns_english", "英文"),
            i18n.t("ns_morse", "摩尔斯"),
        ])
        self.ref_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self.ref_table.verticalHeader().setVisible(False)
        self.ref_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers)
        self.ref_table.setSelectionBehavior(
            QAbstractItemView.SelectRows)
        self.ref_table.setMaximumHeight(240)
        self._fill_ref_table()

        # ---------------- 布局 ----------------
        top = QHBoxLayout()
        top.addWidget(QLabel(i18n.t("ns_input", "输入")))
        top.addWidget(self.value, 1)

        try:
            from ui.widgets.input import InputHistoryButton
            self.history_btn = InputHistoryButton(
                settings, i18n, "number_systems.value", self)
            self.history_btn.attach(self.value)
            top.addWidget(self.history_btn)
        except Exception:
            self.history_btn = None

        top.addWidget(self.make_kb_button())

        sys_row = QHBoxLayout()
        sys_row.addWidget(QLabel(i18n.t("ns_from", "源系统")))
        sys_row.addWidget(self.from_sys, 1)
        sys_row.addWidget(self.swap_btn)
        sys_row.addWidget(QLabel(i18n.t("ns_to", "目标系统")))
        sys_row.addWidget(self.to_sys, 1)

        main = QVBoxLayout(self)
        main.addLayout(top)
        main.addLayout(sys_row)
        main.addWidget(self.preview)
        main.addWidget(self.calc_btn)
        main.addWidget(QLabel(i18n.t("result", "结果")))
        main.addWidget(self.result, 2)
        main.addWidget(QLabel(i18n.t("ns_ref_table", "对照表")))
        main.addWidget(self.ref_table, 1)

        install_panel_shortcuts(
            self,
            on_calc=self.calc,
            on_cancel=self.cancel_current,
            on_clear=self._clear,
            on_undo=self.undo,
            expr_widget=self.value,
            history_getter=self._history_exprs,
        )

        sc_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        sc_undo.setContext(Qt.WidgetWithChildrenShortcut)
        sc_undo.activated.connect(self.undo)
        self._undo_sc = sc_undo

    # ==================================================================

    def _swap(self):
        try:
            i = self.from_sys.currentIndex()
            j = self.to_sys.currentIndex()
            self.from_sys.setCurrentIndex(j)
            self.to_sys.setCurrentIndex(i)
        except Exception:
            pass

    def _preview(self, text):
        s = (text or "").strip()
        if not s:
            return None
        try:
            return ns.convert(
                s,
                self.from_sys.currentData(),
                self.to_sys.currentData())
        except Exception:
            return None

    def _clear(self):
        try:
            self.push_undo()
            self.value.clear()
            self.result.show_result("", "")
        except Exception:
            pass

    def _history_exprs(self):
        try:
            rows = self.history.list(
                module="number_systems", limit=50,
                order="id DESC")
            return [r["expr"] for r in rows if r.get("expr")]
        except Exception:
            return []

    def calc(self):
        s = self.value.text().strip()
        if not s:
            self.result.show_error(
                InputError("输入为空",
                           friendly_key="err_empty_expr"))
            return
        self.push_undo()
        self._calc_start = time.time()
        try:
            out = ns.convert(
                s,
                self.from_sys.currentData(),
                self.to_sys.currentData())
            elapsed = time.time() - self._calc_start
            self.result.show_result(
                str(out), "", elapsed=elapsed)
            self.add_history(
                f"{s} ({self.from_sys.currentText()} → "
                f"{self.to_sys.currentText()})",
                str(out),
                module="number_systems")
        except Exception as e:
            self.result.show_error(e, retry_cb=self.calc)

    def _fill_ref_table(self):
        self.ref_table.setRowCount(0)
        for n in range(1, 21):
            r = self.ref_table.rowCount()
            self.ref_table.insertRow(r)
            try:
                vals = [
                    str(n),
                    ns.to_roman(n),
                    ns.to_chinese(n),
                    ns.to_chinese(n, formal=True),
                    ns.to_english(n),
                    ns.to_morse(n),
                ]
            except Exception:
                vals = [str(n), "", "", "", "", ""]
            for c, v in enumerate(vals):
                self.ref_table.setItem(
                    r, c, QTableWidgetItem(v))