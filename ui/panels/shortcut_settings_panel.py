"""快捷键设置面板：快捷键自定义的独立面板。

变更历史：
- 第 18 轮：新增
"""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout

from core.logger import log_exc
from ui.widgets.shortcut_editor import ShortcutEditor
from .base import CalcPanel


class ShortcutSettingsPanel(CalcPanel):
    module_key = "shortcuts"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        self.hint = QLabel(self.i18n.t(
            "shortcut_hint",
            "双击命令即可录制新键位；右键可清除或恢复默认。"
            "冲突的键位会标红。修改立即生效。"))
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color: #888; padding: 4px;")

        self.editor = ShortcutEditor(
            self.settings, self.i18n, self)
        self.editor.changed.connect(self._on_changed)

        main = QVBoxLayout(self)
        main.addWidget(self.hint)
        main.addWidget(self.editor, 1)

    # ==================================================================

    def _on_changed(self):
        """快捷键变化后通知主窗口刷新。"""
        try:
            mw = self.window()
            fn = getattr(mw, "reload_shortcuts", None)
            if callable(fn):
                fn()
        except Exception as e:
            log_exc(e, module="ShortcutSettingsPanel._on_changed")

    def on_settings_changed(self, key=None):
        # 主题变化时刷新树里的颜色
        if key in (None, "theme", "palette"):
            try:
                self.editor._refresh()
            except Exception:
                pass


__all__ = ["ShortcutSettingsPanel"]