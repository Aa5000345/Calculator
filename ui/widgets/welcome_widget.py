"""首次运行欢迎页：介绍功能 + 快捷入口 + 最近打开。

由 MainWindow 在首次启动时展示（也可从菜单手动打开）。

用法：
    w = WelcomeWidget(settings, i18n, base_path)
    w.quick_action.connect(on_action)     # action, payload
    w.show_panel_requested.connect(...)   # panel_key
    layout.addWidget(w)
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from core import recent_files as rf_mod
from core.logger import log_exc


# ---------------------------------------------------------------------------
# 快捷入口卡片
# ---------------------------------------------------------------------------

class _QuickCard(QFrame):
    """一个快捷入口卡片。"""

    clicked = Signal()

    def __init__(self, icon: str, title: str, subtitle: str,
                 parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(80)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.setStyleSheet(
            "_QuickCard {"
            "  background: rgba(128,128,128,0.08);"
            "  border: 1px solid rgba(128,128,128,0.25);"
            "  border-radius: 8px;"
            "}"
            "_QuickCard:hover {"
            "  background: rgba(128,128,128,0.16);"
            "  border-color: rgba(128,128,128,0.45);"
            "}")

        icon_label = QLabel(icon)
        icon_label.setStyleSheet(
            "font-size: 22pt; padding: 4px;")
        icon_label.setFixedWidth(48)
        icon_label.setAlignment(Qt.AlignCenter)

        title_label = QLabel(title)
        tf = QFont()
        tf.setBold(True)
        tf.setPointSize(11)
        title_label.setFont(tf)

        sub_label = QLabel(subtitle)
        sub_label.setStyleSheet("color: #888; font-size: 9pt;")
        sub_label.setWordWrap(True)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)
        text_col.addWidget(title_label)
        text_col.addWidget(sub_label)
        text_col.addStretch(1)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.addWidget(icon_label)
        lay.addLayout(text_col, 1)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


# ---------------------------------------------------------------------------
# 主组件
# ---------------------------------------------------------------------------

class WelcomeWidget(QWidget):
    """欢迎页。"""

    quick_action = Signal(str, dict)          # action, payload
    panel_requested = Signal(str)              # panel_key
    recent_opened = Signal(str, str)           # path, kind

    def __init__(self, settings, i18n, base_path: str = "",
                 parent=None):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n
        self.base_path = base_path

        # ---------------- 顶部：欢迎语 ----------------
        self.hello = QLabel(i18n.t(
            "welcome_hello", "👋 欢迎使用 MultiCalc"))
        hf = QFont()
        hf.setBold(True)
        hf.setPointSize(18)
        self.hello.setFont(hf)

        self.hello_sub = QLabel(i18n.t(
            "welcome_sub",
            "键盘驱动、随手可用的多功能计算器"))
        self.hello_sub.setStyleSheet("color: #888; font-size: 11pt;")

        # ---------------- 快捷入口 ----------------
        self._cards_layout = QGridLayout()
        self._cards_layout.setSpacing(8)
        self._build_quick_cards()

        # ---------------- 最近打开 ----------------
        self.recent_box = QVBoxLayout()
        self.recent_box.setSpacing(4)

        # ---------------- 页脚 ----------------
        self.footer = QLabel(i18n.t(
            "welcome_footer",
            "提示：按 F1 查看所有快捷键；Ctrl+K 打开命令面板；"
            "设置里可以切换主题和语言。"))
        self.footer.setWordWrap(True)
        self.footer.setStyleSheet(
            "color: #777; padding: 8px; font-size: 9pt;")

        # ---------------- 主布局 ----------------
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(24, 24, 24, 24)
        cl.setSpacing(14)
        cl.addWidget(self.hello)
        cl.addWidget(self.hello_sub)
        cl.addSpacing(6)

        cl.addWidget(self._section_label(i18n.t(
            "welcome_quick_start", "快速开始")))
        cl.addLayout(self._cards_layout)
        cl.addSpacing(6)

        cl.addWidget(self._section_label(i18n.t(
            "welcome_recent", "最近打开")))
        cl.addLayout(self.recent_box)
        cl.addStretch(1)
        cl.addWidget(self.footer)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(scroll)

        self._refresh_recent()

    # ==================================================================

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        f = lbl.font()
        f.setBold(True)
        f.setPointSize(f.pointSize() + 1)
        lbl.setFont(f)
        lbl.setStyleSheet("padding-top: 6px;")
        return lbl

    def _build_quick_cards(self):
        cards = [
            ("🧮", "welcome_card_basic",
             "基础计算", "输入 2+3*4，立即得到结果",
             "basic"),
            ("🔬", "welcome_card_scientific",
             "科学计算", "求解方程、求导、积分",
             "scientific"),
            ("🔄", "welcome_card_unit",
             "单位换算", "1 km → m，100 USD → CNY",
             "unit"),
            ("🔐", "welcome_card_crypto",
             "加密工具", "AES / RSA / 文件加密 / PQC",
             "crypto_tools"),
            ("📓", "welcome_card_notebook",
             "数学笔记本", "多步推导，跨 cell 共享变量",
             "notebook"),
            ("🤖", "welcome_card_ai",
             "AI 助手", "自然语言 → 表达式，支持多轮",
             "ai"),
        ]
        for i, (icon, key, title, sub, panel) in enumerate(cards):
            card = _QuickCard(
                icon,
                self.i18n.t(key, title),
                self.i18n.t(key + "_sub", sub))
            card.clicked.connect(
                lambda _=False, p=panel: self.panel_requested.emit(p))
            self._cards_layout.addWidget(card, i // 2, i % 2)

    def _refresh_recent(self):
        # 清空
        while self.recent_box.count():
            item = self.recent_box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        try:
            items = rf_mod.list_existing(limit=6)
        except Exception as e:
            log_exc(e, module="WelcomeWidget._refresh_recent")
            items = []

        if not items:
            empty = QLabel(self.i18n.t(
                "welcome_no_recent",
                "还没有最近打开的文件。试试打开一个 .mcnb 笔记本或导出历史。"))
            empty.setStyleSheet(
                "color: #666; padding: 8px; font-size: 10pt;")
            empty.setWordWrap(True)
            self.recent_box.addWidget(empty)
            return

        for it in items:
            btn = QPushButton(
                f"  {self._kind_icon(it.kind)}  "
                f"{it.display()}")
            btn.setStyleSheet(
                "QPushButton {"
                "  text-align: left;"
                "  background: rgba(128,128,128,0.06);"
                "  border: none;"
                "  border-radius: 4px;"
                "  padding: 6px 10px;"
                "  font-size: 10pt;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(128,128,128,0.18);"
                "}")
            btn.setToolTip(f"{it.path}\n{it.opened_at}")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(
                lambda _=False, p=it.path, k=it.kind:
                self.recent_opened.emit(p, k))
            self.recent_box.addWidget(btn)

    @staticmethod
    def _kind_icon(kind: str) -> str:
        return {
            "session": "📂",
            "notebook": "📓",
            "csv": "📊",
            "json": "📄",
            "enc": "🔒",
            "image": "🖼️",
            "other": "📄",
        }.get(str(kind or "").lower(), "📄")

    # ==================================================================

    def refresh(self):
        """外部触发刷新（如最近文件变化后）。"""
        self._refresh_recent()


__all__ = ["WelcomeWidget"]