"""设置面板。"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QFormLayout, QComboBox, QSpinBox, QCheckBox, QFontComboBox,
    QColorDialog, QFileDialog, QMessageBox,
)

from core import rates as rates_mod
from core.logger import log_exc
from .base import CalcPanel


class SettingsPanel(CalcPanel):
    module_key = "settings"

    def __init__(self, settings, i18n, main_window):
        super().__init__(settings, i18n, history=None)
        self.main_window = main_window

        self.lang = QComboBox()
        self.lang.addItems(["zh_CN", "en_US"])
        self.lang.setCurrentText(settings.get("language", "zh_CN"))

        self.theme = QComboBox()
        self.theme.addItem(i18n.t("theme_dark", "Dark"), "dark")
        self.theme.addItem(i18n.t("theme_light", "Light"), "light")
        self.theme.addItem(i18n.t("theme_system", "Follow system"), "system")
        self.theme.addItem(i18n.t("theme_hc", "High contrast"), "high_contrast")
        cur_theme = settings.get("theme", "dark")
        idx = self.theme.findData(cur_theme)
        self.theme.setCurrentIndex(idx if idx >= 0 else 0)

        self.font = QFontComboBox()
        self.font.setCurrentFont(QFont(settings.get("font_family", "Microsoft YaHei")))

        self.size = QSpinBox()
        self.size.setRange(8, 30)
        self.size.setValue(int(settings.get("font_size", 11)))

        self.fmt = QComboBox()
        self.fmt.addItems(["text", "unicode", "latex"])
        self.fmt.setCurrentText(settings.get("result_format", "text"))

        self.digits = QSpinBox()
        self.digits.setRange(0, 20)
        self.digits.setSpecialValueText(i18n.t("auto", "Auto"))
        self.digits.setValue(int(settings.get("result_digits", 0)))
        self.sci = QCheckBox(i18n.t("result_sci", "Scientific notation"))
        self.sci.setChecked(bool(settings.get("result_sci", False)))
        self.fraction = QCheckBox(i18n.t("result_fraction", "Show as fraction"))
        self.fraction.setChecked(bool(settings.get("result_fraction", False)))
        self.percent = QCheckBox(i18n.t("result_percent", "Show as percent"))
        self.percent.setChecked(bool(settings.get("result_percent", False)))

        self.source = QComboBox()
        for s in rates_mod.list_sources():
            self.source.addItem(s.label, s.name)
        default_src = settings.get("currency_source", "open.er-api.com")
        idx = self.source.findData(default_src)
        if idx >= 0:
            self.source.setCurrentIndex(idx)

        self.layout_edit = QPlainTextEdit(
            json.dumps(settings.get("button_layout", []), ensure_ascii=False))
        self.layout_edit.setFixedHeight(110)

        self.pal_btns = {}
        for key in ("bg", "fg", "panel", "accent", "border", "hover"):
            b = QPushButton(i18n.t(f"palette_{key}", key))
            b.clicked.connect(lambda _, k=key: self._pick_palette(k))
            self.pal_btns[key] = b
        pal_row = QHBoxLayout()
        for b in self.pal_btns.values():
            pal_row.addWidget(b)

        btn_apply = QPushButton(i18n.t("apply", "Apply")); btn_apply.clicked.connect(self.apply)
        btn_reset = QPushButton(i18n.t("reset", "Reset")); btn_reset.clicked.connect(self.reset)
        btn_export = QPushButton(i18n.t("export", "Export")); btn_export.clicked.connect(self._export)
        btn_import = QPushButton(i18n.t("import", "Import")); btn_import.clicked.connect(self._import)
        btn_vis = QPushButton(i18n.t("module_visibility", "Modules")); btn_vis.clicked.connect(self._edit_visibility)

        self.theme.currentIndexChanged.connect(
            lambda _: self.settings.set("theme", self.theme.currentData()))
        self.font.currentFontChanged.connect(
            lambda f: self.settings.set("font_family", f.family()))
        self.size.valueChanged.connect(lambda v: self.settings.set("font_size", v))
        self.digits.valueChanged.connect(lambda v: self.settings.set("result_digits", v))
        self.sci.stateChanged.connect(
            lambda _: self.settings.set("result_sci", self.sci.isChecked()))
        self.fraction.stateChanged.connect(
            lambda _: self.settings.set("result_fraction", self.fraction.isChecked()))
        self.percent.stateChanged.connect(
            lambda _: self.settings.set("result_percent", self.percent.isChecked()))

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.addRow(QLabel(i18n.t("language")), self.lang)
        form.addRow(QLabel(i18n.t("theme")), self.theme)
        form.addRow(QLabel(i18n.t("font")), self.font)
        form.addRow(QLabel(i18n.t("font_size")), self.size)
        form.addRow(QLabel(i18n.t("result_format")), self.fmt)
        form.addRow(QLabel(i18n.t("result_digits", "Digits")), self.digits)
        form.addRow(QLabel(""), self.sci)
        form.addRow(QLabel(""), self.fraction)
        form.addRow(QLabel(""), self.percent)
        form.addRow(QLabel(i18n.t("source")), self.source)
        form.addRow(QLabel(i18n.t("button_layout")), self.layout_edit)
        form.addRow(QLabel(i18n.t("palette_edit", "Palette")), pal_row)

        row = QHBoxLayout()
        for b in (btn_apply, btn_reset, btn_export, btn_import, btn_vis):
            row.addWidget(b)
        row.addStretch(1)

        main = QVBoxLayout(self)
        main.addLayout(form)
        main.addLayout(row)
        main.addStretch(1)

    def _pick_palette(self, key):
        try:
            current = self.settings.palette().get(key, "#ffffff")
            c = QColorDialog.getColor(QColor(current), self)
            if c.isValid():
                self.settings.set_palette_color(key, c.name())
        except Exception as e:
            log_exc(e, module="SettingsPanel._pick_palette")

    def apply(self):
        try:
            try:
                layout = json.loads(self.layout_edit.toPlainText())
                if not isinstance(layout, list):
                    raise ValueError("必须是 JSON 数组")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"button_layout: {e}")
                layout = self.settings.get("button_layout")

            lang_changed = (self.lang.currentText()
                            != self.settings.get("language"))

            self.settings.update({
                "language": self.lang.currentText(),
                "theme": self.theme.currentData(),
                "font_family": self.font.currentFont().family(),
                "font_size": self.size.value(),
                "result_format": self.fmt.currentText(),
                "result_digits": self.digits.value(),
                "result_sci": self.sci.isChecked(),
                "result_fraction": self.fraction.isChecked(),
                "result_percent": self.percent.isChecked(),
                "currency_source": self.source.currentData(),
                "button_layout": layout,
            })

            if not lang_changed:
                QMessageBox.information(self, "OK",
                                        self.i18n.t("hot_reload", "Applied"))
        except Exception as e:
            log_exc(e, module="SettingsPanel.apply")
            QMessageBox.warning(self, "Error", str(e))

    def reset(self):
        try:
            self.settings.reset()
        except Exception as e:
            log_exc(e, module="SettingsPanel.reset")

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export settings", "settings.json", "JSON (*.json)")
        if not path:
            return
        try:
            self.settings.export_to(path)
            QMessageBox.information(self, "OK", path)
        except Exception as e:
            log_exc(e, module="SettingsPanel._export")
            QMessageBox.warning(self, "Error", str(e))

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import settings", "", "JSON (*.json)")
        if not path:
            return
        try:
            self.settings.import_from(path)
            QMessageBox.information(self, "OK",
                                    self.i18n.t("hot_reload", "Applied"))
        except Exception as e:
            log_exc(e, module="SettingsPanel._import")
            QMessageBox.warning(self, "Error", str(e))

    def _edit_visibility(self):
        try:
            if self.main_window is not None:
                self.main_window.open_visibility_dialog()
        except Exception as e:
            log_exc(e, module="SettingsPanel._edit_visibility")