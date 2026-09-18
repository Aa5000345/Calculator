"""基础计算面板：键盘驱动 + 百分比模板 + 内存槽 + 耗时显示 +
实时预览 + 智能建议 + 输入历史 + LaTeX 检测 + 差异徽章。

变更历史：
- 第 1 轮：初版
- 第 3 轮：primary_input / push_undo / Ctrl+Z
- 第 6 轮：LaTeX 检测（looks_like_latex）
- 第 9 轮：SuggestionBubble
- 第 13 轮：InputHistoryButton
- 第 17 轮：DiffBadge（在 ResultView 内部，自动生效）
"""
from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QGridLayout, QComboBox, QWidget,
)

from core import engine
from core.errors import InputError
from core.logger import log_exc
from ui.shortcuts import install_panel_shortcuts
from ._common import (
    _clear_layout, friendly_error, ResultView, InlinePreviewBar,
)
from .base import CalcPanel


class _CalcLineEdit(QLineEdit):
    """'=' 键直接输入 '+'（无需 Shift）。"""

    def keyPressEvent(self, event):
        key = event.key()
        mods = event.modifiers()
        if key == Qt.Key_Equal and not (mods & Qt.ShiftModifier):
            self.insert("+")
            return
        super().keyPressEvent(event)


class BasicPanel(CalcPanel):
    module_key = "basic"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)
        self._calc_start = None

        self.memory = 0.0
        self.mem_slots = {i: 0.0 for i in range(1, 10)}

        # ---------------- 输入框 ----------------
        self.expr = _CalcLineEdit()
        self.expr.setText(settings.get_draft("basic_expr", ""))
        self.expr.textChanged.connect(
            lambda t: settings.set_draft("basic_expr", t))
        self.expr.returnPressed.connect(self.calc)
        self.primary_input = self.expr

        # ---------------- 结果格式化 ----------------
        self.fmt_mode = QComboBox()
        self.fmt_mode.addItem(i18n.t("fmt_auto", "Auto"), "auto")
        self.fmt_mode.addItem(i18n.t("fmt_number", "Number"), "number")
        self.fmt_mode.addItem(i18n.t("fmt_sci", "Scientific"), "sci")
        self.fmt_mode.addItem(
            i18n.t("fmt_fraction", "Fraction"), "fraction")
        self.fmt_mode.addItem(
            i18n.t("fmt_percent", "Percent"), "percent")
        self.fmt_mode.setCurrentIndex(
            max(0, self.fmt_mode.findData(
                settings.get("basic_fmt_mode", "auto"))))
        self.fmt_mode.currentIndexChanged.connect(
            lambda _: settings.set(
                "basic_fmt_mode", self.fmt_mode.currentData()))

        # ---------------- 按钮区 ----------------
        self.btn_box = QWidget()
        self.grid = QGridLayout(self.btn_box)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(4)
        self.rebuild_buttons()

        # ---------------- 内存槽 ----------------
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

        # ---------------- 主按钮 ----------------
        self.calc_btn = QPushButton(i18n.t("calc"))
        self.calc_btn.setMinimumHeight(36)
        self.calc_btn.clicked.connect(self.calc)

        self.cancel_btn = QPushButton(i18n.t("cancel", "Cancel"))
        self.cancel_btn.setEnabled(False)

        row = QHBoxLayout()
        row.addWidget(self.calc_btn, 1)
        row.addWidget(self.cancel_btn)

        # ---------------- 顶部工具栏 ----------------
        top = QHBoxLayout()
        top.addWidget(QLabel(i18n.t("expr")))
        top.addStretch(1)
        top.addWidget(self.make_kb_button())

        # 输入历史按钮（第 13 轮）
        try:
            from ui.widgets.input_history_widget import (
                InputHistoryButton,
            )
            self.history_btn = InputHistoryButton(
                settings, i18n, "basic.expr", self)
            self.history_btn.attach(self.expr)
            top.addWidget(self.history_btn)
        except Exception:
            self.history_btn = None

        top.addWidget(self.fmt_mode)

        # ---------------- 提示行 ----------------
        self.hint = QLabel("")
        self.hint.setStyleSheet("color: #888; padding-left: 2px;")
        self._update_hint()

        # ---------------- 实时预览 ----------------
        self.preview = InlinePreviewBar(calc_fn=self._preview_calc)
        self.preview.attach(
            self.expr,
            enabled_getter=lambda: bool(
                self.settings.get("inline_preview", True)))

        # ---------------- 结果视图 ----------------
        self.result = ResultView(i18n)

        # ---------------- 主布局 ----------------
        main = QVBoxLayout(self)
        main.addLayout(top)
        main.addWidget(self.expr)
        main.addWidget(self.preview)
        main.addWidget(self.hint)
        main.addWidget(self.btn_box)
        main.addWidget(QLabel(i18n.t(
            "memory_hint",
            "Memory (left-click: recall, right-click: store)")))
        main.addWidget(self.mem_box)
        main.addLayout(row)
        main.addWidget(QLabel(i18n.t("result")))
        main.addWidget(self.result, 1)

        # ---------------- 快捷键 ----------------
        install_panel_shortcuts(
            self,
            on_calc=self.calc,
            on_cancel=self.cancel_current,
            on_clear=self._clear,
            on_undo=self.undo,
            expr_widget=self.expr,
            history_getter=self._history_exprs,
        )

        sc = QShortcut(QKeySequence(Qt.Key_Escape), self.expr)
        sc.setContext(Qt.WidgetShortcut)
        sc.activated.connect(self._clear)
        self._esc_sc = sc

        sc_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        sc_undo.setContext(Qt.WidgetWithChildrenShortcut)
        sc_undo.activated.connect(self.undo)
        self._undo_sc = sc_undo

        self.expr.textChanged.connect(self._update_hint)

        # ---------------- 智能建议（第 9 轮） ----------------
        try:
            from ui.widgets.suggestion_widget import (
                SuggestionBubble,
            )
            self.suggest_bubble = SuggestionBubble(
                settings, i18n, self)
            self.suggest_bubble.attach(
                self.expr,
                module_key="basic",
                history_getter=self._history_exprs)
            self.suggest_bubble.suggestion_clicked.connect(
                self._on_suggestion)
        except Exception as e:
            log_exc(e, module="BasicPanel.suggest_init")
            self.suggest_bubble = None

    # ==================================================================
    # 角度 / 预览
    # ==================================================================

    def _angle_mode(self) -> str:
        try:
            return self.settings.get("angle_mode", "RAD") or "RAD"
        except Exception:
            return "RAD"

    def _preview_calc(self, expr):
        try:
            value, _desc = engine.basic_calc_smart(
                expr, self._angle_mode())
            return value
        except Exception:
            return None

    # ==================================================================
    # 内存槽
    # ==================================================================

    def _mem_pick(self, k):
        try:
            self.push_undo()
            self.expr.insert(str(self.mem_slots[k]))
        except Exception:
            pass

    def _mem_store(self, k):
        try:
            v = self.current_result()
            self.mem_slots[k] = v
            self.result.text.appendPlainText(f"M{k} ← {v}")
            try:
                self.settings.set("memory", v, notify=True)
            except Exception:
                pass
        except Exception:
            pass

    def current_result(self):
        try:
            return float(
                self.result.text.toPlainText().splitlines()[-1])
        except Exception:
            return 0.0

    # ==================================================================
    # 按钮
    # ==================================================================

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
        if t not in ("C", "=", "M+", "M-", "MR", "MC"):
            self.push_undo()

        if t == "C":
            self.push_undo()
            self.expr.clear()
            self.result.show_result("", "")
        elif t == "=":
            self.calc()
        elif t == "M+":
            self.memory += self.current_result()
            self.result.text.appendPlainText(f"M+ {self.memory}")
            try:
                self.settings.set(
                    "memory", self.memory, notify=True)
            except Exception:
                pass
        elif t == "M-":
            self.memory -= self.current_result()
            self.result.text.appendPlainText(f"M- {self.memory}")
            try:
                self.settings.set(
                    "memory", self.memory, notify=True)
            except Exception:
                pass
        elif t == "MR":
            self.push_undo()
            self.expr.insert(str(self.memory))
        elif t == "MC":
            self.memory = 0
            try:
                self.settings.set("memory", 0, notify=True)
            except Exception:
                pass
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
        self.expr.setFocus()
        self.expr.selectAll()

    # ==================================================================
    # 历史提示
    # ==================================================================

    def _update_hint(self, *_):
        try:
            cur = self.expr.text().strip()
            if not cur or len(cur) < 2:
                self.hint.setText("")
                return
            rows = self.history.list(
                module="basic", search=cur, limit=3,
                order="id DESC")
            matches = [r["expr"] for r in rows if r.get("expr")]
            if not matches:
                self.hint.setText("")
                return
            self.hint.setText(
                self.i18n.t("recent_matches", "最近") + ": "
                + "   ".join(matches[:3]))
        except Exception:
            self.hint.setText("")

    def _history_exprs(self):
        try:
            rows = self.history.list(
                module="basic", limit=50, order="id DESC")
            return [r["expr"] for r in rows if r.get("expr")]
        except Exception:
            return []

    # ==================================================================
    # 智能建议
    # ==================================================================

    def _on_suggestion(self, action: str, payload: dict):
        try:
            if action == "plot":
                expr = payload.get("expr") or ""
                self._send_to_plot(expr)
            elif action == "convert":
                self._send_to_unit(
                    self.expr.text())
            elif action == "send_unit":
                self._send_to_unit(payload.get("text") or "")
            elif action == "send_pipeline":
                self._send_to_pipeline(
                    payload.get("text") or "")
            elif action == "recall":
                expr = payload.get("expr") or ""
                if expr:
                    self.push_undo()
                    self.expr.setText(expr)
                    self.expr.setFocus()
            elif action == "replace":
                expr = payload.get("expr") or ""
                if expr:
                    self.push_undo()
                    self.expr.setText(expr)
                    self.expr.setFocus()
        except Exception as e:
            log_exc(e, module="BasicPanel._on_suggestion")

    def _send_to_plot(self, expr: str):
        try:
            from ui.signals import bus
            bus().send_to_plot.emit(expr)
        except Exception:
            pass

    def _send_to_unit(self, text: str):
        try:
            from ui.signals import bus
            bus().send_to_unit.emit(text)
        except Exception:
            pass

    def _send_to_pipeline(self, text: str):
        try:
            mw = self.window()
            switch = getattr(mw, "_switch_by_key_pub", None)
            if callable(switch):
                switch("pipeline")
            panel = None
            panels = getattr(mw, "_panels", {})
            panel = panels.get("pipeline")
            if panel is not None:
                w = getattr(panel, "primary_input", None)
                if w is not None and hasattr(w, "setText"):
                    w.setText(str(text))
        except Exception:
            pass

    # ==================================================================
    # 清空 / 计算
    # ==================================================================

    def _clear(self):
        try:
            self.push_undo()
            self.expr.clear()
            self.result.show_result("", "")
        except Exception:
            pass

    def calc(self):
        expr = self.expr.text()
        if not expr.strip():
            self.result.show_error(
                InputError("表达式为空",
                           friendly_key="err_empty_expr"))
            return

        # LaTeX 检测（第 6 轮）
        try:
            from core import latex_parser as lp
            if lp.looks_like_latex(expr):
                r = lp.latex_to_expr(expr)
                if r.ok and r.expr:
                    self.expr.setText(r.expr)
                    expr = r.expr
        except Exception:
            pass

        self.result.show_result(
            self.i18n.t("running", "Running…"), "")
        self._calc_start = time.time()
        angle = self._angle_mode()
        self.run(
            engine.basic_calc_smart, expr, angle,
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
                text = engine.format_result(
                    value, "text", digits=6)
            elif mode == "sci":
                text = engine.format_result(
                    value, "text", digits=6, sci=True)
            elif mode == "fraction":
                text = engine.format_result(
                    value, "text", fraction=True)
            elif mode == "percent":
                text = engine.format_result(
                    value, "text", percent=True)
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
        elapsed = None
        if self._calc_start is not None:
            elapsed = time.time() - self._calc_start
        self.result.show_result(text, "", elapsed=elapsed)
        self.add_history(self.expr.text(), text, module="basic")
        self._update_hint()

        # 通知智能建议气泡最新结果
        if getattr(self, "suggest_bubble", None) is not None:
            try:
                self.suggest_bubble.set_last_result(text)
            except Exception:
                pass

    def _on_fail(self, e):
        elapsed = None
        if self._calc_start is not None:
            elapsed = time.time() - self._calc_start
        self.result.show_error(e, elapsed=elapsed,
                               retry_cb=self.calc)

    def _on_cancel(self):
        self.result.show_result(
            self.i18n.t("err_cancelled_task",
                        "Calculation cancelled"), "")


__all__ = ["BasicPanel"]