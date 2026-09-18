"""命令面板（Ctrl+K）：模糊搜索 + 直接计算 + 历史复用 + 命令注册。

变更历史：
- 第 1 轮：初版
- 第 4 轮：集成 core.pinyin_map，搜索时同时匹配原文、拼音首字母、全拼
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QApplication, QDialog, QLineEdit, QListWidget, QListWidgetItem,
    QVBoxLayout, QLabel,
)

from core.logger import log_exc
from core import usage_stats
from core.pinyin_map import to_initials, to_full_pinyin


def _fuzzy_score(query: str, target: str) -> int:
    """混合打分：精确 > 子串 > 子序列；对中文与 ASCII 都适用。"""
    if not query:
        return 1
    q = query.lower()
    t = target.lower()

    if q == t:
        return 10000

    idx = t.find(q)
    if idx >= 0:
        return 5000 - idx * 10 - min(len(t), 200)

    i = 0
    first = -1
    last = -1
    for j, ch in enumerate(t):
        if i < len(q) and ch == q[i]:
            if first < 0:
                first = j
            last = j
            i += 1
    if i == len(q):
        spread = max(0, last - first)
        return max(1, 2000 - spread * 5 - min(len(t), 200))

    ratio = i / max(1, len(q))
    if ratio >= 0.5:
        return max(1, int(500 * ratio))
    return 0


def _pinyin_score(query: str, target: str) -> int:
    """拼音匹配：首字母 / 全拼。返回分数，0 表示不匹配。"""
    if not query or not target:
        return 0
    q = str(query).lower().strip()
    t = str(target).lower()

    # 纯 ASCII 查询才做拼音匹配（避免中文字符误判）
    if not all(c.isascii() or c.isspace() for c in q):
        return 0

    try:
        ini = to_initials(t)
        full = to_full_pinyin(t)
    except Exception:
        return 0

    if q == ini and ini:
        return 9000
    if q == full and full:
        return 8500
    if ini and q in ini:
        idx = ini.find(q)
        return max(100, 4000 - idx * 20)
    if full and q in full:
        idx = full.find(q)
        return max(100, 3500 - idx * 15)
    if ini and ini.startswith(q):
        return 3000
    if full and full.startswith(q):
        return 2800
    return 0


def _combined_score(query: str, target: str) -> int:
    """合并普通模糊分与拼音分，取较大值。"""
    s1 = _fuzzy_score(query, target)
    s2 = _pinyin_score(query, target)
    return max(s1, s2)


# 分类条目的前缀标识，用于在 _run_current 中区分
_PREFIX_CATEGORY = "cat"


class CommandPalette(QDialog):
    """命令面板。

    - 模糊搜索命令
    - 拼音首字母搜索（jcjs → 基础计算）
    - ``= 2+2`` 直接计算并内联显示
    - 历史候选项（前缀 ↺）
    - ``> `` 分类导航
    - Tab 在搜索框与列表间切换
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
        self._filtered = []

        self._categories = self._collect_categories()

        self.setWindowTitle(
            i18n.t("command_palette", "Command palette"))
        self.setWindowFlag(Qt.FramelessWindowHint, False)
        self.resize(580, 440)

        self.search = QLineEdit()
        self.search.setPlaceholderText(
            i18n.t("command_palette_hint",
                   "输入以搜索（支持拼音首字母）；"
                   "= 表达式直接计算；> 仅命令"))
        self.search.textChanged.connect(self._on_change)
        self.search.returnPressed.connect(self._run_current)

        self.list = QListWidget()
        self.list.itemActivated.connect(lambda _: self._run_current())
        self.list.itemClicked.connect(lambda _: self._run_current())

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(
            i18n.t("command_palette", "Command palette")))
        lay.addWidget(self.search)
        lay.addWidget(self.list, 1)

        self._on_change("")

    # ------------------------------------------------------------------
    # 分类提取
    # ------------------------------------------------------------------

    def _collect_categories(self) -> list:
        cats = set()
        for title, _cb in self._commands:
            if ":" in title:
                cat = title.split(":", 1)[0].strip()
                if cat and all(
                        c.isalnum() or c in "_- " for c in cat):
                    cats.add(cat)
        return sorted(cats)

    def _commands_in_category(self, cat: str) -> list:
        prefix = cat.lower() + ":"
        return [(t, cb) for t, cb in self._commands
                if t.lower().startswith(prefix)]

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
                self._filtered.append(
                    (self._make_calc_display(expr), "calc", expr))
            self._refresh()
            return

        # 2) > 开头：分类导航
        if text.startswith(">"):
            self._handle_gt(text[1:].strip())
            return

        # 3) 普通模式
        scored = []

        try:
            scores = usage_stats.all_scores()
        except Exception:
            scores = {}

        for title, cb in self._commands:
            s = _combined_score(text, title)
            if s > 0:
                if not text:
                    boost = int(scores.get(title, 0) * 5)
                else:
                    boost = int(scores.get(title, 0) * 0.5)
                scored.append((s + 200 + boost, title, "cmd", cb))

        if self._history_search and text:
            try:
                for h in self._history_search(text, limit=12) or []:
                    expr = (h.get("expr") or "").strip()
                    if not expr:
                        continue
                    s = _combined_score(text, expr)
                    if s > 0:
                        res = (h.get("result") or "").strip()
                        disp = f"↺ {expr}"
                        if res:
                            disp += f"  →  {res[:40]}"
                        scored.append((s, disp, "hist", h))
            except Exception as e:
                log_exc(e, module="CommandPalette.history_search")

        if text and (text[0].isdigit() or text[0] in "+-("):
            scored.append((9999, self._make_calc_display(text),
                           "calc", text))

        scored.sort(key=lambda x: -x[0])
        self._filtered = [(d, k, p) for _, d, k, p in scored]
        self._refresh()

    def _handle_gt(self, q: str):
        self._filtered = []

        if not q:
            for cat in self._categories:
                items = self._commands_in_category(cat)
                self._filtered.append((
                    f"▸ {cat}:   ({len(items)})",
                    _PREFIX_CATEGORY, cat))
            if self._categories:
                self._filtered.append((
                    "— 直接输入命令名或继续键入分类前缀 —",
                    "sep", None))
            for title, cb in self._commands:
                self._filtered.append((f"> {title}", "cmd", cb))
            self._refresh()
            return

        ql = q.lower()
        for cat in self._categories:
            if cat.lower() == ql:
                items = self._commands_in_category(cat)
                if not items:
                    self._filtered.append(
                        (f"（分类 {cat} 下无命令）", "sep", None))
                for title, cb in items:
                    self._filtered.append((f"> {title}", "cmd", cb))
                self._refresh()
                return

        matching_cats = [c for c in self._categories
                         if c.lower().startswith(ql)]
        for cat in matching_cats:
            items = self._commands_in_category(cat)
            self._filtered.append((
                f"▸ {cat}:   ({len(items)})",
                _PREFIX_CATEGORY, cat))

        for title, cb in self._commands:
            if _combined_score(q, title) > 0:
                self._filtered.append((f"> {title}", "cmd", cb))

        if not self._filtered:
            self._filtered.append(
                (f"（无匹配：{q}）", "sep", None))
        self._refresh()

    def _make_calc_display(self, expr: str) -> str:
        if self._calc is None:
            return f"= {expr}"
        try:
            result = self._calc(expr)
        except Exception as e:
            return f"= {expr}   ⚠ {e}"
        if isinstance(result, tuple) and len(result) == 2:
            value, desc = result
            val = str(value) if value is not None else ""
            if desc:
                return f"= {expr}   →   {val}   ({desc})"
            return f"= {expr}   →   {val}"
        return f"= {expr}   →   {result}"

    def _refresh(self):
        self.list.clear()
        for display, kind, _payload in self._filtered[:200]:
            item = QListWidgetItem(display)
            if kind == "sep":
                item.setFlags(
                    item.flags() & ~Qt.ItemIsSelectable)
                item.setForeground(Qt.gray)
            self.list.addItem(item)
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it and (it.flags() & Qt.ItemIsSelectable):
                self.list.setCurrentRow(i)
                self.list.scrollToItem(it)
                break

    # ------------------------------------------------------------------
    # 执行
    # ------------------------------------------------------------------

    def _run_current(self):
        row = self.list.currentRow()
        if row < 0 or row >= len(self._filtered):
            return
        _display, kind, payload = self._filtered[row]

        if kind == _PREFIX_CATEGORY:
            self.search.setText(f"> {payload}")
            self.search.setFocus()
            return
        if kind == "sep":
            return

        parent = self.parent()
        self.accept()
        try:
            if kind == "cmd":
                try:
                    usage_stats.bump(
                        _display.lstrip("> ").strip())
                except Exception:
                    pass
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
            try:
                from ui.toast import toast
                tmpl = self.i18n.t("copied", "已复制")
                toast(parent, f"{tmpl}: {text}",
                      level="success", duration=1800)
            except Exception:
                pass
        except Exception as e:
            try:
                from ui.toast import toast
                toast(parent, str(e), level="error",
                      duration=4000)
            except Exception:
                log_exc(e, module="CommandPalette._run_calc")

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
        key = event.key()
        if key == Qt.Key_Escape:
            self.reject()
            return
        if key in (Qt.Key_Down, Qt.Key_Up):
            self.list.setFocus()
            self.list.keyPressEvent(event)
            return
        if key == Qt.Key_Tab:
            if self.search.hasFocus():
                self.list.setFocus()
                if (self.list.count()
                        and self.list.currentRow() < 0):
                    self.list.setCurrentRow(0)
            else:
                self.search.setFocus()
                self.search.selectAll()
            return
        if key == Qt.Key_Backtab:
            if self.list.hasFocus():
                self.search.setFocus()
                self.search.selectAll()
            else:
                self.list.setFocus()
            return
        super().keyPressEvent(event)

    @staticmethod
    def shortcut():
        return QKeySequence("Ctrl+K")


__all__ = ["CommandPalette", "_fuzzy_score"]