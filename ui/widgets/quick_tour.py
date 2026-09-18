"""简短功能导览：首次启动后，用户可选择看一次。

设计：
- 5 步，每步一张卡片
- 上一步 / 下一步 / 跳过
- 可选「不再显示」（写入 settings）
- 不阻塞主界面：以对话框形式弹出

用法：
    dlg = QuickTour(i18n, parent)
    if dlg.exec() == QDialog.Accepted:
        # 用户看完了
        settings.set("tour_done", True)
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from core.logger import log_exc


# ---------------------------------------------------------------------------
# 步骤定义
# ---------------------------------------------------------------------------

_STEPS = [
    {
        "icon": "🧮",
        "title": "基础计算",
        "body": (
            "输入 `2+3*4`，按 Enter 即得结果。\n\n"
            "• 输入 `20% off 100` 直接算折扣\n"
            "• 输入 `tip 15% on 200` 算小费\n"
            "• M1~M9 是内存槽（左键召回、右键存入）"
        ),
    },
    {
        "icon": "⌨️",
        "title": "命令面板",
        "body": (
            "按 `Ctrl+K` 打开命令面板。\n\n"
            "• 输入 `= 2+2` 直接计算\n"
            "• 输入 `> theme` 只看主题相关命令\n"
            "• 输入 `jcjs` 拼音首字母搜「基础计算」\n"
            "• 越常用的命令越靠前"
        ),
    },
    {
        "icon": "🎹",
        "title": "浮动键盘",
        "body": (
            "按 `Ctrl+Shift+K` 呼出浮动键盘。\n\n"
            "• 不抢焦点，可以边看主窗口边点击\n"
            "• 自动跟随当前活跃的输入框\n"
            "• 支持 DEG / RAD 切换、2ⁿᵈ 二级函数、内存槽\n"
            "• 按模块自动切换布局（共 14 种）"
        ),
    },
    {
        "icon": "🔗",
        "title": "管道工作流",
        "body": (
            "把多步计算串起来：\n\n"
            "```\n"
            "1 km | to m | * 2 | round(3)\n"
            "100 USD | to CNY\n"
            "0.1 | as fraction\n"
            "```\n\n"
            "每一步的中间结果都会显示在表格里。"
        ),
    },
    {
        "icon": "📓",
        "title": "数学笔记本",
        "body": (
            "像 Jupyter 一样，但更轻。\n\n"
            "• 每个 cell 支持代码或 Markdown\n"
            "• `Shift+Enter` 运行并跳到下一个\n"
            "• 跨 cell 共享变量，自动持久化\n"
            "• 可导出 .mcnb 或 .ipynb"
        ),
    },
]


# ---------------------------------------------------------------------------
# 对话框
# ---------------------------------------------------------------------------

class QuickTour(QDialog):
    """功能导览对话框。"""

    def __init__(self, i18n, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self._index = 0
        self._skip_all = False

        self.setWindowTitle(i18n.t(
            "tour_title", "快速了解 MultiCalc"))
        self.resize(560, 420)
        self.setModal(True)

        # ---------------- 内容区 ----------------
        self.icon_label = QLabel("")
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet(
            "font-size: 56pt; padding: 10px;")

        self.title_label = QLabel("")
        self.title_label.setAlignment(Qt.AlignCenter)
        tf = QFont()
        tf.setBold(True)
        tf.setPointSize(16)
        self.title_label.setFont(tf)
        self.title_label.setStyleSheet("padding: 4px;")

        self.body_label = QLabel("")
        self.body_label.setWordWrap(True)
        self.body_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse)
        self.body_label.setStyleSheet(
            "font-size: 10pt; color: #ccc;"
            " padding: 8px 4px; line-height: 1.5;")

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(16, 8, 16, 8)
        cl.addWidget(self.icon_label)
        cl.addWidget(self.title_label)
        cl.addWidget(self.body_label, 1)

        # ---------------- 步骤指示器 ----------------
        self.step_label = QLabel("")
        self.step_label.setAlignment(Qt.AlignCenter)
        self.step_label.setStyleSheet(
            "color: #888; font-size: 9pt;")

        # ---------------- 按钮 ----------------
        self.b_skip = QPushButton(i18n.t("tour_skip", "跳过"))
        self.b_skip.clicked.connect(self._on_skip)

        self.b_prev = QPushButton(i18n.t("tour_prev", "上一步"))
        self.b_prev.clicked.connect(self._on_prev)

        self.b_next = QPushButton(i18n.t("tour_next", "下一步"))
        self.b_next.clicked.connect(self._on_next)
        self.b_next.setDefault(True)

        row = QHBoxLayout()
        row.addWidget(self.b_skip)
        row.addStretch(1)
        row.addWidget(self.b_prev)
        row.addWidget(self.b_next)

        # ---------------- 主布局 ----------------
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.addWidget(content, 1)
        lay.addWidget(self.step_label)
        lay.addLayout(row)

        self._update()

    # ==================================================================

    def _update(self):
        step = _STEPS[self._index]
        self.icon_label.setText(step["icon"])
        self.title_label.setText(self.i18n.t(
            "tour_step_" + str(self._index) + "_title",
            step["title"]))
        self.body_label.setText(self.i18n.t(
            "tour_step_" + str(self._index) + "_body",
            step["body"]))
        self.step_label.setText(
            f"{self._index + 1} / {len(_STEPS)}")

        self.b_prev.setEnabled(self._index > 0)
        if self._index >= len(_STEPS) - 1:
            self.b_next.setText(self.i18n.t("tour_done", "完成"))
        else:
            self.b_next.setText(self.i18n.t("tour_next", "下一步"))

    def _on_prev(self):
        if self._index > 0:
            self._index -= 1
            self._update()

    def _on_next(self):
        if self._index >= len(_STEPS) - 1:
            self.accept()
            return
        self._index += 1
        self._update()

    def _on_skip(self):
        self.reject()

    # ==================================================================

    @property
    def skipped(self) -> bool:
        """用户是否中途跳过。"""
        return self.result() != QDialog.Accepted

    # ==================================================================

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Right, Qt.Key_Down):
            self._on_next()
            return
        if key in (Qt.Key_Left, Qt.Key_Up):
            self._on_prev()
            return
        if key == Qt.Key_Escape:
            self._on_skip()
            return
        super().keyPressEvent(event)


__all__ = ["QuickTour"]