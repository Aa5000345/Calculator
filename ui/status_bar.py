"""状态栏组件：显示当前面板 / 角度模式 / 内存值 / 汇率新鲜度 / 后台任务。

变更历史：
- 第 2 轮：初版
- 第 13 轮：微调（自动刷新间隔）
"""
from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QLabel, QStatusBar, QProgressBar,
)

from core.logger import log_exc


class CalcStatusBar(QStatusBar):
    """主窗口状态栏。

    永久部件（addPermanentWidget）从左到右：
    - 当前面板名
    - 角度模式（RAD / DEG）
    - 内存值
    - 汇率新鲜度
    - 后台任务指示
    """

    def __init__(self, settings, i18n, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n

        self._panel_label = QLabel("")
        self._angle_label = QLabel("RAD")
        self._memory_label = QLabel("内存: 0")
        self._rate_label = QLabel("汇率: —")
        self._task_label = QLabel("")
        self._task_bar = QProgressBar()
        self._task_bar.setRange(0, 0)   # 不确定进度
        self._task_bar.setFixedWidth(80)
        self._task_bar.setVisible(False)

        for w in (self._panel_label, self._angle_label,
                  self._memory_label, self._rate_label):
            w.setStyleSheet("padding: 0 8px; color: #aaa;")
            self.addPermanentWidget(w)

        self.addPermanentWidget(self._task_bar)
        self.addPermanentWidget(self._task_label)

        # 汇率新鲜度定时刷新（每 5 分钟）
        self._rate_timer = QTimer(self)
        self._rate_timer.setInterval(5 * 60 * 1000)
        self._rate_timer.timeout.connect(self._refresh_rate_status)
        self._rate_timer.start()
        self._refresh_rate_status()

        # 监听 settings 变化
        try:
            settings.add_listener(self._on_settings_changed)
        except Exception:
            pass
        self._on_settings_changed(None)

    # ------------------------------------------------------------------

    def set_panel_name(self, name: str):
        self._panel_label.setText(f"[{name}]")

    def set_angle_mode(self, mode: str):
        self._angle_label.setText(str(mode or "RAD").upper())

    def set_memory(self, value: float):
        try:
            v = float(value)
            if abs(v - round(v)) < 1e-9:
                self._memory_label.setText(
                    f"内存: {int(round(v))}")
            else:
                self._memory_label.setText(f"内存: {v:g}")
        except Exception:
            self._memory_label.setText("内存: —")

    def set_task_active(self, active: bool, text: str = ""):
        self._task_bar.setVisible(bool(active))
        self._task_label.setText(
            text or ("⏳ 计算中" if active else ""))

    # ------------------------------------------------------------------

    def _on_settings_changed(self, key=None):
        if key in (None, "angle_mode"):
            try:
                self.set_angle_mode(
                    self.settings.get("angle_mode", "RAD"))
            except Exception:
                pass
        if key in (None, "memory"):
            try:
                self.set_memory(self.settings.get("memory", 0))
            except Exception:
                pass

    def _refresh_rate_status(self):
        """显示汇率缓存新鲜度。"""
        try:
            from core import rates as rates_mod
            base = getattr(self.parent(), "base_path", None)
            if not base:
                self._rate_label.setText("汇率: —")
                return

            data = rates_mod.load_offline(base)
            updated = float(data.get("updated", 0) or 0)
            if updated <= 0:
                self._rate_label.setText("汇率: 离线")
                return

            age = time.time() - updated
            if age < 3600:
                text = f"{int(age / 60)} 分钟前"
            elif age < 86400:
                text = f"{int(age / 3600)} 小时前"
            else:
                text = f"{int(age / 86400)} 天前"
            self._rate_label.setText(f"汇率: {text}")
        except Exception:
            self._rate_label.setText("汇率: —")


__all__ = ["CalcStatusBar"]