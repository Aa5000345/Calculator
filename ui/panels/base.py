"""CalcPanel 基类：Worker 管理 / 取消 / 设置回调 / 主题回调 / 键盘按钮。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QWidget


class CalcPanel(QWidget):
    """所有功能面板的基类。

    提供：
    - settings / i18n / history 存储（均可为 None）
    - _worker 槽位与 cancel_current()
    - run() 封装 run_async
    - on_settings_changed() / set_theme_colors() 默认空实现
    - make_kb_button()：一键生成"⌨"按钮，呼出浮动键盘
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
        from ._common import run_async
        self._worker = run_async(
            self, fn, *args,
            cancel_btn=cancel_btn, main_btn=main_btn,
            on_done=on_done, on_fail=on_fail, on_cancel=on_cancel,
            **kwargs,
        )
        return self._worker

    def cancel_current(self):
        try:
            if self._worker is not None and self._worker.isRunning():
                self._worker.cancel()
        except Exception:
            pass

    def shutdown_workers(self, wait_ms: int = 2000):
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
        if self.history is None:
            return
        try:
            self.history.add(module or self.module_key, str(expr), str(result))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 键盘按钮
    # ------------------------------------------------------------------

    def make_kb_button(self) -> QPushButton:
        """创建一个"⌨"按钮；点击呼出/隐藏浮动键盘。

        面板可以把它加到自己的顶部工具栏中。
        """
        btn = QPushButton("⌨")
        btn.setFixedSize(28, 24)
        try:
            btn.setToolTip(self.i18n.t("calc_keyboard", "计算器键盘"))
        except Exception:
            btn.setToolTip("计算器键盘")
        btn.setFocusPolicy(Qt.NoFocus)
        btn.clicked.connect(self._open_floating_keyboard)
        return btn

    def _open_floating_keyboard(self):
        """通过父窗口上的 toggle_keyboard() 呼出浮动键盘。"""
        try:
            mw = self.window()
            fn = getattr(mw, "toggle_keyboard", None)
            if callable(fn):
                fn()
        except Exception:
            pass