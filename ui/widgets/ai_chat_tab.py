"""AI 多轮对话 Tab：在 AI 面板中新增一个「对话」标签页。

被 ui/panels/ai.py 作为 Tab 使用：
    from ui.widgets.ai_chat_tab import AIChatTab
    tabs.addTab(AIChatTab(settings, i18n, history, cfg_getter),
                i18n.t("ai_chat_tab", "对话"))
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QPlainTextEdit, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

from core import ai as ai_mod
from core import ai_conversation as conv_mod
from core import secrets as sec_mod
from core.logger import log_exc


# ===========================================================================
# 消息气泡
# ===========================================================================

class _MessageBubble(QFrame):
    """单条消息气泡。"""

    def __init__(self, msg: conv_mod.Message, parent=None):
        super().__init__(parent)
        self.msg = msg
        self.setFrameShape(QFrame.StyledPanel)

        role = msg.role
        if role == "user":
            bg = "#2d4f8a"
            fg = "#ffffff"
            title = "你"
            align = Qt.AlignRight
        elif role == "assistant":
            bg = "#2d3d2d"
            fg = "#d8ffd8"
            title = "AI"
            align = Qt.AlignLeft
        else:
            bg = "#3a3a3a"
            fg = "#cccccc"
            title = "系统"
            align = Qt.AlignLeft

        self.setStyleSheet(
            f"_MessageBubble {{ background: {bg};"
            f" border-radius: 8px; padding: 6px; }}")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

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
            # 复制表达式按钮
            btn = QPushButton("复制表达式")
            btn.setFixedHeight(22)
            btn.setStyleSheet(
                "QPushButton{background:transparent;"
                "border:1px solid #888;color:#ddd;"
                "border-radius:4px;padding:0 6px;font-size:9pt;}")
            btn.clicked.connect(
                lambda: QApplication.clipboard().setText(msg.expr))
            lay.addWidget(btn)


# ===========================================================================
# 后台 Worker
# ===========================================================================

class _ChatWorker(QThread):
    done = Signal(object)     # AIResult
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
            r = conv_mod.translate_with_context(
                self._prompt, self._cfg, self._conv)
            if not self._cancelled:
                self.done.emit(r)
        except Exception as e:  # noqa: BLE001
            if not self._cancelled:
                self.failed.emit(str(e))


# ===========================================================================
# 对话 Tab
# ===========================================================================

class AIChatTab(QWidget):
    """AI 多轮对话 UI。"""

    def __init__(self, settings, i18n, history,
                 cfg_getter=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n
        self.history = history
        self._cfg_getter = cfg_getter     # fn() -> AIConfig
        self._conv = conv_mod.new_conversation()
        self._worker: _ChatWorker | None = None

        # ---------------- 顶部：会话选择 ----------------
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

        # ---------------- 消息列表 ----------------
        self._msg_container = QWidget()
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setContentsMargins(4, 4, 4, 4)
        self._msg_layout.setSpacing(6)
        self._msg_layout.addStretch(1)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self._msg_container)

        # ---------------- 输入区 ----------------
        self.input = QPlainTextEdit()
        self.input.setPlaceholderText(i18n.t(
            "ai_chat_placeholder",
            "输入自然语言；例如：100 的 15%、3 的平方根、"
            "刚才的结果乘 2"))
        self.input.setFixedHeight(60)
        # 支持 Ctrl+Enter 发送
        self.input.keyPressEvent = self._input_key_press

        self.send_btn = QPushButton(i18n.t("ai_chat_send", "发送"))
        self.send_btn.setMinimumHeight(40)
        self.send_btn.clicked.connect(self._send)

        input_row = QHBoxLayout()
        input_row.addWidget(self.input, 1)
        input_row.addWidget(self.send_btn)

        # ---------------- 状态栏 ----------------
        self.status = QLabel("")
        self.status.setStyleSheet("color: #888; padding: 2px;")

        # ---------------- 布局 ----------------
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
        items = conv_mod.list_conversations()
        for c in items:
            label = c.title or f"会话 {c.id[-6:]}"
            self.conv_box.addItem(label, c.id)
        # 当前会话放最前
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
        for c in conv_mod.list_conversations():
            if c.id == cid:
                self._conv = c
                self._rebuild_messages()
                return
        # 当前对话
        if cid == self._conv.id:
            self._rebuild_messages()

    def _new_conv(self):
        self._save_current()
        self._conv = conv_mod.new_conversation()
        self._rebuild_messages()
        self._refresh_conv_box()

    def _clear_current(self):
        self._conv.clear()
        self._rebuild_messages()

    def _save_current(self):
        if not self._conv.messages:
            return
        try:
            conv_mod.add_conversation(self._conv)
        except Exception as e:
            log_exc(e, module="AIChatTab._save_current")

    # ==================================================================
    # 消息视图
    # ==================================================================

    def _rebuild_messages(self):
        # 清空
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

        # 滚到底
        QApplication.processEvents()
        bar = self.scroll.verticalScrollBar()
        if bar is not None:
            bar.setValue(bar.maximum())

    def _append_message(self, msg: conv_mod.Message):
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

        # 1) 添加用户消息
        self._conv.add_user(text)
        self._append_message(self._conv.messages[-1])
        self.input.clear()

        # 2) 配置
        if self._cfg_getter is None:
            cfg = ai_mod.AIConfig()
        else:
            try:
                cfg = self._cfg_getter()
            except Exception:
                cfg = ai_mod.AIConfig()

        # 3) 后台翻译
        self.status.setText("正在翻译…")
        self.send_btn.setEnabled(False)

        self._worker = _ChatWorker(text, cfg, self._conv, parent=self)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_fail)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_done(self, r: ai_mod.AIResult):
        try:
            if r.error and not r.expr:
                self._conv.add_assistant(
                    content=f"[错误] {r.error}")
                self._append_message(self._conv.messages[-1])
                return

            # 添加 AI 消息
            self._conv.add_assistant(
                content=r.explain or "",
                expr=r.expr or "",
                result="")
            self._append_message(self._conv.messages[-1])

            # 尝试计算
            if r.expr:
                try:
                    from core import engine
                    val = engine.sci_eval(r.expr)
                    text = engine.format_result(val, "text")
                    # 更新 last assistant 的 result
                    self._conv.messages[-1].result = text
                    # 重建最后一条气泡
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

    def _on_fail(self, msg: str):
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
            if self._worker is not None and self._worker.isRunning():
                self._worker.cancel()
                self._worker.wait(2000)
        except Exception:
            pass
        super().closeEvent(e)