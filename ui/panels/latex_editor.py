"""LaTeX 编辑器面板。"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QSpinBox, QScrollArea, QFileDialog, QMessageBox, QApplication,
)
from matplotlib.figure import Figure
from matplotlib.backends.backend_pdf import PdfPages

from core import latex_ext as latex_mod
from core.logger import log_exc
from ui.latex_widget import LatexLabel
from .base import CalcPanel


class LatexEditorPanel(CalcPanel):
    module_key = "latex"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        self.template = QComboBox()
        self.template.addItem(i18n.t("no_template", "— 无 —"), None)
        for k in sorted(latex_mod.TEMPLATES.keys()):
            self.template.addItem(k, k)
        self.template.currentIndexChanged.connect(self._load_template)

        self.input = QPlainTextEdit(
            r"\int_0^\infty e^{-x^2}\,dx = \frac{\sqrt{\pi}}{2}")
        self.input.setFixedHeight(110)
        self.input.textChanged.connect(self._refresh)

        self.preview = LatexLabel(fontsize=18)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setWidget(self.preview)

        self.fontsize = QSpinBox(); self.fontsize.setRange(8, 72); self.fontsize.setValue(18)
        self.fontsize.valueChanged.connect(self._refresh)

        b_copy = QPushButton(i18n.t("copy_latex", "复制 LaTeX")); b_copy.clicked.connect(self._copy)
        b_png = QPushButton(i18n.t("export_png", "导出 PNG")); b_png.clicked.connect(self.export_png)
        b_svg = QPushButton(i18n.t("export_svg", "导出 SVG")); b_svg.clicked.connect(self.export_svg)
        b_pdf = QPushButton(i18n.t("export_pdf", "导出 PDF")); b_pdf.clicked.connect(self.export_pdf)

        row = QHBoxLayout()
        row.addWidget(QLabel(i18n.t("template", "Template")))
        row.addWidget(self.template, 1)
        row.addWidget(QLabel(i18n.t("font_size", "Font")))
        row.addWidget(self.fontsize)
        for b in (b_copy, b_png, b_svg, b_pdf): row.addWidget(b)

        lay = QVBoxLayout(self)
        lay.addLayout(row)
        lay.addWidget(QLabel("LaTeX"))
        lay.addWidget(self.input)
        lay.addWidget(QLabel(i18n.t("latex_preview", "Preview")))
        lay.addWidget(scroll, 1)

        self._refresh()

    def _load_template(self, _):
        key = self.template.currentData()
        if not key:
            return
        self.input.setPlainText(latex_mod.TEMPLATES.get(key, ""))

    def _refresh(self):
        latex = self.input.toPlainText()
        self.preview.fontsize = self.fontsize.value()
        self.preview.set_latex(latex, latex)

    def set_theme_colors(self, fg, bg, panel):
        try:
            self.preview.set_color(fg)
        except Exception:
            pass

    def _copy(self):
        try:
            QApplication.clipboard().setText(self.input.toPlainText())
            QMessageBox.information(self, "OK", self.i18n.t("copied", "Copied"))
        except Exception as e:
            log_exc(e, module="LatexEditorPanel._copy")

    def export_png(self):
        path, _ = QFileDialog.getSaveFileName(
            self, self.i18n.t("export_png", "Export PNG"),
            "formula.png", "PNG (*.png)")
        if not path:
            return
        try:
            latex_mod.render_png(self.input.toPlainText(), path,
                                 fontsize=self.fontsize.value(), transparent=False)
            QMessageBox.information(self, "OK", path)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def export_svg(self):
        path, _ = QFileDialog.getSaveFileName(
            self, self.i18n.t("export_svg", "Export SVG"),
            "formula.svg", "SVG (*.svg)")
        if not path:
            return
        try:
            latex_mod.render_svg(self.input.toPlainText(), path,
                                 fontsize=self.fontsize.value())
            QMessageBox.information(self, "OK", path)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(
            self, self.i18n.t("export_pdf", "Export PDF"),
            "formula.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            with PdfPages(path) as pdf:
                fig = Figure(figsize=(8, 3))
                fig.text(0.5, 0.5, f"${self.input.toPlainText()}$",
                         ha="center", va="center", fontsize=self.fontsize.value())
                pdf.savefig(fig)
            QMessageBox.information(self, "OK", path)
        except Exception as e:
            log_exc(e, module="LatexEditorPanel.export_pdf")
            QMessageBox.warning(self, "Error", str(e))