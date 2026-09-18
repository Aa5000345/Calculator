"""工具面板：二维码 / JWT / 正则 / 颜色。"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QFormLayout, QTabWidget, QWidget, QFileDialog,
)

from core import tools_ext as tools
from core.logger import log_exc
from ._common import ResultView
from .base import CalcPanel


class ToolsPanel(CalcPanel):
    module_key = "tools"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)
        self._qr_data = None

        self.result = ResultView(i18n)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_qr_tab(), "QR")
        self.tabs.addTab(self._build_jwt_tab(), "JWT")
        self.tabs.addTab(self._build_regex_tab(),
                         i18n.t("regex", "正则"))
        self.tabs.addTab(self._build_color_tab(),
                         i18n.t("color", "颜色"))

        main = QVBoxLayout(self)
        main.addWidget(self.tabs, 2)
        main.addWidget(self.result, 1)

    # ==================================================================
    # QR
    # ==================================================================

    def _build_qr_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.qr_input = QPlainTextEdit("https://example.com")
        self.qr_input.setFixedHeight(80)
        self.primary_input = self.qr_input

        b_gen = QPushButton(self.i18n.t("generate", "生成"))
        b_save = QPushButton(
            self.i18n.t("save_png", "保存 PNG"))
        b_gen.clicked.connect(self._qr_generate)
        b_save.clicked.connect(self._qr_save)

        self.qr_preview = QLabel()
        self.qr_preview.setMinimumHeight(220)
        self.qr_preview.setAlignment(Qt.AlignCenter)

        v.addWidget(QLabel(self.i18n.t("qr_content", "内容")))
        v.addWidget(self.qr_input)
        row = QHBoxLayout()
        row.addWidget(b_gen)
        row.addWidget(b_save)
        row.addStretch(1)
        v.addLayout(row)
        v.addWidget(self.qr_preview, 1)
        return w

    def _qr_generate(self):
        try:
            data = tools.qrcode_pixmap_bytes(
                self.qr_input.toPlainText())
            pm = QPixmap()
            pm.loadFromData(data, "PNG")
            self.qr_preview.setPixmap(pm)
            self._qr_data = data
            self.result.show_result(
                f"✓ {pm.width()}×{pm.height()}", "")
        except Exception as e:
            self.result.show_error(e)

    def _qr_save(self):
        if self._qr_data is None:
            self._qr_generate()
        if self._qr_data is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save PNG", "qrcode.png", "PNG (*.png)")
        if not path:
            return
        try:
            with open(path, "wb") as f:
                f.write(self._qr_data)
            self.result.show_result(f"✓ {path}", "")
        except Exception as e:
            self.result.show_error(e)

    # ==================================================================
    # JWT
    # ==================================================================

    def _build_jwt_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.jwt_input = QPlainTextEdit()
        self.jwt_input.setFixedHeight(120)
        self.jwt_input.setPlaceholderText(
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
        b = QPushButton(self.i18n.t("decode", "解析"))
        b.clicked.connect(self._jwt_decode)
        v.addWidget(QLabel("Token"))
        v.addWidget(self.jwt_input)
        v.addWidget(b)
        v.addStretch(1)
        return w

    def _jwt_decode(self):
        try:
            r = tools.jwt_decode(
                self.jwt_input.toPlainText())
            s = json.dumps(r, ensure_ascii=False,
                           indent=2, default=str)
            self.result.show_result(s, "")
            self.add_history("jwt", s[:300],
                             module="tools-jwt")
        except Exception as e:
            self.result.show_error(e)

    # ==================================================================
    # 正则
    # ==================================================================

    def _build_regex_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.re_pattern = QLineEdit(r"\d+")
        self.re_flags = QLineEdit("im")
        self.re_text = QPlainTextEdit("hello 123 world 456")
        self.re_text.setFixedHeight(120)
        self.re_repl = QLineEdit("")
        b_test = QPushButton(self.i18n.t("test", "测试"))
        b_repl = QPushButton(self.i18n.t("replace", "替换"))
        b_test.clicked.connect(self._regex_test)
        b_repl.clicked.connect(self._regex_replace)

        form = QFormLayout()
        form.addRow(QLabel("Pattern"), self.re_pattern)
        form.addRow(QLabel("Flags (imsx)"), self.re_flags)
        form.addRow(QLabel("Text"), self.re_text)
        form.addRow(QLabel("Replace with"), self.re_repl)
        row = QHBoxLayout()
        row.addWidget(b_test)
        row.addWidget(b_repl)
        row.addStretch(1)

        v.addLayout(form)
        v.addLayout(row)
        v.addStretch(1)
        return w

    def _regex_test(self):
        try:
            r = tools.regex_test(
                self.re_pattern.text(),
                self.re_text.toPlainText(),
                self.re_flags.text())
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.show_result(s, "")
        except Exception as e:
            self.result.show_error(e)

    def _regex_replace(self):
        try:
            out = tools.regex_replace(
                self.re_pattern.text(),
                self.re_repl.text(),
                self.re_text.toPlainText(),
                self.re_flags.text())
            self.result.show_result(out, "")
        except Exception as e:
            self.result.show_error(e)

    # ==================================================================
    # 颜色
    # ==================================================================

    def _build_color_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.color_input = QLineEdit("#007ACC")
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(60)
        self.color_preview.setStyleSheet(
            "background:#007ACC;border:1px solid #888;"
            "border-radius:4px;")
        self.color_other = QLineEdit("#FFFFFF")
        b1 = QPushButton(self.i18n.t("convert", "转换"))
        b2 = QPushButton(self.i18n.t("contrast", "对比度"))
        b1.clicked.connect(self._color_convert)
        b2.clicked.connect(self._color_contrast)

        form = QFormLayout()
        form.addRow(QLabel(self.i18n.t("color", "颜色")),
                    self.color_input)
        form.addRow(QLabel(""), self.color_preview)
        form.addRow(QLabel(self.i18n.t("other_color", "对比色")),
                    self.color_other)
        row = QHBoxLayout()
        row.addWidget(b1)
        row.addWidget(b2)
        row.addStretch(1)

        v.addLayout(form)
        v.addLayout(row)
        v.addStretch(1)
        return w

    def _color_convert(self):
        try:
            r = tools.color_convert(self.color_input.text())
            self.color_preview.setStyleSheet(
                f"background:{r['hex']};border:1px solid #888;"
                f"border-radius:4px;")
            s = json.dumps({
                "hex": r["hex"],
                "rgb": list(r["rgb"]),
                "hsl": list(r["hsl"]),
            }, ensure_ascii=False, indent=2)
            self.result.show_result(s, "")
            self.add_history(
                self.color_input.text(), r["hex"],
                module="tools-color")
        except Exception as e:
            self.result.show_error(e)

    def _color_contrast(self):
        try:
            r = tools.color_contrast(
                self.color_input.text(),
                self.color_other.text())
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.show_result(s, "")
        except Exception as e:
            self.result.show_error(e)


__all__ = ["ToolsPanel"]