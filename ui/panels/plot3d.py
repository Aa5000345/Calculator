"""3D 绘图面板。"""
from __future__ import annotations

import numpy as np
import sympy as sp
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QComboBox,
    QCheckBox, QSpinBox, QFormLayout, QFileDialog, QMessageBox,
)

from core import engine
from core.logger import log_exc
from .base import CalcPanel


class Plot3DPanel(CalcPanel):
    module_key = "plot3d"

    def __init__(self, settings, i18n, history):
        super().__init__(settings, i18n, history)

        self.expr = QLineEdit("sin(x)*cos(y)")
        self.xmin = QLineEdit("-5"); self.xmax = QLineEdit("5")
        self.ymin = QLineEdit("-5"); self.ymax = QLineEdit("5")
        self.frames = QSpinBox(); self.frames.setRange(2, 300); self.frames.setValue(60)
        self.fps = QSpinBox(); self.fps.setRange(1, 60); self.fps.setValue(20)

        self.cmap = QComboBox()
        for k in ("viridis", "plasma", "inferno", "magma", "cividis",
                  "jet", "coolwarm", "RdBu", "turbo", "terrain"):
            self.cmap.addItem(k)
        self.show_contour = QCheckBox(i18n.t("show_contour", "Contour"))
        self.contour_levels = QSpinBox()
        self.contour_levels.setRange(3, 40); self.contour_levels.setValue(10)
        self.show_slice = QCheckBox(i18n.t("show_slice", "Slice at y=0"))
        self.auto_rotate = QCheckBox(i18n.t("auto_rotate", "Auto rotate"))
        self.rotate_speed = QSpinBox()
        self.rotate_speed.setRange(1, 30); self.rotate_speed.setValue(5)

        self.plot_btn = QPushButton(i18n.t("draw", "Plot"))
        self.anim_btn = QPushButton(i18n.t("start_anim", "Play"))
        self.stop_btn = QPushButton(i18n.t("stop_anim", "Stop"))
        self.stop_btn.setEnabled(False)
        self.export_btn = QPushButton(i18n.t("export", "Export"))
        self.export_gif_btn = QPushButton(i18n.t("export_gif", "Export GIF"))

        self.plot_btn.clicked.connect(self.plot)
        self.anim_btn.clicked.connect(self.start_anim)
        self.stop_btn.clicked.connect(self.stop_anim)
        self.export_btn.clicked.connect(self.export)
        self.export_gif_btn.clicked.connect(self.export_gif)

        self.figure = Figure(figsize=(6, 5))
        self.canvas = FigureCanvas(self.figure)
        self._anim = None
        self._rot_timer = None
        self._fg = "#ffffff"; self._bg = "#1e1e1e"; self._panel = "#2d2d30"

        form = QFormLayout()
        form.addRow(QLabel("z = f(x, y[, t])"), self.expr)
        row = QHBoxLayout()
        row.addWidget(QLabel("X min")); row.addWidget(self.xmin)
        row.addWidget(QLabel("X max")); row.addWidget(self.xmax)
        row.addWidget(QLabel("Y min")); row.addWidget(self.ymin)
        row.addWidget(QLabel("Y max")); row.addWidget(self.ymax)
        form.addRow(row)
        form.addRow(QLabel(i18n.t("frames", "Frames")), self.frames)
        form.addRow(QLabel("FPS"), self.fps)
        form.addRow(QLabel("Cmap"), self.cmap)
        form.addRow(QLabel(""), self.show_contour)
        form.addRow(QLabel(i18n.t("levels", "Levels")), self.contour_levels)
        form.addRow(QLabel(""), self.show_slice)
        form.addRow(QLabel(""), self.auto_rotate)
        form.addRow(QLabel(i18n.t("speed", "Speed")), self.rotate_speed)

        row2 = QHBoxLayout()
        for b in (self.plot_btn, self.anim_btn, self.stop_btn,
                  self.export_btn, self.export_gif_btn):
            row2.addWidget(b)

        main = QVBoxLayout(self)
        main.addLayout(form)
        main.addLayout(row2)
        main.addWidget(self.canvas, 1)

        self.auto_rotate.stateChanged.connect(self._on_rotate_toggle)

    def _sample(self, t=0.0, n=60):
        x = np.linspace(float(self.xmin.text()), float(self.xmax.text()), n)
        y = np.linspace(float(self.ymin.text()), float(self.ymax.text()), n)
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
        # 修复：先判定复数，再转 float
        Z = np.asarray(Z)
        if np.iscomplexobj(Z):
            Z = np.where(np.abs(Z.imag) < 1e-9, Z.real, np.nan)
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
            for sp in ax.spines.values():
                sp.set_color(self._fg)
        except Exception:
            pass

    def _draw(self, ax, X, Y, Z, cmap):
        surf = ax.plot_surface(X, Y, Z, cmap=cmap, linewidth=0, antialiased=True)
        if self.show_contour.isChecked():
            try:
                n = self.contour_levels.value()
                zmin = np.nanmin(Z); zmax = np.nanmax(Z)
                if np.isfinite(zmin) and np.isfinite(zmax) and zmax > zmin:
                    ax.contour(X, Y, Z, levels=n, zdir="z",
                               offset=np.nanmin(Z) - 0.5,
                               cmap=cmap, linewidths=0.6)
            except Exception:
                pass
        if self.show_slice.isChecked():
            try:
                n = Z.shape[0] // 2
                ax.plot_surface(X[n:n + 1, :], Y[n:n + 1, :], Z[n:n + 1, :],
                                color="#ff8800", alpha=0.6, linewidth=0)
            except Exception:
                pass
        return surf

    def plot(self):
        try:
            self.figure.clear()
            ax = self.figure.add_subplot(111, projection="3d")
            self._prep_axes(ax)
            X, Y, Z = self._sample(0.0)
            self._draw(ax, X, Y, Z, self.cmap.currentText())
            self.canvas.draw()
            self.add_history(self.expr.text(), "plotted", module="plot3d")
        except Exception as e:
            log_exc(e, module="Plot3DPanel.plot")

    def start_anim(self):
        try:
            from matplotlib.animation import FuncAnimation
            self.figure.clear()
            ax = self.figure.add_subplot(111, projection="3d")
            self._prep_axes(ax)
            X, Y, Z0 = self._sample(0.0)
            surf = [None]
            cmap = self.cmap.currentText()

            def _update(frame):
                if surf[0] is not None:
                    surf[0].remove()
                t = frame / max(1, self.frames.value()) * 2 * np.pi
                _, _, Z = self._sample(t)
                surf[0] = self._draw(ax, X, Y, Z, cmap)
                return [surf[0]]

            self._anim = FuncAnimation(
                self.figure, _update, frames=self.frames.value(),
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
                self._rot_timer.timeout.connect(self._auto_rotate_step)
            self._rot_timer.start()
        else:
            if self._rot_timer is not None:
                self._rot_timer.stop()

    def _auto_rotate_step(self):
        try:
            ax = self.figure.gca()
            if hasattr(ax, "azim"):
                ax.azim = (ax.azim + self.rotate_speed.value()) % 360
                self.canvas.draw_idle()
        except Exception:
            pass

    def export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, self.i18n.t("export", "Export"), "plot3d.png",
            "PNG (*.png);;PDF (*.pdf);;SVG (*.svg)")
        if not path:
            return
        try:
            self.figure.savefig(path, dpi=150, bbox_inches="tight",
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
            from matplotlib.animation import FuncAnimation, PillowWriter
            self.figure.clear()
            ax = self.figure.add_subplot(111, projection="3d")
            self._prep_axes(ax)
            X, Y, Z0 = self._sample(0.0)
            surf = [None]; cmap = self.cmap.currentText()

            def _update(frame):
                if surf[0] is not None:
                    surf[0].remove()
                t = frame / max(1, self.frames.value()) * 2 * np.pi
                _, _, Z = self._sample(t)
                surf[0] = self._draw(ax, X, Y, Z, cmap)
                return [surf[0]]

            anim = FuncAnimation(
                self.figure, _update, frames=self.frames.value(),
                interval=int(1000 / max(1, self.fps.value())), blit=False)
            writer = PillowWriter(fps=self.fps.value())
            anim.save(path, writer=writer)
            QMessageBox.information(self, "OK", path)
        except Exception as e:
            log_exc(e, module="Plot3DPanel.export_gif")
            QMessageBox.warning(self, "Error", str(e))

    def set_theme_colors(self, fg, bg, panel):
        self._fg, self._bg, self._panel = fg, bg, panel