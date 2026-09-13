"""分屏视图：把一个面板同时显示在主区和副区，便于对照。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QStackedWidget, QWidget

from core.logger import log_exc


class SplitView(QWidget):
    """主副区容器；只有当你启用时，才把副区加到布局右侧。"""

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

        lay = QSplitter(Qt.Horizontal)  # 占位避免 import 警告
        from PySide6.QtWidgets import QVBoxLayout
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