"""Qt 运行期辅助：Worker 线程 + 全局异常钩子。

合并自：worker.py + error_handler.py

依赖：PySide6
    - 本模块不应在 CLI 路径下被导入
    - core/__init__.py 不导入本模块

对外接口：
    Worker                  QThread 包装，支持取消
    install_error_handler() 安装 sys.excepthook
"""
from __future__ import annotations

import sys
import traceback

from PySide6.QtCore import QThread, Signal


__all__ = ["Worker", "install_error_handler"]


# ===========================================================================
# Worker
# ===========================================================================

class Worker(QThread):
    """通用后台任务。

    信号：
    - done(obj)      任务正常完成
    - failed(exc)    任务抛出异常
    - cancelled()    任务被取消（无论是否已产生结果）
    - progress(int)  进度（0–100）
    """

    done = Signal(object)
    failed = Signal(Exception)
    cancelled = Signal()
    progress = Signal(int)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._cancelled = False

    def cancel(self):
        """请求取消；若函数支持，可自行读取 is_cancelled() 提前退出。"""
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled

    def run(self):
        try:
            if self._cancelled:
                self.cancelled.emit()
                return
            result = self._fn(*self._args, **self._kwargs)
            if self._cancelled:
                self.cancelled.emit()
            else:
                self.done.emit(result)
        except Exception as exc:  # noqa: BLE001
            if self._cancelled:
                self.cancelled.emit()
            else:
                self.failed.emit(exc)


# ===========================================================================
# 全局异常钩子
# ===========================================================================

def _safe_qmessagebox(exc_value):
    """尝试用 Qt 弹窗提示；Qt 未初始化时静默失败。"""
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
                type(exc_value), exc_value,
                exc_value.__traceback__)))
        msg.exec()
    except Exception:
        pass


def install_error_handler():
    """安装 sys.excepthook：未捕获异常 → 日志 + 弹窗。"""
    from core.base import log_exc

    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        try:
            log_exc(exc_value, module="uncaught")
        except Exception:
            pass
        _safe_qmessagebox(exc_value)

    sys.excepthook = _hook


# 兼容旧接口名
install = install_error_handler