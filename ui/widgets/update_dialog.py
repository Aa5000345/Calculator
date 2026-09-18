"""更新对话框：检查 / 下载 / 提示重启。

用法（MainWindow）：
    dlg = UpdateDialog(settings, i18n, current_version, self)
    dlg.exec()
"""
from __future__ import annotations

import os
import subprocess
import sys

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QVBoxLayout, QWidget,
)

from core import updater as upd_mod
from core.logger import log_exc


# ===========================================================================
# Worker
# ===========================================================================

class _CheckWorker(QThread):
    done = Signal(object)     # UpdateInfo
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
    progress = Signal(int, int, float)     # done, total, speed
    done = Signal(object)                   # DownloadResult
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


# ===========================================================================
# 对话框
# ===========================================================================

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
        self._info: upd_mod.UpdateInfo | None = None

        self.setWindowTitle(i18n.t(
            "update_title", "检查更新"))
        self.resize(600, 480)

        # ---------------- 顶部信息 ----------------
        self.title = QLabel(i18n.t(
            "update_checking", "正在检查…"))
        f = self.title.font()
        f.setBold(True)
        f.setPointSize(f.pointSize() + 1)
        self.title.setFont(f)

        self.meta = QLabel("")
        self.meta.setStyleSheet("color: #888;")

        # ---------------- 发布说明 ----------------
        self.notes = QPlainTextEdit()
        self.notes.setReadOnly(True)
        self.notes.setPlaceholderText(
            i18n.t("update_notes_hint", "（无发布说明）"))

        # ---------------- 进度 ----------------
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        self.status = QLabel("")
        self.status.setStyleSheet("color: #888;")

        # ---------------- 按钮 ----------------
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

        # ---------------- 底部关闭 ----------------
        box = QDialogButtonBox(QDialogButtonBox.Close)
        box.button(QDialogButtonBox.Close).setText(
            i18n.t("close", "关闭"))
        box.rejected.connect(self.reject)

        # ---------------- 布局 ----------------
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

        # 自动开始检查
        self.start_check()

    # ==================================================================
    # 检查
    # ==================================================================

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

    def _on_check_done(self, info: upd_mod.UpdateInfo):
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

        self.title.setText(
            f"🎉 发现新版本：{info.latest}")
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

    # ==================================================================
    # 下载
    # ==================================================================

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
        self._download_worker.failed.connect(self._on_download_failed)
        self._download_worker.finished.connect(self._on_download_finished)
        self._download_worker.start()

    def _on_progress(self, done: int, total: int, speed: float):
        if total > 0:
            self.progress.setValue(min(100, int(done / total * 100)))
            mb_done = done / (1 << 20)
            mb_total = total / (1 << 20)
            speed_mb = speed / (1 << 20)
            self.status.setText(
                f"{mb_done:.1f} / {mb_total:.1f} MiB  "
                f"({speed_mb:.1f} MiB/s)")
        else:
            self.progress.setValue(0)
            self.status.setText(
                f"已下载 {done / (1 << 20):.1f} MiB")

    def _on_download_done(self, r: upd_mod.DownloadResult):
        if r.error:
            self._on_download_failed(r.error)
            return

        verified_text = (self.i18n.t("update_verified", "SHA256 已校验")
                         if r.verified
                         else self.i18n.t("update_not_verified",
                                          "未校验 SHA256"))

        self.status.setText(f"✓ {r.path}")
        self.title.setText(self.i18n.t(
            "update_download_done", "下载完成"))

        msg = (f"文件已下载到：\n{r.path}\n\n"
               f"大小：{r.size / (1 << 20):.2f} MiB\n"
               f"耗时：{r.elapsed:.1f}s\n"
               f"{verified_text}\n\n"
               f"请手动替换旧版本并重启。\n"
               f"是否现在打开所在文件夹？")

        ret = QMessageBox.question(
            self, self.i18n.t("update_download_done", "下载完成"),
            msg,
            QMessageBox.Yes | QMessageBox.No)
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

    # ==================================================================
    # 辅助
    # ==================================================================

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
        """打开文件所在目录（跨平台）。"""
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

    # ==================================================================

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