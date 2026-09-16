"""自定义 widget 集合。"""
from __future__ import annotations

from .focus_tracker import FocusTracker

from .keyboard_layouts import (
    Key, Layout,
    get_layout, get_layout_name, all_module_keys,
    LAYOUT_BASIC, LAYOUT_SCIENTIFIC, LAYOUT_DEFAULT,
    LAYOUT_MATRIX, LAYOUT_PLOT, LAYOUT_PLOT3D, LAYOUT_FINANCE,
    LAYOUT_DATE, LAYOUT_UNIT, LAYOUT_CURRENCY, LAYOUT_BASE,
    LAYOUT_BITS, LAYOUT_CRYPTO, LAYOUT_LATEX, LAYOUT_SCRIPT,
)
from .key_button import KeyButton

# ---------------------------------------------------------------------------
# 向后兼容别名（老代码 import COMPACT_LAYOUT / SCI_LAYOUT 时不再报错）
# ⚠ 关键点：别名在这里定义，不再从 keyboard_layouts 导入
# ---------------------------------------------------------------------------
COMPACT_LAYOUT = LAYOUT_BASIC
SCI_LAYOUT = LAYOUT_SCIENTIFIC

# 手写 / OCR（延迟加载，import 时不会真正实例化 Qt 对象）
try:
    from .handwriting import HandwritingDialog, _Canvas as HandwritingCanvas
except Exception:
    HandwritingDialog = None
    HandwritingCanvas = None

try:
    from .ocr_input import OCRInputDialog
except Exception:
    OCRInputDialog = None


__all__ = [
    "FocusTracker",
    "Key", "Layout",
    "get_layout", "get_layout_name", "all_module_keys",
    "KeyButton",
    "LAYOUT_BASIC", "LAYOUT_SCIENTIFIC", "LAYOUT_DEFAULT",
    "LAYOUT_MATRIX", "LAYOUT_PLOT", "LAYOUT_PLOT3D", "LAYOUT_FINANCE",
    "LAYOUT_DATE", "LAYOUT_UNIT", "LAYOUT_CURRENCY", "LAYOUT_BASE",
    "LAYOUT_BITS", "LAYOUT_CRYPTO", "LAYOUT_LATEX", "LAYOUT_SCRIPT",
    "COMPACT_LAYOUT", "SCI_LAYOUT",
    "HandwritingDialog", "HandwritingCanvas", "OCRInputDialog",
]