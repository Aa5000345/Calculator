# -*- coding: utf-8 -*-
from PySide6.QtCore import Qt, QTimer, QFileSystemWatcher
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QStackedWidget, QDockWidget,
    QAbstractItemView
)

from ui.panels import (
    BasicPanel, ScientificPanel, UnitPanel, CurrencyPanel, BasePanel,
    MatrixPanel, StatsPanel, PlotPanel, FinancePanel, DatePanel,
    RandomPanel, HistoryPanel, SettingsPanel
)
from ui.latex_widget import LatexLabel


class MainWindow(QMainWindow):
    def __init__(self, base_path, settings, i18n, history):
        super().__init__()
        self.base_path = base_path
        self.settings = settings
        self.i18n = i18n
        self.history = history

        self._panels = {}   # key -> widget
        self._keys = []     # 顺序

        self._build()
        self.settings.add_listener(self._on_settings_changed)

        # 监听 settings.json 外部改动
        self._watcher = QFileSystemWatcher(self)
        if settings.user_path:
            try:
                self._watcher.addPath(settings.user_path)
            except Exception:
                pass
        self._watcher.fileChanged.connect(self._on_settings_file_changed)

    # ==================================================================
    # 构建
    # ==================================================================

    def _build(self):
        self.setWindowTitle(self.i18n.t("app_title"))
        self.resize(1280, 850)

        # ---- 内容区 ----
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # ---- 侧边栏 Dock（可拖动停靠 / 浮动） ----
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

        head = QHBoxLayout()
        head.addWidget(self.toggle)
        head.addWidget(QLabel(self.i18n.t("modules", "Modules")))
        head.addStretch(1)

        self.list = QListWidget()
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.setDefaultDropAction(Qt.MoveAction)
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.setMinimumWidth(160)
        self.list.currentRowChanged.connect(self.switch)
        self.list.model().rowsMoved.connect(self._on_rows_moved)

        sl.addLayout(head)
        sl.addWidget(self.list, 1)
        self.dock.setWidget(side)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock)

        # ---- 注册面板 ----
        self._register("basic",     self.i18n.t("basic"),
                       BasicPanel(self.settings, self.i18n, self.history))
        self._register("scientific", self.i18n.t("scientific"),
                       ScientificPanel(self.settings, self.i18n, self.history))
        self._register("unit",      self.i18n.t("unit"),
                       UnitPanel(self.settings, self.i18n, self.history))
        self._register("currency",  self.i18n.t("currency"),
                       CurrencyPanel(self.base_path, self.settings,
                                     self.i18n, self.history))
        self._register("base",      self.i18n.t("base"),
                       BasePanel(self.settings, self.i18n, self.history))
        self._register("matrix",    self.i18n.t("matrix"),
                       MatrixPanel(self.settings, self.i18n, self.history))
        self._register("stats",     self.i18n.t("stats"),
                       StatsPanel(self.settings, self.i18n, self.history))
        self._register("plot",      self.i18n.t("plot"),
                       PlotPanel(self.settings, self.i18n, self.history))
        self._register("finance",   self.i18n.t("finance"),
                       FinancePanel(self.settings, self.i18n, self.history))
        self._register("date",      self.i18n.t("date"),
                       DatePanel(self.settings, self.i18n, self.history))
        self._register("random",    self.i18n.t("random"),
                       RandomPanel(self.settings, self.i18n, self.history))
        self._register("history",   self.i18n.t("history"),
                       HistoryPanel(self.history, self.i18n))
        self._register("settings",  self.i18n.t("settings"),
                       SettingsPanel(self.settings, self.i18n, self))

        self.list.setCurrentRow(0)
        self.apply_theme()

    def _register(self, key, title, widget):
        item = QListWidgetItem(title)
        item.setData(Qt.UserRole, key)
        self.list.addItem(item)
        self._panels[key] = widget
        self._keys.append(key)
        self.stack.addWidget(widget)

    # ==================================================================
    # 拖拽排序
    # ==================================================================

    def _on_rows_moved(self, *_):
        keys = [self.list.item(i).data(Qt.UserRole)
                for i in range(self.list.count())]
        if not keys:
            return
        self._keys = keys
        current = self.stack.currentWidget()
        while self.stack.count():
            self.stack.removeWidget(self.stack.widget(0))
        for k in keys:
            self.stack.addWidget(self._panels[k])
        if current is not None:
            self.stack.setCurrentWidget(current)

    # ==================================================================
    # 交互
    # ==================================================================

    def switch(self, idx):
        if 0 <= idx < self.stack.count():
            self.stack.setCurrentIndex(idx)

    def toggle_sidebar(self):
        self.list.setVisible(not self.list.isVisible())

    # ==================================================================
    # 热重载
    # ==================================================================

    def _on_settings_changed(self, key=None):
        if key == "language":
            QTimer.singleShot(0, self.rebuild)
            return
        self.apply_theme()
        for p in self._panels.values():
            fn = getattr(p, "on_settings_changed", None)
            if callable(fn):
                try:
                    fn(key)
                except Exception:
                    pass

    def _on_settings_file_changed(self, _path):
        QTimer.singleShot(200, self._reload_from_file)

    def _reload_from_file(self):
        old_lang = self.settings.get("language")
        if self.settings.reload_if_changed():
            if self.settings.get("language") != old_lang:
                self.rebuild()
            else:
                self._on_settings_changed(None)
        path = self.settings.user_path
        if path and path not in self._watcher.files():
            try:
                self._watcher.addPath(path)
            except Exception:
                pass

    # ==================================================================
    # 重建（语言切换）
    # ==================================================================

    def rebuild(self):
        self.i18n.load(self.settings.get("language", "zh_CN"))

        # 销毁旧面板
        for w in list(self._panels.values()):
            try:
                self.stack.removeWidget(w)
            except Exception:
                pass
            w.setParent(None)
            w.deleteLater()
        self._panels.clear()
        self._keys.clear()
        self.list.clear()

        # 销毁 dock
        try:
            self.removeDockWidget(self.dock)
        except Exception:
            pass
        self.dock.deleteLater()

        # 销毁 central
        old = self.centralWidget()
        if old is not None:
            self.setCentralWidget(None)
            old.deleteLater()

        self._build()

    # ==================================================================
    # 主题
    # ==================================================================

    def apply_theme(self):
        theme = self.settings.get("theme", "dark")
        family = self.settings.get("font_family", "Microsoft YaHei")
        size = int(self.settings.get("font_size", 11))

        if theme == "dark":
            bg, fg, panel, accent = "#1e1e1e", "#ffffff", "#2d2d30", "#007acc"
            border, hover = "#3f3f46", "#3a3d41"
        else:
            bg, fg, panel, accent = "#f5f5f5", "#000000", "#ffffff", "#0066cc"
            border, hover = "#c8c8c8", "#e6e6e6"

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
        """)

        # ---- LaTeX 标签颜色跟随主题 ----
        for lbl in self.findChildren(LatexLabel):
            try:
                lbl.set_color(fg)
            except Exception:
                pass

        # ---- 通知面板更新画布背景/前景色 ----
        for p in self._panels.values():
            fn = getattr(p, "set_theme_colors", None)
            if callable(fn):
                try:
                    fn(fg, bg, panel)
                except Exception:
                    pass
