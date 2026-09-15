"""AI 助手面板：自然语言 → 表达式翻译。

- Provider 下拉（auto / rule / ollama / openai / anthropic）
- Model / Base URL 可编辑
- API key 通过独立对话框写入 ~/.multicalc/secrets.json
- "发送到基础面板"：走信号总线（send_to_basic），由 MainWindow 转发
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QComboBox, QFormLayout, QInputDialog, QMessageBox,
)

from core import ai as ai_mod
from core import secrets as sec_mod
from core.logger import log_exc
from ui.signals import bus
from ._common import ResultView
from .base import CalcPanel


class AIPanel(CalcPanel):
    module_key = "ai"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        self._last_expr = ""

        # ---- provider 选择 ----
        self.provider = QComboBox()
        self.provider.addItem(i18n.t("ai_provider_auto", "自动"), "auto")
        self.provider.addItem(i18n.t("ai_provider_rule", "本地规则"), "rule")
        self.provider.addItem("Ollama", "ollama")
        self.provider.addItem("OpenAI", "openai")
        self.provider.addItem("Anthropic", "anthropic")
        cur = settings.get("ai_provider", "auto")
        idx = self.provider.findData(cur)
        if idx >= 0:
            self.provider.setCurrentIndex(idx)
        self.provider.currentIndexChanged.connect(
            lambda _: settings.set("ai_provider",
                                   self.provider.currentData()))

        self.model = QLineEdit(settings.get("ai_model", "") or "")
        self.model.setPlaceholderText("(留空使用默认)")
        self.model.editingFinished.connect(
            lambda: settings.set("ai_model", self.model.text().strip()))

        self.base_url = QLineEdit(settings.get("ai_base_url", "") or "")
        self.base_url.setPlaceholderText("http://localhost:11434")
        self.base_url.editingFinished.connect(
            lambda: settings.set("ai_base_url",
                                 self.base_url.text().strip()))

        self.key_btn = QPushButton(i18n.t("ai_set_key", "设置 API key…"))
        self.key_btn.clicked.connect(self._set_api_key)
        self.key_status = QLabel("")
        self.key_status.setStyleSheet("color: #888;")

        # ---- 输入 ----
        self.prompt = QPlainTextEdit("")
        self.prompt.setPlaceholderText(i18n.t(
            "ai_prompt_hint",
            "例如：100 的 15% / 3 的平方根 / 20 的 3 次方"))
        self.prompt.setFixedHeight(72)

        self.translate_btn = QPushButton(
            i18n.t("ai_translate", "翻译为表达式"))
        self.translate_btn.clicked.connect(self._translate)

        self.send_btn = QPushButton(
            i18n.t("ai_send_to_basic", "发送到基础面板"))
        self.send_btn.clicked.connect(self._send_to_basic)
        self.send_btn.setEnabled(False)

        self.result = ResultView(i18n)

        form = QFormLayout()
        form.addRow(QLabel(i18n.t("ai_provider", "Provider")), self.provider)
        form.addRow(QLabel(i18n.t("ai_model", "Model")), self.model)
        form.addRow(QLabel(i18n.t("ai_base_url", "Base URL")), self.base_url)
        key_row = QHBoxLayout()
        key_row.addWidget(self.key_btn)
        key_row.addWidget(self.key_status, 1)
        form.addRow(QLabel(""), key_row)

        row = QHBoxLayout()
        row.addWidget(self.translate_btn)
        row.addWidget(self.send_btn)
        row.addStretch(1)

        main = QVBoxLayout(self)
        main.addLayout(form)
        main.addWidget(QLabel(i18n.t("ai_prompt", "自然语言")))
        main.addWidget(self.prompt)
        main.addLayout(row)
        main.addWidget(self.result, 1)

        self._refresh_key_status()

    # ------------------------------------------------------------------

    def _refresh_key_status(self):
        try:
            key = sec_mod.get("ai_api_key", "") or ""
            if key:
                shown = key[:4] + "…" + key[-4:] if len(key) > 8 else "***"
                tmpl = self.i18n.t("ai_key_set", "已设置：{k}")
                try:
                    self.key_status.setText(tmpl.format(k=shown))
                except Exception:
                    self.key_status.setText(f"已设置：{shown}")
            else:
                self.key_status.setText(
                    self.i18n.t("ai_key_unset", "未设置"))
        except Exception:
            self.key_status.setText("")

    def _set_api_key(self):
        try:
            cur = sec_mod.get("ai_api_key", "") or ""
            key, ok = QInputDialog.getText(
                self,
                self.i18n.t("ai_set_key", "设置 API key"),
                "API key:", QLineEdit.Password, text=cur)
            if not ok:
                return
            sec_mod.set("ai_api_key", key.strip() or None)
            self._refresh_key_status()
        except Exception as e:
            log_exc(e, module="AIPanel._set_api_key")

    def _get_config(self):
        return ai_mod.AIConfig(
            provider=self.provider.currentData() or "auto",
            model=self.model.text().strip(),
            base_url=self.base_url.text().strip(),
            api_key=sec_mod.get("ai_api_key", "") or "",
            timeout=20.0,
            enabled=True,
        )

    def _translate(self):
        text = self.prompt.toPlainText().strip()
        if not text:
            return
        self.result.show_result(self.i18n.t("running", "计算中…"), "")
        self.translate_btn.setEnabled(False)
        try:
            res = ai_mod.translate(text, self._get_config())
            if res.error and not res.expr:
                self.result.show_result(
                    f"[{res.provider or '?'}] {res.error}", "")
                self._last_expr = ""
                self.send_btn.setEnabled(False)
                return

            self._last_expr = res.expr
            lines = [res.expr]
            if res.explain and res.explain.strip() != res.expr.strip():
                lines.append("")
                lines.append("// " + res.explain.strip())
            lines.append("")
            lines.append(
                f"// provider={res.provider}   "
                f"confidence={res.confidence:.2f}")
            self.result.show_result("\n".join(lines), "")
            self.send_btn.setEnabled(bool(res.expr))
            self.add_history(f"ai:{text[:40]}", res.expr, module="ai")
        finally:
            self.translate_btn.setEnabled(True)

    def _send_to_basic(self):
        if not self._last_expr:
            return
        try:
            # 双通道：写入草稿（下次重建时兜底），并广播信号实时同步
            self.settings.set_draft("basic_expr", self._last_expr)
            bus().send_to_basic.emit(self._last_expr)
            QMessageBox.information(
                self, "OK",
                self.i18n.t(
                    "ai_sent_hint",
                    "已写入基础面板输入框；切换到基础面板即可计算。")
                + f"\n\n{self._last_expr}")
        except Exception as e:
            log_exc(e, module="AIPanel._send_to_basic")