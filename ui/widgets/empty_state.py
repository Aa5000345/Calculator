"""可复用的空状态提示组件。

用法：
    es = EmptyState(
        icon="📋",
        title="还没有历史记录",
        subtitle="计算后会自动记录在这里",
        action_text="开始计算",
    )
    es.action_clicked.connect(on_action)
    layout.addWidget(es)

设计：
- 垂直居中：大图标 + 标题 + 副标题 + 可选按钮
- 自适应父容器大小
- 支持自定义图标（emoji / 文本）
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel, QPushButton, QVBoxLayout, QWidget, QSizePolicy,
)


class EmptyState(QWidget):
    """空状态提示。

    - icon: emoji / 短文本
    - title: 主标题
    - subtitle: 副标题（可空）
    - action_text: 按钮文字（空则不显示按钮）
    """

    action_clicked = Signal()

    def __init__(self, icon: str = "📭",
                 title: str = "",
                 subtitle: str = "",
                 action_text: str = "",
                 parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

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

        # 按钮居中
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
        """紧凑模式：小图标，少留白。"""
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