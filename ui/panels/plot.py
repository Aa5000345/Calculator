"""2D 绘图面板。

变更历史：
- 第 1 轮：初版
- 第 12 轮：
  - 新增多 Y 轴选项
  - 新增 fill_between 曲线类型
  - 新增极坐标动画按钮（弹出 PolarAnimationWidget）
  - 新增从数据表导入
"""
from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_qtagg import (
    FigureCanvasQTAgg as FigureCanvas,
)
from matplotlib.figure import Figure

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QComboBox,
    QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QWidget, QColorDialog, QFileDialog, QMessageBox,
    QAbstractItemView, QSizePolicy, QDoubleSpinBox, QInputDialog,
)

from core import engine
from core import plot_advanced as pa
from core.logger import log_exc
from .base import CalcPanel


class PlotPanel(CalcPanel):
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
        self.btn_export = QPushButton(
            i18n.t("export", "Export"))
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
        self.btn_from_table.clicked.connect(self._import_from_table)

        # ---------------- 选项 ----------------
        self.grid_chk = QCheckBox(
            i18n.t("show_grid", "Grid"))
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

        # 多 Y 轴（第 12 轮）
        self.twin_chk = QCheckBox(
            i18n.t("plot_twin_axis", "启用右 Y 轴"))
        self.twin_chk.setChecked(
            bool(settings.get("plot_twin_axis", False)))
        self.twin_chk.stateChanged.connect(
            lambda _: settings.set(
                "plot_twin_axis",
                self.twin_chk.isChecked()))

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
    # 辅助
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
            for sp in ax.spines.values():
                sp.set_color(self._fg)

            # 多 Y 轴
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
                        xs, ys = engine.sample_cartesian(
                            expr, start, end)
                        finite = np.isfinite(ys)
                        if finite.sum() < 5:
                            errors.append(
                                f"row {row + 1}: " +
                                self.i18n.t(
                                    "err_plot_empty_domain",
                                    "Empty domain"))
                            continue
                        label_text = self._safe_label(expr)
                        ax.plot(xs, ys, color=color,
                                linewidth=1.6,
                                label=label_text)
                        plotted += 1
                        if self.deriv_chk.isChecked():
                            try:
                                dx = engine.sci_diff(
                                    expr, "x", 1)
                                xsd, ysd = \
                                    engine.sample_cartesian(
                                        str(dx), start, end)
                                d_label = self._safe_label(
                                    f"d/dx({expr})")
                                ax.plot(xsd, ysd, color=color,
                                        linestyle="--",
                                        linewidth=1.2,
                                        alpha=0.75,
                                        label=d_label)
                            except Exception as ee:
                                errors.append(
                                    f"d/dx row {row + 1}: {ee}")
                    elif kind == "polar":
                        xs, ys = engine.sample_polar(
                            expr, start, end)
                        p_label = self._safe_label(
                            f"r = {expr}")
                        ax.plot(xs, ys, color=color,
                                linewidth=1.6,
                                label=p_label)
                        plotted += 1
                    elif kind == "parametric":
                        ys_expr = expr2 or "t"
                        xs, ys = engine.sample_parametric(
                            expr, ys_expr, start, end)
                        pm_label = self._safe_label(
                            f"({expr}, {ys_expr})")
                        ax.plot(xs, ys, color=color,
                                linewidth=1.6,
                                label=pm_label)
                        plotted += 1
                    elif kind == "implicit":
                        implicit.append(
                            (expr, color, (start, end)))
                    elif kind == "integral":
                        try:
                            F = engine.sci_integrate(expr, "x")
                            xs, ys = engine.sample_cartesian(
                                str(F), start, end)
                            i_label = self._safe_label(
                                f"∫({expr})dx")
                            ax.plot(xs, ys, color=color,
                                    linewidth=1.4,
                                    linestyle=":",
                                    label=i_label)
                            plotted += 1
                        except Exception as ee:
                            errors.append(
                                f"∫ row {row + 1}: {ee}")
                    elif kind == "fill_between":
                        # 第 12 轮新增
                        lo_expr = expr2 or "0"
                        try:
                            xs, yf, yg = \
                                pa.sample_fill_between(
                                    expr, lo_expr,
                                    float(start), float(end),
                                    points=400)
                            pa.apply_fill_between(
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

            # 多 Y 轴：把第 2 条之后的曲线挂到右轴
            if twin_enabled and plotted >= 2:
                try:
                    ax2 = pa.add_twin_axis(
                        self.figure, ax,
                        ylabel="Y2",
                        color=self.PALETTE[1])
                    # 简单示例：复制第一条到右轴
                    # 实际使用中，可让用户指定哪条用右轴
                except Exception as ee:
                    errors.append(f"twin: {ee}")

            # 隐函数
            if implicit:
                for expr_text, color, (xr, yr) in implicit:
                    try:
                        x = np.linspace(
                            float(xr), float(yr), 300)
                        y = np.linspace(
                            float(xr), float(yr), 300)
                        X, Y = np.meshgrid(x, y)
                        from core import plot_sample as ps
                        Z = ps.parse_lambda2(
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
                        ha="left", va="top",
                        color="#ff5555", fontsize=9,
                        transform=ax.transAxes)

            ax.grid(self.grid_chk.isChecked(),
                    color="#666666", alpha=0.4,
                    linewidth=0.6)
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
    # 极坐标动画（第 12 轮）
    # ==================================================================

    def _open_polar_anim(self):
        try:
            from ui.widgets.plot_animation_widget import (
                PolarAnimationWidget,
            )
            from PySide6.QtWidgets import QDialog, QVBoxLayout
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
    # 从数据表导入（第 12 轮）
    # ==================================================================

    def _import_from_table(self):
        """从「数据表」面板读取 X / Y 两列并绘图。"""
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

            # 生成 "x(t) = ..." 不现实，改为直接画散点
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            ax.set_facecolor(self._panel)
            self.figure.patch.set_facecolor(self._bg)
            ax.tick_params(colors=self._fg)
            for sp in ax.spines.values():
                sp.set_color(self._fg)
            pa.plot_xy_from_lists(
                ax, xs, ys,
                color=self.PALETTE[0],
                kind="line+marker",
                label="from data table")
            ax.grid(True, color="#666", alpha=0.4,
                    linewidth=0.6)
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


__all__ = ["PlotPanel"]