import json
import os

from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QGridLayout, QComboBox, QCheckBox, QMessageBox,
    QSpinBox, QFontComboBox
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from core import engine


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

        grid = QGridLayout()
        layout = settings.get("button_layout", [])
        for i, txt in enumerate(layout):
            if not txt:
                continue
            btn = QPushButton(txt)
            btn.clicked.connect(lambda checked=False, t=txt: self.on_button(t))
            grid.addWidget(btn, i // 5, i % 5)

        main = QVBoxLayout(self)
        main.addWidget(QLabel(i18n.t("expr")))
        main.addWidget(self.expr)
        main.addLayout(grid)
        main.addWidget(QLabel(i18n.t("result")))
        main.addWidget(self.result)

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


class ScientificPanel(QWidget):
    def __init__(self, settings, i18n, history):
        super().__init__()
        self.settings = settings
        self.i18n = i18n
        self.history = history

        self.expr = QLineEdit()
        self.var = QLineEdit("x")
        self.lower = QLineEdit()
        self.upper = QLineEdit()
        self.point = QLineEdit("0")
        self.op = QComboBox()
        self.op.addItems(["calc", "solve", "integrate", "diff", "limit"])
        self.fmt = QComboBox()
        self.fmt.addItems(["text", "unicode", "latex"])
        self.fmt.setCurrentText(settings.get("result_format", "text"))

        btn = QPushButton(i18n.t("calc"))
        btn.clicked.connect(self.calc)

        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)

        form = QGridLayout()
        form.addWidget(QLabel(i18n.t("expr")), 0, 0)
        form.addWidget(self.expr, 0, 1)
        form.addWidget(QLabel(i18n.t("operation")), 1, 0)
        form.addWidget(self.op, 1, 1)
        form.addWidget(QLabel(i18n.t("variable")), 2, 0)
        form.addWidget(self.var, 2, 1)
        form.addWidget(QLabel(i18n.t("lower")), 3, 0)
        form.addWidget(self.lower, 3, 1)
        form.addWidget(QLabel(i18n.t("upper")), 4, 0)
        form.addWidget(self.upper, 4, 1)
        form.addWidget(QLabel(i18n.t("point")), 5, 0)
        form.addWidget(self.point, 5, 1)
        form.addWidget(QLabel(i18n.t("result_format")), 6, 0)
        form.addWidget(self.fmt, 6, 1)

        main = QVBoxLayout(self)
        main.addLayout(form)
        main.addWidget(btn)
        main.addWidget(self.result)

    def calc(self):
        op = self.op.currentText()
        expr = self.expr.text()
        var = self.var.text() or "x"
        try:
            if op == "calc":
                r = engine.scientific_calc(expr)
            elif op == "solve":
                r = engine.solve_equation(expr, var)
            elif op == "integrate":
                r = engine.integrate_expr(
                    expr, var,
                    self.lower.text() or None,
                    self.upper.text() or None
                )
            elif op == "diff":
                r = engine.diff_expr(expr, var, 1)
            elif op == "limit":
                r = engine.limit_expr(expr, var, self.point.text() or "0")
            else:
                r = "未知操作"

            s = engine.format_result(r, self.fmt.currentText())
            self.result.setPlainText(s)
            self.history.add("scientific", f"{op}:{expr}", s)
        except Exception as e:
            self.result.setPlainText(f"Error: {e}")


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
        main.addWidget(self.result)

    def convert(self):
        try:
            r = engine.unit_convert(self.value.text(), self.from_u.text(), self.to_u.text())
            self.result.setPlainText(str(r))
            self.history.add("unit", f"{self.value.text()} {self.from_u.text()} -> {self.to_u.text()}", r)
        except Exception as e:
            self.result.setPlainText(f"Error: {e}")


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
        main.addWidget(self.result)

    def load_rates(self):
        try:
            with open(self.rates_path, "r", encoding="utf-8") as f:
                return json.load(f)["rates"]
        except Exception:
            return {"USD": 1, "CNY": 7.2, "EUR": 0.92, "JPY": 150, "GBP": 0.79, "HKD": 7.8}

    def save_rates(self, rates):
        with open(self.rates_path, "w", encoding="utf-8") as f:
            json.dump({"base": "USD", "rates": rates}, f, ensure_ascii=False, indent=2)

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
                    self.amount.text(),
                    self.from_c.text(),
                    self.to_c.text(),
                    rates
                )
            self.result.setPlainText(str(r))
            self.history.add("currency", f"{self.amount.text()} {self.from_c.text()} -> {self.to_c.text()}", r)
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
        main.addWidget(self.result)

    def convert(self):
        try:
            r = engine.base_convert(self.value.text(), self.from_b.text(), self.to_b.text())
            self.result.setPlainText(r)
            self.history.add("base", f"{self.value.text()}({self.from_b.text()}) -> {self.to_b.text()}", r)
        except Exception as e:
            self.result.setPlainText(f"Error: {e}")


class MatrixPanel(QWidget):
    def __init__(self, settings, i18n, history):
        super().__init__()
        self.i18n = i18n
        self.history = history

        self.matrix = QPlainTextEdit("[[1,2],[3,4]]")
        self.op = QComboBox()
        self.op.addItems(["det", "inv", "transpose", "eigenvals", "eigenvects", "rref", "rank"])
        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)

        btn = QPushButton(i18n.t("calc"))
        btn.clicked.connect(self.calc)

        main = QVBoxLayout(self)
        main.addWidget(QLabel(i18n.t("matrix")))
        main.addWidget(self.matrix)
        main.addWidget(QLabel(i18n.t("operation")))
        main.addWidget(self.op)
        main.addWidget(btn)
        main.addWidget(self.result)

    def calc(self):
        try:
            r = engine.matrix_op(self.matrix.toPlainText(), self.op.currentText())
            s = engine.format_result(r, "text")
            self.result.setPlainText(s)
            self.history.add("matrix", f"{self.op.currentText()}:{self.matrix.toPlainText()}", s)
        except Exception as e:
            self.result.setPlainText(f"Error: {e}")


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
        main.addWidget(self.result)

    def calc(self):
        try:
            r = engine.stats_calc(self.data.toPlainText())
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.history.add("stats", self.data.toPlainText(), s)
        except Exception as e:
            self.result.setPlainText(f"Error: {e}")


class PlotPanel(QWidget):
    def __init__(self, settings, i18n, history):
        super().__init__()
        self.i18n = i18n
        self.history = history

        self.expr = QLineEdit("sin(x)")
        self.xmin = QLineEdit("-10")
        self.xmax = QLineEdit("10")
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)

        btn = QPushButton(i18n.t("plot"))
        btn.clicked.connect(self.plot)

        form = QGridLayout()
        form.addWidget(QLabel(i18n.t("expr")), 0, 0)
        form.addWidget(self.expr, 0, 1)
        form.addWidget(QLabel(i18n.t("xmin")), 1, 0)
        form.addWidget(self.xmin, 1, 1)
        form.addWidget(QLabel(i18n.t("xmax")), 2, 0)
        form.addWidget(self.xmax, 2, 1)

        main = QVBoxLayout(self)
        main.addLayout(form)
        main.addWidget(btn)
        main.addWidget(self.canvas)

    def plot(self):
        try:
            xs, ys = engine.plot_data(self.expr.text(), self.xmin.text(), self.xmax.text())
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            ax.plot(xs, ys)
            ax.grid(True)
            self.canvas.draw()
            self.history.add("plot", self.expr.text(), "plotted")
        except Exception as e:
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, f"Error: {e}", ha="center")
            self.canvas.draw()


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
        main.addWidget(self.result)

    def loan(self):
        try:
            r = engine.finance_loan(self.p.text(), self.rate.text(), self.years.text())
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.history.add("finance-loan", f"{self.p.text()},{self.rate.text()},{self.years.text()}", s)
        except Exception as e:
            self.result.setPlainText(f"Error: {e}")

    def compound(self):
        try:
            r = engine.finance_compound(self.p2.text(), self.rate2.text(), self.years2.text(), self.times.text())
            self.result.setPlainText(str(r))
            self.history.add("finance-compound", f"{self.p2.text()},{self.rate2.text()},{self.years2.text()}", r)
        except Exception as e:
            self.result.setPlainText(f"Error: {e}")


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
        main.addWidget(self.result)

    def diff(self):
        try:
            r = engine.date_diff(self.d1.text(), self.d2.text())
            self.result.setPlainText(str(r))
            self.history.add("date-diff", f"{self.d1.text()} -> {self.d2.text()}", r)
        except Exception as e:
            self.result.setPlainText(f"Error: {e}")

    def add(self):
        try:
            r = engine.date_add(self.d1.text(), self.days.text())
            self.result.setPlainText(r)
            self.history.add("date-add", f"{self.d1.text()} + {self.days.text()}", r)
        except Exception as e:
            self.result.setPlainText(f"Error: {e}")


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
        main.addWidget(self.result)

    def gen(self):
        try:
            r = engine.random_numbers(self.low.text(), self.high.text(), self.count.text(), self.mode.currentText())
            s = str(r)
            self.result.setPlainText(s)
            self.history.add("random", f"{self.low.text()}~{self.high.text()}", s)
        except Exception as e:
            self.result.setPlainText(f"Error: {e}")


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
        main.addWidget(self.text)
        main.addWidget(btn)
        self.refresh()

    def refresh(self):
        lines = []
        for x in self.history.items:
            lines.append(f"{x['time']} [{x['module']}] {x['expr']} = {x['result']}")
        self.text.setPlainText("\n".join(lines))

    def clear(self):
        self.history.clear()
        self.refresh()


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
        self.font.setCurrentText(settings.get("font_family", "Microsoft YaHei"))

        self.size = QSpinBox()
        self.size.setRange(8, 30)
        self.size.setValue(settings.get("font_size", 11))

        self.fmt = QComboBox()
        self.fmt.addItems(["text", "unicode", "latex"])
        self.fmt.setCurrentText(settings.get("result_format", "text"))

        self.source = QComboBox()
        self.source.addItems(["open.er-api.com", "exchangerate.host"])
        self.source.setCurrentText(settings.get("currency_source", "open.er-api.com"))

        self.layout_edit = QPlainTextEdit(json.dumps(settings.get("button_layout", []), ensure_ascii=False))

        btn = QPushButton(i18n.t("save"))
        btn.clicked.connect(self.save)

        form = QGridLayout()
        form.addWidget(QLabel(i18n.t("language")), 0, 0)
        form.addWidget(self.lang, 0, 1)
        form.addWidget(QLabel(i18n.t("theme")), 1, 0)
        form.addWidget(self.theme, 1, 1)
        form.addWidget(QLabel(i18n.t("font")), 2, 0)
        form.addWidget(self.font, 2, 1)
        form.addWidget(QLabel(i18n.t("font_size")), 3, 0)
        form.addWidget(self.size, 3, 1)
        form.addWidget(QLabel(i18n.t("result_format")), 4, 0)
        form.addWidget(self.fmt, 4, 1)
        form.addWidget(QLabel(i18n.t("source")), 5, 0)
        form.addWidget(self.source, 5, 1)
        form.addWidget(QLabel(i18n.t("button_layout")), 6, 0)
        form.addWidget(self.layout_edit, 6, 1)

        main = QVBoxLayout(self)
        main.addLayout(form)
        main.addWidget(btn)

    def save(self):
        try:
            layout = json.loads(self.layout_edit.toPlainText())
        except Exception:
            layout = self.settings.get("button_layout")

        self.settings.set("language", self.lang.currentText())
        self.settings.set("theme", self.theme.currentText())
        self.settings.set("font_family", self.font.currentFont().family())
        self.settings.set("font_size", self.size.value())
        self.settings.set("result_format", self.fmt.currentText())
        self.settings.set("currency_source", self.source.currentText())
        self.settings.set("button_layout", layout)
        QMessageBox.information(self, "OK", self.i18n.t("restart_hint"))