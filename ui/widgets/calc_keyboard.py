"""浮动计算器键盘窗口。

自动跟随当前模块切换布局：
- MainWindow.switch_to_key() 调用 set_module(key)
- 未匹配的面板回退到"通用"布局
- 支持 2ⁿᵈ 二级函数、DEG/RAD、内存槽、光标移动、智能插入
- 智能插入：
    - 数字后接字母自动补 '*'
    - '(' 结尾时自动补 ')'，光标停在中间
    - 单位插入避免重复空格
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizeGrip,
    QVBoxLayout, QWidget,
)

from core.logger import log_exc
from .focus_tracker import FocusTracker
from .key_button import KeyButton
from .keyboard_layouts import get_layout


_KEYBOARD_OBJECT_NAME = "CalcKeyboardWindow"


# =====================================================================
# 自绘标题栏
# =====================================================================

class _TitleBar(QWidget):
    def __init__(self, parent: "CalcKeyboard"):
        super().__init__(parent)
        self.setObjectName("CalcKeyboardTitleBar")
        self._parent = parent
        self._drag_pos = None
        self.setFixedHeight(30)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 4, 2)
        layout.setSpacing(6)

        self.title = QLabel("🧮 基础")
        self.title.setStyleSheet("font-size: 11pt; font-weight: bold;")

        self.deg_btn = QPushButton("RAD")
        self.deg_btn.setFixedSize(48, 22)
        self.deg_btn.setToolTip("角度模式：DEG / RAD")
        self.deg_btn.clicked.connect(parent.toggle_angle_mode)

        self.pin_btn = QPushButton("📌")
        self.pin_btn.setFixedSize(26, 22)
        self.pin_btn.setCheckable(True)
        self.pin_btn.setToolTip("置顶")
        self.pin_btn.toggled.connect(parent.on_pin_toggled)

        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(26, 22)
        self.close_btn.setToolTip("关闭")
        self.close_btn.clicked.connect(parent.close)

        layout.addWidget(self.title)
        layout.addWidget(self.deg_btn)
        layout.addStretch(1)
        layout.addWidget(self.pin_btn)
        layout.addWidget(self.close_btn)

    def set_module_label(self, label: str):
        self.title.setText(f"🧮 {label}")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = (
                e.globalPosition().toPoint()
                - self._parent.frameGeometry().topLeft()
            )
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag_pos is not None and e.buttons() & Qt.LeftButton:
            self._parent.move(e.globalPosition().toPoint() - self._drag_pos)
            e.accept()

    def mouseReleaseEvent(self, e):
        self._drag_pos = None
        e.accept()


# =====================================================================
# 浮动键盘
# =====================================================================

class CalcKeyboard(QDialog):
    equals_requested = Signal()

    def __init__(self, settings, i18n, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n
        self.setObjectName(_KEYBOARD_OBJECT_NAME)

        flags = Qt.Tool | Qt.FramelessWindowHint
        if bool(settings.get("keyboard_pinned", True)):
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setModal(False)

        try:
            self._tracker = FocusTracker.instance()
        except Exception:
            self._tracker = None

        self._second = False
        self._angle_mode = settings.get("angle_mode", "RAD") or "RAD"
        self._pinned = bool(settings.get("keyboard_pinned", True))
        self._module_key = "basic"
        self._layout = get_layout("basic")
        self._memory = 0.0
        self._buttons: list[KeyButton] = []

        self._build()
        self._restore_geometry()
        self._apply_theme()

    # ==================================================================

    def _build(self):
        self._titlebar = _TitleBar(self)
        self._titlebar.pin_btn.setChecked(self._pinned)
        self._titlebar.deg_btn.setText(self._angle_mode)
        self._titlebar.set_module_label(self._layout.label)

        self._grid_widget = QWidget()
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setContentsMargins(6, 4, 6, 4)
        self._grid.setSpacing(4)

        self._mem_bar = QWidget()
        mem_layout = QHBoxLayout(self._mem_bar)
        mem_layout.setContentsMargins(6, 0, 6, 4)
        mem_layout.setSpacing(4)
        for label, action in (("MC", "mem_clear"), ("MR", "mem_recall"),
                              ("M+", "mem_add"), ("M-", "mem_sub"),
                              ("MS", "mem_store")):
            b = QPushButton(label)
            b.setFocusPolicy(Qt.NoFocus)
            b.setFixedHeight(24)
            b.setProperty("keyStyle", "fn")
            b.clicked.connect(lambda _=False, a=action: self._do_memory(a))
            mem_layout.addWidget(b)
        mem_layout.addStretch(1)

        self._size_grip = QSizeGrip(self)
        self._size_grip.setFixedSize(16, 16)
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 4, 0)
        bottom.addStretch(1)
        bottom.addWidget(self._size_grip)

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        main.addWidget(self._titlebar)
        main.addWidget(self._grid_widget, 1)
        main.addWidget(self._mem_bar)
        main.addLayout(bottom)

        self._rebuild_grid()

    def _rebuild_grid(self):
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._buttons.clear()

        rows = self._layout.rows
        for r, row in enumerate(rows):
            col = 0
            for key in row:
                b = KeyButton(key)
                b.set_second(self._second)
                b.pressed_key.connect(self._on_key)
                span = max(1, int(getattr(key, "span", 1) or 1))
                self._grid.addWidget(b, r, col, 1, span)
                self._buttons.append(b)
                col += span

        max_cols = max(
            (sum(max(1, int(getattr(k, "span", 1) or 1)) for k in row)
             for row in rows),
            default=6,
        )
        for c in range(max_cols):
            self._grid.setColumnStretch(c, 1)
        for r in range(len(rows)):
            self._grid.setRowStretch(r, 1)

    def _restore_geometry(self):
        geom = self.settings.get("keyboard_geometry")
        if isinstance(geom, (list, tuple)) and len(geom) == 4:
            try:
                self.setGeometry(int(geom[0]), int(geom[1]),
                                 int(geom[2]), int(geom[3]))
                return
            except Exception:
                pass
        self.resize(560, 320)

    # ==================================================================

    def set_module(self, module_key: str):
        try:
            new_layout = get_layout(module_key or "basic")
        except Exception:
            return
        if new_layout is self._layout:
            return
        self._module_key = module_key or "basic"
        self._layout = new_layout
        try:
            self._titlebar.set_module_label(new_layout.label)
        except Exception:
            pass
        self._rebuild_grid()

    def current_module(self) -> str:
        return self._module_key

    # ==================================================================

    def _on_key(self, key):
        try:
            act = key.action or ""
            if act == "equals":
                self.equals_requested.emit()
                return
            if act == "clear":
                if self._tracker:
                    self._tracker.clear()
                return
            if act == "backspace":
                if self._tracker:
                    self._tracker.backspace()
                return
            if act == "second":
                self._second = not self._second
                for b in self._buttons:
                    b.set_second(self._second)
                return
            if act.startswith("mem_"):
                self._do_memory(act)
                return
            if act in ("cursor_left", "cursor_right",
                       "cursor_up", "cursor_down"):
                self._do_cursor(act)
                return
            if key.insert:
                text = self._smart_insert(key.insert)
                if self._tracker:
                    self._insert_with_cursor(text)
        except Exception as e:
            log_exc(e, module="CalcKeyboard._on_key")

    def _insert_with_cursor(self, text: str):
        """智能插入：

        - 若插入文本以 '(' 结尾，自动补 ')'，并把光标回退到括号中间。
        - 其它情况直接插入。
        """
        if not text:
            return
        try:
            if text.endswith("("):
                self._tracker.insert_text(text + ")")
                w = self._tracker.target()
                if w is not None and hasattr(w, "cursorPosition") \
                        and hasattr(w, "setCursorPosition"):
                    w.setCursorPosition(max(0, w.cursorPosition() - 1))
                return
            self._tracker.insert_text(text)
        except Exception as e:
            log_exc(e, module="CalcKeyboard._insert_with_cursor")

    def _smart_insert(self, text: str) -> str:
        """数字后接字母自动补 '*'；开头空格避免重复。"""
        try:
            if not text or not self._tracker:
                return text
            w = self._tracker.target()
            if w is None:
                return text

            cur = ""
            pos = 0
            if hasattr(w, "text"):
                cur = w.text()
                pos = (w.cursorPosition()
                       if hasattr(w, "cursorPosition") else len(cur))
            elif hasattr(w, "toPlainText"):
                cur = w.toPlainText()
                pos = len(cur)

            if text.startswith(" ") and pos > 0 and cur[pos - 1] == " ":
                text = text[1:]

            if pos > 0 and cur and cur[pos - 1].isdigit():
                first = text[0]
                if first.isalpha() and text not in ("pi", "e"):
                    return "*" + text
        except Exception:
            pass
        return text

    def _do_cursor(self, action: str):
        try:
            if not self._tracker:
                return
            w = self._tracker.target()
            if w is None or not hasattr(w, "cursorPosition"):
                return
            pos = w.cursorPosition()
            length = len(w.text()) if hasattr(w, "text") else 0
            if action == "cursor_left":
                w.setCursorPosition(max(0, pos - 1))
            elif action == "cursor_right":
                w.setCursorPosition(min(length, pos + 1))
            elif action == "cursor_up":
                w.setCursorPosition(0)
            elif action == "cursor_down":
                w.setCursorPosition(length)
        except Exception as e:
            log_exc(e, module="CalcKeyboard._do_cursor")

    # ==================================================================

    def _do_memory(self, action: str):
        try:
            if action == "mem_clear":
                self._memory = 0.0
            elif action == "mem_store":
                self._memory = self._read_current_value()
            elif action == "mem_recall":
                if self._tracker:
                    self._tracker.insert_text(str(self._memory))
            elif action == "mem_add":
                self._memory += self._read_current_value()
            elif action == "mem_sub":
                self._memory -= self._read_current_value()
        except Exception as e:
            log_exc(e, module="CalcKeyboard._do_memory")

    def _read_current_value(self) -> float:
        try:
            if not self._tracker:
                return 0.0
            w = self._tracker.target()
            if w is None:
                return 0.0
            if hasattr(w, "text"):
                txt = w.text()
                if txt:
                    return float(txt)
        except Exception:
            pass
        return 0.0

    # ==================================================================

    def toggle_angle_mode(self):
        self._angle_mode = "DEG" if self._angle_mode == "RAD" else "RAD"
        try:
            self.settings.set("angle_mode", self._angle_mode)
        except Exception:
            pass
        self._titlebar.deg_btn.setText(self._angle_mode)

    @property
    def angle_mode(self) -> str:
        return self._angle_mode

    def on_pin_toggled(self, on: bool):
        self._pinned = bool(on)
        try:
            self.settings.set("keyboard_pinned", self._pinned)
        except Exception:
            pass
        flags = self.windowFlags()
        if self._pinned:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    # ==================================================================

    def _apply_theme(self):
        try:
            pal = self.settings.palette()
        except Exception:
            pal = {}
        bg = pal.get("bg", "#1e1e1e")
        fg = pal.get("fg", "#ffffff")
        panel = pal.get("panel", "#2d2d30")
        accent = pal.get("accent", "#007acc")
        border = pal.get("border", "#3f3f46")
        hover = pal.get("hover", "#3a3d41")
        try:
            family = self.settings.get("font_family", "Microsoft YaHei")
        except Exception:
            family = "Microsoft YaHei"

        self.setStyleSheet(f"""
        QDialog#{_KEYBOARD_OBJECT_NAME} {{
            background: {panel};
            border: 1px solid {border};
            border-radius: 8px;
        }}
        QWidget#CalcKeyboardTitleBar {{
            background: {bg};
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
        }}
        QDialog#{_KEYBOARD_OBJECT_NAME} QLabel {{
            color: {fg}; background: transparent;
        }}
        QDialog#{_KEYBOARD_OBJECT_NAME} QPushButton {{
            background: {panel};
            color: {fg};
            border: 1px solid {border};
            border-radius: 6px;
            padding: 2px 6px;
            font-family: '{family}';
            font-size: 10pt;
        }}
        QDialog#{_KEYBOARD_OBJECT_NAME} QPushButton:hover {{
            background: {hover};
        }}
        QDialog#{_KEYBOARD_OBJECT_NAME} QPushButton:pressed {{
            background: {accent};
            color: #ffffff;
        }}
        QDialog#{_KEYBOARD_OBJECT_NAME} QPushButton[keyStyle="op"] {{
            color: {accent};
            font-weight: bold;
        }}
        QDialog#{_KEYBOARD_OBJECT_NAME} QPushButton[keyStyle="fn"] {{
            font-size: 9pt;
        }}
        QDialog#{_KEYBOARD_OBJECT_NAME} QPushButton[keyStyle="danger"] {{
            color: #ff6666;
        }}
        QDialog#{_KEYBOARD_OBJECT_NAME} QPushButton[keyStyle="accent"] {{
            background: {accent};
            color: #ffffff;
        }}
        """)

    def refresh_theme(self):
        self._apply_theme()

    # ==================================================================

    def closeEvent(self, e):
        try:
            g = self.geometry()
            self.settings.set("keyboard_geometry",
                              [g.x(), g.y(), g.width(), g.height()],
                              notify=False)
            self.settings.set("keyboard_visible", False, notify=False)
        except Exception:
            pass
        super().closeEvent(e)

    def showEvent(self, e):
        try:
            self.settings.set("keyboard_visible", True, notify=False)
        except Exception:
            pass
        super().showEvent(e)