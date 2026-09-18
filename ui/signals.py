"""全局信号总线：跨面板通信，避免强耦合 MainWindow。

变更历史：
- 第 1 轮：初版
- 第 12 轮：新增 send_to_data_ops（数据运算面板）
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class _Bus(QObject):
    # 发送 "1.5 km" 之类的带单位文本到单位面板
    send_to_unit = Signal(str)

    # 跨面板发送
    send_to_basic = Signal(str)          # 到基础计算面板
    send_to_sci = Signal(str)            # 到科学计算面板
    send_to_table = Signal(str)          # 到数据表（新行）
    send_to_snippet = Signal(str, str)   # (name, expr) 到片段
    send_to_plot = Signal(str)           # 到绘图面板
    send_to_script = Signal(str)         # 到脚本面板
    send_to_data_ops = Signal(str)       # 到数据运算面板（第 12 轮新增）

    # 剪贴板识别到表达式
    clipboard_expr = Signal(str)

    # 键盘"等于"信号：让当前面板触发 calc()
    keyboard_equals = Signal()


_BUS = _Bus()


def bus() -> _Bus:
    return _BUS


__all__ = ["bus"]