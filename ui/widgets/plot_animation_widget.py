"""绘图动画组件：极坐标动画 + GIF 导出。

被 ui/panels/plot.py 作为子组件调用，或单独使用。
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget,
    QCheckBox, QComboBox,
)

from core import plot_advanced as pa
from core.logger import log_exc


class _GifWorker(QThread):
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            path = self._fn(*self._args, **self._kwargs)
            if not self._cancelled:
                self.done.emit(str(path))
        except Exception as e:  # noqa: BLE001
            if not self._cancelled:
                self.failed.emit(str(e))


class PolarAnimationWidget(QWidget):
    """极坐标动画 + GIF 导出。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: _GifWorker | None = None

        self.expr = QLineEdit("1 + 0.5*cos(6*theta)")
        self.tmin = QLineEdit("0")
        self.tmax = QLineEdit("6.283185307")
        self.frames = QSpinBox()
        self.frames.setRange(2, 600)
        self.frames.setValue(60)
        self.fps = QSpinBox()
        self.fps.setRange(1, 60)
        self.fps.setValue(20)
        self.points = QSpinBox()
        self.points.setRange(50, 2000)
        self.points.setValue(400)

        self.animate_time = QCheckBox(
            "让 `t` 随时间变化（表达式里可用 t）")
        self.line_color = QLineEdit("#007acc")
        self.bg_color = QLineEdit("#1e1e1e")
        self.fg_color = QLineEdit("#ffffff")

        b_preview = QPushButton("预览 GIF（保存后查看）")
        b_preview.clicked.connect(self._export)
        b_stop = QPushButton("取消")
        b_stop.setEnabled(False)
        b_stop.clicked.connect(self._cancel)
        self._stop_btn = b_stop

        self.status = QLabel("")
        self.status.setStyleSheet("color: #888;")

        f = QFormLayout()
        f.addRow(QLabel("极坐标 r(theta)"), self.expr)
        f.addRow(QLabel("theta min"), self.tmin)
        f.addRow(QLabel("theta max"), self.tmax)
        f.addRow(QLabel("帧数"), self.frames)
        f.addRow(QLabel("FPS"), self.fps)
        f.addRow(QLabel("采样点数"), self.points)
        f.addRow(QLabel(""), self.animate_time)
        f.addRow(QLabel("线条颜色"), self.line_color)
        f.addRow(QLabel("背景色"), self.bg_color)
        f.addRow(QLabel("前景色"), self.fg_color)

        row = QHBoxLayout()
        row.addWidget(b_preview, 1)
        row.addWidget(b_stop)

        lay = QVBoxLayout(self)
        lay.addLayout(f)
        lay.addLayout(row)
        lay.addWidget(self.status)
        lay.addStretch(1)

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 GIF", "polar.gif", "GIF (*.gif)")
        if not path:
            return
        if self._worker is not None and self._worker.isRunning():
            return

        self._stop_btn.setEnabled(True)
        self.status.setText("正在渲染…")

        try:
            tmin = float(self.tmin.text())
            tmax = float(self.tmax.text())
        except ValueError:
            QMessageBox.warning(self, "Error", "theta 范围非法")
            self._stop_btn.setEnabled(False)
            return

        self._worker = _GifWorker(
            pa.save_polar_gif,
            self.expr.text(),
            path,
            tmin=tmin, tmax=tmax,
            frames=self.frames.value(),
            points=self.points.value(),
            fps=self.fps.value(),
            animate_time=self.animate_time.isChecked(),
            line_color=self.line_color.text().strip() or "#007acc",
            bg_color=self.bg_color.text().strip() or "#1e1e1e",
            fg_color=self.fg_color.text().strip() or "#ffffff",
        )
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_done(self, path: str):
        self.status.setText(f"✓ {path}")
        QMessageBox.information(self, "OK", path)

    def _on_failed(self, msg: str):
        self.status.setText(f"✗ {msg}")
        QMessageBox.warning(self, "Error", msg)

    def _on_finished(self):
        self._stop_btn.setEnabled(False)
        self._worker = None

    def _cancel(self):
        if self._worker is not None:
            self._worker.cancel()

    def closeEvent(self, e):
        try:
            if self._worker is not None and self._worker.isRunning():
                self._worker.cancel()
                self._worker.wait(2000)
        except Exception:
            pass
        super().closeEvent(e)