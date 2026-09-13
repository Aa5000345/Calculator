# -*- coding: utf-8 -*-
"""主窗口：侧边栏导航 + 面板切换 + 热重载 + 状态持久化 + 模块显隐/排序。"""
from __future__ import annotations

import base64
import os

from PySide6.QtCore import Qt, QTimer, QFileSystemWatcher
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QStackedWidget,
    QDockWidget, QAbstractItemView, QDialog, QMessageBox,
)

from core.logger import log_exc, log_info
from ui.panels import (
    BasicPanel, ScientificPanel, UnitPanel, CurrencyPanel, BasePanel,
    MatrixPanel, StatsPanel, PlotPanel, Plot3DPanel, FinancePanel,
    DatePanel, RandomPanel, ProbabilityPanel, BitsPanel, CryptoPanel,
    LatexEditorPanel, HistoryPanel, SettingsPanel,
)
from ui.latex_widget import LatexLabel
from ui.settings_dialog import ModuleVisibilityDialog
from ui.shortcuts import install_main_window_shortcuts
from ui.command_palette import CommandPalette
from ui.tray import Tray
from ui.split_view import SplitView
from core import updater as update_mod
from core import plugins as plugin_mod


# 历史记录 module 字符串 → 面板 key
_MODULE_KEY_MAP = {
    "basic": "basic",
    "scientific": "scientific",
    "unit": "unit",
    "currency": "currency",
    "base": "base", "ascii": "base", "endian": "base", "ieee": "base",
    "matrix": "matrix",
    "stats": "stats",
    "plot": "plot",
    "plot3d": "plot3d",
    "random": "random",
    "bits": "bits",
    "latex": "latex",
    "settings": "settings",
}

_MODULE_PREFIX_MAP = (
    ("date-", "date"),
    ("finance-", "finance"),
    ("stats-", "stats"),
    ("random-", "random"),
    ("prob-", "probability"),
    ("bits-", "bits"),
    ("unit-", "unit"),
    ("currency-", "currency"),
    ("matrix-", "matrix"),
    ("enc-", "crypto_tools"),
    ("dec-", "crypto_tools"),
    ("hash-", "crypto_tools"),
    ("aes-", "crypto_tools"),
    ("rsa-", "crypto_tools"),
    ("classic-", "crypto_tools"),
    ("crypto", "crypto_tools"),
    ("totp", "crypto_tools"),
    ("pw-strength", "crypto_tools"),
)


class MainWindow(QMainWindow):
    def __init__(self, base_path, settings, i18n, history):
        super().__init__()
        self.base_path = base_path
        self.settings = settings
        self.i18n = i18n
        self.history = history

        self._panels = {}
        self._keys = []
        self._titles = {}
        self._split = None

        self._restore_geometry()
        self._build()
        self.settings.add_listener(self._on_settings_changed)

        self._watcher = QFileSystemWatcher(self)
        if getattr(settings, "user_path", None):
            try:
                self._watcher.addPath(settings.user_path)
            except Exception:
                pass
        self._watcher.fileChanged.connect(self._on_settings_file_changed)

        install_main_window_shortcuts(self)
        self._force_quit = False
        self._tray = Tray(self, self.i18n)
        if self.settings.get("tray_enabled", False):
            self._tray.install()
        self._build_menu()
        self._load_plugins()

    # ==================================================================
    # 几何持久化
    # ==================================================================

    def _restore_geometry(self):
        geom = self.settings.get("window_geometry")
        if isinstance(geom, (list, tuple)) and len(geom) == 4:
            try:
                self.setGeometry(int(geom[0]), int(geom[1]),
                                 int(geom[2]), int(geom[3]))
                return
            except Exception:
                pass
        size = self.settings.get("window_size")
        if isinstance(size, (list, tuple)) and len(size) == 2:
            try:
                self.resize(int(size[0]), int(size[1]))
                return
            except Exception:
                pass
        self.resize(1280, 880)

    # ==================================================================
    # 构建
    # ==================================================================

    def _build(self):
        self.setWindowTitle(self.i18n.t("app_title"))

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.dock = QDockWidget(self.i18n.t("modules", "Modules"), self)
        self.dock.setObjectName("modulesDock")
        self.dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.dock.setFeatures(
            QDockWidget.DockWidgetMovable |
            QDockWidget.DockWidgetFloatable |
            QDockWidget.DockWidgetClosable)

        side = QWidget()
        sl = QVBoxLayout(side)
        sl.setContentsMargins(6, 6, 6, 6)
        sl.setSpacing(6)

        self.toggle = QPushButton("≡")
        self.toggle.setFixedSize(34, 28)
        self.toggle.setToolTip(self.i18n.t("collapse", "Collapse"))
        self.toggle.clicked.connect(self.toggle_sidebar)

        self.vis_btn = QPushButton(self.i18n.t("module_visibility", "Visibility"))
        self.vis_btn.setFixedHeight(26)
        self.vis_btn.clicked.connect(self.open_visibility_dialog)

        head = QHBoxLayout()
        head.addWidget(self.toggle)
        head.addWidget(QLabel(self.i18n.t("modules", "Modules")))
        head.addStretch(1)

        self.list = QListWidget()
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.setDefaultDropAction(Qt.MoveAction)
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.setMinimumWidth(180)
        self.list.currentRowChanged.connect(self.switch)
        self.list.model().rowsMoved.connect(self._on_rows_moved)

        sl.addLayout(head)
        sl.addWidget(self.list, 1)
        sl.addWidget(self.vis_btn)
        self.dock.setWidget(side)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock)

        # ---- 注册面板 ----
        self._register("basic", self.i18n.t("basic"),
                       BasicPanel(self.settings, self.i18n, self.history))
        self._register("scientific", self.i18n.t("scientific"),
                       ScientificPanel(self.settings, self.i18n, self.history))
        self._register("unit", self.i18n.t("unit"),
                       UnitPanel(self.settings, self.i18n, self.history))
        self._register("currency", self.i18n.t("currency"),
                       CurrencyPanel(self.base_path, self.settings,
                                     self.i18n, self.history))
        self._register("base", self.i18n.t("base"),
                       BasePanel(self.settings, self.i18n, self.history))
        self._register("matrix", self.i18n.t("matrix"),
                       MatrixPanel(self.settings, self.i18n, self.history))
        self._register("stats", self.i18n.t("stats"),
                       StatsPanel(self.settings, self.i18n, self.history))
        self._register("plot", self.i18n.t("plot"),
                       PlotPanel(self.settings, self.i18n, self.history))
        self._register("plot3d", self.i18n.t("plot3d", "3D Plot"),
                       Plot3DPanel(self.settings, self.i18n, self.history))
        self._register("finance", self.i18n.t("finance"),
                       FinancePanel(self.settings, self.i18n, self.history))
        self._register("date", self.i18n.t("date"),
                       DatePanel(self.settings, self.i18n, self.history))
        self._register("random", self.i18n.t("random"),
                       RandomPanel(self.settings, self.i18n, self.history))
        self._register("probability", self.i18n.t("prob", "Probability"),
                       ProbabilityPanel(self.settings, self.i18n, self.history))
        self._register("bits", self.i18n.t("bits", "Bits"),
                       BitsPanel(self.settings, self.i18n, self.history))
        self._register("crypto_tools", self.i18n.t("crypto_tools", "Crypto Tools"),
                       CryptoPanel(self.settings, self.i18n, self.history))
        self._register("latex", self.i18n.t("latex_editor", "LaTeX Editor"),
                       LatexEditorPanel(self.settings, self.i18n, self.history))

        history_panel = HistoryPanel(self.history, self.i18n)
        history_panel.set_reuse_handler(self._on_reuse_from_history)
        self._register("history", self.i18n.t("history"), history_panel)

        self._register("settings", self.i18n.t("settings"),
                       SettingsPanel(self.settings, self.i18n, self))

        self._apply_saved_order()
        self._apply_visibility()

        last = self.settings.get("last_module", "basic")
        target_row = 0
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.UserRole) == last:
                target_row = i
                break
        if target_row < self.list.count():
            self.list.setCurrentRow(target_row)

        self._restore_layout()
        self.apply_theme()

    def _register(self, key, title, widget):
        item = QListWidgetItem(title)
        item.setData(Qt.UserRole, key)
        self.list.addItem(item)
        self._panels[key] = widget
        self._titles[key] = title
        self._keys.append(key)
        self.stack.addWidget(widget)

    def _apply_saved_order(self):
        saved = self.settings.get("module_order", [])
        if not isinstance(saved, list) or not saved:
            return
        ordered = [k for k in saved if k in self._panels]
        rest = [k for k in self._keys if k not in ordered]
        final = ordered + rest
        if final == self._keys or not final:
            return
        try:
            self.list.clear()
            while self.stack.count():
                self.stack.removeWidget(self.stack.widget(0))
            for k in final:
                item = QListWidgetItem(self._titles[k])
                item.setData(Qt.UserRole, k)
                self.list.addItem(item)
                self.stack.addWidget(self._panels[k])
            self._keys = final
        except Exception as e:
            log_exc(e, module="main_window._apply_saved_order")

    def _apply_visibility(self):
        for i in range(self.list.count()):
            item = self.list.item(i)
            key = item.data(Qt.UserRole)
            item.setHidden(not self.settings.is_module_visible(key))

    # ==================================================================
    # 拖拽排序
    # ==================================================================

    def _on_rows_moved(self, *_):
        try:
            keys = [self.list.item(i).data(Qt.UserRole)
                    for i in range(self.list.count())]
            if not keys:
                return
            self._keys = keys
            self.settings.set("module_order", keys, notify=False)

            current = self.stack.currentWidget()
            while self.stack.count():
                self.stack.removeWidget(self.stack.widget(0))
            for k in keys:
                self.stack.addWidget(self._panels[k])
            if current is not None:
                self.stack.setCurrentWidget(current)
        except Exception as e:
            log_exc(e, module="main_window._on_rows_moved")

    # ==================================================================
    # 交互
    # ==================================================================

    def switch(self, idx):
        if 0 <= idx < self.stack.count():
            self.stack.setCurrentIndex(idx)
            if 0 <= idx < len(self._keys):
                try:
                    self.settings.set("last_module", self._keys[idx],
                                      notify=False)
                except Exception:
                    pass

    def toggle_sidebar(self):
        self.list.setVisible(not self.list.isVisible())
        self.vis_btn.setVisible(self.list.isVisible())

    def open_visibility_dialog(self):
        try:
            current_keys = [self.list.item(i).data(Qt.UserRole)
                            for i in range(self.list.count())]
            titles = {k: self._titles.get(k, k) for k in current_keys}
            default_order = list(self._titles.keys())
            dlg = ModuleVisibilityDialog(
                self.i18n,
                current_order=current_keys,
                default_order=default_order,
                titles=titles,
                visible_getter=self.settings.is_module_visible,
                parent=self,
            )
            if dlg.exec() != QDialog.Accepted:
                return
            order, vis = dlg.result_state()

            self.settings.set("module_order", order, notify=False)
            for k, v in vis.items():
                try:
                    self.settings.set_module_visible(k, v)
                except Exception:
                    pass

            self._apply_saved_order()
            if order and order != self._keys:
                try:
                    self.list.clear()
                    while self.stack.count():
                        self.stack.removeWidget(self.stack.widget(0))
                    for k in order:
                        if k not in self._panels:
                            continue
                        item = QListWidgetItem(self._titles.get(k, k))
                        item.setData(Qt.UserRole, k)
                        self.list.addItem(item)
                        self.stack.addWidget(self._panels[k])
                    self._keys = [k for k in order if k in self._panels]
                except Exception as e:
                    log_exc(e, module="main_window.open_visibility_dialog.order")

            self._apply_visibility()
        except Exception as e:
            log_exc(e, module="main_window.open_visibility_dialog")

    # ==================================================================
    # 历史复用
    # ==================================================================

    @staticmethod
    def _normalize_module_key(module):
        m = str(module or "").strip().lower()
        if not m:
            return None
        if m in _MODULE_KEY_MAP:
            return _MODULE_KEY_MAP[m]
        for pfx, key in _MODULE_PREFIX_MAP:
            if m.startswith(pfx):
                return key
        return None

    def _on_reuse_from_history(self, module_key, expr):
        """由 HistoryPanel 双击/右键复用触发。"""
        if not expr:
            return
        key = self._normalize_module_key(module_key)
        panel = self._panels.get(key) if key else None
        if panel is None:
            # 兜底：直接复制到剪贴板
            try:
                QApplication.clipboard().setText(expr)
            except Exception:
                pass
            return

        # 切到该面板
        self._switch_by_key_pub(key)

        # 按优先级探测输入控件
        for attr in ("expr", "input", "data", "value", "d1",
                     "a", "enc_in", "cls_in"):
            w = getattr(panel, attr, None)
            if w is None:
                continue
            try:
                if hasattr(w, "setText"):
                    w.setText(expr)
                    if hasattr(w, "setCursorPosition"):
                        w.setCursorPosition(len(expr))
                    return
                if hasattr(w, "setPlainText"):
                    w.setPlainText(expr)
                    return
            except Exception:
                continue

        # 面板没有明显输入控件：复制到剪贴板
        try:
            QApplication.clipboard().setText(expr)
        except Exception:
            pass

    # ==================================================================
    # 热重载
    # ==================================================================

    def _on_settings_changed(self, key=None):
        try:
            if key == "language":
                QTimer.singleShot(0, self.rebuild)
                return

            if key is None:
                if self.settings.get("language") != self.i18n.lang:
                    QTimer.singleShot(0, self.rebuild)
                    return
                self._apply_visibility()

            if key == "visible_modules":
                self._apply_visibility()
            elif key == "module_order":
                try:
                    self._apply_saved_order()
                except Exception as e:
                    log_exc(e, module="main_window._apply_saved_order")

            if key in (None, "theme", "font_family", "font_size",
                       "palette", "result_format"):
                self.apply_theme()

            for p in self._panels.values():
                fn = getattr(p, "on_settings_changed", None)
                if callable(fn):
                    try:
                        fn(key)
                    except Exception as e:
                        log_exc(e, module="main_window.on_settings_changed")
        except Exception as e:
            log_exc(e, module="main_window._on_settings_changed")

    def _on_settings_file_changed(self, _path):
        QTimer.singleShot(200, self._reload_from_file)

    def _reload_from_file(self):
        try:
            old_lang = self.settings.get("language")
            if self.settings.reload_if_changed():
                if self.settings.get("language") != old_lang:
                    self.rebuild()
                else:
                    self._on_settings_changed(None)
        except Exception as e:
            log_exc(e, module="main_window._reload_from_file")
        finally:
            path = getattr(self.settings, "user_path", None)
            if path and path not in self._watcher.files():
                try:
                    self._watcher.addPath(path)
                except Exception:
                    pass

    # ==================================================================
    # 重建（语言切换）—— 用 shutdown_workers() 统一取消
    # ==================================================================

    def rebuild(self):
        try:
            self.i18n.load(self.settings.get("language", "zh_CN"))

            # 1) 先取消所有面板的 Worker
            for w in list(self._panels.values()):
                fn = getattr(w, "shutdown_workers", None)
                if callable(fn):
                    try:
                        fn(2000)
                    except Exception:
                        pass

            # 2) 再移除并销毁
            for w in list(self._panels.values()):
                try:
                    self.stack.removeWidget(w)
                except Exception:
                    pass
                try:
                    w.setParent(None)
                    w.deleteLater()
                except Exception:
                    pass
            self._panels.clear()
            self._keys.clear()
            self._titles.clear()
            self.list.clear()

            try:
                self.removeDockWidget(self.dock)
            except Exception:
                pass
            try:
                self.dock.deleteLater()
            except Exception:
                pass

            old = self.centralWidget()
            if old is not None:
                self.setCentralWidget(None)
                old.setParent(None)
                try:
                    old.deleteLater()
                except Exception:
                    pass

            if self._split is not None:
                try:
                    self._split.close_secondary()
                except Exception:
                    pass
                self._split = None
                self.setCentralWidget(None)

            self._build()
        except Exception as e:
            log_exc(e, module="main_window.rebuild")

    # ==================================================================
    # 主题
    # ==================================================================

    def _resolve_theme(self) -> str:
        theme = self.settings.get("theme", "dark")
        if theme != "system":
            return theme
        try:
            hints = QGuiApplication.styleHints()
            scheme = hints.colorScheme()
            if scheme == Qt.ColorScheme.Light:
                return "light"
        except Exception:
            pass
        return "dark"

    def apply_theme(self):
        try:
            resolved = self._resolve_theme()
            pal = self.settings.palette(resolved)
            bg = pal.get("bg", "#1e1e1e")
            fg = pal.get("fg", "#ffffff")
            panel = pal.get("panel", "#2d2d30")
            accent = pal.get("accent", "#007acc")
            border = pal.get("border", "#3f3f46")
            hover = pal.get("hover", "#3a3d41")

            family = self.settings.get("font_family", "Microsoft YaHei")
            size = int(self.settings.get("font_size", 11))

            self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background: {bg};
                color: {fg};
                font-family: '{family}';
                font-size: {size}pt;
            }}
            QDockWidget {{
                color: {fg};
                titlebar-close-icon: none;
                titlebar-normal-icon: none;
            }}
            QDockWidget::title {{
                background: {panel};
                padding: 6px;
                border: 1px solid {border};
            }}
            QLineEdit, QPlainTextEdit, QTextEdit, QComboBox,
            QSpinBox, QDoubleSpinBox {{
                background: {panel};
                color: {fg};
                border: 1px solid {border};
                padding: 5px;
                border-radius: 4px;
                selection-background-color: {accent};
            }}
            QPushButton {{
                background: {panel};
                color: {fg};
                border: 1px solid {border};
                padding: 6px 10px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background: {accent};
                color: #ffffff;
            }}
            QPushButton:pressed {{
                background: {hover};
            }}
            QPushButton:disabled {{
                color: #888888;
            }}
            QListWidget {{
                background: {panel};
                color: {fg};
                border: 1px solid {border};
                border-radius: 4px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 8px 10px;
            }}
            QListWidget::item:selected {{
                background: {accent};
                color: #ffffff;
            }}
            QListWidget::item:hover {{
                background: {hover};
            }}
            QTabWidget::pane {{
                border: 1px solid {border};
                border-radius: 4px;
            }}
            QTabBar::tab {{
                background: {panel};
                color: {fg};
                border: 1px solid {border};
                padding: 6px 14px;
            }}
            QTabBar::tab:selected {{
                background: {accent};
                color: #ffffff;
            }}
            QHeaderView::section {{
                background: {panel};
                color: {fg};
                border: 1px solid {border};
                padding: 5px;
            }}
            QTableWidget {{
                background: {panel};
                color: {fg};
                gridline-color: {border};
                border: 1px solid {border};
            }}
            QCheckBox, QLabel {{
                background: transparent;
                color: {fg};
            }}
            QSplitter::handle {{
                background: {border};
            }}
            QScrollArea {{
                border: none;
                background: {panel};
            }}
            QMenu {{
                background: {panel};
                color: {fg};
                border: 1px solid {border};
            }}
            QMenu::item:selected {{
                background: {accent};
                color: #ffffff;
            }}
            """)

            for lbl in self.findChildren(LatexLabel):
                try:
                    lbl.set_color(fg)
                except Exception:
                    pass

            for p in self._panels.values():
                fn = getattr(p, "set_theme_colors", None)
                if callable(fn):
                    try:
                        fn(fg, bg, panel)
                    except Exception:
                        pass
        except Exception as e:
            log_exc(e, module="main_window.apply_theme")

    # ==================================================================
    # 工作区布局持久化
    # ==================================================================

    def _save_layout(self):
        try:
            area = ("left" if self.dockWidgetArea(self.dock) == Qt.LeftDockWidgetArea
                    else "right")
            self.settings.set("workspace_layout", {
                "dock_area": area,
                "dock_visible": self.dock.isVisible(),
                "list_visible": self.list.isVisible(),
                "window_state": base64.b64encode(self.saveState()).decode("ascii"),
            }, notify=False)
        except Exception as e:
            log_exc(e, module="main_window._save_layout")

    def _restore_layout(self):
        layout = self.settings.get("workspace_layout")
        if not isinstance(layout, dict):
            return
        try:
            if "dock_area" in layout:
                area = {"left": Qt.LeftDockWidgetArea,
                        "right": Qt.RightDockWidgetArea}.get(
                            layout["dock_area"], Qt.LeftDockWidgetArea)
                self.addDockWidget(area, self.dock)
            if "dock_visible" in layout:
                self.dock.setVisible(bool(layout["dock_visible"]))
            if "list_visible" in layout:
                self.list.setVisible(bool(layout["list_visible"]))
                self.vis_btn.setVisible(bool(layout["list_visible"]))
            if "window_state" in layout and layout["window_state"]:
                try:
                    self.restoreState(base64.b64decode(layout["window_state"]))
                except Exception:
                    pass
        except Exception as e:
            log_exc(e, module="main_window._restore_layout")

    # ==================================================================
    # 菜单
    # ==================================================================

    def _build_menu(self):
        bar = self.menuBar()

        m_file = bar.addMenu(self.i18n.t("menu_file", "File"))
        a_quit = QAction(self.i18n.t("quit", "Quit"), self)
        a_quit.triggered.connect(self._quit_app)
        m_file.addAction(a_quit)

        m_view = bar.addMenu(self.i18n.t("menu_view", "View"))
        a_palette = QAction(self.i18n.t("command_palette", "Command palette"),
                            self)
        a_palette.setShortcut("Ctrl+K")
        a_palette.triggered.connect(self.open_command_palette)
        m_view.addAction(a_palette)

        a_split = QAction(self.i18n.t("open_in_split", "Open in split"), self)
        a_split.setShortcut("Ctrl+\\")
        a_split.triggered.connect(self.open_current_in_split)
        m_view.addAction(a_split)

        a_close_split = QAction(self.i18n.t("close_split", "Close split"), self)
        a_close_split.triggered.connect(self.close_split)
        m_view.addAction(a_close_split)

        m_view.addSeparator()
        a_vis = QAction(self.i18n.t("module_visibility", "Modules"), self)
        a_vis.triggered.connect(self.open_visibility_dialog)
        m_view.addAction(a_vis)

        m_tools = bar.addMenu(self.i18n.t("menu_tools", "Tools"))
        a_upd = QAction(self.i18n.t("check_update", "Check for updates"), self)
        a_upd.triggered.connect(self._check_update)
        m_tools.addAction(a_upd)

        a_plugins = QAction(self.i18n.t("plugins", "Plugins"), self)
        a_plugins.triggered.connect(self._show_plugins)
        m_tools.addAction(a_plugins)

        a_tray = QAction(self.i18n.t("toggle_tray", "Toggle tray"), self)
        a_tray.triggered.connect(self._toggle_tray)
        m_tools.addAction(a_tray)

    # ==================================================================
    # 命令面板
    # ==================================================================

    def _collect_commands(self):
        cmds = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            key = item.data(Qt.UserRole)
            title = item.text()
            cmds.append((f"{self.i18n.t('go_to', 'Go to')}: {title}",
                         (lambda k=key: self._switch_by_key_pub(k))))
        cmds.append((self.i18n.t("settings"), self._go_settings))
        cmds.append((self.i18n.t("module_visibility", "Modules"),
                     self.open_visibility_dialog))
        cmds.append((self.i18n.t("open_in_split", "Open in split"),
                     self.open_current_in_split))
        cmds.append((self.i18n.t("close_split", "Close split"),
                     self.close_split))
        cmds.append((self.i18n.t("check_update", "Check for updates"),
                     self._check_update))
        cmds.append((self.i18n.t("toggle_tray", "Toggle tray"),
                     self._toggle_tray))
        cmds.append((self.i18n.t("reset", "Reset settings"),
                     lambda: self.settings.reset()))
        return cmds

    def open_command_palette(self):
        try:
            dlg = CommandPalette(self.i18n, self._collect_commands(), self)
            dlg.exec()
        except Exception as e:
            log_exc(e, module="MainWindow.open_command_palette")

    def _switch_by_key_pub(self, key):
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.UserRole) == key:
                self.list.setCurrentRow(i)
                return
        try:
            self.settings.set_module_visible(key, True)
            self._apply_visibility()
            for i in range(self.list.count()):
                if self.list.item(i).data(Qt.UserRole) == key:
                    self.list.setCurrentRow(i)
                    return
        except Exception:
            pass

    def _go_settings(self):
        self._switch_by_key_pub("settings")

    # ==================================================================
    # 分屏
    # ==================================================================

    def _ensure_split(self):
        if self._split is None:
            old = self.centralWidget()
            if old is not None:
                self.takeCentralWidget()
                old.setParent(None)
            self._split = SplitView(self.stack, self)
            self.setCentralWidget(self._split)
        return self._split

    def open_current_in_split(self):
        try:
            key = None
            if self._keys and 0 <= self.stack.currentIndex() < len(self._keys):
                key = self._keys[self.stack.currentIndex()]
            if not key:
                return
            panel = self._panels.get(key)
            if panel is None:
                return
            sp = self._ensure_split()
            sp.show_panel(panel)
        except Exception as e:
            log_exc(e, module="MainWindow.open_current_in_split")

    def close_split(self):
        try:
            if self._split is None:
                return
            sec = self._split.secondary
            while sec.count():
                w = sec.widget(0)
                sec.removeWidget(w)
                if self.stack.indexOf(w) == -1:
                    self.stack.addWidget(w)
            self._split.close_secondary()
        except Exception as e:
            log_exc(e, module="MainWindow.close_split")

    # ==================================================================
    # 更新 / 插件 / 托盘
    # ==================================================================

    def _check_update(self):
        try:
            current = self.settings.get("app_version", "1.0.0")
            has, latest, url = update_mod.check_update(current)
            if has:
                QMessageBox.information(
                    self,
                    self.i18n.t("check_update", "Check for updates"),
                    f"{self.i18n.t('new_version', 'New version')}: {latest}\n{url}")
            else:
                QMessageBox.information(
                    self,
                    self.i18n.t("check_update", "Check for updates"),
                    self.i18n.t("up_to_date", "Up to date"))
        except Exception as e:
            log_exc(e, module="MainWindow._check_update")

    def _show_plugins(self):
        try:
            root = os.path.join(self.base_path, "plugins")
            infos = plugin_mod.discover(root)
            if not infos:
                QMessageBox.information(
                    self, self.i18n.t("plugins", "Plugins"),
                    self.i18n.t("no_plugins", "No plugins installed"))
                return
            text = "\n\n".join(
                f"{i.name}  v{i.version}\n{i.description}\n{i.path}"
                for i in infos)
            QMessageBox.information(
                self, self.i18n.t("plugins", "Plugins"), text)
        except Exception as e:
            log_exc(e, module="MainWindow._show_plugins")

    def _load_plugins(self):
        try:
            root = os.path.join(self.base_path, "plugins")
            for info in plugin_mod.discover(root):
                if info.enabled:
                    plugin_mod.load_plugin(info, app_context={
                        "settings": self.settings,
                        "i18n": self.i18n,
                        "history": self.history,
                        "main_window": self,
                    })
        except Exception as e:
            log_exc(e, module="MainWindow._load_plugins")

    def _toggle_tray(self):
        try:
            if self._tray.is_enabled():
                self._tray.uninstall()
                self.settings.set("tray_enabled", False)
            else:
                self._tray.install()
                self.settings.set("tray_enabled", True)
        except Exception as e:
            log_exc(e, module="MainWindow._toggle_tray")

    def _quit_app(self):
        try:
            self._force_quit = True
            QApplication.instance().quit()
        except Exception:
            pass

    # ==================================================================
    # 关闭：冲刷草稿 + 保存几何
    # ==================================================================

    def closeEvent(self, event):
        try:
            if (self._tray.is_enabled()
                    and self.settings.get("minimize_to_tray", True)
                    and not self._force_quit):
                event.ignore()
                self.hide()
                return
        except Exception:
            pass

        try:
            g = self.geometry()
            self.settings.set(
                "window_geometry",
                [g.x(), g.y(), g.width(), g.height()],
                notify=False)
            self.settings.set(
                "window_size", [self.width(), self.height()], notify=False)
            if self._keys and 0 <= self.stack.currentIndex() < len(self._keys):
                self.settings.set(
                    "last_module", self._keys[self.stack.currentIndex()],
                    notify=False)
            self._save_layout()
            # 冲刷草稿写盘
            try:
                self.settings.flush()
            except Exception:
                pass
        except Exception as e:
            log_exc(e, module="main_window.closeEvent")
        super().closeEvent(event)