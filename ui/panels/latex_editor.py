"""LaTeX 编辑器面板。

变更历史：
- 第 6 轮：新增「→ 表达式」按钮（LaTeX → SymPy 表达式）
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QSpinBox, QScrollArea, QFileDialog, QMessageBox,
    QApplication, QDialog, QDialogButtonBox, QLineEdit,
)
from matplotlib.figure import Figure
from matplotlib.backends.backend_pdf import PdfPages

from core import latex_ext as latex_mod
from core import latex_parser as lp_mod
from core.logger import log_exc
from ui.latex_widget import LatexLabel
from .base import CalcPanel


class LatexEditorPanel(CalcPanel):
    module_key = "latex"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        # ---------------- 模板 ----------------
        self.template = QComboBox()
        self.template.addItem(
            i18n.t("no_template", "— 无 —"), None)
        for k in sorted(latex_mod.TEMPLATES.keys()):
            self.template.addItem(k, k)
        self.template.currentIndexChanged.connect(
            self._load_template)

        # ---------------- 输入 ----------------
        self.input = QPlainTextEdit(
            r"\int_0^\infty e^{-x^2}\,dx = "
            r"\frac{\sqrt{\pi}}{2}")
        self.input.setFixedHeight(110)
        self.input.textChanged.connect(self._refresh)
        self.primary_input = self.input

        # ---------------- 预览 ----------------
        self.preview = LatexLabel(fontsize=18)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.preview)

        # ---------------- 字号 ----------------
        self.fontsize = QSpinBox()
        self.fontsize.setRange(8, 72)
        self.fontsize.setValue(18)
        self.fontsize.valueChanged.connect(self._refresh)

        # ---------------- 按钮 ----------------
        b_copy = QPushButton(
            i18n.t("copy_latex", "复制 LaTeX"))
        b_copy.clicked.connect(self._copy)
        b_png = QPushButton(
            i18n.t("export_png", "导出 PNG"))
        b_png.clicked.connect(self.export_png)
        b_svg = QPushButton(
            i18n.t("export_svg", "导出 SVG"))
        b_svg.clicked.connect(self.export_svg)
        b_pdf = QPushButton(
            i18n.t("export_pdf", "导出 PDF"))
        b_pdf.clicked.connect(self.export_pdf)
        # 第 6 轮新增：LaTeX → 表达式
        b_to_expr = QPushButton(
            i18n.t("latex_to_expr", "→ 表达式"))
        b_to_expr.setToolTip(i18n.t(
            "latex_to_expr_hint",
            "把当前 LaTeX 转换为 SymPy 表达式"))
        b_to_expr.clicked.connect(self.convert_to_expr)

        row = QHBoxLayout()
        row.addWidget(QLabel(
            i18n.t("template", "Template")))
        row.addWidget(self.template, 1)
        row.addWidget(QLabel(
            i18n.t("font_size", "Font")))
        row.addWidget(self.fontsize)
        for b in (b_copy, b_to_expr, b_png, b_svg, b_pdf):
            row.addWidget(b)

        lay = QVBoxLayout(self)
        lay.addLayout(row)
        lay.addWidget(QLabel("LaTeX"))
        lay.addWidget(self.input)
        lay.addWidget(QLabel(
            i18n.t("latex_preview", "Preview")))
        lay.addWidget(scroll, 1)

        self._refresh()

    # ==================================================================
    # 模板 / 预览
    # ==================================================================

    def _load_template(self, _):
        key = self.template.currentData()
        if not key:
            return
        self.input.setPlainText(
            latex_mod.TEMPLATES.get(key, ""))

    def _refresh(self):
        latex = self.input.toPlainText()
        self.preview.fontsize = self.fontsize.value()
        self.preview.set_latex(latex, latex)

    def set_theme_colors(self, fg, bg, panel):
        try:
            self.preview.set_color(fg)
        except Exception:
            pass

    # ==================================================================
    # 复制
    # ==================================================================

    def _copy(self):
        try:
            QApplication.clipboard().setText(
                self.input.toPlainText())
            QMessageBox.information(
                self, "OK",
                self.i18n.t("copied", "Copied"))
        except Exception as e:
            log_exc(e, module="LatexEditorPanel._copy")

    # ==================================================================
    # LaTeX → 表达式（第 6 轮）
    # ==================================================================

    def convert_to_expr(self):
        """把当前 LaTeX 转换为 SymPy 表达式，弹窗展示可复制。"""
        try:
            source = self.input.toPlainText().strip()
            if not source:
                QMessageBox.information(
                    self, "OK",
                    self.i18n.t("latex_empty",
                                "LaTeX 源码为空"))
                return

            r = lp_mod.latex_to_expr(source)
            if not r.ok:
                QMessageBox.warning(
                    self, "Error",
                    self.i18n.t("latex_parse_failed",
                                "LaTeX 解析失败：{err}")
                    .format(err=r.error or "unknown"))
                return

            dlg = _ExprResultDialog(
                self.i18n, source, r.expr,
                warnings=r.warnings, parent=self)
            if dlg.exec() == QDialog.Accepted:
                # 用户点击了「发送到科学面板」
                from ui.signals import bus
                bus().send_to_sci.emit(r.expr)
                try:
                    from ui.toast import toast
                    toast(
                        self.window(),
                        self.i18n.t(
                            "latex_sent_to_sci",
                            "已发送到科学面板"),
                        level="success")
                except Exception:
                    pass
        except Exception as e:
            log_exc(e, module="LatexEditorPanel.convert_to_expr")
            QMessageBox.warning(self, "Error", str(e))

    # ==================================================================
    # 导出
    # ==================================================================

    def export_png(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.i18n.t("export_png", "Export PNG"),
            "formula.png", "PNG (*.png)")
        if not path:
            return
        try:
            latex_mod.render_png(
                self.input.toPlainText(), path,
                fontsize=self.fontsize.value(),
                transparent=False)
            QMessageBox.information(self, "OK", path)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def export_svg(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.i18n.t("export_svg", "Export SVG"),
            "formula.svg", "SVG (*.svg)")
        if not path:
            return
        try:
            latex_mod.render_svg(
                self.input.toPlainText(), path,
                fontsize=self.fontsize.value())
            QMessageBox.information(self, "OK", path)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.i18n.t("export_pdf", "Export PDF"),
            "formula.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            with PdfPages(path) as pdf:
                fig = Figure(figsize=(8, 3))
                fig.text(
                    0.5, 0.5,
                    f"${self.input.toPlainText()}$",
                    ha="center", va="center",
                    fontsize=self.fontsize.value())
                pdf.savefig(fig)
            QMessageBox.information(self, "OK", path)
        except Exception as e:
            log_exc(e, module="LatexEditorPanel.export_pdf")
            QMessageBox.warning(self, "Error", str(e))


# ===========================================================================
# 内部：表达式结果对话框
# ===========================================================================

class _ExprResultDialog(QDialog):
    """展示 LaTeX → 表达式结果。"""

    def __init__(self, i18n, source, expr, warnings=None,
                 parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.expr = expr
        self.setWindowTitle(i18n.t(
            "latex_to_expr", "LaTeX → 表达式"))
        self.resize(560, 400)

        # 源
        self.source_edit = QPlainTextEdit(source)
        self.source_edit.setReadOnly(True)
        self.source_edit.setFixedHeight(100)

        # 结果
        self.expr_edit = QLineEdit(expr)
        self.expr_edit.setReadOnly(True)

        # 警告
        self.warn_edit = QPlainTextEdit()
        self.warn_edit.setReadOnly(True)
        self.warn_edit.setFixedHeight(70)
        if warnings:
            self.warn_edit.setPlainText("\n".join(warnings))
        else:
            self.warn_edit.setVisible(False)

        # 按钮
        b_copy = QPushButton(
            i18n.t("copy", "复制"))
        b_copy.clicked.connect(self._copy)
        b_send = QPushButton(
            i18n.t("send_to_sci", "发送到科学面板"))
        b_send.setDefault(True)
        b_send.clicked.connect(self.accept)
        b_cancel = QPushButton(
            i18n.t("close", "关闭"))
        b_cancel.clicked.connect(self.reject)

        row = QHBoxLayout()
        row.addWidget(b_copy)
        row.addStretch(1)
        row.addWidget(b_cancel)
        row.addWidget(b_send)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(i18n.t(
            "latex_source", "LaTeX 源码")))
        lay.addWidget(self.source_edit)
        lay.addWidget(QLabel(i18n.t(
            "latex_expr_result", "转换结果")))
        lay.addWidget(self.expr_edit)
        if warnings:
            lay.addWidget(QLabel(i18n.t(
                "latex_warnings", "警告")))
            lay.addWidget(self.warn_edit)
        lay.addLayout(row)

    def _copy(self):
        try:
            QApplication.clipboard().setText(self.expr)
            QMessageBox.information(
                self, "OK",
                self.i18n.t("copied", "已复制"))
        except Exception:
            pass


__all__ = ["LatexEditorPanel"]