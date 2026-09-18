"""设置面板：语言 / 主题（含主题编辑器）/ 字体 / 结果格式 /
汇率源 / 按钮布局 / 配色 / 导入导出 / 设置搜索。

变更历史：
- 第 3 轮：新增设置项搜索框（_filter_settings）
- 第 16 轮：语言下拉加 ja_JP / zh_TW
"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QFormLayout, QComboBox, QSpinBox, QCheckBox, QFontComboBox,
    QColorDialog, QFileDialog, QMessageBox, QWidget, QLineEdit,
)

from core import rates as rates_mod
from core.logger import log_exc
from .base import CalcPanel


class SettingsPanel(CalcPanel):
    module_key = "settings"

    # 支持的语言代码（第 16 轮）
    LANGUAGES = [
        ("zh_CN", "简体中文"),
        ("zh_TW", "繁體中文"),
        ("en_US", "English"),
        ("ja_JP", "日本語"),
    ]

    def __init__(self, settings, i18n, main_window):
        super().__init__(settings, i18n, history=None)
        self.main_window = main_window

        # ---------------- 设置搜索框 ----------------
        self.search = QLineEdit()
        self.search.setPlaceholderText(
            self.i18n.t("search", "搜索设置项…"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter_settings)

        # ---------------- 语言 ----------------
        self.lang = QComboBox()
        for code, label in self.LANGUAGES:
            self.lang.addItem(label, code)
        cur_lang = self.settings.get("language", "zh_CN")
        idx = self.lang.findData(cur_lang)
        if idx < 0:
            idx = 0
        self.lang.setCurrentIndex(idx)

        # ---------------- 主题 ----------------
        self.theme = QComboBox()
        self.theme_edit_btn = QPushButton(
            self.i18n.t("edit_theme", "编辑主题…"))
        self.theme_edit_btn.clicked.connect(
            self._open_theme_editor)
        self._refresh_theme_combo()
        self.theme.currentIndexChanged.connect(
            lambda _: self.settings.set(
                "theme", self.theme.currentData()))

        # ---------------- 字体 ----------------
        self.font = QFontComboBox()
        self.font.setCurrentFont(
            QFont(self.settings.get(
                "font_family", "Microsoft YaHei")))

        self.size = QSpinBox()
        self.size.setRange(8, 30)
        self.size.setValue(int(self.settings.get("font_size", 11)))

        # ---------------- 结果格式 ----------------
        self.fmt = QComboBox()
        self.fmt.addItems(["text", "unicode", "latex"])
        self.fmt.setCurrentText(
            self.settings.get("result_format", "text"))

        self.digits = QSpinBox()
        self.digits.setRange(0, 20)
        self.digits.setSpecialValueText(
            self.i18n.t("auto", "Auto"))
        self.digits.setValue(
            int(self.settings.get("result_digits", 0)))

        self.sci = QCheckBox(
            self.i18n.t("result_sci", "Scientific notation"))
        self.sci.setChecked(
            bool(self.settings.get("result_sci", False)))

        self.fraction = QCheckBox(
            self.i18n.t("result_fraction",
                        "Show as fraction"))
        self.fraction.setChecked(
            bool(self.settings.get("result_fraction", False)))

        self.percent = QCheckBox(
            self.i18n.t("result_percent",
                        "Show as percent"))
        self.percent.setChecked(
            bool(self.settings.get("result_percent", False)))

        # ---------------- 汇率源 ----------------
        self.source = QComboBox()
        try:
            for s in rates_mod.list_sources():
                self.source.addItem(s.label, s.name)
        except Exception as e:
            log_exc(e, module="SettingsPanel.init.rates")
        default_src = self.settings.get(
            "currency_source", "open.er-api.com")
        idx = self.source.findData(default_src)
        if idx >= 0:
            self.source.setCurrentIndex(idx)

        # ---------------- 按钮布局 ----------------
        self.layout_edit = QPlainTextEdit(
            json.dumps(
                self.settings.get("button_layout", []),
                ensure_ascii=False))
        self.layout_edit.setFixedHeight(110)

        # ---------------- 配色 ----------------
        self.pal_btns = {}
        for key in ("bg", "fg", "panel", "accent",
                    "border", "hover"):
            b = QPushButton(
                self.i18n.t(f"palette_{key}", key))
            b.clicked.connect(
                lambda _, k=key: self._pick_palette(k))
            self.pal_btns[key] = b
        pal_row = QHBoxLayout()
        for b in self.pal_btns.values():
            pal_row.addWidget(b)

        # ---------------- 按钮行 ----------------
        btn_apply = QPushButton(
            self.i18n.t("apply", "Apply"))
        btn_apply.clicked.connect(self.apply)
        btn_reset = QPushButton(
            self.i18n.t("reset", "Reset"))
        btn_reset.clicked.connect(self.reset)
        btn_export = QPushButton(
            self.i18n.t("export", "Export"))
        btn_export.clicked.connect(self._export)
        btn_import = QPushButton(
            self.i18n.t("import", "Import"))
        btn_import.clicked.connect(self._import)
        btn_vis = QPushButton(
            self.i18n.t("module_visibility", "Modules"))
        btn_vis.clicked.connect(self._edit_visibility)

        # ---------------- 实时监听 ----------------
        self.font.currentFontChanged.connect(
            lambda f: self.settings.set(
                "font_family", f.family()))
        self.size.valueChanged.connect(
            lambda v: self.settings.set("font_size", v))
        self.digits.valueChanged.connect(
            lambda v: self.settings.set("result_digits", v))
        self.sci.stateChanged.connect(
            lambda _: self.settings.set(
                "result_sci", self.sci.isChecked()))
        self.fraction.stateChanged.connect(
            lambda _: self.settings.set(
                "result_fraction", self.fraction.isChecked()))
        self.percent.stateChanged.connect(
            lambda _: self.settings.set(
                "result_percent", self.percent.isChecked()))

        # ---------------- 布局 ----------------
        self.form = QFormLayout()
        self.form.setLabelAlignment(Qt.AlignRight)
        self.form.addRow(QLabel(
            self.i18n.t("language")), self.lang)

        theme_row = QHBoxLayout()
        theme_row.addWidget(self.theme, 1)
        theme_row.addWidget(self.theme_edit_btn)
        self.form.addRow(QLabel(
            self.i18n.t("theme")), theme_row)

        self.form.addRow(QLabel(
            self.i18n.t("font")), self.font)
        self.form.addRow(QLabel(
            self.i18n.t("font_size")), self.size)
        self.form.addRow(QLabel(
            self.i18n.t("result_format")), self.fmt)
        self.form.addRow(
            QLabel(self.i18n.t("result_digits", "Digits")),
            self.digits)
        self.form.addRow(QLabel(""), self.sci)
        self.form.addRow(QLabel(""), self.fraction)
        self.form.addRow(QLabel(""), self.percent)
        self.form.addRow(QLabel(
            self.i18n.t("source")), self.source)
        self.form.addRow(
            QLabel(self.i18n.t("button_layout")),
            self.layout_edit)
        self.form.addRow(
            QLabel(self.i18n.t("palette_edit", "Palette")),
            pal_row)

        row = QHBoxLayout()
        for b in (btn_apply, btn_reset, btn_export,
                  btn_import, btn_vis):
            row.addWidget(b)
        row.addStretch(1)

        main = QVBoxLayout(self)
        main.addWidget(self.search)
        main.addLayout(self.form)
        main.addLayout(row)
        main.addStretch(1)

    # ==================================================================
    # 设置搜索
    # ==================================================================

    def _filter_settings(self, text):
        """按关键词过滤 QFormLayout 中的行。"""
        q = (text or "").strip().lower()
        for r in range(self.form.rowCount()):
            label_item = self.form.itemAt(
                r, QFormLayout.LabelRole)
            field_item = self.form.itemAt(
                r, QFormLayout.FieldRole)

            label_text = ""
            if label_item is not None:
                lw = label_item.widget()
                if lw is not None and hasattr(lw, "text"):
                    try:
                        label_text = lw.text()
                    except Exception:
                        label_text = ""

            field_text = ""
            if field_item is not None:
                fw = field_item.widget()
                if fw is not None and hasattr(fw, "text"):
                    try:
                        field_text = fw.text()
                    except Exception:
                        field_text = ""

            match = (not q) or (q in label_text.lower()) \
                or (q in field_text.lower())

            try:
                self.form.setRowVisible(r, match)
            except Exception:
                if label_item is not None:
                    lw = label_item.widget()
                    if lw is not None:
                        lw.setVisible(match)
                if field_item is not None:
                    fw = field_item.widget()
                    if fw is not None:
                        fw.setVisible(match)

    # ==================================================================
    # 主题
    # ==================================================================

    def _refresh_theme_combo(self):
        cur = self.settings.get("theme", "dark")
        self.theme.blockSignals(True)
        self.theme.clear()
        try:
            for name, info in self.settings.themes().items():
                self.theme.addItem(
                    info.get("label", name), name)
        except Exception as e:
            log_exc(e, module="SettingsPanel._refresh_theme_combo")
        self.theme.addItem(
            self.i18n.t("theme_system", "跟随系统"), "system")
        idx = self.theme.findData(cur)
        if idx >= 0:
            self.theme.setCurrentIndex(idx)
        self.theme.blockSignals(False)

    def _notify(self, msg, level="success", duration=2000):
        try:
            from ui.toast import toast
            toast(self.window(), msg, level=level,
                  duration=duration)
        except Exception:
            try:
                QMessageBox.information(self, "OK", str(msg))
            except Exception:
                pass

    def _open_theme_editor(self):
        try:
            from ui.theme_editor import ThemeEditor
            base = self.theme.currentData()
            if base == "system":
                base = self.settings.get("theme", "dark")
            dlg = ThemeEditor(
                self.settings, self.i18n, self,
                base_theme=base)
            if dlg.exec():
                self._refresh_theme_combo()
        except Exception as e:
            log_exc(e, module="SettingsPanel._open_theme_editor")

    def _pick_palette(self, key):
        try:
            current = self.settings.palette().get(
                key, "#ffffff")
            c = QColorDialog.getColor(QColor(current), self)
            if c.isValid():
                self.settings.set_palette_color(key, c.name())
        except Exception as e:
            log_exc(e, module="SettingsPanel._pick_palette")

    # ==================================================================
    # 应用 / 重置
    # ==================================================================

    def apply(self):
        try:
            try:
                layout = json.loads(
                    self.layout_edit.toPlainText())
                if not isinstance(layout, list):
                    raise ValueError("必须是 JSON 数组")
            except Exception as e:
                QMessageBox.warning(
                    self, "Error", f"button_layout: {e}")
                layout = self.settings.get("button_layout")

            lang_changed = (
                self.lang.currentData()
                != self.settings.get("language"))

            self.settings.update({
                "language": self.lang.currentData(),
                "theme": self.theme.currentData(),
                "font_family":
                    self.font.currentFont().family(),
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
                self._notify(self.i18n.t(
                    "hot_reload", "Applied"))
        except Exception as e:
            log_exc(e, module="SettingsPanel.apply")
            QMessageBox.warning(self, "Error", str(e))

    def reset(self):
        try:
            self.settings.reset()
            self._refresh_theme_combo()
        except Exception as e:
            log_exc(e, module="SettingsPanel.reset")

    # ==================================================================
    # 导入 / 导出
    # ==================================================================

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export settings", "settings.json",
            "JSON (*.json)")
        if not path:
            return
        try:
            self.settings.export_to(path)
            self._notify(path)
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
            self._refresh_theme_combo()
            self._notify(self.i18n.t(
                "hot_reload", "Applied"))
        except Exception as e:
            log_exc(e, module="SettingsPanel._import")
            QMessageBox.warning(self, "Error", str(e))

    # ==================================================================
    # 模块可见性
    # ==================================================================

    def _edit_visibility(self):
        try:
            if self.main_window is not None:
                self.main_window.open_visibility_dialog()
        except Exception as e:
            log_exc(e, module="SettingsPanel._edit_visibility")


__all__ = ["SettingsPanel"]