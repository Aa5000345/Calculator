# -*- coding: utf-8 -*-
"""所有功能面板。每个面板接收 (settings, i18n, history)，除个别例外。"""
import json
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QGridLayout, QFormLayout, QComboBox, QCheckBox, QMessageBox,
    QSpinBox, QFontComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QTabWidget, QSplitter, QScrollArea, QColorDialog,
    QAbstractItemView, QSizePolicy, QListWidget, QListWidgetItem
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from core import engine
from ui.latex_widget import LatexLabel


# ===========================================================================
# 通用工具
# ===========================================================================

def _clear_layout(layout):
    """递归清空布局（含子布局）。"""
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
        else:
            sub = item.layout()
            if sub is not None:
                _clear_layout(sub)


class ResultView(QWidget):
    """结果查看器：纯文本 + LaTeX 预览双页签。"""

    def __init__(self, i18n, parent=None):
        super().__init__(parent)
        self.i18n = i18n

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)

        self.latex = LatexLabel(fontsize=16)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.latex)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.text, i18n.t("plain_text", "Plain"))
        self.tabs.addTab(scroll, i18n.t("latex_preview", "LaTeX"))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.tabs)

    def show_result(self, text: str, latex: str = ""):
        self.text.setPlainText(text or "")
        # 空 latex 时禁用 LaTeX 页签，避免显示空白
        self.latex.set_latex(latex or "", text or "")

    def set_color(self, color: str):
        self.latex.set_color(color)


# ===========================================================================
# 基础计算
# ===========================================================================

class BasicPanel(QWidget):
    def __init__(self, settings, i18n, history):
        super().__init__()
        self.settings = settings
        self.i18n = i18n
        self.history = history
        self.memory = 0

        self.expr = QLineEdit()
        self.expr.returnPressed.connect(self.calc)
        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)

        self.btn_box = QWidget()
        self.grid = QGridLayout(self.btn_box)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(4)
        self.rebuild_buttons()

        main = QVBoxLayout(self)
        main.addWidget(QLabel(i18n.t("expr")))
        main.addWidget(self.expr)
        main.addWidget(self.btn_box)
        main.addWidget(QLabel(i18n.t("result")))
        main.addWidget(self.result, 1)

    def rebuild_buttons(self):
        _clear_layout(self.grid)
        layout = self.settings.get("button_layout", []) or []
        for i, txt in enumerate(layout):
            if not txt:
                continue
            btn = QPushButton(txt)
            btn.setMinimumHeight(38)
            btn.clicked.connect(lambda checked=False, t=txt: self.on_button(t))
            self.grid.addWidget(btn, i // 5, i % 5)

    def on_settings_changed(self, key=None):
        if key in (None, "button_layout"):
            self.rebuild_buttons()

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
        else:
            self.expr.insert(t)

    def current_result(self):
        try:
            return float(self.result.toPlainText().splitlines()[-1])
        except Exception:
            return 0

    def calc(self):
        expr = self.expr.text()
        try:
            r = engine.basic_calc(expr)
            s = str(r)
            self.result.appendPlainText(s)
            self.history.add("basic", expr, s)
        except Exception as e:
            self.result.appendPlainText(f"Error: {e}")


# ===========================================================================
# 科学计算 / 微积分
# ===========================================================================

class ScientificPanel(QWidget):
    """完整表单化的科学计算与微积分面板。"""

    # op -> 需要显示的参数字段
    OP_FIELDS = {
        "calc":         [],
        "simplify":     [],
        "expand":       [],
        "factor":       [],
        "apart":        [],
        "trigsimp":     [],
        "solve":        ["var"],
        "solve_system": ["equations", "vars"],
        "diff":         ["var", "order"],
        "integrate":    ["var", "lower", "upper"],
        "limit":        ["var", "point", "direction"],
        "series":       ["var", "point", "order"],
        "summation":    ["var", "lower", "upper"],
        "product":      ["var", "lower", "upper"],
    }

    OPS = [
        "calc", "simplify", "expand", "factor", "apart", "trigsimp",
        "solve", "solve_system", "diff", "integrate", "limit",
        "series", "summation", "product",
    ]

    def __init__(self, settings, i18n, history):
        super().__init__()
        self.settings = settings
        self.i18n = i18n
        self.history = history

        # ---- 操作选择 ----
        self.op = QComboBox()
        for key in self.OPS:
            self.op.addItem(i18n.t(f"op_{key}", key), key)
        self.op.currentIndexChanged.connect(self._update_params)

        # ---- 表达式 ----
        self.expr = QLineEdit("sin(x)*exp(-x)")
        self.expr.returnPressed.connect(self.calc)
        self.expr_label = QLabel(i18n.t("expr"))

        # ---- 参数字段 ----
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

        # ---- 结果格式 ----
        self.fmt = QComboBox()
        self.fmt.addItems(["text", "unicode", "latex"])
        self.fmt.setCurrentText(settings.get("result_format", "text"))

        # ---- 表单 ----
        self.form = QFormLayout()
        self.form.setLabelAlignment(Qt.AlignRight)
        self.form.addRow(self.expr_label, self.expr)
        self.form.addRow(QLabel(i18n.t("operation")), self.op)

        self._rows = {}
        self._add_row("var",       QLabel(i18n.t("variable")),                self.var)
        self._add_row("vars",      QLabel(i18n.t("vars", "Variables")),       self.vars)
        self._add_row("equations", QLabel(i18n.t("equations", "Equations")),  self.equations)
        self._add_row("order",     QLabel(i18n.t("order", "Order")),          self.order)
        self._add_row("lower",     QLabel(i18n.t("lower")),                   self.lower)
        self._add_row("upper",     QLabel(i18n.t("upper")),                   self.upper)
        self._add_row("point",     QLabel(i18n.t("point")),                   self.point)
        self._add_row("direction", QLabel(i18n.t("direction", "Direction")),  self.direction)
        self._add_row("fmt",       QLabel(i18n.t("result_format")),           self.fmt)

        # ---- 按钮 ----
        btn = QPushButton(i18n.t("calc"))
        btn.setMinimumHeight(36)
        btn.clicked.connect(self.calc)

        # ---- 结果 ----
        self.result = ResultView(i18n)

        main = QVBoxLayout(self)
        main.addLayout(self.form)
        main.addWidget(btn)
        main.addWidget(self.result, 1)

        self._update_params()

    def _add_row(self, name, label, widget):
        self.form.addRow(label, widget)
        self._rows[name] = (label, widget, self.form.rowCount() - 1)

    def _update_params(self, *_):
        """根据当前操作显示/隐藏参数行。"""
        op = self.op.currentData()
        need = set(self.OP_FIELDS.get(op, []))
        for name, (label, widget, row) in self._rows.items():
            vis = (name in need) or (name == "fmt")
            try:
                self.form.setRowVisible(row, vis)
            except Exception:
                label.setVisible(vis)
                widget.setVisible(vis)

    # ------------------------------------------------------------------

    def calc(self):
        op = self.op.currentData()
        expr = self.expr.text()
        var = self.var.text() or "x"
        try:
            if op == "calc":
                r = engine.sci_eval(expr)
            elif op == "simplify":
                r = engine.sci_simplify(expr)
            elif op == "expand":
                r = engine.sci_expand(expr)
            elif op == "factor":
                r = engine.sci_factor(expr)
            elif op == "apart":
                r = engine.sci_apart(expr)
            elif op == "trigsimp":
                r = engine.sci_trigsimp(expr)
            elif op == "solve":
                r = engine.sci_solve(expr, var)
            elif op == "solve_system":
                r = engine.sci_solve_system(self.equations.toPlainText(),
                                            self.vars.text())
            elif op == "diff":
                r = engine.sci_diff(expr, var, self.order.value())
            elif op == "integrate":
                r = engine.sci_integrate(expr, var,
                                         self.lower.text() or None,
                                         self.upper.text() or None)
            elif op == "limit":
                r = engine.sci_limit(expr, var,
                                     self.point.text() or "0",
                                     self.direction.currentData())
            elif op == "series":
                r = engine.sci_series(expr, var,
                                      self.point.text() or "0",
                                      self.order.value())
            elif op == "summation":
                r = engine.sci_summation(expr, var,
                                         self.lower.text() or "1",
                                         self.upper.text() or "10")
            elif op == "product":
                r = engine.sci_product(expr, var,
                                       self.lower.text() or "1",
                                       self.upper.text() or "10")
            else:
                r = "未知操作"

            fmt = self.fmt.currentText()
            text = engine.format_result(r, fmt)
            latex = engine.format_result(r, "latex")
            self.result.show_result(text, latex)
            self.history.add("scientific", f"{op}:{expr}", text)
        except Exception as e:
            self.result.show_result(f"Error: {e}", "")


# ===========================================================================
# 单位换算
# ===========================================================================

class UnitPanel(QWidget):
    def __init__(self, settings, i18n, history):
        super().__init__()
        self.i18n = i18n
        self.history = history

        self.value = QLineEdit("1")
        self.from_u = QLineEdit("m")
        self.to_u = QLineEdit("cm")
        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)

        btn = QPushButton(i18n.t("convert"))
        btn.clicked.connect(self.convert)

        form = QGridLayout()
        form.addWidget(QLabel(i18n.t("value")), 0, 0)
        form.addWidget(self.value, 0, 1)
        form.addWidget(QLabel(i18n.t("from")), 1, 0)
        form.addWidget(self.from_u, 1, 1)
        form.addWidget(QLabel(i18n.t("to")), 2, 0)
        form.addWidget(self.to_u, 2, 1)

        main = QVBoxLayout(self)
        main.addLayout(form)
        main.addWidget(btn)
        main.addWidget(self.result, 1)

    def convert(self):
        try:
            r = engine.unit_convert(self.value.text(),
                                    self.from_u.text(),
                                    self.to_u.text())
            self.result.setPlainText(str(r))
            self.history.add(
                "unit",
                f"{self.value.text()} {self.from_u.text()} -> {self.to_u.text()}",
                r)
        except Exception as e:
            self.result.setPlainText(f"Error: {e}")


# ===========================================================================
# 汇率换算
# ===========================================================================

class CurrencyPanel(QWidget):
    def __init__(self, base_path, settings, i18n, history):
        super().__init__()
        self.base_path = base_path
        self.settings = settings
        self.i18n = i18n
        self.history = history
        self.rates_path = os.path.join(base_path, "config", "rates_offline.json")
        self.rates = self.load_rates()

        self.amount = QLineEdit("1")
        self.from_c = QLineEdit("USD")
        self.to_c = QLineEdit("CNY")
        self.source = QComboBox()
        self.source.addItems(["open.er-api.com", "exchangerate.host"])
        self.source.setCurrentText(settings.get("currency_source", "open.er-api.com"))
        self.manual = QLineEdit()
        self.offline = QCheckBox(i18n.t("use_offline"))
        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)

        btn = QPushButton(i18n.t("convert"))
        btn.clicked.connect(self.convert)
        btn_update = QPushButton(i18n.t("update_offline"))
        btn_update.clicked.connect(self.update_offline)

        form = QGridLayout()
        form.addWidget(QLabel(i18n.t("amount")), 0, 0)
        form.addWidget(self.amount, 0, 1)
        form.addWidget(QLabel(i18n.t("from")), 1, 0)
        form.addWidget(self.from_c, 1, 1)
        form.addWidget(QLabel(i18n.t("to")), 2, 0)
        form.addWidget(self.to_c, 2, 1)
        form.addWidget(QLabel(i18n.t("source")), 3, 0)
        form.addWidget(self.source, 3, 1)
        form.addWidget(QLabel(i18n.t("manual_rate")), 4, 0)
        form.addWidget(self.manual, 4, 1)
        form.addWidget(self.offline, 5, 1)

        main = QVBoxLayout(self)
        main.addLayout(form)
        main.addWidget(btn)
        main.addWidget(btn_update)
        main.addWidget(self.result, 1)

    def load_rates(self):
        try:
            with open(self.rates_path, "r", encoding="utf-8") as f:
                return json.load(f)["rates"]
        except Exception:
            return {"USD": 1, "CNY": 7.2, "EUR": 0.92,
                    "JPY": 150, "GBP": 0.79, "HKD": 7.8}

    def save_rates(self, rates):
        try:
            with open(self.rates_path, "w", encoding="utf-8") as f:
                json.dump({"base": "USD", "rates": rates},
                          f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def convert(self):
        try:
            if self.manual.text().strip():
                rate = float(self.manual.text())
                r = float(self.amount.text()) * rate
            else:
                if self.offline.isChecked():
                    rates = self.rates
                else:
                    try:
                        rates = engine.fetch_rates(self.source.currentText())
                        self.rates = rates
                        self.save_rates(rates)
                    except Exception as e:
                        self.result.setPlainText(f"网络失败，使用离线汇率: {e}")
                        rates = self.rates
                r = engine.currency_convert(
                    self.amount.text(), self.from_c.text(),
                    self.to_c.text(), rates)
            self.result.setPlainText(str(r))
            self.history.add(
                "currency",
                f"{self.amount.text()} {self.from_c.text()} -> {self.to_c.text()}",
                r)
        except Exception as e:
            self.result.setPlainText(f"Error: {e}")

    def update_offline(self):
        try:
            rates = engine.fetch_rates(self.source.currentText())
            self.rates = rates
            self.save_rates(rates)
            self.result.setPlainText("离线汇率已更新")
        except Exception as e:
            self.result.setPlainText(f"更新失败: {e}")


# ===========================================================================
# 进制转换
# ===========================================================================

class BasePanel(QWidget):
    def __init__(self, settings, i18n, history):
        super().__init__()
        self.i18n = i18n
        self.history = history

        self.value = QLineEdit("255")
        self.from_b = QLineEdit("10")
        self.to_b = QLineEdit("16")
        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)

        btn = QPushButton(i18n.t("convert"))
        btn.clicked.connect(self.convert)

        form = QGridLayout()
        form.addWidget(QLabel(i18n.t("value")), 0, 0)
        form.addWidget(self.value, 0, 1)
        form.addWidget(QLabel(i18n.t("from")), 1, 0)
        form.addWidget(self.from_b, 1, 1)
        form.addWidget(QLabel(i18n.t("to")), 2, 0)
        form.addWidget(self.to_b, 2, 1)

        main = QVBoxLayout(self)
        main.addLayout(form)
        main.addWidget(btn)
        main.addWidget(self.result, 1)

    def convert(self):
        try:
            r = engine.base_convert(self.value.text(),
                                    self.from_b.text(),
                                    self.to_b.text())
            self.result.setPlainText(r)
            self.history.add(
                "base",
                f"{self.value.text()}({self.from_b.text()}) -> {self.to_b.text()}",
                r)
        except Exception as e:
            self.result.setPlainText(f"Error: {e}")


# ===========================================================================
# 矩阵与线性代数
# ===========================================================================

class MatrixPanel(QWidget):
    UNARY = ["det", "inv", "transpose", "trace", "rank", "rref",
             "eigenvals", "eigenvects", "charpoly", "adjugate",
             "nullspace", "columnspace", "rowspace", "lu", "qr",
             "exp", "norm", "power"]

    BINARY = ["mat_add", "mat_sub", "mat_mul", "mat_hadamard",
              "mat_kron", "mat_solve", "mat_lstsq"]

    def __init__(self, settings, i18n, history):
        super().__init__()
        self.settings = settings
        self.i18n = i18n
        self.history = history

        self.a = QPlainTextEdit("[[1, 2], [3, 4]]")
        self.a.setFixedHeight(90)
        self.b = QPlainTextEdit("[[5, 6], [7, 8]]")
        self.b.setFixedHeight(90)
        self.scalar = QLineEdit("2")

        self.op = QComboBox()
        for k in self.UNARY:
            self.op.addItem(i18n.t(f"mat_{k}", k), k)
        self.op.insertSeparator(self.op.count())
        for k in self.BINARY:
            self.op.addItem(i18n.t(f"mat_{k}", k), k)
        self.op.currentIndexChanged.connect(self._update_params)

        self.fmt = QComboBox()
        self.fmt.addItems(["text", "unicode", "latex"])
        self.fmt.setCurrentText(settings.get("result_format", "text"))

        btn = QPushButton(i18n.t("calc"))
        btn.setMinimumHeight(36)
        btn.clicked.connect(self.calc)

        self.result = ResultView(i18n)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        self.a_label = QLabel(i18n.t("matrix_a", "Matrix A"))
        self.b_label = QLabel(i18n.t("matrix_b", "Matrix B"))
        self.s_label = QLabel(i18n.t("scalar", "Scalar / Power"))
        form.addRow(self.a_label, self.a)
        form.addRow(QLabel(i18n.t("operation")), self.op)
        form.addRow(self.b_label, self.b)
        form.addRow(self.s_label, self.scalar)
        form.addRow(QLabel(i18n.t("result_format")), self.fmt)

        self._form = form
        self._b_row = 2
        self._s_row = 3

        main = QVBoxLayout(self)
        main.addLayout(form)
        main.addWidget(btn)
        main.addWidget(self.result, 1)

        self._update_params()

    def _update_params(self, *_):
        op = self.op.currentData()
        is_binary = op in self.BINARY
        is_power = (op == "power")
        for row, vis in ((self._b_row, is_binary), (self._s_row, is_power)):
            try:
                self._form.setRowVisible(row, vis)
            except Exception:
                pass

    def calc(self):
        op = self.op.currentData()
        try:
            if op in self.BINARY:
                r = engine.matrix_binary(op, self.a.toPlainText(),
                                         self.b.toPlainText())
            else:
                scalar = self.scalar.text() if op == "power" else None
                r = engine.matrix_unary(op, self.a.toPlainText(), scalar)

            fmt = self.fmt.currentText()
            text = engine.format_result(r, "unicode" if fmt == "text" else fmt)
            latex = engine.format_result(r, "latex")
            self.result.show_result(text, latex)
            self.history.add("matrix", f"{op}:{self.a.toPlainText()}", text)
        except Exception as e:
            self.result.show_result(f"Error: {e}", "")


# ===========================================================================
# 统计
# ===========================================================================

class StatsPanel(QWidget):
    def __init__(self, settings, i18n, history):
        super().__init__()
        self.i18n = i18n
        self.history = history

        self.data = QPlainTextEdit("1 2 3 4 5")
        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)

        btn = QPushButton(i18n.t("calc"))
        btn.clicked.connect(self.calc)

        main = QVBoxLayout(self)
        main.addWidget(QLabel(i18n.t("data")))
        main.addWidget(self.data)
        main.addWidget(btn)
        main.addWidget(self.result, 1)

    def calc(self):
        try:
            r = engine.stats_calc(self.data.toPlainText())
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.history.add("stats", self.data.toPlainText(), s)
        except Exception as e:
            self.result.setPlainText(f"Error: {e}")


# ===========================================================================
# 绘图（多曲线 / 极坐标 / 参数方程 / 导出）
# ===========================================================================

class PlotPanel(QWidget):
    COLS = 6
    PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
               "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]
    KINDS = ["cartesian", "polar", "parametric"]

    def __init__(self, settings, i18n, history):
        super().__init__()
        self.settings = settings
        self.i18n = i18n
        self.history = history
        self._color_index = 0
        self._fg = "#ffffff"
        self._bg = "#1e1e1e"
        self._panel = "#2d2d30"

        # ---- 曲线表 ----
        self.table = QTableWidget(0, self.COLS)
        self.table.setHorizontalHeaderLabels([
            i18n.t("curve_expr", "Expression"),
            i18n.t("curve_kind", "Type"),
            i18n.t("curve_expr2", "Y / 2nd"),
            i18n.t("curve_start", "From"),
            i18n.t("curve_end", "To"),
            i18n.t("curve_color", "Color"),
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setFixedHeight(170)

        # ---- 按钮 ----
        self.btn_add = QPushButton(i18n.t("add_curve", "Add curve"))
        self.btn_del = QPushButton(i18n.t("remove_curve", "Remove"))
        self.btn_clr = QPushButton(i18n.t("clear_curves", "Clear all"))
        self.btn_plot = QPushButton(i18n.t("draw", "Plot"))
        self.btn_export = QPushButton(i18n.t("export", "Export"))

        self.btn_add.clicked.connect(lambda: self.add_curve())
        self.btn_del.clicked.connect(self.remove_curve)
        self.btn_clr.clicked.connect(self.clear_curves)
        self.btn_plot.clicked.connect(self.plot)
        self.btn_export.clicked.connect(self.export)

        # ---- 选项 ----
        self.grid_chk = QCheckBox(i18n.t("show_grid", "Grid"))
        self.grid_chk.setChecked(True)
        self.legend_chk = QCheckBox(i18n.t("show_legend", "Legend"))
        self.legend_chk.setChecked(True)

        # ---- 画布 ----
        self.figure = Figure(figsize=(6, 4))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        top = QHBoxLayout()
        top.addWidget(self.btn_add)
        top.addWidget(self.btn_del)
        top.addWidget(self.btn_clr)
        top.addStretch(1)
        top.addWidget(self.btn_plot)
        top.addWidget(self.btn_export)

        opts = QHBoxLayout()
        opts.addWidget(self.grid_chk)
        opts.addWidget(self.legend_chk)
        opts.addStretch(1)

        splitter = QSplitter(Qt.Vertical)
        upper = QWidget()
        ul = QVBoxLayout(upper)
        ul.setContentsMargins(0, 0, 0, 0)
        ul.addWidget(self.table)
        ul.addLayout(top)
        ul.addLayout(opts)
        splitter.addWidget(upper)
        splitter.addWidget(self.canvas)
        splitter.setStretchFactor(1, 1)

        main = QVBoxLayout(self)
        main.addWidget(splitter)

        # 默认曲线
        self.add_curve("sin(x)", "cartesian", "-10", "10")
        self.add_curve("cos(x)", "cartesian", "-10", "10")

    # ------------------------------------------------------------------

    def _next_color(self):
        c = self.PALETTE[self._color_index % len(self.PALETTE)]
        self._color_index += 1
        return c

    def add_curve(self, expr="", kind="cartesian", start="-10", end="10"):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(expr))

        combo = QComboBox()
        for k in self.KINDS:
            combo.addItem(self.i18n.t(f"kind_{k}", k), k)
        idx = self.KINDS.index(kind) if kind in self.KINDS else 0
        combo.setCurrentIndex(idx)
        self.table.setCellWidget(row, 1, combo)

        self.table.setItem(row, 2, QTableWidgetItem("t" if kind == "parametric" else ""))
        self.table.setItem(row, 3, QTableWidgetItem(start))
        self.table.setItem(row, 4, QTableWidgetItem(end))

        color = self._next_color()
        btn = QPushButton()
        btn.setProperty("color", color)
        btn.setStyleSheet(
            f"background:{color};border:1px solid #888;border-radius:4px;")
        btn.setToolTip(color)
        btn.clicked.connect(lambda _, b=btn: self._pick_color(b))
        self.table.setCellWidget(row, 5, btn)

    def remove_curve(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        if not rows and self.table.rowCount():
            rows = [self.table.rowCount() - 1]
        for r in rows:
            self.table.removeRow(r)

    def clear_curves(self):
        self.table.setRowCount(0)

    def _pick_color(self, btn):
        cur = QColor(btn.property("color") or "#1f77b4")
        c = QColorDialog.getColor(cur, self)
        if c.isValid():
            btn.setProperty("color", c.name())
            btn.setStyleSheet(
                f"background:{c.name()};border:1px solid #888;border-radius:4px;")
            btn.setToolTip(c.name())

    def _cell(self, row, col):
        it = self.table.item(row, col)
        return it.text().strip() if it else ""

    # ------------------------------------------------------------------

    def plot(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(self._panel)
        self.figure.patch.set_facecolor(self._bg)
        ax.tick_params(colors=self._fg)
        for spine in ax.spines.values():
            spine.set_color(self._fg)

        errors = []
        plotted = 0
        for row in range(self.table.rowCount()):
            expr = self._cell(row, 0)
            if not expr:
                continue
            widget = self.table.cellWidget(row, 1)
            kind = widget.currentData() if widget else "cartesian"
            expr2 = self._cell(row, 2)
            start = self._cell(row, 3) or "-10"
            end = self._cell(row, 4) or "10"
            cbtn = self.table.cellWidget(row, 5)
            color = (cbtn.property("color") if cbtn else None) or self.PALETTE[0]

            try:
                if kind == "cartesian":
                    xs, ys = engine.sample_cartesian(expr, start, end)
                    label = expr
                elif kind == "polar":
                    xs, ys = engine.sample_polar(expr, start, end)
                    label = f"r = {expr}"
                else:
                    ys_expr = expr2 or "t"
                    xs, ys = engine.sample_parametric(expr, ys_expr, start, end)
                    label = f"({expr}, {ys_expr})"
                ax.plot(xs, ys, color=color, linewidth=1.6, label=label)
                plotted += 1
            except Exception as e:
                errors.append(f"row {row + 1}: {e}")

        if plotted == 0 and not errors:
            ax.text(0.5, 0.5, "No curve", ha="center", va="center",
                    color=self._fg, transform=ax.transAxes)
        if errors:
            ax.text(0.02, 0.98, "\n".join(errors[:4]), ha="left", va="top",
                    color="#ff5555", fontsize=9, transform=ax.transAxes)

        ax.grid(self.grid_chk.isChecked(), color="#666666",
                alpha=0.4, linewidth=0.6)
        if self.legend_chk.isChecked() and plotted:
            leg = ax.legend(facecolor=self._panel, edgecolor=self._fg, fontsize=8)
            for t in leg.get_texts():
                t.set_color(self._fg)

        try:
            self.figure.tight_layout()
        except Exception:
            pass
        self.canvas.draw()
        self.history.add("plot", f"{plotted} curve(s)", "plotted")

    def export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, self.i18n.t("export", "Export"), "plot.png",
            "PNG (*.png);;PDF (*.pdf);;SVG (*.svg)")
        if not path:
            return
        try:
            self.figure.savefig(path, dpi=150, bbox_inches="tight",
                                facecolor=self._bg)
            QMessageBox.information(self, "OK", path)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def set_theme_colors(self, fg, bg, panel):
        self._fg, self._bg, self._panel = fg, bg, panel
        self.plot()


# ===========================================================================
# 财务
# ===========================================================================

class FinancePanel(QWidget):
    def __init__(self, settings, i18n, history):
        super().__init__()
        self.i18n = i18n
        self.history = history

        self.p = QLineEdit("100000")
        self.rate = QLineEdit("4.9")
        self.years = QLineEdit("30")
        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)

        btn = QPushButton(i18n.t("loan"))
        btn.clicked.connect(self.loan)

        self.p2 = QLineEdit("10000")
        self.rate2 = QLineEdit("5")
        self.years2 = QLineEdit("10")
        self.times = QLineEdit("1")
        btn2 = QPushButton(i18n.t("compound_calc"))
        btn2.clicked.connect(self.compound)

        form = QGridLayout()
        form.addWidget(QLabel(i18n.t("principal")), 0, 0)
        form.addWidget(self.p, 0, 1)
        form.addWidget(QLabel(i18n.t("annual_rate")), 1, 0)
        form.addWidget(self.rate, 1, 1)
        form.addWidget(QLabel(i18n.t("years")), 2, 0)
        form.addWidget(self.years, 2, 1)

        form2 = QGridLayout()
        form2.addWidget(QLabel(i18n.t("principal")), 0, 0)
        form2.addWidget(self.p2, 0, 1)
        form2.addWidget(QLabel(i18n.t("annual_rate")), 1, 0)
        form2.addWidget(self.rate2, 1, 1)
        form2.addWidget(QLabel(i18n.t("years")), 2, 0)
        form2.addWidget(self.years2, 2, 1)
        form2.addWidget(QLabel(i18n.t("times")), 3, 0)
        form2.addWidget(self.times, 3, 1)

        main = QVBoxLayout(self)
        main.addLayout(form)
        main.addWidget(btn)
        main.addLayout(form2)
        main.addWidget(btn2)
        main.addWidget(self.result, 1)

    def loan(self):
        try:
            r = engine.finance_loan(self.p.text(), self.rate.text(), self.years.text())
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.history.add(
                "finance-loan",
                f"{self.p.text()},{self.rate.text()},{self.years.text()}", s)
        except Exception as e:
            self.result.setPlainText(f"Error: {e}")

    def compound(self):
        try:
            r = engine.finance_compound(self.p2.text(), self.rate2.text(),
                                        self.years2.text(), self.times.text())
            self.result.setPlainText(str(r))
            self.history.add(
                "finance-compound",
                f"{self.p2.text()},{self.rate2.text()},{self.years2.text()}", r)
        except Exception as e:
            self.result.setPlainText(f"Error: {e}")


# ===========================================================================
# 日期
# ===========================================================================

class DatePanel(QWidget):
    def __init__(self, settings, i18n, history):
        super().__init__()
        self.i18n = i18n
        self.history = history

        self.d1 = QLineEdit("2024-01-01")
        self.d2 = QLineEdit("2024-12-31")
        self.days = QLineEdit("30")
        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)

        btn1 = QPushButton(i18n.t("diff"))
        btn1.clicked.connect(self.diff)
        btn2 = QPushButton(i18n.t("add"))
        btn2.clicked.connect(self.add)

        form = QGridLayout()
        form.addWidget(QLabel(i18n.t("date1")), 0, 0)
        form.addWidget(self.d1, 0, 1)
        form.addWidget(QLabel(i18n.t("date2")), 1, 0)
        form.addWidget(self.d2, 1, 1)
        form.addWidget(QLabel(i18n.t("days")), 2, 0)
        form.addWidget(self.days, 2, 1)

        main = QVBoxLayout(self)
        main.addLayout(form)
        main.addWidget(btn1)
        main.addWidget(btn2)
        main.addWidget(self.result, 1)

    def diff(self):
        try:
            r = engine.date_diff(self.d1.text(), self.d2.text())
            self.result.setPlainText(str(r))
            self.history.add("date-diff",
                             f"{self.d1.text()} -> {self.d2.text()}", r)
        except Exception as e:
            self.result.setPlainText(f"Error: {e}")

    def add(self):
        try:
            r = engine.date_add(self.d1.text(), self.days.text())
            self.result.setPlainText(r)
            self.history.add("date-add",
                             f"{self.d1.text()} + {self.days.text()}", r)
        except Exception as e:
            self.result.setPlainText(f"Error: {e}")


# ===========================================================================
# 随机数
# ===========================================================================

class RandomPanel(QWidget):
    def __init__(self, settings, i18n, history):
        super().__init__()
        self.i18n = i18n
        self.history = history

        self.low = QLineEdit("1")
        self.high = QLineEdit("100")
        self.count = QLineEdit("1")
        self.mode = QComboBox()
        self.mode.addItems(["int", "float"])
        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)

        btn = QPushButton(i18n.t("generate"))
        btn.clicked.connect(self.gen)

        form = QGridLayout()
        form.addWidget(QLabel(i18n.t("low")), 0, 0)
        form.addWidget(self.low, 0, 1)
        form.addWidget(QLabel(i18n.t("high")), 1, 0)
        form.addWidget(self.high, 1, 1)
        form.addWidget(QLabel(i18n.t("count")), 2, 0)
        form.addWidget(self.count, 2, 1)
        form.addWidget(QLabel(i18n.t("mode")), 3, 0)
        form.addWidget(self.mode, 3, 1)

        main = QVBoxLayout(self)
        main.addLayout(form)
        main.addWidget(btn)
        main.addWidget(self.result, 1)

    def gen(self):
        try:
            r = engine.random_numbers(self.low.text(), self.high.text(),
                                      self.count.text(), self.mode.currentText())
            s = str(r)
            self.result.setPlainText(s)
            self.history.add("random",
                             f"{self.low.text()}~{self.high.text()}", s)
        except Exception as e:
            self.result.setPlainText(f"Error: {e}")


# ===========================================================================
# 历史
# ===========================================================================

class HistoryPanel(QWidget):
    def __init__(self, history, i18n):
        super().__init__()
        self.history = history
        self.i18n = i18n
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        btn = QPushButton(i18n.t("clear"))
        btn.clicked.connect(self.clear)
        main = QVBoxLayout(self)
        main.addWidget(self.text, 1)
        main.addWidget(btn)
        self.refresh()

    def refresh(self):
        lines = []
        for x in self.history.items:
            lines.append(f"{x['time']} [{x['module']}] "
                         f"{x['expr']} = {x['result']}")
        self.text.setPlainText("\n".join(lines))

    def clear(self):
        self.history.clear()
        self.refresh()


# ===========================================================================
# 设置（热重载）
# ===========================================================================

class SettingsPanel(QWidget):
    def __init__(self, settings, i18n, main_window):
        super().__init__()
        self.settings = settings
        self.i18n = i18n
        self.main_window = main_window

        self.lang = QComboBox()
        self.lang.addItems(["zh_CN", "en_US"])
        self.lang.setCurrentText(settings.get("language", "zh_CN"))

        self.theme = QComboBox()
        self.theme.addItems(["dark", "light"])
        self.theme.setCurrentText(settings.get("theme", "dark"))

        self.font = QFontComboBox()
        self.font.setCurrentFont(settings.get("font_family", "Microsoft YaHei"))

        self.size = QSpinBox()
        self.size.setRange(8, 30)
        self.size.setValue(int(settings.get("font_size", 11)))

        self.fmt = QComboBox()
        self.fmt.addItems(["text", "unicode", "latex"])
        self.fmt.setCurrentText(settings.get("result_format", "text"))

        self.source = QComboBox()
        self.source.addItems(["open.er-api.com", "exchangerate.host"])
        self.source.setCurrentText(settings.get("currency_source", "open.er-api.com"))

        self.layout_edit = QPlainTextEdit(
            json.dumps(settings.get("button_layout", []), ensure_ascii=False))
        self.layout_edit.setFixedHeight(110)

        btn_apply = QPushButton(i18n.t("apply", "Apply"))
        btn_apply.clicked.connect(self.apply)
        btn_reset = QPushButton(i18n.t("reset", "Reset"))
        btn_reset.clicked.connect(self.reset)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.addRow(QLabel(i18n.t("language")), self.lang)
        form.addRow(QLabel(i18n.t("theme")), self.theme)
        form.addRow(QLabel(i18n.t("font")), self.font)
        form.addRow(QLabel(i18n.t("font_size")), self.size)
        form.addRow(QLabel(i18n.t("result_format")), self.fmt)
        form.addRow(QLabel(i18n.t("source")), self.source)
        form.addRow(QLabel(i18n.t("button_layout")), self.layout_edit)

        # 即时预览：变更即写回设置，触发热重载
        self.theme.currentTextChanged.connect(lambda v: settings.set("theme", v))
        self.font.currentFontChanged.connect(
            lambda f: settings.set("font_family", f.family()))
        self.size.valueChanged.connect(lambda v: settings.set("font_size", v))

        row = QHBoxLayout()
        row.addWidget(btn_apply)
        row.addWidget(btn_reset)

        main = QVBoxLayout(self)
        main.addLayout(form)
        main.addLayout(row)
        main.addStretch(1)

    def apply(self):
        try:
            layout = json.loads(self.layout_edit.toPlainText())
            if not isinstance(layout, list):
                raise ValueError("必须是 JSON 数组")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"button_layout: {e}")
            layout = self.settings.get("button_layout")

        lang_changed = self.lang.currentText() != self.settings.get("language")
        self.settings.update({
            "language": self.lang.currentText(),
            "theme": self.theme.currentText(),
            "font_family": self.font.currentFont().family(),
            "font_size": self.size.value(),
            "result_format": self.fmt.currentText(),
            "currency_source": self.source.currentText(),
            "button_layout": layout,
        })
        if not lang_changed:
            QMessageBox.information(self, "OK",
                                    self.i18n.t("hot_reload", "Applied"))

    def reset(self):
        self.settings.reset()
