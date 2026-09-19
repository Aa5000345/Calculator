"""Qt 运行期辅助：信号总线 / 状态栏 / 分屏 / Toast / 托盘。

合并自：ui/signals.py + ui/status_bar.py + ui/split_view.py
        + ui/toast.py + ui/tray.py

对外接口：
    # 信号总线
    bus() -> _Bus

    # 状态栏
    CalcStatusBar

    # 分屏
    SplitView

    # 非模态提示
    toast(parent, text, level, duration, on_click)

    # 系统托盘
    Tray
"""
from __future__ import annotations

import os
import sys
import time

from PySide6.QtCore import (
    Qt, QObject, Signal, QTimer,
    QPropertyAnimation, QEasingCurve,
)
from PySide6.QtGui import (
    QAction, QColor, QIcon, QPainter, QPixmap,
)
from PySide6.QtWidgets import (
    QApplication, QGraphicsOpacityEffect, QLabel, QMenu,
    QProgressBar, QSplitter, QStackedWidget, QStatusBar,
    QSystemTrayIcon, QVBoxLayout, QWidget,
)

from core.base import log_exc


__all__ = [
    "bus",
    "CalcStatusBar",
    "SplitView",
    "toast",
    "Tray",
]


# ===========================================================================
# 信号总线
# ===========================================================================

class _Bus(QObject):
    # 发送 "1.5 km" 之类的带单位文本到单位面板
    send_to_unit = Signal(str)

    # 跨面板发送
    send_to_basic = Signal(str)
    send_to_sci = Signal(str)
    send_to_table = Signal(str)
    send_to_snippet = Signal(str, str)   # (name, expr)
    send_to_plot = Signal(str)
    send_to_script = Signal(str)
    send_to_data_ops = Signal(str)

    # 剪贴板识别到表达式
    clipboard_expr = Signal(str)

    # 键盘"等于"信号
    keyboard_equals = Signal()


_BUS = _Bus()


def bus() -> _Bus:
    """获取全局信号总线单例。"""
    return _BUS


# ===========================================================================
# 状态栏
# ===========================================================================

class CalcStatusBar(QStatusBar):
    """主窗口状态栏。

    永久部件从左到右：
    - 当前面板名
    - 角度模式（RAD / DEG）
    - 内存值
    - 汇率新鲜度
    - 后台任务指示
    """

    def __init__(self, settings, i18n, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n

        self._panel_label = QLabel("")
        self._angle_label = QLabel("RAD")
        self._memory_label = QLabel("内存: 0")
        self._rate_label = QLabel("汇率: —")
        self._task_label = QLabel("")
        self._task_bar = QProgressBar()
        self._task_bar.setRange(0, 0)
        self._task_bar.setFixedWidth(80)
        self._task_bar.setVisible(False)

        for w in (self._panel_label, self._angle_label,
                  self._memory_label, self._rate_label):
            w.setStyleSheet("padding: 0 8px; color: #aaa;")
            self.addPermanentWidget(w)

        self.addPermanentWidget(self._task_bar)
        self.addPermanentWidget(self._task_label)

        # 汇率新鲜度定时刷新（每 5 分钟）
        self._rate_timer = QTimer(self)
        self._rate_timer.setInterval(5 * 60 * 1000)
        self._rate_timer.timeout.connect(self._refresh_rate_status)
        self._rate_timer.start()
        self._refresh_rate_status()

        try:
            settings.add_listener(self._on_settings_changed)
        except Exception:
            pass
        self._on_settings_changed(None)

    # ------------------------------------------------------------------

    def set_panel_name(self, name: str):
        self._panel_label.setText(f"[{name}]")

    def set_angle_mode(self, mode: str):
        self._angle_label.setText(str(mode or "RAD").upper())

    def set_memory(self, value: float):
        try:
            v = float(value)
            if abs(v - round(v)) < 1e-9:
                self._memory_label.setText(
                    f"内存: {int(round(v))}")
            else:
                self._memory_label.setText(f"内存: {v:g}")
        except Exception:
            self._memory_label.setText("内存: —")

    def set_task_active(self, active: bool, text: str = ""):
        self._task_bar.setVisible(bool(active))
        self._task_label.setText(
            text or ("⏳ 计算中" if active else ""))

    # ------------------------------------------------------------------

    def _on_settings_changed(self, key=None):
        if key in (None, "angle_mode"):
            try:
                self.set_angle_mode(
                    self.settings.get("angle_mode", "RAD"))
            except Exception:
                pass
        if key in (None, "memory"):
            try:
                self.set_memory(self.settings.get("memory", 0))
            except Exception:
                pass

    def _refresh_rate_status(self):
        try:
            from core import rates as rates_mod
            base = getattr(self.parent(), "base_path", None)
            if not base:
                self._rate_label.setText("汇率: —")
                return

            data = rates_mod.load_offline(base)
            updated = float(data.get("updated", 0) or 0)
            if updated <= 0:
                self._rate_label.setText("汇率: 离线")
                return

            age = time.time() - updated
            if age < 3600:
                text = f"{int(age / 60)} 分钟前"
            elif age < 86400:
                text = f"{int(age / 3600)} 小时前"
            else:
                text = f"{int(age / 86400)} 天前"
            self._rate_label.setText(f"汇率: {text}")
        except Exception:
            self._rate_label.setText("汇率: —")


# ===========================================================================
# 分屏
# ===========================================================================

class SplitView(QWidget):
    """主副区容器；只有启用时才把副区加到布局右侧。"""

    def __init__(self, primary_stack: QStackedWidget, parent=None):
        super().__init__(parent)
        self.primary = primary_stack
        self.secondary = QStackedWidget()
        self.secondary.setVisible(False)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.primary)
        self.splitter.addWidget(self.secondary)
        self.splitter.setSizes([700, 400])
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self.splitter)

    def is_open(self) -> bool:
        return self.secondary.isVisible() and self.secondary.count() > 0

    def show_panel(self, widget: QWidget):
        """把 widget 放进副区；同一 widget 会从主区移除。"""
        try:
            self.secondary.addWidget(widget)
            self.secondary.setCurrentWidget(widget)
            self.secondary.setVisible(True)
        except Exception as e:
            log_exc(e, module="SplitView.show_panel")

    def close_secondary(self):
        try:
            self.secondary.setVisible(False)
        except Exception:
            pass


# ===========================================================================
# Toast
# ===========================================================================

_ACTIVE: list = []

_TOAST_STYLE = {
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

        bg, fg, accent = _TOAST_STYLE.get(level, _TOAST_STYLE["info"])
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

        self._fade_in = QPropertyAnimation(
            self._effect, b"opacity", self)
        self._fade_in.setDuration(150)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)

        self._fade_out = QPropertyAnimation(
            self._effect, b"opacity", self)
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
        t = _Toast(parent, str(text), level=level,
                   duration=duration, on_click=on_click)
        _ACTIVE.append(t)
        _ACTIVE[:] = [x for x in _ACTIVE if x is not None]
        t.show_toast()
        return t
    except Exception:
        return None


# ===========================================================================
# 系统托盘
# ===========================================================================

def _make_tray_icon():
    """加载 assets/icon.ico；若不存在，回退到手绘。"""
    candidates = [
        os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "assets", "icon.ico"),
        os.path.join(os.getcwd(), "assets", "icon.ico"),
        os.path.join(getattr(sys, "_MEIPASS", ""),
                     "assets", "icon.ico"),
    ]
    for p in candidates:
        if p and os.path.exists(p):
            icon = QIcon(p)
            if not icon.isNull():
                return icon

    pm = QPixmap(64, 64)
    pm.fill(QColor("#007acc"))
    p = QPainter(pm)
    p.setPen(QColor("#ffffff"))
    f = p.font()
    f.setBold(True)
    f.setPointSize(24)
    p.setFont(f)
    p.drawText(pm.rect(), 0x84, "M")
    p.end()
    return QIcon(pm)


class Tray:
    """系统托盘：显示/隐藏窗口 + 快速打开 + 计算器键盘 + 退出。"""

    def __init__(self, main_window, i18n):
        self.window = main_window
        self.i18n = i18n
        self._enabled = False
        self.tray = None

    def install(self):
        try:
            if QSystemTrayIcon.isSystemTrayAvailable() is False:
                return
            self.tray = QSystemTrayIcon(
                _make_tray_icon(), self.window)
            self.tray.setToolTip(self.i18n.t("app_title"))

            menu = QMenu()
            act_show = QAction(
                self.i18n.t("show", "Show"), menu)
            act_show.triggered.connect(self._show)
            act_hide = QAction(
                self.i18n.t("hide", "Hide"), menu)
            act_hide.triggered.connect(self.window.hide)
            act_settings = QAction(
                self.i18n.t("settings"), menu)
            act_settings.triggered.connect(self._open_settings)

            act_kb = QAction(
                self.i18n.t("calc_keyboard", "计算器键盘"), menu)
            act_kb.triggered.connect(self._toggle_keyboard)

            act_quit = QAction(
                self.i18n.t("quit", "Quit"), menu)
            act_quit.triggered.connect(self._quit)

            menu.addAction(act_show)
            menu.addAction(act_hide)
            menu.addSeparator()
            menu.addAction(act_settings)
            menu.addAction(act_kb)
            menu.addSeparator()
            menu.addAction(act_quit)

            self.tray.setContextMenu(menu)
            self.tray.activated.connect(self._on_activated)
            self.tray.show()
            self._enabled = True
        except Exception as e:
            log_exc(e, module="Tray.install")

    def uninstall(self):
        try:
            if self.tray is not None:
                self.tray.hide()
                self.tray = None
            self._enabled = False
        except Exception:
            pass

    def is_enabled(self) -> bool:
        return self._enabled

    def _show(self):
        try:
            self.window.showNormal()
            self.window.raise_()
            self.window.activateWindow()
        except Exception:
            pass

    def _open_settings(self):
        try:
            self.window.showNormal()
            self.window._switch_by_key_pub("settings")
        except Exception:
            pass

    def _toggle_keyboard(self):
        try:
            self.window.showNormal()
            self.window.toggle_keyboard()
        except Exception:
            pass

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.window.isVisible():
                self.window.hide()
            else:
                self._show()

    def _quit(self):
        try:
            self.window._force_quit = True
            QApplication.instance().quit()
        except Exception:
            pass