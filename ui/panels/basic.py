"""基础计算面板：百分比 / 折扣 / 小费 / 税 + 内存槽 M1–M9。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QGridLayout, QComboBox, QWidget,
)

from core import engine
from core.errors import InputError
from core.logger import log_exc
from ui.shortcuts import install_panel_shortcuts
from ._common import _clear_layout, friendly_error
from .base import CalcPanel


class BasicPanel(CalcPanel):
    module_key = "basic"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        self.memory = 0.0
        self.mem_slots = {i: 0.0 for i in range(1, 10)}

        self.expr = QLineEdit()
        self.expr.setText(settings.get_draft("basic_expr", ""))
        self.expr.textChanged.connect(
            lambda t: settings.set_draft("basic_expr", t))
        self.expr.returnPressed.connect(self.calc)

        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)

        self.fmt_mode = QComboBox()
        self.fmt_mode.addItem(i18n.t("fmt_auto", "Auto"), "auto")
        self.fmt_mode.addItem(i18n.t("fmt_number", "Number"), "number")
        self.fmt_mode.addItem(i18n.t("fmt_sci", "Scientific"), "sci")
        self.fmt_mode.addItem(i18n.t("fmt_fraction", "Fraction"), "fraction")
        self.fmt_mode.addItem(i18n.t("fmt_percent", "Percent"), "percent")
        self.fmt_mode.setCurrentIndex(
            max(0, self.fmt_mode.findData(
                settings.get("basic_fmt_mode", "auto"))))
        self.fmt_mode.currentIndexChanged.connect(
            lambda _: settings.set("basic_fmt_mode",
                                   self.fmt_mode.currentData()))

        self.btn_box = QWidget()
        self.grid = QGridLayout(self.btn_box)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(4)
        self.rebuild_buttons()

        self.mem_box = QWidget()
        mrow = QHBoxLayout(self.mem_box)
        mrow.setContentsMargins(0, 0, 0, 0)
        for i in range(1, 10):
            b = QPushButton(f"M{i}")
            b.setFixedHeight(26)
            b.clicked.connect(lambda _, k=i: self._mem_pick(k))
            b.setContextMenuPolicy(Qt.CustomContextMenu)
            b.customContextMenuRequested.connect(
                lambda pos, k=i: self._mem_store(k))
            mrow.addWidget(b)

        self.calc_btn = QPushButton(i18n.t("calc"))
        self.calc_btn.setMinimumHeight(36)
        self.calc_btn.clicked.connect(self.calc)

        self.cancel_btn = QPushButton(i18n.t("cancel", "Cancel"))
        self.cancel_btn.setEnabled(False)

        row = QHBoxLayout()
        row.addWidget(self.calc_btn, 1)
        row.addWidget(self.cancel_btn)

        top = QHBoxLayout()
        top.addWidget(QLabel(i18n.t("expr")))
        top.addStretch(1)
        top.addWidget(self.fmt_mode)

        main = QVBoxLayout(self)
        main.addLayout(top)
        main.addWidget(self.expr)
        main.addWidget(self.btn_box)
        main.addWidget(QLabel(i18n.t(
            "memory_hint",
            "Memory (left-click: recall, right-click: store)")))
        main.addWidget(self.mem_box)
        main.addLayout(row)
        main.addWidget(QLabel(i18n.t("result")))
        main.addWidget(self.result, 1)

        install_panel_shortcuts(
            self,
            on_calc=self.calc,
            on_cancel=self.cancel_current,
            on_clear=self._clear,
            expr_widget=self.expr,
            history_getter=self._history_exprs,
        )

    # ---------------- 内存槽 ----------------

    def _mem_pick(self, k):
        try:
            self.expr.insert(str(self.mem_slots[k]))
        except Exception:
            pass

    def _mem_store(self, k):
        try:
            v = self.current_result()
            self.mem_slots[k] = v
            self.result.appendPlainText(f"M{k} ← {v}")
        except Exception:
            pass

    def current_result(self):
        try:
            return float(self.result.toPlainText().splitlines()[-1])
        except Exception:
            return 0.0

    # ---------------- 按钮 ----------------

    def rebuild_buttons(self):
        _clear_layout(self.grid)
        layout = self.settings.get("button_layout", []) or []
        for i, txt in enumerate(layout):
            if not txt:
                continue
            btn = QPushButton(txt)
            btn.setMinimumHeight(38)
            btn.clicked.connect(
                lambda checked=False, t=txt: self.on_button(t))
            self.grid.addWidget(btn, i // 5, i % 5)

        pct = [("%", "%"), ("x% off", "%off"), ("x% on", "%on"),
               ("Tip", "tip"), ("Tax", "tax")]
        base_row = (len(layout) + 4) // 5
        for j, (label, action) in enumerate(pct):
            b = QPushButton(label)
            b.setMinimumHeight(32)
            b.clicked.connect(
                lambda checked=False, a=action: self.on_button(a))
            self.grid.addWidget(b, base_row, j)

    def on_settings_changed(self, key=None):
        if key in (None, "button_layout"):
            try:
                self.rebuild_buttons()
            except Exception as e:
                log_exc(e, module="BasicPanel.on_settings_changed")

    def on_button(self, t):
        if t == "C":
            self.expr.clear()
            self.result.clear()
        elif t == "=":
            self.calc()
        elif t == "M+":
            self.memory += self.current_result()
            self.result.appendPlainText(f"M+ {self.memory}")
        elif t == "M-":
            self.memory -= self.current_result()
            self.result.appendPlainText(f"M- {self.memory}")
        elif t == "MR":
            self.expr.insert(str(self.memory))
        elif t == "MC":
            self.memory = 0
        elif t == "%":
            self.expr.insert("%")
        elif t == "%off":
            self._template_percent("off")
        elif t == "%on":
            self._template_percent("on")
        elif t == "tip":
            self._template_percent("tip")
        elif t == "tax":
            self._template_percent("tax")
        else:
            self.expr.insert(t)

    def _template_percent(self, kind):
        cur = self.expr.text().strip()
        if kind == "off":
            self.expr.setText(f"{cur or '20'}% off 100")
        elif kind == "on":
            self.expr.setText(f"{cur or '8'}% on 100")
        elif kind == "tip":
            self.expr.setText(f"tip 15% on {cur or '100'}")
        elif kind == "tax":
            self.expr.setText(f"tax 13% on {cur or '100'}")

    # ---------------- 计算 ----------------

    def _history_exprs(self):
        try:
            rows = self.history.list(module="basic", limit=50, order="id DESC")
            return [r["expr"] for r in rows if r.get("expr")]
        except Exception:
            return []

    def _clear(self):
        try:
            self.expr.clear()
            self.result.clear()
        except Exception:
            pass

    def calc(self):
        expr = self.expr.text()
        if not expr.strip():
            self.result.appendPlainText(
                friendly_error(self.i18n,
                               InputError("表达式为空",
                                          friendly_key="err_empty_expr"),
                               "basic"))
            return
        self.result.appendPlainText(self.i18n.t("running", "Running…"))
        self.run(
            engine.basic_calc_smart, expr,
            cancel_btn=self.cancel_btn,
            main_btn=self.calc_btn,
            on_done=self._on_done,
            on_fail=self._on_fail,
            on_cancel=self._on_cancel,
        )

    def _apply_format(self, value, raw_desc=None):
        mode = self.fmt_mode.currentData()
        try:
            if mode == "auto":
                text = raw_desc if raw_desc else str(value)
            elif mode == "number":
                text = engine.format_result(value, "text", digits=6)
            elif mode == "sci":
                text = engine.format_result(value, "text", digits=6, sci=True)
            elif mode == "fraction":
                text = engine.format_result(value, "text", fraction=True)
            elif mode == "percent":
                text = engine.format_result(value, "text", percent=True)
            else:
                text = str(value)
        except Exception:
            text = str(value)
        return text

    def _on_done(self, result):
        if isinstance(result, tuple) and len(result) == 2:
            value, desc = result
        else:
            value, desc = result, None
        text = self._apply_format(value, desc)
        self.result.appendPlainText(text)
        self.add_history(self.expr.text(), text, module="basic")

    def _on_fail(self, e):
        self.result.appendPlainText(friendly_error(self.i18n, e, "basic"))

    def _on_cancel(self):
        self.result.appendPlainText(
            self.i18n.t("err_cancelled_task", "Calculation cancelled"))