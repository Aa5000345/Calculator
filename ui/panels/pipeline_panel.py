"""工作流管道面板：把多个计算步骤串起来。

变更历史：
- 第 5 轮：新增
- 第 13 轮：InputHistoryButton
"""
from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView,
)

from core import pipeline as pipe_mod
from core import engine
from core.errors import InputError
from core.logger import log_exc
from ui.shortcuts import install_panel_shortcuts
from ._common import ResultView, InlinePreviewBar, friendly_error
from .base import CalcPanel


class PipelinePanel(CalcPanel):
    module_key = "pipeline"

    EXAMPLES = [
        "1 km | to m",
        "1 km | to m | * 2",
        "1 kg | to g | * 1000",
        "100 USD | to CNY",
        "5 | sqrt | round(2)",
        "0.1 | as fraction",
        "sin(30) | round(3)",
        "100 | * 1.15 | as percent",
        "0.5 | as percent | round(1)",
        "2 | + 3 | * 4 | ** 2",
    ]

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)
        self._calc_start = None

        # ---------------- 主输入框 ----------------
        self.expr = QLineEdit()
        draft = settings.get_draft(
            "pipeline_expr", "1 km | to m | * 2")
        self.expr.setText(draft)
        self.expr.textChanged.connect(
            lambda t: settings.set_draft("pipeline_expr", t))
        self.expr.returnPressed.connect(self.calc)
        self.primary_input = self.expr

        # ---------------- 示例下拉 ----------------
        self.examples = QComboBox()
        self.examples.addItem(
            i18n.t("pipeline_examples", "示例…"), None)
        for ex in self.EXAMPLES:
            self.examples.addItem(ex, ex)
        self.examples.currentIndexChanged.connect(
            self._on_example_chosen)

        # ---------------- 按钮 ----------------
        self.calc_btn = QPushButton(i18n.t("calc", "计算"))
        self.calc_btn.setMinimumHeight(32)
        self.calc_btn.clicked.connect(self.calc)

        self.cancel_btn = QPushButton(
            i18n.t("cancel", "取消"))
        self.cancel_btn.setEnabled(False)

        # ---------------- 实时预览 ----------------
        self.preview = InlinePreviewBar(
            calc_fn=self._preview_calc)
        self.preview.attach(
            self.expr,
            enabled_getter=lambda: bool(
                self.settings.get("inline_preview", True)))

        # ---------------- 步骤表格 ----------------
        self.steps_table = QTableWidget(0, 3)
        self.steps_table.setHorizontalHeaderLabels([
            "#",
            i18n.t("pipeline_step", "步骤"),
            i18n.t("pipeline_step_result", "结果"),
        ])
        hdr = self.steps_table.horizontalHeader()
        hdr.setSectionResizeMode(
            0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        self.steps_table.verticalHeader().setVisible(False)
        self.steps_table.setSelectionBehavior(
            QAbstractItemView.SelectRows)
        self.steps_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers)
        self.steps_table.setFixedHeight(180)

        # ---------------- 结果视图 ----------------
        self.result = ResultView(i18n)

        # ---------------- 布局 ----------------
        top = QHBoxLayout()
        top.addWidget(QLabel(i18n.t("expr", "表达式")))
        top.addWidget(self.expr, 1)

        # 输入历史按钮（第 13 轮）
        try:
            from ui.widgets.input_history_widget import (
                InputHistoryButton,
            )
            self.history_btn = InputHistoryButton(
                settings, i18n, "pipeline.expr", self)
            self.history_btn.attach(self.expr)
            top.addWidget(self.history_btn)
        except Exception:
            self.history_btn = None

        top.addWidget(self.examples)
        top.addWidget(self.make_kb_button())

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.calc_btn, 1)
        btn_row.addWidget(self.cancel_btn)

        self.hint = QLabel(i18n.t(
            "pipeline_hint",
            "管道：<初始> | <步骤1> | <步骤2> | ...    "
            "步骤示例：to m / * 2 / round(3) / as fraction"))
        self.hint.setStyleSheet(
            "color: #888; padding-left: 2px;")
        self.hint.setWordWrap(True)

        main = QVBoxLayout(self)
        main.addLayout(top)
        main.addWidget(self.preview)
        main.addWidget(self.hint)
        main.addLayout(btn_row)
        main.addWidget(QLabel(
            i18n.t("pipeline_steps", "步骤")))
        main.addWidget(self.steps_table)
        main.addWidget(QLabel(i18n.t("result", "结果")))
        main.addWidget(self.result, 1)

        install_panel_shortcuts(
            self,
            on_calc=self.calc,
            on_cancel=self.cancel_current,
            on_clear=self._clear,
            on_undo=self.undo,
            expr_widget=self.expr,
            history_getter=self._history_exprs,
        )

        sc_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        sc_undo.setContext(Qt.WidgetWithChildrenShortcut)
        sc_undo.activated.connect(self.undo)
        self._undo_sc = sc_undo

    # ==================================================================
    # 辅助
    # ==================================================================

    def _angle_mode(self) -> str:
        try:
            return self.settings.get(
                "angle_mode", "RAD") or "RAD"
        except Exception:
            return "RAD"

    def _base_path(self) -> str:
        try:
            mw = self.window()
            return getattr(mw, "base_path", "")
        except Exception:
            return ""

    def _rate_provider(self, amount, from_code, to_code):
        """货币换算回调，供 core.pipeline 使用。"""
        base = self._base_path()
        if not base:
            raise RuntimeError("找不到 base_path")
        from core import rates as rates_mod
        data = rates_mod.ensure_fresh(base)
        rates = data.get("rates", {}) or {}
        return rates_mod.convert(
            amount, from_code, to_code, rates)

    def _preview_calc(self, expr):
        s = (expr or "").strip()
        if not s:
            return None
        if not pipe_mod.has_pipe(s):
            try:
                return engine.sci_eval(s, self._angle_mode())
            except Exception:
                return None
        try:
            r = pipe_mod.execute_pipeline(
                s,
                angle_mode=self._angle_mode(),
                rate_provider=self._rate_provider,
            )
            if r.ok:
                return r.final_display or r.final
        except Exception:
            pass
        return None

    def _on_example_chosen(self, _):
        ex = self.examples.currentData()
        if ex:
            self.push_undo()
            self.expr.setText(ex)
            self.expr.setFocus()
            self.calc()

    # ==================================================================
    # 历史
    # ==================================================================

    def _history_exprs(self):
        try:
            rows = self.history.list(
                module="pipeline", limit=50, order="id DESC")
            return [r["expr"] for r in rows if r.get("expr")]
        except Exception:
            return []

    def _clear(self):
        try:
            self.push_undo()
            self.expr.clear()
            self.steps_table.setRowCount(0)
            self.result.show_result("", "")
        except Exception:
            pass

    # ==================================================================
    # 计算
    # ==================================================================

    def calc(self):
        expr = self.expr.text().strip()
        if not expr:
            self.result.show_error(
                InputError("表达式为空",
                           friendly_key="err_empty_expr"))
            return

        self.push_undo()
        self._calc_start = time.time()
        self.result.show_result(
            self.i18n.t("running", "计算中…"), "")
        self.steps_table.setRowCount(0)

        self.run(
            self._compute, expr,
            cancel_btn=self.cancel_btn,
            main_btn=self.calc_btn,
            on_done=self._on_done,
            on_fail=self._on_fail,
            on_cancel=self._on_cancel,
        )

    def _compute(self, expr):
        return pipe_mod.execute_pipeline(
            expr,
            angle_mode=self._angle_mode(),
            rate_provider=self._rate_provider,
        )

    def _on_done(self, r: pipe_mod.PipelineResult):
        try:
            self._fill_steps(r.steps)
        except Exception as e:
            log_exc(e, module="PipelinePanel._on_done.fill")

        elapsed = None
        if self._calc_start is not None:
            elapsed = time.time() - self._calc_start

        if not r.ok:
            err = InputError(r.error or "管道执行失败")
            self.result.show_error(
                err, elapsed=elapsed, retry_cb=self.calc)
            self.add_history(
                self.expr.text(),
                f"ERROR: {r.error}",
                module="pipeline")
            return

        text = r.final_display or str(r.final)
        try:
            latex = engine.format_result(r.final, "latex")
        except Exception:
            latex = ""

        self.result.show_result(text, latex, elapsed=elapsed)
        self.add_history(
            self.expr.text(), text, module="pipeline")

    def _fill_steps(self, steps):
        self.steps_table.setRowCount(0)
        for i, sr in enumerate(steps, 1):
            row = self.steps_table.rowCount()
            self.steps_table.insertRow(row)
            self.steps_table.setItem(
                row, 0, QTableWidgetItem(str(i)))
            self.steps_table.setItem(
                row, 1, QTableWidgetItem(sr.step.raw))
            if sr.ok:
                self.steps_table.setItem(
                    row, 2, QTableWidgetItem(sr.display))
            else:
                item = QTableWidgetItem(f"✗ {sr.error}")
                item.setForeground(Qt.red)
                self.steps_table.setItem(row, 2, item)

    def _on_fail(self, e):
        elapsed = None
        if self._calc_start is not None:
            elapsed = time.time() - self._calc_start
        self.result.show_error(
            e, elapsed=elapsed, retry_cb=self.calc)

    def _on_cancel(self):
        try:
            self.result.show_result(
                self.i18n.t("err_cancelled_task",
                            "计算已取消"), "")
        except Exception:
            pass

    # ==================================================================
    # 设置变更
    # ==================================================================

    def on_settings_changed(self, key=None):
        if key in (None, "angle_mode"):
            try:
                self.preview.refresh(self.expr.text())
            except Exception:
                pass


__all__ = ["PipelinePanel"]