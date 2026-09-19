"""计时器 / 剪贴板 / 笔记本 / 脚本面板。

合并自：ui/panels/timer_panel.py + ui/panels/clipboard_history.py
        + ui/panels/notebook_panel.py + ui/panels/script.py

对外接口（类名保持不变，老 registry.py 无需改动）：
    TimerPanel
    ClipboardHistoryPanel
    NotebookPanel
    ScriptPanel

依赖（合并后）：
    core.base            —— InputError / CalcError / log_exc
    core.state           —— symbols（用户变量，notebook / script 使用）
    core.engine          —— sci_eval / format_result
    core.notebook        —— Notebook / NotebookCell / MCNB_FORMAT
    core.user_data       —— 最近文件（notebook 打开时记录）
    core.clipboard_monitor —— 剪贴板监听
    ui.shortcuts         —— install_panel_shortcuts
    ui.shell             —— bus / toast
    ui.widgets.input     —— InputHistoryButton（延迟）
    ui.panels.base       —— CalcPanel
    ui.panels._common    —— ResultView / friendly_error

修复记录（本轮）：
- NotebookPanel：`from core import notebook as nb_mod` 保持不变
  （第 4 轮已合并 notebook + notebook_export + pipeline）。
- NotebookPanel：`from core import symbols as sym_mod`
  → `from core import state as state_mod`（symbols 已合并进 state）。
- ScriptPanel：`from core.errors import InputError`
  → `from core.base import InputError`。
- `from core.logger import log_exc` → `from core.base import log_exc`。
- `from ui.signals import bus` → `from ui.shell import bus`。
- `from ui.toast import toast` → `from ui.shell import toast`（延迟）。
- NotebookPanel：`from ui.widgets.input_history_widget import ...`
  → `from ui.widgets.input import ...`（延迟）。
"""
from __future__ import annotations

import csv as _csv
import os
import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QFileDialog,
    QFormLayout, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QSpinBox,
    QSplitter, QTabWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from core import engine
from core import notebook as nb_mod
from core import clipboard_monitor
from core import user_data as ud
from core.base import CalcError, log_exc
from ui.shell import bus
from ._common import (
    ResultView,
    friendly_error,
)
from .base import CalcPanel


__all__ = [
    "TimerPanel",
    "ClipboardHistoryPanel",
    "NotebookPanel",
    "ScriptPanel",
]


# ===========================================================================
# 计时器
# ===========================================================================

def _fmt_seconds(seconds):
    s = max(0, int(seconds))
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class TimerPanel(CalcPanel):
    """计时器 / 秒表 / 番茄钟。"""

    module_key = "timer"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        tabs = QTabWidget()
        tabs.addTab(self._build_countdown(),
                    i18n.t("countdown", "倒计时"))
        tabs.addTab(self._build_stopwatch(),
                    i18n.t("stopwatch", "秒表"))
        tabs.addTab(self._build_pomodoro(),
                    i18n.t("pomodoro", "番茄钟"))

        main = QVBoxLayout(self)
        main.addWidget(tabs)

    # ==================================================================
    # 倒计时
    # ==================================================================

    def _build_countdown(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.cd_display = QLabel("00:00:00")
        self.cd_display.setAlignment(Qt.AlignCenter)
        self.cd_display.setStyleSheet(
            "font-size: 36pt;"
            " font-family: Consolas, monospace;")

        self.cd_h = QSpinBox()
        self.cd_h.setRange(0, 99)
        self.cd_m = QSpinBox()
        self.cd_m.setRange(0, 59)
        self.cd_s = QSpinBox()
        self.cd_s.setRange(0, 59)

        b_start = QPushButton(self.i18n.t("start", "开始"))
        b_pause = QPushButton(self.i18n.t("pause", "暂停"))
        b_reset = QPushButton(self.i18n.t("reset", "重置"))
        b_start.clicked.connect(self._cd_start)
        b_pause.clicked.connect(self._cd_pause)
        b_reset.clicked.connect(self._cd_reset)

        form = QHBoxLayout()
        for w_, lbl in ((self.cd_h, "H"),
                        (self.cd_m, "M"),
                        (self.cd_s, "S")):
            form.addWidget(QLabel(lbl))
            form.addWidget(w_)

        row = QHBoxLayout()
        for b in (b_start, b_pause, b_reset):
            row.addWidget(b)
        row.addStretch(1)

        v.addWidget(self.cd_display)
        v.addLayout(form)
        v.addLayout(row)
        v.addStretch(1)

        self._cd_timer = QTimer(self)
        self._cd_timer.setInterval(1000)
        self._cd_timer.timeout.connect(self._cd_tick)
        self._cd_left = 0
        return w

    def _cd_start(self):
        if self._cd_left <= 0:
            self._cd_left = (self.cd_h.value() * 3600
                             + self.cd_m.value() * 60
                             + self.cd_s.value())
        self._cd_timer.start()

    def _cd_pause(self):
        self._cd_timer.stop()

    def _cd_reset(self):
        self._cd_timer.stop()
        self._cd_left = 0
        self.cd_display.setText("00:00:00")

    def _cd_tick(self):
        self._cd_left -= 1
        if self._cd_left <= 0:
            self._cd_left = 0
            self._cd_timer.stop()
            self.cd_display.setText("DONE")
            try:
                QApplication.beep()
            except Exception:
                pass
        else:
            self.cd_display.setText(_fmt_seconds(self._cd_left))

    # ==================================================================
    # 秒表
    # ==================================================================

    def _build_stopwatch(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.sw_display = QLabel("00:00:00")
        self.sw_display.setAlignment(Qt.AlignCenter)
        self.sw_display.setStyleSheet(
            "font-size: 36pt;"
            " font-family: Consolas, monospace;")

        b_start = QPushButton(self.i18n.t("start", "开始"))
        b_lap = QPushButton(self.i18n.t("lap", "计次"))
        b_reset = QPushButton(self.i18n.t("reset", "重置"))
        b_start.clicked.connect(self._sw_toggle)
        b_lap.clicked.connect(self._sw_lap)
        b_reset.clicked.connect(self._sw_reset)

        self.sw_laps = QListWidget()

        row = QHBoxLayout()
        for b in (b_start, b_lap, b_reset):
            row.addWidget(b)
        row.addStretch(1)

        v.addWidget(self.sw_display)
        v.addLayout(row)
        v.addWidget(self.sw_laps, 1)

        self._sw_timer = QTimer(self)
        self._sw_timer.setInterval(100)
        self._sw_timer.timeout.connect(self._sw_tick)
        self._sw_ms = 0
        self._sw_running = False
        self._sw_btn = b_start
        return w

    def _sw_toggle(self):
        if self._sw_running:
            self._sw_timer.stop()
            self._sw_running = False
            self._sw_btn.setText(self.i18n.t("start", "开始"))
        else:
            self._sw_timer.start()
            self._sw_running = True
            self._sw_btn.setText(self.i18n.t("pause", "暂停"))

    def _sw_tick(self):
        self._sw_ms += 100
        self.sw_display.setText(_fmt_seconds(self._sw_ms / 1000))

    def _sw_lap(self):
        self.sw_laps.addItem(
            QListWidgetItem(self.sw_display.text()))

    def _sw_reset(self):
        self._sw_timer.stop()
        self._sw_running = False
        self._sw_ms = 0
        self.sw_display.setText("00:00:00")
        self.sw_laps.clear()
        self._sw_btn.setText(self.i18n.t("start", "开始"))

    # ==================================================================
    # 番茄钟
    # ==================================================================

    def _build_pomodoro(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.pm_display = QLabel("25:00")
        self.pm_display.setAlignment(Qt.AlignCenter)
        self.pm_display.setStyleSheet(
            "font-size: 48pt;"
            " font-family: Consolas, monospace;")

        self.pm_min = QSpinBox()
        self.pm_min.setRange(1, 120)
        self.pm_min.setValue(25)
        self.pm_break = QSpinBox()
        self.pm_break.setRange(1, 60)
        self.pm_break.setValue(5)

        b_start = QPushButton(self.i18n.t("start", "开始"))
        b_reset = QPushButton(self.i18n.t("reset", "重置"))
        b_start.clicked.connect(self._pm_start)
        b_reset.clicked.connect(self._pm_reset)

        form = QFormLayout()
        form.addRow(QLabel("Work (min)"), self.pm_min)
        form.addRow(QLabel("Break (min)"), self.pm_break)

        row = QHBoxLayout()
        for b in (b_start, b_reset):
            row.addWidget(b)
        row.addStretch(1)

        v.addWidget(self.pm_display)
        v.addLayout(form)
        v.addLayout(row)
        v.addStretch(1)

        self._pm_timer = QTimer(self)
        self._pm_timer.setInterval(1000)
        self._pm_timer.timeout.connect(self._pm_tick)
        self._pm_left = 0
        self._pm_mode = "work"
        return w

    def _pm_start(self):
        if self._pm_left <= 0:
            self._pm_mode = "work"
            self._pm_left = self.pm_min.value() * 60
        self._pm_timer.start()

    def _pm_reset(self):
        self._pm_timer.stop()
        self._pm_left = 0
        self._pm_mode = "work"
        self.pm_display.setText(
            f"{self.pm_min.value():02d}:00")

    def _pm_tick(self):
        self._pm_left -= 1
        if self._pm_left <= 0:
            try:
                QApplication.beep()
            except Exception:
                pass
            if self._pm_mode == "work":
                self._pm_mode = "break"
                self._pm_left = self.pm_break.value() * 60
            else:
                self._pm_mode = "work"
                self._pm_left = self.pm_min.value() * 60
        m, s = divmod(self._pm_left, 60)
        tag = "🍅" if self._pm_mode == "work" else "☕"
        self.pm_display.setText(f"{tag} {m:02d}:{s:02d}")


# ===========================================================================
# 剪贴板历史
# ===========================================================================

class ClipboardHistoryPanel(CalcPanel):
    """剪贴板历史面板。

    监听系统剪贴板、可搜索、可固定、可智能识别表达式。
    """

    module_key = "clipboard_history"

    MAX = 200

    expr_detected = Signal(str)

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)
        self._items: list = []

        self.search = QLineEdit()
        self.search.setPlaceholderText(i18n.t("search", "搜索"))
        self.search.textChanged.connect(self._refresh)

        self.list = QListWidget()
        self.list.setSelectionMode(
            QAbstractItemView.SingleSelection)
        self.list.itemDoubleClicked.connect(
            lambda _: self._copy_current())

        b_copy = QPushButton(i18n.t("copy", "复制"))
        b_pin = QPushButton(i18n.t("pin", "固定"))
        b_clear = QPushButton(i18n.t("clear", "清空"))
        b_copy.clicked.connect(self._copy_current)
        b_pin.clicked.connect(self._toggle_pin)
        b_clear.clicked.connect(self._clear)

        # ---------------- 智能识别开关 ----------------
        self.smart_detect = QCheckBox(
            i18n.t("clipboard_smart_detect",
                   "智能识别表达式"))
        self.smart_detect.setChecked(
            bool(settings.get("clipboard_smart_detect", False)))
        self.smart_detect.stateChanged.connect(
            self._on_smart_toggle)

        self.smart_toast = QCheckBox(
            i18n.t("clipboard_smart_toast", "识别后弹提示"))
        self.smart_toast.setChecked(
            bool(settings.get("clipboard_smart_toast", True)))
        self.smart_toast.stateChanged.connect(
            lambda _: settings.set(
                "clipboard_smart_toast",
                self.smart_toast.isChecked()))

        row = QHBoxLayout()
        for b in (b_copy, b_pin, b_clear):
            row.addWidget(b)
        row.addStretch(1)

        smart_row = QHBoxLayout()
        smart_row.addWidget(self.smart_detect)
        smart_row.addWidget(self.smart_toast)
        smart_row.addStretch(1)

        main = QVBoxLayout(self)
        main.addWidget(self.search)
        main.addLayout(smart_row)
        main.addWidget(self.list, 1)
        main.addLayout(row)

        # ---------------- 内部信号 → bus 转发 ----------------
        self.expr_detected.connect(self._forward_to_bus)

        # ---------------- 剪贴板监听 ----------------
        self._monitor = clipboard_monitor.ClipboardMonitor(self)

        cb = QApplication.clipboard()
        cb.dataChanged.connect(self._on_clipboard)
        self._last_text = ""
        self._refresh()

        if self.smart_detect.isChecked():
            QTimer.singleShot(0, self._start_monitor)

    # ==================================================================

    def _forward_to_bus(self, text):
        try:
            bus().clipboard_expr.emit(str(text))
        except Exception:
            pass

    def _on_smart_toggle(self, state):
        try:
            self.settings.set(
                "clipboard_smart_detect", bool(state))
        except Exception:
            pass
        if state:
            self._start_monitor()
        else:
            self._stop_monitor()

    def _start_monitor(self):
        try:
            self._monitor.start(self._on_expr_detected)
        except Exception:
            pass

    def _stop_monitor(self):
        try:
            self._monitor.stop()
        except Exception:
            pass

    def _on_expr_detected(self, text):
        if not self.smart_detect.isChecked():
            return
        try:
            self.expr_detected.emit(text)
        except Exception:
            pass

    def closeEvent(self, e):
        try:
            self._stop_monitor()
        except Exception:
            pass
        super().closeEvent(e)

    # ==================================================================

    def _on_clipboard(self):
        try:
            t = QApplication.clipboard().text()
        except Exception:
            return
        if not t or t == self._last_text:
            return
        self._last_text = t
        self._items.insert(0, {"text": t, "pinned": False})
        if len(self._items) > self.MAX:
            keep = [x for x in self._items if x["pinned"]]
            others = [x for x in self._items
                      if not x["pinned"]]
            others = others[: self.MAX - len(keep)]
            self._items = keep + others
        self._refresh()

    def _refresh(self):
        q = self.search.text().strip().lower()
        self.list.clear()
        for i, item in enumerate(self._items):
            text = item["text"]
            if q and q not in text.lower():
                continue
            star = "📌 " if item["pinned"] else ""
            preview = text.replace("\n", " ⏎ ")[:120]
            li = QListWidgetItem(f"{star}{preview}")
            li.setData(Qt.UserRole, i)
            self.list.addItem(li)

    def _current_index(self):
        it = self.list.currentItem()
        return it.data(Qt.UserRole) if it else None

    def _copy_current(self):
        i = self._current_index()
        if i is None:
            return
        QApplication.clipboard().setText(
            self._items[i]["text"])
        self._last_text = self._items[i]["text"]

    def _toggle_pin(self):
        i = self._current_index()
        if i is None:
            return
        self._items[i]["pinned"] = not self._items[i]["pinned"]
        self._refresh()

    def _clear(self):
        self._items = [x for x in self._items if x["pinned"]]
        self._refresh()


# ===========================================================================
# 笔记本
# ===========================================================================

class NotebookCellWidget(QFrame):
    """笔记本中的一个单元格。"""

    run_requested = Signal(int, bool)
    remove_requested = Signal(int)
    move_up_requested = Signal(int)
    move_down_requested = Signal(int)

    def __init__(self, index: int, cell: nb_mod.NotebookCell,
                 i18n, parent=None):
        super().__init__(parent)
        self.index = index
        self.cell = cell
        self.i18n = i18n
        self._exec_count_shown = cell.exec_count

        self.setFrameShape(QFrame.StyledPanel)
        self.setObjectName("NotebookCell")

        # ---------------- 序号 ----------------
        self.idx_label = QLabel(
            f"[{index + 1}]" if cell.kind == "code"
            else f"[{index + 1}] MD")
        self.idx_label.setFixedWidth(58)
        self.idx_label.setAlignment(
            Qt.AlignTop | Qt.AlignHCenter)
        f = self.idx_label.font()
        f.setFamily("Consolas")
        f.setPointSize(max(8, f.pointSize() - 1))
        self.idx_label.setFont(f)

        # ---------------- 编辑器 ----------------
        self.editor = QPlainTextEdit()
        self.editor.setPlainText(cell.source)
        self.editor.setMinimumHeight(60)
        self.editor.setMaximumHeight(200)
        self.editor.setPlaceholderText(i18n.t(
            "notebook_placeholder",
            "输入表达式；Shift+Enter 运行并跳到下一个"))
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.Monospace)
        mono.setPointSize(10)
        self.editor.setFont(mono)

        # ---------------- 按钮列 ----------------
        self._btn_col = QVBoxLayout()
        self._btn_col.setSpacing(2)
        b_run = QPushButton("▶")
        b_run.setFixedSize(28, 24)
        b_run.setToolTip("运行 (Shift+Enter)")
        b_run.clicked.connect(
            lambda: self.run_requested.emit(self.index, False))

        b_up = QPushButton("↑")
        b_up.setFixedSize(28, 24)
        b_up.setToolTip("上移")
        b_up.clicked.connect(
            lambda: self.move_up_requested.emit(self.index))

        b_down = QPushButton("↓")
        b_down.setFixedSize(28, 24)
        b_down.setToolTip("下移")
        b_down.clicked.connect(
            lambda: self.move_down_requested.emit(self.index))

        b_del = QPushButton("✕")
        b_del.setFixedSize(28, 24)
        b_del.setToolTip("删除")
        b_del.clicked.connect(
            lambda: self.remove_requested.emit(self.index))

        self._btn_col.addWidget(b_run)
        self._btn_col.addWidget(b_up)
        self._btn_col.addWidget(b_down)
        self._btn_col.addWidget(b_del)
        self._btn_col.addStretch(1)

        # ---------------- 输出 ----------------
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(28)
        self.output.setMaximumHeight(200)
        self.output.setFont(mono)
        self.output.setPlaceholderText("")
        self._refresh_output()

        # ---------------- 布局 ----------------
        top = QHBoxLayout()
        top.setContentsMargins(4, 4, 4, 4)
        top.addWidget(self.idx_label)
        top.addWidget(self.editor, 1)

        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.addLayout(top)
        col.addWidget(self.output)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addLayout(col, 1)
        row.addLayout(self._btn_col)

        if cell.kind == "markdown":
            self.output.setVisible(False)

    # ==================================================================

    def get_source(self) -> str:
        return self.editor.toPlainText()

    def _refresh_output(self):
        c = self.cell
        if c.error:
            self.output.setPlainText(f"✗ {c.error}")
            self.output.setStyleSheet("color: #ff6666;")
        elif c.result:
            prefix = (f"[{c.exec_count}] "
                      if c.exec_count else "")
            self.output.setPlainText(f"{prefix}{c.result}")
            self.output.setStyleSheet("color: #88ff88;")
        else:
            self.output.setPlainText("")
            self.output.setStyleSheet("")

    def update_from_cell(self):
        self.editor.blockSignals(True)
        if self.editor.toPlainText() != self.cell.source:
            self.editor.setPlainText(self.cell.source)
        self.editor.blockSignals(False)

        if self.cell.kind == "markdown":
            self.idx_label.setText(f"[{self.index + 1}] MD")
        else:
            self.idx_label.setText(f"[{self.index + 1}]")
        self._refresh_output()

    def keyPressEvent(self, event):
        key = event.key()
        mods = event.modifiers()
        if key in (Qt.Key_Return, Qt.Key_Enter):
            if mods & Qt.ShiftModifier:
                self.run_requested.emit(self.index, True)
                return
            if mods & Qt.ControlModifier:
                self.run_requested.emit(self.index, False)
                return
        super().keyPressEvent(event)


class NotebookPanel(CalcPanel):
    """数学笔记本面板：可折叠、可执行的 notebook 视图。"""

    module_key = "notebook"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        self.notebook = nb_mod.Notebook()
        self._cell_widgets: list = []

        # ---------------- 工具栏 ----------------
        b_new_code = QPushButton("+ Code")
        b_new_code.clicked.connect(lambda: self._add_cell("code"))
        b_new_md = QPushButton("+ Markdown")
        b_new_md.clicked.connect(
            lambda: self._add_cell("markdown"))
        b_run_all = QPushButton(
            i18n.t("notebook_run_all", "运行全部"))
        b_run_all.clicked.connect(self._run_all)
        b_clear_out = QPushButton(
            i18n.t("notebook_clear_outputs", "清空输出"))
        b_clear_out.clicked.connect(self._clear_outputs)
        b_save = QPushButton(i18n.t("save", "保存"))
        b_save.clicked.connect(self._save)
        b_load = QPushButton(i18n.t("open", "打开"))
        b_load.clicked.connect(self._load)
        b_export = QPushButton(
            i18n.t("notebook_export_ipynb", "导出 .ipynb"))
        b_export.clicked.connect(self._export_ipynb)
        b_new = QPushButton(i18n.t("notebook_new", "新建"))
        b_new.clicked.connect(self._new_notebook)

        toolbar = QHBoxLayout()
        for w in (b_new, b_new_code, b_new_md, b_run_all,
                  b_clear_out, b_save, b_load, b_export):
            toolbar.addWidget(w)
        toolbar.addStretch(1)
        toolbar.addWidget(self.make_kb_button())

        # ---------------- 标题栏 ----------------
        self.title_label = QLabel(
            i18n.t("notebook_untitled", "未命名笔记本"))
        self.title_label.setStyleSheet(
            "font-weight: bold; padding: 4px;")

        # ---------------- cell 容器 ----------------
        self._cell_container = QWidget()
        self._cell_layout = QVBoxLayout(self._cell_container)
        self._cell_layout.setContentsMargins(4, 4, 4, 4)
        self._cell_layout.setSpacing(6)
        self._cell_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._cell_container)

        # ---------------- 结果视图 ----------------
        self.result = ResultView(i18n)
        self.result.setMaximumHeight(120)

        self.status = QLabel("")
        self.status.setStyleSheet("color: #888; padding: 2px;")

        # ---------------- 布局 ----------------
        main = QVBoxLayout(self)
        main.addLayout(toolbar)
        main.addWidget(self.title_label)
        main.addWidget(scroll, 1)
        main.addWidget(self.status)

        self._install_shortcuts()
        self._rebuild_cells()

        self.primary_input = None
        self._sync_primary_input()

    # ==================================================================
    # 快捷键
    # ==================================================================

    def _install_shortcuts(self):
        sc_run_all = QShortcut(
            QKeySequence("Ctrl+Shift+Return"), self)
        sc_run_all.setContext(Qt.WidgetWithChildrenShortcut)
        sc_run_all.activated.connect(self._run_all)

        sc_save = QShortcut(QKeySequence("Ctrl+S"), self)
        sc_save.setContext(Qt.WidgetWithChildrenShortcut)
        sc_save.activated.connect(self._save)

        sc_new_code = QShortcut(
            QKeySequence("Ctrl+Shift+C"), self)
        sc_new_code.setContext(Qt.WidgetWithChildrenShortcut)
        sc_new_code.activated.connect(
            lambda: self._add_cell("code"))

        sc_new_md = QShortcut(
            QKeySequence("Ctrl+Shift+M"), self)
        sc_new_md.setContext(Qt.WidgetWithChildrenShortcut)
        sc_new_md.activated.connect(
            lambda: self._add_cell("markdown"))

    # ==================================================================
    # 视图刷新
    # ==================================================================

    def _rebuild_cells(self):
        while self._cell_layout.count() > 1:
            item = self._cell_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._cell_widgets = []

        for i, cell in enumerate(self.notebook.cells):
            w = NotebookCellWidget(i, cell, self.i18n, self)
            w.run_requested.connect(self._on_run)
            w.remove_requested.connect(self._on_remove)
            w.move_up_requested.connect(self._on_move_up)
            w.move_down_requested.connect(self._on_move_down)
            w.editor.textChanged.connect(
                lambda idx=i, ww=w: self._on_cell_edited(
                    idx, ww))
            self._cell_layout.insertWidget(
                self._cell_layout.count() - 1, w)
            self._cell_widgets.append(w)

        self._sync_primary_input()
        self._update_title()

    def _update_title(self):
        name = (os.path.basename(self.notebook.path)
                if self.notebook.path
                else self.i18n.t("notebook_untitled",
                                 "未命名笔记本"))
        n = len(self.notebook.cells)
        self.title_label.setText(f"📓 {name}   ({n} cells)")

    def _sync_primary_input(self):
        for w in self._cell_widgets:
            if w.cell.kind == "code":
                self.primary_input = w.editor
                return
        self.primary_input = None

    def _on_cell_edited(self, idx, widget):
        if 0 <= idx < len(self.notebook.cells):
            self.notebook.cells[idx].source = widget.get_source()

    # ==================================================================
    # cell 操作
    # ==================================================================

    def _add_cell(self, kind: str = "code"):
        idx = len(self.notebook.cells)
        self.notebook.add_cell(kind=kind)
        cell = self.notebook.cells[idx]
        w = NotebookCellWidget(idx, cell, self.i18n, self)
        w.run_requested.connect(self._on_run)
        w.remove_requested.connect(self._on_remove)
        w.move_up_requested.connect(self._on_move_up)
        w.move_down_requested.connect(self._on_move_down)
        w.editor.textChanged.connect(
            lambda i=idx, ww=w: self._on_cell_edited(i, ww))
        self._cell_layout.insertWidget(
            self._cell_layout.count() - 1, w)
        self._cell_widgets.append(w)
        self._sync_primary_input()
        self._update_title()
        w.editor.setFocus()

    def _on_remove(self, idx):
        if len(self.notebook.cells) <= 1:
            self.notebook.cells[0].source = ""
            self.notebook.cells[0].result = ""
            self.notebook.cells[0].error = ""
            self._rebuild_cells()
            return
        self.notebook.remove_cell(idx)
        self._rebuild_cells()

    def _on_move_up(self, idx):
        if idx <= 0:
            return
        self.notebook.move_cell(idx, idx - 1)
        self._rebuild_cells()

    def _on_move_down(self, idx):
        if idx >= len(self.notebook.cells) - 1:
            return
        self.notebook.move_cell(idx, idx + 1)
        self._rebuild_cells()

    def _clear_outputs(self):
        self.notebook.clear_outputs()
        for w in self._cell_widgets:
            w.update_from_cell()
        self.result.show_result("", "")

    # ==================================================================
    # 执行
    # ==================================================================

    def _on_run(self, idx: int, advance: bool):
        if not (0 <= idx < len(self.notebook.cells)):
            return
        cell = self.notebook.cells[idx]
        if cell.kind == "markdown":
            if advance and idx + 1 < len(self._cell_widgets):
                self._cell_widgets[idx + 1].editor.setFocus()
            return

        if idx < len(self._cell_widgets):
            cell.source = self._cell_widgets[idx].get_source()

        src = cell.source.strip()
        if not src:
            cell.result = ""
            cell.error = ""
            self._refresh_one(idx)
            return

        angle = self._angle_mode()
        started = time.time()
        try:
            val = engine.sci_eval(src, angle)
            try:
                text = engine.format_result(val, "text")
            except Exception:
                text = str(val)
            cell.result = text
            cell.error = ""
            cell.exec_count += 1
            self.add_history(src, text, module="notebook")
        except CalcError as e:
            cell.result = ""
            cell.error = e.message or str(e)
        except Exception as e:  # noqa: BLE001
            cell.result = ""
            cell.error = f"{type(e).__name__}: {e}"

        elapsed = time.time() - started
        self._refresh_one(idx)
        self._update_status(idx, elapsed)

        if advance and idx + 1 < len(self._cell_widgets):
            self._cell_widgets[idx + 1].editor.setFocus()

    def _run_all(self):
        for i, w in enumerate(self._cell_widgets):
            if i < len(self.notebook.cells):
                self.notebook.cells[i].source = w.get_source()

        n_ok = 0
        n_err = 0
        for i, cell in enumerate(self.notebook.cells):
            if cell.kind != "code" or not cell.source.strip():
                continue
            self._on_run(i, advance=False)
            if cell.error:
                n_err += 1
            else:
                n_ok += 1

        self.status.setText(
            self.i18n.t("notebook_done",
                        "完成：成功 {ok}，失败 {err}")
            .format(ok=n_ok, err=n_err))

    def _refresh_one(self, idx: int):
        if 0 <= idx < len(self._cell_widgets):
            self._cell_widgets[idx].update_from_cell()

    def _update_status(self, idx: int, elapsed: float):
        self.status.setText(
            f"cell [{idx + 1}] ⏱ {elapsed:.3f}s")

    # ==================================================================
    # 文件操作
    # ==================================================================

    def _new_notebook(self):
        self.notebook = nb_mod.Notebook()
        self._rebuild_cells()
        self.result.show_result("", "")
        self.status.setText(
            self.i18n.t("notebook_new_done", "已新建"))

    def _save(self):
        for i, w in enumerate(self._cell_widgets):
            if i < len(self.notebook.cells):
                self.notebook.cells[i].source = w.get_source()

        path = self.notebook.path
        if not path:
            path, _ = QFileDialog.getSaveFileName(
                self, self.i18n.t("save", "保存"),
                "notebook.mcnb",
                "MultiCalc Notebook (*.mcnb);;JSON (*.json)")
            if not path:
                return
        try:
            self.notebook.save(path)
            self._update_title()
            self.status.setText(path)
            try:
                ud.recent_add(path, kind="notebook")
            except Exception:
                pass
            try:
                from ui.shell import toast
                toast(self.window(), path, level="success")
            except Exception:
                pass
        except Exception as e:
            log_exc(e, module="NotebookPanel._save")
            QMessageBox.warning(self, "Error", str(e))

    def _load(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self.i18n.t("open", "打开"), "",
            "Notebook (*.mcnb *.ipynb);;All Files (*)")
        if not path:
            return
        self._load_path(path)

    def _load_path(self, path: str):
        """加载指定路径的 notebook。"""
        try:
            self.notebook = nb_mod.Notebook.load(path)
            self._rebuild_cells()
            self.result.show_result("", "")
            self.status.setText(path)
            try:
                ud.recent_add(path, kind="notebook")
            except Exception:
                pass
        except Exception as e:
            log_exc(e, module="NotebookPanel._load_path")
            QMessageBox.warning(self, "Error", str(e))

    def _export_ipynb(self):
        for i, w in enumerate(self._cell_widgets):
            if i < len(self.notebook.cells):
                self.notebook.cells[i].source = w.get_source()

        path, _ = QFileDialog.getSaveFileName(
            self,
            self.i18n.t("notebook_export_ipynb", "导出 .ipynb"),
            "notebook.ipynb",
            "Jupyter Notebook (*.ipynb)")
        if not path:
            return
        try:
            self.notebook.export_ipynb(path)
            self.status.setText(path)
            try:
                from ui.shell import toast
                toast(self.window(), path, level="success")
            except Exception:
                pass
        except Exception as e:
            log_exc(e, module="NotebookPanel._export_ipynb")
            QMessageBox.warning(self, "Error", str(e))

    # ==================================================================

    def _angle_mode(self) -> str:
        try:
            return self.settings.get(
                "angle_mode", "RAD") or "RAD"
        except Exception:
            return "RAD"

    def _clear(self):
        try:
            fw = QApplication.focusWidget()
            if isinstance(fw, QPlainTextEdit):
                fw.clear()
        except Exception:
            pass

    def on_settings_changed(self, key=None):
        pass

    def set_theme_colors(self, fg, bg, panel):
        pass


# ===========================================================================
# 脚本 / 批量计算
# ===========================================================================

class ScriptPanel(CalcPanel):
    """脚本 / 批量计算面板：多行表达式顺序执行。"""

    module_key = "script"

    SAMPLE = (
        "# 每行一个表达式；# 开头或行尾 ' #' 为注释\n"
        "a = 3\n"
        "b = 4\n"
        "sqrt(a^2 + b^2)\n"
        "\n"
        "100 的 15%  # 脚本中暂不支持百分比语法，"
        "请用 100 * 15 / 100\n"
        "100 * 15 / 100\n"
        "sin(pi / 6)\n"
        "factorial(5)\n"
    )

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText(self.SAMPLE)
        self.editor.setPlainText(self.SAMPLE)
        self.primary_input = self.editor

        self.run_btn = QPushButton(
            i18n.t("script_run", "运行全部"))
        self.run_btn.clicked.connect(self.run_script)

        self.clear_btn = QPushButton(i18n.t("clear", "清空"))
        self.clear_btn.clicked.connect(self._clear)

        self.export_btn = QPushButton(
            i18n.t("script_export_csv", "导出结果 CSV"))
        self.export_btn.clicked.connect(self._export_csv)

        # ---------------- 结果表 ----------------
        self.result_table = QTableWidget(0, 3)
        self.result_table.setHorizontalHeaderLabels([
            i18n.t("script_line", "行"),
            i18n.t("script_expr", "表达式"),
            i18n.t("result", "结果"),
        ])
        hdr = self.result_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        self.result_table.setSelectionBehavior(
            QTableWidget.SelectRows)

        self.status = QLabel("")
        self.status.setStyleSheet("color: #888;")

        row = QHBoxLayout()
        for b in (self.run_btn, self.clear_btn,
                  self.export_btn):
            row.addWidget(b)
        row.addStretch(1)

        top = QWidget()
        tv = QVBoxLayout(top)
        tv.setContentsMargins(0, 0, 0, 0)
        tv.addWidget(QLabel(
            i18n.t("script_source", "脚本源码")))
        tv.addWidget(self.editor, 1)

        bottom = QWidget()
        bv = QVBoxLayout(bottom)
        bv.setContentsMargins(0, 0, 0, 0)
        bv.addWidget(QLabel(i18n.t("script_results", "结果")))
        bv.addWidget(self.result_table, 1)

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(top)
        splitter.addWidget(bottom)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        main = QVBoxLayout(self)
        main.addWidget(splitter, 1)
        main.addLayout(row)
        main.addWidget(self.status)

    # ==================================================================

    def _angle_mode(self) -> str:
        try:
            return self.settings.get(
                "angle_mode", "RAD") or "RAD"
        except Exception:
            return "RAD"

    def run_script(self):
        self.result_table.setRowCount(0)
        text = self.editor.toPlainText()
        angle = self._angle_mode()

        n_ok = 0
        n_err = 0
        for lineno, line in enumerate(text.splitlines(), 1):
            raw = line.rstrip()
            s = raw.strip()
            if not s or s.startswith("#"):
                continue
            if " #" in s:
                s = s.split(" #", 1)[0].strip()
                if not s:
                    continue
            try:
                r = engine.sci_eval(s, angle)
                try:
                    out = engine.format_result(r, "text")
                except Exception:
                    out = str(r)
                self._add_row(lineno, s, out)
                n_ok += 1
            except Exception as e:
                msg = friendly_error(self.i18n, e, "script")
                self._add_row(lineno, s, f"⚠ {msg}")
                n_err += 1

        tmpl = self.i18n.t(
            "script_done", "完成：成功 {ok}，失败 {err}")
        try:
            self.status.setText(
                tmpl.format(ok=n_ok, err=n_err))
        except Exception:
            self.status.setText(
                f"完成：成功 {n_ok}，失败 {n_err}")

        try:
            self.add_history(
                f"script:{n_ok}lines",
                f"ok={n_ok} err={n_err}", module="script")
        except Exception:
            pass

    def _add_row(self, lineno, expr, result):
        r = self.result_table.rowCount()
        self.result_table.insertRow(r)
        self.result_table.setItem(
            r, 0, QTableWidgetItem(str(lineno)))
        self.result_table.setItem(
            r, 1, QTableWidgetItem(expr))
        self.result_table.setItem(
            r, 2, QTableWidgetItem(result))

    def _clear(self):
        self.result_table.setRowCount(0)
        self.status.setText("")

    def _export_csv(self):
        if self.result_table.rowCount() == 0:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "script_results.csv",
            "CSV (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8-sig",
                      newline="") as f:
                w = _csv.writer(f)
                w.writerow(["line", "expr", "result"])
                for r in range(self.result_table.rowCount()):
                    row = []
                    for c in range(3):
                        it = self.result_table.item(r, c)
                        row.append(it.text() if it else "")
                    w.writerow(row)
            self.status.setText(path)
        except Exception as e:
            log_exc(e, module="ScriptPanel._export_csv")
            QMessageBox.warning(self, "Error", str(e))