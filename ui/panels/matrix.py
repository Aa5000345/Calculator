"""矩阵面板。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QFormLayout, QComboBox, QCheckBox, QSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QTabWidget,
    QWidget, QMessageBox,
)

from core import engine
from core.logger import log_exc
from ._common import ResultView, friendly_error
from .base import CalcPanel


class MatrixPanel(CalcPanel):
    module_key = "matrix"

    UNARY = ["det", "inv", "transpose", "trace", "rank", "rref",
             "eigenvals", "eigenvects", "charpoly", "adjugate",
             "nullspace", "columnspace", "rowspace", "lu", "qr",
             "exp", "norm", "power"]
    BINARY = ["mat_add", "mat_sub", "mat_mul", "mat_hadamard",
              "mat_kron", "mat_solve", "mat_lstsq"]

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)
        self._updating = False

        # --- A ---
        self.a_rows = QSpinBox(); self.a_rows.setRange(1, 15); self.a_rows.setValue(2)
        self.a_cols = QSpinBox(); self.a_cols.setRange(1, 15); self.a_cols.setValue(2)
        self.a_table = QTableWidget(2, 2)
        self.a_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.a_table.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._rebuild_table(self.a_table, 2, 2, [["1", "2"], ["3", "4"]])
        self.a_rows.valueChanged.connect(
            lambda _: self._rebuild_table(self.a_table,
                                          self.a_rows.value(), self.a_cols.value()))
        self.a_cols.valueChanged.connect(
            lambda _: self._rebuild_table(self.a_table,
                                          self.a_rows.value(), self.a_cols.value()))

        # --- B ---
        self.b_rows = QSpinBox(); self.b_rows.setRange(1, 15); self.b_rows.setValue(2)
        self.b_cols = QSpinBox(); self.b_cols.setRange(1, 15); self.b_cols.setValue(2)
        self.b_table = QTableWidget(2, 2)
        self.b_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.b_table.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._rebuild_table(self.b_table, 2, 2, [["5", "6"], ["7", "8"]])
        self.b_rows.valueChanged.connect(
            lambda _: self._rebuild_table(self.b_table,
                                          self.b_rows.value(), self.b_cols.value()))
        self.b_cols.valueChanged.connect(
            lambda _: self._rebuild_table(self.b_table,
                                          self.b_rows.value(), self.b_cols.value()))

        # --- 操作 ---
        self.op = QComboBox()
        for k in self.UNARY:
            self.op.addItem(i18n.t(f"mat_{k}", k), k)
        self.op.insertSeparator(self.op.count())
        for k in self.BINARY:
            self.op.addItem(i18n.t(f"mat_{k}", k), k)
        self.op.currentIndexChanged.connect(self._update_params)

        self.scalar = QLineEdit("2")
        self.scalar_row_widget = QWidget()
        sr = QHBoxLayout(self.scalar_row_widget)
        sr.setContentsMargins(0, 0, 0, 0)
        sr.addWidget(QLabel(i18n.t("scalar", "Scalar / Power")))
        sr.addWidget(self.scalar, 1)

        self.fmt = QComboBox()
        self.fmt.addItems(["text", "unicode", "latex"])
        self.fmt.setCurrentText(settings.get("result_format", "text"))
        self.show_steps = QCheckBox(i18n.t("show_steps", "Show steps"))

        # --- 随机矩阵 ---
        self.rnd_rows = QSpinBox(); self.rnd_rows.setRange(1, 15); self.rnd_rows.setValue(3)
        self.rnd_cols = QSpinBox(); self.rnd_cols.setRange(1, 15); self.rnd_cols.setValue(3)
        self.rnd_low = QLineEdit("-9")
        self.rnd_high = QLineEdit("9")
        self.rnd_kind = QComboBox()
        self.rnd_kind.addItems(["int", "float", "sym"])
        b_rand = QPushButton(i18n.t("random_matrix", "Random A"))
        b_rand.clicked.connect(self._random_a)

        b_csv_in_a = QPushButton(i18n.t("import_csv", "Import A (CSV)"))
        b_csv_in_a.clicked.connect(lambda: self._import_csv(self.a_table))
        b_csv_out_a = QPushButton(i18n.t("export_csv", "Export A (CSV)"))
        b_csv_out_a.clicked.connect(lambda: self._export_csv(self.a_table))
        b_csv_in_b = QPushButton(i18n.t("import_csv", "Import B (CSV)"))
        b_csv_in_b.clicked.connect(lambda: self._import_csv(self.b_table))
        b_csv_out_b = QPushButton(i18n.t("export_csv", "Export B (CSV)"))
        b_csv_out_b.clicked.connect(lambda: self._export_csv(self.b_table))

        # --- 方程组 ---
        self.solver_A = QPlainTextEdit("1 2\n3 4")
        self.solver_A.setFixedHeight(80)
        self.solver_b = QLineEdit("5, 6")
        b_solve = QPushButton(i18n.t("solve_linear", "Solve Ax=b"))
        b_solve.clicked.connect(self._solve_linear)

        btn = QPushButton(i18n.t("calc"))
        btn.setMinimumHeight(36)
        btn.clicked.connect(self.calc)
        self.result = ResultView(i18n)

        # B 编辑器包装成 widget，便于整体显隐
        self.b_editor = QWidget()
        be = QVBoxLayout(self.b_editor)
        be.setContentsMargins(0, 0, 0, 0)
        be.addWidget(QLabel(i18n.t("matrix_b", "Matrix B")))
        b_head = QHBoxLayout()
        b_head.addWidget(QLabel("Rows")); b_head.addWidget(self.b_rows)
        b_head.addWidget(QLabel("Cols")); b_head.addWidget(self.b_cols)
        b_head.addStretch(1)
        be.addLayout(b_head)
        be.addWidget(self.b_table)

        editor = QWidget()
        ev = QVBoxLayout(editor)
        ev.addWidget(QLabel(i18n.t("matrix_a", "Matrix A")))
        a_head = QHBoxLayout()
        a_head.addWidget(QLabel("Rows")); a_head.addWidget(self.a_rows)
        a_head.addWidget(QLabel("Cols")); a_head.addWidget(self.a_cols)
        a_head.addStretch(1)
        ev.addLayout(a_head)
        ev.addWidget(self.a_table)
        ev.addWidget(self.b_editor)

        csv_row = QHBoxLayout()
        for b in (b_csv_in_a, b_csv_out_a, b_csv_in_b, b_csv_out_b):
            csv_row.addWidget(b)
        csv_row.addStretch(1)

        rnd_row = QHBoxLayout()
        rnd_row.addWidget(QLabel("Rows")); rnd_row.addWidget(self.rnd_rows)
        rnd_row.addWidget(QLabel("Cols")); rnd_row.addWidget(self.rnd_cols)
        rnd_row.addWidget(QLabel("Low")); rnd_row.addWidget(self.rnd_low)
        rnd_row.addWidget(QLabel("High")); rnd_row.addWidget(self.rnd_high)
        rnd_row.addWidget(self.rnd_kind)
        rnd_row.addWidget(b_rand)
        rnd_row.addStretch(1)

        op_row = QFormLayout()
        op_row.setLabelAlignment(Qt.AlignRight)
        op_row.addRow(QLabel(i18n.t("operation")), self.op)
        op_row.addRow(QLabel(""), self.scalar_row_widget)
        op_row.addRow(QLabel(i18n.t("result_format")), self.fmt)
        op_row.addRow(QLabel(""), self.show_steps)

        solver = QWidget()
        sv = QVBoxLayout(solver)
        sv.addWidget(QLabel("A (每行一个，逗号/空格分隔)"))
        sv.addWidget(self.solver_A)
        sv.addWidget(QLabel("b (逗号分隔)"))
        sv.addWidget(self.solver_b)
        sv.addWidget(b_solve)
        sv.addStretch(1)

        tabs = QTabWidget()
        w1 = QWidget(); v1 = QVBoxLayout(w1)
        v1.addWidget(editor)
        v1.addLayout(csv_row)
        v1.addLayout(rnd_row)
        tabs.addTab(w1, i18n.t("editor", "Editor"))

        w2 = QWidget(); v2 = QVBoxLayout(w2)
        v2.addLayout(op_row)
        v2.addWidget(btn)
        v2.addStretch(1)
        tabs.addTab(w2, i18n.t("operation", "Op"))

        tabs.addTab(solver, i18n.t("solver", "Solver"))

        main = QVBoxLayout(self)
        main.addWidget(tabs, 1)
        main.addWidget(self.result, 2)

        self._update_params()

    def _rebuild_table(self, table, rows, cols, init=None):
        if self._updating:
            return
        self._updating = True
        try:
            old = self._table_data(table)
            table.setRowCount(int(rows))
            table.setColumnCount(int(cols))
            for i in range(int(rows)):
                for j in range(int(cols)):
                    if init is not None and i < len(init) and j < len(init[i]):
                        val = init[i][j]
                    elif i < len(old) and j < len(old[i]):
                        val = old[i][j]
                    else:
                        val = "0"
                    table.setItem(i, j, QTableWidgetItem(str(val)))
        finally:
            self._updating = False

    def _table_data(self, table):
        out = []
        for i in range(table.rowCount()):
            row = []
            for j in range(table.columnCount()):
                it = table.item(i, j)
                row.append(it.text() if it else "0")
            out.append(row)
        return out

    def _table_to_text(self, table):
        rows = self._table_data(table)
        return "[" + ",".join("[" + ",".join(r) + "]" for r in rows) + "]"

    def _random_a(self):
        try:
            A = engine.matrix_random(
                self.rnd_rows.value(), self.rnd_cols.value(),
                self.rnd_kind.currentText(),
                self.rnd_low.text(), self.rnd_high.text())
            self.a_rows.setValue(A.rows)
            self.a_cols.setValue(A.cols)
            self._rebuild_table(
                self.a_table, A.rows, A.cols,
                [[str(A[i, j]) for j in range(A.cols)] for i in range(A.rows)])
        except Exception as e:
            log_exc(e, module="MatrixPanel._random_a")

    def _import_csv(self, table):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import CSV", "", "CSV (*.csv);;Text (*.txt)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                text = f.read()
            A = engine.matrix_from_csv_text(text)
            if table is self.a_table:
                self.a_rows.setValue(A.rows); self.a_cols.setValue(A.cols)
            else:
                self.b_rows.setValue(A.rows); self.b_cols.setValue(A.cols)
            self._rebuild_table(
                table, A.rows, A.cols,
                [[str(A[i, j]) for j in range(A.cols)] for i in range(A.rows)])
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _export_csv(self, table):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "matrix.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            text = engine.matrix_to_csv_text(
                engine._parse_matrix(self._table_to_text(table)))
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                f.write(text)
            QMessageBox.information(self, "OK", path)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _update_params(self, *_):
        """修复：二元操作时显示 B 编辑器；power 时显示标量输入。"""
        op = self.op.currentData()
        is_binary = op in self.BINARY
        is_power = (op == "power")
        try:
            self.b_editor.setVisible(is_binary)
            self.scalar_row_widget.setVisible(is_power)
        except Exception:
            pass

    def _classify_error(self, e):
        msg = str(e); low = msg.lower()
        if "奇异" in msg or "singular" in low or "det" in low:
            return self.i18n.t("err_singular", "Matrix is singular")
        if "非方阵" in msg or "square" in low:
            return self.i18n.t("err_not_square", "Not a square matrix")
        if "维度" in msg or "dim" in low or "shape" in low:
            return self.i18n.t("err_dim_mismatch", "Dimension mismatch")
        if "空" in msg or "empty" in low:
            return self.i18n.t("err_matrix_empty", "Empty matrix")
        return friendly_error(self.i18n, e, "matrix")

    def _solve_linear(self):
        try:
            A_text = self.solver_A.toPlainText()
            b_text = self.solver_b.text()
            sol, steps = engine.matrix_solve_linear(A_text, b_text)
            text = "\n".join(steps) + "\n\n" + str(sol)
            self.result.show_result(text, "")
            self.add_history(f"A={A_text[:60]}...", text, module="matrix-solve")
        except Exception as e:
            self.result.show_result(self._classify_error(e), "")

    def calc(self):
        op = self.op.currentData()
        try:
            a_text = self._table_to_text(self.a_table)
            if op in self.BINARY:
                b_text = self._table_to_text(self.b_table)
                r = engine.matrix_binary(op, a_text, b_text)
            elif op == "inv" and self.show_steps.isChecked():
                r, steps = engine.matrix_inv_steps(a_text)
                text = "\n".join(steps) + "\n\n" + \
                       engine.format_result(r, "unicode")
                latex = engine.format_result(r, "latex")
                self.result.show_result(text, latex)
                self.add_history(f"{op}:{a_text}", text, module="matrix")
                return
            else:
                scalar = self.scalar.text() if op == "power" else None
                r = engine.matrix_unary(op, a_text, scalar)

            fmt = self.fmt.currentText()
            text = engine.format_result(
                r, "unicode" if fmt == "text" else fmt)
            latex = engine.format_result(r, "latex")
            self.result.show_result(text, latex)
            self.add_history(f"{op}:{a_text}", text, module="matrix")
        except Exception as e:
            self.result.show_result(self._classify_error(e), "")