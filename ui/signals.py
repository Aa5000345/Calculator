"""全局信号总线：跨面板通信，避免强耦合 MainWindow。"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class _Bus(QObject):
    # 发送 "1.5 km" 之类的带单位文本到单位面板
    send_to_unit = Signal(str)

    # 跨面板发送
    send_to_basic = Signal(str)          # 到基础计算面板（写入 expr）
    send_to_sci = Signal(str)            # 到科学计算面板（写入 expr）
    send_to_table = Signal(str)          # 到数据表（新行）
    send_to_snippet = Signal(str, str)   # (name, expr) 到片段管理器
    send_to_plot = Signal(str)           # 到绘图面板（新曲线）
    send_to_script = Signal(str) 
    clipboard_expr = Signal(str)
    # 键盘"等于"信号：让当前面板触发 calc()
    keyboard_equals = Signal()




_BUS = _Bus()


def bus() -> _Bus:
    return _BUS