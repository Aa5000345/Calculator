"""快捷键编辑器组件：搜索 + 分组 + 录制 + 冲突高亮。

被 ui/panels/shortcut_settings_panel.py 使用。

用法：
    editor = ShortcutEditor(settings, i18n, parent)
    editor.changed.connect(on_shortcuts_changed)

修复记录：
- 第 18 轮：初版
- 本轮：修复 _import() 中 `.format` 行首语法错误（改为拆局部变量）
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog,
    QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMenu,
    QMessageBox, QPushButton, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from core import shortcut_config as sc_cfg
from core import shortcut_meta as sc_meta
from core import shortcut_scheme as sc_scheme
from core.logger import log_exc


# ===========================================================================
# 录制对话框
# ===========================================================================

class _RecordDialog(QDialog):
    """录制组合键。"""

    def __init__(self, i18n, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.key_sequence = ""
        self.setWindowTitle(i18n.t(
            "shortcut_record_title", "录制快捷键"))
        self.resize(380, 180)

        self.label = QLabel(i18n.t(
            "shortcut_record_hint", "按下组合键…"))
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(
            "font-size: 16pt; padding: 20px;"
            " background: rgba(128,128,128,0.15);"
            " border: 1px dashed #888; border-radius: 6px;")

        self.ok_btn = QPushButton(i18n.t("ok", "确定"))
        self.ok_btn.setEnabled(False)
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton(i18n.t("cancel", "取消"))
        self.cancel_btn.clicked.connect(self.reject)
        self.clear_btn = QPushButton(i18n.t(
            "shortcut_clear_key", "清除"))
        self.clear_btn.clicked.connect(self._clear)

        row = QHBoxLayout()
        row.addWidget(self.clear_btn)
        row.addStretch(1)
        row.addWidget(self.cancel_btn)
        row.addWidget(self.ok_btn)

        lay = QVBoxLayout(self)
        lay.addWidget(self.label, 1)
        lay.addLayout(row)

        self.setFocusPolicy(Qt.StrongFocus)

    def _clear(self):
        self.key_sequence = ""
        self.label.setText(self.i18n.t(
            "shortcut_empty", "（未设置）"))
        self.ok_btn.setEnabled(True)

    def keyPressEvent(self, event):
        key = event.key()
        mods = event.modifiers()

        if key in (Qt.Key_Control, Qt.Key_Shift,
                   Qt.Key_Alt, Qt.Key_Meta):
            return
        if key == Qt.Key_Escape:
            self.reject()
            return
        if key == Qt.Key_Backspace:
            self._clear()
            return

        seq = QKeySequence(mods | key)
        text = seq.toString()
        if not text:
            return
        self.key_sequence = text
        self.label.setText(text)

        if sc_meta.is_system_conflict(text):
            self.label.setStyleSheet(
                "font-size: 16pt; padding: 20px;"
                " background: rgba(240,80,80,0.15);"
                " border: 1px dashed #f05050;"
                " border-radius: 6px;"
                " color: #f05050;")
            self.label.setText(
                f"{text}\n⚠ 可能与系统快捷键冲突")
        else:
            self.label.setStyleSheet(
                "font-size: 16pt; padding: 20px;"
                " background: rgba(128,128,128,0.15);"
                " border: 1px dashed #888;"
                " border-radius: 6px;")

        self.ok_btn.setEnabled(True)

    def mousePressEvent(self, e):
        self.setFocus()
        super().mousePressEvent(e)


# ===========================================================================
# 编辑器
# ===========================================================================

class ShortcutEditor(QWidget):
    """快捷键编辑器。"""

    changed = Signal()

    def __init__(self, settings, i18n, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n

        # 顶部：搜索 + 预设方案
        self.search = QLineEdit()
        self.search.setPlaceholderText(
            i18n.t("shortcut_search_hint", "搜索命令…"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._on_search)

        self.preset_box = QComboBox()
        self.preset_box.addItem(
            i18n.t("shortcut_preset_custom", "（自定义）"), "custom")
        for p in sc_scheme.list_presets():
            label = (p["label_zh"]
                     if self.i18n.lang.startswith("zh")
                     else p["label_en"])
            self.preset_box.addItem(
                i18n.t("shortcut_preset_tpl", "方案：{n}")
                .format(n=label), p["name"])
        self._select_current_preset()
        self.preset_box.currentIndexChanged.connect(
            self._on_preset_changed)

        b_apply = QPushButton(i18n.t("apply", "应用"))
        b_apply.clicked.connect(self._apply_preset)

        # 中间：树
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([
            i18n.t("shortcut_col_command", "命令"),
            i18n.t("shortcut_col_keys", "快捷键"),
            i18n.t("shortcut_col_scope", "作用域"),
        ])
        self.tree.setColumnWidth(0, 300)
        self.tree.setColumnWidth(1, 220)
        self.tree.setColumnWidth(2, 80)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.itemDoubleClicked.connect(self._record_selected)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(
            self._show_context_menu)

        # 底部：操作
        self.conflict_chk = QCheckBox(
            i18n.t("shortcut_warn_system",
                   "警告系统级冲突"))
        self.conflict_chk.setChecked(True)
        self.conflict_chk.stateChanged.connect(
            lambda _: self._refresh())

        b_record = QPushButton(i18n.t("shortcut_record", "录制…"))
        b_record.clicked.connect(self._record_selected)
        b_clear = QPushButton(i18n.t("shortcut_clear", "清除"))
        b_clear.clicked.connect(self._clear_selected)
        b_reset = QPushButton(i18n.t("shortcut_reset_one", "恢复默认"))
        b_reset.clicked.connect(self._reset_selected)
        b_reset_all = QPushButton(i18n.t(
            "shortcut_reset_all", "全部恢复默认"))
        b_reset_all.clicked.connect(self._reset_all)
        b_export = QPushButton(i18n.t("export", "导出"))
        b_export.clicked.connect(self._export)
        b_import = QPushButton(i18n.t("import", "导入"))
        b_import.clicked.connect(self._import)

        btn_row = QHBoxLayout()
        for b in (b_record, b_clear, b_reset,
                  b_reset_all, b_export, b_import):
            btn_row.addWidget(b)
        btn_row.addStretch(1)

        self.status = QLabel("")
        self.status.setStyleSheet("color: #888; padding: 2px;")

        # 布局
        top = QHBoxLayout()
        top.addWidget(self.search, 1)
        top.addWidget(QLabel(i18n.t(
            "shortcut_preset", "预设方案")))
        top.addWidget(self.preset_box)
        top.addWidget(b_apply)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addLayout(top)
        lay.addWidget(self.tree, 1)
        lay.addLayout(btn_row)
        lay.addWidget(self.conflict_chk)
        lay.addWidget(self.status)

        self._refresh()

    # ==================================================================
    # 视图刷新
    # ==================================================================

    def _select_current_preset(self):
        name = sc_scheme.current_scheme_name()
        idx = self.preset_box.findData(name)
        if idx < 0:
            idx = self.preset_box.findData("custom")
        if idx >= 0:
            self.preset_box.setCurrentIndex(idx)

    def _on_search(self, *_):
        self._refresh()

    def _on_preset_changed(self, *_):
        pass

    def _refresh(self):
        q = self.search.text().strip()
        metas = sc_meta.search(q) if q else sc_meta.all_metas()

        conflicts = {}
        warn_sys = self.conflict_chk.isChecked()
        try:
            for c in sc_scheme.detect_conflicts(
                    include_system=warn_sys):
                for cmd_id in c["commands"]:
                    conflicts.setdefault(cmd_id, []).append(c)
        except Exception as e:
            log_exc(e, module="ShortcutEditor._refresh.conflicts")

        groups = sc_meta.list_groups()
        by_group: dict = {k: [] for k, _, _ in groups}
        for m in metas:
            by_group.setdefault(m.group, []).append(m)

        self.tree.clear()

        for gk, gzh, gen in groups:
            items = by_group.get(gk, [])
            if not items:
                continue
            label = (gzh if self.i18n.lang.startswith("zh")
                     else gen)
            parent = QTreeWidgetItem([label, "", ""])
            font = parent.font(0)
            font.setBold(True)
            parent.setFont(0, font)
            parent.setFlags(parent.flags() & ~Qt.ItemIsSelectable)
            self.tree.addTopLevelItem(parent)

            for m in items:
                key = sc_cfg.get(m.command_id)
                label_text = (m.label
                              if self.i18n.lang.startswith("zh")
                              else (m.label_en or m.label))
                key_text = key or self.i18n.t(
                    "shortcut_empty", "（未设置）")
                child = QTreeWidgetItem([
                    label_text, key_text, m.scope])
                child.setData(0, Qt.UserRole, m.command_id)
                if m.command_id in conflicts:
                    child.setForeground(1, Qt.red)
                    tips = []
                    for c in conflicts[m.command_id]:
                        if c["is_system"]:
                            tips.append(self.i18n.t(
                                "shortcut_conflict_system",
                                "⚠ 与系统快捷键冲突"))
                        else:
                            tips.append(self.i18n.t(
                                "shortcut_conflict_internal",
                                "⚠ 与 {n} 个命令冲突")
                                .format(n=len(c["commands"])))
                    child.setToolTip(1, "\n".join(set(tips)))
                parent.addChild(child)

        self.tree.expandAll()

        n_conf = sum(1 for k, v in conflicts.items() if v)
        if n_conf:
            self.status.setText(self.i18n.t(
                "shortcut_conflict_summary",
                "发现 {n} 个冲突键位").format(n=n_conf))
            self.status.setStyleSheet("color: #e74c3c;")
        else:
            self.status.setText(self.i18n.t(
                "shortcut_no_conflict", "无冲突"))
            self.status.setStyleSheet("color: #2ecc71;")

    # ==================================================================
    # 选择
    # ==================================================================

    def _selected_command_id(self):
        items = self.tree.selectedItems()
        if not items:
            return None
        item = items[0]
        cmd_id = item.data(0, Qt.UserRole)
        return cmd_id if cmd_id else None

    # ==================================================================
    # 录制 / 清除 / 重置
    # ==================================================================

    def _record_selected(self, *_):
        cmd_id = self._selected_command_id()
        if cmd_id is None:
            return

        meta = sc_meta.get_meta(cmd_id)

        dlg = _RecordDialog(self.i18n, self)
        if dlg.exec() != QDialog.Accepted:
            return

        new_key = dlg.key_sequence

        if new_key:
            current = {
                m.command_id: sc_cfg.get(m.command_id)
                for m in sc_meta.all_metas()
            }
            current[cmd_id] = new_key
            confs = sc_scheme.detect_conflicts(
                keys=current,
                include_system=self.conflict_chk.isChecked())
            related = [
                c for c in confs
                if cmd_id in c["commands"]
            ]
            if related:
                msgs = []
                for c in related:
                    if c["is_system"]:
                        msgs.append(
                            f"• {c['key']} 可能与系统快捷键冲突")
                    else:
                        others = [x for x in c["commands"]
                                  if x != cmd_id]
                        names = [
                            (sc_meta.get_meta(x).label
                             if sc_meta.get_meta(x) else x)
                            for x in others
                        ]
                        msgs.append(
                            f"• {c['key']} 已被 "
                            f"{', '.join(names)} 使用")
                ret = QMessageBox.question(
                    self,
                    self.i18n.t("shortcut_conflict_title",
                                "冲突警告"),
                    "\n".join(msgs) + "\n\n仍要设置吗？",
                    QMessageBox.Yes | QMessageBox.No)
                if ret != QMessageBox.Yes:
                    return

        try:
            sc_cfg.set(cmd_id, new_key)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
            return

        self._select_current_preset()
        self._refresh()
        self.changed.emit()

    def _clear_selected(self):
        cmd_id = self._selected_command_id()
        if cmd_id is None:
            return
        try:
            sc_cfg.set(cmd_id, "")
            self._refresh()
            self.changed.emit()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _reset_selected(self):
        cmd_id = self._selected_command_id()
        if cmd_id is None:
            return
        try:
            sc_cfg.reset(cmd_id)
            self._refresh()
            self.changed.emit()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _reset_all(self):
        if QMessageBox.question(
                self,
                self.i18n.t("shortcut_reset_all",
                            "全部恢复默认"),
                self.i18n.t("shortcut_reset_all_confirm",
                            "恢复所有快捷键为默认值？"),
                QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        try:
            sc_scheme.reset_to_default()
            self._select_current_preset()
            self._refresh()
            self.changed.emit()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    # ==================================================================
    # 方案
    # ==================================================================

    def _apply_preset(self):
        name = self.preset_box.currentData()
        if name == "custom":
            return
        try:
            info = sc_scheme.get_preset_info(name)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
            return

        label = (info["label_zh"]
                 if self.i18n.lang.startswith("zh")
                 else info["label_en"])
        ret = QMessageBox.question(
            self,
            self.i18n.t("shortcut_apply_preset",
                        "应用预设方案"),
            self.i18n.t(
                "shortcut_apply_preset_confirm",
                "应用「{name}」方案？当前自定义的键位将被覆盖。")
            .format(name=label),
            QMessageBox.Yes | QMessageBox.No)
        if ret != QMessageBox.Yes:
            return

        if sc_scheme.apply_preset(name):
            self._refresh()
            self.changed.emit()

    # ==================================================================
    # 导入 / 导出
    # ==================================================================

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.i18n.t("shortcut_export", "导出快捷键"),
            "shortcuts.json",
            "JSON (*.json)")
        if not path:
            return
        if sc_scheme.export_current(path):
            QMessageBox.information(
                self, "OK",
                self.i18n.t("shortcut_export_done",
                            "已导出到：{p}").format(p=path))
        else:
            QMessageBox.warning(
                self, "Error",
                self.i18n.t("shortcut_export_failed", "导出失败"))

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.i18n.t("shortcut_import", "导入快捷键"),
            "", "JSON (*.json)")
        if not path:
            return

        ret = QMessageBox.question(
            self,
            self.i18n.t("shortcut_import", "导入快捷键"),
            self.i18n.t(
                "shortcut_import_merge",
                "合并导入（保留未在文件中的命令）？\n"
                "选「否」将先重置为默认。"),
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        if ret == QMessageBox.Cancel:
            return
        merge = (ret == QMessageBox.Yes)

        r = sc_scheme.import_from(path, merge=merge)
        if not r.get("ok"):
            QMessageBox.warning(
                self, "Error", r.get("error", "导入失败"))
            return

        # 主消息（拆局部变量，避免 .format 在行首）
        msg = self.i18n.t(
            "shortcut_import_done",
            "导入完成：应用 {n} 项").format(n=r["applied"])

        # 若有未知命令，追加一段提示
        unknown = r.get("unknown") or []
        if unknown:
            unknown_list = ", ".join(str(x) for x in unknown[:8])
            if len(unknown) > 8:
                unknown_list += "..."
            unknown_tmpl = self.i18n.t(
                "shortcut_import_unknown",
                "忽略未知命令 {n} 项：\n{list}")
            msg += "\n\n" + unknown_tmpl.format(
                n=len(unknown), list=unknown_list)

        QMessageBox.information(self, "OK", msg)
        self._select_current_preset()
        self._refresh()
        self.changed.emit()

    # ==================================================================
    # 右键菜单
    # ==================================================================

    def _show_context_menu(self, pos):
        cmd_id = self._selected_command_id()
        if cmd_id is None:
            return

        menu = QMenu(self)
        a_rec = menu.addAction(self.i18n.t(
            "shortcut_record", "录制…"))
        a_clear = menu.addAction(self.i18n.t(
            "shortcut_clear", "清除"))
        a_reset = menu.addAction(self.i18n.t(
            "shortcut_reset_one", "恢复默认"))
        menu.addSeparator()
        a_copy = menu.addAction(self.i18n.t(
            "shortcut_copy_id", "复制命令 ID"))

        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen is a_rec:
            self._record_selected()
        elif chosen is a_clear:
            self._clear_selected()
        elif chosen is a_reset:
            self._reset_selected()
        elif chosen is a_copy:
            try:
                from PySide6.QtWidgets import QApplication
                QApplication.clipboard().setText(cmd_id)
            except Exception:
                pass


__all__ = ["ShortcutEditor"]