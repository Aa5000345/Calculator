"""全局异常钩子：未捕获异常 → 日志 + 弹窗，避免直接崩溃。"""
from __future__ import annotations

import sys
import traceback

from core.logger import log_exc, log_error


def _safe_qmessagebox(exc_value):
    """尝试用 Qt 弹窗提示；在 Qt 尚未初始化时静默失败。"""
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        if QApplication.instance() is None:
            return
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("Error")
        msg.setText(str(exc_value) or exc_value.__class__.__name__)
        msg.setDetailedText(
            "".join(traceback.format_exception(
                type(exc_value), exc_value, exc_value.__traceback__)))
        msg.exec()
    except Exception:
        pass


def install():
    """安装 sys.excepthook。"""
    def _hook(exc_type, exc_value, exc_tb):
        # KeyboardInterrupt 继续按 Python 默认处理
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        try:
            log_exc(exc_value, module="uncaught")
        except Exception:
            pass
        _safe_qmessagebox(exc_value)

    sys.excepthook = _hook