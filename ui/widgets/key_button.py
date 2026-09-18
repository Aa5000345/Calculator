"""单键组件：NoFocus + 2ⁿᵈ 切换 + 主题化 QSS。"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QPushButton, QSizePolicy

from .keyboard_layouts import Key


class KeyButton(QPushButton):
    """一个按键。

    发出 ``pressed_key(Key)`` 信号——已经在 2ⁿᵈ 状态下替换为对应 Key。
    """

    pressed_key = Signal(object)

    def __init__(self, key: Key, parent=None):
        super().__init__(parent)
        self._key = key
        self._second = False
        self.setFocusPolicy(Qt.NoFocus)
        self.setMinimumSize(36, 32)
        self.setSizePolicy(QSizePolicy.Expanding,
                           QSizePolicy.Expanding)
        if key.tooltip:
            self.setToolTip(key.tooltip)
        self.clicked.connect(self._on_click)
        self._refresh()

    # ------------------------------------------------------------------

    def key_def(self) -> Key:
        return self._key

    def set_second(self, on: bool):
        if self._second == on:
            return
        self._second = on
        self._refresh()

    def _effective(self) -> Key:
        k = self._key
        if self._second and k.alt_label:
            return Key(
                label=k.alt_label,
                insert=k.alt_insert,
                action=k.alt_action
                or ("insert" if k.alt_insert else ""),
                tooltip=k.tooltip,
                style=k.style,
                span=k.span,
            )
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


__all__ = ["KeyButton"]