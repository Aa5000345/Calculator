"""UI 对话框 + LaTeX 渲染组件。

合并自：ui/command_palette.py + ui/shortcuts_dialog.py
        + ui/settings_dialog.py + ui/theme_editor.py
        + ui/latex_widget.py

对外接口：
    # 命令面板（Ctrl+K）
    CommandPalette, _fuzzy_score

    # 快捷键速查（F1）
    ShortcutsDialog

    # 模块可见性
    ModuleVisibilityDialog

    # 主题编辑器
    ThemeEditor

    # LaTeX 渲染
    LatexLabel, clear_cache
"""
from __future__ import annotations

import io
from functools import lru_cache

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QColorDialog, QDialog,
    QDialogButtonBox, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QScrollArea, QTabWidget, QVBoxLayout, QWidget,
)

from core.base import log_exc
from core import shortcuts as sc
from core import user_data as ud
from core.pinyin_map import to_initials, to_full_pinyin


__all__ = [
    "CommandPalette", "_fuzzy_score",
    "ShortcutsDialog",
    "ModuleVisibilityDialog",
    "ThemeEditor",
    "LatexLabel", "clear_cache",
]


# ===========================================================================
# 命令面板：模糊匹配评分
# ===========================================================================

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
    return max(_fuzzy_score(query, target),
               _pinyin_score(query, target))


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
        self.list.itemActivated.connect(
            lambda _: self._run_current())
        self.list.itemClicked.connect(
            lambda _: self._run_current())

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(
            i18n.t("command_palette", "Command palette")))
        lay.addWidget(self.search)
        lay.addWidget(self.list, 1)

        self._on_change("")

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

    def _on_change(self, text):
        text = text.strip()

        if text.startswith("="):
            expr = text[1:].strip()
            self._filtered = []
            if expr:
                self._filtered.append(
                    (self._make_calc_display(expr), "calc", expr))
            self._refresh()
            return

        if text.startswith(">"):
            self._handle_gt(text[1:].strip())
            return

        scored = []
        try:
            scores = ud.usage_all_scores()
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
                for h in (self._history_search(text, limit=12)
                          or []):
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

        if text and (text[0].isdigit()
                     or text[0] in "+-("):
            scored.append((9999,
                           self._make_calc_display(text),
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
                    self._filtered.append(
                        (f"> {title}", "cmd", cb))
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
                    ud.usage_bump(
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
                from ui.shell import toast
                tmpl = self.i18n.t("copied", "已复制")
                toast(parent, f"{tmpl}: {text}",
                      level="success", duration=1800)
            except Exception:
                pass
        except Exception as e:
            try:
                from ui.shell import toast
                toast(parent, str(e), level="error",
                      duration=4000)
            except Exception:
                log_exc(
                    e, module="CommandPalette._run_calc")

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


# ===========================================================================
# 快捷键速查表
# ===========================================================================

_SHORTCUTS_HELP = [
    ("全局", [
        ("Ctrl+K", "命令面板（支持拼音首字母）"),
        ("Ctrl+Shift+K", "显示 / 隐藏浮动计算器键盘"),
        ("Ctrl+,", "打开设置面板"),
        ("Ctrl+1 ~ Ctrl+9", "切换到第 N 个可见模块"),
        ("Ctrl+\\", "当前面板在分屏中打开"),
        ("Ctrl+Shift+L", "显示 / 隐藏侧边栏"),
        ("Ctrl+Shift+H", "手写输入"),
        ("Ctrl+Shift+O", "截图 / 图片识别"),
        ("Ctrl+Shift+Z", "保存会话快照"),
        ("Ctrl+Shift+Y", "打开快照时间线"),
        ("F11", "专注模式"),
        ("F1", "快捷键速查表（本窗口）"),
        ("Esc", "关闭对话框 / 取消任务"),
    ]),
    ("输入框内", [
        ("Enter", "计算（输入框内）"),
        ("Ctrl+Enter", "计算（不限焦点）"),
        ("Esc", "取消运行中的任务；基础面板中清空输入"),
        ("Ctrl+L", "清空输入"),
        ("Ctrl+Z", "撤销上一次操作"),
        ("↑ / ↓", "召回历史表达式"),
    ]),
    ("浮动键盘", [
        ("2ⁿᵈ", "切换二级函数（sin⁻¹ / cos⁻¹ / x³ …）"),
        ("=", "触发当前面板 calc()"),
        ("C", "清空当前输入框"),
        ("⌫", "退格"),
        ("RAD / DEG", "切换角度模式"),
        ("📌", "置顶开关"),
        ("(", "自动补全右括号，光标停在中间"),
    ]),
    ("命令面板", [
        ("= 2+2", "直接计算，结果内联显示，Enter 复制"),
        ("> theme", "只匹配 theme: 前缀命令"),
        ("> 任意", "只匹配命令，忽略历史与计算"),
        ("jcjs", "拼音首字母搜索（基础计算）"),
        ("Tab", "在搜索框 / 列表间切换焦点"),
        ("↑ / ↓", "在列表中移动"),
    ]),
    ("结果面板", [
        ("右键", "复制 / 发送到其他面板 / 在新分屏打开"),
    ]),
    ("自定义", [
        ("F1 → 自定义 Tab", "录制新键位、切换预设方案、导入导出"),
    ]),
]


class ShortcutsDialog(QDialog):
    """快捷键速查表 + 自定义。"""

    def __init__(self, i18n, parent=None, settings=None):
        super().__init__(parent)
        self.i18n = i18n
        self.settings = settings
        if self.settings is None:
            try:
                self.settings = getattr(
                    parent, "settings", None)
            except Exception:
                self.settings = None

        self.setWindowTitle(i18n.t(
            "shortcuts_title", "快捷键速查表"))
        self.resize(680, 720)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_help_tab(), "速查")
        self.tabs.addTab(self._build_custom_tab(), "自定义")

        main = QVBoxLayout(self)
        main.setContentsMargins(12, 12, 12, 12)
        main.addWidget(self.tabs, 1)

        close_btn = QPushButton(i18n.t("close", "关闭"))
        close_btn.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close_btn)
        main.addLayout(row)

    # ------------------------------------------------------------------

    def _build_help_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        cv = QVBoxLayout(content)
        cv.setContentsMargins(4, 4, 4, 4)
        cv.setSpacing(10)

        for section, items in _SHORTCUTS_HELP:
            cv.addWidget(self._make_section(section, items))

        cv.addStretch(1)
        scroll.setWidget(content)
        return scroll

    def _make_section(self, title, items):
        box = QFrame()
        box.setFrameShape(QFrame.StyledPanel)
        lay = QVBoxLayout(box)

        hdr = QLabel(title)
        f = hdr.font()
        f.setBold(True)
        f.setPointSize(f.pointSize() + 1)
        hdr.setFont(f)
        lay.addWidget(hdr)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        for key, desc in items:
            k = QLabel(key)
            k.setStyleSheet(
                "background: rgba(128,128,128,0.22);"
                "padding: 2px 8px; border-radius: 4px;"
                "font-family: Consolas, monospace;")
            k.setTextInteractionFlags(Qt.TextSelectableByMouse)
            d = QLabel(desc)
            d.setWordWrap(True)
            d.setTextInteractionFlags(Qt.TextSelectableByMouse)
            form.addRow(k, d)
        lay.addLayout(form)
        return box

    def _build_custom_tab(self):
        if self.settings is None:
            w = QWidget()
            v = QVBoxLayout(w)
            v.addWidget(QLabel(self.i18n.t(
                "shortcut_no_settings",
                "需要 Settings 实例才能编辑快捷键。")))
            v.addStretch(1)
            return w

        try:
            from ui.widgets.dialogs import (
            ShortcutEditor)
            editor = ShortcutEditor(
                self.settings, self.i18n, self)
            editor.changed.connect(self._on_changed)
            return editor
        except Exception as e:
            log_exc(e, module="ShortcutsDialog._build_custom_tab")
            w = QWidget()
            v = QVBoxLayout(w)
            v.addWidget(QLabel(f"✗ {e}"))
            v.addStretch(1)
            return w

    def _on_changed(self):
        try:
            w = self.parent()
            fn = getattr(w, "reload_shortcuts", None)
            if callable(fn):
                fn()
        except Exception as e:
            log_exc(e, module="ShortcutsDialog._on_changed")


# ===========================================================================
# 模块可见性 / 排序对话框
# ===========================================================================

class ModuleVisibilityDialog(QDialog):
    """一个对话框完成模块显隐 + 拖拽排序。

    使用：
        dlg = ModuleVisibilityDialog(i18n, current_order,
                                     default_order, titles,
                                     visible_getter, parent)
        if dlg.exec() == QDialog.Accepted:
            order, vis = dlg.result_state()
    """

    def __init__(self, i18n, current_order, default_order,
                 titles, visible_getter, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self._default_order = list(default_order)
        self.setWindowTitle(
            i18n.t("module_visibility", "Module visibility"))
        self.resize(460, 520)

        self.list = QListWidget()
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.setDefaultDropAction(Qt.MoveAction)
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.setAlternatingRowColors(True)

        for key in current_order:
            item = QListWidgetItem(titles.get(key, key))
            item.setData(Qt.UserRole, key)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(
                Qt.Checked if visible_getter(key)
                else Qt.Unchecked)
            self.list.addItem(item)

        btn_all = QPushButton(i18n.t("select_all", "Select all"))
        btn_none = QPushButton(i18n.t("select_none", "Select none"))
        btn_reset = QPushButton(
            i18n.t("reset_order", "Reset order"))
        btn_all.clicked.connect(lambda: self._set_all(Qt.Checked))
        btn_none.clicked.connect(
            lambda: self._set_all(Qt.Unchecked))
        btn_reset.clicked.connect(self._reset_order)

        hint = QLabel(i18n.t(
            "module_visibility_hint",
            "勾选显示，拖拽调整顺序；点击 OK 生效。"))

        top = QHBoxLayout()
        top.addWidget(btn_all)
        top.addWidget(btn_none)
        top.addWidget(btn_reset)
        top.addStretch(1)

        box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(hint)
        lay.addLayout(top)
        lay.addWidget(self.list, 1)
        lay.addWidget(box)

    def _set_all(self, state):
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(state)

    def _reset_order(self):
        state_by_key = {}
        for i in range(self.list.count()):
            it = self.list.item(i)
            state_by_key[it.data(Qt.UserRole)] = it.checkState()

        order = [k for k in self._default_order
                 if k in state_by_key]
        order += [k for k in state_by_key if k not in order]

        self.list.clear()
        for key in order:
            item = QListWidgetItem(key)
            item.setData(Qt.UserRole, key)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(state_by_key.get(key, Qt.Checked))
            self.list.addItem(item)

    def result_state(self) -> tuple:
        order = []
        vis = {}
        for i in range(self.list.count()):
            it = self.list.item(i)
            key = it.data(Qt.UserRole)
            order.append(key)
            vis[key] = it.checkState() == Qt.Checked
        return order, vis


# ===========================================================================
# 主题编辑器
# ===========================================================================

class ThemeEditor(QDialog):
    """主题编辑器：编辑调色板、保存为 config/themes/*.json。"""

    PAL_KEYS = ("bg", "fg", "panel", "accent", "border", "hover")

    def __init__(self, settings, i18n, parent=None,
                 base_theme=None):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n
        self.setWindowTitle(i18n.t("theme_editor", "主题编辑器"))
        self.resize(460, 360)

        try:
            self._palette = dict(settings.palette(base_theme))
        except Exception:
            self._palette = {
                "bg": "#1e1e1e", "fg": "#ffffff",
                "panel": "#2d2d30", "accent": "#007acc",
                "border": "#3f3f46", "hover": "#3a3d41",
            }
        for k in self.PAL_KEYS:
            self._palette.setdefault(k, "#000000")

        self._color_btns = {}

        self.name = QLineEdit(base_theme or "my_theme")
        self.label = QLineEdit("My Theme")

        form = QFormLayout()
        form.addRow(QLabel(i18n.t("theme_name", "主题 ID")),
                    self.name)
        form.addRow(QLabel(i18n.t("theme_label", "显示名")),
                    self.label)

        for k in self.PAL_KEYS:
            b = QPushButton()
            b.setFixedHeight(28)
            b.clicked.connect(lambda _, key=k: self._pick(key))
            self._color_btns[k] = b
            form.addRow(QLabel(i18n.t(f"palette_{k}", k)), b)

        self._refresh_btns()

        btn_save = QPushButton(i18n.t("save", "保存"))
        btn_apply = QPushButton(i18n.t("apply", "应用"))
        btn_close = QPushButton(i18n.t("cancel", "取消"))
        btn_save.clicked.connect(self._save)
        btn_apply.clicked.connect(self._apply)
        btn_close.clicked.connect(self.reject)

        row = QHBoxLayout()
        row.addWidget(btn_save)
        row.addWidget(btn_apply)
        row.addStretch(1)
        row.addWidget(btn_close)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addLayout(row)

    def _pick(self, key):
        cur = QColor(self._palette.get(key, "#000000"))
        c = QColorDialog.getColor(cur, self)
        if c.isValid():
            self._palette[key] = c.name()
            self._refresh_btns()

    def _refresh_btns(self):
        for k, b in self._color_btns.items():
            color = self._palette.get(k, "#000000")
            b.setText(color)
            b.setStyleSheet(
                f"background:{color};border:1px solid #888;"
                f"border-radius:4px;padding:2px 8px;")

    def _apply(self):
        try:
            theme = self.settings.get("theme", "dark")
            if theme == "system":
                theme = "dark"

            try:
                base = dict(self.settings.palette(theme))
            except Exception:
                base = {}

            try:
                themes = self.settings.data.get("_themes") or {}
                if theme in themes and not base:
                    base = dict(themes[theme].get("palette") or {})
            except Exception:
                pass

            base.update(self._palette)

            pal = dict(self.settings.get("palette", {}) or {})
            pal[theme] = base
            self.settings.set("palette", pal)
        except Exception as e:
            log_exc(e, module="ThemeEditor._apply")

    def _save(self):
        name = (self.name.text() or "").strip()
        label = (self.label.text() or "").strip() or name
        if not name:
            QMessageBox.warning(self, "Error", "name required")
            return
        path = self.settings.save_theme(
            name, label, dict(self._palette))
        if path:
            self.settings.set("theme", name)
            QMessageBox.information(self, "OK", path)
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "save failed")


# ===========================================================================
# LaTeX 渲染组件
# ===========================================================================

@lru_cache(maxsize=512)
def _render_bytes_cached(latex: str, fontsize: int, dpi: int,
                         color: str) -> bytes | None:
    """渲染 LaTeX 到 PNG 字节。

    用 lru_cache 缓存；参数全部可哈希（str / int）。
    返回 None 表示渲染失败（会缓存 None，避免重复尝试）。
    """
    fig = Figure(figsize=(0.01, 0.01), dpi=dpi)
    fig.patch.set_alpha(0.0)
    try:
        fig.text(0, 0, f"${latex}$",
                 fontsize=fontsize, color=color)
    except Exception:
        fig.clear()
        return None

    buf = io.BytesIO()
    try:
        FigureCanvasAgg(fig)
        fig.savefig(buf, format="png", bbox_inches="tight",
                    pad_inches=0.08, transparent=True, dpi=dpi)
    except Exception:
        return None
    finally:
        fig.clear()

    return buf.getvalue()


def _render_bytes(latex: str, fontsize: int, dpi: int,
                  color: str) -> bytes | None:
    try:
        return _render_bytes_cached(
            str(latex), int(fontsize), int(dpi), str(color))
    except Exception:
        return None


def clear_cache():
    """手动清空缓存（例如主题切换后）。"""
    try:
        _render_bytes_cached.cache_clear()
    except Exception:
        pass


class LatexLabel(QLabel):
    """把 LaTeX 渲染成 QPixmap 显示；失败时退化为纯文本。"""

    def __init__(self, parent=None, fontsize=14, dpi=200):
        super().__init__(parent)
        self.fontsize = fontsize
        self.dpi = dpi
        self._color = "#ffffff"
        self._latex = ""
        self._fallback = ""
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setWordWrap(True)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.setMinimumHeight(40)

    def set_color(self, color: str):
        if color == self._color:
            return
        self._color = color
        if self._latex:
            self.set_latex(self._latex, self._fallback)

    def set_latex(self, latex: str, fallback: str = ""):
        self._latex = latex or ""
        self._fallback = fallback or latex or ""
        if not self._latex:
            self.setPixmap(QPixmap())
            self.setText(self._fallback)
            return
        data = _render_bytes(
            self._latex, self.fontsize, self.dpi, self._color)
        if data is None:
            self.setPixmap(QPixmap())
            self.setText(self._fallback)
            return
        pm = QPixmap()
        if not pm.loadFromData(data, "PNG"):
            self.setText(self._fallback)
            return
        self.setText("")
        self.setPixmap(pm)
        self.resize(pm.size())