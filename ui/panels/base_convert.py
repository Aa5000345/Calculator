"""进制转换面板。"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QGridLayout, QComboBox, QSpinBox, QTabWidget, QWidget,
)

from core import engine
from ._common import friendly_error
from .base import CalcPanel


class BasePanel(CalcPanel):
    module_key = "base"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)
        self._live = True
        # 显式保存 widget -> base 的映射，避免 sender() 脆弱
        self._live_map: dict = {}

        self.in_dec = QLineEdit("255")
        self.in_hex = QLineEdit("FF")
        self.in_bin = QLineEdit("11111111")
        self.in_oct = QLineEdit("377")
        for w, base in ((self.in_dec, 10), (self.in_hex, 16),
                        (self.in_bin, 2), (self.in_oct, 8)):
            self._live_map[w] = base
            # 使用 lambda 显式捕获 (base, widget)，彻底摆脱 sender()
            w.textChanged.connect(
                lambda _t, b=base, ww=w: self._on_live(b, ww))

        self.value = QLineEdit("255")
        self.from_b = QLineEdit("10")
        self.to_b = QLineEdit("16")
        self.precision = QSpinBox()
        self.precision.setRange(1, 32)
        self.precision.setValue(12)
        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)

        self.ascii_text = QPlainTextEdit("Hello")
        self.ascii_text.setFixedHeight(60)
        self.ascii_mode = QComboBox()
        self.ascii_mode.addItem(i18n.t("ascii_encode", "Encode"), "encode")
        self.ascii_mode.addItem(i18n.t("ascii_decode", "Decode"), "decode")
        b_ascii = QPushButton(i18n.t("ascii_convert", "Convert"))
        b_ascii.clicked.connect(self._do_ascii)

        self.es_value = QLineEdit("0x12345678")
        self.es_width = QSpinBox()
        self.es_width.setRange(8, 128)
        self.es_width.setSingleStep(8)
        self.es_width.setValue(32)
        b_swap = QPushButton(i18n.t("endian_swap", "Endian swap"))
        b_swap.clicked.connect(self._do_endian)

        self.ieee_value = QLineEdit("3.14")
        b_ieee = QPushButton("IEEE 754")
        b_ieee.clicked.connect(self._do_ieee)

        btn = QPushButton(i18n.t("convert"))
        btn.clicked.connect(self.convert)

        form = QGridLayout()
        for r, (lbl, w) in enumerate((("Dec", self.in_dec), ("Hex", self.in_hex),
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
        form2.addWidget(QLabel(i18n.t("precision", "Precision")), 3, 0)
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
        w1 = QWidget(); v1 = QVBoxLayout(w1)
        v1.addLayout(form)
        v1.addWidget(QLabel(i18n.t("live_hint", "4 bases stay in sync")))
        tabs.addTab(w1, i18n.t("live", "Live"))

        w2 = QWidget(); v2 = QVBoxLayout(w2)
        v2.addLayout(form2); v2.addWidget(btn)
        tabs.addTab(w2, i18n.t("convert", "Convert"))

        w3 = QWidget(); v3 = QVBoxLayout(w3)
        v3.addWidget(QLabel("ASCII / Unicode"))
        v3.addWidget(self.ascii_text)
        v3.addLayout(ascii_row)
        tabs.addTab(w3, "ASCII")

        w4 = QWidget(); v4 = QVBoxLayout(w4)
        v4.addLayout(endian_row); v4.addLayout(ieee_row); v4.addStretch(1)
        tabs.addTab(w4, i18n.t("bits_extra", "Bit tools"))

        main = QVBoxLayout(self)
        main.addWidget(tabs)
        main.addWidget(QLabel(i18n.t("result")))
        main.addWidget(self.result, 1)

    # ------------------------------------------------------------------

    def _on_live(self, base: int, sender_widget=None):
        """实时联动 4 个进制输入框。

        修复：
        - 使用显式 sender_widget，而非脆弱的 self.sender()。
        - 支持小数：使用 base_convert_float 而非 base_convert。
        - 无论源进制是什么，全部转换为十进制再做中转，保证精度一致。
        """
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
                # 源为十进制：向其他三个目标进制转换
                for w, b in self._live_map.items():
                    if w is sender_widget:
                        continue
                    try:
                        w.setText(engine.base_convert_float(
                            text, 10, b, 12))
                    except Exception:
                        pass
            else:
                # 源为其他进制：先转十进制，再分发
                try:
                    dec = engine.base_convert_float(text, base, 10, 12)
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
    # 其余方法保持不变（convert / _do_ascii / _do_endian / _do_ieee）
    # ------------------------------------------------------------------

    def convert(self):
        try:
            r = engine.base_convert_float(
                self.value.text(), self.from_b.text(), self.to_b.text(),
                self.precision.value())
            self.result.setPlainText(r)
            self.add_history(
                f"{self.value.text()}({self.from_b.text()}) -> {self.to_b.text()}",
                r, module="base")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "base"))

    def _do_ascii(self):
        try:
            r = engine.ascii_convert(self.ascii_text.toPlainText(),
                                     self.ascii_mode.currentData())
            self.result.setPlainText(r)
            self.add_history(self.ascii_mode.currentData(), r[:200],
                             module="ascii")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "base"))

    def _do_endian(self):
        try:
            raw = self.es_value.text().strip()
            v = int(raw, 16) if raw.lower().startswith("0x") else int(raw, 0)
            swapped, be, le = engine.endian_swap(v, self.es_width.value())
            text = (f"原值(十进制): {v}\n交换后(十进制): {swapped}\n"
                    f"BE hex: 0x{be}\nLE hex: 0x{le}")
            self.result.setPlainText(text)
            self.add_history(raw, text[:200], module="endian")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "base"))

    def _do_ieee(self):
        try:
            info = engine.float_ieee754(self.ieee_value.text())
            text = "\n".join(f"{k}: {v}" for k, v in info.items())
            self.result.setPlainText(text)
            self.add_history(self.ieee_value.text(), text[:200],
                             module="ieee")
        except Exception as e:
            self.result.setPlainText(friendly_error(self.i18n, e, "base"))