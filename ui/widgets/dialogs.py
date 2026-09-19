"""UI 对话框：快照 / 更新 / 插件管理 / 导览 / 欢迎页 /
快捷键编辑器。

合并自：ui/widgets/snapshot_dialog.py
        + ui/widgets/update_dialog.py
        + ui/widgets/plugin_manager.py
        + ui/widgets/quick_tour.py
        + ui/widgets/welcome_widget.py
        + ui/widgets/shortcut_editor.py

对外接口：
    SnapshotDialog          会话快照时间线
    UpdateDialog            检查更新 / 下载
    PluginManagerDialog     插件管理器
    QuickTour               首次启动 5 步导览
    WelcomeWidget           欢迎页组件
    ShortcutEditor          快捷键编辑器
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox,
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame,
    QGridLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMenu, QMessageBox,
    QPlainTextEdit, QProgressBar, QPushButton, QScrollArea,
    QSizePolicy, QSplitter, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from core import plugins as plugin_mod
from core import shortcuts as sc
from core import updater as upd_mod
from core import user_data as ud
from core.base import log_exc


__all__ = [
    "SnapshotDialog",
    "UpdateDialog",
    "PluginManagerDialog",
    "QuickTour",
    "WelcomeWidget",
    "ShortcutEditor",
]


# ===========================================================================
# 会话快照对话框
# ===========================================================================

class SnapshotDialog(QDialog):
    """快照时间线对话框：恢复 / 删除 / 重命名 / 对比 / 导出。"""

    def __init__(self, settings, i18n, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n
        self.mgr = ud.get_snapshot_manager()
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
        b_clear = QPushButton(
            i18n.t("snapshot_clear_all", "清空全部"))
        b_clear.clicked.connect(self._clear_all)

        top = QHBoxLayout()
        for b in (b_new, b_refresh, b_rename, b_delete,
                  b_export, b_clear):
            top.addWidget(b)
        top.addStretch(1)

        # ---------------- 左：列表 ----------------
        self.list = QListWidget()
        self.list.setSelectionMode(
            QAbstractItemView.ExtendedSelection)
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

        lines = ["对比：", f"  A = {id_a}", f"  B = {id_b}", ""]
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
        out = {}
        try:
            w = self.parent()
            if w is None:
                return out
            settings = getattr(w, "settings", None)
            if settings is not None:
                out["settings"] = settings
                out["drafts"] = dict(
                    (settings.data or {}).get("_drafts") or {})
            try:
                from core.state import get_raw as _sym_raw
                out["symbols"] = _sym_raw()
            except Exception:
                pass
            try:
                out["snippets"] = ud.snippet_load()
            except Exception:
                pass
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
        try:
            w = self.parent()
            fn = getattr(w, "apply_snapshot", None)
            if callable(fn):
                fn(data)
        except Exception as e:
            log_exc(
                e, module="SnapshotDialog._restore_selected.apply")
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


# ===========================================================================
# 更新对话框
# ===========================================================================

class _CheckWorker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, current, feed, silent=True, parent=None):
        super().__init__(parent)
        self._current = current
        self._feed = feed
        self._silent = silent

    def run(self):
        try:
            info = upd_mod.check_update(
                self._current, self._feed,
                silent=self._silent)
            self.done.emit(info)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class _DownloadWorker(QThread):
    progress = Signal(int, int, float)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, info, dest_dir, parent=None):
        super().__init__(parent)
        self._info = info
        self._dest = dest_dir
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            def _prog(p):
                self.progress.emit(int(p.done), int(p.total),
                                   float(p.speed_bps))

            def _canc():
                return self._cancelled

            r = upd_mod.download_asset(
                self._info, self._dest,
                progress_cb=_prog, cancelled=_canc)
            if not self._cancelled:
                self.done.emit(r)
        except Exception as e:  # noqa: BLE001
            if not self._cancelled:
                self.failed.emit(str(e))


class UpdateDialog(QDialog):
    """检查更新 / 下载。"""

    def __init__(self, settings, i18n, current_version: str,
                 parent=None):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n
        self.current_version = str(current_version or "1.0.0")

        self._check_worker: _CheckWorker | None = None
        self._download_worker: _DownloadWorker | None = None
        self._info = None

        self.setWindowTitle(i18n.t("update_title", "检查更新"))
        self.resize(600, 480)

        self.title = QLabel(i18n.t("update_checking", "正在检查…"))
        f = self.title.font()
        f.setBold(True)
        f.setPointSize(f.pointSize() + 1)
        self.title.setFont(f)

        self.meta = QLabel("")
        self.meta.setStyleSheet("color: #888;")

        self.notes = QPlainTextEdit()
        self.notes.setReadOnly(True)
        self.notes.setPlaceholderText(
            i18n.t("update_notes_hint", "（无发布说明）"))

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        self.status = QLabel("")
        self.status.setStyleSheet("color: #888;")

        self.b_check = QPushButton(i18n.t(
            "update_check_again", "重新检查"))
        self.b_check.clicked.connect(self.start_check)
        self.b_download = QPushButton(i18n.t(
            "update_download", "下载"))
        self.b_download.setEnabled(False)
        self.b_download.clicked.connect(self._start_download)
        self.b_cancel = QPushButton(i18n.t("cancel", "取消"))
        self.b_cancel.setEnabled(False)
        self.b_cancel.clicked.connect(self._cancel_download)
        self.b_open_page = QPushButton(i18n.t(
            "update_open_page", "打开 Release 页面"))
        self.b_open_page.setEnabled(False)
        self.b_open_page.clicked.connect(self._open_page)

        row = QHBoxLayout()
        row.addWidget(self.b_check)
        row.addWidget(self.b_open_page)
        row.addStretch(1)
        row.addWidget(self.b_cancel)
        row.addWidget(self.b_download)

        box = QDialogButtonBox(QDialogButtonBox.Close)
        box.button(QDialogButtonBox.Close).setText(
            i18n.t("close", "关闭"))
        box.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(self.title)
        lay.addWidget(self.meta)
        lay.addWidget(QLabel(i18n.t(
            "update_notes", "发布说明")))
        lay.addWidget(self.notes, 1)
        lay.addWidget(self.progress)
        lay.addWidget(self.status)
        lay.addLayout(row)
        lay.addWidget(box)

        self.start_check()

    def start_check(self):
        if (self._check_worker is not None
                and self._check_worker.isRunning()):
            return
        self.title.setText(self.i18n.t(
            "update_checking", "正在检查…"))
        self.meta.setText(f"当前版本：{self.current_version}")
        self.notes.setPlainText("")
        self.b_download.setEnabled(False)
        self.b_open_page.setEnabled(False)

        self._check_worker = _CheckWorker(
            self.current_version, upd_mod.DEFAULT_FEED,
            parent=self)
        self._check_worker.done.connect(self._on_check_done)
        self._check_worker.failed.connect(self._on_check_failed)
        self._check_worker.finished.connect(
            lambda: setattr(self, "_check_worker", None))
        self._check_worker.start()

    def _on_check_done(self, info):
        self._info = info
        if info.error:
            self.title.setText(self.i18n.t(
                "update_failed", "检查失败"))
            self.meta.setText(info.error)
            self.b_open_page.setEnabled(True)
            return
        self.b_open_page.setEnabled(bool(info.url))
        if not info.has_update:
            self.title.setText(self.i18n.t(
                "up_to_date", "已是最新版"))
            self.meta.setText(
                f"当前：{self.current_version}    "
                f"最新：{info.latest}")
            return
        self.title.setText(f"🎉 发现新版本：{info.latest}")
        self.meta.setText(
            f"当前：{self.current_version}  →  "
            f"最新：{info.latest}"
            + (f"    {info.published_at[:10]}"
               if info.published_at else ""))
        self.notes.setPlainText(info.notes or "")
        self.b_download.setEnabled(True)

    def _on_check_failed(self, msg: str):
        self.title.setText(self.i18n.t(
            "update_failed", "检查失败"))
        self.meta.setText(msg)

    def _start_download(self):
        if self._info is None or not self._info.has_update:
            return
        if (self._download_worker is not None
                and self._download_worker.isRunning()):
            return
        dest_dir = os.path.join(
            os.path.expanduser("~"),
            ".multicalc", "updates")
        os.makedirs(dest_dir, exist_ok=True)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.b_download.setEnabled(False)
        self.b_cancel.setEnabled(True)
        self.status.setText(self.i18n.t(
            "update_downloading", "正在下载…"))

        self._download_worker = _DownloadWorker(
            self._info, dest_dir, parent=self)
        self._download_worker.progress.connect(self._on_progress)
        self._download_worker.done.connect(self._on_download_done)
        self._download_worker.failed.connect(
            self._on_download_failed)
        self._download_worker.finished.connect(
            self._on_download_finished)
        self._download_worker.start()

    def _on_progress(self, done: int, total: int, speed: float):
        if total > 0:
            self.progress.setValue(min(100, int(done / total * 100)))
            self.status.setText(
                f"{done / (1 << 20):.1f} / "
                f"{total / (1 << 20):.1f} MiB  "
                f"({speed / (1 << 20):.1f} MiB/s)")
        else:
            self.progress.setValue(0)
            self.status.setText(
                f"已下载 {done / (1 << 20):.1f} MiB")

    def _on_download_done(self, r):
        if r.error:
            self._on_download_failed(r.error)
            return
        verified = (self.i18n.t("update_verified", "SHA256 已校验")
                    if r.verified
                    else self.i18n.t("update_not_verified",
                                     "未校验 SHA256"))
        self.status.setText(f"✓ {r.path}")
        self.title.setText(self.i18n.t(
            "update_download_done", "下载完成"))
        msg = (f"文件已下载到：\n{r.path}\n\n"
               f"大小：{r.size / (1 << 20):.2f} MiB\n"
               f"耗时：{r.elapsed:.1f}s\n"
               f"{verified}\n\n"
               f"请手动替换旧版本并重启。\n"
               f"是否现在打开所在文件夹？")
        ret = QMessageBox.question(
            self,
            self.i18n.t("update_download_done", "下载完成"),
            msg, QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            self._open_folder(os.path.dirname(r.path))

    def _on_download_failed(self, msg: str):
        self.status.setText(f"✗ {msg}")
        self.title.setText(self.i18n.t(
            "update_download_failed", "下载失败"))
        QMessageBox.warning(self, "Error", msg)

    def _on_download_finished(self):
        self.b_download.setEnabled(True)
        self.b_cancel.setEnabled(False)
        self._download_worker = None

    def _cancel_download(self):
        if self._download_worker is not None:
            self._download_worker.cancel()
            self.status.setText(self.i18n.t(
                "update_cancelled", "已取消"))

    def _open_page(self):
        try:
            url = (self._info.url if self._info else "")
            if not url:
                return
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl(url))
        except Exception as e:
            log_exc(e, module="UpdateDialog._open_page")

    def _open_folder(self, path: str):
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            log_exc(e, module="UpdateDialog._open_folder")
            QMessageBox.information(self, "Path", path)

    def closeEvent(self, e):
        try:
            if (self._check_worker is not None
                    and self._check_worker.isRunning()):
                self._check_worker.quit()
                self._check_worker.wait(1500)
        except Exception:
            pass
        try:
            if (self._download_worker is not None
                    and self._download_worker.isRunning()):
                self._download_worker.cancel()
                self._download_worker.wait(2000)
        except Exception:
            pass
        super().closeEvent(e)


# ===========================================================================
# 插件管理器
# ===========================================================================

class PluginManagerDialog(QDialog):
    """插件管理器。"""

    def __init__(self, settings, i18n, base_path: str,
                 parent=None):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n
        self.base_path = base_path
        self.registry = plugin_mod.get_registry()

        self.setWindowTitle(i18n.t(
            "plugin_manager", "插件管理器"))
        self.resize(880, 560)

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

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([
            i18n.t("plugin_name", "插件"),
            i18n.t("plugin_version", "版本"),
            i18n.t("plugin_enabled", "启用"),
        ])
        self.tree.setColumnWidth(0, 280)
        self.tree.setSelectionMode(
            QAbstractItemView.SingleSelection)
        self.tree.itemSelectionChanged.connect(self._on_select)
        self.tree.itemChanged.connect(self._on_item_changed)

        self.detail = QPlainTextEdit()
        self.detail.setReadOnly(True)

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

        self.summary = QLabel("")
        self.summary.setStyleSheet("color: #888;")

        box = QDialogButtonBox(QDialogButtonBox.Close)
        box.button(QDialogButtonBox.Close).setText(
            i18n.t("close", "关闭"))
        box.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(splitter, 1)
        lay.addWidget(self.summary)
        lay.addWidget(box)

        self._reload()

    def _reload(self):
        self.tree.blockSignals(True)
        self.tree.clear()
        self.detail.setPlainText("")
        self.registry_view.clear()
        self._plugin_items = {}

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
            "commands": self.i18n.t(
                "plugin_sec_commands", "命令"),
            "menus": self.i18n.t("plugin_sec_menus", "菜单项"),
            "themes": self.i18n.t("plugin_sec_themes", "主题"),
            "rates": self.i18n.t("plugin_sec_rates", "汇率源"),
            "status": self.i18n.t(
                "plugin_sec_status", "状态栏组件"),
        }.get(section, section)

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
        try:
            self._set_plugin_enabled(info, enabled)
        except Exception as e:
            log_exc(e,
                    module="PluginManagerDialog._on_item_changed")
        try:
            self.registry.set_enabled(info.name, enabled)
        except Exception:
            pass
        QMessageBox.information(
            self,
            self.i18n.t("plugin_manager", "插件管理器"),
            self.i18n.t(
                "plugin_toggle_hint",
                "已{state}「{name}」。部分改动需重启应用生效。")
            .format(
                state=self.i18n.t(
                    "plugin_enabled_on", "启用")
                if enabled else
                self.i18n.t("plugin_enabled_off", "禁用"),
                name=info.name))
        self._refresh_registry_view()

    def _set_plugin_enabled(self, info, enabled: bool):
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

    def _open_dir(self):
        try:
            path = os.path.join(self.base_path, "plugins")
            os.makedirs(path, exist_ok=True)
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


# ===========================================================================
# 快速导览
# ===========================================================================

_STEPS = [
    {
        "icon": "🧮",
        "title": "基础计算",
        "body": (
            "输入 `2+3*4`，按 Enter 即得结果。\n\n"
            "• 输入 `20% off 100` 直接算折扣\n"
            "• 输入 `tip 15% on 200` 算小费\n"
            "• M1~M9 是内存槽（左键召回、右键存入）"
        ),
    },
    {
        "icon": "⌨️",
        "title": "命令面板",
        "body": (
            "按 `Ctrl+K` 打开命令面板。\n\n"
            "• 输入 `= 2+2` 直接计算\n"
            "• 输入 `> theme` 只看主题相关命令\n"
            "• 输入 `jcjs` 拼音首字母搜「基础计算」\n"
            "• 越常用的命令越靠前"
        ),
    },
    {
        "icon": "🎹",
        "title": "浮动键盘",
        "body": (
            "按 `Ctrl+Shift+K` 呼出浮动键盘。\n\n"
            "• 不抢焦点，可以边看主窗口边点击\n"
            "• 自动跟随当前活跃的输入框\n"
            "• 支持 DEG / RAD 切换、2ⁿᵈ 二级函数、内存槽\n"
            "• 按模块自动切换布局（共 14 种）"
        ),
    },
    {
        "icon": "🔗",
        "title": "管道工作流",
        "body": (
            "把多步计算串起来：\n\n"
            "```\n"
            "1 km | to m | * 2 | round(3)\n"
            "100 USD | to CNY\n"
            "0.1 | as fraction\n"
            "```\n\n"
            "每一步的中间结果都会显示在表格里。"
        ),
    },
    {
        "icon": "📓",
        "title": "数学笔记本",
        "body": (
            "像 Jupyter 一样，但更轻。\n\n"
            "• 每个 cell 支持代码或 Markdown\n"
            "• `Shift+Enter` 运行并跳到下一个\n"
            "• 跨 cell 共享变量，自动持久化\n"
            "• 可导出 .mcnb 或 .ipynb"
        ),
    },
]


class QuickTour(QDialog):
    """功能导览对话框。"""

    def __init__(self, i18n, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self._index = 0

        self.setWindowTitle(i18n.t(
            "tour_title", "快速了解 MultiCalc"))
        self.resize(560, 420)
        self.setModal(True)

        self.icon_label = QLabel("")
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet(
            "font-size: 56pt; padding: 10px;")

        self.title_label = QLabel("")
        self.title_label.setAlignment(Qt.AlignCenter)
        tf = QFont()
        tf.setBold(True)
        tf.setPointSize(16)
        self.title_label.setFont(tf)
        self.title_label.setStyleSheet("padding: 4px;")

        self.body_label = QLabel("")
        self.body_label.setWordWrap(True)
        self.body_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse)
        self.body_label.setStyleSheet(
            "font-size: 10pt; color: #ccc;"
            " padding: 8px 4px; line-height: 1.5;")

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(16, 8, 16, 8)
        cl.addWidget(self.icon_label)
        cl.addWidget(self.title_label)
        cl.addWidget(self.body_label, 1)

        self.step_label = QLabel("")
        self.step_label.setAlignment(Qt.AlignCenter)
        self.step_label.setStyleSheet(
            "color: #888; font-size: 9pt;")

        self.b_skip = QPushButton(i18n.t("tour_skip", "跳过"))
        self.b_skip.clicked.connect(self._on_skip)
        self.b_prev = QPushButton(i18n.t("tour_prev", "上一步"))
        self.b_prev.clicked.connect(self._on_prev)
        self.b_next = QPushButton(i18n.t("tour_next", "下一步"))
        self.b_next.clicked.connect(self._on_next)
        self.b_next.setDefault(True)

        row = QHBoxLayout()
        row.addWidget(self.b_skip)
        row.addStretch(1)
        row.addWidget(self.b_prev)
        row.addWidget(self.b_next)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.addWidget(content, 1)
        lay.addWidget(self.step_label)
        lay.addLayout(row)

        self._update()

    def _update(self):
        step = _STEPS[self._index]
        self.icon_label.setText(step["icon"])
        self.title_label.setText(self.i18n.t(
            "tour_step_" + str(self._index) + "_title",
            step["title"]))
        self.body_label.setText(self.i18n.t(
            "tour_step_" + str(self._index) + "_body",
            step["body"]))
        self.step_label.setText(
            f"{self._index + 1} / {len(_STEPS)}")
        self.b_prev.setEnabled(self._index > 0)
        if self._index >= len(_STEPS) - 1:
            self.b_next.setText(self.i18n.t("tour_done", "完成"))
        else:
            self.b_next.setText(self.i18n.t("tour_next", "下一步"))

    def _on_prev(self):
        if self._index > 0:
            self._index -= 1
            self._update()

    def _on_next(self):
        if self._index >= len(_STEPS) - 1:
            self.accept()
            return
        self._index += 1
        self._update()

    def _on_skip(self):
        self.reject()

    @property
    def skipped(self) -> bool:
        return self.result() != QDialog.Accepted

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Right, Qt.Key_Down):
            self._on_next()
            return
        if key in (Qt.Key_Left, Qt.Key_Up):
            self._on_prev()
            return
        if key == Qt.Key_Escape:
            self._on_skip()
            return
        super().keyPressEvent(event)


# ===========================================================================
# 欢迎页
# ===========================================================================

class _QuickCard(QFrame):
    """一个快捷入口卡片。"""

    clicked = Signal()

    def __init__(self, icon: str, title: str, subtitle: str,
                 parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(80)
        self.setSizePolicy(QSizePolicy.Expanding,
                           QSizePolicy.Fixed)
        self.setStyleSheet(
            "_QuickCard {"
            "  background: rgba(128,128,128,0.08);"
            "  border: 1px solid rgba(128,128,128,0.25);"
            "  border-radius: 8px;"
            "}"
            "_QuickCard:hover {"
            "  background: rgba(128,128,128,0.16);"
            "  border-color: rgba(128,128,128,0.45);"
            "}")

        icon_label = QLabel(icon)
        icon_label.setStyleSheet(
            "font-size: 22pt; padding: 4px;")
        icon_label.setFixedWidth(48)
        icon_label.setAlignment(Qt.AlignCenter)

        title_label = QLabel(title)
        tf = QFont()
        tf.setBold(True)
        tf.setPointSize(11)
        title_label.setFont(tf)

        sub_label = QLabel(subtitle)
        sub_label.setStyleSheet("color: #888; font-size: 9pt;")
        sub_label.setWordWrap(True)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)
        text_col.addWidget(title_label)
        text_col.addWidget(sub_label)
        text_col.addStretch(1)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.addWidget(icon_label)
        lay.addLayout(text_col, 1)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class WelcomeWidget(QWidget):
    """欢迎页。"""

    quick_action = Signal(str, dict)
    panel_requested = Signal(str)
    recent_opened = Signal(str, str)

    def __init__(self, settings, i18n, base_path: str = "",
                 parent=None):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n
        self.base_path = base_path

        self.hello = QLabel(i18n.t(
            "welcome_hello", "👋 欢迎使用 MultiCalc"))
        hf = QFont()
        hf.setBold(True)
        hf.setPointSize(18)
        self.hello.setFont(hf)

        self.hello_sub = QLabel(i18n.t(
            "welcome_sub",
            "键盘驱动、随手可用的多功能计算器"))
        self.hello_sub.setStyleSheet(
            "color: #888; font-size: 11pt;")

        self._cards_layout = QGridLayout()
        self._cards_layout.setSpacing(8)
        self._build_quick_cards()

        self.recent_box = QVBoxLayout()
        self.recent_box.setSpacing(4)

        self.footer = QLabel(i18n.t(
            "welcome_footer",
            "提示：按 F1 查看所有快捷键；Ctrl+K 打开命令面板；"
            "设置里可以切换主题和语言。"))
        self.footer.setWordWrap(True)
        self.footer.setStyleSheet(
            "color: #777; padding: 8px; font-size: 9pt;")

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(24, 24, 24, 24)
        cl.setSpacing(14)
        cl.addWidget(self.hello)
        cl.addWidget(self.hello_sub)
        cl.addSpacing(6)
        cl.addWidget(self._section_label(i18n.t(
            "welcome_quick_start", "快速开始")))
        cl.addLayout(self._cards_layout)
        cl.addSpacing(6)
        cl.addWidget(self._section_label(i18n.t(
            "welcome_recent", "最近打开")))
        cl.addLayout(self.recent_box)
        cl.addStretch(1)
        cl.addWidget(self.footer)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(scroll)

        self._refresh_recent()

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        f = lbl.font()
        f.setBold(True)
        f.setPointSize(f.pointSize() + 1)
        lbl.setFont(f)
        lbl.setStyleSheet("padding-top: 6px;")
        return lbl

    def _build_quick_cards(self):
        cards = [
            ("🧮", "welcome_card_basic",
             "基础计算", "输入 2+3*4，立即得到结果",
             "basic"),
            ("🔬", "welcome_card_scientific",
             "科学计算", "求解方程、求导、积分",
             "scientific"),
            ("🔄", "welcome_card_unit",
             "单位换算", "1 km → m，100 USD → CNY",
             "unit"),
            ("🔐", "welcome_card_crypto",
             "加密工具", "AES / RSA / 文件加密 / PQC",
             "crypto_tools"),
            ("📓", "welcome_card_notebook",
             "数学笔记本", "多步推导，跨 cell 共享变量",
             "notebook"),
            ("🤖", "welcome_card_ai",
             "AI 助手", "自然语言 → 表达式，支持多轮",
             "ai"),
        ]
        for i, (icon, key, title, sub, panel) in enumerate(cards):
            card = _QuickCard(
                icon,
                self.i18n.t(key, title),
                self.i18n.t(key + "_sub", sub))
            card.clicked.connect(
                lambda _=False, p=panel:
                self.panel_requested.emit(p))
            self._cards_layout.addWidget(card, i // 2, i % 2)

    def _refresh_recent(self):
        while self.recent_box.count():
            item = self.recent_box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        try:
            items = ud.recent_list_existing(limit=6)
        except Exception as e:
            log_exc(e, module="WelcomeWidget._refresh_recent")
            items = []

        if not items:
            empty = QLabel(self.i18n.t(
                "welcome_no_recent",
                "还没有最近打开的文件。试试打开一个 .mcnb "
                "笔记本或导出历史。"))
            empty.setStyleSheet(
                "color: #666; padding: 8px; font-size: 10pt;")
            empty.setWordWrap(True)
            self.recent_box.addWidget(empty)
            return

        for it in items:
            btn = QPushButton(
                f"  {self._kind_icon(it.kind)}  "
                f"{it.display()}")
            btn.setStyleSheet(
                "QPushButton {"
                "  text-align: left;"
                "  background: rgba(128,128,128,0.06);"
                "  border: none;"
                "  border-radius: 4px;"
                "  padding: 6px 10px;"
                "  font-size: 10pt;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(128,128,128,0.18);"
                "}")
            btn.setToolTip(f"{it.path}\n{it.opened_at}")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(
                lambda _=False, p=it.path, k=it.kind:
                self.recent_opened.emit(p, k))
            self.recent_box.addWidget(btn)

    @staticmethod
    def _kind_icon(kind: str) -> str:
        return {
            "session": "📂",
            "notebook": "📓",
            "csv": "📊",
            "json": "📄",
            "enc": "🔒",
            "image": "🖼️",
            "other": "📄",
        }.get(str(kind or "").lower(), "📄")

    def refresh(self):
        self._refresh_recent()


# ===========================================================================
# 快捷键编辑器
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

        if sc.is_system_conflict(text):
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


class ShortcutEditor(QWidget):
    """快捷键编辑器。"""

    changed = Signal()

    def __init__(self, settings, i18n, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n

        self.search = QLineEdit()
        self.search.setPlaceholderText(
            i18n.t("shortcut_search_hint", "搜索命令…"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._on_search)

        self.preset_box = QComboBox()
        self.preset_box.addItem(
            i18n.t("shortcut_preset_custom", "（自定义）"),
            "custom")
        for p in sc.list_presets():
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

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([
            i18n.t("shortcut_col_command", "命令"),
            i18n.t("shortcut_col_keys", "快捷键"),
            i18n.t("shortcut_col_scope", "作用域"),
        ])
        self.tree.setColumnWidth(0, 300)
        self.tree.setColumnWidth(1, 220)
        self.tree.setColumnWidth(2, 80)
        self.tree.setSelectionMode(
            QAbstractItemView.SingleSelection)
        self.tree.itemDoubleClicked.connect(self._record_selected)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(
            self._show_context_menu)

        self.conflict_chk = QCheckBox(
            i18n.t("shortcut_warn_system",
                   "警告系统级冲突"))
        self.conflict_chk.setChecked(True)
        self.conflict_chk.stateChanged.connect(
            lambda _: self._refresh())

        b_record = QPushButton(
            i18n.t("shortcut_record", "录制…"))
        b_record.clicked.connect(self._record_selected)
        b_clear = QPushButton(i18n.t("shortcut_clear", "清除"))
        b_clear.clicked.connect(self._clear_selected)
        b_reset = QPushButton(i18n.t(
            "shortcut_reset_one", "恢复默认"))
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

    def _select_current_preset(self):
        name = sc.current_scheme_name()
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
        metas = sc.search(q) if q else sc.all_metas()

        conflicts = {}
        warn_sys = self.conflict_chk.isChecked()
        try:
            for c in sc.detect_conflicts(include_system=warn_sys):
                for cmd_id in c["commands"]:
                    conflicts.setdefault(cmd_id, []).append(c)
        except Exception as e:
            log_exc(e, module="ShortcutEditor._refresh.conflicts")

        groups = sc.list_groups()
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
            parent.setFlags(
                parent.flags() & ~Qt.ItemIsSelectable)
            self.tree.addTopLevelItem(parent)

            for m in items:
                key = sc.get(m.command_id)
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

    def _selected_command_id(self):
        items = self.tree.selectedItems()
        if not items:
            return None
        item = items[0]
        cmd_id = item.data(0, Qt.UserRole)
        return cmd_id if cmd_id else None

    def _record_selected(self, *_):
        cmd_id = self._selected_command_id()
        if cmd_id is None:
            return

        dlg = _RecordDialog(self.i18n, self)
        if dlg.exec() != QDialog.Accepted:
            return

        new_key = dlg.key_sequence

        if new_key:
            current = {
                m.command_id: sc.get(m.command_id)
                for m in sc.all_metas()
            }
            current[cmd_id] = new_key
            confs = sc.detect_conflicts(
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
                            (sc.get_meta(x).label
                             if sc.get_meta(x) else x)
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
            sc.set(cmd_id, new_key)
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
            sc.set(cmd_id, "")
            self._refresh()
            self.changed.emit()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _reset_selected(self):
        cmd_id = self._selected_command_id()
        if cmd_id is None:
            return
        try:
            sc.reset(cmd_id)
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
            sc.reset_to_default()
            self._select_current_preset()
            self._refresh()
            self.changed.emit()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _apply_preset(self):
        name = self.preset_box.currentData()
        if name == "custom":
            return
        try:
            info = sc.get_preset_info(name)
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

        if sc.apply_preset(name):
            self._refresh()
            self.changed.emit()

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.i18n.t("shortcut_export", "导出快捷键"),
            "shortcuts.json", "JSON (*.json)")
        if not path:
            return
        if sc.export_current(path):
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

        r = sc.import_from(path, merge=merge)
        if not r.get("ok"):
            QMessageBox.warning(
                self, "Error", r.get("error", "导入失败"))
            return

        msg = self.i18n.t(
            "shortcut_import_done",
            "导入完成：应用 {n} 项").format(n=r["applied"])

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

        chosen = menu.exec(
            self.tree.viewport().mapToGlobal(pos))
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
                QApplication.clipboard().setText(cmd_id)
            except Exception:
                pass