"""历史记录面板。"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QComboBox,
    QCheckBox, QListWidget, QListWidgetItem, QMenu, QFileDialog, QMessageBox,
    QInputDialog, QApplication, QAbstractItemView,
)

from core.logger import log_exc
from .base import CalcPanel


class HistoryPanel(CalcPanel):
    module_key = "history"
    PAGE_SIZE = 100

    # 复用信号：(module_key, expr)
    reuse_requested = Signal(str, str)

    def __init__(self, history, i18n):
        super().__init__(settings=None, i18n=i18n, history=history)
        self._page = 0
        self._total = 0
        self._rows = []
        self._reuse_handler = None

        self.search = QLineEdit()
        self.search.setPlaceholderText(i18n.t("search", "Search"))
        self.search.textChanged.connect(self._on_filter_changed)

        self.module_filter = QComboBox()
        self.tag_filter = QComboBox()
        self.fav_only = QCheckBox(i18n.t("favorites_only", "Favorites only"))
        self.fav_value_only = QCheckBox(i18n.t("fav_value_memo", "Saved values only"))
        self.fav_only.stateChanged.connect(lambda _: self._on_filter_changed())
        self.fav_value_only.stateChanged.connect(lambda _: self._on_filter_changed())
        self.module_filter.currentIndexChanged.connect(lambda _: self._on_filter_changed())
        self.tag_filter.currentIndexChanged.connect(lambda _: self._on_filter_changed())

        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        # 修复：双击 = 复用表达式
        self.list.itemDoubleClicked.connect(self._reuse_selected)
        # 右键菜单
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._show_context_menu)

        self.page_label = QLabel("0 / 0")
        self.prev_btn = QPushButton("◀"); self.next_btn = QPushButton("▶")
        self.prev_btn.clicked.connect(self._prev_page)
        self.next_btn.clicked.connect(self._next_page)

        b_refresh = QPushButton(i18n.t("refresh", "Refresh")); b_refresh.clicked.connect(self.refresh)
        b_del = QPushButton(i18n.t("delete", "Delete")); b_del.clicked.connect(self.remove_selected)
        b_clear_mod = QPushButton(i18n.t("clear_module", "Clear module")); b_clear_mod.clicked.connect(self.clear_module)
        b_clear = QPushButton(i18n.t("clear")); b_clear.clicked.connect(self.clear_all)
        b_json = QPushButton(i18n.t("export_json", "Export JSON")); b_json.clicked.connect(lambda: self._export("json"))
        b_csv = QPushButton(i18n.t("export_csv", "Export CSV")); b_csv.clicked.connect(lambda: self._export("csv"))
        b_save_val = QPushButton(i18n.t("fav_value_memo", "Save value")); b_save_val.clicked.connect(self.save_favorite_value)
        b_tags = QPushButton(i18n.t("edit_tags", "Edit tags")); b_tags.clicked.connect(self.edit_tags)

        filters = QHBoxLayout()
        filters.addWidget(self.search, 1)
        filters.addWidget(self.module_filter)
        filters.addWidget(self.tag_filter)

        checks = QHBoxLayout()
        checks.addWidget(self.fav_only); checks.addWidget(self.fav_value_only)
        checks.addStretch(1)

        pager = QHBoxLayout()
        pager.addWidget(self.prev_btn); pager.addWidget(self.page_label)
        pager.addWidget(self.next_btn); pager.addStretch(1)

        btns = QHBoxLayout()
        for b in (b_refresh, b_del, b_clear_mod, b_clear,
                  b_json, b_csv, b_save_val, b_tags):
            btns.addWidget(b)
        btns.addStretch(1)

        main = QVBoxLayout(self)
        main.addLayout(filters); main.addLayout(checks)
        main.addLayout(pager); main.addWidget(self.list, 1)
        main.addLayout(btns)

        self._reload_filters()
        self.refresh()

    # ------------------------------------------------------------------
    # 复用
    # ------------------------------------------------------------------

    def set_reuse_handler(self, fn):
        """由 MainWindow 调用；fn(module_key, expr)。若未设置则回退到复制。"""
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
                self, "OK", self.i18n.t("copied", "Copied to clipboard"))
        self.reuse_requested.emit(module, expr)

    # ------------------------------------------------------------------
    # 右键菜单
    # ------------------------------------------------------------------

    def _show_context_menu(self, pos):
        it = self._selected_item()
        if it is None:
            return
        menu = QMenu(self)
        a_reuse = menu.addAction(self.i18n.t("reuse_expr", "Reuse expression"))
        a_copy_expr = menu.addAction(self.i18n.t("copy_expr", "Copy expression"))
        a_copy_res = menu.addAction(self.i18n.t("copy_value", "Copy result"))
        menu.addSeparator()
        a_fav = menu.addAction(
            self.i18n.t("unfavorite", "Unfavorite")
            if it.get("favorite")
            else self.i18n.t("favorite", "Favorite"))
        a_tags = menu.addAction(self.i18n.t("edit_tags", "Edit tags"))
        menu.addSeparator()
        a_del = menu.addAction(self.i18n.t("delete", "Delete"))

        chosen = menu.exec(self.list.viewport().mapToGlobal(pos))
        if chosen is a_reuse:
            self._reuse_selected()
        elif chosen is a_copy_expr:
            QApplication.clipboard().setText(it.get("expr", ""))
        elif chosen is a_copy_res:
            QApplication.clipboard().setText(it.get("result", ""))
        elif chosen is a_fav:
            self.history.toggle_favorite(it["id"])
            self.refresh()
        elif chosen is a_tags:
            self.edit_tags()
        elif chosen is a_del:
            self.remove_selected()

    # ------------------------------------------------------------------
    # 过滤下拉
    # ------------------------------------------------------------------

    def _reload_filters(self):
        cur_mod = self.module_filter.currentData()
        self.module_filter.blockSignals(True)
        self.module_filter.clear()
        self.module_filter.addItem(self.i18n.t("all", "All"), None)
        for m in self.history.modules():
            self.module_filter.addItem(m, m)
        idx = self.module_filter.findData(cur_mod)
        if idx >= 0:
            self.module_filter.setCurrentIndex(idx)
        self.module_filter.blockSignals(False)

        cur_tag = self.tag_filter.currentData()
        self.tag_filter.blockSignals(True)
        self.tag_filter.clear()
        self.tag_filter.addItem(self.i18n.t("all", "All"), None)
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

    def refresh(self):
        try:
            kwargs = dict(
                module=self.module_filter.currentData(),
                search=self.search.text().strip() or None,
                favorites_only=self.fav_only.isChecked(),
                tag=self.tag_filter.currentData(),
                has_favorite_value=self.fav_value_only.isChecked(),
            )
            self._total = self.history.count(**kwargs)
            rows = self.history.list(
                **kwargs, offset=self._page * self.PAGE_SIZE, limit=self.PAGE_SIZE)
            self._rows = rows
            self.list.clear()
            for r in rows:
                star = "★" if r["favorite"] else "☆"
                fv = r.get("favorite_value")
                suffix = f"  [FV: {fv}]" if fv is not None else ""
                tags = r.get("tags") or []
                tag_str = ("  #" + " #".join(tags)) if tags else ""
                self.list.addItem(
                    f"{star} {r['time']} [{r['module']}] "
                    f"{r['expr']} = {r['result']}{suffix}{tag_str}")
            max_page = max(0, (self._total - 1) // self.PAGE_SIZE)
            self.page_label.setText(
                f"{self._page + 1} / {max_page + 1}  ({self._total})")
            self.prev_btn.setEnabled(self._page > 0)
            self.next_btn.setEnabled(self._page < max_page)
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
        self.history.set_favorite_value(it["id"], it.get("result", ""))
        self.refresh()

    def edit_tags(self):
        it = self._selected_item()
        if it is None:
            return
        current = ", ".join(it.get("tags") or [])
        text, ok = QInputDialog.getText(
            self, self.i18n.t("edit_tags", "Edit tags"),
            self.i18n.t("tags_hint", "Comma-separated tags:"), text=current)
        if not ok:
            return
        tags = [t.strip() for t in text.split(",") if t.strip()]
        self.history.set_tags(it["id"], tags)
        self._reload_filters()
        self.refresh()

    def remove_selected(self):
        rows = sorted({i.row() for i in self.list.selectedIndexes()}, reverse=True)
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

    def _export(self, kind):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export", f"history.{kind}", "JSON (*.json);;CSV (*.csv)")
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