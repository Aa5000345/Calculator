"""AI 助手面板：自然语言 → 表达式翻译。

- 单条 Tab：Provider / Model / Base URL / API key / 翻译 / 发送到基础面板
- 批量 Tab：多行 NL 一次翻译 → 结果表 → 一键发送到脚本面板
- 翻译走 Worker，不阻塞 UI
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QComboBox, QFormLayout, QInputDialog, QMessageBox,
    QTabWidget, QWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView,
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
        self._last_prompt = ""

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_single_tab(), i18n.t(
            "ai_single_tab", "单条翻译"))
        self.tabs.addTab(self._build_batch_tab(), i18n.t(
            "ai_batch_tab", "批量翻译"))

        main = QVBoxLayout(self)
        main.addWidget(self.tabs)

    # ==================================================================
    # 单条
    # ==================================================================

    def _build_single_tab(self):
        i18n = self.i18n
        settings = self.settings

        w = QWidget()
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

        v = QVBoxLayout(w)
        v.addLayout(form)
        v.addWidget(QLabel(i18n.t("ai_prompt", "自然语言")))
        v.addWidget(self.prompt)
        v.addLayout(row)
        v.addWidget(self.result, 1)

        self._refresh_key_status()
        return w

    # ==================================================================
    # 批量
    # ==================================================================

    def _build_batch_tab(self):
        i18n = self.i18n
        w = QWidget()

        self.batch_input = QPlainTextEdit()
        self.batch_input.setPlaceholderText(i18n.t(
            "ai_batch_hint",
            "每行一条自然语言，例如：\n"
            "100 的 15%\n"
            "3 的平方根\n"
            "20 的 3 次方"))
        self.batch_input.setFixedHeight(130)
        self.batch_input.setPlainText(
            "100 的 15%\n3 的平方根\n20 的 3 次方\nfactorial of 5")

        self.batch_btn = QPushButton(i18n.t(
            "ai_batch_run", "全部翻译"))
        self.batch_btn.clicked.connect(self._batch_translate)

        self.batch_clear = QPushButton(i18n.t("clear", "清空"))
        self.batch_clear.clicked.connect(self.batch_input.clear)

        self.batch_to_script = QPushButton(i18n.t(
            "ai_batch_to_script", "发送到脚本面板"))
        self.batch_to_script.clicked.connect(self._send_batch_to_script)

        self.batch_to_clip = QPushButton(i18n.t(
            "ai_batch_to_clip", "复制全部表达式"))
        self.batch_to_clip.clicked.connect(self._copy_batch)

        tool_row = QHBoxLayout()
        tool_row.addWidget(self.batch_btn)
        tool_row.addWidget(self.batch_clear)
        tool_row.addStretch(1)
        tool_row.addWidget(self.batch_to_clip)
        tool_row.addWidget(self.batch_to_script)

        self.batch_table = QTableWidget(0, 3)
        self.batch_table.setHorizontalHeaderLabels([
            i18n.t("ai_batch_col_nl", "自然语言"),
            i18n.t("ai_batch_col_expr", "表达式"),
            i18n.t("ai_batch_col_note", "备注"),
        ])
        hdr = self.batch_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.batch_table.setSelectionBehavior(
            QAbstractItemView.SelectRows)

        self.batch_status = QLabel("")
        self.batch_status.setStyleSheet("color: #888;")

        v = QVBoxLayout(w)
        v.addWidget(QLabel(i18n.t(
            "ai_batch_prompt", "每行一条自然语言")))
        v.addWidget(self.batch_input)
        v.addLayout(tool_row)
        v.addWidget(self.batch_table, 1)
        v.addWidget(self.batch_status)
        return w

    # ==================================================================
    # 单条 —— 逻辑
    # ==================================================================

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
        self._last_prompt = text
        self.result.show_result(self.i18n.t("running", "计算中…"), "")
        self.translate_btn.setEnabled(False)
        try:
            self.run(
                ai_mod.translate, text, self._get_config(),
                cancel_btn=None,
                main_btn=self.translate_btn,
                on_done=self._on_translate_done,
                on_fail=self._on_translate_fail,
            )
        except Exception as e:
            self.translate_btn.setEnabled(True)
            log_exc(e, module="AIPanel._translate")

    def _on_translate_done(self, res):
        try:
            self.translate_btn.setEnabled(True)
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
            prompt = self._last_prompt[:40] if self._last_prompt else "ai"
            self.add_history(f"ai:{prompt}", res.expr, module="ai")
        except Exception as e:
            log_exc(e, module="AIPanel._on_translate_done")

    def _on_translate_fail(self, e):
        try:
            self.translate_btn.setEnabled(True)
            self.result.show_result(f"[error] {e}", "")
            self._last_expr = ""
            self.send_btn.setEnabled(False)
        except Exception as ex:
            log_exc(ex, module="AIPanel._on_translate_fail")

    def _send_to_basic(self):
        if not self._last_expr:
            return
        try:
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

    # ==================================================================
    # 批量 —— 逻辑
    # ==================================================================

    def _batch_translate(self):
        lines = [ln.strip()
                 for ln in self.batch_input.toPlainText().splitlines()
                 if ln.strip()]
        if not lines:
            self.batch_status.setText(
                self.i18n.t("ai_batch_empty", "输入为空"))
            return
        self.batch_table.setRowCount(0)
        self.batch_status.setText(
            self.i18n.t("running", "计算中…"))
        self.batch_btn.setEnabled(False)
        cfg = self._get_config()
        try:
            self.run(
                self._batch_worker, lines, cfg,
                cancel_btn=None,
                main_btn=self.batch_btn,
                on_done=self._on_batch_done,
                on_fail=self._on_batch_fail,
            )
        except Exception as e:
            self.batch_btn.setEnabled(True)
            log_exc(e, module="AIPanel._batch_translate")

    @staticmethod
    def _batch_worker(lines, cfg):
        """worker 线程：逐行翻译。"""
        out = []
        for ln in lines:
            try:
                r = ai_mod.translate(ln, cfg)
                out.append({
                    "nl": ln,
                    "expr": r.expr or "",
                    "provider": r.provider or "",
                    "error": r.error or "",
                    "confidence": float(r.confidence or 0.0),
                })
            except Exception as e:  # noqa: BLE001
                out.append({"nl": ln, "expr": "", "provider": "",
                            "error": str(e), "confidence": 0.0})
        return out

    def _on_batch_done(self, rows):
        try:
            self.batch_btn.setEnabled(True)
            ok = 0
            err = 0
            for r in rows or []:
                row = self.batch_table.rowCount()
                self.batch_table.insertRow(row)
                self.batch_table.setItem(
                    row, 0, QTableWidgetItem(r.get("nl", "")))
                self.batch_table.setItem(
                    row, 1, QTableWidgetItem(r.get("expr", "")))
                if r.get("error") and not r.get("expr"):
                    note = f"✗ {r['error']}"
                    err += 1
                else:
                    note = f"✓ {r.get('provider','')}  " \
                           f"c={r.get('confidence', 0):.2f}"
                    ok += 1
                self.batch_table.setItem(row, 2, QTableWidgetItem(note))

            tmpl = self.i18n.t(
                "ai_batch_done", "完成：成功 {ok}，失败 {err}")
            try:
                self.batch_status.setText(tmpl.format(ok=ok, err=err))
            except Exception:
                self.batch_status.setText(f"完成：{ok} 成功 / {err} 失败")

            try:
                self.add_history(
                    f"ai-batch:{len(rows)}lines",
                    f"ok={ok} err={err}", module="ai")
            except Exception:
                pass
        except Exception as e:
            log_exc(e, module="AIPanel._on_batch_done")

    def _on_batch_fail(self, e):
        try:
            self.batch_btn.setEnabled(True)
            self.batch_status.setText(f"[error] {e}")
        except Exception as ex:
            log_exc(ex, module="AIPanel._on_batch_fail")

    def _collect_batch_exprs(self) -> list[str]:
        out = []
        for r in range(self.batch_table.rowCount()):
            it = self.batch_table.item(r, 1)
            if it and it.text().strip():
                out.append(it.text().strip())
        return out

    def _copy_batch(self):
        exprs = self._collect_batch_exprs()
        if not exprs:
            self.batch_status.setText(
                self.i18n.t("ai_batch_empty", "没有可复制的表达式"))
            return
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText("\n".join(exprs))
        try:
            from ui.toast import toast
            toast(self.window(),
                  self.i18n.t("copied", "已复制"),
                  level="success")
        except Exception:
            pass

    def _send_batch_to_script(self):
        exprs = self._collect_batch_exprs()
        if not exprs:
            self.batch_status.setText(
                self.i18n.t("ai_batch_empty", "没有可发送的表达式"))
            return
        try:
            bus().send_to_script.emit("\n".join(exprs))
            try:
                from ui.toast import toast
                toast(self.window(),
                      self.i18n.t("ai_batch_sent",
                                  "已发送到脚本面板"),
                      level="success")
            except Exception:
                pass
        except Exception as e:
            log_exc(e, module="AIPanel._send_batch_to_script")