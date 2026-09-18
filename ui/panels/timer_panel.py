"""计时器 / 秒表 / 番茄钟。"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QTabWidget,
    QWidget, QSpinBox, QFormLayout, QListWidget, QListWidgetItem,
)

from .base import CalcPanel


def _fmt(seconds):
    s = max(0, int(seconds))
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class TimerPanel(CalcPanel):
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

        b_start = QPushButton(
            self.i18n.t("start", "开始"))
        b_pause = QPushButton(
            self.i18n.t("pause", "暂停"))
        b_reset = QPushButton(
            self.i18n.t("reset", "重置"))
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
                from PySide6.QtWidgets import QApplication
                QApplication.beep()
            except Exception:
                pass
        else:
            self.cd_display.setText(_fmt(self._cd_left))

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

        b_start = QPushButton(
            self.i18n.t("start", "开始"))
        b_lap = QPushButton(self.i18n.t("lap", "计次"))
        b_reset = QPushButton(
            self.i18n.t("reset", "重置"))
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
            self._sw_btn.setText(
                self.i18n.t("start", "开始"))
        else:
            self._sw_timer.start()
            self._sw_running = True
            self._sw_btn.setText(
                self.i18n.t("pause", "暂停"))

    def _sw_tick(self):
        self._sw_ms += 100
        self.sw_display.setText(_fmt(self._sw_ms / 1000))

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

        b_start = QPushButton(
            self.i18n.t("start", "开始"))
        b_reset = QPushButton(
            self.i18n.t("reset", "重置"))
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
                from PySide6.QtWidgets import QApplication
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


__all__ = ["TimerPanel"]