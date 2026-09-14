"""主题编辑器：编辑调色板、保存为 config/themes/*.json。"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QPushButton, QColorDialog, QDialogButtonBox, QMessageBox,
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

        self._palette = dict(settings.palette(base_theme))
        self._color_btns = {}

        self.name = QLineEdit(base_theme or "my_theme")
        self.label = QLineEdit("My Theme")

        form = QFormLayout()
        form.addRow(QLabel(i18n.t("theme_name", "主题 ID")), self.name)
        form.addRow(QLabel(i18n.t("theme_label", "显示名")), self.label)

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
        """临时把当前调色板应用到当前主题，实时预览。"""
        try:
            theme = self.settings.get("theme", "dark")
            pal = dict(self.settings.get("palette", {}) or {})
            pal[theme] = dict(self._palette)
            self.settings.set("palette", pal)
        except Exception as e:
            log_exc(e, module="ThemeEditor._apply")

    def _save(self):
        name = (self.name.text() or "").strip()
        label = (self.label.text() or "").strip() or name
        if not name:
            QMessageBox.warning(self, "Error", "name required")
            return
        path = self.settings.save_theme(name, label, dict(self._palette))
        if path:
            self.settings.set("theme", name)
            QMessageBox.information(self, "OK", path)
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "save failed")