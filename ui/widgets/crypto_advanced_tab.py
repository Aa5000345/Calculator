"""高级加密 Tab：PQC + 其他常用算法 + 后端能力探测。

被 ui/panels/crypto_tools.py 作为 Tab 使用。
"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget, QCheckBox,
)

from core import crypto_advanced as ca
from core.logger import log_exc


class _CryptoWorker(QThread):
    """通用后台执行。"""
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            r = self._fn(*self._args, **self._kwargs)
            if not self._cancelled:
                self.done.emit(r)
        except Exception as e:  # noqa: BLE001
            if not self._cancelled:
                self.failed.emit(str(e))


class CryptoAdvancedTab(QWidget):
    """高级加密：PQC / ChaCha20 / Ed25519 / X25519 / Argon2 / Base58。"""

    def __init__(self, settings, i18n, history, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n
        self.history = history
        self._worker = None

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_backend_tab(), "后端能力")
        self.tabs.addTab(self._build_mlkem_tab(), "ML-KEM")
        self.tabs.addTab(self._build_mldsa_tab(), "ML-DSA")
        self.tabs.addTab(self._build_slhdsa_tab(), "SLH-DSA")
        self.tabs.addTab(self._build_chacha_tab(), "ChaCha20")
        self.tabs.addTab(self._build_ed25519_tab(), "Ed25519")
        self.tabs.addTab(self._build_x25519_tab(), "X25519")
        self.tabs.addTab(self._build_argon2_tab(), "Argon2/bcrypt")
        self.tabs.addTab(self._build_encoding_tab(), "编码")

        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)
        self.result.setMaximumHeight(200)

        main = QVBoxLayout(self)
        main.addWidget(self.tabs, 1)
        main.addWidget(QLabel(self.i18n.t("result", "结果")))
        main.addWidget(self.result)

    # ==================================================================
    # 后端能力
    # ==================================================================

    def _build_backend_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        b = QPushButton("刷新后端能力")
        b.clicked.connect(self._refresh_backend)
        self.backend_out = QPlainTextEdit()
        self.backend_out.setReadOnly(True)
        v.addWidget(b)
        v.addWidget(self.backend_out, 1)
        self._refresh_backend()
        return w

    def _refresh_backend(self):
        try:
            info = ca.backend_info(force=True)
            text = json.dumps(info.to_dict(),
                              ensure_ascii=False, indent=2)
            self.backend_out.setPlainText(text)
        except Exception as e:
            self.backend_out.setPlainText(f"✗ {e}")

    # ==================================================================
    # ML-KEM
    # ==================================================================

    def _build_mlkem_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.mlkem_level = QComboBox()
        for lv in ("ML-KEM-512", "ML-KEM-768", "ML-KEM-1024"):
            self.mlkem_level.addItem(lv, lv)
        self.mlkem_level.setCurrentIndex(1)

        b_gen = QPushButton("生成密钥对")
        b_gen.clicked.connect(self._mlkem_gen)

        self.mlkem_pk = QPlainTextEdit(); self.mlkem_pk.setFixedHeight(60)
        self.mlkem_sk = QPlainTextEdit(); self.mlkem_sk.setFixedHeight(60)
        self.mlkem_ct = QPlainTextEdit(); self.mlkem_ct.setFixedHeight(60)

        b_enc = QPushButton("封装（加密密钥）")
        b_enc.clicked.connect(self._mlkem_enc)
        b_dec = QPushButton("解封装（解密密钥）")
        b_dec.clicked.connect(self._mlkem_dec)

        f = QFormLayout()
        f.addRow(QLabel("安全级别"), self.mlkem_level)
        f.addRow(b_gen)
        f.addRow(QLabel("公钥 (hex)"), self.mlkem_pk)
        f.addRow(QLabel("私钥 (hex)"), self.mlkem_sk)
        f.addRow(QLabel("密文 (hex)"), self.mlkem_ct)
        row = QHBoxLayout()
        row.addWidget(b_enc)
        row.addWidget(b_dec)
        f.addRow(row)
        v.addLayout(f)
        v.addStretch(1)
        return w

    def _mlkem_gen(self):
        self._run_async(
            ca.mlkem_generate, self.mlkem_level.currentData(),
            on_done=self._on_mlkem_gen)

    def _on_mlkem_gen(self, r):
        self.mlkem_pk.setPlainText(r["public_key"])
        self.mlkem_sk.setPlainText(r["private_key"])
        self._show(r)

    def _mlkem_enc(self):
        self._run_async(
            ca.mlkem_encapsulate,
            self.mlkem_level.currentData(),
            self.mlkem_pk.toPlainText().strip(),
            on_done=lambda r: (
                self.mlkem_ct.setPlainText(r["ciphertext"]),
                self._show(r)))

    def _mlkem_dec(self):
        self._run_async(
            ca.mlkem_decapsulate,
            self.mlkem_level.currentData(),
            self.mlkem_sk.toPlainText().strip(),
            self.mlkem_ct.toPlainText().strip(),
            on_done=self._show)

    # ==================================================================
    # ML-DSA
    # ==================================================================

    def _build_mldsa_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.mldsa_level = QComboBox()
        for lv in ("ML-DSA-44", "ML-DSA-65", "ML-DSA-87"):
            self.mldsa_level.addItem(lv, lv)
        self.mldsa_level.setCurrentIndex(1)

        b_gen = QPushButton("生成密钥对")
        b_gen.clicked.connect(self._mldsa_gen)

        self.mldsa_pk = QPlainTextEdit(); self.mldsa_pk.setFixedHeight(60)
        self.mldsa_sk = QPlainTextEdit(); self.mldsa_sk.setFixedHeight(60)
        self.mldsa_msg = QPlainTextEdit("Hello, post-quantum!")
        self.mldsa_msg.setFixedHeight(60)
        self.mldsa_sig = QPlainTextEdit(); self.mldsa_sig.setFixedHeight(60)

        b_sign = QPushButton("签名")
        b_sign.clicked.connect(self._mldsa_sign)
        b_verify = QPushButton("验证")
        b_verify.clicked.connect(self._mldsa_verify)

        f = QFormLayout()
        f.addRow(QLabel("安全级别"), self.mldsa_level)
        f.addRow(b_gen)
        f.addRow(QLabel("公钥"), self.mldsa_pk)
        f.addRow(QLabel("私钥"), self.mldsa_sk)
        f.addRow(QLabel("消息"), self.mldsa_msg)
        f.addRow(QLabel("签名"), self.mldsa_sig)
        row = QHBoxLayout()
        row.addWidget(b_sign)
        row.addWidget(b_verify)
        f.addRow(row)
        v.addLayout(f)
        v.addStretch(1)
        return w

    def _mldsa_gen(self):
        self._run_async(
            ca.mldsa_generate, self.mldsa_level.currentData(),
            on_done=self._on_mldsa_gen)

    def _on_mldsa_gen(self, r):
        self.mldsa_pk.setPlainText(r["public_key"])
        self.mldsa_sk.setPlainText(r["private_key"])
        self._show(r)

    def _mldsa_sign(self):
        self._run_async(
            ca.mldsa_sign, self.mldsa_level.currentData(),
            self.mldsa_sk.toPlainText().strip(),
            self.mldsa_msg.toPlainText(),
            on_done=lambda r: (
                self.mldsa_sig.setPlainText(r["signature"]),
                self._show(r)))

    def _mldsa_verify(self):
        self._run_async(
            ca.mldsa_verify, self.mldsa_level.currentData(),
            self.mldsa_pk.toPlainText().strip(),
            self.mldsa_msg.toPlainText(),
            self.mldsa_sig.toPlainText().strip(),
            on_done=self._show)

    # ==================================================================
    # SLH-DSA
    # ==================================================================

    def _build_slhdsa_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.slh_level = QComboBox()
        for lv in ("SLH-DSA-SHA2-128s", "SLH-DSA-SHA2-128f",
                   "SLH-DSA-SHAKE-128s", "SLH-DSA-SHAKE-128f"):
            self.slh_level.addItem(lv, lv)
        b_gen = QPushButton("生成密钥对")
        b_gen.clicked.connect(self._slh_gen)
        self.slh_pk = QPlainTextEdit(); self.slh_pk.setFixedHeight(60)
        self.slh_sk = QPlainTextEdit(); self.slh_sk.setFixedHeight(60)
        self.slh_msg = QPlainTextEdit("Hello, SLH-DSA!")
        self.slh_msg.setFixedHeight(60)
        self.slh_sig = QPlainTextEdit(); self.slh_sig.setFixedHeight(60)
        b_sign = QPushButton("签名"); b_sign.clicked.connect(self._slh_sign)
        b_v = QPushButton("验证"); b_v.clicked.connect(self._slh_verify)

        f = QFormLayout()
        f.addRow(QLabel("参数集"), self.slh_level)
        f.addRow(b_gen)
        f.addRow(QLabel("公钥"), self.slh_pk)
        f.addRow(QLabel("私钥"), self.slh_sk)
        f.addRow(QLabel("消息"), self.slh_msg)
        f.addRow(QLabel("签名"), self.slh_sig)
        row = QHBoxLayout()
        row.addWidget(b_sign); row.addWidget(b_v)
        f.addRow(row)
        v.addLayout(f); v.addStretch(1)
        return w

    def _slh_gen(self):
        self._run_async(
            ca.slhdsa_generate, self.slh_level.currentData(),
            on_done=lambda r: (
                self.slh_pk.setPlainText(r["public_key"]),
                self.slh_sk.setPlainText(r["private_key"]),
                self._show(r)))

    def _slh_sign(self):
        self._run_async(
            ca.slhdsa_sign, self.slh_level.currentData(),
            self.slh_sk.toPlainText().strip(),
            self.slh_msg.toPlainText(),
            on_done=lambda r: (
                self.slh_sig.setPlainText(r["signature"]),
                self._show(r)))

    def _slh_verify(self):
        self._run_async(
            ca.slhdsa_verify, self.slh_level.currentData(),
            self.slh_pk.toPlainText().strip(),
            self.slh_msg.toPlainText(),
            self.slh_sig.toPlainText().strip(),
            on_done=self._show)

    # ==================================================================
    # ChaCha20
    # ==================================================================

    def _build_chacha_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.ch_plain = QPlainTextEdit("Secret message")
        self.ch_plain.setFixedHeight(70)
        self.ch_key = QLineEdit(ca.chacha20_gen_key())
        self.ch_aad = QLineEdit("")
        self.ch_ct = QPlainTextEdit(""); self.ch_ct.setFixedHeight(70)
        b_gen = QPushButton("生成密钥")
        b_gen.clicked.connect(
            lambda: self.ch_key.setText(ca.chacha20_gen_key()))
        b_enc = QPushButton("加密")
        b_enc.clicked.connect(self._ch_enc)
        b_dec = QPushButton("解密")
        b_dec.clicked.connect(self._ch_dec)

        f = QFormLayout()
        f.addRow(QLabel("密钥 (hex)"), self.ch_key)
        f.addRow(QLabel("AAD (可选)"), self.ch_aad)
        f.addRow(QLabel("明文"), self.ch_plain)
        f.addRow(QLabel("密文 (combined)"), self.ch_ct)
        row = QHBoxLayout()
        for b in (b_gen, b_enc, b_dec): row.addWidget(b)
        f.addRow(row)
        v.addLayout(f); v.addStretch(1)
        return w

    def _ch_enc(self):
        self._run_async(
            ca.chacha20_encrypt,
            self.ch_plain.toPlainText(),
            self.ch_key.text().strip(),
            self.ch_aad.text(),
            on_done=lambda r: (
                self.ch_ct.setPlainText(r["combined"]),
                self._show(r)))

    def _ch_dec(self):
        self._run_async(
            ca.chacha20_decrypt,
            self.ch_ct.toPlainText().strip(),
            self.ch_key.text().strip(),
            self.ch_aad.text(),
            on_done=lambda r: (
                self.ch_plain.setPlainText(r),
                self._show({"plaintext": r})))

    # ==================================================================
    # Ed25519
    # ==================================================================

    def _build_ed25519_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.ed_pk = QPlainTextEdit(); self.ed_pk.setFixedHeight(60)
        self.ed_sk = QPlainTextEdit(); self.ed_sk.setFixedHeight(60)
        self.ed_msg = QPlainTextEdit("Hello Ed25519")
        self.ed_msg.setFixedHeight(60)
        self.ed_sig = QPlainTextEdit(); self.ed_sig.setFixedHeight(60)
        b_gen = QPushButton("生成密钥")
        b_gen.clicked.connect(
            lambda: self._run_async(
                ca.ed25519_generate, on_done=self._on_ed_gen))
        b_sign = QPushButton("签名")
        b_sign.clicked.connect(self._ed_sign)
        b_verify = QPushButton("验证")
        b_verify.clicked.connect(self._ed_verify)
        f = QFormLayout()
        f.addRow(b_gen)
        f.addRow(QLabel("公钥 hex"), self.ed_pk)
        f.addRow(QLabel("私钥 hex"), self.ed_sk)
        f.addRow(QLabel("消息"), self.ed_msg)
        f.addRow(QLabel("签名"), self.ed_sig)
        row = QHBoxLayout()
        row.addWidget(b_sign); row.addWidget(b_verify)
        f.addRow(row)
        v.addLayout(f); v.addStretch(1)
        return w

    def _on_ed_gen(self, r):
        self.ed_pk.setPlainText(r["public_hex"])
        self.ed_sk.setPlainText(r["private_hex"])
        self._show(r)

    def _ed_sign(self):
        self._run_async(
            ca.ed25519_sign,
            self.ed_sk.toPlainText().strip(),
            self.ed_msg.toPlainText(),
            on_done=lambda r: (
                self.ed_sig.setPlainText(r["signature"]),
                self._show(r)))

    def _ed_verify(self):
        self._run_async(
            ca.ed25519_verify,
            self.ed_pk.toPlainText().strip(),
            self.ed_msg.toPlainText(),
            self.ed_sig.toPlainText().strip(),
            on_done=self._show)

    # ==================================================================
    # X25519
    # ==================================================================

    def _build_x25519_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.x_a_priv = QLineEdit()
        self.x_a_pub = QLineEdit()
        self.x_b_priv = QLineEdit()
        self.x_b_pub = QLineEdit()
        b_gen = QPushButton("生成双方密钥")
        b_gen.clicked.connect(self._x_gen)
        b_shared = QPushButton("计算共享密钥")
        b_shared.clicked.connect(self._x_shared)

        f = QFormLayout()
        f.addRow(QLabel("A 私钥"), self.x_a_priv)
        f.addRow(QLabel("A 公钥"), self.x_a_pub)
        f.addRow(QLabel("B 私钥"), self.x_b_priv)
        f.addRow(QLabel("B 公钥"), self.x_b_pub)
        f.addRow(b_gen)
        f.addRow(b_shared)
        v.addLayout(f); v.addStretch(1)
        return w

    def _x_gen(self):
        def _do():
            a = ca.x25519_generate()
            b = ca.x25519_generate()
            return {"a": a, "b": b}

        def _done(r):
            self.x_a_priv.setText(r["a"]["private_hex"])
            self.x_a_pub.setText(r["a"]["public_hex"])
            self.x_b_priv.setText(r["b"]["private_hex"])
            self.x_b_pub.setText(r["b"]["public_hex"])
            self._show(r)

        self._run_async(_do, on_done=_done)

    def _x_shared(self):
        def _do():
            s_ab = ca.x25519_shared(
                self.x_a_priv.text().strip(),
                self.x_b_pub.text().strip())
            s_ba = ca.x25519_shared(
                self.x_b_priv.text().strip(),
                self.x_a_pub.text().strip())
            return {"ab": s_ab, "ba": s_ba,
                    "match": s_ab["shared_secret"] == s_ba["shared_secret"]}

        self._run_async(_do, on_done=self._show)

    # ==================================================================
    # Argon2 / bcrypt
    # ==================================================================

    def _build_argon2_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.pw_input = QLineEdit("my_strong_password")
        self.pw_input.setEchoMode(QLineEdit.Password)
        self.argon_time = QSpinBox(); self.argon_time.setRange(1, 10)
        self.argon_time.setValue(3)
        self.argon_mem = QSpinBox(); self.argon_mem.setRange(8, 1024)
        self.argon_mem.setValue(64)
        self.argon_par = QSpinBox(); self.argon_par.setRange(1, 16)
        self.argon_par.setValue(4)
        b_a2 = QPushButton("Argon2id 哈希")
        b_a2.clicked.connect(self._argon2)
        b_bc = QPushButton("bcrypt 哈希")
        b_bc.clicked.connect(self._bcrypt)
        self.pw_out = QPlainTextEdit(); self.pw_out.setReadOnly(True)
        b_verify = QPushButton("验证（对上一条结果）")
        b_verify.clicked.connect(self._pw_verify)

        f = QFormLayout()
        f.addRow(QLabel("密码"), self.pw_input)
        f.addRow(QLabel("Argon2 time"), self.argon_time)
        f.addRow(QLabel("Argon2 mem (MiB)"), self.argon_mem)
        f.addRow(QLabel("Argon2 par"), self.argon_par)
        row = QHBoxLayout()
        row.addWidget(b_a2); row.addWidget(b_bc)
        f.addRow(row)
        f.addRow(QLabel("哈希结果"), self.pw_out)
        f.addRow(b_verify)
        v.addLayout(f); v.addStretch(1)
        return w

    def _argon2(self):
        self._run_async(
            ca.argon2_hash,
            self.pw_input.text(),
            time_cost=self.argon_time.value(),
            memory_cost=self.argon_mem.value() * 1024,
            parallelism=self.argon_par.value(),
            on_done=lambda r: (
                self.pw_out.setPlainText(r["hash"]),
                self._show(r)))

    def _bcrypt(self):
        self._run_async(
            ca.bcrypt_hash, self.pw_input.text(),
            on_done=lambda r: (
                self.pw_out.setPlainText(r["hash"]),
                self._show(r)))

    def _pw_verify(self):
        h = self.pw_out.toPlainText().strip()
        if not h:
            return
        if h.startswith("$argon2"):
            fn = ca.argon2_verify
        else:
            fn = ca.bcrypt_verify
        self._run_async(
            fn, self.pw_input.text(), h, on_done=self._show)

    # ==================================================================
    # 编码
    # ==================================================================

    def _build_encoding_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.enc_input = QPlainTextEdit("Hello, 世界")
        self.enc_input.setFixedHeight(80)
        self.enc_kind = QComboBox()
        for k in ("base58", "base32", "base85", "ascii85"):
            self.enc_kind.addItem(k, k)
        b_enc = QPushButton("编码")
        b_enc.clicked.connect(self._do_encode)
        b_dec = QPushButton("解码")
        b_dec.clicked.connect(self._do_decode)
        f = QFormLayout()
        f.addRow(QLabel("输入"), self.enc_input)
        f.addRow(QLabel("类型"), self.enc_kind)
        row = QHBoxLayout()
        row.addWidget(b_enc); row.addWidget(b_dec)
        f.addRow(row)
        v.addLayout(f); v.addStretch(1)
        return w

    def _do_encode(self):
        k = self.enc_kind.currentData()
        fn = {
            "base58": ca.base58_encode,
            "base32": ca.base32_encode,
            "base85": ca.base85_encode,
            "ascii85": ca.ascii85_encode,
        }[k]
        self._run_async(
            fn, self.enc_input.toPlainText(),
            on_done=lambda r: self._show({"encoded": r}))

    def _do_decode(self):
        k = self.enc_kind.currentData()
        fn = {
            "base58": ca.base58_decode,
            "base32": ca.base32_decode,
            "base85": ca.base85_decode,
            "ascii85": ca.ascii85_decode,
        }[k]
        self._run_async(
            fn, self.enc_input.toPlainText().strip(),
            on_done=lambda r: self._show({"decoded": r}))

    # ==================================================================
    # 通用
    # ==================================================================

    def _show(self, r):
        try:
            if isinstance(r, dict):
                text = json.dumps(r, ensure_ascii=False,
                                  indent=2, default=str)
            else:
                text = str(r)
            self.result.setPlainText(text)
            if self.history is not None:
                try:
                    self.history.add(
                        "crypto-advanced", "op",
                        text[:500])
                except Exception:
                    pass
        except Exception as e:
            log_exc(e, module="CryptoAdvancedTab._show")

    def _run_async(self, fn, *args, on_done=None, **kwargs):
        if self._worker is not None and self._worker.isRunning():
            return
        w = _CryptoWorker(fn, *args, **kwargs)
        if on_done:
            w.done.connect(on_done)
        w.failed.connect(
            lambda msg: self.result.setPlainText(f"✗ {msg}"))
        w.finished.connect(lambda: setattr(self, "_worker", None))
        self._worker = w
        w.start()

    def closeEvent(self, e):
        try:
            if self._worker is not None and self._worker.isRunning():
                self._worker.cancel()
                self._worker.wait(2000)
        except Exception:
            pass
        super().closeEvent(e)