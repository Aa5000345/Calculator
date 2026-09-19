"""绘图 / 3D 绘图 / 管道 / LaTeX 编辑器面板。

合并自：ui/panels/plot.py + ui/panels/plot3d.py
        + ui/panels/pipeline_panel.py + ui/panels/latex_editor.py

对外接口（类名保持不变，老 registry.py 无需改动）：
    PlotPanel
    Plot3DPanel
    PipelinePanel
    LatexEditorPanel

依赖（合并后）：
    core.base       —— InputError / log_exc
    core.engine     —— sci_diff / sci_integrate / _parse
    core.plot       —— 所有 sample_* / parse_lambda2 /
                        sample_fill_between / apply_fill_between /
                        add_twin_axis / plot_xy_from_lists /
                        save_polar_gif
    core.notebook   —— execute_pipeline / has_pipe / PipelineResult
    core.latex      —— TEMPLATES / render_png / render_svg /
                        latex_to_expr
    core.rates      —— ensure_fresh / convert（PipelinePanel 货币）
    ui.dialogs      —— LatexLabel
    ui.shell        —— bus
    ui.shortcuts    —— install_panel_shortcuts
    ui.panels.base       —— CalcPanel
    ui.panels._common    —— ResultView / InlinePreviewBar /
                            friendly_error

修复记录（本轮）：
- PipelinePanel：`from core import pipeline as pipe_mod`
  → `from core import notebook as nb_mod`（pipeline 已合并进
  core.notebook）。
- LaTeX 相关：`latex_ext` / `latex_parser` 合并为 `core.latex`。
- PlotPanel / Plot3DPanel：`plot_advanced` / `plot_sample`
  合并为 `core.plot`。
- `ui.latex_widget` → `ui.dialogs`。
- `ui.signals.bus` → `ui.shell.bus`。
- `ui.widgets.plot_animation_widget` → `ui.widgets.tools`。
- `ui.widgets.input_history_widget` → `ui.widgets.input`（延迟导入）。
"""
from __future__ import annotations

import os
import time

import numpy as np
import sympy as sp
from matplotlib.backends.backend_qtagg import (
    FigureCanvasQTAgg as FigureCanvas,
)
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QColorDialog, QComboBox,
    QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QHBoxLayout, QHeaderView, QInputDialog,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QScrollArea, QSizePolicy, QSpinBox,
    QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from core import engine
from core import plot as plot_mod
from core import notebook as nb_mod
from core import latex as latex_mod
from core import rates as rates_mod
from core.base import InputError, log_exc
from ui.dialogs import LatexLabel
from ui.shortcuts import install_panel_shortcuts
from ui.shell import bus
from ._common import (
    ResultView,
    InlinePreviewBar,
    friendly_error,
)
from .base import CalcPanel


__all__ = [
    "PlotPanel",
    "Plot3DPanel",
    "PipelinePanel",
    "LatexEditorPanel",
]


# ===========================================================================
# 2D 绘图
# ===========================================================================

class PlotPanel(CalcPanel):
    """2D 绘图面板。

    支持 Cartesian / Polar / Parametric / Implicit / Integral /
    Fill between；多曲线、多 Y 轴、LaTeX 标签、从数据表导入、
    极坐标动画。
    """

    module_key = "plot"

    COLS = 6
    PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
               "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
               "#bcbd22", "#17becf"]
    KINDS = ["cartesian", "polar", "parametric", "implicit",
             "integral", "fill_between"]

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)
        self._color_index = 0
        self._fg = "#ffffff"
        self._bg = "#1e1e1e"
        self._panel = "#2d2d30"

        # ---------------- 表格 ----------------
        self.table = QTableWidget(0, self.COLS)
        self.table.setHorizontalHeaderLabels([
            i18n.t("curve_expr", "Expression"),
            i18n.t("curve_kind", "Type"),
            i18n.t("curve_expr2", "Y / 2nd"),
            i18n.t("curve_start", "From"),
            i18n.t("curve_end", "To"),
            i18n.t("curve_color", "Color"),
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectRows)
        self.table.setFixedHeight(170)

        # ---------------- 按钮 ----------------
        self.btn_add = QPushButton(
            i18n.t("add_curve", "Add curve"))
        self.btn_del = QPushButton(
            i18n.t("remove_curve", "Remove"))
        self.btn_clr = QPushButton(
            i18n.t("clear_curves", "Clear all"))
        self.btn_plot = QPushButton(i18n.t("draw", "Plot"))
        self.btn_export = QPushButton(i18n.t("export", "Export"))
        self.btn_polar_anim = QPushButton(
            i18n.t("plot_polar_animation", "极坐标动画…"))
        self.btn_from_table = QPushButton(
            i18n.t("plot_from_table", "从数据表导入…"))

        self.btn_add.clicked.connect(lambda: self.add_curve())
        self.btn_del.clicked.connect(self.remove_curve)
        self.btn_clr.clicked.connect(self.clear_curves)
        self.btn_plot.clicked.connect(self.plot)
        self.btn_export.clicked.connect(self.export)
        self.btn_polar_anim.clicked.connect(self._open_polar_anim)
        self.btn_from_table.clicked.connect(
            self._import_from_table)

        # ---------------- 选项 ----------------
        self.grid_chk = QCheckBox(i18n.t("show_grid", "Grid"))
        self.grid_chk.setChecked(True)
        self.legend_chk = QCheckBox(
            i18n.t("show_legend", "Legend"))
        self.legend_chk.setChecked(True)
        self.deriv_chk = QCheckBox(
            i18n.t("show_derivative", "Show derivative"))
        self.interact_chk = QCheckBox(
            i18n.t("interactive", "Interactive pan/zoom"))
        self.interact_chk.setChecked(True)
        self.latex_chk = QCheckBox(
            i18n.t("latex_labels", "LaTeX 标签"))
        self.latex_chk.setChecked(
            bool(settings.get("plot_latex_labels", False)))
        self.latex_chk.stateChanged.connect(
            lambda _: settings.set(
                "plot_latex_labels",
                self.latex_chk.isChecked()))

        self.twin_chk = QCheckBox(
            i18n.t("plot_twin_axis", "启用右 Y 轴"))
        self.twin_chk.setChecked(
            bool(settings.get("plot_twin_axis", False)))
        self.twin_chk.stateChanged.connect(
            lambda _: settings.set(
                "plot_twin_axis", self.twin_chk.isChecked()))

        # ---------------- 画布 ----------------
        self.figure = Figure(figsize=(6, 4))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding)

        # ---------------- 顶栏 ----------------
        top = QHBoxLayout()
        top.addWidget(self.btn_add)
        top.addWidget(self.btn_del)
        top.addWidget(self.btn_clr)
        top.addStretch(1)
        top.addWidget(self.btn_from_table)
        top.addWidget(self.btn_polar_anim)
        top.addWidget(self.btn_plot)
        top.addWidget(self.btn_export)

        opts = QHBoxLayout()
        for w in (self.grid_chk, self.legend_chk,
                  self.deriv_chk, self.interact_chk,
                  self.latex_chk, self.twin_chk):
            opts.addWidget(w)
        opts.addStretch(1)

        # ---------------- 布局 ----------------
        splitter = QSplitter(Qt.Vertical)
        upper = QWidget()
        ul = QVBoxLayout(upper)
        ul.setContentsMargins(0, 0, 0, 0)
        ul.addWidget(self.table)
        ul.addLayout(top)
        ul.addLayout(opts)
        splitter.addWidget(upper)
        splitter.addWidget(self.canvas)
        splitter.setStretchFactor(1, 1)

        main = QVBoxLayout(self)
        main.addWidget(splitter)

        self.add_curve("sin(x)", "cartesian", "-10", "10")
        self.add_curve("cos(x)", "cartesian", "-10", "10")

    # ==================================================================

    def _safe_label(self, expr: str) -> str:
        s = (expr or "").strip()
        if not s:
            return s
        if not self.latex_chk.isChecked():
            return s
        return f"${s}$"

    def _next_color(self):
        c = self.PALETTE[self._color_index
                         % len(self.PALETTE)]
        self._color_index += 1
        return c

    def add_curve(self, expr="", kind="cartesian",
                  start="-10", end="10"):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(expr))

        combo = QComboBox()
        for k in self.KINDS:
            combo.addItem(self.i18n.t(f"kind_{k}", k), k)
        idx = (self.KINDS.index(kind)
               if kind in self.KINDS else 0)
        combo.setCurrentIndex(idx)
        self.table.setCellWidget(row, 1, combo)

        self.table.setItem(
            row, 2,
            QTableWidgetItem(
                "t" if kind == "parametric" else ""))
        self.table.setItem(row, 3, QTableWidgetItem(start))
        self.table.setItem(row, 4, QTableWidgetItem(end))

        color = self._next_color()
        btn = QPushButton()
        btn.setProperty("color", color)
        btn.setStyleSheet(
            f"background:{color};border:1px solid #888;"
            f"border-radius:4px;")
        btn.setToolTip(color)
        btn.clicked.connect(
            lambda _, b=btn: self._pick_color(b))
        self.table.setCellWidget(row, 5, btn)

    def remove_curve(self):
        rows = sorted(
            {i.row() for i in self.table.selectedIndexes()},
            reverse=True)
        if not rows and self.table.rowCount():
            rows = [self.table.rowCount() - 1]
        for r in rows:
            self.table.removeRow(r)

    def clear_curves(self):
        self.table.setRowCount(0)

    def _pick_color(self, btn):
        cur = QColor(btn.property("color") or "#1f77b4")
        c = QColorDialog.getColor(cur, self)
        if c.isValid():
            btn.setProperty("color", c.name())
            btn.setStyleSheet(
                f"background:{c.name()};"
                f"border:1px solid #888;border-radius:4px;")
            btn.setToolTip(c.name())

    def _cell(self, row, col):
        it = self.table.item(row, col)
        return it.text().strip() if it else ""

    # ==================================================================
    # 绘图
    # ==================================================================

    def plot(self):
        try:
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            ax.set_facecolor(self._panel)
            self.figure.patch.set_facecolor(self._bg)
            ax.tick_params(colors=self._fg)
            for sp_ in ax.spines.values():
                sp_.set_color(self._fg)

            ax2 = None
            twin_enabled = self.twin_chk.isChecked()

            errors = []
            plotted = 0
            implicit = []

            for row in range(self.table.rowCount()):
                expr = self._cell(row, 0)
                if not expr:
                    continue
                widget = self.table.cellWidget(row, 1)
                kind = (widget.currentData()
                        if widget else "cartesian")
                expr2 = self._cell(row, 2)
                start = self._cell(row, 3) or "-10"
                end = self._cell(row, 4) or "10"
                cbtn = self.table.cellWidget(row, 5)
                color = ((cbtn.property("color")
                          if cbtn else None)
                         or self.PALETTE[0])

                try:
                    if kind == "cartesian":
                        xs, ys = plot_mod.sample_cartesian(
                            expr, start, end)
                        finite = np.isfinite(ys)
                        if finite.sum() < 5:
                            errors.append(
                                f"row {row + 1}: "
                                + self.i18n.t(
                                    "err_plot_empty_domain",
                                    "Empty domain"))
                            continue
                        ax.plot(xs, ys, color=color,
                                linewidth=1.6,
                                label=self._safe_label(expr))
                        plotted += 1
                        if self.deriv_chk.isChecked():
                            try:
                                dx = engine.sci_diff(expr, "x", 1)
                                xsd, ysd = \
                                    plot_mod.sample_cartesian(
                                        str(dx), start, end)
                                ax.plot(xsd, ysd, color=color,
                                        linestyle="--",
                                        linewidth=1.2, alpha=0.75,
                                        label=self._safe_label(
                                            f"d/dx({expr})"))
                            except Exception as ee:
                                errors.append(
                                    f"d/dx row {row + 1}: {ee}")
                    elif kind == "polar":
                        xs, ys = plot_mod.sample_polar(
                            expr, start, end)
                        ax.plot(xs, ys, color=color,
                                linewidth=1.6,
                                label=self._safe_label(
                                    f"r = {expr}"))
                        plotted += 1
                    elif kind == "parametric":
                        ys_expr = expr2 or "t"
                        xs, ys = plot_mod.sample_parametric(
                            expr, ys_expr, start, end)
                        ax.plot(xs, ys, color=color,
                                linewidth=1.6,
                                label=self._safe_label(
                                    f"({expr}, {ys_expr})"))
                        plotted += 1
                    elif kind == "implicit":
                        implicit.append(
                            (expr, color, (start, end)))
                    elif kind == "integral":
                        try:
                            F = engine.sci_integrate(expr, "x")
                            xs, ys = plot_mod.sample_cartesian(
                                str(F), start, end)
                            ax.plot(xs, ys, color=color,
                                    linewidth=1.4,
                                    linestyle=":",
                                    label=self._safe_label(
                                        f"∫({expr})dx"))
                            plotted += 1
                        except Exception as ee:
                            errors.append(
                                f"∫ row {row + 1}: {ee}")
                    elif kind == "fill_between":
                        lo_expr = expr2 or "0"
                        try:
                            xs, yf, yg = \
                                plot_mod.sample_fill_between(
                                    expr, lo_expr,
                                    float(start), float(end),
                                    points=400)
                            plot_mod.apply_fill_between(
                                ax, xs, yf, yg,
                                color=color, alpha=0.35,
                                label=self._safe_label(
                                    f"{expr} vs {lo_expr}"))
                            plotted += 1
                        except Exception as ee:
                            errors.append(
                                f"fill row {row + 1}: {ee}")
                except Exception as e:
                    log_exc(e, module=f"PlotPanel.row{row + 1}")
                    errors.append(f"row {row + 1}: {e}")

            if twin_enabled and plotted >= 2:
                try:
                    ax2 = plot_mod.add_twin_axis(
                        self.figure, ax,
                        ylabel="Y2", color=self.PALETTE[1])
                except Exception as ee:
                    errors.append(f"twin: {ee}")

            if implicit:
                for expr_text, color, (xr, yr) in implicit:
                    try:
                        x = np.linspace(
                            float(xr), float(yr), 300)
                        y = np.linspace(
                            float(xr), float(yr), 300)
                        X, Y = np.meshgrid(x, y)
                        Z = plot_mod.parse_lambda2(
                            expr_text)(X, Y)
                        ax.contour(X, Y, Z, levels=[0],
                                   colors=[color],
                                   linewidths=1.6)
                        plotted += 1
                    except Exception as ee:
                        errors.append(
                            f"implicit {expr_text}: {ee}")

            if plotted == 0 and not errors:
                ax.text(0.5, 0.5, "No curve", ha="center",
                        va="center", color=self._fg,
                        transform=ax.transAxes)
            if errors:
                ax.text(0.02, 0.98, "\n".join(errors[:4]),
                        ha="left", va="top", color="#ff5555",
                        fontsize=9, transform=ax.transAxes)

            ax.grid(self.grid_chk.isChecked(), color="#666666",
                    alpha=0.4, linewidth=0.6)
            if self.legend_chk.isChecked() and plotted:
                leg = ax.legend(
                    facecolor=self._panel,
                    edgecolor=self._fg, fontsize=8)
                for t in leg.get_texts():
                    t.set_color(self._fg)
            if ax2 is not None:
                try:
                    leg2 = ax2.legend(
                        facecolor=self._panel,
                        edgecolor=self._fg,
                        fontsize=8, loc="upper right")
                    for t in leg2.get_texts():
                        t.set_color(self._fg)
                except Exception:
                    pass

            try:
                self.figure.tight_layout()
            except Exception:
                pass

            try:
                from matplotlib.backends.backend_qtagg import (
                    NavigationToolbar2QT,
                )
                if self.interact_chk.isChecked():
                    if not hasattr(self, "_nav"):
                        self._nav = NavigationToolbar2QT(
                            self.canvas, self)
                    self._nav.setVisible(True)
                else:
                    if hasattr(self, "_nav"):
                        self._nav.setVisible(False)
            except Exception:
                pass

            self.canvas.draw()
            self.add_history(
                f"{plotted} curve(s)", "plotted",
                module="plot")
        except Exception as e:
            log_exc(e, module="PlotPanel.plot")

    # ==================================================================
    # 导出
    # ==================================================================

    def export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, self.i18n.t("export", "Export"),
            "plot.png",
            "PNG (*.png);;PDF (*.pdf);;SVG (*.svg)")
        if not path:
            return
        try:
            self.figure.savefig(
                path, dpi=150, bbox_inches="tight",
                facecolor=self._bg)
            QMessageBox.information(self, "OK", path)
        except Exception as e:
            log_exc(e, module="PlotPanel.export")
            QMessageBox.warning(self, "Error", str(e))

    # ==================================================================
    # 极坐标动画
    # ==================================================================

    def _open_polar_anim(self):
        try:
            from ui.widgets.tools import PolarAnimationWidget
            dlg = QDialog(self)
            dlg.setWindowTitle(self.i18n.t(
                "plot_polar_animation", "极坐标动画"))
            dlg.resize(520, 620)
            w = PolarAnimationWidget(dlg)
            lay = QVBoxLayout(dlg)
            lay.addWidget(w)
            dlg.exec()
        except Exception as e:
            log_exc(e, module="PlotPanel._open_polar_anim")
            QMessageBox.warning(self, "Error", str(e))

    # ==================================================================
    # 从数据表导入
    # ==================================================================

    def _import_from_table(self):
        try:
            mw = self.window()
            panel = getattr(mw, "_panels", {}).get("data_table")
            if panel is None:
                QMessageBox.information(
                    self, "提示", "找不到数据表面板")
                return
            table = getattr(panel, "table", None)
            if table is None or table.rowCount() == 0:
                QMessageBox.information(
                    self, "提示", "数据表为空")
                return

            xs, ys = [], []
            for r in range(table.rowCount()):
                it_x = table.item(r, 0)
                it_y = table.item(r, 1)
                if it_x is None or it_y is None:
                    continue
                try:
                    x = float(it_x.text())
                    y = float(it_y.text())
                except (TypeError, ValueError):
                    continue
                xs.append(x)
                ys.append(y)

            if len(xs) < 2:
                QMessageBox.information(
                    self, "提示",
                    "至少需要两行数值数据（A、B 两列）")
                return

            self.figure.clear()
            ax = self.figure.add_subplot(111)
            ax.set_facecolor(self._panel)
            self.figure.patch.set_facecolor(self._bg)
            ax.tick_params(colors=self._fg)
            for sp_ in ax.spines.values():
                sp_.set_color(self._fg)
            plot_mod.plot_xy_from_lists(
                ax, xs, ys,
                color=self.PALETTE[0],
                kind="line+marker",
                label="from data table")
            ax.grid(True, color="#666", alpha=0.4, linewidth=0.6)
            try:
                self.figure.tight_layout()
            except Exception:
                pass
            self.canvas.draw()
            self.add_history(
                f"table {len(xs)} points", "plotted",
                module="plot")
        except Exception as e:
            log_exc(e, module="PlotPanel._import_from_table")
            QMessageBox.warning(self, "Error", str(e))

    # ==================================================================

    def set_theme_colors(self, fg, bg, panel):
        self._fg, self._bg, self._panel = fg, bg, panel
        try:
            self.plot()
        except Exception as e:
            log_exc(e, module="PlotPanel.set_theme_colors")


# ===========================================================================
# 3D 绘图
# ===========================================================================

class Plot3DPanel(CalcPanel):
    """3D 绘图面板。"""

    module_key = "plot3d"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        self.expr = QLineEdit("sin(x)*cos(y)")
        self.primary_input = self.expr
        self.xmin = QLineEdit("-5")
        self.xmax = QLineEdit("5")
        self.ymin = QLineEdit("-5")
        self.ymax = QLineEdit("5")
        self.frames = QSpinBox()
        self.frames.setRange(2, 300)
        self.frames.setValue(60)
        self.fps = QSpinBox()
        self.fps.setRange(1, 60)
        self.fps.setValue(20)

        self.cmap = QComboBox()
        for k in ("viridis", "plasma", "inferno", "magma",
                  "cividis", "jet", "coolwarm", "RdBu",
                  "turbo", "terrain"):
            self.cmap.addItem(k)
        self.show_contour = QCheckBox(
            i18n.t("show_contour", "Contour"))
        self.contour_levels = QSpinBox()
        self.contour_levels.setRange(3, 40)
        self.contour_levels.setValue(10)
        self.show_slice = QCheckBox(
            i18n.t("show_slice", "Slice at y=0"))
        self.auto_rotate = QCheckBox(
            i18n.t("auto_rotate", "Auto rotate"))
        self.rotate_speed = QSpinBox()
        self.rotate_speed.setRange(1, 30)
        self.rotate_speed.setValue(5)

        self.plot_btn = QPushButton(i18n.t("draw", "Plot"))
        self.anim_btn = QPushButton(i18n.t("start_anim", "Play"))
        self.stop_btn = QPushButton(i18n.t("stop_anim", "Stop"))
        self.stop_btn.setEnabled(False)
        self.export_btn = QPushButton(i18n.t("export", "Export"))
        self.export_gif_btn = QPushButton(
            i18n.t("export_gif", "Export GIF"))

        self.plot_btn.clicked.connect(self.plot)
        self.anim_btn.clicked.connect(self.start_anim)
        self.stop_btn.clicked.connect(self.stop_anim)
        self.export_btn.clicked.connect(self.export)
        self.export_gif_btn.clicked.connect(self.export_gif)

        self.figure = Figure(figsize=(6, 5))
        self.canvas = FigureCanvas(self.figure)
        self._anim = None
        self._rot_timer = None
        self._fg = "#ffffff"
        self._bg = "#1e1e1e"
        self._panel = "#2d2d30"

        form = QFormLayout()
        form.addRow(QLabel("z = f(x, y[, t])"), self.expr)
        row = QHBoxLayout()
        row.addWidget(QLabel("X min"))
        row.addWidget(self.xmin)
        row.addWidget(QLabel("X max"))
        row.addWidget(self.xmax)
        row.addWidget(QLabel("Y min"))
        row.addWidget(self.ymin)
        row.addWidget(QLabel("Y max"))
        row.addWidget(self.ymax)
        form.addRow(row)
        form.addRow(QLabel(i18n.t("frames", "Frames")),
                    self.frames)
        form.addRow(QLabel("FPS"), self.fps)
        form.addRow(QLabel("Cmap"), self.cmap)
        form.addRow(QLabel(""), self.show_contour)
        form.addRow(QLabel(i18n.t("levels", "Levels")),
                    self.contour_levels)
        form.addRow(QLabel(""), self.show_slice)
        form.addRow(QLabel(""), self.auto_rotate)
        form.addRow(QLabel(i18n.t("speed", "Speed")),
                    self.rotate_speed)

        row2 = QHBoxLayout()
        for b in (self.plot_btn, self.anim_btn,
                  self.stop_btn, self.export_btn,
                  self.export_gif_btn):
            row2.addWidget(b)

        main = QVBoxLayout(self)
        main.addLayout(form)
        main.addLayout(row2)
        main.addWidget(self.canvas, 1)

        self.auto_rotate.stateChanged.connect(
            self._on_rotate_toggle)

    # ==================================================================

    def _sample(self, t=0.0, n=60):
        x = np.linspace(float(self.xmin.text()),
                        float(self.xmax.text()), n)
        y = np.linspace(float(self.ymin.text()),
                        float(self.ymax.text()), n)
        X, Y = np.meshgrid(x, y)
        e = engine._parse(self.expr.text())
        syms = {s.name: s for s in e.free_symbols}
        args = []
        if "x" in syms:
            args.append(syms["x"])
        if "y" in syms:
            args.append(syms["y"])
        has_t = "t" in syms
        if has_t:
            args.append(syms["t"])
        f = sp.lambdify(args, e, modules=["numpy"])
        try:
            if has_t:
                Z = f(X, Y, t)
            else:
                Z = f(X, Y)
        except Exception:
            Z = f(X, Y)
        Z = np.asarray(Z)
        if np.iscomplexobj(Z):
            Z = np.where(np.abs(Z.imag) < 1e-9,
                         Z.real, np.nan)
        try:
            Z = Z.astype(float, copy=False)
        except Exception:
            Z = np.full(Z.shape, np.nan)
        Z[~np.isfinite(Z)] = np.nan
        return X, Y, Z

    def _prep_axes(self, ax):
        ax.set_facecolor(self._panel)
        self.figure.patch.set_facecolor(self._bg)
        try:
            ax.tick_params(colors=self._fg)
            for sp_ in ax.spines.values():
                sp_.set_color(self._fg)
        except Exception:
            pass

    def _draw(self, ax, X, Y, Z, cmap):
        surf = ax.plot_surface(X, Y, Z, cmap=cmap,
                               linewidth=0,
                               antialiased=True)
        if self.show_contour.isChecked():
            try:
                n = self.contour_levels.value()
                zmin = np.nanmin(Z)
                zmax = np.nanmax(Z)
                if (np.isfinite(zmin) and np.isfinite(zmax)
                        and zmax > zmin):
                    ax.contour(X, Y, Z, levels=n, zdir="z",
                               offset=np.nanmin(Z) - 0.5,
                               cmap=cmap, linewidths=0.6)
            except Exception:
                pass
        if self.show_slice.isChecked():
            try:
                n = Z.shape[0] // 2
                ax.plot_surface(X[n:n + 1, :],
                                Y[n:n + 1, :],
                                Z[n:n + 1, :],
                                color="#ff8800", alpha=0.6,
                                linewidth=0)
            except Exception:
                pass
        return surf

    def plot(self):
        try:
            self.figure.clear()
            ax = self.figure.add_subplot(
                111, projection="3d")
            self._prep_axes(ax)
            X, Y, Z = self._sample(0.0)
            self._draw(ax, X, Y, Z, self.cmap.currentText())
            self.canvas.draw()
            self.add_history(
                self.expr.text(), "plotted", module="plot3d")
        except Exception as e:
            log_exc(e, module="Plot3DPanel.plot")

    def start_anim(self):
        try:
            from matplotlib.animation import FuncAnimation
            self.figure.clear()
            ax = self.figure.add_subplot(
                111, projection="3d")
            self._prep_axes(ax)
            X, Y, Z0 = self._sample(0.0)
            surf = [None]
            cmap = self.cmap.currentText()

            def _update(frame):
                if surf[0] is not None:
                    surf[0].remove()
                t = (frame / max(1, self.frames.value())
                     * 2 * np.pi)
                _, _, Z = self._sample(t)
                surf[0] = self._draw(ax, X, Y, Z, cmap)
                return [surf[0]]

            self._anim = FuncAnimation(
                self.figure, _update,
                frames=self.frames.value(),
                interval=int(1000 / max(1, self.fps.value())),
                blit=False, repeat=True)
            self.canvas.draw()
            self.anim_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
        except Exception as e:
            log_exc(e, module="Plot3DPanel.start_anim")

    def stop_anim(self):
        try:
            if self._anim is not None:
                try:
                    self._anim.event_source.stop()
                except Exception:
                    pass
            self._anim = None
        finally:
            self.anim_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)

    def _on_rotate_toggle(self, state):
        if state:
            if self._rot_timer is None:
                self._rot_timer = QTimer(self)
                self._rot_timer.setInterval(80)
                self._rot_timer.timeout.connect(
                    self._auto_rotate_step)
            self._rot_timer.start()
        else:
            if self._rot_timer is not None:
                self._rot_timer.stop()

    def _auto_rotate_step(self):
        try:
            ax = self.figure.gca()
            if hasattr(ax, "azim"):
                ax.azim = ((ax.azim
                            + self.rotate_speed.value())
                           % 360)
                self.canvas.draw_idle()
        except Exception:
            pass

    def export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, self.i18n.t("export", "Export"),
            "plot3d.png",
            "PNG (*.png);;PDF (*.pdf);;SVG (*.svg)")
        if not path:
            return
        try:
            self.figure.savefig(
                path, dpi=150, bbox_inches="tight",
                facecolor=self._bg)
            QMessageBox.information(self, "OK", path)
        except Exception as e:
            log_exc(e, module="Plot3DPanel.export")
            QMessageBox.warning(self, "Error", str(e))

    def export_gif(self):
        path, _ = QFileDialog.getSaveFileName(
            self, self.i18n.t("export_gif", "Export GIF"),
            "plot3d.gif", "GIF (*.gif)")
        if not path:
            return
        try:
            from matplotlib.animation import (
                FuncAnimation, PillowWriter,
            )
            self.figure.clear()
            ax = self.figure.add_subplot(
                111, projection="3d")
            self._prep_axes(ax)
            X, Y, Z0 = self._sample(0.0)
            surf = [None]
            cmap = self.cmap.currentText()

            def _update(frame):
                if surf[0] is not None:
                    surf[0].remove()
                t = (frame / max(1, self.frames.value())
                     * 2 * np.pi)
                _, _, Z = self._sample(t)
                surf[0] = self._draw(ax, X, Y, Z, cmap)
                return [surf[0]]

            anim = FuncAnimation(
                self.figure, _update,
                frames=self.frames.value(),
                interval=int(1000 / max(1, self.fps.value())),
                blit=False)
            writer = PillowWriter(fps=self.fps.value())
            anim.save(path, writer=writer)
            QMessageBox.information(self, "OK", path)
        except Exception as e:
            log_exc(e, module="Plot3DPanel.export_gif")
            QMessageBox.warning(self, "Error", str(e))

    def closeEvent(self, e):
        try:
            self.stop_anim()
        except Exception:
            pass
        try:
            if self._rot_timer is not None:
                self._rot_timer.stop()
                self._rot_timer = None
        except Exception:
            pass
        try:
            self.figure.clear()
        except Exception:
            pass
        try:
            super().closeEvent(e)
        except Exception:
            pass

    def hideEvent(self, e):
        try:
            if (self._rot_timer is not None
                    and self._rot_timer.isActive()):
                self._rot_timer.stop()
        except Exception:
            pass
        try:
            super().hideEvent(e)
        except Exception:
            pass

    def set_theme_colors(self, fg, bg, panel):
        self._fg, self._bg, self._panel = fg, bg, panel


# ===========================================================================
# 管道
# ===========================================================================

class PipelinePanel(CalcPanel):
    """工作流管道面板：把多个计算步骤串起来。"""

    module_key = "pipeline"

    EXAMPLES = [
        "1 km | to m",
        "1 km | to m | * 2",
        "1 kg | to g | * 1000",
        "100 USD | to CNY",
        "5 | sqrt | round(2)",
        "0.1 | as fraction",
        "sin(30) | round(3)",
        "100 | * 1.15 | as percent",
        "0.5 | as percent | round(1)",
        "2 | + 3 | * 4 | ** 2",
    ]

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)
        self._calc_start = None

        self.expr = QLineEdit()
        draft = settings.get_draft(
            "pipeline_expr", "1 km | to m | * 2")
        self.expr.setText(draft)
        self.expr.textChanged.connect(
            lambda t: settings.set_draft("pipeline_expr", t))
        self.expr.returnPressed.connect(self.calc)
        self.primary_input = self.expr

        self.examples = QComboBox()
        self.examples.addItem(
            i18n.t("pipeline_examples", "示例…"), None)
        for ex in self.EXAMPLES:
            self.examples.addItem(ex, ex)
        self.examples.currentIndexChanged.connect(
            self._on_example_chosen)

        self.calc_btn = QPushButton(i18n.t("calc", "计算"))
        self.calc_btn.setMinimumHeight(32)
        self.calc_btn.clicked.connect(self.calc)

        self.cancel_btn = QPushButton(i18n.t("cancel", "取消"))
        self.cancel_btn.setEnabled(False)

        self.preview = InlinePreviewBar(
            calc_fn=self._preview_calc)
        self.preview.attach(
            self.expr,
            enabled_getter=lambda: bool(
                self.settings.get("inline_preview", True)))

        self.steps_table = QTableWidget(0, 3)
        self.steps_table.setHorizontalHeaderLabels([
            "#",
            i18n.t("pipeline_step", "步骤"),
            i18n.t("pipeline_step_result", "结果"),
        ])
        hdr = self.steps_table.horizontalHeader()
        hdr.setSectionResizeMode(
            0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        self.steps_table.verticalHeader().setVisible(False)
        self.steps_table.setSelectionBehavior(
            QAbstractItemView.SelectRows)
        self.steps_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers)
        self.steps_table.setFixedHeight(180)

        self.result = ResultView(i18n)

        top = QHBoxLayout()
        top.addWidget(QLabel(i18n.t("expr", "表达式")))
        top.addWidget(self.expr, 1)

        try:
            from ui.widgets.input import InputHistoryButton
            self.history_btn = InputHistoryButton(
                settings, i18n, "pipeline.expr", self)
            self.history_btn.attach(self.expr)
            top.addWidget(self.history_btn)
        except Exception:
            self.history_btn = None

        top.addWidget(self.examples)
        top.addWidget(self.make_kb_button())

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.calc_btn, 1)
        btn_row.addWidget(self.cancel_btn)

        self.hint = QLabel(i18n.t(
            "pipeline_hint",
            "管道：<初始> | <步骤1> | <步骤2> | ...    "
            "步骤示例：to m / * 2 / round(3) / as fraction"))
        self.hint.setStyleSheet(
            "color: #888; padding-left: 2px;")
        self.hint.setWordWrap(True)

        main = QVBoxLayout(self)
        main.addLayout(top)
        main.addWidget(self.preview)
        main.addWidget(self.hint)
        main.addLayout(btn_row)
        main.addWidget(QLabel(
            i18n.t("pipeline_steps", "步骤")))
        main.addWidget(self.steps_table)
        main.addWidget(QLabel(i18n.t("result", "结果")))
        main.addWidget(self.result, 1)

        install_panel_shortcuts(
            self,
            on_calc=self.calc,
            on_cancel=self.cancel_current,
            on_clear=self._clear,
            on_undo=self.undo,
            expr_widget=self.expr,
            history_getter=self._history_exprs,
        )

        sc_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        sc_undo.setContext(Qt.WidgetWithChildrenShortcut)
        sc_undo.activated.connect(self.undo)
        self._undo_sc = sc_undo

    # ==================================================================

    def _angle_mode(self) -> str:
        try:
            return self.settings.get(
                "angle_mode", "RAD") or "RAD"
        except Exception:
            return "RAD"

    def _base_path(self) -> str:
        try:
            mw = self.window()
            return getattr(mw, "base_path", "")
        except Exception:
            return ""

    def _rate_provider(self, amount, from_code, to_code):
        """货币换算回调，供 core.notebook 使用。"""
        base = self._base_path()
        if not base:
            raise RuntimeError("找不到 base_path")
        data = rates_mod.ensure_fresh(base)
        rates = data.get("rates", {}) or {}
        return rates_mod.convert(
            amount, from_code, to_code, rates)

    def _preview_calc(self, expr):
        s = (expr or "").strip()
        if not s:
            return None
        if not nb_mod.has_pipe(s):
            try:
                return engine.sci_eval(s, self._angle_mode())
            except Exception:
                return None
        try:
            r = nb_mod.execute_pipeline(
                s,
                angle_mode=self._angle_mode(),
                rate_provider=self._rate_provider,
            )
            if r.ok:
                return r.final_display or r.final
        except Exception:
            pass
        return None

    def _on_example_chosen(self, _):
        ex = self.examples.currentData()
        if ex:
            self.push_undo()
            self.expr.setText(ex)
            self.expr.setFocus()
            self.calc()

    # ==================================================================

    def _history_exprs(self):
        try:
            rows = self.history.list(
                module="pipeline", limit=50, order="id DESC")
            return [r["expr"] for r in rows if r.get("expr")]
        except Exception:
            return []

    def _clear(self):
        try:
            self.push_undo()
            self.expr.clear()
            self.steps_table.setRowCount(0)
            self.result.show_result("", "")
        except Exception:
            pass

    # ==================================================================

    def calc(self):
        expr = self.expr.text().strip()
        if not expr:
            self.result.show_error(
                InputError("表达式为空",
                           friendly_key="err_empty_expr"))
            return

        self.push_undo()
        self._calc_start = time.time()
        self.result.show_result(
            self.i18n.t("running", "计算中…"), "")
        self.steps_table.setRowCount(0)

        self.run(
            self._compute, expr,
            cancel_btn=self.cancel_btn,
            main_btn=self.calc_btn,
            on_done=self._on_done,
            on_fail=self._on_fail,
            on_cancel=self._on_cancel,
        )

    def _compute(self, expr):
        return nb_mod.execute_pipeline(
            expr,
            angle_mode=self._angle_mode(),
            rate_provider=self._rate_provider,
        )

    def _on_done(self, r: nb_mod.PipelineResult):
        try:
            self._fill_steps(r.steps)
        except Exception as e:
            log_exc(e, module="PipelinePanel._on_done.fill")

        elapsed = None
        if self._calc_start is not None:
            elapsed = time.time() - self._calc_start

        if not r.ok:
            err = InputError(r.error or "管道执行失败")
            self.result.show_error(
                err, elapsed=elapsed, retry_cb=self.calc)
            self.add_history(
                self.expr.text(),
                f"ERROR: {r.error}", module="pipeline")
            return

        text = r.final_display or str(r.final)
        try:
            latex = engine.format_result(r.final, "latex")
        except Exception:
            latex = ""

        self.result.show_result(text, latex, elapsed=elapsed)
        self.add_history(
            self.expr.text(), text, module="pipeline")

    def _fill_steps(self, steps):
        self.steps_table.setRowCount(0)
        for i, sr in enumerate(steps, 1):
            row = self.steps_table.rowCount()
            self.steps_table.insertRow(row)
            self.steps_table.setItem(
                row, 0, QTableWidgetItem(str(i)))
            self.steps_table.setItem(
                row, 1, QTableWidgetItem(sr.step.raw))
            if sr.ok:
                self.steps_table.setItem(
                    row, 2, QTableWidgetItem(sr.display))
            else:
                item = QTableWidgetItem(f"✗ {sr.error}")
                item.setForeground(Qt.red)
                self.steps_table.setItem(row, 2, item)

    def _on_fail(self, e):
        elapsed = None
        if self._calc_start is not None:
            elapsed = time.time() - self._calc_start
        self.result.show_error(
            e, elapsed=elapsed, retry_cb=self.calc)

    def _on_cancel(self):
        try:
            self.result.show_result(
                self.i18n.t("err_cancelled_task",
                            "计算已取消"), "")
        except Exception:
            pass

    def on_settings_changed(self, key=None):
        if key in (None, "angle_mode"):
            try:
                self.preview.refresh(self.expr.text())
            except Exception:
                pass


# ===========================================================================
# LaTeX 编辑器
# ===========================================================================

class LatexEditorPanel(CalcPanel):
    """LaTeX 编辑器面板。"""

    module_key = "latex"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        self.template = QComboBox()
        self.template.addItem(
            i18n.t("no_template", "— 无 —"), None)
        for k in sorted(latex_mod.TEMPLATES.keys()):
            self.template.addItem(k, k)
        self.template.currentIndexChanged.connect(
            self._load_template)

        self.input = QPlainTextEdit(
            r"\int_0^\infty e^{-x^2}\,dx = "
            r"\frac{\sqrt{\pi}}{2}")
        self.input.setFixedHeight(110)
        self.input.textChanged.connect(self._refresh)
        self.primary_input = self.input

        self.preview = LatexLabel(fontsize=18)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.preview)

        self.fontsize = QSpinBox()
        self.fontsize.setRange(8, 72)
        self.fontsize.setValue(18)
        self.fontsize.valueChanged.connect(self._refresh)

        b_copy = QPushButton(
            i18n.t("copy_latex", "复制 LaTeX"))
        b_copy.clicked.connect(self._copy)
        b_png = QPushButton(
            i18n.t("export_png", "导出 PNG"))
        b_png.clicked.connect(self.export_png)
        b_svg = QPushButton(
            i18n.t("export_svg", "导出 SVG"))
        b_svg.clicked.connect(self.export_svg)
        b_pdf = QPushButton(
            i18n.t("export_pdf", "导出 PDF"))
        b_pdf.clicked.connect(self.export_pdf)
        b_to_expr = QPushButton(
            i18n.t("latex_to_expr", "→ 表达式"))
        b_to_expr.setToolTip(i18n.t(
            "latex_to_expr_hint",
            "把当前 LaTeX 转换为 SymPy 表达式"))
        b_to_expr.clicked.connect(self.convert_to_expr)

        row = QHBoxLayout()
        row.addWidget(QLabel(i18n.t("template", "Template")))
        row.addWidget(self.template, 1)
        row.addWidget(QLabel(i18n.t("font_size", "Font")))
        row.addWidget(self.fontsize)
        for b in (b_copy, b_to_expr, b_png, b_svg, b_pdf):
            row.addWidget(b)

        lay = QVBoxLayout(self)
        lay.addLayout(row)
        lay.addWidget(QLabel("LaTeX"))
        lay.addWidget(self.input)
        lay.addWidget(QLabel(
            i18n.t("latex_preview", "Preview")))
        lay.addWidget(scroll, 1)

        self._refresh()

    # ==================================================================

    def _load_template(self, _):
        key = self.template.currentData()
        if not key:
            return
        self.input.setPlainText(
            latex_mod.TEMPLATES.get(key, ""))

    def _refresh(self):
        latex = self.input.toPlainText()
        self.preview.fontsize = self.fontsize.value()
        self.preview.set_latex(latex, latex)

    def set_theme_colors(self, fg, bg, panel):
        try:
            self.preview.set_color(fg)
        except Exception:
            pass

    # ==================================================================

    def _copy(self):
        try:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(
                self.input.toPlainText())
            QMessageBox.information(
                self, "OK",
                self.i18n.t("copied", "Copied"))
        except Exception as e:
            log_exc(e, module="LatexEditorPanel._copy")

    # ==================================================================

    def convert_to_expr(self):
        try:
            source = self.input.toPlainText().strip()
            if not source:
                QMessageBox.information(
                    self, "OK",
                    self.i18n.t("latex_empty",
                                "LaTeX 源码为空"))
                return

            r = latex_mod.latex_to_expr(source)
            if not r.ok:
                QMessageBox.warning(
                    self, "Error",
                    self.i18n.t("latex_parse_failed",
                                "LaTeX 解析失败：{err}")
                    .format(err=r.error or "unknown"))
                return

            dlg = _ExprResultDialog(
                self.i18n, source, r.expr,
                warnings=r.warnings, parent=self)
            if dlg.exec() == QDialog.Accepted:
                bus().send_to_sci.emit(r.expr)
                try:
                    from ui.shell import toast
                    toast(
                        self.window(),
                        self.i18n.t(
                            "latex_sent_to_sci",
                            "已发送到科学面板"),
                        level="success")
                except Exception:
                    pass
        except Exception as e:
            log_exc(e, module="LatexEditorPanel.convert_to_expr")
            QMessageBox.warning(self, "Error", str(e))

    # ==================================================================

    def export_png(self):
        path, _ = QFileDialog.getSaveFileName(
            self, self.i18n.t("export_png", "Export PNG"),
            "formula.png", "PNG (*.png)")
        if not path:
            return
        try:
            latex_mod.render_png(
                self.input.toPlainText(), path,
                fontsize=self.fontsize.value(),
                transparent=False)
            QMessageBox.information(self, "OK", path)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def export_svg(self):
        path, _ = QFileDialog.getSaveFileName(
            self, self.i18n.t("export_svg", "Export SVG"),
            "formula.svg", "SVG (*.svg)")
        if not path:
            return
        try:
            latex_mod.render_svg(
                self.input.toPlainText(), path,
                fontsize=self.fontsize.value())
            QMessageBox.information(self, "OK", path)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(
            self, self.i18n.t("export_pdf", "Export PDF"),
            "formula.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            with PdfPages(path) as pdf:
                fig = Figure(figsize=(8, 3))
                fig.text(
                    0.5, 0.5,
                    f"${self.input.toPlainText()}$",
                    ha="center", va="center",
                    fontsize=self.fontsize.value())
                pdf.savefig(fig)
            QMessageBox.information(self, "OK", path)
        except Exception as e:
            log_exc(e, module="LatexEditorPanel.export_pdf")
            QMessageBox.warning(self, "Error", str(e))


class _ExprResultDialog(QDialog):
    """展示 LaTeX → 表达式结果。"""

    def __init__(self, i18n, source, expr, warnings=None,
                 parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.expr = expr
        self.setWindowTitle(i18n.t(
            "latex_to_expr", "LaTeX → 表达式"))
        self.resize(560, 400)

        self.source_edit = QPlainTextEdit(source)
        self.source_edit.setReadOnly(True)
        self.source_edit.setFixedHeight(100)

        self.expr_edit = QLineEdit(expr)
        self.expr_edit.setReadOnly(True)

        self.warn_edit = QPlainTextEdit()
        self.warn_edit.setReadOnly(True)
        self.warn_edit.setFixedHeight(70)
        if warnings:
            self.warn_edit.setPlainText("\n".join(warnings))
        else:
            self.warn_edit.setVisible(False)

        b_copy = QPushButton(i18n.t("copy", "复制"))
        b_copy.clicked.connect(self._copy)
        b_send = QPushButton(
            i18n.t("send_to_sci", "发送到科学面板"))
        b_send.setDefault(True)
        b_send.clicked.connect(self.accept)
        b_cancel = QPushButton(i18n.t("close", "关闭"))
        b_cancel.clicked.connect(self.reject)

        row = QHBoxLayout()
        row.addWidget(b_copy)
        row.addStretch(1)
        row.addWidget(b_cancel)
        row.addWidget(b_send)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(i18n.t(
            "latex_source", "LaTeX 源码")))
        lay.addWidget(self.source_edit)
        lay.addWidget(QLabel(i18n.t(
            "latex_expr_result", "转换结果")))
        lay.addWidget(self.expr_edit)
        if warnings:
            lay.addWidget(QLabel(i18n.t(
                "latex_warnings", "警告")))
            lay.addWidget(self.warn_edit)
        lay.addLayout(row)

    def _copy(self):
        try:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(self.expr)
            QMessageBox.information(
                self, "OK",
                self.i18n.t("copied", "已复制"))
        except Exception:
            pass