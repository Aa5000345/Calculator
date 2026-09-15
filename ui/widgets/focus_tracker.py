"""应用级焦点追踪：让浮动键盘知道往哪个输入控件插入文本。

设计要点：
- 单例：`FocusTracker.instance()`，随应用生命周期存续。
- 忽略键盘自身的输入控件（通过 window().objectName()）。
- 目标控件被销毁时（RuntimeError）自动清空引用。
- 只追踪 QLineEdit / QPlainTextEdit / QTextEdit 及可编辑 QComboBox。
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QLineEdit, QPlainTextEdit, QTextEdit,
)


_KEYBOARD_OBJECT_NAME = "CalcKeyboardWindow"


class FocusTracker(QObject):
    _instance = None

    @classmethod
    def instance(cls) -> "FocusTracker":
        if cls._instance is None:
            app = QApplication.instance()
            if app is None:
                raise RuntimeError("QApplication 未初始化")
            cls._instance = FocusTracker(app)
        return cls._instance

    def __init__(self, app: QApplication):
        super().__init__(app)
        self._target = None
        app.focusChanged.connect(self._on_focus_changed)

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _on_focus_changed(self, old, new):
        if new is None:
            return
        # 忽略键盘自身
        try:
            win = new.window()
            if win is not None and win.objectName() == _KEYBOARD_OBJECT_NAME:
                return
        except Exception:
            pass
        if not self._is_editable(new):
            return
        self._target = new

    @staticmethod
    def _is_editable(w) -> bool:
        try:
            if isinstance(w, QComboBox):
                return bool(w.isEditable())
            if isinstance(w, (QLineEdit, QPlainTextEdit, QTextEdit)):
                try:
                    if w.isReadOnly():
                        return False
                except Exception:
                    pass
                return True
        except Exception:
            pass
        # 兜底：有 insert + isReadOnly 的控件
        if hasattr(w, "insert") and hasattr(w, "isReadOnly"):
            try:
                return not w.isReadOnly()
            except Exception:
                return False
        return False

    def _unwrap(self, w):
        """QComboBox 可编辑时把内部 lineEdit 取出。"""
        if isinstance(w, QComboBox):
            try:
                return w.lineEdit()
            except Exception:
                return None
        return w

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def target(self):
        w = self._target
        if w is None:
            return None
        try:
            w.objectName()  # 探测是否已被销毁
        except RuntimeError:
            self._target = None
            return None
        return self._unwrap(w)

    def insert_text(self, text: str) -> bool:
        w = self.target()
        if w is None or not text:
            return False
        try:
            if isinstance(w, QLineEdit):
                w.insert(text)
                return True
            if isinstance(w, (QPlainTextEdit, QTextEdit)):
                w.insertPlainText(text)
                return True
            if hasattr(w, "insert"):
                w.insert(text)
                return True
        except Exception:
            pass
        return False

    def backspace(self) -> bool:
        w = self.target()
        if w is None:
            return False
        try:
            if isinstance(w, QLineEdit):
                w.backspace()
                return True
            if isinstance(w, (QPlainTextEdit, QTextEdit)):
                cur = w.textCursor()
                cur.deletePreviousChar()
                return True
        except Exception:
            pass
        return False

    def clear(self) -> bool:
        w = self.target()
        if w is None:
            return False
        try:
            w.clear()
            return True
        except Exception:
            return False

    def send_enter(self) -> bool:
        w = self.target()
        if w is None:
            return False
        try:
            if isinstance(w, QLineEdit):
                w.returnPressed.emit()
                return True
        except Exception:
            pass
        return False

    def current_text(self) -> str:
        w = self.target()
        if w is None:
            return ""
        try:
            if isinstance(w, QLineEdit):
                return w.text()
            if isinstance(w, (QPlainTextEdit, QTextEdit)):
                return w.toPlainText()
        except Exception:
            pass
        return ""