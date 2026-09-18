"""汇率换算面板：多源 fallback / 缓存 / 离线回退 / 手动币对 / 加密货币。"""
from __future__ import annotations

import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QGridLayout, QComboBox, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView,
)

from core import rates as rates_mod
from core import crypto as crypto_mod
from core.logger import log_exc
from ._common import friendly_error
from .base import CalcPanel


class CurrencyPanel(CalcPanel):
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
        self.crypto_symbol.addItems(crypto_mod.list_coins())
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
            {i.row() for i in self.manual_table.selectedIndexes()},
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
                    r = amount / rate if inverse else amount * rate
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
            crypto_mod.fetch_prices, "usd",
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


__all__ = ["CurrencyPanel"]