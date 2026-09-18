"""主题编辑器：编辑调色板、保存为 config/themes/*.json。

变更历史：
- 第 1 轮：初版
- 第 2 轮：_apply() 以 settings.palette(theme) 为基底，
          避免从主题文件切换时覆盖掉主题文件里的其他颜色
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QPushButton, QColorDialog, QMessageBox,
)
from PySide6.QtGui import QColor

from core.logger import log_exc


class ThemeEditor(QDialog):
    PAL_KEYS = ("bg", "fg", "panel", "accent", "border", "hover")

    def __init__(self, settings, i18n, parent=None, base_theme=None):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n
        self.setWindowTitle(i18n.t("theme_editor", "主题编辑器"))
        self.resize(460, 360)

        # 用 settings.palette() 取当前主题实际生效的颜色作为基底
        try:
            self._palette = dict(settings.palette(base_theme))
        except Exception:
            self._palette = {
                "bg": "#1e1e1e", "fg": "#ffffff",
                "panel": "#2d2d30", "accent": "#007acc",
                "border": "#3f3f46", "hover": "#3a3d41",
            }
        # 保证六个键齐全（来自主题文件时可能缺失某些键）
        for k in self.PAL_KEYS:
            self._palette.setdefault(k, "#000000")

        self._color_btns = {}

        self.name = QLineEdit(base_theme or "my_theme")
        self.label = QLineEdit("My Theme")

        form = QFormLayout()
        form.addRow(QLabel(i18n.t("theme_name", "主题 ID")),
                    self.name)
        form.addRow(QLabel(i18n.t("theme_label", "显示名")),
                    self.label)

        for k in self.PAL_KEYS:
            b = QPushButton()
            b.setFixedHeight(28)
            b.clicked.connect(lambda _, key=k: self._pick(key))
            self._color_btns[k] = b
            form.addRow(QLabel(i18n.t(f"palette_{k}", k)), b)

        self._refresh_btns()

        btn_save = QPushButton(i18n.t("save", "保存"))
        btn_apply = QPushButton(i18n.t("apply", "应用"))
        btn_close = QPushButton(i18n.t("cancel", "取消"))
        btn_save.clicked.connect(self._save)
        btn_apply.clicked.connect(self._apply)
        btn_close.clicked.connect(self.reject)

        row = QHBoxLayout()
        row.addWidget(btn_save)
        row.addWidget(btn_apply)
        row.addStretch(1)
        row.addWidget(btn_close)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addLayout(row)

    # ------------------------------------------------------------------

    def _pick(self, key):
        cur = QColor(self._palette.get(key, "#000000"))
        c = QColorDialog.getColor(cur, self)
        if c.isValid():
            self._palette[key] = c.name()
            self._refresh_btns()

    def _refresh_btns(self):
        for k, b in self._color_btns.items():
            color = self._palette.get(k, "#000000")
            b.setText(color)
            b.setStyleSheet(
                f"background:{color};border:1px solid #888;"
                f"border-radius:4px;padding:2px 8px;")

    def _apply(self):
        """临时把当前调色板应用到当前主题，实时预览。

        以 settings.palette(theme) 为基底，
        避免从主题文件切换时新建键盖住主题文件里的其他颜色。
        """
        try:
            theme = self.settings.get("theme", "dark")
            if theme == "system":
                theme = "dark"

            # 基底：优先当前实际生效的颜色
            try:
                base = dict(self.settings.palette(theme))
            except Exception:
                base = {}

            # 用主题文件中的 palette 兜底（若当前主题来自文件）
            try:
                themes = self.settings.data.get("_themes") or {}
                if theme in themes and not base:
                    base = dict(themes[theme].get("palette") or {})
            except Exception:
                pass

            # 合并用户编辑的颜色
            base.update(self._palette)

            pal = dict(self.settings.get("palette", {}) or {})
            pal[theme] = base
            self.settings.set("palette", pal)
        except Exception as e:
            log_exc(e, module="ThemeEditor._apply")

    def _save(self):
        name = (self.name.text() or "").strip()
        label = (self.label.text() or "").strip() or name
        if not name:
            QMessageBox.warning(self, "Error", "name required")
            return
        path = self.settings.save_theme(
            name, label, dict(self._palette))
        if path:
            self.settings.set("theme", name)
            QMessageBox.information(self, "OK", path)
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "save failed")


__all__ = ["ThemeEditor"]