"""位运算面板。"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QFormLayout, QComboBox, QSpinBox, QCheckBox,
    QTabWidget, QWidget,
)

from core import bits as bitmod
from core import bits_ext as bit_ext
from ._common import friendly_error
from .base import CalcPanel


class BitsPanel(CalcPanel):
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
        self.op.addItems(["and", "or", "xor", "not", "shl", "shr"])

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
            v = bitmod.twos_complement(raw, self.width.value())
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
                r = bit_ext.crc32(text)
            else:
                sub = kind.split("_", 1)[1]
                r = bit_ext.crc16(text, sub)
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
            r = bit_ext.hash_text(
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
            info = bit_ext.int_to_bitmap(v, self.bm_width.value())
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


__all__ = ["BitsPanel"]