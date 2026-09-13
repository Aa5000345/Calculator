"""后台计算：QThread 包装，支持取消、进度与取消信号。"""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal


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