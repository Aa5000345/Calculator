"""命令面板（Ctrl+K）：模糊搜索 + 直接计算 + 历史复用 + 命令注册。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QApplication, QDialog, QLineEdit, QListWidget, QListWidgetItem,
    QVBoxLayout, QLabel, QMessageBox,
)

from core.logger import log_exc


def _fuzzy_score(query: str, target: str) -> int:
    """简单子序列匹配打分；越高越匹配。"""
    q = query.lower()
    t = target.lower()
    if not q:
        return 1
    if q in t:
        return 1000 - t.index(q)
    i = 0
    for ch in t:
        if i < len(q) and ch == q[i]:
            i += 1
    if i == len(q):
        return 500 - len(t)
    return 0


class CommandPalette(QDialog):
    """命令面板。

    支持：
    - 模糊搜索命令（模块跳转、主题切换、工具动作）
    - ``= 2+2`` 直接计算并复制结果
    - 普通输入时附带历史记录候选项（前缀 ↺）
    - ``> `` 前缀只匹配命令
    """

    def __init__(self, i18n, commands, parent=None,
                 history_search=None, calc=None,
                 reuse_handler=None):
        super().__init__(parent)
        self.i18n = i18n
        self._commands = list(commands)
        self._history_search = history_search
        self._calc = calc
        self._reuse_handler = reuse_handler
        self._filtered = []  # [(display, kind, payload)]

        self.setWindowTitle(i18n.t("command_palette", "Command palette"))
        self.setWindowFlag(Qt.FramelessWindowHint, False)
        self.resize(560, 420)

        self.search = QLineEdit()
        self.search.setPlaceholderText(
            i18n.t("command_palette_hint",
                   "输入以搜索；= 表达式直接计算；> 仅命令"))
        self.search.textChanged.connect(self._on_change)
        self.search.returnPressed.connect(self._run_current)

        self.list = QListWidget()
        self.list.itemActivated.connect(lambda _: self._run_current())
        self.list.itemClicked.connect(lambda _: self._run_current())

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(i18n.t("command_palette", "Command palette")))
        lay.addWidget(self.search)
        lay.addWidget(self.list, 1)

        self._on_change("")

    # ------------------------------------------------------------------
    # 过滤
    # ------------------------------------------------------------------

    def _on_change(self, text):
        text = text.strip()

        # 1) = 开头：直接计算
        if text.startswith("="):
            expr = text[1:].strip()
            self._filtered = []
            if expr:
                self._filtered.append((f"= {expr}", "calc", expr))
            self._refresh()
            return

        # 2) > 开头：只匹配命令
        if text.startswith(">"):
            q = text[1:].strip()
            self._filtered = []
            for title, cb in self._commands:
                if not q or _fuzzy_score(q, title) > 0:
                    self._filtered.append((f"> {title}", "cmd", cb))
            self._refresh()
            return

        # 3) 普通模式：命令 + 历史 + 计算候选
        scored = []

        for title, cb in self._commands:
            s = _fuzzy_score(text, title)
            if s > 0:
                scored.append((s + 200, title, "cmd", cb))

        if self._history_search and text:
            try:
                for h in self._history_search(text, limit=12) or []:
                    expr = (h.get("expr") or "").strip()
                    if not expr:
                        continue
                    s = _fuzzy_score(text, expr)
                    if s > 0:
                        res = (h.get("result") or "").strip()
                        disp = f"↺ {expr}"
                        if res:
                            disp += f"  →  {res[:40]}"
                        scored.append((s, disp, "hist", h))
            except Exception as e:
                log_exc(e, module="CommandPalette.history_search")

        if text and (text[0].isdigit() or text[0] in "+-("):
            scored.append((9999, f"= {text}", "calc", text))

        scored.sort(key=lambda x: -x[0])
        self._filtered = [(d, k, p) for _, d, k, p in scored]
        self._refresh()

    def _refresh(self):
        self.list.clear()
        for display, _kind, _payload in self._filtered[:200]:
            item = QListWidgetItem(display)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    # ------------------------------------------------------------------
    # 执行
    # ------------------------------------------------------------------

    def _run_current(self):
        row = self.list.currentRow()
        if row < 0 or row >= len(self._filtered):
            return
        _display, kind, payload = self._filtered[row]
        parent = self.parent()
        self.accept()
        try:
            if kind == "cmd":
                payload()
            elif kind == "calc":
                self._run_calc(payload, parent)
            elif kind == "hist":
                self._run_reuse(payload)
        except Exception as e:
            log_exc(e, module="CommandPalette.run")

    def _run_calc(self, expr, parent):
        try:
            if self._calc is None:
                return
            result = self._calc(expr)
            if isinstance(result, tuple) and len(result) == 2:
                value, desc = result
                text = str(value) if value is not None else ""
                if desc:
                    text = f"{text}   ({desc})"
            else:
                text = str(result)
            QApplication.clipboard().setText(text)
            QMessageBox.information(
                parent, "OK",
                f"{self.i18n.t('copied', 'Copied to clipboard')}\n\n= {text}")
        except Exception as e:
            QMessageBox.warning(parent, "Error", str(e))

    def _run_reuse(self, h):
        try:
            expr = h.get("expr", "")
            module = h.get("module", "")
            if self._reuse_handler is not None:
                self._reuse_handler(module, expr)
            else:
                QApplication.clipboard().setText(expr)
        except Exception as e:
            log_exc(e, module="CommandPalette.reuse")

    # ------------------------------------------------------------------
    # 键盘
    # ------------------------------------------------------------------

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
            return
        if event.key() in (Qt.Key_Down, Qt.Key_Up):
            self.list.setFocus()
            self.list.keyPressEvent(event)
            return
        super().keyPressEvent(event)

    @staticmethod
    def shortcut():
        return QKeySequence("Ctrl+K")