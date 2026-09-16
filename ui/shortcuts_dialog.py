"""快捷键速查表对话框（F1 打开）。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFormLayout, QFrame,
)


_SHORTCUTS = [
    ("全局", [
        ("Ctrl+K", "命令面板"),
        ("Ctrl+Shift+K", "显示 / 隐藏浮动计算器键盘"),
        ("Ctrl+,", "打开设置面板"),
        ("Ctrl+1 ~ Ctrl+9", "切换到第 N 个可见模块"),
        ("Ctrl+\\", "当前面板在分屏中打开"),
        ("Ctrl+Shift+L", "显示 / 隐藏侧边栏"),
        ("F1", "快捷键速查表（本窗口）"),
        ("Esc", "关闭对话框 / 取消任务"),
    ]),
    ("输入框内", [
        ("Enter", "计算（输入框内）"),
        ("Ctrl+Enter", "计算（不限焦点）"),
        ("Esc", "取消运行中的任务；基础面板中清空输入"),
        ("Ctrl+L", "清空输入"),
        ("↑ / ↓", "召回历史表达式"),
    ]),
    ("浮动键盘", [
        ("2ⁿᵈ", "切换二级函数（sin⁻¹ / cos⁻¹ / x³ …）"),
        ("=", "触发当前面板 calc()"),
        ("C", "清空当前输入框"),
        ("⌫", "退格"),
        ("RAD / DEG", "切换角度模式"),
        ("📌", "置顶开关"),
        ("(", "自动补全右括号，光标停在中间"),
    ]),
    ("命令面板", [
        ("= 2+2", "直接计算，结果内联显示，Enter 复制"),
        ("> theme", "只匹配 theme: 前缀命令"),
        ("> 任意", "只匹配命令，忽略历史与计算"),
        ("Tab", "在搜索框 / 列表间切换焦点"),
        ("↑ / ↓", "在列表中移动"),
    ]),
    ("结果面板", [
        ("右键", "复制为文本 / LaTeX / JSON / CSV；发送到其他面板"),
    ]),
]


class ShortcutsDialog(QDialog):
    def __init__(self, i18n, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.setWindowTitle(i18n.t("shortcuts_title", "快捷键速查表"))
        self.resize(580, 660)

        main = QVBoxLayout(self)
        main.setContentsMargins(12, 12, 12, 12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        cv = QVBoxLayout(content)
        cv.setContentsMargins(4, 4, 4, 4)
        cv.setSpacing(10)

        for section, items in _SHORTCUTS:
            cv.addWidget(self._make_section(section, items))

        cv.addStretch(1)
        scroll.setWidget(content)
        main.addWidget(scroll, 1)

        close_btn = QPushButton(i18n.t("close", "关闭"))
        close_btn.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close_btn)
        main.addLayout(row)

    def _make_section(self, title, items):
        box = QFrame()
        box.setFrameShape(QFrame.StyledPanel)
        lay = QVBoxLayout(box)

        hdr = QLabel(title)
        f = hdr.font()
        f.setBold(True)
        f.setPointSize(f.pointSize() + 1)
        hdr.setFont(f)
        lay.addWidget(hdr)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        for key, desc in items:
            k = QLabel(key)
            k.setStyleSheet(
                "background: rgba(128,128,128,0.22);"
                "padding: 2px 8px; border-radius: 4px;"
                "font-family: Consolas, monospace;")
            k.setTextInteractionFlags(Qt.TextSelectableByMouse)
            d = QLabel(desc)
            d.setWordWrap(True)
            d.setTextInteractionFlags(Qt.TextSelectableByMouse)
            form.addRow(k, d)
        lay.addLayout(form)
        return box