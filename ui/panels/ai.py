"""AI 助手面板：单条翻译 / 批量翻译 / 多轮对话。

合并自：ui/panels/ai.py + ui/widgets/ai_chat_tab.py

对外接口（类名保持不变）：
    AIPanel
    AIChatTab

依赖（合并后）：
    core.base   —— secret_get / log_exc
    core.ai     —— AIConfig / AIResult / translate /
                   translate_with_context / new_conversation /
                   list_conversations / add_conversation
    ui.shell    —— bus
    ui.panels.base       —— CalcPanel
    ui.panels._common    —— ResultView
"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QFormLayout,
    QFrame, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
    QScrollArea, QSizePolicy, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from core import ai as ai_mod
from core.base import secret_get, log_exc
from ui.shell import bus
from ._common import ResultView
from .base import CalcPanel


__all__ = ["AIPanel", "AIChatTab"]


# ===========================================================================
# 单条翻译 / 批量翻译面板
# ===========================================================================

class AIPanel(CalcPanel):
    """AI 助手面板。"""

    module_key = "ai"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        self._last_expr = ""
        self._last_prompt = ""

        self.tabs = QTabWidget()
        self.tabs.addTab(
            self._build_single_tab(),
            i18n.t("ai_single_tab", "单条翻译"))
        self.tabs.addTab(
            self._build_batch_tab(),
            i18n.t("ai_batch_tab", "批量翻译"))

        # 对话 Tab
        try:
            self.chat_tab = AIChatTab(
                settings, i18n, history,
                cfg_getter=self._get_config, parent=self)
            self.tabs.addTab(
                self.chat_tab,
                i18n.t("ai_chat_tab", "对话"))
        except Exception as e:
            log_exc(e, module="AIPanel.chat_init")
            self.chat_tab = None

        main = QVBoxLayout(self)
        main.addWidget(self.tabs)

    # ==================================================================
    # 单条翻译
    # ==================================================================

    def _build_single_tab(self):
        w = QWidget()

        self.provider = QComboBox()
        self.provider.addItem(
            self.i18n.t("ai_provider_auto", "自动"), "auto")
        self.provider.addItem(
            self.i18n.t("ai_provider_rule", "本地规则"), "rule")
        self.provider.addItem("Ollama", "ollama")
        self.provider.addItem("OpenAI", "openai")
        self.provider.addItem("Anthropic", "anthropic")
        cur = self.settings.get("ai_provider", "auto")
        idx = self.provider.findData(cur)
        if idx >= 0:
            self.provider.setCurrentIndex(idx)
        self.provider.currentIndexChanged.connect(
            lambda _: self.settings.set(
                "ai_provider", self.provider.currentData()))

        self.model = QLineEdit(
            self.settings.get("ai_model", "") or "")
        self.model.setPlaceholderText("(留空使用默认)")
        self.model.editingFinished.connect(
            lambda: self.settings.set(
                "ai_model", self.model.text().strip()))

        self.base_url = QLineEdit(
            self.settings.get("ai_base_url", "") or "")
        self.base_url.setPlaceholderText(
            "http://localhost:11434")
        self.base_url.editingFinished.connect(
            lambda: self.settings.set(
                "ai_base_url", self.base_url.text().strip()))

        self.key_btn = QPushButton(
            self.i18n.t("ai_set_key", "设置 API key…"))
        self.key_btn.clicked.connect(self._set_api_key)
        self.key_status = QLabel("")
        self.key_status.setStyleSheet("color: #888;")

        self.prompt = QPlainTextEdit("")
        self.prompt.setPlaceholderText(self.i18n.t(
            "ai_prompt_hint",
            "例如：100 的 15% / 3 的平方根 / 20 的 3 次方"))
        self.prompt.setFixedHeight(72)
        self.primary_input = self.prompt

        self.translate_btn = QPushButton(
            self.i18n.t("ai_translate", "翻译为表达式"))
        self.translate_btn.clicked.connect(self._translate)

        self.send_btn = QPushButton(
            self.i18n.t("ai_send_to_basic", "发送到基础面板"))
        self.send_btn.clicked.connect(self._send_to_basic)
        self.send_btn.setEnabled(False)

        self.result = ResultView(self.i18n)

        form = QFormLayout()
        form.addRow(QLabel(
            self.i18n.t("ai_provider", "Provider")),
            self.provider)
        form.addRow(QLabel(
            self.i18n.t("ai_model", "Model")), self.model)
        form.addRow(QLabel(
            self.i18n.t("ai_base_url", "Base URL")),
            self.base_url)
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
        v.addWidget(QLabel(
            self.i18n.t("ai_prompt", "自然语言")))
        v.addWidget(self.prompt)
        v.addLayout(row)
        v.addWidget(self.result, 1)

        self._refresh_key_status()
        return w

    # ==================================================================
    # 批量翻译
    # ==================================================================

    def _build_batch_tab(self):
        w = QWidget()

        self.batch_input = QPlainTextEdit()
        self.batch_input.setPlaceholderText(self.i18n.t(
            "ai_batch_hint",
            "每行一条自然语言，例如：\n"
            "100 的 15%\n"
            "3 的平方根\n"
            "20 的 3 次方"))
        self.batch_input.setFixedHeight(130)
        self.batch_input.setPlainText(
            "100 的 15%\n3 的平方根\n20 的 3 次方\n"
            "factorial of 5")

        self.batch_btn = QPushButton(
            self.i18n.t("ai_batch_run", "全部翻译"))
        self.batch_btn.clicked.connect(self._batch_translate)

        self.batch_clear = QPushButton(
            self.i18n.t("clear", "清空"))
        self.batch_clear.clicked.connect(
            self.batch_input.clear)

        self.batch_to_script = QPushButton(
            self.i18n.t("ai_batch_to_script",
                        "发送到脚本面板"))
        self.batch_to_script.clicked.connect(
            self._send_batch_to_script)

        self.batch_to_clip = QPushButton(
            self.i18n.t("ai_batch_to_clip",
                        "复制全部表达式"))
        self.batch_to_clip.clicked.connect(self._copy_batch)

        tool_row = QHBoxLayout()
        tool_row.addWidget(self.batch_btn)
        tool_row.addWidget(self.batch_clear)
        tool_row.addStretch(1)
        tool_row.addWidget(self.batch_to_clip)
        tool_row.addWidget(self.batch_to_script)

        self.batch_table = QTableWidget(0, 3)
        self.batch_table.setHorizontalHeaderLabels([
            self.i18n.t("ai_batch_col_nl", "自然语言"),
            self.i18n.t("ai_batch_col_expr", "表达式"),
            self.i18n.t("ai_batch_col_note", "备注"),
        ])
        hdr = self.batch_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(
            2, QHeaderView.ResizeToContents)
        self.batch_table.setSelectionBehavior(
            QAbstractItemView.SelectRows)

        self.batch_status = QLabel("")
        self.batch_status.setStyleSheet("color: #888;")

        v = QVBoxLayout(w)
        v.addWidget(QLabel(self.i18n.t(
            "ai_batch_prompt", "每行一条自然语言")))
        v.addWidget(self.batch_input)
        v.addLayout(tool_row)
        v.addWidget(self.batch_table, 1)
        v.addWidget(self.batch_status)
        return w

    # ==================================================================
    # 单条逻辑
    # ==================================================================

    def _refresh_key_status(self):
        try:
            key = secret_get("ai_api_key", "") or ""
            if key:
                shown = (key[:4] + "…" + key[-4:]
                         if len(key) > 8 else "***")
                tmpl = self.i18n.t(
                    "ai_key_set", "已设置：{k}")
                try:
                    self.key_status.setText(
                        tmpl.format(k=shown))
                except Exception:
                    self.key_status.setText(
                        f"已设置：{shown}")
            else:
                self.key_status.setText(
                    self.i18n.t("ai_key_unset", "未设置"))
        except Exception:
            self.key_status.setText("")

    def _set_api_key(self):
        try:
            cur = secret_get("ai_api_key", "") or ""
            key, ok = QInputDialog.getText(
                self,
                self.i18n.t("ai_set_key", "设置 API key"),
                "API key:", QLineEdit.Password, text=cur)
            if not ok:
                return
            from core.base import secret_set
            secret_set("ai_api_key", key.strip() or None)
            self._refresh_key_status()
        except Exception as e:
            log_exc(e, module="AIPanel._set_api_key")

    def _get_config(self):
        return ai_mod.AIConfig(
            provider=self.provider.currentData() or "auto",
            model=self.model.text().strip(),
            base_url=self.base_url.text().strip(),
            api_key=secret_get("ai_api_key", "") or "",
            timeout=20.0,
            enabled=True,
        )

    def _translate(self):
        text = self.prompt.toPlainText().strip()
        if not text:
            return
        self._last_prompt = text
        self.result.show_result(
            self.i18n.t("running", "计算中…"), "")
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
            prompt = (self._last_prompt[:40]
                      if self._last_prompt else "ai")
            self.add_history(
                f"ai:{prompt}", res.expr, module="ai")
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
            self.settings.set_draft(
                "basic_expr", self._last_expr)
            bus().send_to_basic.emit(self._last_expr)
            QMessageBox.information(
                self, "OK",
                self.i18n.t(
                    "ai_sent_hint",
                    "已写入基础面板输入框；切换到基础面板"
                    "即可计算。")
                + f"\n\n{self._last_expr}")
        except Exception as e:
            log_exc(e, module="AIPanel._send_to_basic")

    # ==================================================================
    # 批量逻辑
    # ==================================================================

    def _batch_translate(self):
        lines = [ln.strip()
                 for ln in self.batch_input.toPlainText()
                 .splitlines() if ln.strip()]
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
                out.append({
                    "nl": ln, "expr": "",
                    "provider": "", "error": str(e),
                    "confidence": 0.0,
                })
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
                    note = (f"✓ {r.get('provider', '')}  "
                            f"c={r.get('confidence', 0):.2f}")
                    ok += 1
                self.batch_table.setItem(
                    row, 2, QTableWidgetItem(note))

            tmpl = self.i18n.t(
                "ai_batch_done",
                "完成：成功 {ok}，失败 {err}")
            try:
                self.batch_status.setText(
                    tmpl.format(ok=ok, err=err))
            except Exception:
                self.batch_status.setText(
                    f"完成：{ok} 成功 / {err} 失败")

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

    def _collect_batch_exprs(self) -> list:
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
                self.i18n.t("ai_batch_empty",
                            "没有可复制的表达式"))
            return
        QApplication.clipboard().setText("\n".join(exprs))
        try:
            from ui.shell import toast
            toast(self.window(),
                  self.i18n.t("copied", "已复制"),
                  level="success")
        except Exception:
            pass

    def _send_batch_to_script(self):
        exprs = self._collect_batch_exprs()
        if not exprs:
            self.batch_status.setText(
                self.i18n.t("ai_batch_empty",
                            "没有可发送的表达式"))
            return
        try:
            bus().send_to_script.emit("\n".join(exprs))
            try:
                from ui.shell import toast
                toast(self.window(),
                      self.i18n.t(
                          "ai_batch_sent",
                          "已发送到脚本面板"),
                      level="success")
            except Exception:
                pass
        except Exception as e:
            log_exc(e, module="AIPanel._send_batch_to_script")


# ===========================================================================
# 对话 Tab
# ===========================================================================

class _MessageBubble(QFrame):
    """单条消息气泡。"""

    def __init__(self, msg, parent=None):
        super().__init__(parent)
        self.msg = msg
        self.setFrameShape(QFrame.StyledPanel)

        role = msg.role
        if role == "user":
            bg = "#2d4f8a"
            fg = "#ffffff"
            title = "你"
        elif role == "assistant":
            bg = "#2d3d2d"
            fg = "#d8ffd8"
            title = "AI"
        else:
            bg = "#3a3a3a"
            fg = "#cccccc"
            title = "系统"

        self.setStyleSheet(
            f"_MessageBubble {{ background: {bg};"
            f" border-radius: 8px; padding: 6px; }}")
        self.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Minimum)

        head = QLabel(title)
        hf = QFont()
        hf.setBold(True)
        hf.setPointSize(max(8, hf.pointSize() - 1))
        head.setFont(hf)
        head.setStyleSheet(f"color: {fg}; opacity: 0.7;")

        body_text = msg.content or ""
        if msg.expr and msg.role == "assistant":
            body_text = (body_text + "\n" if body_text else "") + \
                f"表达式：{msg.expr}"
        if msg.result and msg.role == "assistant":
            body_text += f"\n结果：{msg.result}"

        body = QLabel(body_text)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        body.setStyleSheet(f"color: {fg};")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.addWidget(head)
        lay.addWidget(body)

        if role == "assistant" and msg.expr:
            btn = QPushButton("复制表达式")
            btn.setFixedHeight(22)
            btn.setStyleSheet(
                "QPushButton{background:transparent;"
                "border:1px solid #888;color:#ddd;"
                "border-radius:4px;padding:0 6px;"
                "font-size:9pt;}")
            btn.clicked.connect(
                lambda: QApplication.clipboard().setText(
                    msg.expr))
            lay.addWidget(btn)


class _ChatWorker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, prompt, cfg, conv, parent=None):
        super().__init__(parent)
        self._prompt = prompt
        self._cfg = cfg
        self._conv = conv
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            r = ai_mod.translate_with_context(
                self._prompt, self._cfg, self._conv)
            if not self._cancelled:
                self.done.emit(r)
        except Exception as e:  # noqa: BLE001
            if not self._cancelled:
                self.failed.emit(str(e))


class AIChatTab(QWidget):
    """AI 多轮对话 UI。"""

    def __init__(self, settings, i18n, history,
                 cfg_getter=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n
        self.history = history
        self._cfg_getter = cfg_getter
        self._conv = ai_mod.new_conversation()
        self._worker: _ChatWorker | None = None

        self.conv_box = QComboBox()
        self.conv_box.setMinimumWidth(200)
        self.conv_box.currentIndexChanged.connect(
            self._on_conv_changed)

        b_new = QPushButton("＋ 新对话")
        b_new.clicked.connect(self._new_conv)
        b_clear = QPushButton("清空当前")
        b_clear.clicked.connect(self._clear_current)
        b_save = QPushButton("保存会话")
        b_save.clicked.connect(self._save_current)

        top = QHBoxLayout()
        top.addWidget(QLabel("会话"))
        top.addWidget(self.conv_box, 1)
        top.addWidget(b_new)
        top.addWidget(b_clear)
        top.addWidget(b_save)

        self._msg_container = QWidget()
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setContentsMargins(4, 4, 4, 4)
        self._msg_layout.setSpacing(6)
        self._msg_layout.addStretch(1)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self._msg_container)

        self.input = QPlainTextEdit()
        self.input.setPlaceholderText(i18n.t(
            "ai_chat_placeholder",
            "输入自然语言；例如：100 的 15%、3 的平方根、"
            "刚才的结果乘 2"))
        self.input.setFixedHeight(60)
        self.input.keyPressEvent = self._input_key_press

        self.send_btn = QPushButton(i18n.t("ai_chat_send", "发送"))
        self.send_btn.setMinimumHeight(40)
        self.send_btn.clicked.connect(self._send)

        input_row = QHBoxLayout()
        input_row.addWidget(self.input, 1)
        input_row.addWidget(self.send_btn)

        self.status = QLabel("")
        self.status.setStyleSheet("color: #888; padding: 2px;")

        main = QVBoxLayout(self)
        main.addLayout(top)
        main.addWidget(self.scroll, 1)
        main.addLayout(input_row)
        main.addWidget(self.status)

        self._refresh_conv_box()

    # ==================================================================
    # 会话管理
    # ==================================================================

    def _refresh_conv_box(self):
        self.conv_box.blockSignals(True)
        self.conv_box.clear()
        items = ai_mod.list_conversations()
        for c in items:
            label = c.title or f"会话 {c.id[-6:]}"
            self.conv_box.addItem(label, c.id)
        if self._conv.id:
            idx = self.conv_box.findData(self._conv.id)
            if idx < 0:
                self.conv_box.insertItem(
                    0, self._conv.title, self._conv.id)
                idx = 0
            self.conv_box.setCurrentIndex(idx)
        self.conv_box.blockSignals(False)

    def _on_conv_changed(self, _):
        cid = self.conv_box.currentData()
        if not cid:
            return
        for c in ai_mod.list_conversations():
            if c.id == cid:
                self._conv = c
                self._rebuild_messages()
                return
        if cid == self._conv.id:
            self._rebuild_messages()

    def _new_conv(self):
        self._save_current()
        self._conv = ai_mod.new_conversation()
        self._rebuild_messages()
        self._refresh_conv_box()

    def _clear_current(self):
        self._conv.clear()
        self._rebuild_messages()

    def _save_current(self):
        if not self._conv.messages:
            return
        try:
            ai_mod.add_conversation(self._conv)
        except Exception as e:
            log_exc(e, module="AIChatTab._save_current")

    # ==================================================================
    # 消息视图
    # ==================================================================

    def _rebuild_messages(self):
        while self._msg_layout.count() > 1:
            item = self._msg_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        for m in self._conv.messages:
            bubble = _MessageBubble(m, self)
            self._msg_layout.insertWidget(
                self._msg_layout.count() - 1, bubble)

        QApplication.processEvents()
        bar = self.scroll.verticalScrollBar()
        if bar is not None:
            bar.setValue(bar.maximum())

    def _append_message(self, msg):
        bubble = _MessageBubble(msg, self)
        self._msg_layout.insertWidget(
            self._msg_layout.count() - 1, bubble)
        QApplication.processEvents()
        bar = self.scroll.verticalScrollBar()
        if bar is not None:
            bar.setValue(bar.maximum())

    # ==================================================================
    # 发送
    # ==================================================================

    def _input_key_press(self, event):
        if (event.key() in (Qt.Key_Return, Qt.Key_Enter)
                and (event.modifiers() & Qt.ControlModifier)):
            self._send()
            return
        QPlainTextEdit.keyPressEvent(self.input, event)

    def _send(self):
        text = self.input.toPlainText().strip()
        if not text:
            return
        if self._worker is not None and self._worker.isRunning():
            return

        self._conv.add_user(text)
        self._append_message(self._conv.messages[-1])
        self.input.clear()

        if self._cfg_getter is None:
            cfg = ai_mod.AIConfig()
        else:
            try:
                cfg = self._cfg_getter()
            except Exception:
                cfg = ai_mod.AIConfig()

        self.status.setText("正在翻译…")
        self.send_btn.setEnabled(False)

        self._worker = _ChatWorker(
            text, cfg, self._conv, parent=self)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_fail)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_done(self, r):
        try:
            if r.error and not r.expr:
                self._conv.add_assistant(
                    content=f"[错误] {r.error}")
                self._append_message(self._conv.messages[-1])
                return

            self._conv.add_assistant(
                content=r.explain or "",
                expr=r.expr or "",
                result="")
            self._append_message(self._conv.messages[-1])

            if r.expr:
                try:
                    from core import engine
                    val = engine.sci_eval(r.expr)
                    text = engine.format_result(val, "text")
                    self._conv.messages[-1].result = text
                    self._rebuild_messages()
                    if self.history is not None:
                        self.history.add(
                            "ai-chat",
                            (self._conv.messages[-2].content
                             if len(self._conv.messages) >= 2
                             else ""),
                            f"{r.expr} = {text}")
                except Exception as e:
                    log_exc(e, module="AIChatTab._on_done.calc")
        except Exception as e:
            log_exc(e, module="AIChatTab._on_done")

    def _on_fail(self, msg):
        try:
            self._conv.add_assistant(content=f"[错误] {msg}")
            self._append_message(self._conv.messages[-1])
        except Exception:
            pass

    def _on_finished(self):
        self.send_btn.setEnabled(True)
        self._worker = None
        self.status.setText("")

    # ==================================================================

    def closeEvent(self, e):
        try:
            self._save_current()
        except Exception:
            pass
        try:
            if (self._worker is not None
                    and self._worker.isRunning()):
                self._worker.cancel()
                self._worker.wait(2000)
        except Exception:
            pass
        super().closeEvent(e)