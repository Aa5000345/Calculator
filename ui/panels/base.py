"""CalcPanel 基类：Worker 管理 / 取消 / 设置回调 / 主题回调 /
键盘按钮 / primary_input / 撤销栈 / 自动重试。

依赖（合并后）：
    PySide6.QtWidgets
    core.runtime —— Worker（延迟导入）

变更历史：
- 第 2 轮：primary_input、_undo_stack、_notify_task
- 第 3 轮：run() 默认 on_fail 自动把 retry_cb 注入 ResultView
- 本轮：无（仅导入路径统一，实际 Worker 导入仍走 _common）
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QWidget


class CalcPanel(QWidget):
    """所有功能面板的基类。"""

    module_key = "generic"

    # 子类覆盖：指向主输入控件（QLineEdit / QPlainTextEdit）
    primary_input = None

    def __init__(self, settings, i18n, history, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n
        self.history = history
        self._worker = None
        self._undo_stack: list = []
        self._undo_max = 50

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------

    def run(self, fn, *args,
            on_done=None, on_fail=None, on_cancel=None,
            cancel_btn=None, main_btn=None, **kwargs):
        from ._common import run_async
        self._notify_task(True, "⏳ 计算中")

        fail_cb = (on_fail
                   if on_fail is not None
                   else self._default_on_fail)

        def _wrap_done(r):
            self._notify_task(False)
            if on_done:
                on_done(r)

        def _wrap_fail(e):
            self._notify_task(False)
            try:
                fail_cb(e)
            except Exception:
                pass

        def _wrap_cancel():
            self._notify_task(False)
            if on_cancel:
                on_cancel()

        self._worker = run_async(
            self, fn, *args,
            cancel_btn=cancel_btn, main_btn=main_btn,
            on_done=_wrap_done, on_fail=_wrap_fail,
            on_cancel=_wrap_cancel,
            **kwargs,
        )
        return self._worker

    def get_result_view(self):
        """返回主 ResultView；子类可覆盖。"""
        rv = getattr(self, "result", None)
        if rv is not None and hasattr(rv, "show_error"):
            return rv
        return None

    def _default_on_fail(self, e):
        """默认失败处理：显示到主 ResultView 并注入重试回调。"""
        rv = self.get_result_view()
        if rv is None:
            return
        retry = getattr(self, "calc", None)
        try:
            rv.show_error(e, retry_cb=retry)
        except Exception:
            pass

    def _notify_task(self, active: bool, text: str = ""):
        try:
            mw = self.window()
            sb = getattr(mw, "status_bar", None)
            if sb is not None and hasattr(sb, "set_task_active"):
                sb.set_task_active(active, text)
        except Exception:
            pass

    def cancel_current(self):
        try:
            if (self._worker is not None
                    and self._worker.isRunning()):
                self._worker.cancel()
        except Exception:
            pass

    def shutdown_workers(self, wait_ms: int = 2000):
        try:
            if (self._worker is not None
                    and self._worker.isRunning()):
                self._worker.cancel()
                self._worker.wait(wait_ms)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 撤销
    # ------------------------------------------------------------------

    def push_undo(self, snapshot=None):
        """保存一次撤销快照（默认取 primary_input 的文本）。"""
        try:
            if snapshot is None:
                w = self.primary_input
                if w is not None and hasattr(w, "text"):
                    snapshot = w.text()
                elif w is not None and hasattr(w, "toPlainText"):
                    snapshot = w.toPlainText()
            if snapshot is None:
                return
            self._undo_stack.append(snapshot)
            if len(self._undo_stack) > self._undo_max:
                self._undo_stack.pop(0)
        except Exception:
            pass

    def undo(self):
        """恢复上一次快照到 primary_input。"""
        if not self._undo_stack:
            return False
        try:
            snapshot = self._undo_stack.pop()
            w = self.primary_input
            if w is None:
                return False
            if hasattr(w, "setText"):
                w.setText(str(snapshot))
            elif hasattr(w, "setPlainText"):
                w.setPlainText(str(snapshot))
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # 子类可覆盖
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
            self.history.add(
                module or self.module_key, str(expr), str(result))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 键盘按钮
    # ------------------------------------------------------------------

    def make_kb_button(self) -> QPushButton:
        btn = QPushButton("⌨")
        btn.setFixedSize(28, 24)
        try:
            btn.setToolTip(self.i18n.t(
                "calc_keyboard", "计算器键盘"))
        except Exception:
            btn.setToolTip("计算器键盘")
        btn.setFocusPolicy(Qt.NoFocus)
        btn.clicked.connect(self._open_floating_keyboard)
        return btn

    def _open_floating_keyboard(self):
        try:
            mw = self.window()
            fn = getattr(mw, "toggle_keyboard", None)
            if callable(fn):
                fn()
        except Exception:
            pass


__all__ = ["CalcPanel"]