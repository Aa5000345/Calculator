"""智能建议气泡：在输入框旁侧显示「灯泡」+ 建议列表。

用法：
    bubble = SuggestionBubble(settings, i18n, parent_widget)
    bubble.attach(line_edit)
    bubble.suggestion_clicked.connect(on_click)

设计：
- 附着到任意 QLineEdit / QPlainTextEdit
- 输入变化后 500ms 触发 suggest()
- 显示最多 3 条建议，点击即触发信号
- ESC 隐藏
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal, QPoint
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
    QWidget, QApplication,
)

from core import suggestions as sug_mod


class SuggestionBubble(QFrame):
    """浮动在输入框旁的智能建议气泡。"""

    suggestion_clicked = Signal(str, dict)   # (action, payload)

    def __init__(self, settings, i18n, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n
        self._target = None
        self._history_exprs: list = []
        self._module_key = ""
        self._last_result = ""

        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setStyleSheet(
            "SuggestionBubble {"
            " background: #2d2d30;"
            " border: 1px solid #555;"
            " border-radius: 6px;"
            "}")
        self.setVisible(False)

        self._icon = QLabel("💡")
        self._icon.setFixedWidth(22)
        f = QFont()
        f.setPointSize(11)
        self._icon.setFont(f)

        self._body = QVBoxLayout()
        self._body.setContentsMargins(4, 2, 4, 2)
        self._body.setSpacing(2)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addWidget(self._icon)
        top.addLayout(self._body, 1)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addLayout(top)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._do_suggest)

        self._enabled = bool(
            settings.get("suggestions_enabled", True))

    # ==================================================================
    # 附着
    # ==================================================================

    def attach(self, widget, module_key: str = "",
               history_getter=None):
        """把气泡附着到输入框。"""
        self._target = widget
        self._module_key = module_key
        self._history_getter = history_getter

        try:
            widget.textChanged.connect(self._on_text_changed)
        except AttributeError:
            try:
                widget.textChanged.connect(self._on_text_changed)
            except Exception:
                pass

        # 失焦时隐藏
        try:
            widget.installEventFilter(self)
        except Exception:
            pass

    def set_last_result(self, text: str):
        self._last_result = str(text or "")

    def set_enabled(self, on: bool):
        self._enabled = bool(on)
        if not on:
            self.hide()

    # ==================================================================
    # 触发
    # ==================================================================

    def _on_text_changed(self, *_):
        if not self._enabled:
            return
        self._timer.start()

    def _do_suggest(self):
        if self._target is None:
            return
        try:
            text = self._read_text()
        except Exception:
            return
        if not text or len(text) < 2:
            self.hide()
            return

        # 拉历史
        hist = self._history_exprs
        if not hist and getattr(self, "_history_getter", None):
            try:
                hist = self._history_getter() or []
            except Exception:
                hist = []
        self._history_exprs = hist

        items = sug_mod.suggest(
            text,
            history_exprs=hist,
            last_result=self._last_result,
            module_key=self._module_key,
            limit=3,
        )
        self._render(items)

    def _read_text(self) -> str:
        w = self._target
        if w is None:
            return ""
        if hasattr(w, "text"):
            return w.text()
        if hasattr(w, "toPlainText"):
            return w.toPlainText()
        return ""

    # ==================================================================
    # 渲染
    # ==================================================================

    def _render(self, items):
        # 清空旧建议
        while self._body.count():
            it = self._body.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        if not items:
            self.hide()
            return

        for s in items:
            btn = QPushButton(s.text)
            btn.setFlat(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton{"
                " background:transparent;"
                " border:none;"
                " color:#cfcfcf;"
                " text-align:left;"
                " padding: 2px 4px;"
                " font-size: 9pt;"
                "}"
                "QPushButton:hover{ color:#ffffff;"
                " background:rgba(255,255,255,0.08); }")
            btn.clicked.connect(
                lambda _=False, ss=s: self._on_click(ss))
            self._body.addWidget(btn)

        # 定位
        self._reposition()
        self.show()
        self.raise_()

    def _reposition(self):
        try:
            w = self._target
            if w is None:
                return
            gp = w.mapToGlobal(QPoint(0, w.height() + 4))
            self.adjustSize()
            self.move(gp)
        except Exception:
            pass

    def _on_click(self, s: sug_mod.Suggestion):
        try:
            self.suggestion_clicked.emit(s.action, s.payload or {})
        except Exception:
            pass
        self.hide()

    # ==================================================================
    # 事件
    # ==================================================================

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(e)

    def eventFilter(self, obj, event):
        # 目标失焦时隐藏（延迟一点避免点击自身触发）
        if event.type() == event.Type.FocusOut:
            QTimer.singleShot(150, self._maybe_hide)
        return super().eventFilter(obj, event)

    def _maybe_hide(self):
        try:
            fw = QApplication.focusWidget()
            if fw is None or fw is not self._target:
                self.hide()
        except Exception:
            self.hide()