"""系统托盘：显示/隐藏窗口 + 快速打开 + 计算器键盘 + 退出。"""
from __future__ import annotations

from PySide6.QtGui import QAction, QIcon, QPixmap, QPainter, QColor
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from core.logger import log_exc


def _make_icon():
    """加载 assets/icon.ico；若不存在，回退到手绘。"""
    import os
    from PySide6.QtGui import QIcon
    # 打包后 base_path 与源码运行时的相对路径不同，尝试多个候选
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)),
                     "assets", "icon.ico"),
        os.path.join(os.getcwd(), "assets", "icon.ico"),
        # PyInstaller onefile 解包目录
        os.path.join(getattr(__import__("sys"), "_MEIPASS", ""),
                     "assets", "icon.ico"),
    ]
    for p in candidates:
        if p and os.path.exists(p):
            icon = QIcon(p)
            if not icon.isNull():
                return icon

    # 回退：原来的手绘逻辑
    pm = QPixmap(64, 64)
    pm.fill(QColor("#007acc"))
    p = QPainter(pm)
    p.setPen(QColor("#ffffff"))
    f = p.font(); f.setBold(True); f.setPointSize(24)
    p.setFont(f)
    p.drawText(pm.rect(), 0x84, "M")
    p.end()
    return QIcon(pm)


class Tray:
    def __init__(self, main_window, i18n):
        self.window = main_window
        self.i18n = i18n
        self._enabled = False
        self.tray = None

    def install(self):
        try:
            if QSystemTrayIcon.isSystemTrayAvailable() is False:
                return
            self.tray = QSystemTrayIcon(_make_icon(), self.window)
            self.tray.setToolTip(self.i18n.t("app_title"))

            menu = QMenu()
            act_show = QAction(self.i18n.t("show", "Show"), menu)
            act_show.triggered.connect(self._show)
            act_hide = QAction(self.i18n.t("hide", "Hide"), menu)
            act_hide.triggered.connect(self.window.hide)
            act_settings = QAction(self.i18n.t("settings"), menu)
            act_settings.triggered.connect(self._open_settings)

            act_kb = QAction(
                self.i18n.t("calc_keyboard", "计算器键盘"), menu)
            act_kb.triggered.connect(self._toggle_keyboard)

            act_quit = QAction(self.i18n.t("quit", "Quit"), menu)
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

    def is_enabled(self):
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
            from PySide6.QtWidgets import QApplication
            self.window._force_quit = True
            QApplication.instance().quit()
        except Exception:
            pass