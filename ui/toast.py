"""非模态 Toast 通知。

显示在父窗口底部中央，自动消失，可叠加。不打断输入流。
用法：
    from ui.toast import toast
    toast(self.window(), "已复制到剪贴板")
    toast(self.window(), "导入成功", level="success", duration=2500)
    toast(self.window(), "网络失败", level="error", duration=4000)
    toast(self.window(), "点我算一算", level="info",
          duration=3500, on_click=my_callback)
level: info / success / warn / error
"""
from __future__ import annotations

from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
)
from PySide6.QtWidgets import (
    QLabel, QWidget, QVBoxLayout, QGraphicsOpacityEffect, QApplication,
)

_ACTIVE: list = []  # 当前显示的 toast

_STYLE = {
    "info":    ("#3a3d41", "#ffffff", "#007acc"),
    "success": ("#1e3a1e", "#c8f5c8", "#2ecc71"),
    "warn":    ("#3a3018", "#f5e8a8", "#f39c12"),
    "error":   ("#3a1e1e", "#f5c8c8", "#e74c3c"),
}


class _Toast(QWidget):
    def __init__(self, parent, text, level="info", duration=2500,
                 on_click=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        self._on_click = on_click

        bg, fg, accent = _STYLE.get(level, _STYLE["info"])
        self.setStyleSheet(f"""
            QWidget {{
                background: {bg};
                border: 1px solid {accent};
                border-radius: 6px;
            }}
            QLabel {{
                background: transparent;
                color: {fg};
                padding: 8px 14px;
                font-size: 10pt;
            }}
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setMaximumWidth(480)
        lay.addWidget(self.label)

        self.adjustSize()
        self.setMinimumWidth(min(360, self.sizeHint().width() + 8))

        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self.setGraphicsEffect(self._effect)

        self._fade_in = QPropertyAnimation(self._effect, b"opacity", self)
        self._fade_in.setDuration(150)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)

        self._fade_out = QPropertyAnimation(self._effect, b"opacity", self)
        self._fade_out.setDuration(250)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.finished.connect(self._remove_self)

        self._duration = int(duration)

    def show_toast(self):
        self._reposition()
        self.show()
        self.raise_()
        self._fade_in.start()
        QTimer.singleShot(self._duration, self._fade_out.start)

    def _reposition(self):
        parent = self.parent()
        if parent is None:
            return
        try:
            pr = parent.rect()
            offset = 0
            for t in _ACTIVE:
                if t is self or not t.isVisible():
                    continue
                offset += t.height() + 6
            x = pr.center().x() - self.width() // 2
            y = pr.height() - self.height() - 24 - offset
            self.move(max(8, x), max(8, y))
        except Exception:
            pass

    def _remove_self(self):
        try:
            if self in _ACTIVE:
                _ACTIVE.remove(self)
        except Exception:
            pass
        for t in list(_ACTIVE):
            try:
                t._reposition()
            except Exception:
                pass
        self.deleteLater()

    def mousePressEvent(self, e):
        # 点击：先执行回调，再关闭
        if self._on_click is not None:
            try:
                self._on_click()
            except Exception:
                pass
        try:
            self._fade_out.start()
        except Exception:
            self._remove_self()


def toast(parent, text, level="info", duration=2500, on_click=None):
    """在 parent 底部弹出一个非模态提示。

    on_click：可选；点击 toast 时调用的无参回调。
    """
    try:
        if parent is None:
            parent = QApplication.activeWindow()
        if parent is None:
            return None
        t = _Toast(parent, str(text), level=level, duration=duration,
                   on_click=on_click)
        _ACTIVE.append(t)
        _ACTIVE[:] = [x for x in _ACTIVE if x is not None]
        t.show_toast()
        return t
    except Exception:
        return None