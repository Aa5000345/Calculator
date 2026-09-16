# -*- coding: utf-8 -*-
"""主窗口：侧边栏分组 + 搜索 + 面板切换 + 热重载 + 状态持久化 + 键盘/AI/脚本集成。"""
from __future__ import annotations

import base64
import json
import os
import re

from PySide6.QtCore import Qt, QTimer, QFileSystemWatcher
from PySide6.QtGui import (
    QAction, QGuiApplication, QKeySequence, QShortcut,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QLineEdit, QTreeWidget, QTreeWidgetItem,
    QStackedWidget, QDockWidget, QAbstractItemView, QDialog, QMessageBox,
    QTableWidgetItem,
)

from core.logger import log_exc, log_info
from ui.latex_widget import LatexLabel
from ui.settings_dialog import ModuleVisibilityDialog
from ui.shortcuts import install_main_window_shortcuts
from ui.command_palette import CommandPalette, _fuzzy_score
from ui.tray import Tray
from ui.split_view import SplitView
from ui.signals import bus
from core import engine
from core import updater as update_mod
from core import plugins as plugin_mod
from core import snippets as snip_mod
from ui.panels.registry import all_panels


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

DEFAULT_GROUPS = [
    ("基础", ["basic", "scientific"]),
    ("转换", ["unit", "currency", "base"]),
    ("数据", ["stats", "probability", "random", "data_table"]),
    ("数学", ["matrix", "plot", "plot3d"]),
    ("财务", ["finance", "date"]),
    ("工具", ["bits", "crypto_tools", "latex", "tools"]),
    ("生产力", ["snippets", "timer", "clipboard_history", "script"]),
    ("AI", ["ai"]),
    ("系统", ["history", "settings"]),
]


_MODULE_KEY_MAP = {
    "basic": "basic", "scientific": "scientific", "unit": "unit",
    "currency": "currency",
    "base": "base", "ascii": "base", "endian": "base", "ieee": "base",
    "matrix": "matrix", "stats": "stats", "plot": "plot",
    "plot3d": "plot3d", "random": "random", "bits": "bits",
    "latex": "latex", "settings": "settings",
    "data_table": "data_table", "tools": "tools",
    "snippets": "snippets", "timer": "timer", "script": "script",
    "ai": "ai",
    "clipboard": "clipboard_history",
    "clipboard_history": "clipboard_history",
}

_MODULE_PREFIX_MAP = (
    ("date-", "date"), ("finance-", "finance"),
    ("stats-", "stats"), ("random-", "random"),
    ("prob-", "probability"), ("bits-", "bits"),
    ("unit-", "unit"), ("currency-", "currency"), ("matrix-", "matrix"),
    ("enc-", "crypto_tools"), ("dec-", "crypto_tools"),
    ("hash-", "crypto_tools"), ("aes-", "crypto_tools"),
    ("rsa-", "crypto_tools"), ("classic-", "crypto_tools"),
    ("crypto", "crypto_tools"), ("totp", "crypto_tools"),
    ("pw-strength", "crypto_tools"),
    ("table-", "data_table"),
    ("jwt", "tools"), ("qr", "tools"), ("regex", "tools"),
    ("ai:", "ai"), ("script:", "script"),
)


# 保存分组原始名称的 role，避免搜索时被 "(N)" 后缀污染
_GROUP_NAME_ROLE = Qt.UserRole + 1


# ---------------------------------------------------------------------------
# 上下文对象
# ---------------------------------------------------------------------------

class _Ctx:
    def __init__(self, base_path, settings, i18n, history,
                 main_window, reuse_handler):
        self.base_path = base_path
        self.settings = settings
        self.i18n = i18n
        self.history = history
        self.main_window = main_window
        self.reuse_handler = reuse_handler


# ---------------------------------------------------------------------------
# MainWindow
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self, base_path, settings, i18n, history):
        super().__init__()
        self.base_path = base_path
        self.settings = settings
        self.i18n = i18n
        self.history = history

        self._panels = {}
        self._keys = []
        self._titles = {}
        self._panel_group = {}
        self._item_by_key = {}
        self._split = None
        self._force_quit = False
        self._keyboard = None

        # 专注模式
        self._focus_mode = False
        self._focus_saved = {}
        self._focus_exit_btn = None
        self._focus_shortcut = None

        self._restore_geometry()
        self._build()
        self.settings.add_listener(self._on_settings_changed)

        self._watcher = QFileSystemWatcher(self)
        if getattr(settings, "user_path", None):
            try:
                self._watcher.addPath(settings.user_path)
            except Exception:
                pass
        self._watcher.fileChanged.connect(self._on_settings_file_changed)

        install_main_window_shortcuts(self)
        self._tray = Tray(self, self.i18n)
        if self.settings.get("tray_enabled", False):
            self._tray.install()
        self._build_menu()
        self._load_plugins()

        if self.settings.get("keyboard_visible", False):
            QTimer.singleShot(200, self._show_keyboard_initial)

        # URL 参数传入的初始表达式
        QTimer.singleShot(300, self._consume_init_expr)

    # ------------------------------------------------------------------
    # 几何
    # ------------------------------------------------------------------

    def _show_keyboard_initial(self):
        try:
            kb = self._ensure_keyboard()
            kb.show()
            kb.raise_()
        except Exception:
            pass

    def _restore_geometry(self):
        geom = self.settings.get("window_geometry")
        if isinstance(geom, (list, tuple)) and len(geom) == 4:
            try:
                self.setGeometry(int(geom[0]), int(geom[1]),
                                 int(geom[2]), int(geom[3]))
                return
            except Exception:
                pass
        self.resize(1280, 880)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 专注模式下浮动按钮保持在右上角
        if self._focus_mode and self._focus_exit_btn is not None:
            try:
                btn = self._focus_exit_btn
                btn.move(max(10, self.width() - btn.width() - 24), 12)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # 构建
    # ------------------------------------------------------------------

    def _build(self):
        self.setWindowTitle(self.i18n.t("app_title"))

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.dock = QDockWidget(self.i18n.t("modules", "Modules"), self)
        self.dock.setObjectName("modulesDock")
        self.dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.dock.setFeatures(
            QDockWidget.DockWidgetMovable |
            QDockWidget.DockWidgetFloatable |
            QDockWidget.DockWidgetClosable)

        side = QWidget()
        sl = QVBoxLayout(side)
        sl.setContentsMargins(6, 6, 6, 6)
        sl.setSpacing(6)

        self.toggle = QPushButton("≡")
        self.toggle.setFixedSize(34, 28)
        self.toggle.clicked.connect(self.toggle_sidebar)

        self.vis_btn = QPushButton(self.i18n.t("module_visibility", "Visibility"))
        self.vis_btn.setFixedHeight(26)
        self.vis_btn.clicked.connect(self.open_visibility_dialog)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(
            self.i18n.t("search_modules", "搜索模块…"))
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self._apply_filter)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setDragDropMode(QAbstractItemView.InternalMove)
        self.tree.setDefaultDropAction(Qt.MoveAction)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setMinimumWidth(180)
        self.tree.setIndentation(14)
        self.tree.setRootIsDecorated(True)
        self.tree.setExpandsOnDoubleClick(False)
        self.tree.itemClicked.connect(self._on_tree_item_clicked)
        self.tree.model().rowsMoved.connect(self._on_tree_rows_moved)

        head = QHBoxLayout()
        head.addWidget(self.toggle)
        head.addWidget(QLabel(self.i18n.t("modules", "Modules")))
        head.addStretch(1)

        sl.addLayout(head)
        sl.addWidget(self.search_box)
        sl.addWidget(self.tree, 1)
        sl.addWidget(self.vis_btn)
        self.dock.setWidget(side)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock)

        ctx = _Ctx(
            base_path=self.base_path,
            settings=self.settings,
            i18n=self.i18n,
            history=self.history,
            main_window=self,
            reuse_handler=self._on_reuse_from_history,
        )
        for spec in all_panels():
            try:
                widget = spec.factory(ctx)
                title = self.i18n.t(spec.title_key, spec.title_default)
                self._register(spec.key, title, widget, spec.group)
            except Exception as e:
                log_exc(e, module=f"main_window.register:{spec.key}")

        self._rebuild_tree()
        self._apply_filter("")

        last = self.settings.get("last_module", "basic")
        if last in self._panels:
            self.switch_to_key(last)
        elif self._keys:
            self.switch_to_key(self._keys[0])

        self._restore_layout()
        self._wire_signals()
        self.apply_theme()

    def _wire_signals(self):
        """连接跨面板信号总线。"""
        try:
            b = bus()
            b.send_to_basic.connect(self._on_send_to_basic)
            b.send_to_sci.connect(self._on_send_to_sci)
            b.send_to_table.connect(self._on_send_to_table)
            b.send_to_snippet.connect(self._on_send_to_snippet)
            b.send_to_plot.connect(self._on_send_to_plot)
            b.send_to_unit.connect(self._on_send_to_unit_view)
            b.send_to_script.connect(self._on_send_to_script)
            b.clipboard_expr.connect(self._on_clipboard_expr)
        except Exception as e:
            log_exc(e, module="MainWindow._wire_signals")

    def _register(self, key, title, widget, group="工具"):
        self._panels[key] = widget
        self._titles[key] = title
        self._keys.append(key)
        self._panel_group[key] = group
        self.stack.addWidget(widget)

    # ------------------------------------------------------------------
    # 树
    # ------------------------------------------------------------------

    def _default_groups(self):
        return [(name, list(keys)) for name, keys in DEFAULT_GROUPS]

    def _load_groups(self):
        raw = self.settings.get("module_groups")
        groups = []
        seen = set()
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                keys = [k for k in (item.get("keys") or [])
                        if k in self._panels and k not in seen]
                if name and keys:
                    groups.append((name, keys))
                    seen.update(keys)
        if not groups:
            groups = self._default_groups()
            for _, keys in groups:
                seen.update(keys)
        unassigned = [k for k in self._keys if k not in seen]
        if unassigned:
            groups.append(("其他", unassigned))
        return groups

    def _rebuild_tree(self):
        expanded = {}
        for i in range(self.tree.topLevelItemCount()):
            p = self.tree.topLevelItem(i)
            base = p.data(0, _GROUP_NAME_ROLE) or p.text(0)
            base = re.sub(r"\s*\(\d+\)\s*$", "", base)
            expanded[base] = p.isExpanded()

        groups = self._load_groups()
        self._panel_group = {k: n for n, keys in groups for k in keys}

        self.tree.clear()
        self._item_by_key.clear()

        for name, keys in groups:
            parent = QTreeWidgetItem([name])
            parent.setData(0, _GROUP_NAME_ROLE, name)  # 保存原始名
            parent.setFlags(
                (parent.flags() | Qt.ItemIsDropEnabled) & ~Qt.ItemIsSelectable)
            font = parent.font(0)
            font.setBold(True)
            parent.setFont(0, font)
            self.tree.addTopLevelItem(parent)
            for k in keys:
                child = QTreeWidgetItem([self._titles.get(k, k)])
                child.setData(0, Qt.UserRole, k)
                child.setFlags(child.flags() | Qt.ItemIsDragEnabled)
                parent.addChild(child)
                self._item_by_key[k] = child
            parent.setExpanded(expanded.get(name, True))

    def _apply_filter(self, text):
        """过滤模块树。

        - 搜索为空：按 visible_modules 隐藏
        - 搜索非空：文本匹配 且 visible_modules 为真 才显示
        - 分组头显示 "(N)" 计数（搜索时）
        """
        text = (text or "").strip().lower()

        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            parent_name = parent.data(0, _GROUP_NAME_ROLE) or parent.text(0)
            parent_name = re.sub(r"\s*\(\d+\)\s*$", "", parent_name)

            any_visible = False
            visible_count = 0

            for j in range(parent.childCount()):
                child = parent.child(j)
                key = child.data(0, Qt.UserRole)
                title = child.text(0)
                is_visible = bool(self.settings.is_module_visible(key))

                if not text:
                    hidden = not is_visible
                    child.setHidden(hidden)
                    if not hidden:
                        any_visible = True
                        visible_count += 1
                    continue

                # 搜索模式：不可见模块始终隐藏
                if not is_visible:
                    child.setHidden(True)
                    continue

                s1 = _fuzzy_score(text, title)
                s2 = _fuzzy_score(text, str(key or ""))
                s3 = _fuzzy_score(text, parent_name)
                if max(s1, s2, s3) > 0:
                    child.setHidden(False)
                    any_visible = True
                    visible_count += 1
                else:
                    child.setHidden(True)

            parent.setHidden(not any_visible)

            if text and any_visible:
                parent.setText(0, f"{parent_name} ({visible_count})")
            else:
                parent.setText(0, parent_name)

            if text and any_visible:
                parent.setExpanded(True)

    def _on_tree_item_clicked(self, item, _col=0):
        key = item.data(0, Qt.UserRole)
        if key:
            self.switch_to_key(key)
        else:
            item.setExpanded(not item.isExpanded())

    def _on_tree_rows_moved(self, *_):
        try:
            groups = []
            for i in range(self.tree.topLevelItemCount()):
                parent = self.tree.topLevelItem(i)
                keys = []
                for j in range(parent.childCount()):
                    k = parent.child(j).data(0, Qt.UserRole)
                    if k:
                        keys.append(k)
                if keys:
                    name = parent.data(0, _GROUP_NAME_ROLE) or parent.text(0)
                    name = re.sub(r"\s*\(\d+\)\s*$", "", name)
                    groups.append({"name": name, "keys": keys})
            self.settings.set("module_groups", groups, notify=False)
        except Exception as e:
            log_exc(e, module="main_window._on_tree_rows_moved")

    # ------------------------------------------------------------------
    # 切换
    # ------------------------------------------------------------------

    def switch_to_key(self, key):
        widget = self._panels.get(key)
        if widget is None:
            return
        self.stack.setCurrentWidget(widget)
        try:
            self.settings.set("last_module", key, notify=False)
        except Exception:
            pass

        if self._keyboard is not None:
            try:
                self._keyboard.set_module(key)
            except Exception:
                pass

        item = self._item_by_key.get(key)
        if (item is not None and not item.isHidden()
                and self.tree.currentItem() is not item):
            self.tree.setCurrentItem(item)
            self.tree.scrollToItem(item)

    def switch(self, idx):
        if 0 <= idx < self.stack.count():
            w = self.stack.widget(idx)
            for k, v in self._panels.items():
                if v is w:
                    self.switch_to_key(k)
                    break

    def _visible_keys_in_order(self):
        out = []
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            if parent.isHidden():
                continue
            for j in range(parent.childCount()):
                child = parent.child(j)
                if child.isHidden():
                    continue
                k = child.data(0, Qt.UserRole)
                if k:
                    out.append(k)
        return out

    def _tree_keys(self):
        out = []
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            for j in range(parent.childCount()):
                k = parent.child(j).data(0, Qt.UserRole)
                if k:
                    out.append(k)
        return out

    def _switch_by_key_pub(self, key):
        if key not in self._panels:
            return
        try:
            if not self.settings.is_module_visible(key):
                self.settings.set_module_visible(key, True)
                self._apply_filter(self.search_box.text())
        except Exception:
            pass
        self.switch_to_key(key)

    def _go_settings(self):
        self._switch_by_key_pub("settings")

    def toggle_sidebar(self):
        self.tree.setVisible(not self.tree.isVisible())
        self.search_box.setVisible(self.tree.isVisible())
        self.vis_btn.setVisible(self.tree.isVisible())

    # ------------------------------------------------------------------
    # 浮动键盘
    # ------------------------------------------------------------------

    def _ensure_keyboard(self):
        if self._keyboard is None:
            try:
                from ui.widgets.calc_keyboard import CalcKeyboard
                self._keyboard = CalcKeyboard(
                    self.settings, self.i18n, self)
                self._keyboard.equals_requested.connect(
                    self._on_keyboard_equals)
            except Exception as e:
                log_exc(e, module="MainWindow._ensure_keyboard")
        return self._keyboard

    def toggle_keyboard(self):
        kb = self._ensure_keyboard()
        if kb is None:
            return
        try:
            cur = self.stack.currentWidget()
            for k, w in self._panels.items():
                if w is cur:
                    kb.set_module(k)
                    break
        except Exception:
            pass
        try:
            if kb.isVisible():
                kb.hide()
            else:
                kb.show()
                kb.raise_()
        except Exception as e:
            log_exc(e, module="MainWindow.toggle_keyboard")

    def _on_keyboard_equals(self):
        """键盘按下 "=" 时，触发当前面板的 calc()。"""
        try:
            current = self.stack.currentWidget()
            fn = getattr(current, "calc", None)
            if callable(fn):
                fn()
        except Exception as e:
            log_exc(e, module="MainWindow._on_keyboard_equals")

    # ------------------------------------------------------------------
    # 跨面板发送
    # ------------------------------------------------------------------

    def _on_send_to_unit_view(self, _text):
        try:
            self._switch_by_key_pub("unit")
        except Exception:
            pass

    def _on_send_to_basic(self, text):
        try:
            self._switch_by_key_pub("basic")
            panel = self._panels.get("basic")
            if panel is not None:
                w = getattr(panel, "expr", None)
                if w is not None and hasattr(w, "setText"):
                    w.setText(str(text))
                    if hasattr(w, "setFocus"):
                        w.setFocus()
        except Exception as e:
            log_exc(e, module="MainWindow._on_send_to_basic")

    def _on_send_to_sci(self, text):
        try:
            self._switch_by_key_pub("scientific")
            panel = self._panels.get("scientific")
            if panel is not None:
                w = getattr(panel, "expr", None)
                if w is not None and hasattr(w, "setText"):
                    w.setText(str(text))
        except Exception as e:
            log_exc(e, module="MainWindow._on_send_to_sci")

    def _on_send_to_table(self, text):
        try:
            self._switch_by_key_pub("data_table")
            panel = self._panels.get("data_table")
            if panel is None:
                return
            if hasattr(panel, "_append_row"):
                panel._append_row()
                row = panel.table.rowCount() - 1
                panel.table.setItem(row, 0, QTableWidgetItem(str(text)))
        except Exception as e:
            log_exc(e, module="MainWindow._on_send_to_table")

    def _on_send_to_snippet(self, name, expr):
        try:
            snip_mod.add(name or "snippet", expr)
            self._switch_by_key_pub("snippets")
            panel = self._panels.get("snippets")
            if panel is not None and hasattr(panel, "_reload"):
                panel._reload()
        except Exception as e:
            log_exc(e, module="MainWindow._on_send_to_snippet")

    def _on_send_to_plot(self, text):
        try:
            self._switch_by_key_pub("plot")
            panel = self._panels.get("plot")
            if panel is not None and hasattr(panel, "add_curve"):
                panel.add_curve(str(text), "cartesian", "-10", "10")
                if hasattr(panel, "plot"):
                    panel.plot()
        except Exception as e:
            log_exc(e, module="MainWindow._on_send_to_plot")

    def _on_send_to_script(self, text):
        try:
            self._switch_by_key_pub("script")
            panel = self._panels.get("script")
            if panel is not None and hasattr(panel, "editor"):
                try:
                    panel.editor.setPlainText(str(text))
                except Exception:
                    pass
        except Exception as e:
            log_exc(e, module="MainWindow._on_send_to_script")

    # ------------------------------------------------------------------
    # 剪贴板智能识别
    # ------------------------------------------------------------------

    def _on_clipboard_expr(self, text):
        """剪贴板检测到表达式：toast 提示 + 点击送往基础面板。"""
        try:
            preview = (text or "").strip().replace("\n", " ")[:60]
            if not preview:
                return
        except Exception:
            return

        def _go():
            try:
                self.settings.set_draft("basic_expr", text)
                self._switch_by_key_pub("basic")
                panel = self._panels.get("basic")
                if panel is not None:
                    w = getattr(panel, "expr", None)
                    if w is not None and hasattr(w, "setText"):
                        w.setText(text)
                        if hasattr(w, "setFocus"):
                            w.setFocus()
                self.show_toast(
                    self.i18n.t("clipboard_sent_basic",
                                "已发送到基础面板"),
                    level="success", duration=1500)
            except Exception as e:
                log_exc(e, module="MainWindow._on_clipboard_expr._go")

        try:
            from ui.toast import toast as toast_fn
            toast_fn(self, f"📋 {preview}",
                     level="info", duration=3500, on_click=_go)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # URL 初始表达式
    # ------------------------------------------------------------------

    def _consume_init_expr(self):
        """消费由 main.py 通过环境变量传入的初始表达式。"""
        try:
            expr = os.environ.pop("MULTICALC_INIT_EXPR", "")
        except Exception:
            expr = ""
        if not expr:
            return
        try:
            self.settings.set_draft("basic_expr", expr)
            self._switch_by_key_pub("basic")
            panel = self._panels.get("basic")
            if panel is not None:
                w = getattr(panel, "expr", None)
                if w is not None and hasattr(w, "setText"):
                    w.setText(expr)
                    if hasattr(w, "setFocus"):
                        w.setFocus()
            self.show_toast(
                f"{self.i18n.t('init_expr_loaded', '已加载表达式')}: "
                f"{expr[:60]}",
                level="info", duration=3000)
        except Exception as e:
            log_exc(e, module="MainWindow._consume_init_expr")

    # ------------------------------------------------------------------
    # 可见性
    # ------------------------------------------------------------------

    def _apply_visibility(self):
        self._apply_filter(self.search_box.text())

    def open_visibility_dialog(self):
        try:
            current_keys = self._tree_keys()
            for k in self._keys:
                if k not in current_keys:
                    current_keys.append(k)

            titles = {k: self._titles.get(k, k) for k in current_keys}
            dlg = ModuleVisibilityDialog(
                self.i18n,
                current_order=current_keys,
                default_order=list(self._keys),
                titles=titles,
                visible_getter=self.settings.is_module_visible,
                parent=self,
            )
            if dlg.exec() != QDialog.Accepted:
                return
            order, vis = dlg.result_state()
            for k, v in vis.items():
                try:
                    self.settings.set_module_visible(k, v)
                except Exception:
                    pass
            self._reorder_tree_by_flat(order)
            self._apply_visibility()
        except Exception as e:
            log_exc(e, module="main_window.open_visibility_dialog")

    def _reorder_tree_by_flat(self, flat_order):
        pos = {k: i for i, k in enumerate(flat_order)}
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            children = []
            for j in range(parent.childCount()):
                child = parent.child(j)
                k = child.data(0, Qt.UserRole)
                children.append((pos.get(k, 9999), k, child))
            children.sort(key=lambda x: (x[0], x[1]))
            parent.takeChildren()
            for _, _, child in children:
                parent.addChild(child)

        self._item_by_key = {}
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            for j in range(parent.childCount()):
                child = parent.child(j)
                k = child.data(0, Qt.UserRole)
                if k:
                    self._item_by_key[k] = child

    def _rebuild_tree_and_filter(self):
        try:
            self._rebuild_tree()
            self._apply_filter(self.search_box.text())
        except Exception as e:
            log_exc(e, module="main_window._rebuild_tree_and_filter")

    # ------------------------------------------------------------------
    # 历史复用
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_module_key(module):
        m = str(module or "").strip().lower()
        if not m:
            return None
        if m in _MODULE_KEY_MAP:
            return _MODULE_KEY_MAP[m]
        for pfx, key in _MODULE_PREFIX_MAP:
            if m.startswith(pfx):
                return key
        return None

    def _on_reuse_from_history(self, module_key, expr):
        if not expr:
            return
        key = self._normalize_module_key(module_key)
        panel = self._panels.get(key) if key else None
        if panel is None:
            try:
                QApplication.clipboard().setText(expr)
            except Exception:
                pass
            return
        self._switch_by_key_pub(key)
        for attr in ("expr", "input", "data", "value", "d1",
                     "a", "enc_in", "cls_in"):
            w = getattr(panel, attr, None)
            if w is None:
                continue
            try:
                if hasattr(w, "setText"):
                    w.setText(expr)
                    if hasattr(w, "setCursorPosition"):
                        w.setCursorPosition(len(expr))
                    return
                if hasattr(w, "setPlainText"):
                    w.setPlainText(expr)
                    return
            except Exception:
                continue
        try:
            QApplication.clipboard().setText(expr)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 热重载
    # ------------------------------------------------------------------

    def _on_settings_changed(self, key=None):
        try:
            if key == "language":
                QTimer.singleShot(0, self.rebuild)
                return
            if key is None:
                if self.settings.get("language") != self.i18n.lang:
                    QTimer.singleShot(0, self.rebuild)
                    return
                QTimer.singleShot(0, self._rebuild_tree_and_filter)
            if key == "visible_modules":
                self._apply_visibility()
            elif key == "module_groups":
                QTimer.singleShot(0, self._rebuild_tree_and_filter)
            if key in (None, "theme", "font_family", "font_size",
                       "palette", "result_format"):
                self.apply_theme()
                if self._keyboard is not None:
                    try:
                        self._keyboard.refresh_theme()
                    except Exception:
                        pass
            for p in self._panels.values():
                fn = getattr(p, "on_settings_changed", None)
                if callable(fn):
                    try:
                        fn(key)
                    except Exception as e:
                        log_exc(e, module="main_window.on_settings_changed")
        except Exception as e:
            log_exc(e, module="main_window._on_settings_changed")

    def _on_settings_file_changed(self, _path):
        QTimer.singleShot(200, self._reload_from_file)

    def _reload_from_file(self):
        try:
            old_lang = self.settings.get("language")
            if self.settings.reload_if_changed():
                if self.settings.get("language") != old_lang:
                    self.rebuild()
                else:
                    self._on_settings_changed(None)
        except Exception as e:
            log_exc(e, module="main_window._reload_from_file")
        finally:
            path = getattr(self.settings, "user_path", None)
            if path and path not in self._watcher.files():
                try:
                    self._watcher.addPath(path)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # 重建
    # ------------------------------------------------------------------

    def rebuild(self):
        try:
            self.i18n.load(self.settings.get("language", "zh_CN"))

            for w in list(self._panels.values()):
                fn = getattr(w, "shutdown_workers", None)
                if callable(fn):
                    try:
                        fn(2000)
                    except Exception:
                        pass

            for w in list(self._panels.values()):
                try:
                    self.stack.removeWidget(w)
                except Exception:
                    pass
                try:
                    w.setParent(None)
                    w.deleteLater()
                except Exception:
                    pass
            self._panels.clear()
            self._keys.clear()
            self._titles.clear()
            self._panel_group.clear()
            self._item_by_key.clear()

            try:
                self.removeDockWidget(self.dock)
            except Exception:
                pass
            try:
                self.dock.deleteLater()
            except Exception:
                pass

            old = self.centralWidget()
            if old is not None:
                self.setCentralWidget(None)
                old.setParent(None)
                try:
                    old.deleteLater()
                except Exception:
                    pass

            if self._split is not None:
                try:
                    self._split.close_secondary()
                except Exception:
                    pass
                self._split = None
                self.setCentralWidget(None)

            self._build()
        except Exception as e:
            log_exc(e, module="main_window.rebuild")

    # ------------------------------------------------------------------
    # 主题
    # ------------------------------------------------------------------

    def _resolve_theme(self) -> str:
        theme = self.settings.get("theme", "dark")
        if theme != "system":
            return theme
        try:
            hints = QGuiApplication.styleHints()
            if hints.colorScheme() == Qt.ColorScheme.Light:
                return "light"
        except Exception:
            pass
        return "dark"

    def apply_theme(self):
        try:
            resolved = self._resolve_theme()
            pal = self.settings.palette(resolved)
            bg = pal.get("bg", "#1e1e1e")
            fg = pal.get("fg", "#ffffff")
            panel = pal.get("panel", "#2d2d30")
            accent = pal.get("accent", "#007acc")
            border = pal.get("border", "#3f3f46")
            hover = pal.get("hover", "#3a3d41")
            family = self.settings.get("font_family", "Microsoft YaHei")
            size = int(self.settings.get("font_size", 11))

            self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background: {bg}; color: {fg};
                font-family: '{family}'; font-size: {size}pt;
            }}
            QDockWidget {{ color: {fg}; }}
            QDockWidget::title {{
                background: {panel}; padding: 6px; border: 1px solid {border};
            }}
            QLineEdit, QPlainTextEdit, QTextEdit, QComboBox,
            QSpinBox, QDoubleSpinBox {{
                background: {panel}; color: {fg};
                border: 1px solid {border}; padding: 5px;
                border-radius: 4px;
                selection-background-color: {accent};
            }}
            QPushButton {{
                background: {panel}; color: {fg};
                border: 1px solid {border}; padding: 6px 10px;
                border-radius: 4px;
            }}
            QPushButton:hover {{ background: {accent}; color: #ffffff; }}
            QPushButton:pressed {{ background: {hover}; }}
            QPushButton:disabled {{ color: #888888; }}
            QTreeWidget, QListWidget {{
                background: {panel}; color: {fg};
                border: 1px solid {border}; border-radius: 4px;
                outline: none;
            }}
            QTreeWidget::item, QListWidget::item {{ padding: 5px 8px; }}
            QTreeWidget::item:selected, QListWidget::item:selected {{
                background: {accent}; color: #ffffff;
            }}
            QTreeWidget::item:hover, QListWidget::item:hover {{
                background: {hover};
            }}
            QTabWidget::pane {{
                border: 1px solid {border}; border-radius: 4px;
            }}
            QTabBar::tab {{
                background: {panel}; color: {fg};
                border: 1px solid {border}; padding: 6px 14px;
            }}
            QTabBar::tab:selected {{ background: {accent}; color: #ffffff; }}
            QHeaderView::section {{
                background: {panel}; color: {fg};
                border: 1px solid {border}; padding: 5px;
            }}
            QTableWidget {{
                background: {panel}; color: {fg};
                gridline-color: {border}; border: 1px solid {border};
            }}
            QCheckBox, QLabel {{ background: transparent; color: {fg}; }}
            QSplitter::handle {{ background: {border}; }}
            QScrollArea {{ border: none; background: {panel}; }}
            QMenu {{
                background: {panel}; color: {fg};
                border: 1px solid {border};
            }}
            QMenu::item:selected {{ background: {accent}; color: #ffffff; }}
            """)

            for lbl in self.findChildren(LatexLabel):
                try:
                    lbl.set_color(fg)
                except Exception:
                    pass
            for p in self._panels.values():
                fn = getattr(p, "set_theme_colors", None)
                if callable(fn):
                    try:
                        fn(fg, bg, panel)
                    except Exception:
                        pass
        except Exception as e:
            log_exc(e, module="main_window.apply_theme")

    # ------------------------------------------------------------------
    # 布局
    # ------------------------------------------------------------------

    def _save_layout(self):
        try:
            area = ("left" if self.dockWidgetArea(self.dock) == Qt.LeftDockWidgetArea
                    else "right")
            self.settings.set("workspace_layout", {
                "dock_area": area,
                "dock_visible": self.dock.isVisible(),
                "list_visible": self.tree.isVisible(),
                "window_state": base64.b64encode(self.saveState()).decode("ascii"),
            }, notify=False)
        except Exception as e:
            log_exc(e, module="main_window._save_layout")

    def _restore_layout(self):
        layout = self.settings.get("workspace_layout")
        if not isinstance(layout, dict):
            return
        try:
            if "dock_area" in layout:
                area = {"left": Qt.LeftDockWidgetArea,
                        "right": Qt.RightDockWidgetArea}.get(
                            layout["dock_area"], Qt.LeftDockWidgetArea)
                self.addDockWidget(area, self.dock)
            if "dock_visible" in layout:
                self.dock.setVisible(bool(layout["dock_visible"]))
            if "list_visible" in layout:
                self.tree.setVisible(bool(layout["list_visible"]))
                self.search_box.setVisible(bool(layout["list_visible"]))
                self.vis_btn.setVisible(bool(layout["list_visible"]))
            if "window_state" in layout and layout["window_state"]:
                try:
                    self.restoreState(base64.b64decode(layout["window_state"]))
                except Exception:
                    pass
        except Exception as e:
            log_exc(e, module="main_window._restore_layout")

    # ------------------------------------------------------------------
    # 菜单
    # ------------------------------------------------------------------

    def _build_menu(self):
        bar = self.menuBar()

        m_file = bar.addMenu(self.i18n.t("menu_file", "File"))
        a_quit = QAction(self.i18n.t("quit", "Quit"), self)
        a_quit.triggered.connect(self._quit_app)
        m_file.addAction(a_quit)

        m_view = bar.addMenu(self.i18n.t("menu_view", "View"))
        a_palette = QAction(self.i18n.t("command_palette", "Command palette"),
                            self)
        a_palette.setShortcut("Ctrl+K")
        a_palette.triggered.connect(self.open_command_palette)
        m_view.addAction(a_palette)

        a_kb = QAction(self.i18n.t("calc_keyboard", "计算器键盘"), self)
        a_kb.setShortcut("Ctrl+Shift+K")
        a_kb.triggered.connect(self.toggle_keyboard)
        m_view.addAction(a_kb)

        a_split = QAction(self.i18n.t("open_in_split", "Open in split"), self)
        a_split.setShortcut("Ctrl+\\")
        a_split.triggered.connect(self.open_current_in_split)
        m_view.addAction(a_split)

        a_close_split = QAction(self.i18n.t("close_split", "Close split"), self)
        a_close_split.triggered.connect(self.close_split)
        m_view.addAction(a_close_split)

        m_view.addSeparator()
        a_vis = QAction(self.i18n.t("module_visibility", "Modules"), self)
        a_vis.triggered.connect(self.open_visibility_dialog)
        m_view.addAction(a_vis)

        m_view.addSeparator()

        # 手写 / OCR / AI 批量
        a_hand = QAction(
            self.i18n.t("handwriting_title", "手写输入…"), self)
        a_hand.setShortcut("Ctrl+Shift+H")
        a_hand.triggered.connect(self.open_handwriting)
        m_view.addAction(a_hand)

        a_ocr = QAction(
            self.i18n.t("ocr_title", "截图 / 图片识别…"), self)
        a_ocr.setShortcut("Ctrl+Shift+O")
        a_ocr.triggered.connect(self.open_ocr_input)
        m_view.addAction(a_ocr)

        a_batch = QAction(
            self.i18n.t("ai_batch_tab", "AI 批量翻译…"), self)
        a_batch.triggered.connect(self.open_ai_batch)
        m_view.addAction(a_batch)

        m_view.addSeparator()

        # 专注模式（用独立 QShortcut 触发，见下方注册）
        a_focus = QAction(
            self.i18n.t("focus_mode", "专注模式 (F11)"), self)
        a_focus.triggered.connect(self.toggle_focus_mode)
        m_view.addAction(a_focus)

        # 会话导入
        a_session = QAction(
            self.i18n.t("import_session", "打开 .mcsession…"), self)
        a_session.triggered.connect(self.import_session)
        m_view.addAction(a_session)

        # 独立 QShortcut 注册 F11：菜单栏隐藏后仍生效
        sc_focus = QShortcut(QKeySequence("F11"), self)
        sc_focus.setContext(Qt.ApplicationShortcut)
        sc_focus.activated.connect(self.toggle_focus_mode)
        self._focus_shortcut = sc_focus

        # ---------- 工具菜单 ----------
        m_tools = bar.addMenu(self.i18n.t("menu_tools", "Tools"))
        a_upd = QAction(self.i18n.t("check_update", "Check for updates"), self)
        a_upd.triggered.connect(self._check_update)
        m_tools.addAction(a_upd)

        a_plugins = QAction(self.i18n.t("plugins", "Plugins"), self)
        a_plugins.triggered.connect(self._show_plugins)
        m_tools.addAction(a_plugins)

        a_tray = QAction(self.i18n.t("toggle_tray", "Toggle tray"), self)
        a_tray.triggered.connect(self._toggle_tray)
        m_tools.addAction(a_tray)

        # ---------- 帮助菜单 ----------
        m_help = bar.addMenu(self.i18n.t("menu_help", "帮助"))
        a_help = QAction(
            self.i18n.t("shortcuts_title", "快捷键速查表"), self)
        a_help.setShortcut("F1")
        a_help.triggered.connect(self._show_shortcuts)
        m_help.addAction(a_help)

    # ------------------------------------------------------------------
    # 命令面板
    # ------------------------------------------------------------------

    def _collect_commands(self):
        cmds = []
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            for j in range(parent.childCount()):
                child = parent.child(j)
                key = child.data(0, Qt.UserRole)
                if key:
                    cmds.append((
                        f"{self.i18n.t('go_to', 'Go to')}: {child.text(0)}",
                        lambda k=key: self._switch_by_key_pub(k)))

        cmds.append((self.i18n.t("settings"), self._go_settings))
        cmds.append((self.i18n.t("module_visibility", "Modules"),
                     self.open_visibility_dialog))
        cmds.append((self.i18n.t("open_in_split", "Open in split"),
                     self.open_current_in_split))
        cmds.append((self.i18n.t("close_split", "Close split"),
                     self.close_split))

        cmds.append((self.i18n.t("calc_keyboard_show", "显示计算器键盘"),
                     self.toggle_keyboard))

        for name, info in self.settings.themes().items():
            cmds.append((f"theme: {info.get('label', name)}",
                         lambda x=name: self.settings.set("theme", x)))
        cmds.append(("theme: system",
                     lambda: self.settings.set("theme", "system")))

        cmds.append(("check update", self._check_update))
        cmds.append(("clear history", self._clear_history_cmd))
        cmds.append(("refresh rates", self._refresh_rates_cmd))
        cmds.append(("import settings", self._import_settings_cmd))
        cmds.append(("export settings", self._export_settings_cmd))
        cmds.append((self.i18n.t("toggle_tray", "Toggle tray"),
                     self._toggle_tray))
        cmds.append((self.i18n.t("reset", "Reset settings"),
                     lambda: self.settings.reset()))
        return cmds

    def _clear_history_cmd(self):
        try:
            self.history.clear()
        except Exception as e:
            log_exc(e, module="MainWindow._clear_history_cmd")

    def _refresh_rates_cmd(self):
        try:
            panel = self._panels.get("currency")
            if panel and hasattr(panel, "_refresh_async"):
                panel._refresh_async(force=True)
        except Exception as e:
            log_exc(e, module="MainWindow._refresh_rates_cmd")

    def _import_settings_cmd(self):
        try:
            panel = self._panels.get("settings")
            if panel and hasattr(panel, "_import"):
                panel._import()
        except Exception as e:
            log_exc(e, module="MainWindow._import_settings_cmd")

    def _export_settings_cmd(self):
        try:
            panel = self._panels.get("settings")
            if panel and hasattr(panel, "_export"):
                panel._export()
        except Exception as e:
            log_exc(e, module="MainWindow._export_settings_cmd")

    def _palette_history(self, query, limit=10):
        try:
            return self.history.list(search=query, limit=int(limit))
        except Exception:
            return []

    def _palette_calc(self, expr):
        try:
            angle = self.settings.get("angle_mode", "RAD") or "RAD"
            return engine.basic_calc_smart(expr, angle)
        except Exception:
            return engine.basic_calc_smart(expr)

    def open_command_palette(self):
        try:
            dlg = CommandPalette(
                self.i18n,
                self._collect_commands(),
                self,
                history_search=self._palette_history,
                calc=self._palette_calc,
                reuse_handler=self._on_reuse_from_history,
            )
            dlg.exec()
        except Exception as e:
            log_exc(e, module="MainWindow.open_command_palette")

    # ------------------------------------------------------------------
    # 分屏
    # ------------------------------------------------------------------

    def _ensure_split(self):
        if self._split is None:
            old = self.centralWidget()
            if old is not None:
                self.takeCentralWidget()
                old.setParent(None)
            self._split = SplitView(self.stack, self)
            self.setCentralWidget(self._split)
        return self._split

    def open_current_in_split(self):
        try:
            current = self.stack.currentWidget()
            for k, w in self._panels.items():
                if w is current:
                    panel = self._panels.get(k)
                    if panel is not None:
                        sp = self._ensure_split()
                        sp.show_panel(panel)
                    return
        except Exception as e:
            log_exc(e, module="MainWindow.open_current_in_split")

    def close_split(self):
        try:
            if self._split is None:
                return
            sec = self._split.secondary
            while sec.count():
                w = sec.widget(0)
                sec.removeWidget(w)
                if self.stack.indexOf(w) == -1:
                    self.stack.addWidget(w)
            self._split.close_secondary()
        except Exception as e:
            log_exc(e, module="MainWindow.close_split")

    # ------------------------------------------------------------------
    # 更新 / 插件 / 托盘
    # ------------------------------------------------------------------

    def _check_update(self):
        try:
            current = self.settings.get("app_version", "1.0.0")
            has, latest, url = update_mod.check_update(current)
            if has:
                self.show_toast(
                    f"{self.i18n.t('new_version', '新版本')}: {latest}",
                    level="info", duration=5000)
            else:
                self.show_toast(
                    self.i18n.t("up_to_date", "已是最新版"),
                    level="success")
        except Exception as e:
            log_exc(e, module="MainWindow._check_update")

    def _show_plugins(self):
        try:
            root = os.path.join(self.base_path, "plugins")
            infos = plugin_mod.discover(root)
            if not infos:
                QMessageBox.information(
                    self, self.i18n.t("plugins", "Plugins"),
                    self.i18n.t("no_plugins", "No plugins installed"))
                return
            text = "\n\n".join(
                f"{i.name}  v{i.version}\n{i.description}\n{i.path}"
                for i in infos)
            QMessageBox.information(
                self, self.i18n.t("plugins", "Plugins"), text)
        except Exception as e:
            log_exc(e, module="MainWindow._show_plugins")

    def _load_plugins(self):
        try:
            root = os.path.join(self.base_path, "plugins")
            for info in plugin_mod.discover(root):
                if info.enabled:
                    plugin_mod.load_plugin(info, app_context={
                        "settings": self.settings,
                        "i18n": self.i18n,
                        "history": self.history,
                        "main_window": self,
                    })
        except Exception as e:
            log_exc(e, module="MainWindow._load_plugins")

    def _toggle_tray(self):
        try:
            if self._tray.is_enabled():
                self._tray.uninstall()
                self.settings.set("tray_enabled", False)
            else:
                self._tray.install()
                self.settings.set("tray_enabled", True)
        except Exception as e:
            log_exc(e, module="MainWindow._toggle_tray")

    def _quit_app(self):
        try:
            self._force_quit = True
            QApplication.instance().quit()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Toast / 快捷键速查表
    # ------------------------------------------------------------------

    def show_toast(self, text, level="info", duration=2500):
        """给面板 / 插件调用的轻量提示入口。"""
        try:
            from ui.toast import toast
            return toast(self, text, level=level, duration=duration)
        except Exception as e:
            log_exc(e, module="MainWindow.show_toast")
            return None

    def _show_shortcuts(self):
        try:
            from ui.shortcuts_dialog import ShortcutsDialog
            dlg = ShortcutsDialog(self.i18n, self)
            dlg.exec()
        except Exception as e:
            log_exc(e, module="MainWindow._show_shortcuts")

    # ------------------------------------------------------------------
    # 创新输入：手写 / OCR / AI 批量
    # ------------------------------------------------------------------

    def open_handwriting(self):
        """打开手写画板；结果插入到打开前的焦点输入框。"""
        try:
            from ui.widgets.focus_tracker import FocusTracker
            from ui.widgets.handwriting import HandwritingDialog
        except Exception as e:
            log_exc(e, module="MainWindow.open_handwriting")
            return

        try:
            tracker = FocusTracker.instance()
            target_before = tracker.target()
        except Exception:
            target_before = None

        try:
            dlg = HandwritingDialog(self.i18n, self)
            if dlg.exec() == QDialog.Accepted and dlg.expression:
                self._insert_into_target(target_before, dlg.expression)
        except Exception as e:
            log_exc(e, module="MainWindow.open_handwriting")

    def open_ocr_input(self):
        """打开图片识别对话框。"""
        try:
            from ui.widgets.focus_tracker import FocusTracker
            from ui.widgets.ocr_input import OCRInputDialog
        except Exception as e:
            log_exc(e, module="MainWindow.open_ocr_input")
            return

        try:
            tracker = FocusTracker.instance()
            target_before = tracker.target()
        except Exception:
            target_before = None

        try:
            dlg = OCRInputDialog(self.i18n, self)
            if dlg.exec() == QDialog.Accepted and dlg.expression:
                self._insert_into_target(target_before, dlg.expression)
        except Exception as e:
            log_exc(e, module="MainWindow.open_ocr_input")

    def open_ai_batch(self):
        """切到 AI 面板的批量 Tab。"""
        try:
            self._switch_by_key_pub("ai")
            panel = self._panels.get("ai")
            if panel is not None and hasattr(panel, "tabs"):
                try:
                    panel.tabs.setCurrentIndex(1)
                except Exception:
                    pass
        except Exception as e:
            log_exc(e, module="MainWindow.open_ai_batch")

    def _insert_into_target(self, widget, text: str):
        """把 text 插入到 widget（QLineEdit / QPlainTextEdit / QTextEdit）。

        若 widget 已失效则复制到剪贴板并用 toast 提示。
        """
        try:
            if not text:
                return
            if widget is not None:
                try:
                    widget.objectName()  # 探测是否已被销毁
                except RuntimeError:
                    widget = None

            if widget is None:
                QApplication.clipboard().setText(text)
                self.show_toast(
                    self.i18n.t("copied", "已复制") + f": {text[:40]}",
                    level="info")
                return

            inserted = False
            try:
                if hasattr(widget, "insert") and callable(widget.insert):
                    widget.insert(text)
                    inserted = True
                elif hasattr(widget, "insertPlainText"):
                    widget.insertPlainText(text)
                    inserted = True
            except Exception:
                inserted = False

            if not inserted:
                QApplication.clipboard().setText(text)
                self.show_toast(
                    self.i18n.t("copied", "已复制") + f": {text[:40]}",
                    level="info")
        except Exception as e:
            log_exc(e, module="MainWindow._insert_into_target")

    # ------------------------------------------------------------------
    # 专注模式
    # ------------------------------------------------------------------

    def toggle_focus_mode(self):
        """F11：隐藏菜单栏 / 侧边栏，仅留当前面板。

        - 用独立 QShortcut 触发（不再依赖菜单 action 的快捷键）
        - 进入时显示浮动「退出」按钮，作为 F11 失灵的兜底
        """
        try:
            if not self._focus_mode:
                # ---------- 进入 ----------
                self._focus_saved = {
                    "menubar": self.menuBar().isVisible(),
                    "dock": self.dock.isVisible(),
                    "tree": self.tree.isVisible(),
                    "search": self.search_box.isVisible(),
                    "vis_btn": self.vis_btn.isVisible(),
                    "toggle": self.toggle.isVisible(),
                }
                self.menuBar().setVisible(False)
                self.dock.setVisible(False)
                self._focus_mode = True
                self._show_focus_exit_button()
                self.show_toast(
                    self.i18n.t("focus_on", "专注模式：F11 退出"),
                    level="info", duration=2200)
            else:
                # ---------- 退出 ----------
                saved = self._focus_saved or {}
                self.menuBar().setVisible(saved.get("menubar", True))
                self.dock.setVisible(saved.get("dock", True))
                self.tree.setVisible(saved.get("tree", True))
                self.search_box.setVisible(saved.get("search", True))
                self.vis_btn.setVisible(saved.get("vis_btn", True))
                self.toggle.setVisible(saved.get("toggle", True))
                self._focus_mode = False
                self._hide_focus_exit_button()
                self.show_toast(
                    self.i18n.t("focus_off", "已退出专注模式"),
                    level="info", duration=1500)
        except Exception as e:
            log_exc(e, module="MainWindow.toggle_focus_mode")

    def _show_focus_exit_button(self):
        """进入专注时，右上角悬浮一个「退出」按钮（F11 兜底）。"""
        try:
            btn = QPushButton("✕ 退出专注 (F11)", self)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(50, 50, 55, 220);"
                "  color: #ffffff;"
                "  border: 1px solid #888888;"
                "  border-radius: 4px;"
                "  padding: 6px 12px;"
                "}"
                "QPushButton:hover { background: #c0392b; }"
            )
            btn.adjustSize()
            btn.move(max(10, self.width() - btn.width() - 24), 12)
            btn.clicked.connect(self.toggle_focus_mode)
            btn.show()
            btn.raise_()
            self._focus_exit_btn = btn
        except Exception as e:
            log_exc(e, module="MainWindow._show_focus_exit_button")

    def _hide_focus_exit_button(self):
        try:
            if self._focus_exit_btn is not None:
                self._focus_exit_btn.deleteLater()
                self._focus_exit_btn = None
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 会话导入
    # ------------------------------------------------------------------

    def import_session(self):
        """打开 .mcsession 文件，把条目加载到历史 + 脚本面板。"""
        try:
            from PySide6.QtWidgets import QFileDialog
        except Exception:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, self.i18n.t("import_session", "打开会话"),
            "", "MultiCalc Session (*.mcsession);;JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            entries = data.get("entries") if isinstance(data, dict) else None
            if not entries:
                self.show_toast(
                    self.i18n.t("session_empty", "会话为空"),
                    level="warn")
                return

            n = 0
            for it in entries:
                try:
                    self.history.add(
                        it.get("module") or "session",
                        it.get("expr") or "",
                        it.get("result") or "")
                    n += 1
                except Exception:
                    pass

            try:
                exprs = "\n".join(
                    (it.get("expr") or "").strip()
                    for it in entries if (it.get("expr") or "").strip())
                if exprs:
                    bus().send_to_script.emit(exprs)
            except Exception:
                pass

            try:
                hp = self._panels.get("history")
                if hp is not None and hasattr(hp, "refresh"):
                    hp.refresh()
            except Exception:
                pass

            self.show_toast(
                f"{self.i18n.t('session_loaded', '已加载会话')}: {n} 条",
                level="success", duration=2200)
        except Exception as e:
            log_exc(e, module="MainWindow.import_session")
            QMessageBox.warning(self, "Error", str(e))

    # ------------------------------------------------------------------
    # 关闭
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        try:
            if (self._tray.is_enabled()
                    and self.settings.get("minimize_to_tray", True)
                    and not self._force_quit):
                event.ignore()
                self.hide()
                return
        except Exception:
            pass

        try:
            if self._focus_mode:
                try:
                    self.toggle_focus_mode()   # 恢复 UI 状态
                except Exception:
                    pass

            g = self.geometry()
            self.settings.set(
                "window_geometry",
                [g.x(), g.y(), g.width(), g.height()],
                notify=False)
            self.settings.set(
                "window_size", [self.width(), self.height()], notify=False)

            current = self.stack.currentWidget()
            for k, w in self._panels.items():
                if w is current:
                    self.settings.set("last_module", k, notify=False)
                    break

            self._save_layout()
            try:
                self.settings.flush()
            except Exception:
                pass
        except Exception as e:
            log_exc(e, module="main_window.closeEvent")
        super().closeEvent(event)