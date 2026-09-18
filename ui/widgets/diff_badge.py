"""差异徽章：显示在结果旁的彩色小标签。

用法（ResultView 或面板中）：
    badge = DiffBadge(i18n)
    badge.update_from(prev_result, curr_result)
    layout.addWidget(badge)

设计：
- 数值差异 → 绿色（增）/ 红色（减）/ 灰色（同）
- 文本差异 → 蓝色
- 无差异 → 隐藏
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel


class DiffBadge(QLabel):
    """结果差异徽章。

    自动根据 DiffResult 渲染颜色与文本。
    """

    # 颜色
    COLOR_UP = "#2ecc71"
    COLOR_DOWN = "#e74c3c"
    COLOR_SAME = "#888888"
    COLOR_TEXT = "#3498db"
    COLOR_WARN = "#f39c12"

    def __init__(self, i18n=None, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        f = QFont()
        f.setPointSize(max(8, f.pointSize() - 1))
        f.setBold(True)
        self.setFont(f)
        self.setStyleSheet("padding: 1px 6px;")
        self.setVisible(False)
        self._current_diff = None

    # ------------------------------------------------------------------

    def update_from(self, prev, curr, tolerance: float = 1e-12):
        """比较两个结果并更新显示。"""
        from core import result_diff as rd
        diff = rd.compare(prev, curr, tolerance=tolerance)
        self.set_diff(diff)

    def set_diff(self, diff):
        """直接设置 DiffResult。"""
        self._current_diff = diff

        if diff is None or not diff.has_diff:
            self.setText("")
            self.setVisible(False)
            return

        from core import result_diff as rd
        text = rd.describe(diff, self.i18n)
        if not text:
            self.setVisible(False)
            return

        # 颜色
        if diff.kind == "numeric":
            if diff.direction == "+":
                color = self.COLOR_UP
            elif diff.direction == "-":
                color = self.COLOR_DOWN
            else:
                color = self.COLOR_SAME
        elif diff.kind == "text":
            color = self.COLOR_TEXT
        else:
            color = self.COLOR_WARN

        self.setText(text)
        self.setStyleSheet(
            f"color: {color};"
            f" background: rgba(128,128,128,0.12);"
            f" border-radius: 4px;"
            f" padding: 1px 6px;")
        self.setToolTip(
            f"上一次：{diff.prev_repr}\n"
            f"本次：  {diff.curr_repr}")
        self.setVisible(True)

    def clear(self):
        self.setText("")
        self.setVisible(False)
        self._current_diff = None

    def current_diff(self):
        return self._current_diff