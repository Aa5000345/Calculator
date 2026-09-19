"""加密 / 工具 / 符号字典 / 片段面板。

合并自：ui/panels/crypto_tools.py + ui/panels/tools.py
        + ui/panels/glyph_panel.py + ui/panels/snippets.py

对外接口（类名保持不变，老 registry.py 无需改动）：
    CryptoPanel
    ToolsPanel
    GlyphPanel
    SnippetsPanel

依赖（合并后）：
    core.base        —— log_exc
    core.crypto_tools —— 编码 / 哈希 / AES / RSA / TOTP / 密码强度
                        （第 4 轮已合并 crypto_advanced / file_crypto）
    core.share       —— QR / JWT / 正则 / 颜色
                        （原 core.tools_ext）
    core.symbols_lib —— 符号库（原 core.glyph_library）
    core.user_data   —— 片段存储（原 core.snippets）
    ui.widgets.input —— FocusTracker（符号插入）
    ui.panels.base       —— CalcPanel
    ui.panels._common    —— ResultView / friendly_error

修复记录（本轮）：
- CryptoPanel：`from core import crypto_tools as ct` 保持不变
  （该模块名未变）。
- ToolsPanel：`from core import tools_ext as tools`
  → `from core import share as tools`。
- GlyphPanel：`from core import glyph_library as gl`
  → `from core import symbols_lib as gl`；
  `from ui.widgets.focus_tracker import FocusTracker`
  → `from ui.widgets.input import FocusTracker`。
- SnippetsPanel：`from core import snippets as snip_mod`
  → `from core import user_data as ud`，调用统一为
  `ud.snippet_load / snippet_add / snippet_update / snippet_remove`。
- `from core.logger import log_exc` → `from core.base import log_exc`。
"""
from __future__ import annotations

import json
import os
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox,
    QFileDialog, QFormLayout, QGridLayout, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMenu, QMessageBox, QPlainTextEdit,
    QPushButton, QScrollArea, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget,QProgressBar
)

from core import crypto_tools as ct
from core import share as tools
from core import symbols_lib as gl
from core import user_data as ud
from core.base import log_exc
from ._common import (
    ResultView,
    friendly_error,
)
from .base import CalcPanel


__all__ = [
    "CryptoPanel",
    "ToolsPanel",
    "GlyphPanel",
    "SnippetsPanel",
]


# ===========================================================================
# 加密工具
# ===========================================================================

class CryptoPanel(CalcPanel):
    """加密工具面板。

    编码 / 经典密码 / 哈希-HMAC / AES / RSA / TOTP / 密码强度 /
    文件加密 / 高级加密（PQC）。
    """

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

        # 文件加密
        tabs.addTab(
            FileCryptoTab(settings, i18n, history, self),
            i18n.t("crypto_file", "文件加密"))

        # 高级加密（PQC，延迟导入）
        tabs.addTab(
            CryptoAdvancedTab(settings, i18n, history, self),
            i18n.t("crypto_advanced", "高级加密"))

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


# ===========================================================================
# 工具
# ===========================================================================

class ToolsPanel(CalcPanel):
    """工具面板：二维码 / JWT / 正则 / 颜色。"""

    module_key = "tools"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)
        self._qr_data = None

        self.result = ResultView(i18n)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_qr_tab(), "QR")
        self.tabs.addTab(self._build_jwt_tab(), "JWT")
        self.tabs.addTab(self._build_regex_tab(),
                         i18n.t("regex", "正则"))
        self.tabs.addTab(self._build_color_tab(),
                         i18n.t("color", "颜色"))

        main = QVBoxLayout(self)
        main.addWidget(self.tabs, 2)
        main.addWidget(self.result, 1)

    # ==================================================================
    # QR
    # ==================================================================

    def _build_qr_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.qr_input = QPlainTextEdit("https://example.com")
        self.qr_input.setFixedHeight(80)
        self.primary_input = self.qr_input

        b_gen = QPushButton(self.i18n.t("generate", "生成"))
        b_save = QPushButton(
            self.i18n.t("save_png", "保存 PNG"))
        b_gen.clicked.connect(self._qr_generate)
        b_save.clicked.connect(self._qr_save)

        self.qr_preview = QLabel()
        self.qr_preview.setMinimumHeight(220)
        self.qr_preview.setAlignment(Qt.AlignCenter)

        v.addWidget(QLabel(self.i18n.t("qr_content", "内容")))
        v.addWidget(self.qr_input)
        row = QHBoxLayout()
        row.addWidget(b_gen)
        row.addWidget(b_save)
        row.addStretch(1)
        v.addLayout(row)
        v.addWidget(self.qr_preview, 1)
        return w

    def _qr_generate(self):
        try:
            data = tools.qrcode_pixmap_bytes(
                self.qr_input.toPlainText())
            pm = QPixmap()
            pm.loadFromData(data, "PNG")
            self.qr_preview.setPixmap(pm)
            self._qr_data = data
            self.result.show_result(
                f"✓ {pm.width()}×{pm.height()}", "")
        except Exception as e:
            self.result.show_error(e)

    def _qr_save(self):
        if self._qr_data is None:
            self._qr_generate()
        if self._qr_data is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save PNG", "qrcode.png", "PNG (*.png)")
        if not path:
            return
        try:
            with open(path, "wb") as f:
                f.write(self._qr_data)
            self.result.show_result(f"✓ {path}", "")
        except Exception as e:
            self.result.show_error(e)

    # ==================================================================
    # JWT
    # ==================================================================

    def _build_jwt_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.jwt_input = QPlainTextEdit()
        self.jwt_input.setFixedHeight(120)
        self.jwt_input.setPlaceholderText(
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
        b = QPushButton(self.i18n.t("decode", "解析"))
        b.clicked.connect(self._jwt_decode)
        v.addWidget(QLabel("Token"))
        v.addWidget(self.jwt_input)
        v.addWidget(b)
        v.addStretch(1)
        return w

    def _jwt_decode(self):
        try:
            r = tools.jwt_decode(
                self.jwt_input.toPlainText())
            s = json.dumps(r, ensure_ascii=False,
                           indent=2, default=str)
            self.result.show_result(s, "")
            self.add_history("jwt", s[:300],
                             module="tools-jwt")
        except Exception as e:
            self.result.show_error(e)

    # ==================================================================
    # 正则
    # ==================================================================

    def _build_regex_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.re_pattern = QLineEdit(r"\d+")
        self.re_flags = QLineEdit("im")
        self.re_text = QPlainTextEdit("hello 123 world 456")
        self.re_text.setFixedHeight(120)
        self.re_repl = QLineEdit("")
        b_test = QPushButton(self.i18n.t("test", "测试"))
        b_repl = QPushButton(self.i18n.t("replace", "替换"))
        b_test.clicked.connect(self._regex_test)
        b_repl.clicked.connect(self._regex_replace)

        form = QFormLayout()
        form.addRow(QLabel("Pattern"), self.re_pattern)
        form.addRow(QLabel("Flags (imsx)"), self.re_flags)
        form.addRow(QLabel("Text"), self.re_text)
        form.addRow(QLabel("Replace with"), self.re_repl)
        row = QHBoxLayout()
        row.addWidget(b_test)
        row.addWidget(b_repl)
        row.addStretch(1)

        v.addLayout(form)
        v.addLayout(row)
        v.addStretch(1)
        return w

    def _regex_test(self):
        try:
            r = tools.regex_test(
                self.re_pattern.text(),
                self.re_text.toPlainText(),
                self.re_flags.text())
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.show_result(s, "")
        except Exception as e:
            self.result.show_error(e)

    def _regex_replace(self):
        try:
            out = tools.regex_replace(
                self.re_pattern.text(),
                self.re_repl.text(),
                self.re_text.toPlainText(),
                self.re_flags.text())
            self.result.show_result(out, "")
        except Exception as e:
            self.result.show_error(e)

    # ==================================================================
    # 颜色
    # ==================================================================

    def _build_color_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.color_input = QLineEdit("#007ACC")
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(60)
        self.color_preview.setStyleSheet(
            "background:#007ACC;border:1px solid #888;"
            "border-radius:4px;")
        self.color_other = QLineEdit("#FFFFFF")
        b1 = QPushButton(self.i18n.t("convert", "转换"))
        b2 = QPushButton(self.i18n.t("contrast", "对比度"))
        b1.clicked.connect(self._color_convert)
        b2.clicked.connect(self._color_contrast)

        form = QFormLayout()
        form.addRow(QLabel(self.i18n.t("color", "颜色")),
                    self.color_input)
        form.addRow(QLabel(""), self.color_preview)
        form.addRow(QLabel(self.i18n.t("other_color", "对比色")),
                    self.color_other)
        row = QHBoxLayout()
        row.addWidget(b1)
        row.addWidget(b2)
        row.addStretch(1)

        v.addLayout(form)
        v.addLayout(row)
        v.addStretch(1)
        return w

    def _color_convert(self):
        try:
            r = tools.color_convert(self.color_input.text())
            self.color_preview.setStyleSheet(
                f"background:{r['hex']};border:1px solid #888;"
                f"border-radius:4px;")
            s = json.dumps({
                "hex": r["hex"],
                "rgb": list(r["rgb"]),
                "hsl": list(r["hsl"]),
            }, ensure_ascii=False, indent=2)
            self.result.show_result(s, "")
            self.add_history(
                self.color_input.text(), r["hex"],
                module="tools-color")
        except Exception as e:
            self.result.show_error(e)

    def _color_contrast(self):
        try:
            r = tools.color_contrast(
                self.color_input.text(),
                self.color_other.text())
            s = json.dumps(r, ensure_ascii=False, indent=2)
            self.result.show_result(s, "")
        except Exception as e:
            self.result.show_error(e)


# ===========================================================================
# 符号字典
# ===========================================================================

COLUMNS = 12


class _GlyphButton(QPushButton):
    """单个符号按钮。"""

    def __init__(self, glyph, parent=None):
        super().__init__(glyph.char, parent)
        self.glyph = glyph
        self.setFixedSize(40, 40)
        f = QFont()
        f.setPointSize(14)
        self.setFont(f)
        self.setToolTip(
            f"{glyph.name_zh} / {glyph.name_en}\n"
            f"LaTeX: {glyph.latex or '—'}")
        self.setFocusPolicy(Qt.NoFocus)


class GlyphPanel(CalcPanel):
    """符号库面板。"""

    module_key = "glyph"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        # ---------------- 顶部 ----------------
        self.search = QLineEdit()
        self.search.setPlaceholderText(
            i18n.t("glyph_search_hint",
                   "搜索符号（中文 / 英文 / LaTeX）…"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._on_search)

        self.cat_box = QComboBox()
        self.cat_box.addItem(
            i18n.t("glyph_all", "全部"), "__all__")
        self.cat_box.addItem(
            i18n.t("glyph_favorites", "收藏 ⭐"), "__fav__")
        for c in gl.categories():
            label = i18n.t(
                f"glyph_cat_{c.key}", c.label_zh)
            self.cat_box.addItem(f"{c.icon}  {label}", c.key)
        self.cat_box.currentIndexChanged.connect(
            lambda _: self._refresh())

        top = QHBoxLayout()
        top.addWidget(self.search, 1)
        top.addWidget(self.cat_box)
        top.addWidget(self.make_kb_button())

        # ---------------- 网格 ----------------
        self._grid_widget = QWidget()
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setContentsMargins(8, 8, 8, 8)
        self._grid.setSpacing(4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._grid_widget)

        # ---------------- 状态 ----------------
        self.status = QLabel("")
        self.status.setStyleSheet(
            "color: #888; padding: 2px 6px; font-size: 9pt;")
        self.status.setWordWrap(True)

        # ---------------- 布局 ----------------
        main = QVBoxLayout(self)
        main.addLayout(top)
        main.addWidget(scroll, 1)
        main.addWidget(self.status)

        self._refresh()

    # ==================================================================
    # 刷新
    # ==================================================================

    def _current_glyphs(self):
        cat = self.cat_box.currentData()
        query = self.search.text().strip()

        if query:
            return gl.search(query)
        if cat == "__fav__":
            favs = set(gl.favorites())
            return [g for g in gl.all_glyphs()
                    if g.char in favs]
        if cat == "__all__" or not cat:
            return gl.all_glyphs()
        return gl.by_category(cat)

    def _refresh(self):
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        glyphs = self._current_glyphs()
        for i, g in enumerate(glyphs):
            btn = _GlyphButton(g)
            btn.clicked.connect(
                lambda _=False, gg=g: self._on_click(gg))
            btn.setContextMenuPolicy(Qt.CustomContextMenu)
            btn.customContextMenuRequested.connect(
                lambda pos, gg=g, bb=btn:
                self._on_context_menu(pos, gg, bb))
            r, c = divmod(i, COLUMNS)
            self._grid.addWidget(btn, r, c)

        for c in range(COLUMNS):
            self._grid.setColumnStretch(c, 1)

        n = len(glyphs)
        self.status.setText(
            self.i18n.t("glyph_count", "共 {n} 个符号")
            .format(n=n))

    # ==================================================================
    # 交互
    # ==================================================================

    def _on_search(self, _):
        self._refresh()

    def _on_click(self, glyph):
        try:
            QApplication.clipboard().setText(glyph.char)
            self.status.setText(
                self.i18n.t(
                    "glyph_copied", "已复制：{c}  {name}")
                .format(c=glyph.char, name=glyph.name_zh))
            try:
                from ui.shell import toast
                toast(self.window(),
                      f"{glyph.char}  {glyph.name_zh}",
                      level="success", duration=1200)
            except Exception:
                pass
        except Exception as e:
            log_exc(e, module="GlyphPanel._on_click")

    def _insert_to_target(self, glyph):
        try:
            from ui.widgets.input import FocusTracker
            tracker = FocusTracker.instance()
            if tracker.insert_text(glyph.char):
                self.status.setText(
                    self.i18n.t(
                        "glyph_inserted", "已插入：{c}")
                    .format(c=glyph.char))
                return
        except Exception:
            pass
        QApplication.clipboard().setText(glyph.char)
        self.status.setText(
            self.i18n.t(
                "glyph_copied", "已复制：{c}  {name}")
            .format(c=glyph.char, name=glyph.name_zh))

    def _on_context_menu(self, pos, glyph, btn):
        menu = QMenu(self)

        a_copy = menu.addAction(
            self.i18n.t("glyph_menu_copy", "复制符号"))
        a_insert = menu.addAction(
            self.i18n.t("glyph_menu_insert",
                        "插入到焦点输入框"))
        a_copy_latex = menu.addAction(
            self.i18n.t("glyph_menu_copy_latex",
                        "复制 LaTeX"))
        a_copy_char = menu.addAction(
            self.i18n.t("glyph_menu_copy_char",
                        "复制 Unicode 字符"))
        menu.addSeparator()
        is_fav = gl.is_favorite(glyph.char)
        a_fav = menu.addAction(
            self.i18n.t("glyph_menu_unfav", "取消收藏")
            if is_fav
            else self.i18n.t("glyph_menu_fav", "加入收藏"))
        menu.addSeparator()
        a_info = menu.addAction(
            self.i18n.t("glyph_menu_info", "查看详情…"))

        chosen = menu.exec(btn.mapToGlobal(pos))
        if chosen is None:
            return

        try:
            if chosen is a_copy:
                QApplication.clipboard().setText(glyph.char)
                self.status.setText(
                    self.i18n.t(
                        "glyph_copied",
                        "已复制：{c}  {name}")
                    .format(c=glyph.char,
                            name=glyph.name_zh))
            elif chosen is a_insert:
                self._insert_to_target(glyph)
            elif chosen is a_copy_latex:
                if glyph.latex:
                    QApplication.clipboard().setText(glyph.latex)
                    self.status.setText(
                        self.i18n.t(
                            "glyph_latex_copied",
                            "已复制 LaTeX：{lx}")
                        .format(lx=glyph.latex))
            elif chosen is a_copy_char:
                QApplication.clipboard().setText(glyph.char)
                self.status.setText(
                    self.i18n.t(
                        "glyph_copied",
                        "已复制：{c}  {name}")
                    .format(c=glyph.char,
                            name=glyph.name_zh))
            elif chosen is a_fav:
                new_state = gl.toggle_favorite(glyph.char)
                if new_state:
                    self.status.setText(
                        self.i18n.t(
                            "glyph_fav_added",
                            "已加入收藏：{c}")
                        .format(c=glyph.char))
                else:
                    self.status.setText(
                        self.i18n.t(
                            "glyph_fav_removed",
                            "已取消收藏：{c}")
                        .format(c=glyph.char))
                if self.cat_box.currentData() == "__fav__":
                    self._refresh()
            elif chosen is a_info:
                self._show_info(glyph)
        except Exception as e:
            log_exc(e, module="GlyphPanel._on_context_menu")

    def _show_info(self, glyph):
        text = (
            f"字符：{glyph.char}\n"
            f"中文名：{glyph.name_zh}\n"
            f"英文名：{glyph.name_en}\n"
            f"LaTeX：{glyph.latex or '—'}\n"
            f"分类：{glyph.category}\n"
            f"Unicode：U+{ord(glyph.char):04X}")
        QMessageBox.information(
            self,
            self.i18n.t("glyph_menu_info", "符号详情"),
            text)

    def on_settings_changed(self, key=None):
        pass

    def set_theme_colors(self, fg, bg, panel):
        pass


# ===========================================================================
# 片段
# ===========================================================================

class SnippetsPanel(CalcPanel):
    """片段管理器面板。"""

    module_key = "snippets"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        # ---------------- 搜索 ----------------
        self.search = QLineEdit()
        self.search.setPlaceholderText(
            i18n.t("search", "搜索"))
        self.search.textChanged.connect(self._reload)

        # ---------------- 列表 ----------------
        self.list = QListWidget()
        self.list.setSelectionMode(
            QAbstractItemView.SingleSelection)
        self.list.itemDoubleClicked.connect(
            lambda _: self._insert_current())

        # ---------------- 按钮 ----------------
        b_add = QPushButton(i18n.t("add", "新增"))
        b_edit = QPushButton(i18n.t("edit", "编辑"))
        b_del = QPushButton(i18n.t("delete", "删除"))
        b_ins = QPushButton(i18n.t("insert", "插入"))

        b_add.clicked.connect(self._add)
        b_edit.clicked.connect(self._edit)
        b_del.clicked.connect(self._delete)
        b_ins.clicked.connect(self._insert_current)

        row = QHBoxLayout()
        for b in (b_add, b_edit, b_del, b_ins):
            row.addWidget(b)
        row.addStretch(1)

        main = QVBoxLayout(self)
        main.addWidget(self.search)
        main.addWidget(self.list, 1)
        main.addLayout(row)

        self._items = []
        self._reload()

    # ==================================================================

    def _reload(self):
        self.list.clear()
        q = self.search.text().strip().lower()
        self._items = ud.snippet_load()
        for s in self._items:
            text = f"{s.get('name')}  →  {s.get('expr')}"
            tags = s.get("tags") or []
            if tags:
                text += "   #" + " #".join(tags)
            if q and q not in text.lower():
                continue
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, s)
            self.list.addItem(item)

    def _selected(self):
        it = self.list.currentItem()
        return it.data(Qt.UserRole) if it else None

    def _add(self):
        name, ok = QInputDialog.getText(
            self, self.i18n.t("add", "新增"),
            self.i18n.t("name", "名称"))
        if not ok or not name:
            return
        expr, ok = QInputDialog.getText(
            self, self.i18n.t("add", "新增"),
            self.i18n.t("expr", "表达式"))
        if not ok or not expr:
            return
        ud.snippet_add(name, expr)
        self._reload()

    def _edit(self):
        cur = self._selected()
        if cur is None:
            return
        name, ok = QInputDialog.getText(
            self, self.i18n.t("edit", "编辑"),
            self.i18n.t("name", "名称"),
            text=cur.get("name", ""))
        if not ok:
            return
        expr, ok = QInputDialog.getText(
            self, self.i18n.t("edit", "编辑"),
            self.i18n.t("expr", "表达式"),
            text=cur.get("expr", ""))
        if not ok:
            return
        try:
            idx = self._items.index(cur)
        except ValueError:
            return
        ud.snippet_update(idx, name, expr, cur.get("tags"))
        self._reload()

    def _delete(self):
        cur = self._selected()
        if cur is None:
            return
        try:
            idx = self._items.index(cur)
        except ValueError:
            return
        ud.snippet_remove(idx)
        self._reload()

    def _insert_current(self):
        cur = self._selected()
        if cur is None:
            return
        expr = cur.get("expr", "")
        try:
            QApplication.clipboard().setText(expr)
            QMessageBox.information(
                self, "OK",
                self.i18n.t("copied", "已复制到剪贴板")
                + f"\n{expr}")
        except Exception as e:
            log_exc(e, module="SnippetsPanel._insert_current")

# ===========================================================================
# 高级加密（PQC + ChaCha20 + Ed25519 + X25519 + Argon2 + 编码）
# ===========================================================================

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
    """高级加密：PQC / ChaCha20 / Ed25519 / X25519 /
    Argon2 / Base58。"""

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
            info = ct.backend_info(force=True)
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

        self.mlkem_pk = QPlainTextEdit()
        self.mlkem_pk.setFixedHeight(60)
        self.mlkem_sk = QPlainTextEdit()
        self.mlkem_sk.setFixedHeight(60)
        self.mlkem_ct = QPlainTextEdit()
        self.mlkem_ct.setFixedHeight(60)

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
            ct.mlkem_generate, self.mlkem_level.currentData(),
            on_done=self._on_mlkem_gen)

    def _on_mlkem_gen(self, r):
        self.mlkem_pk.setPlainText(r["public_key"])
        self.mlkem_sk.setPlainText(r["private_key"])
        self._show(r)

    def _mlkem_enc(self):
        self._run_async(
            ct.mlkem_encapsulate,
            self.mlkem_level.currentData(),
            self.mlkem_pk.toPlainText().strip(),
            on_done=lambda r: (
                self.mlkem_ct.setPlainText(r["ciphertext"]),
                self._show(r)))

    def _mlkem_dec(self):
        self._run_async(
            ct.mlkem_decapsulate,
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

        self.mldsa_pk = QPlainTextEdit()
        self.mldsa_pk.setFixedHeight(60)
        self.mldsa_sk = QPlainTextEdit()
        self.mldsa_sk.setFixedHeight(60)
        self.mldsa_msg = QPlainTextEdit("Hello, post-quantum!")
        self.mldsa_msg.setFixedHeight(60)
        self.mldsa_sig = QPlainTextEdit()
        self.mldsa_sig.setFixedHeight(60)

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
            ct.mldsa_generate, self.mldsa_level.currentData(),
            on_done=self._on_mldsa_gen)

    def _on_mldsa_gen(self, r):
        self.mldsa_pk.setPlainText(r["public_key"])
        self.mldsa_sk.setPlainText(r["private_key"])
        self._show(r)

    def _mldsa_sign(self):
        self._run_async(
            ct.mldsa_sign, self.mldsa_level.currentData(),
            self.mldsa_sk.toPlainText().strip(),
            self.mldsa_msg.toPlainText(),
            on_done=lambda r: (
                self.mldsa_sig.setPlainText(r["signature"]),
                self._show(r)))

    def _mldsa_verify(self):
        self._run_async(
            ct.mldsa_verify, self.mldsa_level.currentData(),
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
        self.slh_pk = QPlainTextEdit()
        self.slh_pk.setFixedHeight(60)
        self.slh_sk = QPlainTextEdit()
        self.slh_sk.setFixedHeight(60)
        self.slh_msg = QPlainTextEdit("Hello, SLH-DSA!")
        self.slh_msg.setFixedHeight(60)
        self.slh_sig = QPlainTextEdit()
        self.slh_sig.setFixedHeight(60)
        b_sign = QPushButton("签名")
        b_sign.clicked.connect(self._slh_sign)
        b_v = QPushButton("验证")
        b_v.clicked.connect(self._slh_verify)

        f = QFormLayout()
        f.addRow(QLabel("参数集"), self.slh_level)
        f.addRow(b_gen)
        f.addRow(QLabel("公钥"), self.slh_pk)
        f.addRow(QLabel("私钥"), self.slh_sk)
        f.addRow(QLabel("消息"), self.slh_msg)
        f.addRow(QLabel("签名"), self.slh_sig)
        row = QHBoxLayout()
        row.addWidget(b_sign)
        row.addWidget(b_v)
        f.addRow(row)
        v.addLayout(f)
        v.addStretch(1)
        return w

    def _slh_gen(self):
        self._run_async(
            ct.slhdsa_generate, self.slh_level.currentData(),
            on_done=lambda r: (
                self.slh_pk.setPlainText(r["public_key"]),
                self.slh_sk.setPlainText(r["private_key"]),
                self._show(r)))

    def _slh_sign(self):
        self._run_async(
            ct.slhdsa_sign, self.slh_level.currentData(),
            self.slh_sk.toPlainText().strip(),
            self.slh_msg.toPlainText(),
            on_done=lambda r: (
                self.slh_sig.setPlainText(r["signature"]),
                self._show(r)))

    def _slh_verify(self):
        self._run_async(
            ct.slhdsa_verify, self.slh_level.currentData(),
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
        self.ch_key = QLineEdit(ct.chacha20_gen_key())
        self.ch_aad = QLineEdit("")
        self.ch_ct = QPlainTextEdit("")
        self.ch_ct.setFixedHeight(70)
        b_gen = QPushButton("生成密钥")
        b_gen.clicked.connect(
            lambda: self.ch_key.setText(
                ct.chacha20_gen_key()))
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
        for b in (b_gen, b_enc, b_dec):
            row.addWidget(b)
        f.addRow(row)
        v.addLayout(f)
        v.addStretch(1)
        return w

    def _ch_enc(self):
        self._run_async(
            ct.chacha20_encrypt,
            self.ch_plain.toPlainText(),
            self.ch_key.text().strip(),
            self.ch_aad.text(),
            on_done=lambda r: (
                self.ch_ct.setPlainText(r["combined"]),
                self._show(r)))

    def _ch_dec(self):
        self._run_async(
            ct.chacha20_decrypt,
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
        self.ed_pk = QPlainTextEdit()
        self.ed_pk.setFixedHeight(60)
        self.ed_sk = QPlainTextEdit()
        self.ed_sk.setFixedHeight(60)
        self.ed_msg = QPlainTextEdit("Hello Ed25519")
        self.ed_msg.setFixedHeight(60)
        self.ed_sig = QPlainTextEdit()
        self.ed_sig.setFixedHeight(60)
        b_gen = QPushButton("生成密钥")
        b_gen.clicked.connect(
            lambda: self._run_async(
                ct.ed25519_generate, on_done=self._on_ed_gen))
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
        row.addWidget(b_sign)
        row.addWidget(b_verify)
        f.addRow(row)
        v.addLayout(f)
        v.addStretch(1)
        return w

    def _on_ed_gen(self, r):
        self.ed_pk.setPlainText(r["public_hex"])
        self.ed_sk.setPlainText(r["private_hex"])
        self._show(r)

    def _ed_sign(self):
        self._run_async(
            ct.ed25519_sign,
            self.ed_sk.toPlainText().strip(),
            self.ed_msg.toPlainText(),
            on_done=lambda r: (
                self.ed_sig.setPlainText(r["signature"]),
                self._show(r)))

    def _ed_verify(self):
        self._run_async(
            ct.ed25519_verify,
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
        v.addLayout(f)
        v.addStretch(1)
        return w

    def _x_gen(self):
        def _do():
            a = ct.x25519_generate()
            b = ct.x25519_generate()
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
            s_ab = ct.x25519_shared(
                self.x_a_priv.text().strip(),
                self.x_b_pub.text().strip())
            s_ba = ct.x25519_shared(
                self.x_b_priv.text().strip(),
                self.x_a_pub.text().strip())
            return {"ab": s_ab, "ba": s_ba,
                    "match": (s_ab["shared_secret"]
                              == s_ba["shared_secret"])}

        self._run_async(_do, on_done=self._show)

    # ==================================================================
    # Argon2 / bcrypt
    # ==================================================================

    def _build_argon2_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.pw_input = QLineEdit("my_strong_password")
        self.pw_input.setEchoMode(QLineEdit.Password)
        self.argon_time = QSpinBox()
        self.argon_time.setRange(1, 10)
        self.argon_time.setValue(3)
        self.argon_mem = QSpinBox()
        self.argon_mem.setRange(8, 1024)
        self.argon_mem.setValue(64)
        self.argon_par = QSpinBox()
        self.argon_par.setRange(1, 16)
        self.argon_par.setValue(4)
        b_a2 = QPushButton("Argon2id 哈希")
        b_a2.clicked.connect(self._argon2)
        b_bc = QPushButton("bcrypt 哈希")
        b_bc.clicked.connect(self._bcrypt)
        self.pw_out = QPlainTextEdit()
        self.pw_out.setReadOnly(True)
        b_verify = QPushButton("验证（对上一条结果）")
        b_verify.clicked.connect(self._pw_verify)

        f = QFormLayout()
        f.addRow(QLabel("密码"), self.pw_input)
        f.addRow(QLabel("Argon2 time"), self.argon_time)
        f.addRow(QLabel("Argon2 mem (MiB)"), self.argon_mem)
        f.addRow(QLabel("Argon2 par"), self.argon_par)
        row = QHBoxLayout()
        row.addWidget(b_a2)
        row.addWidget(b_bc)
        f.addRow(row)
        f.addRow(QLabel("哈希结果"), self.pw_out)
        f.addRow(b_verify)
        v.addLayout(f)
        v.addStretch(1)
        return w

    def _argon2(self):
        self._run_async(
            ct.argon2_hash,
            self.pw_input.text(),
            time_cost=self.argon_time.value(),
            memory_cost=self.argon_mem.value() * 1024,
            parallelism=self.argon_par.value(),
            on_done=lambda r: (
                self.pw_out.setPlainText(r["hash"]),
                self._show(r)))

    def _bcrypt(self):
        self._run_async(
            ct.bcrypt_hash, self.pw_input.text(),
            on_done=lambda r: (
                self.pw_out.setPlainText(r["hash"]),
                self._show(r)))

    def _pw_verify(self):
        h = self.pw_out.toPlainText().strip()
        if not h:
            return
        if h.startswith("$argon2"):
            fn = ct.argon2_verify
        else:
            fn = ct.bcrypt_verify
        self._run_async(
            fn, self.pw_input.text(), h,
            on_done=self._show)

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
        row.addWidget(b_enc)
        row.addWidget(b_dec)
        f.addRow(row)
        v.addLayout(f)
        v.addStretch(1)
        return w

    def _do_encode(self):
        k = self.enc_kind.currentData()
        fn = {
            "base58": ct.base58_encode,
            "base32": ct.base32_encode,
            "base85": ct.base85_encode,
            "ascii85": ct.ascii85_encode,
        }[k]
        self._run_async(
            fn, self.enc_input.toPlainText(),
            on_done=lambda r: self._show({"encoded": r}))

    def _do_decode(self):
        k = self.enc_kind.currentData()
        fn = {
            "base58": ct.base58_decode,
            "base32": ct.base32_decode,
            "base85": ct.base85_decode,
            "ascii85": ct.ascii85_decode,
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
        w.finished.connect(
            lambda: setattr(self, "_worker", None))
        self._worker = w
        w.start()

    def closeEvent(self, e):
        try:
            if (self._worker is not None
                    and self._worker.isRunning()):
                self._worker.cancel()
                self._worker.wait(2000)
        except Exception:
            pass
        super().closeEvent(e)


# ===========================================================================
# 文件加密
# ===========================================================================

class _FileCryptoWorker(QThread):
    """文件加解密后台线程。"""

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
            fn = (ct.encrypt_file if self._op == "encrypt"
                  else ct.decrypt_file)

            def _prog(p):
                self.progress.emit(
                    int(p.done), int(p.total), p.stage)

            def _cancel():
                return self._cancelled

            r = fn(
                *self._args,
                progress_cb=_prog,
                cancelled=_cancel,
                **self._kwargs)
            if not self._cancelled:
                self.done.emit(
                    r if isinstance(r, dict) else {})
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
        self.sub_tabs.addTab(
            self._build_encrypt_tab(),
            i18n.t("crypto_file_encrypt", "加密"))
        self.sub_tabs.addTab(
            self._build_decrypt_tab(),
            i18n.t("crypto_file_decrypt", "解密"))
        self.sub_tabs.addTab(
            self._build_info_tab(),
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
        self.enc_iter.setValue(ct.DEFAULT_PBKDF2_ITERATIONS)

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
                QLineEdit.Normal if s
                else QLineEdit.Password))

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
                QLineEdit.Normal if s
                else QLineEdit.Password))

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
            QMessageBox.warning(
                self, "Error", "请选择有效的源文件")
            return
        if not out_path:
            QMessageBox.warning(
                self, "Error", "请填写输出文件")
            return
        if not pw:
            QMessageBox.warning(
                self, "Error", "密码不能为空")
            return
        if pw != pw2:
            QMessageBox.warning(
                self, "Error", "两次密码不一致")
            return
        if (self._worker is not None
                and self._worker.isRunning()):
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
            QMessageBox.warning(
                self, "Error", "请选择加密文件")
            return
        if not out_path:
            QMessageBox.warning(
                self, "Error", "请填写输出文件")
            return
        if not pw:
            QMessageBox.warning(
                self, "Error", "密码不能为空")
            return
        if (self._worker is not None
                and self._worker.isRunning()):
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
            info = ct.get_file_info(path)
            self.info_out.setPlainText(
                json.dumps(info, ensure_ascii=False,
                           indent=2))
            self.status.setText("✓ 读取成功")
        except Exception as e:
            self.info_out.setPlainText(f"✗ {e}")
            self.status.setText("✗ 读取失败")

    def _on_progress(self, done: int, total: int, stage: str):
        try:
            if total > 0:
                pct = min(100, int(done / total * 100))
                self.progress.setValue(pct)
                self.status.setText(
                    f"{stage}: {done / (1 << 20):.1f} / "
                    f"{total / (1 << 20):.1f} MiB ({pct}%)")
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
            if (self._worker is not None
                    and self._worker.isRunning()):
                self._worker.cancel()
                self._worker.wait(2000)
        except Exception:
            pass
        super().closeEvent(e)


__all__ = [
    "CryptoPanel",
    "CryptoAdvancedTab",
    "FileCryptoTab",
    "ToolsPanel",
    "GlyphPanel",
    "SnippetsPanel",
]
