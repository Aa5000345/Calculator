"""加密工具面板：编码 / 经典密码 / 哈希-HMAC / AES / RSA / TOTP /
密码强度 / 文件加密 / 高级加密（PQC）。

变更历史：
- 第 3 轮：primary_input / push_undo / Ctrl+Z
- 第 6.5 轮：新增「文件加密」Tab（FileCryptoTab）
- 第 8 轮：新增「高级加密」Tab（CryptoAdvancedTab），含 PQC
"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QFormLayout, QComboBox, QSpinBox, QCheckBox,
    QTabWidget, QWidget,
)

from core import crypto_tools as ct
from core.logger import log_exc
from ._common import friendly_error
from .base import CalcPanel


class CryptoPanel(CalcPanel):
    module_key = "crypto_tools"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)

        tabs = QTabWidget()
        tabs.addTab(self._build_encode_tab(),
                    i18n.t("crypto_encode", "Encode"))
        tabs.addTab(self._build_classic_tab(),
                    i18n.t("crypto_classic", "Classic"))
        tabs.addTab(self._build_hash_tab(),
                    i18n.t("crypto_hash", "Hash / HMAC"))
        tabs.addTab(self._build_aes_tab(),
                    i18n.t("crypto_aes", "AES"))
        tabs.addTab(self._build_rsa_tab(),
                    i18n.t("crypto_rsa", "RSA"))
        tabs.addTab(self._build_otp_tab(),
                    i18n.t("crypto_otp", "TOTP"))
        tabs.addTab(self._build_pw_tab(),
                    i18n.t("crypto_pw", "Password"))

        # 第 6.5 轮：文件加密
        try:
            from ui.widgets.file_crypto_tab import FileCryptoTab
            tabs.addTab(
                FileCryptoTab(settings, i18n, history, self),
                i18n.t("crypto_file", "文件加密"))
        except Exception as e:
            log_exc(e, module="CryptoPanel.file_tab_init")

        # 第 8 轮：高级加密（PQC）
        try:
            from ui.widgets.crypto_advanced_tab import (
                CryptoAdvancedTab,
            )
            tabs.addTab(
                CryptoAdvancedTab(settings, i18n, history, self),
                i18n.t("crypto_advanced", "高级加密"))
        except Exception as e:
            log_exc(e, module="CryptoPanel.advanced_tab_init")

        main = QVBoxLayout(self)
        main.addWidget(tabs)
        main.addWidget(QLabel(i18n.t("result")))
        main.addWidget(self.result, 1)

        sc_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        sc_undo.setContext(Qt.WidgetWithChildrenShortcut)
        sc_undo.activated.connect(self.undo)
        self._undo_sc = sc_undo

    # ==================================================================

    def _show(self, obj, tag="crypto"):
        s = (json.dumps(obj, ensure_ascii=False, indent=2)
             if not isinstance(obj, str) else obj)
        self.result.setPlainText(s)
        self.add_history(tag, s[:500], module="crypto")

    def _err(self, e):
        self.result.setPlainText(
            friendly_error(self.i18n, e, "crypto"))

    # ==================================================================
    # 编码
    # ==================================================================

    def _build_encode_tab(self):
        self.enc_in = QPlainTextEdit("Hello, 世界")
        self.enc_in.setFixedHeight(70)
        self.primary_input = self.enc_in

        self.enc_kind = QComboBox()
        # 第 8 轮：新增 base58 / base32 / base85 / ascii85
        for k in ("base64", "base64url", "hex", "url", "html",
                  "base58", "base32", "base85", "ascii85"):
            self.enc_kind.addItem(k, k)

        b_enc = QPushButton(self.i18n.t("encode", "Encode"))
        b_enc.clicked.connect(self._do_encode)
        b_dec = QPushButton(self.i18n.t("decode", "Decode"))
        b_dec.clicked.connect(self._do_decode)

        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabel(self.i18n.t("input", "Input")))
        v.addWidget(self.enc_in)
        v.addWidget(QLabel(self.i18n.t("kind", "Kind")))
        v.addWidget(self.enc_kind)
        row = QHBoxLayout()
        row.addWidget(b_enc)
        row.addWidget(b_dec)
        v.addLayout(row)
        v.addStretch(1)
        return w

    def _do_encode(self):
        try:
            self.push_undo()
            text = self.enc_in.toPlainText()
            kind = self.enc_kind.currentData()
            if kind == "base64":
                r = ct.b64_encode(text)
            elif kind == "base64url":
                r = ct.b64_encode(text, url_safe=True)
            elif kind == "hex":
                r = ct.hex_encode(text)
            elif kind == "url":
                r = ct.url_encode(text)
            elif kind == "html":
                r = ct.html_encode(text)
            elif kind == "base58":
                r = ct.base58_encode(text)
            elif kind == "base32":
                r = ct.base32_encode(text)
            elif kind == "base85":
                r = ct.base85_encode(text)
            elif kind == "ascii85":
                r = ct.ascii85_encode(text)
            else:
                return
            self._show({"kind": kind, "output": r},
                       tag=f"enc-{kind}")
        except Exception as e:
            self._err(e)

    def _do_decode(self):
        try:
            self.push_undo()
            text = self.enc_in.toPlainText()
            kind = self.enc_kind.currentData()
            if kind == "base64":
                r = ct.b64_decode(text)
            elif kind == "base64url":
                r = ct.b64_decode(text, url_safe=True)
            elif kind == "hex":
                r = ct.hex_decode(text)
            elif kind == "url":
                r = ct.url_decode(text)
            elif kind == "html":
                r = ct.html_decode(text)
            elif kind == "base58":
                r = ct.base58_decode(text)
            elif kind == "base32":
                r = ct.base32_decode(text)
            elif kind == "base85":
                r = ct.base85_decode(text)
            elif kind == "ascii85":
                r = ct.ascii85_decode(text)
            else:
                return
            self._show({"kind": kind, "output": r},
                       tag=f"dec-{kind}")
        except Exception as e:
            self._err(e)

    # ==================================================================
    # 经典密码
    # ==================================================================

    def _build_classic_tab(self):
        self.cls_in = QLineEdit("Hello World")
        self.cls_kind = QComboBox()
        self.cls_kind.addItem("ROT13", "rot13")
        self.cls_kind.addItem("Caesar", "caesar")
        self.cls_shift = QSpinBox()
        self.cls_shift.setRange(-25, 25)
        self.cls_shift.setValue(3)
        b = QPushButton(self.i18n.t("apply", "Apply"))
        b.clicked.connect(self._do_classic)

        w = QWidget()
        f = QFormLayout(w)
        f.addRow(QLabel(self.i18n.t("input", "Input")),
                 self.cls_in)
        f.addRow(QLabel(self.i18n.t("kind", "Kind")),
                 self.cls_kind)
        f.addRow(QLabel("Shift"), self.cls_shift)
        f.addRow(b)
        return w

    def _do_classic(self):
        try:
            self.push_undo()
            text = self.cls_in.text()
            kind = self.cls_kind.currentData()
            if kind == "rot13":
                r = ct.rot13(text)
            else:
                r = ct.caesar(text, self.cls_shift.value())
            self._show({"kind": kind, "output": r},
                       tag=f"classic-{kind}")
        except Exception as e:
            self._err(e)

    # ==================================================================
    # 哈希 / HMAC
    # ==================================================================

    def _build_hash_tab(self):
        self.h_in = QPlainTextEdit("hello world")
        self.h_in.setFixedHeight(70)
        self.h_algo = QComboBox()
        for k in ("md5", "sha1", "sha224", "sha256",
                  "sha384", "sha512",
                  "sha3_256", "sha3_512",
                  "blake2b", "blake2s"):
            self.h_algo.addItem(k, k)
        self.h_key = QLineEdit("")
        self.h_key.setPlaceholderText("(HMAC key, optional)")
        self.h_upper = QCheckBox(
            self.i18n.t("uppercase", "Uppercase"))
        b = QPushButton("Hash")
        b.clicked.connect(self._do_hash)

        w = QWidget()
        f = QFormLayout(w)
        f.addRow(QLabel(self.i18n.t("input", "Input")),
                 self.h_in)
        f.addRow(QLabel("Algorithm"), self.h_algo)
        f.addRow(QLabel("HMAC key"), self.h_key)
        f.addRow(QLabel(""), self.h_upper)
        f.addRow(b)
        return w

    def _do_hash(self):
        try:
            text = self.h_in.toPlainText()
            algo = self.h_algo.currentData()
            key = self.h_key.text()
            if key:
                r = ct.hmac_text(
                    text, key, algo,
                    self.h_upper.isChecked())
            else:
                r = ct.hash_text(
                    text, algo, self.h_upper.isChecked())
            self._show(r, tag=f"hash-{algo}")
        except Exception as e:
            self._err(e)

    # ==================================================================
    # AES
    # ==================================================================

    def _build_aes_tab(self):
        self.aes_plain = QPlainTextEdit("Secret message")
        self.aes_plain.setFixedHeight(70)
        self.aes_cipher = QPlainTextEdit("")
        self.aes_cipher.setFixedHeight(70)
        self.aes_key = QLineEdit(ct.gen_aes_key(256))
        self.aes_bits = QSpinBox()
        self.aes_bits.setRange(128, 256)
        self.aes_bits.setSingleStep(64)
        self.aes_bits.setValue(256)
        b_gen = QPushButton(
            self.i18n.t("gen_key", "Generate key"))
        b_gen.clicked.connect(self._aes_gen_key)
        b_enc = QPushButton(self.i18n.t("encode", "Encrypt"))
        b_enc.clicked.connect(self._aes_enc)
        b_dec = QPushButton(self.i18n.t("decode", "Decrypt"))
        b_dec.clicked.connect(self._aes_dec)

        w = QWidget()
        v = QVBoxLayout(w)
        f = QFormLayout()
        f.addRow(QLabel("Key (hex)"), self.aes_key)
        f.addRow(QLabel("Bits"), self.aes_bits)
        v.addLayout(f)
        v.addWidget(QLabel("Plaintext"))
        v.addWidget(self.aes_plain)
        v.addWidget(QLabel("Cipher (combined hex)"))
        v.addWidget(self.aes_cipher)
        row = QHBoxLayout()
        for b in (b_gen, b_enc, b_dec):
            row.addWidget(b)
        v.addLayout(row)
        v.addStretch(1)
        return w

    def _aes_gen_key(self):
        try:
            self.aes_key.setText(
                ct.gen_aes_key(self.aes_bits.value()))
        except Exception as e:
            self._err(e)

    def _aes_enc(self):
        try:
            r = ct.aes_gcm_encrypt(
                self.aes_plain.toPlainText(),
                self.aes_key.text())
            self.aes_cipher.setPlainText(r["combined"])
            self._show(r, tag="aes-enc")
        except Exception as e:
            self._err(e)

    def _aes_dec(self):
        try:
            r = ct.aes_gcm_decrypt(
                self.aes_cipher.toPlainText(),
                self.aes_key.text())
            self.aes_plain.setPlainText(r)
            self._show({"plaintext": r}, tag="aes-dec")
        except Exception as e:
            self._err(e)

    # ==================================================================
    # RSA
    # ==================================================================

    def _build_rsa_tab(self):
        self.rsa_priv = QPlainTextEdit("")
        self.rsa_priv.setFixedHeight(100)
        self.rsa_pub = QPlainTextEdit("")
        self.rsa_pub.setFixedHeight(100)
        self.rsa_bits = QSpinBox()
        self.rsa_bits.setRange(1024, 4096)
        self.rsa_bits.setSingleStep(512)
        self.rsa_bits.setValue(2048)
        self.rsa_in = QPlainTextEdit("Hello RSA")
        self.rsa_in.setFixedHeight(60)
        self.rsa_ct = QPlainTextEdit("")
        self.rsa_ct.setFixedHeight(60)
        self.rsa_gen_btn = QPushButton(
            self.i18n.t("gen_key", "Generate key"))
        self.rsa_gen_btn.clicked.connect(self._rsa_gen)
        b_enc = QPushButton(self.i18n.t("encode", "Encrypt"))
        b_enc.clicked.connect(self._rsa_enc)
        b_dec = QPushButton(self.i18n.t("decode", "Decrypt"))
        b_dec.clicked.connect(self._rsa_dec)

        w = QWidget()
        v = QVBoxLayout(w)
        row = QHBoxLayout()
        row.addWidget(QLabel("Bits"))
        row.addWidget(self.rsa_bits)
        row.addWidget(self.rsa_gen_btn)
        row.addStretch(1)
        v.addLayout(row)
        v.addWidget(QLabel("Public key (PEM)"))
        v.addWidget(self.rsa_pub)
        v.addWidget(QLabel("Private key (PEM)"))
        v.addWidget(self.rsa_priv)
        v.addWidget(QLabel("Plaintext"))
        v.addWidget(self.rsa_in)
        v.addWidget(QLabel("Cipher (hex)"))
        v.addWidget(self.rsa_ct)
        row2 = QHBoxLayout()
        row2.addWidget(b_enc)
        row2.addWidget(b_dec)
        v.addLayout(row2)
        v.addStretch(1)
        return w

    def _rsa_gen(self):
        self.result.setPlainText(
            self.i18n.t("running", "Running…"))
        try:
            self.run(
                ct.rsa_generate, self.rsa_bits.value(),
                cancel_btn=None,
                main_btn=self.rsa_gen_btn,
                on_done=self._on_rsa_gen_done,
                on_fail=self._err,
            )
        except Exception as e:
            self._err(e)

    def _on_rsa_gen_done(self, r):
        try:
            self.rsa_priv.setPlainText(r["private_key"])
            self.rsa_pub.setPlainText(r["public_key"])
            self._show(
                {"bits": r["bits"],
                 "info": "key pair generated"},
                tag="rsa-gen")
        except Exception as e:
            self._err(e)

    def _rsa_enc(self):
        try:
            r = ct.rsa_encrypt(
                self.rsa_in.toPlainText(),
                self.rsa_pub.toPlainText())
            self.rsa_ct.setPlainText(r)
            self._show(
                {"cipher": (r[:120] + "..."
                            if len(r) > 120 else r)},
                tag="rsa-enc")
        except Exception as e:
            self._err(e)

    def _rsa_dec(self):
        try:
            r = ct.rsa_decrypt(
                self.rsa_ct.toPlainText(),
                self.rsa_priv.toPlainText())
            self.rsa_in.setPlainText(r)
            self._show({"plaintext": r}, tag="rsa-dec")
        except Exception as e:
            self._err(e)

    # ==================================================================
    # TOTP
    # ==================================================================

    def _build_otp_tab(self):
        self.otp_secret = QLineEdit(ct.gen_totp_secret())
        self.otp_digits = QSpinBox()
        self.otp_digits.setRange(6, 10)
        self.otp_digits.setValue(6)
        self.otp_period = QSpinBox()
        self.otp_period.setRange(10, 120)
        self.otp_period.setValue(30)
        b_gen = QPushButton(
            self.i18n.t("gen_key", "New secret"))
        b_gen.clicked.connect(self._otp_gen)
        b_calc = QPushButton(
            self.i18n.t("calc", "Generate"))
        b_calc.clicked.connect(self._otp_calc)

        w = QWidget()
        f = QFormLayout(w)
        f.addRow(QLabel("Secret (Base32)"), self.otp_secret)
        f.addRow(QLabel("Digits"), self.otp_digits)
        f.addRow(QLabel("Period (s)"), self.otp_period)
        row = QHBoxLayout()
        row.addWidget(b_gen)
        row.addWidget(b_calc)
        f.addRow(row)
        return w

    def _otp_gen(self):
        try:
            self.otp_secret.setText(ct.gen_totp_secret())
        except Exception as e:
            self._err(e)

    def _otp_calc(self):
        try:
            r = ct.totp(
                self.otp_secret.text(),
                self.otp_digits.value(),
                self.otp_period.value())
            self._show(r, tag="totp")
        except Exception as e:
            self._err(e)

    # ==================================================================
    # 密码强度
    # ==================================================================

    def _build_pw_tab(self):
        self.pw_in = QLineEdit("")
        b = QPushButton(self.i18n.t("calc", "Analyze"))
        b.clicked.connect(self._pw_strength)
        w = QWidget()
        f = QFormLayout(w)
        f.addRow(QLabel("Password"), self.pw_in)
        f.addRow(b)
        return w

    def _pw_strength(self):
        try:
            r = ct.password_strength(self.pw_in.text())
            self._show(r, tag="pw-strength")
        except Exception as e:
            self._err(e)


__all__ = ["CryptoPanel"]