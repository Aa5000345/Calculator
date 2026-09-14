"""全局信号总线：跨面板通信，避免强耦合 MainWindow。"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class _Bus(QObject):
    # 发送 "1.5 km" 之类的带单位文本到单位面板
    send_to_unit = Signal(str)


_BUS = _Bus()


def bus() -> _Bus:
    return _BUS