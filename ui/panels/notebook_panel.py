"""数学笔记本面板：可折叠、可执行的 notebook 视图。

变更历史：
- 第 6 轮：新增
"""
from __future__ import annotations

import os
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QFont
from PySide6.QtWidgets import (
    QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QComboBox, QFileDialog, QMessageBox, QScrollArea, QWidget,
    QFrame, QApplication, QInputDialog, QSizePolicy,
)

from core import notebook as nb_mod
from core import engine
from core import symbols as sym_mod
from core.errors import InputError, CalcError
from core.logger import log_exc
from ._common import ResultView, friendly_error
from .base import CalcPanel


# ===========================================================================
# 单个 cell
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


# ===========================================================================
# 主面板
# ===========================================================================

class NotebookPanel(CalcPanel):
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
                from ui.toast import toast
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
        except Exception as e:
            log_exc(e, module="NotebookPanel._load_path")
            QMessageBox.warning(self, "Error", str(e))

    def _export_ipynb(self):
        for i, w in enumerate(self._cell_widgets):
            if i < len(self.notebook.cells):
                self.notebook.cells[i].source = w.get_source()

        path, _ = QFileDialog.getSaveFileName(
            self,
            self.i18n.t("notebook_export_ipynb",
                        "导出 .ipynb"),
            "notebook.ipynb",
            "Jupyter Notebook (*.ipynb)")
        if not path:
            return
        try:
            self.notebook.export_ipynb(path)
            self.status.setText(path)
            try:
                from ui.toast import toast
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


__all__ = ["NotebookPanel"]