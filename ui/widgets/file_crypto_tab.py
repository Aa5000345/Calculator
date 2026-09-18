"""文件加密 Tab v2：支持 AES-GCM / ChaCha20 + PBKDF2 / Scrypt / Argon2id。

被 ui/panels/crypto_tools.py 作为 Tab 使用。
"""
from __future__ import annotations

import json
import os

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from core import file_crypto as fc
from core.logger import log_exc


class _FileCryptoWorker(QThread):
    progress = Signal(int, int, str)
    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, op: str, *args, **kwargs):
        super().__init__()
        self._op = op
        self._args = args
        self._kwargs = kwargs
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            fn = (fc.encrypt_file if self._op == "encrypt"
                  else fc.decrypt_file)

            def _prog(p):
                self.progress.emit(int(p.done), int(p.total), p.stage)

            def _cancel():
                return self._cancelled

            r = fn(
                *self._args,
                progress_cb=_prog,
                cancelled=_cancel,
                **self._kwargs)
            if not self._cancelled:
                self.done.emit(r if isinstance(r, dict) else {})
        except Exception as e:  # noqa: BLE001
            if not self._cancelled:
                self.failed.emit(str(e))


class FileCryptoTab(QWidget):
    """文件加密 / 解密 / 信息。"""

    def __init__(self, settings, i18n, history, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n
        self.history = history
        self._worker: _FileCryptoWorker | None = None

        self.sub_tabs = QTabWidget()
        self.sub_tabs.addTab(self._build_encrypt_tab(),
                             i18n.t("crypto_file_encrypt", "加密"))
        self.sub_tabs.addTab(self._build_decrypt_tab(),
                             i18n.t("crypto_file_decrypt", "解密"))
        self.sub_tabs.addTab(self._build_info_tab(),
                             i18n.t("crypto_file_info", "文件信息"))

        self.status = QLabel("")
        self.status.setStyleSheet("color: #888;")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)

        lay = QVBoxLayout(self)
        lay.addWidget(self.sub_tabs, 1)
        lay.addWidget(self.progress)
        lay.addWidget(self.status)

    # ==================================================================
    # 加密
    # ==================================================================

    def _build_encrypt_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.enc_in = QLineEdit()
        b_in = QPushButton("…")
        b_in.setFixedWidth(30)
        b_in.clicked.connect(
            lambda: self._pick_file(self.enc_in, "open"))
        row_in = QHBoxLayout()
        row_in.addWidget(self.enc_in, 1)
        row_in.addWidget(b_in)

        self.enc_out = QLineEdit()
        b_out = QPushButton("…")
        b_out.setFixedWidth(30)
        b_out.clicked.connect(
            lambda: self._pick_file(self.enc_out, "save_enc"))
        row_out = QHBoxLayout()
        row_out.addWidget(self.enc_out, 1)
        row_out.addWidget(b_out)

        self.enc_pw = QLineEdit()
        self.enc_pw.setEchoMode(QLineEdit.Password)
        self.enc_pw2 = QLineEdit()
        self.enc_pw2.setEchoMode(QLineEdit.Password)

        self.enc_cipher = QComboBox()
        self.enc_cipher.addItem("AES-256-GCM (推荐)", "aes-gcm")
        self.enc_cipher.addItem("ChaCha20-Poly1305", "chacha20")

        self.enc_kdf = QComboBox()
        self.enc_kdf.addItem("PBKDF2-HMAC-SHA256", "pbkdf2")
        self.enc_kdf.addItem("Scrypt (更强但更慢)", "scrypt")
        self.enc_kdf.addItem("Argon2id (推荐)", "argon2id")

        self.enc_iter = QSpinBox()
        self.enc_iter.setRange(10_000, 10_000_000)
        self.enc_iter.setSingleStep(50_000)
        self.enc_iter.setValue(fc.DEFAULT_PBKDF2_ITERATIONS)

        self.enc_chunk = QComboBox()
        for label, size in (("256 KiB", 1 << 18),
                            ("1 MiB（默认）", 1 << 20),
                            ("4 MiB", 1 << 22),
                            ("16 MiB", 1 << 24)):
            self.enc_chunk.addItem(label, size)
        self.enc_chunk.setCurrentIndex(1)

        self.enc_show_pw = QCheckBox("显示密码")
        self.enc_show_pw.stateChanged.connect(
            lambda s: self.enc_pw.setEchoMode(
                QLineEdit.Normal if s else QLineEdit.Password))

        form = QFormLayout()
        form.addRow(QLabel("源文件"), row_in)
        form.addRow(QLabel("输出文件"), row_out)
        form.addRow(QLabel("加密算法"), self.enc_cipher)
        form.addRow(QLabel("密码"), self.enc_pw)
        form.addRow(QLabel("确认密码"), self.enc_pw2)
        form.addRow(QLabel(""), self.enc_show_pw)
        form.addRow(QLabel("KDF"), self.enc_kdf)
        form.addRow(QLabel("迭代次数"), self.enc_iter)
        form.addRow(QLabel("分块大小"), self.enc_chunk)

        self.enc_start = QPushButton("开始加密")
        self.enc_start.setMinimumHeight(34)
        self.enc_start.clicked.connect(self._do_encrypt)
        self.enc_cancel = QPushButton("取消")
        self.enc_cancel.setEnabled(False)
        self.enc_cancel.clicked.connect(self._cancel)

        row_btn = QHBoxLayout()
        row_btn.addWidget(self.enc_start, 1)
        row_btn.addWidget(self.enc_cancel)

        v.addLayout(form)
        v.addLayout(row_btn)
        v.addStretch(1)
        return w

    # ==================================================================
    # 解密
    # ==================================================================

    def _build_decrypt_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.dec_in = QLineEdit()
        b_in = QPushButton("…")
        b_in.setFixedWidth(30)
        b_in.clicked.connect(
            lambda: self._pick_file(self.dec_in, "open_enc"))
        row_in = QHBoxLayout()
        row_in.addWidget(self.dec_in, 1)
        row_in.addWidget(b_in)

        self.dec_out = QLineEdit()
        b_out = QPushButton("…")
        b_out.setFixedWidth(30)
        b_out.clicked.connect(
            lambda: self._pick_file(self.dec_out, "save"))
        row_out = QHBoxLayout()
        row_out.addWidget(self.dec_out, 1)
        row_out.addWidget(b_out)

        self.dec_pw = QLineEdit()
        self.dec_pw.setEchoMode(QLineEdit.Password)
        self.dec_show_pw = QCheckBox("显示密码")
        self.dec_show_pw.stateChanged.connect(
            lambda s: self.dec_pw.setEchoMode(
                QLineEdit.Normal if s else QLineEdit.Password))

        form = QFormLayout()
        form.addRow(QLabel("加密文件"), row_in)
        form.addRow(QLabel("输出文件"), row_out)
        form.addRow(QLabel("密码"), self.dec_pw)
        form.addRow(QLabel(""), self.dec_show_pw)

        self.dec_start = QPushButton("开始解密")
        self.dec_start.setMinimumHeight(34)
        self.dec_start.clicked.connect(self._do_decrypt)
        self.dec_cancel = QPushButton("取消")
        self.dec_cancel.setEnabled(False)
        self.dec_cancel.clicked.connect(self._cancel)

        row_btn = QHBoxLayout()
        row_btn.addWidget(self.dec_start, 1)
        row_btn.addWidget(self.dec_cancel)

        v.addLayout(form)
        v.addLayout(row_btn)
        v.addStretch(1)
        return w

    # ==================================================================
    # 信息
    # ==================================================================

    def _build_info_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.info_path = QLineEdit()
        b_in = QPushButton("…")
        b_in.setFixedWidth(30)
        b_in.clicked.connect(
            lambda: self._pick_file(self.info_path, "open_enc"))
        row = QHBoxLayout()
        row.addWidget(self.info_path, 1)
        row.addWidget(b_in)
        b_read = QPushButton("读取文件头")
        b_read.clicked.connect(self._do_info)
        self.info_out = QPlainTextEdit()
        self.info_out.setReadOnly(True)
        v.addWidget(QLabel("加密文件"))
        v.addLayout(row)
        v.addWidget(b_read)
        v.addWidget(self.info_out, 1)
        return w

    # ==================================================================

    def _pick_file(self, line_edit, mode: str):
        if mode == "open":
            p, _ = QFileDialog.getOpenFileName(
                self, "选择文件", "", "All Files (*)")
        elif mode == "open_enc":
            p, _ = QFileDialog.getOpenFileName(
                self, "选择加密文件", "",
                "MultiCalc 加密 (*.mcenc);;All Files (*)")
        elif mode == "save_enc":
            p, _ = QFileDialog.getSaveFileName(
                self, "保存为", "encrypted.mcenc",
                "MultiCalc 加密 (*.mcenc)")
        else:
            p, _ = QFileDialog.getSaveFileName(
                self, "保存为", "", "All Files (*)")
        if p:
            line_edit.setText(p)

    def _set_busy(self, busy: bool):
        self.progress.setVisible(busy)
        if busy:
            self.progress.setValue(0)
        self.enc_start.setEnabled(not busy)
        self.dec_start.setEnabled(not busy)
        self.enc_cancel.setEnabled(busy)
        self.dec_cancel.setEnabled(busy)

    def _cancel(self):
        if self._worker is not None:
            self._worker.cancel()

    # ==================================================================
    # 加密 / 解密
    # ==================================================================

    def _do_encrypt(self):
        in_path = self.enc_in.text().strip()
        out_path = self.enc_out.text().strip()
        pw = self.enc_pw.text()
        pw2 = self.enc_pw2.text()
        if not in_path or not os.path.isfile(in_path):
            QMessageBox.warning(self, "Error", "请选择有效的源文件")
            return
        if not out_path:
            QMessageBox.warning(self, "Error", "请填写输出文件")
            return
        if not pw:
            QMessageBox.warning(self, "Error", "密码不能为空")
            return
        if pw != pw2:
            QMessageBox.warning(self, "Error", "两次密码不一致")
            return
        if self._worker is not None and self._worker.isRunning():
            return

        self._set_busy(True)
        self.status.setText("正在派生密钥…")

        self._worker = _FileCryptoWorker(
            "encrypt", in_path, out_path, pw,
            cipher=self.enc_cipher.currentData(),
            kdf=self.enc_kdf.currentData(),
            iterations=self.enc_iter.value(),
            chunk_size=self.enc_chunk.currentData(),
            parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_enc_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_enc_done(self, r: dict):
        try:
            size = r.get("size", 0)
            elapsed = r.get("elapsed", 0)
            cipher = r.get("cipher", "?")
            msg = (f"✓ 加密完成\n"
                   f"算法：{cipher}\n"
                   f"输出：{r.get('out')}\n"
                   f"原始大小：{size:,} 字节\n"
                   f"耗时：{elapsed:.2f}s")
            self.status.setText(msg.split("\n")[0])
            QMessageBox.information(self, "OK", msg)
            self._add_history(
                f"encrypt {os.path.basename(r.get('in',''))}",
                f"{size} bytes, {cipher}")
        except Exception as e:
            log_exc(e, module="FileCryptoTab._on_enc_done")

    def _do_decrypt(self):
        in_path = self.dec_in.text().strip()
        out_path = self.dec_out.text().strip()
        pw = self.dec_pw.text()
        if not in_path or not os.path.isfile(in_path):
            QMessageBox.warning(self, "Error", "请选择加密文件")
            return
        if not out_path:
            QMessageBox.warning(self, "Error", "请填写输出文件")
            return
        if not pw:
            QMessageBox.warning(self, "Error", "密码不能为空")
            return
        if self._worker is not None and self._worker.isRunning():
            return

        self._set_busy(True)
        self.status.setText("正在派生密钥…")

        self._worker = _FileCryptoWorker(
            "decrypt", in_path, out_path, pw, parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_dec_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_dec_done(self, r: dict):
        try:
            size = r.get("size", 0)
            elapsed = r.get("elapsed", 0)
            fmt = r.get("format", "?")
            msg = (f"✓ 解密完成\n"
                   f"格式：{fmt}\n"
                   f"输出：{r.get('out')}\n"
                   f"明文大小：{size:,} 字节\n"
                   f"耗时：{elapsed:.2f}s")
            self.status.setText(msg.split("\n")[0])
            QMessageBox.information(self, "OK", msg)
            self._add_history(
                f"decrypt {os.path.basename(r.get('in',''))}",
                f"{size} bytes, format {fmt}")
        except Exception as e:
            log_exc(e, module="FileCryptoTab._on_dec_done")

    # ==================================================================

    def _do_info(self):
        path = self.info_path.text().strip()
        if not path or not os.path.isfile(path):
            self.info_out.setPlainText("请选择有效的加密文件")
            return
        try:
            info = fc.get_file_info(path)
            self.info_out.setPlainText(
                json.dumps(info, ensure_ascii=False, indent=2))
            self.status.setText("✓ 读取成功")
        except Exception as e:
            self.info_out.setPlainText(f"✗ {e}")
            self.status.setText("✗ 读取失败")

    def _on_progress(self, done: int, total: int, stage: str):
        try:
            if total > 0:
                pct = min(100, int(done / total * 100))
                self.progress.setValue(pct)
                mb_done = done / (1 << 20)
                mb_total = total / (1 << 20)
                self.status.setText(
                    f"{stage}: {mb_done:.1f} / {mb_total:.1f} MiB "
                    f"({pct}%)")
            else:
                self.progress.setValue(0)
                self.status.setText(stage)
        except Exception:
            pass

    def _on_failed(self, msg: str):
        self.status.setText(f"✗ {msg}")
        QMessageBox.warning(self, "Error", msg)

    def _on_finished(self):
        self._set_busy(False)
        self._worker = None

    def _add_history(self, expr: str, result: str):
        if self.history is None:
            return
        try:
            self.history.add("crypto-file", expr, result)
        except Exception:
            pass

    def closeEvent(self, e):
        try:
            if self._worker is not None and self._worker.isRunning():
                self._worker.cancel()
                self._worker.wait(2000)
        except Exception:
            pass
        super().closeEvent(e)