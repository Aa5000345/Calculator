"""快捷键速查表对话框（F1 打开）。

变更历史：
- 第 1 轮：初版
- 第 4 轮：新增「自定义」Tab
- 第 18 轮：「自定义」Tab 改为内嵌 ShortcutEditor
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFormLayout, QFrame, QTabWidget,
)

from core.logger import log_exc


# ---------------------------------------------------------------------------
# 速查内容（保持简洁、面向新手）
# ---------------------------------------------------------------------------

_SHORTCUTS = [
    ("全局", [
        ("Ctrl+K", "命令面板（支持拼音首字母）"),
        ("Ctrl+Shift+K", "显示 / 隐藏浮动计算器键盘"),
        ("Ctrl+,", "打开设置面板"),
        ("Ctrl+1 ~ Ctrl+9", "切换到第 N 个可见模块"),
        ("Ctrl+\\", "当前面板在分屏中打开"),
        ("Ctrl+Shift+L", "显示 / 隐藏侧边栏"),
        ("Ctrl+Shift+H", "手写输入"),
        ("Ctrl+Shift+O", "截图 / 图片识别"),
        ("Ctrl+Shift+Z", "保存会话快照"),
        ("Ctrl+Shift+Y", "打开快照时间线"),
        ("F11", "专注模式"),
        ("F1", "快捷键速查表（本窗口）"),
        ("Esc", "关闭对话框 / 取消任务"),
    ]),
    ("输入框内", [
        ("Enter", "计算（输入框内）"),
        ("Ctrl+Enter", "计算（不限焦点）"),
        ("Esc", "取消运行中的任务；基础面板中清空输入"),
        ("Ctrl+L", "清空输入"),
        ("Ctrl+Z", "撤销上一次操作"),
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
        ("jcjs", "拼音首字母搜索（基础计算）"),
        ("Tab", "在搜索框 / 列表间切换焦点"),
        ("↑ / ↓", "在列表中移动"),
    ]),
    ("结果面板", [
        ("右键", "复制 / 发送到其他面板 / 在新分屏打开"),
    ]),
    ("自定义", [
        ("F1 → 自定义 Tab", "录制新键位、切换预设方案、导入导出"),
    ]),
]


class ShortcutsDialog(QDialog):
    """快捷键速查表 + 自定义。"""

    def __init__(self, i18n, parent=None, settings=None):
        super().__init__(parent)
        self.i18n = i18n
        # settings 可选：为 None 时，自定义 Tab 只读展示
        self.settings = settings
        if self.settings is None:
            # 尝试从主窗口拿
            try:
                self.settings = getattr(
                    parent, "settings", None)
            except Exception:
                self.settings = None

        self.setWindowTitle(i18n.t(
            "shortcuts_title", "快捷键速查表"))
        self.resize(680, 720)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_help_tab(), "速查")
        self.tabs.addTab(self._build_custom_tab(), "自定义")

        main = QVBoxLayout(self)
        main.setContentsMargins(12, 12, 12, 12)
        main.addWidget(self.tabs, 1)

        close_btn = QPushButton(i18n.t("close", "关闭"))
        close_btn.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close_btn)
        main.addLayout(row)

    # ==================================================================
    # 速查 Tab
    # ==================================================================

    def _build_help_tab(self):
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
        return scroll

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

    # ==================================================================
    # 自定义 Tab
    # ==================================================================

    def _build_custom_tab(self):
        if self.settings is None:
            w = QWidget()
            v = QVBoxLayout(w)
            v.addWidget(QLabel(self.i18n.t(
                "shortcut_no_settings",
                "需要 Settings 实例才能编辑快捷键。")))
            v.addStretch(1)
            return w

        try:
            from ui.widgets.shortcut_editor import ShortcutEditor
            editor = ShortcutEditor(self.settings, self.i18n, self)
            editor.changed.connect(self._on_changed)
            return editor
        except Exception as e:
            log_exc(e, module="ShortcutsDialog._build_custom_tab")
            w = QWidget()
            v = QVBoxLayout(w)
            v.addWidget(QLabel(f"✗ {e}"))
            v.addStretch(1)
            return w

    def _on_changed(self):
        """快捷键变化后通知主窗口刷新。"""
        try:
            w = self.parent()
            fn = getattr(w, "reload_shortcuts", None)
            if callable(fn):
                fn()
        except Exception as e:
            log_exc(e, module="ShortcutsDialog._on_changed")


__all__ = ["ShortcutsDialog"]