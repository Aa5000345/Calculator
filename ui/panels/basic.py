"""基础计算 / 进制转换 / 位运算面板。

合并自：ui/panels/basic.py + ui/panels/base_convert.py
        + ui/panels/bits.py

对外接口（类名保持不变，老 registry.py 无需改动）：
    BasicPanel
    BasePanel
    BitsPanel

依赖（合并后）：
    core.base   —— InputError / log_exc
    core.engine —— basic_calc_smart / format_result / base_convert_float
                   / ascii_convert / endian_swap / float_ieee754
    core.bits   —— to_unsigned / to_signed / twos_complement /
                   bit_bin / bit_hex / bit_op / crc32 / crc16 /
                   hash_text / int_to_bitmap
    ui.shortcuts        —— install_panel_shortcuts
    ui.panels.base      —— CalcPanel
    ui.panels._common   —— ResultView / InlinePreviewBar /
                            friendly_error / _clear_layout
"""
from __future__ import annotations

import json
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor, QImage, QKeySequence, QPixmap, QShortcut,
)
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QSpinBox,
    QTabWidget, QVBoxLayout, QWidget,
)

from core import engine
from core import bits as bitmod
from core.base import InputError, log_exc
from ui.shortcuts import install_panel_shortcuts
from ._common import (
    _clear_layout,
    friendly_error,
    ResultView,
    InlinePreviewBar,
)
from .base import CalcPanel


__all__ = ["BasicPanel", "BasePanel", "BitsPanel"]


# ===========================================================================
# 基础计算
# ===========================================================================

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
    """基础计算面板。

    键盘驱动 + 百分比模板 + 内存槽 + 耗时显示 + 实时预览 +
    智能建议 + 输入历史 + LaTeX 检测 + 差异徽章。
    """

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
        self.fmt_mode.addItem(
            i18n.t("fmt_number", "Number"), "number")
        self.fmt_mode.addItem(
            i18n.t("fmt_sci", "Scientific"), "sci")
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
            b.clicked.connect(
                lambda _, k=i: self._mem_pick(k))
            b.setContextMenuPolicy(Qt.CustomContextMenu)
            b.customContextMenuRequested.connect(
                lambda pos, k=i: self._mem_store(k))
            mrow.addWidget(b)

        # ---------------- 主按钮 ----------------
        self.calc_btn = QPushButton(i18n.t("calc"))
        self.calc_btn.setMinimumHeight(36)
        self.calc_btn.clicked.connect(self.calc)

        self.cancel_btn = QPushButton(
            i18n.t("cancel", "Cancel"))
        self.cancel_btn.setEnabled(False)

        row = QHBoxLayout()
        row.addWidget(self.calc_btn, 1)
        row.addWidget(self.cancel_btn)

        # ---------------- 顶部工具栏 ----------------
        top = QHBoxLayout()
        top.addWidget(QLabel(i18n.t("expr")))
        top.addStretch(1)
        top.addWidget(self.make_kb_button())

        try:
            from ui.widgets.input import InputHistoryButton
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
        self.preview = InlinePreviewBar(
            calc_fn=self._preview_calc)
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
            "Memory (left-click: recall, "
            "right-click: store)")))
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

        # ---------------- 智能建议 ----------------
        try:
            from ui.widgets.input import SuggestionBubble
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
            return self.settings.get(
                "angle_mode", "RAD") or "RAD"
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
                lambda checked=False, a=action:
                self.on_button(a))
            self.grid.addWidget(b, base_row, j)

    def on_settings_changed(self, key=None):
        if key in (None, "button_layout"):
            try:
                self.rebuild_buttons()
            except Exception as e:
                log_exc(
                    e, module="BasicPanel.on_settings_changed")

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
            self.result.text.appendPlainText(
                f"M+ {self.memory}")
            try:
                self.settings.set(
                    "memory", self.memory, notify=True)
            except Exception:
                pass
        elif t == "M-":
            self.memory -= self.current_result()
            self.result.text.appendPlainText(
                f"M- {self.memory}")
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
                self._send_to_unit(self.expr.text())
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
            from ui.shell import bus
            bus().send_to_plot.emit(expr)
        except Exception:
            pass

    def _send_to_unit(self, text: str):
        try:
            from ui.shell import bus
            bus().send_to_unit.emit(text)
        except Exception:
            pass

    def _send_to_pipeline(self, text: str):
        try:
            mw = self.window()
            switch = getattr(mw, "_switch_by_key_pub", None)
            if callable(switch):
                switch("pipeline")
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

        # LaTeX 检测
        try:
            from core import latex as lp
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


# ===========================================================================
# 进制转换
# ===========================================================================

class BasePanel(CalcPanel):
    """进制转换面板。

    - Live Tab：4 个进制输入框实时联动
    - Convert Tab：单值转换（支持 2~36 进制、小数）
    - ASCII Tab：文本 ↔ 编码
    - Bit tools Tab：字节序交换、IEEE 754
    """

    module_key = "base"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)
        self._live = True
        self._live_map: dict = {}

        # ---------------- 4 个进制输入框 ----------------
        self.in_dec = QLineEdit("255")
        self.in_hex = QLineEdit("FF")
        self.in_bin = QLineEdit("11111111")
        self.in_oct = QLineEdit("377")
        for w, base in ((self.in_dec, 10), (self.in_hex, 16),
                        (self.in_bin, 2), (self.in_oct, 8)):
            self._live_map[w] = base
            w.textChanged.connect(
                lambda _t, b=base, ww=w:
                self._on_live(b, ww))

        # ---------------- 通用转换 ----------------
        self.value = QLineEdit("255")
        self.primary_input = self.value
        self.from_b = QLineEdit("10")
        self.to_b = QLineEdit("16")
        self.precision = QSpinBox()
        self.precision.setRange(1, 32)
        self.precision.setValue(12)
        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)

        # ---------------- ASCII ----------------
        self.ascii_text = QPlainTextEdit("Hello")
        self.ascii_text.setFixedHeight(60)
        self.ascii_mode = QComboBox()
        self.ascii_mode.addItem(
            i18n.t("ascii_encode", "Encode"), "encode")
        self.ascii_mode.addItem(
            i18n.t("ascii_decode", "Decode"), "decode")
        b_ascii = QPushButton(
            i18n.t("ascii_convert", "Convert"))
        b_ascii.clicked.connect(self._do_ascii)

        # ---------------- Endian / IEEE ----------------
        self.es_value = QLineEdit("0x12345678")
        self.es_width = QSpinBox()
        self.es_width.setRange(8, 128)
        self.es_width.setSingleStep(8)
        self.es_width.setValue(32)
        b_swap = QPushButton(
            i18n.t("endian_swap", "Endian swap"))
        b_swap.clicked.connect(self._do_endian)

        self.ieee_value = QLineEdit("3.14")
        b_ieee = QPushButton("IEEE 754")
        b_ieee.clicked.connect(self._do_ieee)

        btn = QPushButton(i18n.t("convert"))
        btn.clicked.connect(self.convert)

        # ---------------- 布局 ----------------
        form = QGridLayout()
        for r, (lbl, w) in enumerate((
                ("Dec", self.in_dec), ("Hex", self.in_hex),
                ("Bin", self.in_bin), ("Oct", self.in_oct))):
            form.addWidget(QLabel(lbl), r, 0)
            form.addWidget(w, r, 1)

        form2 = QGridLayout()
        form2.addWidget(QLabel(i18n.t("value")), 0, 0)
        form2.addWidget(self.value, 0, 1)
        form2.addWidget(QLabel(i18n.t("from")), 1, 0)
        form2.addWidget(self.from_b, 1, 1)
        form2.addWidget(QLabel(i18n.t("to")), 2, 0)
        form2.addWidget(self.to_b, 2, 1)
        form2.addWidget(
            QLabel(i18n.t("precision", "Precision")), 3, 0)
        form2.addWidget(self.precision, 3, 1)

        ascii_row = QHBoxLayout()
        ascii_row.addWidget(self.ascii_mode)
        ascii_row.addWidget(b_ascii)
        ascii_row.addStretch(1)

        endian_row = QHBoxLayout()
        endian_row.addWidget(QLabel("Value"))
        endian_row.addWidget(self.es_value, 1)
        endian_row.addWidget(QLabel("Bits"))
        endian_row.addWidget(self.es_width)
        endian_row.addWidget(b_swap)

        ieee_row = QHBoxLayout()
        ieee_row.addWidget(QLabel("Float"))
        ieee_row.addWidget(self.ieee_value, 1)
        ieee_row.addWidget(b_ieee)

        tabs = QTabWidget()
        w1 = QWidget()
        v1 = QVBoxLayout(w1)
        v1.addLayout(form)
        v1.addWidget(QLabel(
            i18n.t("live_hint", "4 bases stay in sync")))
        tabs.addTab(w1, i18n.t("live", "Live"))

        w2 = QWidget()
        v2 = QVBoxLayout(w2)
        v2.addLayout(form2)
        v2.addWidget(btn)
        tabs.addTab(w2, i18n.t("convert", "Convert"))

        w3 = QWidget()
        v3 = QVBoxLayout(w3)
        v3.addWidget(QLabel("ASCII / Unicode"))
        v3.addWidget(self.ascii_text)
        v3.addLayout(ascii_row)
        tabs.addTab(w3, "ASCII")

        w4 = QWidget()
        v4 = QVBoxLayout(w4)
        v4.addLayout(endian_row)
        v4.addLayout(ieee_row)
        v4.addStretch(1)
        tabs.addTab(w4, i18n.t("bits_extra", "Bit tools"))

        main = QVBoxLayout(self)
        main.addWidget(tabs)
        main.addWidget(QLabel(i18n.t("result")))
        main.addWidget(self.result, 1)

        sc_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        sc_undo.setContext(Qt.WidgetWithChildrenShortcut)
        sc_undo.activated.connect(self.undo)
        self._undo_sc = sc_undo

    # ------------------------------------------------------------------

    def _on_live(self, base: int, sender_widget=None):
        """实时联动 4 个进制输入框。"""
        if not self._live:
            return
        if sender_widget is None:
            return
        try:
            text = sender_widget.text().strip()
        except Exception:
            return
        if not text:
            return

        self._live = False
        try:
            if base == 10:
                for w, b in self._live_map.items():
                    if w is sender_widget:
                        continue
                    try:
                        w.setText(engine.base_convert_float(
                            text, 10, b, 12))
                    except Exception:
                        pass
            else:
                try:
                    dec = engine.base_convert_float(
                        text, base, 10, 12)
                except Exception:
                    return
                self.in_dec.setText(dec)
                for w, b in self._live_map.items():
                    if w is sender_widget or b == 10:
                        continue
                    try:
                        w.setText(engine.base_convert_float(
                            dec, 10, b, 12))
                    except Exception:
                        pass
        finally:
            self._live = True

    # ------------------------------------------------------------------

    def convert(self):
        try:
            self.push_undo()
            r = engine.base_convert_float(
                self.value.text(), self.from_b.text(),
                self.to_b.text(), self.precision.value())
            self.result.setPlainText(r)
            self.add_history(
                f"{self.value.text()}({self.from_b.text()}) "
                f"-> {self.to_b.text()}",
                r, module="base")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "base"))

    def _do_ascii(self):
        try:
            self.push_undo()
            r = engine.ascii_convert(
                self.ascii_text.toPlainText(),
                self.ascii_mode.currentData())
            self.result.setPlainText(r)
            self.add_history(
                self.ascii_mode.currentData(), r[:200],
                module="ascii")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "base"))

    def _do_endian(self):
        try:
            self.push_undo()
            raw = self.es_value.text().strip()
            v = (int(raw, 16) if raw.lower().startswith("0x")
                 else int(raw, 0))
            swapped, be, le = engine.endian_swap(
                v, self.es_width.value())
            text = (f"原值(十进制): {v}\n"
                    f"交换后(十进制): {swapped}\n"
                    f"BE hex: 0x{be}\nLE hex: 0x{le}")
            self.result.setPlainText(text)
            self.add_history(raw, text[:200], module="endian")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "base"))

    def _do_ieee(self):
        try:
            self.push_undo()
            info = engine.float_ieee754(self.ieee_value.text())
            text = "\n".join(f"{k}: {v}"
                             for k, v in info.items())
            self.result.setPlainText(text)
            self.add_history(
                self.ieee_value.text(), text[:200],
                module="ieee")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "base"))


# ===========================================================================
# 位运算
# ===========================================================================

class BitsPanel(CalcPanel):
    """位运算面板。

    Tab：Operations / CRC / Hash / Bitmap。
    """

    module_key = "bits"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)
        self.bitmap_label = QLabel()
        self.bitmap_label.setMinimumHeight(80)
        self.bitmap_label.setAlignment(
            Qt.AlignLeft | Qt.AlignTop)

        tabs = QTabWidget()
        tabs.addTab(self._build_op_tab(),
                    i18n.t("bit_op", "Operations"))
        tabs.addTab(self._build_crc_tab(), "CRC")
        tabs.addTab(self._build_hash_tab(), "Hash")
        tabs.addTab(self._build_bitmap_tab(),
                    i18n.t("bitmap", "Bitmap"))

        main = QVBoxLayout(self)
        main.addWidget(tabs)
        main.addWidget(QLabel(i18n.t("result")))
        main.addWidget(self.result, 1)

    # ==================================================================
    # 位运算
    # ==================================================================

    def _build_op_tab(self):
        self.a = QLineEdit("-1")
        self.b = QLineEdit("5")
        self.width = QSpinBox()
        self.width.setRange(4, 128)
        self.width.setValue(32)
        self.op = QComboBox()
        self.op.addItems(
            ["and", "or", "xor", "not", "shl", "shr"])

        b_unsigned = QPushButton(
            self.i18n.t("to_unsigned", "To unsigned"))
        b_signed = QPushButton(
            self.i18n.t("to_signed", "To signed"))
        b_comp = QPushButton(
            self.i18n.t("twos_complement", "Two's complement"))
        b_op = QPushButton(self.i18n.t("bit_op", "Apply"))
        b_unsigned.clicked.connect(self.do_unsigned)
        b_signed.clicked.connect(self.do_signed)
        b_comp.clicked.connect(self.do_comp)
        b_op.clicked.connect(self.do_op)

        w = QWidget()
        f = QFormLayout(w)
        f.addRow(QLabel("A"), self.a)
        f.addRow(QLabel("B"), self.b)
        f.addRow(QLabel(
            self.i18n.t("bit_width", "Width")), self.width)
        f.addRow(QLabel(
            self.i18n.t("bit_op", "Op")), self.op)
        row = QHBoxLayout()
        for btn in (b_unsigned, b_signed, b_comp):
            row.addWidget(btn)
        f.addRow(row)
        f.addRow(b_op)
        return w

    def _show(self, obj, tag="bits"):
        s = json.dumps(obj, ensure_ascii=False,
                       indent=2, default=str)
        self.result.setPlainText(s)
        self.add_history(
            self.op.currentText() if hasattr(self, "op")
            else tag,
            s, module=tag)

    def do_unsigned(self):
        try:
            v = bitmod.to_unsigned(
                int(self.a.text()), self.width.value())
            self._show({
                "unsigned": v,
                "bin": bitmod.bit_bin(v, self.width.value()),
                "hex": bitmod.bit_hex(v, self.width.value()),
            })
        except Exception as e:
            self.result.setPlainText(str(e))

    def do_signed(self):
        try:
            v = bitmod.to_signed(
                int(self.a.text()), self.width.value())
            self._show({"signed": v})
        except Exception as e:
            self.result.setPlainText(str(e))

    def do_comp(self):
        try:
            raw = int(self.a.text())
            v = bitmod.twos_complement(
                raw, self.width.value())
            self._show({
                "twos_complement": v,
                "bin": bitmod.bit_bin(raw, self.width.value()),
                "hex": bitmod.bit_hex(raw, self.width.value()),
            })
        except Exception as e:
            self.result.setPlainText(str(e))

    def do_op(self):
        try:
            w = self.width.value()
            r = bitmod.bit_op(
                int(self.a.text()), int(self.b.text()),
                self.op.currentText(), w)
            self._show({
                "result": r,
                "bin": format(r, f"0{w}b"),
                "hex": format(r, f"0{(w + 3) // 4}X"),
                "signed": bitmod.to_signed(r, w),
            })
        except Exception as e:
            self.result.setPlainText(str(e))

    # ==================================================================
    # CRC
    # ==================================================================

    def _build_crc_tab(self):
        self.crc_text = QLineEdit("hello world")
        self.crc_kind = QComboBox()
        self.crc_kind.addItems(
            ["crc32", "crc16_ccitt", "crc16_modbus"])
        b = QPushButton("CRC")
        b.clicked.connect(self._do_crc)
        w = QWidget()
        f = QFormLayout(w)
        f.addRow(QLabel("Text"), self.crc_text)
        f.addRow(QLabel("Type"), self.crc_kind)
        f.addRow(b)
        return w

    def _do_crc(self):
        try:
            kind = self.crc_kind.currentText()
            text = self.crc_text.text()
            if kind == "crc32":
                r = bitmod.crc32(text)
            else:
                sub = kind.split("_", 1)[1]
                r = bitmod.crc16(text, sub)
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history(
                f"{kind}:{text[:30]}", s, module="bits-crc")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "bits"))

    # ==================================================================
    # Hash
    # ==================================================================

    def _build_hash_tab(self):
        self.hash_text = QPlainTextEdit("hello world")
        self.hash_text.setFixedHeight(80)
        self.hash_algo = QComboBox()
        for k in ("md5", "sha1", "sha224", "sha256",
                  "sha384", "sha512",
                  "sha3_256", "sha3_512",
                  "blake2b", "blake2s"):
            self.hash_algo.addItem(k)
        self.hash_upper = QCheckBox(
            self.i18n.t("uppercase", "Uppercase"))
        b = QPushButton("Hash")
        b.clicked.connect(self._do_hash)
        w = QWidget()
        f = QFormLayout(w)
        f.addRow(QLabel("Text"), self.hash_text)
        f.addRow(QLabel("Algorithm"), self.hash_algo)
        f.addRow(QLabel(""), self.hash_upper)
        f.addRow(b)
        return w

    def _do_hash(self):
        try:
            r = bitmod.hash_text(
                self.hash_text.toPlainText(),
                self.hash_algo.currentText(),
                self.hash_upper.isChecked())
            self.result.setPlainText(
                json.dumps(r, ensure_ascii=False, indent=2))
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "bits"))

    # ==================================================================
    # 位图
    # ==================================================================

    def _build_bitmap_tab(self):
        self.bm_value = QLineEdit("0xDEADBEEF")
        self.bm_width = QSpinBox()
        self.bm_width.setRange(4, 4096)
        self.bm_width.setValue(32)
        b = QPushButton(self.i18n.t("render", "Render"))
        b.clicked.connect(self._do_bitmap)
        w = QWidget()
        f = QFormLayout(w)
        f.addRow(QLabel("Value (int/hex)"), self.bm_value)
        f.addRow(QLabel("Width"), self.bm_width)
        f.addRow(b)
        f.addRow(self.bitmap_label)
        return w

    def _do_bitmap(self):
        try:
            raw = self.bm_value.text().strip()
            v = (int(raw, 16)
                 if raw.lower().startswith("0x")
                 else int(raw, 0))
            info = bitmod.int_to_bitmap(v, self.bm_width.value())
            self._render_bitmap(info)
            s = json.dumps({
                "width": info["width"],
                "cols": info["cols"],
                "rows": info["rows"],
                "bits_first_row": info["bits"][0][:32],
            }, ensure_ascii=False, indent=2)
            self.result.setPlainText(s)
            self.add_history(raw, s[:200],
                             module="bits-bitmap")
        except Exception as e:
            self.result.setPlainText(
                friendly_error(self.i18n, e, "bits"))

    def _render_bitmap(self, info):
        cols = info["cols"]
        rows = info["rows"]
        cell = 8
        img = QImage(cols * cell, rows * cell,
                     QImage.Format_RGB32)
        img.fill(QColor("#111111"))
        for r in range(rows):
            for c in range(cols):
                color = (QColor("#00e0ff")
                         if info["bits"][r][c]
                         else QColor("#222222"))
                for dy in range(cell):
                    for dx in range(cell):
                        img.setPixelColor(
                            c * cell + dx,
                            r * cell + dy, color)
        pix = QPixmap.fromImage(img)
        self.bitmap_label.setPixmap(pix)
        self.bitmap_label.resize(pix.size())