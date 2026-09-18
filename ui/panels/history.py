"""历史记录面板。

变更历史：
- 第 1 轮：初版（复用 + 右键菜单）
- 第 19 轮：空历史时用 EmptyState
"""
from __future__ import annotations

import datetime as _dt
import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QCheckBox, QListWidget, QListWidgetItem, QMenu,
    QFileDialog, QMessageBox, QInputDialog, QApplication,
    QAbstractItemView, QStackedWidget, QWidget,
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

        # ---------------- 空状态（第 19 轮） ----------------
        try:
            from ui.widgets.empty_state import EmptyState
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

            # 空状态切换（第 19 轮）
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
                from ui.toast import toast
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
            from core import notebook_export as nb_mod
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
                from ui.toast import toast
                toast(self.window(), path, level="success")
            except Exception:
                QMessageBox.information(self, "OK", path)
        except Exception as e:
            log_exc(e, module="HistoryPanel._export_notebook")
            QMessageBox.warning(self, "Error", str(e))


__all__ = ["HistoryPanel"]