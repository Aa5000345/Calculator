"""科学计算 / 微积分面板：变量 / ODE / 数值积分 / 优化。"""
from __future__ import annotations

import re
import time

import sympy as sp

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QComboBox, QCheckBox, QSpinBox, QFormLayout,
    QInputDialog, QTabWidget, QWidget, QTableWidget, QTableWidgetItem,
    QHeaderView,
)

from core import engine
from core import constants as const_mod
from core import symbols as sym_mod
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
        "quad":         ["var", "lower", "upper"],
        "limit":        ["var", "point", "direction"],
        "series":       ["var", "point", "order", "series_kind"],
        "summation":    ["var", "lower", "upper"],
        "product":      ["var", "lower", "upper"],
        "dsolve":       ["var", "func_name", "ics"],
        "minimize":     ["var", "x0", "opt_method"],
        "linprog":      ["lp_params"],
    }

    OPS = [
        "calc", "complex", "simplify", "expand", "factor", "apart",
        "trigsimp", "solve", "solve_ineq", "solve_system",
        "diff", "integrate", "quad", "limit", "series",
        "summation", "product",
        "dsolve", "minimize", "linprog",
    ]

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)
        self._calc_start = None

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

        # --- ODE / 优化 新增控件 ---
        self.func_name = QLineEdit("y")
        self.ics = QLineEdit("")
        self.ics.setPlaceholderText("y(0)=1, y(1)=2")
        self.x0 = QLineEdit("0")
        self.opt_method = QComboBox()
        for m in ("BFGS", "Nelder-Mead", "Powell", "CG", "L-BFGS-B",
                  "TNC", "COBYLA"):
            self.opt_method.addItem(m, m)
        self.lp_params = QPlainTextEdit(
            '{"c":[1,2],"A_ub":[[1,1],[1,-1]],"b_ub":[10,2]}')
        self.lp_params.setFixedHeight(90)

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
        self._add_row("func_name",
                      QLabel(i18n.t("func_name", "函数名")), self.func_name)
        self._add_row("ics",
                      QLabel(i18n.t("ics", "初值条件")), self.ics)
        self._add_row("x0",
                      QLabel(i18n.t("x0", "初始值")), self.x0)
        self._add_row("opt_method",
                      QLabel(i18n.t("method", "方法")), self.opt_method)
        self._add_row("lp_params",
                      QLabel(i18n.t("lp_params", "线性规划参数 (JSON)")),
                      self.lp_params)

        self.calc_btn = QPushButton(i18n.t("calc"))
        self.calc_btn.setMinimumHeight(36)
        self.calc_btn.clicked.connect(self.calc)

        self.cancel_btn = QPushButton(i18n.t("cancel", "Cancel"))
        self.cancel_btn.setEnabled(False)

        row = QHBoxLayout()
        row.addWidget(self.calc_btn, 1)
        row.addWidget(self.cancel_btn)

        self.result = ResultView(i18n)

        # --- 变量标签页 ---
        self.tabs = QTabWidget()
        self.tabs.addTab(self.result, i18n.t("result", "结果"))
        self.tabs.addTab(self._build_var_tab(),
                         i18n.t("variables", "变量"))
        self.tabs.currentChanged.connect(self._on_tab_changed)

        main = QVBoxLayout(self)
        main.addLayout(self.form)
        main.addLayout(row)
        main.addWidget(self.tabs, 1)

        self._update_params()

        install_panel_shortcuts(
            self,
            on_calc=self.calc,
            on_cancel=self.cancel_current,
            on_clear=self._clear,
            expr_widget=self.expr,
            history_getter=self._history_exprs,
        )

    # ---------------- 变量标签页 ----------------

    def _build_var_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabel(self.i18n.t(
            "var_hint",
            "在表达式框输入  x = 5  或  f(x) = x^2 + 1  即可定义")))
        self.var_table = QTableWidget(0, 3)
        self.var_table.setHorizontalHeaderLabels(
            [self.i18n.t("name", "名称"),
             self.i18n.t("value", "值"),
             self.i18n.t("actions", "操作")])
        self.var_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        v.addWidget(self.var_table, 1)

        row = QHBoxLayout()
        b_refresh = QPushButton(self.i18n.t("refresh", "刷新"))
        b_clear = QPushButton(self.i18n.t("clear", "清空全部"))
        b_refresh.clicked.connect(self._refresh_vars)
        b_clear.clicked.connect(self._clear_vars)
        row.addWidget(b_refresh)
        row.addWidget(b_clear)
        row.addStretch(1)
        v.addLayout(row)
        return w

    def _refresh_vars(self):
        items = sym_mod.get_all()
        raw = sym_mod.get_raw()
        self.var_table.setRowCount(0)
        for name, val in items.items():
            r = self.var_table.rowCount()
            self.var_table.insertRow(r)
            self.var_table.setItem(r, 0, QTableWidgetItem(name))
            display = raw.get(name, str(val))
            self.var_table.setItem(r, 1, QTableWidgetItem(display))
            cell = QWidget()
            h = QHBoxLayout(cell)
            h.setContentsMargins(0, 0, 0, 0)
            b_ins = QPushButton(self.i18n.t("insert", "插入"))
            b_del = QPushButton(self.i18n.t("delete", "删除"))
            b_ins.clicked.connect(lambda _, n=name: self._insert_var(n))
            b_del.clicked.connect(lambda _, n=name: self._delete_var(n))
            h.addWidget(b_ins)
            h.addWidget(b_del)
            self.var_table.setCellWidget(r, 2, cell)

    def _insert_var(self, name):
        try:
            self.expr.insert(name)
            self.tabs.setCurrentIndex(0)
        except Exception as e:
            log_exc(e, module="ScientificPanel._insert_var")

    def _delete_var(self, name):
        sym_mod.delete_symbol(name)
        self._refresh_vars()

    def _clear_vars(self):
        sym_mod.clear()
        self._refresh_vars()

    def _on_tab_changed(self, idx):
        if idx == 1:
            self._refresh_vars()

    # ---------------- 参数显隐 ----------------

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

    # ---------------- 计算 ----------------

    def calc(self):
        op = self.op.currentData()
        expr = self.expr.text()
        var = self.var.text() or "x"
        self._calc_start = time.time()
        self.run(
            self._compute, op, expr, var,
            cancel_btn=self.cancel_btn,
            main_btn=self.calc_btn,
            on_done=self._on_done,
            on_fail=self._on_fail,
            on_cancel=self._on_cancel,
        )

    def _parse_ics(self):
        s = self.ics.text().strip()
        if not s:
            return None
        out = {}
        for part in s.split(","):
            part = part.strip()
            if "=" not in part:
                continue
            lhs, rhs = part.split("=", 1)
            m = re.search(r"\(\s*([^)]+)\s*\)", lhs)
            if not m:
                continue
            try:
                point = float(sp.sympify(m.group(1)))
            except Exception:
                continue
            try:
                value = float(sp.sympify(rhs.strip()))
            except Exception:
                continue
            out[point] = value
        return out if out else None

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
        if op == "quad":
            return engine.sci_quad(expr, var,
                                   self.lower.text() or "0",
                                   self.upper.text() or "1")
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
        if op == "dsolve":
            return engine.sci_dsolve(
                expr, self.func_name.text() or "y", var,
                self._parse_ics())
        if op == "minimize":
            return engine.sci_minimize(
                expr, var,
                self.x0.text() or "0",
                self.opt_method.currentData() or "BFGS")
        if op == "linprog":
            return engine.sci_linprog(self.lp_params.toPlainText())
        return "未知操作"

    def _special_hints(self, op, r):
        if isinstance(r, dict) and "__solutions__" in r:
            return None
        if op in ("solve", "solve_ineq", "solve_system"):
            if r is None or r == [] or r == {}:
                return self.i18n.t("no_solution", "No solution")
            if isinstance(r, list) and len(r) > 1:
                return (f"{self.i18n.t('multi_solution', 'Multiple solutions')}"
                        f" ({len(r)})")
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

        # 若表达式是赋值，刷新变量列表
        if sym_mod.match_assignment(expr.strip()):
            self._refresh_vars()

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

        elapsed = None
        if self._calc_start is not None:
            elapsed = time.time() - self._calc_start

        self.result.show_result(text, latex, steps=extra_steps,
                                elapsed=elapsed)
        self.add_history(f"{op}:{expr}", text, module="scientific")

    def _on_fail(self, e):
        elapsed = None
        if self._calc_start is not None:
            elapsed = time.time() - self._calc_start
        self.result.show_error(e, elapsed=elapsed, retry_cb=self.calc)

    def _on_cancel(self):
        try:
            self.result.show_result(
                self.i18n.t("err_cancelled_task", "Calculation cancelled"), "")
        except Exception:
            pass