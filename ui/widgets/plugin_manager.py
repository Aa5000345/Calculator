"""插件管理器：查看 / 启停 / 卸载插件。

由 MainWindow 通过菜单 → 工具 → 「插件…」打开：
    from ui.widgets.plugin_manager import PluginManagerDialog
    dlg = PluginManagerDialog(settings, i18n, base_path, self)
    dlg.exec()
"""
from __future__ import annotations

import json
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox,
    QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QPushButton,
    QSplitter, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from core import plugins as plugin_mod
from core import plugin_registry as reg_mod
from core.logger import log_exc


class PluginManagerDialog(QDialog):
    """插件管理器。"""

    def __init__(self, settings, i18n, base_path: str, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n
        self.base_path = base_path
        self.registry = reg_mod.get_registry()

        self.setWindowTitle(i18n.t("plugin_manager", "插件管理器"))
        self.resize(880, 560)

        # ---------------- 顶部工具栏 ----------------
        b_refresh = QPushButton(i18n.t("refresh", "刷新"))
        b_refresh.clicked.connect(self._reload)
        b_open_dir = QPushButton(i18n.t(
            "plugin_open_dir", "打开插件目录"))
        b_open_dir.clicked.connect(self._open_dir)
        b_snapshot = QPushButton(i18n.t(
            "plugin_snapshot", "导出注册表快照"))
        b_snapshot.clicked.connect(self._export_snapshot)

        top = QHBoxLayout()
        top.addWidget(b_refresh)
        top.addWidget(b_open_dir)
        top.addWidget(b_snapshot)
        top.addStretch(1)

        # ---------------- 左：插件列表 ----------------
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([
            i18n.t("plugin_name", "插件"),
            i18n.t("plugin_version", "版本"),
            i18n.t("plugin_enabled", "启用"),
        ])
        self.tree.setColumnWidth(0, 280)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.itemSelectionChanged.connect(self._on_select)
        self.tree.itemChanged.connect(self._on_item_changed)

        # ---------------- 右：详情 ----------------
        self.detail = QPlainTextEdit()
        self.detail.setReadOnly(True)

        # ---------------- 注册内容列表 ----------------
        self.registry_view = QTreeWidget()
        self.registry_view.setHeaderLabels([
            i18n.t("plugin_registry_item", "注册内容"),
            i18n.t("plugin_source", "来源"),
        ])
        self.registry_view.setColumnWidth(0, 340)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.addWidget(QLabel(i18n.t(
            "plugin_detail", "插件详情")))
        rv.addWidget(self.detail, 1)
        rv.addWidget(QLabel(i18n.t(
            "plugin_registry", "已注册内容")))
        rv.addWidget(self.registry_view, 2)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.tree)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([320, 560])

        # ---------------- 底部 ----------------
        self.summary = QLabel("")
        self.summary.setStyleSheet("color: #888;")

        box = QDialogButtonBox(QDialogButtonBox.Close)
        box.button(QDialogButtonBox.Close).setText(
            i18n.t("close", "关闭"))
        box.rejected.connect(self.reject)

        # ---------------- 布局 ----------------
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(splitter, 1)
        lay.addWidget(self.summary)
        lay.addWidget(box)

        self._reload()

    # ==================================================================
    # 加载
    # ==================================================================

    def _reload(self):
        # 清空
        self.tree.blockSignals(True)
        self.tree.clear()
        self.detail.setPlainText("")
        self.registry_view.clear()
        self._plugin_items = {}

        # 发现插件
        root = os.path.join(self.base_path, "plugins")
        try:
            infos = plugin_mod.discover(root)
        except Exception as e:
            log_exc(e, module="PluginManagerDialog._reload")
            infos = []

        n_enabled = 0
        for info in infos:
            item = QTreeWidgetItem([
                info.name, info.version or "—", ""])
            item.setData(0, Qt.UserRole, info)
            item.setCheckState(
                2, Qt.Checked if info.enabled else Qt.Unchecked)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            self.tree.addTopLevelItem(item)
            self._plugin_items[info.name] = item
            if info.enabled:
                n_enabled += 1

        self.tree.blockSignals(False)

        # 更新注册表视图
        self._refresh_registry_view()

        n_total = len(infos)
        self.summary.setText(self.i18n.t(
            "plugin_summary",
            "共 {total} 个插件，已启用 {enabled} 个")
            .format(total=n_total, enabled=n_enabled))

        if self.tree.topLevelItemCount():
            self.tree.setCurrentItem(self.tree.topLevelItem(0))

    def _refresh_registry_view(self):
        self.registry_view.clear()
        snap = self.registry.snapshot()

        for section, items in snap.items():
            if not items:
                continue
            parent = QTreeWidgetItem([
                self._section_label(section),
                f"({len(items)})",
            ])
            font = parent.font(0)
            font.setBold(True)
            parent.setFont(0, font)
            self.registry_view.addTopLevelItem(parent)
            for it in items:
                name = (it.get("key") or it.get("id")
                        or it.get("path") or it.get("name")
                        or "?")
                src = it.get("source") or "(内置)"
                en = "✓" if it.get("enabled") else "✗"
                child = QTreeWidgetItem(
                    [f"{en} {name}", src])
                parent.addChild(child)
            parent.setExpanded(True)

    def _section_label(self, section: str) -> str:
        return {
            "panels": self.i18n.t("plugin_sec_panels", "面板"),
            "commands": self.i18n.t("plugin_sec_commands", "命令"),
            "menus": self.i18n.t("plugin_sec_menus", "菜单项"),
            "themes": self.i18n.t("plugin_sec_themes", "主题"),
            "rates": self.i18n.t("plugin_sec_rates", "汇率源"),
            "status": self.i18n.t("plugin_sec_status", "状态栏组件"),
        }.get(section, section)

    # ==================================================================
    # 交互
    # ==================================================================

    def _on_select(self):
        items = self.tree.selectedItems()
        if not items:
            self.detail.setPlainText("")
            return
        item = items[0]
        info = item.data(0, Qt.UserRole)
        if info is None:
            return

        lines = [
            f"名称：{info.name}",
            f"版本：{info.version or '—'}",
            f"作者：{info.author or '—'}",
            f"描述：{info.description or '—'}",
            f"路径：{info.path}",
            f"启用：{'是' if info.enabled else '否'}",
            "",
        ]

        # 该插件注册的内容
        regs = self.registry.records_by_source(info.name)
        n_items = sum(len(v) for v in regs.values())
        lines.append(f"---- 注册内容（{n_items} 项）----")
        for section, records in regs.items():
            if records:
                lines.append(
                    f"  {self._section_label(section)}: "
                    f"{len(records)} 项")
                for r in records[:5]:
                    name = self._record_name(section, r)
                    lines.append(f"    - {name}")
                if len(records) > 5:
                    lines.append(
                        f"    ... 还有 {len(records) - 5} 项")

        self.detail.setPlainText("\n".join(lines))

    def _record_name(self, section: str, r) -> str:
        try:
            if section == "panels":
                return getattr(r.cls, "key", "?")
            if section == "commands":
                return r.command_id
            if section == "menus":
                return r.menu_path
            if section == "themes":
                return getattr(r.theme, "name", "?")
            if section == "rates":
                return getattr(r.source_obj, "name", "?")
            if section == "status":
                return f"{r.position}"
        except Exception:
            pass
        return "?"

    def _on_item_changed(self, item, col):
        if col != 2:
            return
        info = item.data(0, Qt.UserRole)
        if info is None:
            return

        enabled = item.checkState(2) == Qt.Checked
        if enabled == info.enabled:
            return
        info.enabled = enabled

        # 更新 plugin.json
        try:
            self._set_plugin_enabled(info, enabled)
        except Exception as e:
            log_exc(e, module="PluginManagerDialog._on_item_changed")

        # 同步到运行时注册表
        try:
            self.registry.set_enabled(info.name, enabled)
        except Exception:
            pass

        # 提示
        QMessageBox.information(
            self,
            self.i18n.t("plugin_manager", "插件管理器"),
            self.i18n.t(
                "plugin_toggle_hint",
                "已{state}「{name}」。部分改动需重启应用生效。")
            .format(
                state=self.i18n.t("plugin_enabled_on", "启用")
                if enabled else
                self.i18n.t("plugin_enabled_off", "禁用"),
                name=info.name))

        self._refresh_registry_view()

    def _set_plugin_enabled(self, info, enabled: bool):
        """写回 plugin.json。"""
        meta_path = os.path.join(info.path, "plugin.json")
        if not os.path.exists(meta_path):
            return
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
            data["enabled"] = bool(enabled)
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            raise RuntimeError(f"写入 plugin.json 失败：{e}")

    # ==================================================================
    # 工具
    # ==================================================================

    def _open_dir(self):
        try:
            path = os.path.join(self.base_path, "plugins")
            os.makedirs(path, exist_ok=True)
            import sys
            import subprocess
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            log_exc(e, module="PluginManagerDialog._open_dir")
            QMessageBox.information(
                self, "Path",
                os.path.join(self.base_path, "plugins"))

    def _export_snapshot(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.i18n.t("plugin_snapshot", "导出注册表快照"),
            "plugin_registry.json", "JSON (*.json)")
        if not path:
            return
        try:
            snap = self.registry.snapshot()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(snap, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "OK", path)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))