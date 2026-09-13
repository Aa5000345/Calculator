"""CalcPanel 基类：统一 Worker 管理、取消、设置回调、主题回调。"""
from __future__ import annotations

from PySide6.QtWidgets import QWidget


class CalcPanel(QWidget):
    """所有功能面板的基类。

    提供：
    - settings / i18n / history 存储
    - _worker 槽位与 cancel_current()
    - run() 封装 run_async，自动把 worker 存到 self._worker
    - on_settings_changed() / set_theme_colors() 默认空实现
    """

    module_key = "generic"

    def __init__(self, settings, i18n, history, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n
        self.history = history
        self._worker = None

    # ------------------------------------------------------------------
    # Worker 管理
    # ------------------------------------------------------------------

    def run(self, fn, *args,
            on_done=None, on_fail=None, on_cancel=None,
            cancel_btn=None, main_btn=None, **kwargs):
        """在后台线程执行 fn；返回 Worker（同时保存在 self._worker）。"""
        from ._common import run_async
        self._worker = run_async(
            self, fn, *args,
            cancel_btn=cancel_btn, main_btn=main_btn,
            on_done=on_done, on_fail=on_fail, on_cancel=on_cancel,
            **kwargs,
        )
        return self._worker

    def cancel_current(self):
        """取消当前正在运行的 Worker（若有）。"""
        try:
            if self._worker is not None and self._worker.isRunning():
                self._worker.cancel()
        except Exception:
            pass

    def shutdown_workers(self, wait_ms: int = 2000):
        """供 MainWindow.rebuild() 调用；同步等待 Worker 结束。"""
        try:
            if self._worker is not None and self._worker.isRunning():
                self._worker.cancel()
                self._worker.wait(wait_ms)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 回调（子类可覆盖）
    # ------------------------------------------------------------------

    def on_settings_changed(self, key=None):
        pass

    def set_theme_colors(self, fg, bg, panel):
        pass

    # ------------------------------------------------------------------
    # 快捷接口
    # ------------------------------------------------------------------

    def add_history(self, expr, result, module=None):
        try:
            self.history.add(module or self.module_key, str(expr), str(result))
        except Exception:
            pass