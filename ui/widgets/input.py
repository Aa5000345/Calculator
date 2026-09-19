"""输入相关组件：焦点追踪 / 键按钮 / 输入历史 / 建议气泡 /
差异徽章 / 空状态。

合并自：ui/widgets/focus_tracker.py + ui/widgets/key_button.py
        + ui/widgets/input_history_widget.py
        + ui/widgets/suggestion_widget.py
        + ui/widgets/diff_badge.py
        + ui/widgets/empty_state.py

对外接口：
    FocusTracker, KeyButton, InputHistoryButton,
    SuggestionBubble, DiffBadge, EmptyState
"""
from __future__ import annotations

from PySide6.QtCore import (
    Qt, QObject, QTimer, Signal, QPoint,
)
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMenu, QPlainTextEdit, QPushButton,
    QSizePolicy, QTextEdit, QVBoxLayout, QWidget,
)

from core import ai as _ai
from core import user_data as _ud
from core.base import log_exc


__all__ = [
    "FocusTracker",
    "KeyButton",
    "InputHistoryButton",
    "SuggestionBubble",
    "DiffBadge",
    "EmptyState",
]


# ===========================================================================
# 焦点追踪
# ===========================================================================

_KEYBOARD_OBJECT_NAME = "CalcKeyboardWindow"


class FocusTracker(QObject):
    """应用级焦点追踪：让浮动键盘知道往哪个输入控件插入文本。"""

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

    def _on_focus_changed(self, old, new):
        if new is None:
            return
        try:
            win = new.window()
            if (win is not None
                    and win.objectName() == _KEYBOARD_OBJECT_NAME):
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
        if hasattr(w, "insert") and hasattr(w, "isReadOnly"):
            try:
                return not w.isReadOnly()
            except Exception:
                return False
        return False

    def _unwrap(self, w):
        if isinstance(w, QComboBox):
            try:
                return w.lineEdit()
            except Exception:
                return None
        return w

    # ------------------------------------------------------------------

    def target(self):
        w = self._target
        if w is None:
            return None
        try:
            w.objectName()
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


# ===========================================================================
# 键按钮
# ===========================================================================

class KeyButton(QPushButton):
    """一个按键。发出 ``pressed_key(Key)`` 信号。"""

    pressed_key = Signal(object)

    def __init__(self, key, parent=None):
        super().__init__(parent)
        self._key = key
        self._second = False
        self.setFocusPolicy(Qt.NoFocus)
        self.setMinimumSize(36, 32)
        self.setSizePolicy(QSizePolicy.Expanding,
                           QSizePolicy.Expanding)
        if getattr(key, "tooltip", ""):
            self.setToolTip(key.tooltip)
        self.clicked.connect(self._on_click)
        self._refresh()

    def key_def(self):
        return self._key

    def set_second(self, on: bool):
        if self._second == on:
            return
        self._second = on
        self._refresh()

    def _effective(self):
        k = self._key
        if not (self._second and getattr(k, "alt_label", "")):
            return k
        try:
            from .keyboard import Key
            return Key(
                label=k.alt_label,
                insert=k.alt_insert,
                action=(k.alt_action
                        or ("insert" if k.alt_insert else "")),
                tooltip=k.tooltip,
                style=k.style,
                span=k.span,
            )
        except Exception:
            return k

    def _refresh(self):
        eff = self._effective()
        self.setText(eff.label)
        self.setProperty("keyStyle", eff.style)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def _on_click(self):
        eff = self._effective()
        if not eff.insert and not eff.action:
            return
        self.pressed_key.emit(eff)


# ===========================================================================
# 输入框版本历史
# ===========================================================================

class InputHistoryButton(QPushButton):
    """输入框历史按钮（🕘）。"""

    version_selected = Signal(str)

    def __init__(self, settings, i18n, key: str, parent=None):
        super().__init__("🕘", parent)
        self.settings = settings
        self.i18n = i18n
        self.key = str(key or "")
        self._target = None
        self._record_timer = QTimer(self)
        self._record_timer.setSingleShot(True)
        self._record_timer.setInterval(800)
        self._record_timer.timeout.connect(self._do_record)

        self.setFixedSize(26, 24)
        self.setToolTip(i18n.t(
            "input_history_tip", "查看历史版本"))
        self.setFocusPolicy(Qt.NoFocus)
        self.clicked.connect(self._show_menu)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context)

    # ------------------------------------------------------------------

    def attach(self, widget):
        self._target = widget
        try:
            widget.textChanged.connect(self._on_text_changed)
        except AttributeError:
            try:
                widget.textChanged.connect(
                    self._on_text_changed)
            except Exception:
                pass
        try:
            t = self._read_text()
            if t:
                _ud.input_record(self.key, t)
        except Exception:
            pass

    def _on_text_changed(self, *_):
        self._record_timer.start()

    def _do_record(self):
        try:
            t = self._read_text()
            _ud.input_record(self.key, t)
        except Exception:
            pass

    def _read_text(self) -> str:
        w = self._target
        if w is None:
            return ""
        try:
            if hasattr(w, "text"):
                return w.text()
            if hasattr(w, "toPlainText"):
                return w.toPlainText()
        except Exception:
            pass
        return ""

    def _write_text(self, text: str):
        w = self._target
        if w is None:
            return
        try:
            if hasattr(w, "setText"):
                w.setText(text)
                if hasattr(w, "setCursorPosition"):
                    w.setCursorPosition(len(text))
            elif hasattr(w, "setPlainText"):
                w.setPlainText(text)
        except Exception:
            pass

    # ------------------------------------------------------------------

    def _show_menu(self):
        try:
            versions = _ud.input_list_versions(self.key)
        except Exception as e:
            log_exc(e, module="InputHistoryButton._show_menu")
            return

        if not versions:
            self.setToolTip(
                self.i18n.t("input_history_empty", "暂无历史"))
            return

        menu = QMenu(self)
        for i, v in enumerate(versions[:20]):
            text = str(v.get("text") or "")
            preview = text.replace("\n", " ⏎ ")
            if len(preview) > 60:
                preview = preview[:57] + "…"
            ts = str(v.get("time") or "")[-8:]
            act = menu.addAction(f"{ts}  {preview}")
            act.triggered.connect(
                lambda _=False, t=text: self._on_selected(t))

        menu.addSeparator()
        a_clear = menu.addAction(
            self.i18n.t("input_history_clear",
                        "清空本输入框历史"))
        a_clear.triggered.connect(self._clear)

        menu.exec(self.mapToGlobal(self.rect().bottomLeft()))

    def _on_selected(self, text: str):
        self._write_text(text)
        try:
            self.version_selected.emit(text)
        except Exception:
            pass

    def _show_context(self, pos):
        menu = QMenu(self)
        a_clear = menu.addAction(
            self.i18n.t("input_history_clear",
                        "清空本输入框历史"))
        a_clear.triggered.connect(self._clear)
        menu.exec(self.mapToGlobal(pos))

    def _clear(self):
        _ud.input_clear(self.key)
        self.setToolTip(
            self.i18n.t("input_history_cleared", "历史已清空"))


# ===========================================================================
# 智能建议气泡
# ===========================================================================

class SuggestionBubble(QFrame):
    """浮动在输入框旁的智能建议气泡。"""

    suggestion_clicked = Signal(str, dict)

    def __init__(self, settings, i18n, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n
        self._target = None
        self._history_exprs: list = []
        self._history_getter = None
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

    # ------------------------------------------------------------------

    def attach(self, widget, module_key: str = "",
               history_getter=None):
        self._target = widget
        self._module_key = module_key
        self._history_getter = history_getter

        try:
            widget.textChanged.connect(self._on_text_changed)
        except AttributeError:
            try:
                widget.textChanged.connect(
                    self._on_text_changed)
            except Exception:
                pass

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

    # ------------------------------------------------------------------

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

        hist = self._history_exprs
        if not hist and self._history_getter:
            try:
                hist = self._history_getter() or []
            except Exception:
                hist = []
        self._history_exprs = hist

        try:
            items = _ai.suggest(
                text,
                history_exprs=hist,
                last_result=self._last_result,
                module_key=self._module_key,
                limit=3,
            )
        except Exception:
            items = []
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

    # ------------------------------------------------------------------

    def _render(self, items):
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

    def _on_click(self, s):
        try:
            self.suggestion_clicked.emit(
                s.action, s.payload or {})
        except Exception:
            pass
        self.hide()

    # ------------------------------------------------------------------

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(e)

    def eventFilter(self, obj, event):
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


# ===========================================================================
# 差异徽章
# ===========================================================================

class DiffBadge(QLabel):
    """结果差异徽章。自动根据 DiffResult 渲染颜色与文本。"""

    COLOR_UP = "#2ecc71"
    COLOR_DOWN = "#e74c3c"
    COLOR_SAME = "#888888"
    COLOR_TEXT = "#3498db"
    COLOR_WARN = "#f39c12"

    def __init__(self, i18n=None, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        f = QFont()
        f.setPointSize(max(8, f.pointSize() - 1))
        f.setBold(True)
        self.setFont(f)
        self.setStyleSheet("padding: 1px 6px;")
        self.setVisible(False)
        self._current_diff = None

    # ------------------------------------------------------------------

    def update_from(self, prev, curr, tolerance: float = 1e-12):
        from core import result_diff as rd
        diff = rd.compare(prev, curr, tolerance=tolerance)
        self.set_diff(diff)

    def set_diff(self, diff):
        self._current_diff = diff

        if diff is None or not diff.has_diff:
            self.setText("")
            self.setVisible(False)
            return

        from core import result_diff as rd
        text = rd.describe(diff, self.i18n)
        if not text:
            self.setVisible(False)
            return

        if diff.kind == "numeric":
            if diff.direction == "+":
                color = self.COLOR_UP
            elif diff.direction == "-":
                color = self.COLOR_DOWN
            else:
                color = self.COLOR_SAME
        elif diff.kind == "text":
            color = self.COLOR_TEXT
        else:
            color = self.COLOR_WARN

        self.setText(text)
        self.setStyleSheet(
            f"color: {color};"
            f" background: rgba(128,128,128,0.12);"
            f" border-radius: 4px;"
            f" padding: 1px 6px;")
        self.setToolTip(
            f"上一次：{diff.prev_repr}\n"
            f"本次：  {diff.curr_repr}")
        self.setVisible(True)

    def clear(self):
        self.setText("")
        self.setVisible(False)
        self._current_diff = None

    def current_diff(self):
        return self._current_diff


# ===========================================================================
# 空状态
# ===========================================================================

class EmptyState(QWidget):
    """空状态提示。"""

    action_clicked = Signal()

    def __init__(self, icon: str = "📭",
                 title: str = "",
                 subtitle: str = "",
                 action_text: str = "",
                 parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding,
                           QSizePolicy.Expanding)

        self.icon_label = QLabel(icon)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet(
            "font-size: 48pt; padding: 12px;")

        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet(
            "font-size: 14pt; font-weight: bold;"
            " color: #888; padding: 4px;")
        self.title_label.setWordWrap(True)

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setStyleSheet(
            "font-size: 10pt; color: #777; padding: 2px;")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setVisible(bool(subtitle))

        self.action_btn = QPushButton(action_text)
        self.action_btn.setMinimumWidth(140)
        self.action_btn.setMinimumHeight(34)
        self.action_btn.setCursor(Qt.PointingHandCursor)
        self.action_btn.clicked.connect(self.action_clicked.emit)
        self.action_btn.setVisible(bool(action_text))

        btn_row = QVBoxLayout()
        btn_row.setContentsMargins(0, 8, 0, 0)
        btn_row.addWidget(self.action_btn, 0, Qt.AlignHCenter)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.addStretch(1)
        lay.addWidget(self.icon_label)
        lay.addWidget(self.title_label)
        lay.addWidget(self.subtitle_label)
        lay.addLayout(btn_row)
        lay.addStretch(1)

    # ------------------------------------------------------------------

    def set_icon(self, icon: str):
        self.icon_label.setText(str(icon))

    def set_title(self, text: str):
        self.title_label.setText(str(text))

    def set_subtitle(self, text: str):
        self.subtitle_label.setText(str(text or ""))
        self.subtitle_label.setVisible(bool(text))

    def set_action(self, text: str):
        self.action_btn.setText(str(text or ""))
        self.action_btn.setVisible(bool(text))

    def set_compact(self, compact: bool = True):
        if compact:
            self.icon_label.setStyleSheet(
                "font-size: 28pt; padding: 4px;")
            self.title_label.setStyleSheet(
                "font-size: 12pt; font-weight: bold;"
                " color: #888; padding: 2px;")
        else:
            self.icon_label.setStyleSheet(
                "font-size: 48pt; padding: 12px;")
            self.title_label.setStyleSheet(
                "font-size: 14pt; font-weight: bold;"
                " color: #888; padding: 4px;")