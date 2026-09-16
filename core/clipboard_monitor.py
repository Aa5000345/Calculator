"""剪贴板智能识别：判断文本是否像一条可计算的表达式。

策略：只做"是否像"，不做"能不能算"——真正是否可算交给引擎。
识别通过的文本由上层决定怎么用（弹提示、发基础面板、静默忽略等）。
"""
from __future__ import annotations

import re

from PySide6.QtCore import QObject, QTimer

# 允许的字符集（含常见 Unicode 运算符）
_ALLOWED_CHARS = re.compile(
    r"^[\d\s\+\-\*/%\(\)\^\.\,\!\&\|\<\>\=\u00d7\u00f7\u2212\u03c0"
    r"a-zA-Z_]+$"
)

# 必须包含至少一个数字
_HAS_DIGIT = re.compile(r"\d")

# 至少包含一个运算符
_HAS_OP = re.compile(r"[\+\-\*/%\^]|×|÷|−")

# 明显不是表达式的模式
_NOT_EXPR_PATTERNS = [
    re.compile(r"^https?://", re.I),           # URL
    re.compile(r"^[\w\.\-]+@[\w\.\-]+$"),      # 邮箱
    re.compile(r"^[A-Za-z]:[\\/]"),            # Windows 路径
    re.compile(r"^/(?:[^\s/]+/)+[^\s/]+$"),    # Unix 路径
    re.compile(r"^[\d\-]{7,}$"),               # 长数字串（身份证、电话）
    re.compile(r"^0x[0-9A-Fa-f]+$"),           # 单独的 hex
]

# 出现这些函数名说明用户很可能在写算式
_FUNCTION_HINTS = (
    "sqrt", "sin", "cos", "tan", "log", "ln", "exp",
    "abs", "factorial", "pi", "asin", "acos", "atan",
)


def is_expression(text: str) -> bool:
    """判断文本是否像一条可计算的表达式。

    全部条件满足才返回 True：
    1. 长度 2 ~ 200
    2. 单行（不含换行符）
    3. 字符集在白名单内
    4. 至少包含一个数字
    5. 至少包含一个运算符或函数名
    6. 不匹配明显的非表达式模式
    7. 不是单独的纯数字 / 小数
    """
    if not text:
        return False
    s = str(text).strip()
    if not (2 <= len(s) <= 200):
        return False
    if "\n" in s or "\r" in s:
        return False

    for pat in _NOT_EXPR_PATTERNS:
        if pat.match(s):
            return False

    if not _ALLOWED_CHARS.match(s):
        return False

    if not _HAS_DIGIT.search(s):
        return False

    has_op = bool(_HAS_OP.search(s))
    has_fn = any(fn in s.lower() for fn in _FUNCTION_HINTS)
    if not (has_op or has_fn):
        return False

    # 排除单独的数字 / 小数
    if re.match(r"^-?\d+(\.\d+)?$", s):
        return False

    return True


class ClipboardMonitor(QObject):
    """剪贴板监听器：轮询系统剪贴板，识别到表达式时触发回调。

    - 使用 QTimer 轮询（跨平台一致，比 QClipboard.dataChanged 更可靠）
    - 自动去重：相同文本不重复触发
    - 线程/生命周期：由 parent（通常是面板）托管，面板销毁即释放
    """

    def __init__(self, parent=None, interval_ms: int = 700):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(int(interval_ms))
        self._timer.timeout.connect(self._poll)
        self._last_text = ""
        self._callback = None

    def start(self, callback):
        """开始监听；callback(text) 在识别到表达式时被调用。"""
        self._callback = callback
        try:
            from PySide6.QtWidgets import QApplication
            self._last_text = QApplication.clipboard().text() or ""
        except Exception:
            self._last_text = ""
        self._timer.start()

    def stop(self):
        try:
            self._timer.stop()
        except Exception:
            pass

    def is_running(self) -> bool:
        try:
            return self._timer.isActive()
        except Exception:
            return False

    def _poll(self):
        try:
            from PySide6.QtWidgets import QApplication
            text = QApplication.clipboard().text() or ""
        except Exception:
            return
        if text == self._last_text:
            return
        self._last_text = text
        if not is_expression(text):
            return
        cb = self._callback
        if cb is None:
            return
        try:
            cb(text)
        except Exception:
            pass