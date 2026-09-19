"""会话快照对话框：时间线视图 + 恢复 / 删除 / 比较。"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox,
    QFileDialog, QHBoxLayout, QInputDialog, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton,
    QSplitter, QVBoxLayout, QWidget,
)

from core import snapshot as snap_mod
from core.base import log_exc

class SnapshotDialog(QDialog):
    """快照时间线对话框。

    由 MainWindow 调用：
        dlg = SnapshotDialog(settings, i18n, parent=main_window)
        dlg.restore_requested.connect(on_restore)
        dlg.exec()
    """

    def __init__(self, settings, i18n, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n
        self.mgr = snap_mod.get_manager()
        self._selected_id = None
        self._compare_id = None

        self.setWindowTitle(i18n.t(
            "snapshot_title", "会话快照 / 时间机器"))
        self.resize(860, 560)

        # ---------------- 顶部操作 ----------------
        b_new = QPushButton(i18n.t("snapshot_new", "新建快照"))
        b_new.clicked.connect(self._new_snapshot)

        b_refresh = QPushButton(i18n.t("refresh", "刷新"))
        b_refresh.clicked.connect(self._refresh)

        b_delete = QPushButton(i18n.t("delete", "删除"))
        b_delete.clicked.connect(self._delete_selected)

        b_rename = QPushButton(i18n.t("snapshot_rename", "重命名"))
        b_rename.clicked.connect(self._rename_selected)

        b_export = QPushButton(i18n.t("export", "导出"))
        b_export.clicked.connect(self._export_selected)

        b_clear = QPushButton(i18n.t("snapshot_clear_all", "清空全部"))
        b_clear.clicked.connect(self._clear_all)

        top = QHBoxLayout()
        for b in (b_new, b_refresh, b_rename, b_delete,
                  b_export, b_clear):
            top.addWidget(b)
        top.addStretch(1)

        # ---------------- 左：列表 ----------------
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.itemSelectionChanged.connect(self._on_select)
        self.list.itemDoubleClicked.connect(
            lambda _: self._restore_selected())

        self.compare_chk = QCheckBox(i18n.t(
            "snapshot_compare_hint", "勾选第二个以对比"))
        self.compare_chk.stateChanged.connect(
            lambda _: self._update_detail())

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.addWidget(QLabel(i18n.t("snapshot_list", "快照列表")))
        lv.addWidget(self.list, 1)
        lv.addWidget(self.compare_chk)

        # ---------------- 右：详情 ----------------
        self.detail = QPlainTextEdit()
        self.detail.setReadOnly(True)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.addWidget(QLabel(i18n.t("snapshot_detail", "详情")))
        rv.addWidget(self.detail, 1)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([300, 560])

        # ---------------- 底部按钮 ----------------
        box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.button(QDialogButtonBox.Ok).setText(
            i18n.t("snapshot_restore", "恢复"))
        box.button(QDialogButtonBox.Cancel).setText(
            i18n.t("cancel", "取消"))
        box.accepted.connect(self._restore_selected)
        box.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(splitter, 1)
        lay.addWidget(box)

        self._refresh()

    # ==================================================================
    # 刷新
    # ==================================================================

    def _refresh(self):
        self.list.clear()
        for meta in self.mgr.list():
            item = QListWidgetItem(
                f"{meta.title}\n"
                f"  {meta.created}  ·  {meta.entries} 项  ·  "
                f"{meta.size} 字节")
            item.setData(Qt.UserRole, meta.id)
            self.list.addItem(item)

        if self.list.count():
            self.list.setCurrentRow(0)

    def _current_ids(self):
        """返回当前选中的多个 id（按顺序）。"""
        out = []
        for it in self.list.selectedItems():
            sid = it.data(Qt.UserRole)
            if sid:
                out.append(sid)
        return out

    def _on_select(self):
        self._update_detail()

    def _update_detail(self):
        ids = self._current_ids()
        if not ids:
            self.detail.setPlainText("")
            return

        if len(ids) >= 2 and self.compare_chk.isChecked():
            self._show_diff(ids[0], ids[1])
        else:
            self._show_one(ids[0])

    def _show_one(self, sid: str):
        snap = self.mgr.get(sid)
        if snap is None:
            self.detail.setPlainText("快照不存在")
            return
        meta = snap.meta
        data = snap.data

        lines = [
            f"ID: {meta.id}",
            f"标题: {meta.title}",
            f"创建: {meta.created}",
            f"备注: {meta.note or '—'}",
            f"项数: {meta.entries}",
            f"大小: {meta.size} 字节",
            "",
            "---- 内容摘要 ----",
            f"settings 差异: {len(data.get('settings_diff') or {})} 项",
            f"变量/函数: {len(data.get('symbols') or {})} 个",
            f"片段: {len(data.get('snippets') or [])} 个",
            f"草稿: {len(data.get('drafts') or {})} 个",
            f"面板状态: {len(data.get('panel_states') or {})} 个",
        ]

        # settings diff 展开
        diff = data.get("settings_diff") or {}
        if diff:
            lines.append("")
            lines.append("---- settings 差异 ----")
            for k, v in list(diff.items())[:20]:
                vs = json.dumps(v, ensure_ascii=False)
                if len(vs) > 100:
                    vs = vs[:97] + "…"
                lines.append(f"  {k} = {vs}")
            if len(diff) > 20:
                lines.append(f"  ... 还有 {len(diff) - 20} 项")

        # 变量展开
        symbols = data.get("symbols") or {}
        if symbols:
            lines.append("")
            lines.append("---- 变量 / 函数 ----")
            for k, v in list(symbols.items())[:15]:
                vs = str(v)
                if len(vs) > 60:
                    vs = vs[:57] + "…"
                lines.append(f"  {k} = {vs}")
            if len(symbols) > 15:
                lines.append(f"  ... 还有 {len(symbols) - 15} 个")

        self.detail.setPlainText("\n".join(lines))

    def _show_diff(self, id_a: str, id_b: str):
        try:
            d = self.mgr.diff(id_a, id_b)
        except Exception as e:
            self.detail.setPlainText(f"✗ {e}")
            return

        lines = [
            f"对比：",
            f"  A = {id_a}",
            f"  B = {id_b}",
            "",
        ]
        for section in ("settings", "symbols", "drafts",
                        "panel_states"):
            sec = d.get(section) or {}
            added = sec.get("added") or {}
            removed = sec.get("removed") or {}
            changed = sec.get("changed") or {}
            if not (added or removed or changed):
                continue
            lines.append(f"==== {section} ====")
            if added:
                lines.append(f"  + 新增 {len(added)} 项:")
                for k, v in list(added.items())[:10]:
                    lines.append(f"      + {k} = {v}")
            if removed:
                lines.append(f"  - 删除 {len(removed)} 项:")
                for k, v in list(removed.items())[:10]:
                    lines.append(f"      - {k} = {v}")
            if changed:
                lines.append(f"  ~ 修改 {len(changed)} 项:")
                for k, v in list(changed.items())[:10]:
                    lines.append(
                        f"      ~ {k}: {v['from']} → {v['to']}")
            lines.append("")

        if len(lines) <= 4:
            lines.append("（无差异）")

        self.detail.setPlainText("\n".join(lines))

    # ==================================================================
    # 操作
    # ==================================================================

    def _new_snapshot(self):
        title, ok = QInputDialog.getText(
            self,
            self.i18n.t("snapshot_new", "新建快照"),
            self.i18n.t("snapshot_name_hint",
                        "快照名（留空自动生成）："))
        if not ok:
            return
        try:
            ctx = self._collect_context()
            self.mgr.create(title=title.strip(), context=ctx)
            self._refresh()
        except Exception as e:
            log_exc(e, module="SnapshotDialog._new_snapshot")
            QMessageBox.warning(self, "Error", str(e))

    def _collect_context(self) -> dict:
        """从父窗口（MainWindow）收集状态。"""
        out = {}
        try:
            w = self.parent()
            if w is None:
                return out

            # settings
            settings = getattr(w, "settings", None)
            if settings is not None:
                out["settings"] = settings
                out["drafts"] = dict(
                    (settings.data or {}).get("_drafts") or {})

            # symbols
            try:
                from core import symbols as sym_mod
                out["symbols"] = sym_mod.get_raw()
            except Exception:
                pass

            # snippets
            try:
                from core import snippets as snip_mod
                out["snippets"] = snip_mod.load()
            except Exception:
                pass

            # panel states
            states = {}
            panels = getattr(w, "_panels", {}) or {}
            for k, p in panels.items():
                try:
                    if hasattr(p, "expr"):
                        w_expr = getattr(p, "expr")
                        if hasattr(w_expr, "text"):
                            states[k] = w_expr.text()
                except Exception:
                    continue
            out["panel_states"] = states

        except Exception:
            pass
        return out

    def _restore_selected(self):
        ids = self._current_ids()
        if not ids:
            return
        sid = ids[0]
        snap = self.mgr.get(sid)
        if snap is None:
            return
        if QMessageBox.question(
                self,
                self.i18n.t("snapshot_restore", "恢复"),
                self.i18n.t(
                    "snapshot_restore_confirm",
                    "恢复「{title}」？当前状态将被覆盖。")
                .format(title=snap.meta.title),
                QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return

        try:
            data = self.mgr.restore(sid)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
            return

        # 通知父窗口应用
        try:
            w = self.parent()
            fn = getattr(w, "apply_snapshot", None)
            if callable(fn):
                fn(data)
        except Exception as e:
            log_exc(e, module="SnapshotDialog._restore_selected.apply")

        self.accept()

    def _delete_selected(self):
        ids = self._current_ids()
        if not ids:
            return
        if QMessageBox.question(
                self,
                self.i18n.t("delete", "删除"),
                self.i18n.t("snapshot_delete_confirm",
                            "删除选中的 {n} 个快照？")
                .format(n=len(ids)),
                QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        for sid in ids:
            self.mgr.delete(sid)
        self._refresh()

    def _rename_selected(self):
        ids = self._current_ids()
        if not ids:
            return
        sid = ids[0]
        snap = self.mgr.get(sid)
        if snap is None:
            return
        new, ok = QInputDialog.getText(
            self,
            self.i18n.t("snapshot_rename", "重命名"),
            self.i18n.t("snapshot_name_hint", "新名称："),
            text=snap.meta.title)
        if not ok:
            return
        self.mgr.rename(sid, new)
        self._refresh()

    def _export_selected(self):
        ids = self._current_ids()
        if not ids:
            return
        sid = ids[0]
        snap = self.mgr.get(sid)
        if snap is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export snapshot",
            f"snapshot_{sid}.json", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(snap.to_dict(), f,
                          ensure_ascii=False, indent=2)
            QMessageBox.information(self, "OK", path)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _clear_all(self):
        if QMessageBox.question(
                self,
                self.i18n.t("snapshot_clear_all", "清空全部"),
                self.i18n.t("snapshot_clear_confirm",
                            "删除所有快照？此操作不可撤销。"),
                QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        n = self.mgr.clear_all()
        QMessageBox.information(
            self, "OK",
            self.i18n.t("snapshot_cleared",
                        "已删除 {n} 个快照").format(n=n))
        self._refresh()