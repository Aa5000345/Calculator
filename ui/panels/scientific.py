"""科学计算 / 微积分面板。"""
from __future__ import annotations

import sympy as sp

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QComboBox, QCheckBox, QSpinBox, QFormLayout, QInputDialog,
)

from core import engine
from core import constants as const_mod
from core.logger import log_exc
from ui.shortcuts import install_panel_shortcuts
from ._common import ResultView, friendly_error
from .base import CalcPanel


class ScientificPanel(CalcPanel):
    module_key = "scientific"

    OP_FIELDS = {
        "calc":         [],
        "complex":      [],
        "simplify":     [],
        "expand":       [],
        "factor":       [],
        "apart":        [],
        "trigsimp":     [],
        "solve":        ["var", "show_steps"],
        "solve_ineq":   ["var"],
        "solve_system": ["equations", "vars"],
        "diff":         ["var", "order"],
        "integrate":    ["var", "lower", "upper"],
        "limit":        ["var", "point", "direction"],
        "series":       ["var", "point", "order", "series_kind"],
        "summation":    ["var", "lower", "upper"],
        "product":      ["var", "lower", "upper"],
    }

    OPS = [
        "calc", "complex", "simplify", "expand", "factor", "apart",
        "trigsimp", "solve", "solve_ineq", "solve_system",
        "diff", "integrate", "limit", "series", "summation", "product",
    ]

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        self.op = QComboBox()
        for key in self.OPS:
            self.op.addItem(i18n.t(f"op_{key}", key), key)
        self.op.currentIndexChanged.connect(self._update_params)

        self.expr = QLineEdit(
            settings.get_draft("sci_expr", "sin(x)*exp(-x)"))
        self.expr.textChanged.connect(
            lambda t: settings.set_draft("sci_expr", t))
        self.expr.returnPressed.connect(self.calc)
        self.expr_label = QLabel(i18n.t("expr"))

        self.const_btn = QPushButton(i18n.t("constants", "Constants…"))
        self.const_btn.setFixedHeight(24)
        self.const_btn.clicked.connect(self._pick_constant)

        self.var = QLineEdit("x")
        self.vars = QLineEdit("x, y")
        self.equations = QPlainTextEdit("x + y = 3\nx - y = 1")
        self.equations.setFixedHeight(80)
        self.order = QSpinBox()
        self.order.setRange(1, 30)
        self.order.setValue(1)
        self.lower = QLineEdit()
        self.upper = QLineEdit()
        self.point = QLineEdit("0")
        self.direction = QComboBox()
        self.direction.addItem("+", "+")
        self.direction.addItem("-", "-")
        self.direction.addItem("+-", "+-")

        self.series_kind = QComboBox()
        for k in ("taylor", "fps", "laurent", "asin", "acos",
                  "atan", "log", "exp"):
            self.series_kind.addItem(i18n.t(f"series_{k}", k), k)

        self.show_steps = QCheckBox(i18n.t("show_steps", "Show steps"))

        self.fmt = QComboBox()
        self.fmt.addItems(["text", "unicode", "latex"])
        self.fmt.setCurrentText(settings.get("result_format", "text"))

        self.form = QFormLayout()
        self.form.setLabelAlignment(Qt.AlignRight)

        head = QHBoxLayout()
        head.addWidget(self.expr, 1)
        head.addWidget(self.const_btn)
        self.form.addRow(self.expr_label, head)
        self.form.addRow(QLabel(i18n.t("operation")), self.op)

        self._rows = {}
        self._add_row("var", QLabel(i18n.t("variable")), self.var)
        self._add_row("vars", QLabel(i18n.t("vars", "Variables")), self.vars)
        self._add_row("equations",
                      QLabel(i18n.t("equations", "Equations")), self.equations)
        self._add_row("order", QLabel(i18n.t("order", "Order")), self.order)
        self._add_row("lower", QLabel(i18n.t("lower")), self.lower)
        self._add_row("upper", QLabel(i18n.t("upper")), self.upper)
        self._add_row("point", QLabel(i18n.t("point")), self.point)
        self._add_row("direction",
                      QLabel(i18n.t("direction", "Direction")), self.direction)
        self._add_row("series_kind",
                      QLabel(i18n.t("series_kind", "Series")), self.series_kind)
        self._add_row("show_steps", QLabel(""), self.show_steps)
        self._add_row("fmt", QLabel(i18n.t("result_format")), self.fmt)

        self.calc_btn = QPushButton(i18n.t("calc"))
        self.calc_btn.setMinimumHeight(36)
        self.calc_btn.clicked.connect(self.calc)

        self.cancel_btn = QPushButton(i18n.t("cancel", "Cancel"))
        self.cancel_btn.setEnabled(False)

        row = QHBoxLayout()
        row.addWidget(self.calc_btn, 1)
        row.addWidget(self.cancel_btn)

        self.result = ResultView(i18n)

        main = QVBoxLayout(self)
        main.addLayout(self.form)
        main.addLayout(row)
        main.addWidget(self.result, 1)

        self._update_params()

        install_panel_shortcuts(
            self,
            on_calc=self.calc,
            on_cancel=self.cancel_current,
            on_clear=self._clear,
            expr_widget=self.expr,
            history_getter=self._history_exprs,
        )

    def _add_row(self, name, label, widget):
        self.form.addRow(label, widget)
        self._rows[name] = (label, widget, self.form.rowCount() - 1)

    def _update_params(self, *_):
        op = self.op.currentData()
        need = set(self.OP_FIELDS.get(op, []))
        for name, (label, widget, row) in self._rows.items():
            vis = (name in need) or (name == "fmt")
            try:
                self.form.setRowVisible(row, vis)
            except Exception:
                label.setVisible(vis)
                widget.setVisible(vis)

    def _pick_constant(self):
        try:
            allc = const_mod.all_constants()
            items = [f"{k} = {v[0]}  ({v[3]})" for k, v in sorted(allc.items())]
            text, ok = QInputDialog.getItem(
                self,
                self.i18n.t("constants", "Constants"),
                self.i18n.t("pick_constant", "Insert constant:"),
                items, 0, False,
            )
            if not ok or not text:
                return
            key = text.split("=", 1)[0].strip()
            self.expr.insert(key)
        except Exception as e:
            log_exc(e, module="ScientificPanel._pick_constant")

    def _history_exprs(self):
        try:
            rows = self.history.list(module="scientific", limit=50,
                                     order="id DESC")
            return [r["expr"] for r in rows if r.get("expr")]
        except Exception:
            return []

    def _clear(self):
        try:
            self.expr.clear()
            self.result.show_result("", "")
        except Exception:
            pass

    def calc(self):
        op = self.op.currentData()
        expr = self.expr.text()
        var = self.var.text() or "x"
        self.run(
            self._compute, op, expr, var,
            cancel_btn=self.cancel_btn,
            main_btn=self.calc_btn,
            on_done=self._on_done,
            on_fail=self._on_fail,
            on_cancel=self._on_cancel,
        )

    def _compute(self, op, expr, var):
        if op == "calc":
            return engine.sci_eval(expr)
        if op == "complex":
            return engine.sci_complex_eval(expr)
        if op == "simplify":
            return engine.sci_simplify(expr)
        if op == "expand":
            return engine.sci_expand(expr)
        if op == "factor":
            return engine.sci_factor(expr)
        if op == "apart":
            return engine.sci_apart(expr)
        if op == "trigsimp":
            return engine.sci_trigsimp(expr)
        if op == "solve":
            if self.show_steps.isChecked():
                sols, steps = engine.sci_steps_solve(expr, var)
                return {"__solutions__": sols, "__steps__": steps}
            return engine.sci_solve(expr, var)
        if op == "solve_ineq":
            return engine.sci_solve_inequality(expr, var)
        if op == "solve_system":
            return engine.sci_solve_system(self.equations.toPlainText(),
                                           self.vars.text())
        if op == "diff":
            return engine.sci_diff(expr, var, self.order.value())
        if op == "integrate":
            return engine.sci_integrate(expr, var,
                                        self.lower.text() or None,
                                        self.upper.text() or None)
        if op == "limit":
            return engine.sci_limit(expr, var,
                                    self.point.text() or "0",
                                    self.direction.currentData())
        if op == "series":
            return engine.sci_series_ext(
                expr, var,
                self.point.text() or "0",
                self.order.value(),
                self.series_kind.currentData())
        if op == "summation":
            return engine.sci_summation(expr, var,
                                        self.lower.text() or "1",
                                        self.upper.text() or "10")
        if op == "product":
            return engine.sci_product(expr, var,
                                      self.lower.text() or "1",
                                      self.upper.text() or "10")
        return "未知操作"

    def _special_hints(self, op, r):
        if isinstance(r, dict) and "__solutions__" in r:
            return None
        if op in ("solve", "solve_ineq", "solve_system"):
            if r is None or r == [] or r == {}:
                return self.i18n.t("no_solution", "No solution")
            if isinstance(r, list) and len(r) > 1:
                return f"{self.i18n.t('multi_solution', 'Multiple solutions')} ({len(r)})"
            if isinstance(r, dict) and any(isinstance(v, list) for v in r.values()):
                return self.i18n.t("infinite_solutions", "Infinite solutions")
        if op == "limit":
            if r in (sp.zoo, sp.nan, sp.oo, -sp.oo):
                return self.i18n.t("limit_not_exist", "Limit does not exist")
            if hasattr(r, "is_finite") and r.is_finite is False:
                return self.i18n.t("limit_not_exist", "Limit does not exist")
        return None

    def _on_done(self, r):
        op = self.op.currentData()
        expr = self.expr.text()
        hint = self._special_hints(op, r)

        extra_steps = None
        if isinstance(r, dict) and "__solutions__" in r:
            extra_steps = r.get("__steps__")
            r = r.get("__solutions__")

        digits_raw = self.settings.get("result_digits", 0)
        digits = digits_raw if isinstance(digits_raw, int) and digits_raw > 0 else None
        sci = bool(self.settings.get("result_sci", False))
        fraction = bool(self.settings.get("result_fraction", False))
        percent = bool(self.settings.get("result_percent", False))

        try:
            fmt = self.fmt.currentText()
            text = engine.format_result(r, fmt, digits=digits, sci=sci,
                                        fraction=fraction, percent=percent)
        except Exception:
            text = str(r)

        if hint:
            text = f"[{hint}]\n{text}"

        if extra_steps:
            text = "\n".join(extra_steps) + "\n\n" + text

        try:
            latex = engine.format_result(r, "latex")
        except Exception:
            latex = ""
        self.result.show_result(text, latex)
        self.add_history(f"{op}:{expr}", text, module="scientific")

    def _on_fail(self, e):
        self.result.show_error(e)

    def _on_cancel(self):
        try:
            self.result.show_result(
                self.i18n.t("err_cancelled_task", "Calculation cancelled"), "")
        except Exception:
            pass