"""面板共享工具：错误展示、异步执行、布局清理。"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QPlainTextEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QTabWidget, QScrollArea, QMessageBox, QApplication,
)

from core.errors import CalcError
from core.logger import log_exc, log_path
from core.worker import Worker
from ui.latex_widget import LatexLabel


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
        else:
            sub = item.layout()
            if sub is not None:
                _clear_layout(sub)


def friendly_error(i18n, exc, module="ui"):
    try:
        log_exc(exc, module=module)
    except Exception:
        pass
    if isinstance(exc, CalcError):
        try:
            return exc.friendly(i18n)
        except Exception:
            return str(exc)
    return f"{type(exc).__name__}: {exc}"


def run_async(parent_widget, fn, *args,
              on_done=None, on_fail=None, on_cancel=None,
              cancel_btn=None, main_btn=None, **kwargs):
    """在 QThread 中执行 fn，返回 Worker。"""
    w = Worker(fn, *args, **kwargs)

    if cancel_btn is not None:
        cancel_btn.setEnabled(True)
        try:
            cancel_btn.clicked.disconnect()
        except Exception:
            pass
        cancel_btn.clicked.connect(w.cancel)

    def _restore():
        if cancel_btn is not None:
            cancel_btn.setEnabled(False)
        if main_btn is not None:
            main_btn.setEnabled(True)

    def _done(r):
        _restore()
        if on_done:
            on_done(r)

    def _fail(e):
        _restore()
        if on_fail:
            on_fail(e)

    def _cancelled():
        _restore()
        if on_cancel:
            on_cancel()

    w.done.connect(_done)
    w.failed.connect(_fail)
    w.cancelled.connect(_cancelled)
    w.finished.connect(w.deleteLater)
    w.start()
    return w


class ResultView(QWidget):
    """结果查看器：纯文本 + LaTeX 预览 + 复制。"""

    def __init__(self, i18n, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self._last_error = ""
        self._last_text = ""

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)

        self.latex = LatexLabel(fontsize=16)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.latex)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.text, i18n.t("plain_text", "Plain"))
        self.tabs.addTab(scroll, i18n.t("latex_preview", "LaTeX"))

        self.copy_btn = QPushButton(i18n.t("copy_error", "Copy error details"))
        self.copy_btn.setVisible(False)
        self.copy_btn.clicked.connect(self._copy_error)

        self.copy_value_btn = QPushButton(i18n.t("copy_value", "Copy result"))
        self.copy_value_btn.clicked.connect(self._copy_value)

        row = QHBoxLayout()
        row.addWidget(self.copy_btn)
        row.addWidget(self.copy_value_btn)
        row.addStretch(1)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.tabs, 1)
        lay.addLayout(row)

    def show_result(self, text: str, latex: str = ""):
        self.text.setPlainText(text or "")
        self.latex.set_latex(latex or "", text or "")
        self.copy_btn.setVisible(False)
        self._last_error = ""
        self._last_text = text or ""

    def show_error(self, exc):
        msg = friendly_error(self.i18n, exc, "ui")
        self.text.setPlainText(msg)
        self.latex.set_latex("", msg)
        self._last_error = msg
        self._last_text = msg
        self.copy_btn.setVisible(True)

    def set_color(self, color: str):
        self.latex.set_color(color)

    def _copy_error(self):
        try:
            payload = self._last_error + "\n\nlog: " + log_path()
            QApplication.clipboard().setText(payload)
            QMessageBox.information(
                self, "OK", self.i18n.t("copied", "Copied to clipboard"))
        except Exception as e:
            log_exc(e, module="ResultView._copy_error")

    def _copy_value(self):
        try:
            QApplication.clipboard().setText(self._last_text)
            QMessageBox.information(
                self, "OK", self.i18n.t("copied", "Copied to clipboard"))
        except Exception as e:
            log_exc(e, module="ResultView._copy_value")