"""历史记录 / 设置 / 快捷键设置面板。

合并自：ui/panels/history.py + ui/panels/settings.py
        + ui/panels/shortcut_settings_panel.py

对外接口（类名保持不变）：
    HistoryPanel
    SettingsPanel
    ShortcutSettingsPanel

依赖（合并后）：
    core.base        —— log_exc
    core.state       —— Settings（类型注解用）
    core.rates       —— list_sources
    core.user_data   —— 无（history 由 core.state 提供）
    ui.dialogs       —— ThemeEditor
    ui.widgets.input —— EmptyState（延迟）
    ui.widgets.shortcut_editor —— ShortcutEditor（延迟）
    ui.panels.base       —— CalcPanel
    ui.panels._common    —— friendly_error

修复记录（本轮）：
- HistoryPanel：构造签名保持 `(history, i18n)`，由 registry 通过
  `_make_history(ctx)` 工厂构造。
- SettingsPanel：`from core import rates as rates_mod`
  保持不变（该模块名未变）。
- ShortcutSettingsPanel：`from ui.widgets.shortcut_editor import
  ShortcutEditor` 保持延迟导入。
- `from core.logger import log_exc` → `from core.base import log_exc`。
"""
from __future__ import annotations

import datetime as _dt
import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QColorDialog,
    QComboBox, QFileDialog, QFontComboBox, QFormLayout,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMenu, QMessageBox, QPlainTextEdit,
    QPushButton, QSpinBox, QStackedWidget, QVBoxLayout, QWidget,
)

from core import rates as rates_mod
from core.base import log_exc
from ._common import friendly_error
from .base import CalcPanel


__all__ = [
    "HistoryPanel",
    "SettingsPanel",
    "ShortcutSettingsPanel",
]


# ===========================================================================
# 历史记录
# ===========================================================================

class HistoryPanel(CalcPanel):
    """历史记录面板。

    注意：构造签名为 ``(history, i18n)``，与其它面板不同。
    `registry._make_history(ctx)` 负责用正确的参数构造。
    """

    module_key = "history"
    PAGE_SIZE = 100

    reuse_requested = Signal(str, str)

    def __init__(self, history, i18n):
        super().__init__(settings=None, i18n=i18n,
                         history=history)
        self._page = 0
        self._total = 0
        self._rows = []
        self._reuse_handler = None

        # ---------------- 搜索 / 过滤 ----------------
        self.search = QLineEdit()
        self.search.setPlaceholderText(i18n.t("search", "Search"))
        self.search.textChanged.connect(self._on_filter_changed)

        self.module_filter = QComboBox()
        self.tag_filter = QComboBox()
        self.fav_only = QCheckBox(
            i18n.t("favorites_only", "Favorites only"))
        self.fav_value_only = QCheckBox(
            i18n.t("fav_value_memo", "Saved values only"))
        self.fav_only.stateChanged.connect(
            lambda _: self._on_filter_changed())
        self.fav_value_only.stateChanged.connect(
            lambda _: self._on_filter_changed())
        self.module_filter.currentIndexChanged.connect(
            lambda _: self._on_filter_changed())
        self.tag_filter.currentIndexChanged.connect(
            lambda _: self._on_filter_changed())

        # ---------------- 列表 ----------------
        self.list = QListWidget()
        self.list.setSelectionMode(
            QAbstractItemView.ExtendedSelection)
        self.list.itemDoubleClicked.connect(
            self._reuse_selected)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(
            self._show_context_menu)

        # ---------------- 空状态 ----------------
        try:
            from ui.widgets.input import EmptyState
            self.empty_state = EmptyState(
                icon="📋",
                title=i18n.t("history_empty_title",
                             "还没有历史记录"),
                subtitle=i18n.t(
                    "history_empty_sub",
                    "计算后会自动记录在这里"),
                action_text=i18n.t(
                    "history_empty_action",
                    "去计算 →"),
            )
            self.empty_state.action_clicked.connect(
                self._go_basic)
        except Exception as e:
            log_exc(e, module="HistoryPanel.empty_state")
            self.empty_state = None

        self._stack = QStackedWidget()
        self._stack.addWidget(self.list)
        if self.empty_state is not None:
            self._stack.addWidget(self.empty_state)
        self._stack.setCurrentWidget(self.list)

        # ---------------- 分页 ----------------
        self.page_label = QLabel("0 / 0")
        self.prev_btn = QPushButton("◀")
        self.next_btn = QPushButton("▶")
        self.prev_btn.clicked.connect(self._prev_page)
        self.next_btn.clicked.connect(self._next_page)

        # ---------------- 按钮 ----------------
        b_refresh = QPushButton(
            i18n.t("refresh", "Refresh"))
        b_refresh.clicked.connect(self.refresh)
        b_del = QPushButton(i18n.t("delete", "Delete"))
        b_del.clicked.connect(self.remove_selected)
        b_clear_mod = QPushButton(
            i18n.t("clear_module", "Clear module"))
        b_clear_mod.clicked.connect(self.clear_module)
        b_clear = QPushButton(i18n.t("clear"))
        b_clear.clicked.connect(self.clear_all)
        b_json = QPushButton(
            i18n.t("export_json", "Export JSON"))
        b_json.clicked.connect(lambda: self._export("json"))
        b_csv = QPushButton(
            i18n.t("export_csv", "Export CSV"))
        b_csv.clicked.connect(lambda: self._export("csv"))
        b_save_val = QPushButton(
            i18n.t("fav_value_memo", "Save value"))
        b_save_val.clicked.connect(self.save_favorite_value)
        b_tags = QPushButton(
            i18n.t("edit_tags", "Edit tags"))
        b_tags.clicked.connect(self.edit_tags)
        b_session = QPushButton(
            i18n.t("export_session", "导出 .mcsession"))
        b_session.clicked.connect(self._export_session)
        b_notebook = QPushButton(
            i18n.t("export_notebook", "导出 Notebook"))
        b_notebook.clicked.connect(self._export_notebook)

        # ---------------- 布局 ----------------
        filters = QHBoxLayout()
        filters.addWidget(self.search, 1)
        filters.addWidget(self.module_filter)
        filters.addWidget(self.tag_filter)

        checks = QHBoxLayout()
        checks.addWidget(self.fav_only)
        checks.addWidget(self.fav_value_only)
        checks.addStretch(1)

        pager = QHBoxLayout()
        pager.addWidget(self.prev_btn)
        pager.addWidget(self.page_label)
        pager.addWidget(self.next_btn)
        pager.addStretch(1)

        btns = QHBoxLayout()
        for b in (b_refresh, b_del, b_clear_mod, b_clear,
                  b_json, b_csv, b_save_val, b_tags,
                  b_session, b_notebook):
            btns.addWidget(b)
        btns.addStretch(1)

        main = QVBoxLayout(self)
        main.addLayout(filters)
        main.addLayout(checks)
        main.addLayout(pager)
        main.addWidget(self._stack, 1)
        main.addLayout(btns)

        self._reload_filters()
        self.refresh()

    # ==================================================================
    # 空状态跳转
    # ==================================================================

    def _go_basic(self):
        try:
            mw = self.window()
            fn = getattr(mw, "_switch_by_key_pub", None)
            if callable(fn):
                fn("basic")
        except Exception:
            pass

    # ==================================================================
    # 复用
    # ==================================================================

    def set_reuse_handler(self, fn):
        self._reuse_handler = fn

    def _reuse_selected(self, _item=None):
        it = self._selected_item()
        if it is None:
            return
        module = it.get("module", "")
        expr = it.get("expr", "")
        if self._reuse_handler is not None:
            try:
                self._reuse_handler(module, expr)
            except Exception as e:
                log_exc(e, module="HistoryPanel.reuse")
        else:
            QApplication.clipboard().setText(expr)
            QMessageBox.information(
                self, "OK",
                self.i18n.t("copied",
                            "Copied to clipboard"))
        self.reuse_requested.emit(module, expr)

    # ==================================================================
    # 右键菜单
    # ==================================================================

    def _show_context_menu(self, pos):
        it = self._selected_item()
        if it is None:
            return
        menu = QMenu(self)
        a_reuse = menu.addAction(
            self.i18n.t("reuse_expr", "Reuse expression"))
        a_copy_expr = menu.addAction(
            self.i18n.t("copy_expr", "Copy expression"))
        a_copy_res = menu.addAction(
            self.i18n.t("copy_value", "Copy result"))
        menu.addSeparator()
        a_fav = menu.addAction(
            self.i18n.t("unfavorite", "Unfavorite")
            if it.get("favorite")
            else self.i18n.t("favorite", "Favorite"))
        a_tags = menu.addAction(
            self.i18n.t("edit_tags", "Edit tags"))
        menu.addSeparator()
        a_del = menu.addAction(
            self.i18n.t("delete", "Delete"))

        chosen = menu.exec(
            self.list.viewport().mapToGlobal(pos))
        if chosen is a_reuse:
            self._reuse_selected()
        elif chosen is a_copy_expr:
            QApplication.clipboard().setText(it.get("expr", ""))
        elif chosen is a_copy_res:
            QApplication.clipboard().setText(
                it.get("result", ""))
        elif chosen is a_fav:
            self.history.toggle_favorite(it["id"])
            self.refresh()
        elif chosen is a_tags:
            self.edit_tags()
        elif chosen is a_del:
            self.remove_selected()

    # ==================================================================
    # 过滤下拉
    # ==================================================================

    def _reload_filters(self):
        cur_mod = self.module_filter.currentData()
        self.module_filter.blockSignals(True)
        self.module_filter.clear()
        self.module_filter.addItem(
            self.i18n.t("all", "All"), None)
        for m in self.history.modules():
            self.module_filter.addItem(m, m)
        idx = self.module_filter.findData(cur_mod)
        if idx >= 0:
            self.module_filter.setCurrentIndex(idx)
        self.module_filter.blockSignals(False)

        cur_tag = self.tag_filter.currentData()
        self.tag_filter.blockSignals(True)
        self.tag_filter.clear()
        self.tag_filter.addItem(
            self.i18n.t("all", "All"), None)
        for t in self.history.tags():
            self.tag_filter.addItem(t, t)
        idx = self.tag_filter.findData(cur_tag)
        if idx >= 0:
            self.tag_filter.setCurrentIndex(idx)
        self.tag_filter.blockSignals(False)

    def _on_filter_changed(self):
        self._page = 0
        self.refresh()

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
            self.refresh()

    def _next_page(self):
        max_page = max(0, (self._total - 1) // self.PAGE_SIZE)
        if self._page < max_page:
            self._page += 1
            self.refresh()

    # ==================================================================
    # 选中保留
    # ==================================================================

    def _capture_selected_ids(self):
        try:
            rows = sorted(
                {i.row() for i in self.list.selectedIndexes()})
            ids = []
            for r in rows:
                if 0 <= r < len(self._rows):
                    rid = self._rows[r].get("id")
                    if rid is not None:
                        ids.append(rid)
            return ids
        except Exception:
            return []

    def _restore_selected_ids(self, ids):
        try:
            if not ids:
                return
            want = set(ids)
            for i, r in enumerate(self._rows):
                if r.get("id") in want:
                    it = self.list.item(i)
                    if it is not None:
                        it.setSelected(True)
        except Exception:
            pass

    # ==================================================================
    # 刷新
    # ==================================================================

    def refresh(self):
        try:
            keep_ids = self._capture_selected_ids()

            kwargs = dict(
                module=self.module_filter.currentData(),
                search=self.search.text().strip() or None,
                favorites_only=self.fav_only.isChecked(),
                tag=self.tag_filter.currentData(),
                has_favorite_value=self.fav_value_only.isChecked(),
            )
            self._total = self.history.count(**kwargs)
            rows = self.history.list(
                **kwargs,
                offset=self._page * self.PAGE_SIZE,
                limit=self.PAGE_SIZE)
            self._rows = rows
            self.list.clear()
            for r in rows:
                star = "★" if r["favorite"] else "☆"
                fv = r.get("favorite_value")
                suffix = (f"  [FV: {fv}]"
                          if fv is not None else "")
                tags = r.get("tags") or []
                tag_str = (("  #" + " #".join(tags))
                           if tags else "")
                self.list.addItem(
                    f"{star} {r['time']} [{r['module']}] "
                    f"{r['expr']} = {r['result']}"
                    f"{suffix}{tag_str}")

            self._restore_selected_ids(keep_ids)

            max_page = max(0,
                           (self._total - 1) // self.PAGE_SIZE)
            self.page_label.setText(
                f"{self._page + 1} / {max_page + 1}"
                f"  ({self._total})")
            self.prev_btn.setEnabled(self._page > 0)
            self.next_btn.setEnabled(self._page < max_page)

            if self._total == 0 and self.empty_state is not None:
                self._stack.setCurrentWidget(self.empty_state)
            else:
                self._stack.setCurrentWidget(self.list)
        except Exception as e:
            log_exc(e, module="HistoryPanel.refresh")

    def _selected_item(self):
        row = self.list.currentRow()
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def save_favorite_value(self):
        it = self._selected_item()
        if it is None:
            return
        self.history.set_favorite_value(
            it["id"], it.get("result", ""))
        self.refresh()

    def edit_tags(self):
        it = self._selected_item()
        if it is None:
            return
        current = ", ".join(it.get("tags") or [])
        text, ok = QInputDialog.getText(
            self,
            self.i18n.t("edit_tags", "Edit tags"),
            self.i18n.t("tags_hint",
                        "Comma-separated tags:"),
            text=current)
        if not ok:
            return
        tags = [t.strip()
                for t in text.split(",") if t.strip()]
        self.history.set_tags(it["id"], tags)
        self._reload_filters()
        self.refresh()

    def remove_selected(self):
        rows = sorted(
            {i.row() for i in self.list.selectedIndexes()},
            reverse=True)
        if not rows:
            it = self._selected_item()
            if it is not None:
                rows = [self.list.currentRow()]
        for r in rows:
            if 0 <= r < len(self._rows):
                self.history.remove(self._rows[r]["id"])
        self.refresh()

    def clear_module(self):
        mod = self.module_filter.currentData()
        if mod:
            self.history.clear_module(mod)
            self._reload_filters()
            self.refresh()

    def clear_all(self):
        self.history.clear()
        self._reload_filters()
        self.refresh()

    # ==================================================================
    # 导出
    # ==================================================================

    def _export(self, kind):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export", f"history.{kind}",
            "JSON (*.json);;CSV (*.csv)")
        if not path:
            return
        try:
            if kind == "json":
                self.history.export_json(path)
            else:
                self.history.export_csv(path)
            QMessageBox.information(self, "OK", path)
        except Exception as e:
            log_exc(e, module="HistoryPanel._export")
            QMessageBox.warning(self, "Error", str(e))

    def _collect_for_export(self):
        rows = sorted(
            {i.row() for i in self.list.selectedIndexes()})
        if rows:
            return [self._rows[r] for r in rows
                    if 0 <= r < len(self._rows)]
        return list(self._rows)

    def _export_session(self):
        items = self._collect_for_export()
        if not items:
            QMessageBox.information(
                self, "OK",
                self.i18n.t("nothing_to_export",
                            "无可导出条目"))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export session", "session.mcsession",
            "MultiCalc Session (*.mcsession);;JSON (*.json)")
        if not path:
            return
        try:
            payload = {
                "version": 1,
                "app": "MultiCalc",
                "created": _dt.datetime.now().isoformat(),
                "count": len(items),
                "entries": [
                    {
                        "module": it.get("module", ""),
                        "expr": it.get("expr", ""),
                        "result": it.get("result", ""),
                        "time": it.get("time", ""),
                        "tags": list(it.get("tags") or []),
                    }
                    for it in items
                ],
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False,
                          indent=2)
            try:
                from ui.shell import toast
                toast(self.window(), path, level="success")
            except Exception:
                QMessageBox.information(self, "OK", path)
        except Exception as e:
            log_exc(e, module="HistoryPanel._export_session")
            QMessageBox.warning(self, "Error", str(e))

    def _export_notebook(self):
        items = self._collect_for_export()
        if not items:
            QMessageBox.information(
                self, "OK",
                self.i18n.t("nothing_to_export",
                            "无可导出条目"))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Notebook", "multicalc.ipynb",
            "Jupyter Notebook (*.ipynb)")
        if not path:
            return
        try:
            from core import notebook as nb_mod
            norm = []
            for it in items:
                norm.append({
                    "module": it.get("module", ""),
                    "expr": it.get("expr", ""),
                    "result": it.get("result", ""),
                    "time": it.get("time", ""),
                    "latex": "",
                })
            nb_mod.export_to_ipynb(
                norm, path, title="MultiCalc Session")
            try:
                from ui.shell import toast
                toast(self.window(), path, level="success")
            except Exception:
                QMessageBox.information(self, "OK", path)
        except Exception as e:
            log_exc(e, module="HistoryPanel._export_notebook")
            QMessageBox.warning(self, "Error", str(e))


# ===========================================================================
# 设置
# ===========================================================================

class SettingsPanel(CalcPanel):
    """设置面板：语言 / 主题 / 字体 / 结果格式 / 汇率源 /
    按钮布局 / 配色 / 导入导出 / 设置搜索。"""

    module_key = "settings"

    LANGUAGES = [
        ("zh_CN", "简体中文"),
        ("zh_TW", "繁體中文"),
        ("en_US", "English"),
        ("ja_JP", "日本語"),
    ]

    def __init__(self, settings, i18n, main_window):
        super().__init__(settings, i18n, history=None)
        self.main_window = main_window

        # ---------------- 搜索框 ----------------
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

            match = ((not q)
                     or (q in label_text.lower())
                     or (q in field_text.lower()))

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
            from ui.shell import toast
            toast(self.window(), msg, level=level,
                  duration=duration)
        except Exception:
            try:
                QMessageBox.information(self, "OK", str(msg))
            except Exception:
                pass

    def _open_theme_editor(self):
        try:
            from ui.dialogs import ThemeEditor
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


# ===========================================================================
# 快捷键设置
# ===========================================================================

class ShortcutSettingsPanel(CalcPanel):
    """快捷键设置面板：快捷键自定义的独立面板。"""

    module_key = "shortcuts"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        self.hint = QLabel(self.i18n.t(
            "shortcut_hint",
            "双击命令即可录制新键位；右键可清除或恢复默认。"
            "冲突的键位会标红。修改立即生效。"))
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color: #888; padding: 4px;")

        try:
            from ui.widgets.dialogs import ShortcutEditor
            self.editor = ShortcutEditor(
                self.settings, self.i18n, self)
            self.editor.changed.connect(self._on_changed)
        except Exception as e:
            log_exc(e,
                    module="ShortcutSettingsPanel.editor_init")
            self.editor = QLabel(f"✗ {e}")

        main = QVBoxLayout(self)
        main.addWidget(self.hint)
        main.addWidget(self.editor, 1)

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
        if key in (None, "theme", "palette"):
            try:
                self.editor._refresh()
            except Exception:
                pass